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


def query(sql: str, params: list | None = None):
    with duckdb.connect(str(DB), read_only=True) as con:
        return con.execute(sql, params or []).fetchdf()


def account_rows(search: str, tiers: list[str], attribution: list[str], limit: int = 100):
    conditions = ["1=1"]
    params: list = []
    if search:
        conditions.append("a.candidate_domain ILIKE ?")
        params.append("%" + search.strip() + "%")
    if tiers:
        conditions.append("priority_tier IN (SELECT unnest(?))")
        params.append(tiers)
    if attribution:
        conditions.append("attribution_status IN (SELECT unnest(?))")
        params.append(attribution)
    params.append(limit)
    return query(
        "SELECT a.candidate_domain, a.priority_tier, a.attribution_status, a.investigation_score, "
        "a.observation_count, a.vulnerability_association_count, a.last_observed_at, "
        "coalesce(assessment.decision, 'rule_only') AS ai_decision "
        "FROM accounts a LEFT JOIN assessments assessment USING (candidate_domain) WHERE " + " AND ".join(conditions) +
        " ORDER BY CASE a.priority_tier WHEN 'investigate_first' THEN 0 "
        "WHEN 'research' THEN 1 ELSE 2 END, a.investigation_score DESC, a.candidate_domain LIMIT ?",
        params,
    )


def account_detail(domain: str):
    account = query("SELECT * FROM accounts WHERE candidate_domain = ?", [domain])
    assessment = query("SELECT * FROM assessments WHERE candidate_domain = ?", [domain])
    evidence = query(
        "SELECT source_line, observed_at, ip_address, port, infrastructure_org, "
        "infrastructure_country, product, http_host, http_title, certificate_cn, "
        "vulnerability_count, http_domain_match, cert_domain_match, "
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
        "SELECT candidate_domain, priority_tier, attribution_status, investigation_score, "
        "observation_count, vulnerability_association_count, verified_vulnerability_association_count, "
        "last_observed_at, next_action "
        f"FROM accounts WHERE candidate_domain IN ({placeholders}) ORDER BY investigation_score DESC",
        domains,
    )
    out = StringIO()
    writer = csv.writer(out)
    writer.writerow(list(rows.columns))
    writer.writerows(rows.itertuples(index=False, name=None))
    return out.getvalue()


if not DB.exists():
    st.error("The published serving snapshot is missing. Run the pipeline and serving export first.")
    st.stop()

if "shortlist" not in st.session_state:
    st.session_state.shortlist = []

info = query("SELECT * FROM build_info").iloc[0]
st.caption("WELOOK  /  CYBERSECURITY ACCOUNT RESEARCH")
st.title("Know who to investigate next.")
st.write("Explore external-service evidence, check attribution, and prepare a focused research list.")

c1, c2, c3, c4 = st.columns(4)
c1.metric("Source observations", f"{int(info.source_lines):,}")
c2.metric("Candidate domains", f"{int(info.candidate_accounts):,}")
c3.metric("Available in app", f"{int(info.hosted_accounts):,}")
c4.metric("Shortlisted this session", len(st.session_state.shortlist))
st.caption(
    f"Snapshot built {str(info.built_at)[:19]} · "
    f"{int(info.accepted_observations):,} validated observations · "
    f"{int(info.ai_assessed_accounts):,} offline AI assessments · "
    "Technical evidence is a research signal, not a confirmed vulnerability or buying intent."
)
if int(info.hosted_accounts) < int(info.candidate_accounts):
    st.info("This hosted view shows a ranked subset. The local pipeline processed the full source; "
            "the account count above shows the complete candidate universe.")

prospects, research, saved, method = st.tabs(["Prospect queue", "Research queue", "Shortlist & export", "How to read this"])

with prospects:
    left, middle, right = st.columns([2, 2, 2])
    search = left.text_input("Find a domain", placeholder="company.example")
    tiers = middle.multiselect("Priority", ["investigate_first", "research", "low_evidence"],
                                default=["investigate_first", "research"])
    attribution = right.multiselect("Attribution", ["supported", "partial", "unresolved", "provider_only"])
    matches = account_rows(search, tiers, attribution)
    st.caption(f"Showing {len(matches):,} highest-ranked matching accounts. Search by domain to narrow further.")
    st.dataframe(matches, hide_index=True, width="stretch")
    if len(matches):
        domain = st.selectbox("Inspect account evidence", matches["candidate_domain"].tolist())
        row, evidence, assessment = account_detail(domain)
        st.subheader(domain)
        a, b, c = st.columns(3)
        a.metric("Investigation score", int(row.investigation_score))
        b.metric("Attribution", row.attribution_status)
        c.metric("Observed services", f"{int(row.observation_count):,}")
        st.write(f"**Suggested next step:** {row.next_action}")
        if len(assessment):
            ai = assessment.iloc[0]
            st.info(f"AI evidence assessment ({ai.prompt_version}, {ai.model}): "
                    f"{ai.decision}. {ai.reason} Next: {ai.next_action}")
        if row.example_http_title:
            st.write(f"**Example page title:** {row.example_http_title}")
        if row.example_product:
            st.write(f"**Observed product:** {row.example_product}")
        st.caption("Displayed evidence is selected from the dataset; it may not represent every associated service. "
                   "An IP or infrastructure organisation is not proof of account ownership.")
        st.dataframe(evidence, hide_index=True, width="stretch")
        if int(row.vulnerability_association_count):
            st.warning(f"Dataset vulnerability associations appear on {int(row.vulnerability_association_count):,} observations; "
                       f"{int(row.verified_vulnerability_association_count):,} have a scanner-verified flag. "
                       "Affected status and account ownership still require verification before outreach.")
        if st.button("Add to shortlist", disabled=domain in st.session_state.shortlist):
            st.session_state.shortlist.append(domain)
            st.rerun()

with research:
    st.subheader("Accounts needing verification")
    st.write("These have a technical cue but only a partial account match. Confirm who operates the service before contacting anyone.")
    review = account_rows("", ["research", "low_evidence"], ["partial", "unresolved", "provider_only"], 100)
    st.dataframe(review, hide_index=True, width="stretch")

with saved:
    st.subheader("Session shortlist")
    st.caption("Saved only in this browser session. Download the CSV to keep your work.")
    if st.session_state.shortlist:
        st.write(", ".join(st.session_state.shortlist))
        st.download_button("Download prospect brief CSV", shortlist_csv(st.session_state.shortlist),
                           file_name="welook-prospect-brief.csv", mime="text/csv")
        remove = st.selectbox("Remove an account", st.session_state.shortlist)
        if st.button("Remove selected"):
            st.session_state.shortlist.remove(remove)
            st.rerun()
    else:
        st.info("Open an account in the prospect queue and add it here.")

with method:
    st.subheader("What the labels mean")
    st.markdown("""
    - **Supported attribution:** The candidate domain matches both HTTP host and certificate name in an observation. It still needs human verification.
    - **Partial attribution:** One of those fields matches; the other is absent or different.
    - **Provider only:** The candidate domain is on a conservative infrastructure-provider list.
    - **Investigation score:** A transparent technical-research score, not a sales conversion probability.
    - **Vulnerability association:** A label supplied with the observation, not proof that the named business is affected.
    """)
    st.write("The source is one historical snapshot. We cannot infer a new exposure, live security posture, purchase intent, company territory, or a named decision-maker from it.")
    st.caption("WeLook · Firmable take-home prototype · Rule-only queue until evaluated AI assessments are published.")
