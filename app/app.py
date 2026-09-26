"""WeLook sales-research UI. Reads a published, compact DuckDB snapshot only."""

from __future__ import annotations

import csv
from io import StringIO
import os
from pathlib import Path

import duckdb
import streamlit as st


DEFAULT_DB = Path(__file__).resolve().parent / "data" / "welook_serving.duckdb"
DB = Path(os.environ.get("WELOOK_SERVING_DB", DEFAULT_DB))
st.set_page_config(page_title="WeLook · Account intelligence", page_icon="◉", layout="wide")

SIGNAL_CASE = """CASE
    WHEN a.directly_supported_verified_observation_count > 0 THEN 'Direct verified label'
    WHEN a.verified_vulnerability_association_count > 0 THEN 'Verified label; check operator'
    WHEN a.vulnerability_association_count > 0 THEN 'Vulnerability metadata'
    WHEN a.admin_or_login_observation_count > 0 THEN 'Admin/login page'
    ELSE 'Observed service' END"""


def query(sql: str, params: list | None = None):
    with duckdb.connect(str(DB), read_only=True) as con:
        return con.execute(sql, params or []).fetchdf()


def account_rows(search: str, view: str, signal: str, direct_only: bool,
                 attribution: str, limit: int = 100):
    conditions = ["1=1"]
    params: list = []
    if search:
        conditions.append("a.candidate_domain ILIKE ?")
        params.append("%" + search.strip() + "%")
    if view == "Investigate first":
        conditions.append("a.priority_tier = 'investigate_first'")
    elif view == "Needs research":
        conditions.append("a.priority_tier = 'research'")
    elif view == "AI notes":
        conditions.append("assessment.candidate_domain IS NOT NULL")
    if attribution != "Any match":
        conditions.append("a.attribution_status = ?")
        params.append(attribution)
    if direct_only:
        conditions.append("a.attribution_status = 'supported'")
    signal_columns = {
        "Direct verified label": "a.directly_supported_verified_observation_count",
        "Any scanner-verified label": "a.verified_vulnerability_association_count",
        "Admin/login page": "a.admin_or_login_observation_count",
        "Vulnerability metadata": "a.vulnerability_association_count",
    }
    if signal != "Any signal":
        conditions.append(f"{signal_columns[signal]} > 0")
    params.append(limit)
    return query(
        "SELECT a.candidate_domain, a.priority_tier, a.attribution_status, "
        f"{SIGNAL_CASE} AS research_signal, a.investigation_score, a.last_observed_at "
        "FROM accounts a LEFT JOIN assessments assessment USING (candidate_domain) WHERE " + " AND ".join(conditions) +
        " ORDER BY CASE a.priority_tier WHEN 'investigate_first' THEN 0 "
        "WHEN 'research' THEN 1 ELSE 2 END, a.investigation_score DESC, a.candidate_domain LIMIT ?",
        params,
    )


def account_detail(domain: str):
    account = query("SELECT * FROM accounts WHERE candidate_domain = ?", [domain])
    assessment = query("SELECT * FROM assessments WHERE candidate_domain = ?", [domain])
    evidence = query(
        "SELECT 'source-record-' || source_record_id AS evidence_id, source_line, observed_at, ip_address, port, infrastructure_org, "
        "infrastructure_country, product, http_host, http_title, certificate_cn, "
        "vulnerability_count, verified_vulnerability_count, http_domain_match, cert_domain_match, "
        "attribution_status, evidence_score FROM evidence "
        "WHERE candidate_domain = ? ORDER BY evidence_score DESC, observed_at DESC",
        [domain],
    )
    return account.iloc[0], evidence, assessment


def shortlist_csv(domains: list[str]) -> str:
    if not domains:
        return ""
    placeholders = ",".join("?" for _ in domains)
    rows = query(
        "SELECT a.candidate_domain, a.priority_tier, a.attribution_status, "
        f"{SIGNAL_CASE} AS research_signal, a.last_observed_at, "
        "(SELECT 'source-record-' || e.source_record_id FROM evidence e "
        " WHERE e.candidate_domain = a.candidate_domain "
        " ORDER BY e.evidence_score DESC, e.observed_at DESC, e.source_record_id LIMIT 1) "
        "AS example_evidence_id, a.next_action, "
        "'Unverified candidate domain' AS identity_status "
        f"FROM accounts a WHERE a.candidate_domain IN ({placeholders}) "
        "ORDER BY CASE a.priority_tier WHEN 'investigate_first' THEN 0 "
        "WHEN 'research' THEN 1 ELSE 2 END, a.investigation_score DESC",
        domains,
    )
    out = StringIO()
    writer = csv.writer(out)
    writer.writerow(list(rows.columns))
    writer.writerows(rows.itertuples(index=False, name=None))
    return out.getvalue()


def research_reason(row) -> str:
    if row.directly_supported_verified_observation_count:
        count = int(row.directly_supported_verified_observation_count)
        return (f"{count} service observation{'s have' if count != 1 else ' has'} a "
                "scanner-verified vulnerability label and both HTTP-host and certificate-domain matches.")
    if row.verified_vulnerability_association_count:
        return ("A scanner-verified vulnerability label appears in associated observations, "
                "but none of those labelled observations has both direct domain matches.")
    if row.vulnerability_association_count:
        return ("Associated observations contain vulnerability metadata. The directly matched "
                "evidence has no scanner-verified label.")
    if row.admin_or_login_observation_count:
        return "An admin/login page title was observed. A login page alone is not evidence of a weakness."
    return "Internet-facing service observations reference this domain; their operator and relevance need research."


if not DB.exists():
    st.error("The published serving snapshot is missing. Run the pipeline and serving export first.")
    st.stop()

if "shortlist" not in st.session_state:
    st.session_state.shortlist = []

info = query("SELECT * FROM build_info").iloc[0]
first_count = int(query("SELECT count(*) AS n FROM accounts WHERE priority_tier = 'investigate_first'").iloc[0].n)
st.caption("WELOOK  /  CYBERSECURITY ACCOUNT RESEARCH")
st.title("Know who to investigate next.")
st.write("Filter candidate domains, inspect the evidence, and save a short research list.")

c1, c2, c3 = st.columns(3)
c1.metric("Candidate domains analysed", f"{int(info.candidate_accounts):,}")
c2.metric("Investigate first", f"{first_count:,}")
c3.metric("Available to explore", f"{int(info.hosted_accounts):,}")
st.caption(
    f"Historical source: {int(info.accepted_observations):,} service observations · "
    f"{int(info.ai_assessed_accounts):,} offline AI research notes · Snapshot built {str(info.built_at)[:19]}"
)
st.info("These are candidate domains, not verified organisations or confirmed vulnerabilities. "
        "Confirm the business and service operator before outreach.")
if int(info.hosted_accounts) < int(info.candidate_accounts):
    st.caption("The app contains a ranked subset; the pipeline processed the full source.")
if int(info.stale_ai_notes_skipped):
    st.info(f"{int(info.stale_ai_notes_skipped)} offline AI notes were withheld after a new source file arrived. "
            "The account queue remains rule-based until those notes are reassessed.")

st.subheader("Explore candidates")
search_col, view_col, signal_col = st.columns([2, 1.2, 1.5])
search = search_col.text_input("Find a domain", placeholder="company.example")
view = view_col.selectbox("View", ["All candidates", "Investigate first", "Needs research", "AI notes"])
signal = signal_col.selectbox("Technical signal", ["Any signal", "Direct verified label",
                                                    "Any scanner-verified label", "Admin/login page",
                                                    "Vulnerability metadata"])
with st.expander("More filters"):
    direct_only = st.toggle(
        "Direct domain matches only",
        help="Both HTTP host and certificate match a candidate domain in at least one observation. "
             "This does not verify a legal business or service operator.",
    )
    attribution = st.selectbox("Evidence match", ["Any match", "supported", "partial",
                                                    "unresolved", "provider_only"])

matches = account_rows(search, view, signal, direct_only, attribution)
st.caption(f"Showing {len(matches):,} highest-ranked matches. Select a row to inspect it; "
           "search by domain to narrow the 50,000-account hosted set.")
if len(matches):
    display = matches.rename(columns={
        "candidate_domain": "Domain", "priority_tier": "Priority",
        "attribution_status": "Match", "research_signal": "Research signal",
        "investigation_score": "Score", "last_observed_at": "Last observed",
    }).copy()
    display["Priority"] = display["Priority"].str.replace("_", " ").str.title()
    display["Match"] = display["Match"].str.replace("_", " ").str.title()
    choice = st.dataframe(display, hide_index=True, width="stretch", height=360,
                          on_select="rerun", selection_mode="single-row",
                          column_config={"Score": st.column_config.NumberColumn(
                              "Score", help="Rule-derived investigation score, not purchase probability.")})
    selected_rows = choice.selection.rows
    selected_index = selected_rows[0] if selected_rows and selected_rows[0] < len(matches) else 0
    domain = str(matches.iloc[selected_index].candidate_domain)
    row, evidence, assessment = account_detail(domain)

    with st.container(border=True):
        st.subheader(domain)
        st.caption(f"{str(row.priority_tier).replace('_', ' ').title()} · "
                   f"{str(row.attribution_status).replace('_', ' ').title()} domain match · "
                   f"Last observed {str(row.last_observed_at)[:10]}")
        st.write(f"**Why it is in the queue:** {research_reason(row)}")
        st.write(f"**Next research step:** {row.next_action}")
        st.write("**Likely buyer role:** IT or security owner. The dataset has no named contact. "
                 "Confirm who operates this service before choosing a person to contact.")
        if st.button("Add to shortlist", disabled=domain in st.session_state.shortlist):
            st.session_state.shortlist.append(domain)
            st.rerun()
        if len(assessment):
            ai = assessment.iloc[0]
            st.info(f"**AI research note ({ai.decision}):** {ai.reason} Next: {ai.next_action}")
            st.caption("Advisory only; the note does not change priority or verify ownership. "
                       f"Prompt {ai.prompt_version} · {ai.model} · {ai.review_status}")
            with st.expander("AI citations"):
                st.write(", ".join(ai.evidence_ids))

        st.markdown("**Selected source evidence**")
        st.caption("Up to three observations are shown. Scanner labels and domain matches are evidence, "
                   "not proof that the business is affected.")
        compact_evidence = evidence.assign(
            service=evidence["ip_address"].astype(str) + ":" + evidence["port"].astype(str),
            domain_link=[
                "Host + certificate" if host and cert else "One field" if host or cert else "Unresolved"
                for host, cert in zip(evidence["http_domain_match"], evidence["cert_domain_match"])
            ],
        )[["observed_at", "service", "domain_link", "verified_vulnerability_count",
            "product", "http_title"]].rename(columns={
                "observed_at": "Observed", "service": "Service", "domain_link": "Domain link",
                "verified_vulnerability_count": "Verified labels", "product": "Product",
                "http_title": "Page title",
            })
        st.dataframe(compact_evidence, hide_index=True, width="stretch")
        with st.expander("Full source fields and evidence IDs"):
            st.dataframe(evidence, hide_index=True, width="stretch")
else:
    st.info("No candidate domains match these filters. Try a broader view or signal.")

with st.sidebar:
    st.header(f"Shortlist · {len(st.session_state.shortlist)}")
    st.caption("Saved for this browser session only. Export a research brief to keep it.")
    if st.session_state.shortlist:
        for shortlisted_domain in st.session_state.shortlist:
            st.write(shortlisted_domain)
        st.download_button("Download research brief CSV", shortlist_csv(st.session_state.shortlist),
                           file_name="welook-research-brief.csv", mime="text/csv")
        remove = st.selectbox("Remove a domain", st.session_state.shortlist)
        if st.button("Remove selected"):
            st.session_state.shortlist.remove(remove)
            st.rerun()
    else:
        st.write("Select a candidate and add it here.")

with st.expander("How to read the evidence"):
    st.markdown("""
    - **Investigate first:** Both domain fields match and a scanner-verified vulnerability label appears on the same observation. Verify the finding and operator before outreach.
    - **Needs research:** A weaker signal or account match, including an admin/login title. A login page is not a vulnerability by itself.
    - **Direct domain matches only:** A rule-based evidence filter, not a verified-business list. A hosting provider can still pass.
    - **AI notes:** Offline suggestions on 35 selected accounts. Most accounts use rules only; notes are not a measured quality evaluation or permission to contact a business.
    """)
    st.write("This is one historical scan snapshot. It cannot establish current exposure, "
             "buying intent, company territory, legal identity, or a decision-maker.")
st.caption("WeLook · Firmable take-home prototype · Evidence-backed research, not automated outreach.")
