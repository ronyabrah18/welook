"""WeLook sales-research UI. Reads a published, compact DuckDB snapshot only."""

from __future__ import annotations

import os
from pathlib import Path
from urllib.parse import urlparse

import duckdb
import streamlit as st

from handoff import SIGNAL_CASE, shortlist_csv


DEFAULT_DB = Path(__file__).resolve().parent / "data" / "welook_serving.duckdb"
DB = Path(os.environ.get("WELOOK_SERVING_DB", DEFAULT_DB))
st.set_page_config(page_title="WeLook · Account research", page_icon="◉", layout="wide")

DOMAIN_LINK_LABELS = {
    "supported": "Strong · host + certificate",
    "partial": "Partial · host or certificate",
    "unresolved": "Weak · no direct domain match",
    "provider_only": "Infrastructure provider",
}
PRIORITY_LABELS = {
    "investigate_first": "Investigate first",
    "review_next": "Review next",
    "research": "Needs research",
    "low_evidence": "Low evidence",
}
FILTER_DEFAULTS = {
    "filter_search": "", "filter_view": "Review queue", "filter_signal": "Any reason",
    "filter_product": "",
}


def reset_filters():
    for key, value in FILTER_DEFAULTS.items():
        st.session_state[key] = value


def query(sql: str, params: list | None = None):
    try:
        with duckdb.connect(str(DB), read_only=True) as con:
            return con.execute(sql, params or []).fetchdf()
    except duckdb.Error:
        st.error("The research snapshot could not be loaded. Please refresh the page or contact the app owner.")
        st.stop()


def account_rows(search: str, view: str, signal: str, product: str = "", limit: int = 100):
    conditions = ["1=1"]
    params: list = []
    if search:
        conditions.append("a.candidate_domain ILIKE ?")
        params.append("%" + search.strip() + "%")
    if view == "Review queue":
        conditions.append("a.priority_tier IN ('investigate_first', 'review_next')")
    elif view == "Investigate first":
        conditions.append("a.priority_tier = 'investigate_first'")
    elif view == "Review next":
        conditions.append("a.priority_tier = 'review_next'")
    elif view == "Needs research":
        conditions.append("a.priority_tier = 'research'")
    elif view == "AI suggestions":
        conditions.append("assessment.candidate_domain IS NOT NULL")
    if product.strip():
        conditions.append("EXISTS (SELECT 1 FROM evidence e WHERE e.candidate_domain = a.candidate_domain "
                          "AND e.product ILIKE ?)")
        params.append("%" + product.strip() + "%")
    signal_columns = {
        "Strong scanner-verified signal": "a.directly_supported_verified_observation_count",
        "Any scanner-verified signal": "a.verified_vulnerability_association_count",
        "Admin or login page": "a.admin_or_login_observation_count",
        "Any scanner finding": "a.vulnerability_association_count",
    }
    if signal != "Any reason":
        conditions.append(f"{signal_columns[signal]} > 0")
    params.append(limit)
    return query(
        "SELECT a.candidate_domain, a.priority_tier, a.attribution_status, "
        f"{SIGNAL_CASE} AS research_signal, a.investigation_score, a.last_observed_at "
        "FROM accounts a LEFT JOIN assessments assessment USING (candidate_domain) WHERE " + " AND ".join(conditions) +
        " ORDER BY CASE a.priority_tier WHEN 'investigate_first' THEN 0 "
        "WHEN 'review_next' THEN 1 WHEN 'research' THEN 2 ELSE 3 END, "
        "a.investigation_score DESC, a.candidate_domain LIMIT ?",
        params,
    )


def account_detail(domain: str):
    account = query("SELECT * FROM accounts WHERE candidate_domain = ?", [domain])
    assessment = query("SELECT * FROM assessments WHERE candidate_domain = ?", [domain])
    evidence = query(
        "SELECT 'source-record-' || source_record_id AS evidence_id, source_line, observed_at, ip_address, port, infrastructure_org, "
        "infrastructure_country, product, http_host, http_title, certificate_cn, "
        "vulnerability_count, verified_vulnerability_count, scanner_label_ids, "
        "http_domain_match, cert_domain_match, "
        "attribution_status, evidence_score FROM evidence "
        "WHERE candidate_domain = ? ORDER BY evidence_score DESC, observed_at DESC",
        [domain],
    )
    return account.iloc[0], evidence, assessment


def scanner_ids_preview(value) -> str:
    if value is None or isinstance(value, str) or not hasattr(value, "__iter__"):
        return ""
    ids = [str(item) for item in value]
    return ", ".join(ids[:3]) + (f" (+{len(ids) - 3} more)" if len(ids) > 3 else "")


RESEARCH_STATUSES = ["Researching", "Verify operator", "Verify technical finding",
                     "Hold", "Ready for sales review"]


def research_reason(row) -> str:
    if row.directly_supported_verified_observation_count:
        count = int(row.directly_supported_verified_observation_count)
        return (f"{count} service observation{'s have' if count != 1 else ' has'} a "
                "scanner-verified vulnerability label and both HTTP-host and certificate-domain matches.")
    if row.directly_supported_vulnerability_observation_count:
        count = int(row.directly_supported_vulnerability_observation_count)
        return (f"{count} directly matched service observation{'s carry' if count != 1 else ' carries'} "
                "scanner vulnerability metadata. The label is unverified; confirm the finding and operator.")
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
    st.error("The research snapshot is unavailable. Please contact the app owner.")
    st.caption("For a local setup, use the bundled app/data/welook_serving.duckdb file "
               "or check your WELOOK_SERVING_DB setting.")
    st.stop()

if "shortlist" not in st.session_state:
    st.session_state.shortlist = []
if "research" not in st.session_state:
    st.session_state.research = {}

build_info = query("SELECT * FROM build_info")
if len(build_info) != 1:
    st.error("The research snapshot is incomplete. Please contact the app owner.")
    st.stop()
info = build_info.iloc[0]
first_count = int(query("SELECT count(*) AS n FROM accounts WHERE priority_tier = 'investigate_first'").iloc[0].n)
review_next_count = int(query("SELECT count(*) AS n FROM accounts WHERE priority_tier = 'review_next'").iloc[0].n)
st.caption("WELOOK  /  CYBERSECURITY ACCOUNT RESEARCH")
st.title("Find your next account to research.")
st.write("Explore cybersecurity signals, check the evidence, and prepare a shortlist for sales review.")

c1, c2, c3 = st.columns(3)
c1.metric("Domains analysed", f"{int(info.candidate_accounts):,}")
c2.metric("Available to explore", f"{int(info.hosted_accounts):,}")
c3.metric("In the review queue", f"{first_count + review_next_count:,}")
st.caption(
    f"{first_count:,} investigate first · {review_next_count:,} review next · "
    f"{int(info.ai_assessed_accounts):,} AI summaries available"
)
st.info("Start with the review queue. These historical signals need checking: "
        "confirm the business, service operator, and technical finding before outreach.")
if int(info.hosted_accounts) < int(info.candidate_accounts):
    st.caption("You are exploring a ranked subset of all analysed domains.")
if int(info.stale_ai_notes_skipped):
    st.info(f"{int(info.stale_ai_notes_skipped)} offline AI summaries were withheld after a new source file arrived. "
            "The account queue remains rule-based until those summaries are reassessed.")

with st.expander("User Guide · How to use WeLook"):
    st.markdown(Path(__file__).with_name("user_guide.md").read_text(encoding="utf-8"))
    st.caption(f"Full source processed: {int(info.accepted_observations):,} observations. "
               f"Serving snapshot built {str(info.built_at)[:19]}.")

st.subheader("Explore candidates")
search_col, view_col, signal_col = st.columns([2, 1.2, 1.5])
search = search_col.text_input("Find a domain", placeholder="e.g. 3ds.com", key="filter_search",
                               help="Search candidate domain names. Your other filters still apply.")
view = view_col.selectbox("Queue", ["Review queue", "All candidates", "Investigate first",
                                    "Review next", "Needs research", "AI suggestions"], key="filter_view",
                           help="Start with the review queue, or choose a broader group. See the User Guide for each queue.")
signal = signal_col.selectbox("Why it surfaced", ["Any reason", "Strong scanner-verified signal",
                                                   "Any scanner-verified signal", "Admin or login page",
                                                   "Any scanner finding"], key="filter_signal",
                              help="Keep domains with this historical signal. Scanner findings still need verification.")
product = st.text_input("Observed product (optional)", placeholder="e.g. cPanel",
                        key="filter_product",
                        help="Searches product names in the selected evidence shown by the app. "
                             "A missing match does not prove that a company does not use the product.")
st.button("Reset filters", on_click=reset_filters,
          help="Return to the default review queue. Your shortlist is kept.")

with st.spinner("Loading candidates…"):
    matches = account_rows(search, view, signal, product)
if len(matches):
    st.caption(f"Showing {len(matches):,} results (up to 100), ordered by priority, then evidence score. "
               "The first result opens below; select another row to review it.")
    display = matches.rename(columns={
        "candidate_domain": "Domain", "priority_tier": "Priority",
        "attribution_status": "Domain link", "research_signal": "Why it surfaced",
        "investigation_score": "Evidence score", "last_observed_at": "Last seen",
    }).copy()
    display["Priority"] = display["Priority"].map(PRIORITY_LABELS)
    display["Domain link"] = display["Domain link"].map(DOMAIN_LINK_LABELS)
    display["Last seen"] = display["Last seen"].astype(str).str[:10]
    display = display[["Domain", "Priority", "Why it surfaced", "Domain link", "Evidence score", "Last seen"]]
    choice = st.dataframe(display, hide_index=True, width="stretch", height=360,
                          on_select="rerun", selection_mode="single-row",
                          column_config={"Evidence score": st.column_config.NumberColumn(
                              "Evidence score", help="Strength of the best observation. Priority tier sorts first. "
                              "This is not a risk percentage or purchase probability; see the User Guide.")})
    selected_rows = choice.selection.rows
    selected_index = selected_rows[0] if selected_rows and selected_rows[0] < len(matches) else 0
    domain = str(matches.iloc[selected_index].candidate_domain)
    row, evidence, assessment = account_detail(domain)

    with st.container(border=True):
        st.subheader(domain)
        st.caption(f"{PRIORITY_LABELS[row.priority_tier]} · "
                   f"{DOMAIN_LINK_LABELS[row.attribution_status]} · "
                   f"Last observed {str(row.last_observed_at)[:10]}")
        st.write(f"**Why it surfaced:** {research_reason(row)}")
        st.write(f"**Suggested next check:** {row.next_action}")
        st.write("**Likely buyer role:** Security or IT owner. Verify who operates the service before choosing a contact.")
        if st.button("Add to shortlist", disabled=domain in st.session_state.shortlist):
            st.session_state.shortlist.append(domain)
            st.rerun()
        if domain in st.session_state.shortlist:
            with st.expander("Research handoff", expanded=True):
                saved = st.session_state.research.get(domain, {})
                status = st.selectbox("Research status", RESEARCH_STATUSES,
                                      index=RESEARCH_STATUSES.index(saved.get("status", "Researching")),
                                      key=f"research_status_{domain}")
                note = st.text_area("What you checked or need to check", value=saved.get("note", ""),
                                    max_chars=600, key=f"research_note_{domain}")
                company_name = st.text_input("Company name found (optional)",
                                             value=saved.get("company_name", ""), max_chars=120,
                                             help="Required when marking Ready for sales review.",
                                             key=f"company_name_{domain}")
                source_url = st.text_input("Source URL for company identity (optional)",
                                           value=saved.get("source_url", ""), max_chars=300,
                                           help="Use the HTTPS page where you found the company identity. Required for Ready for sales review.",
                                           key=f"source_url_{domain}")
                st.caption("Your status and note stay in this browser session and appear in the CSV export. "
                           "A researched name and URL still require a person to check service ownership.")
                if st.button("Save research update", key=f"save_research_{domain}"):
                    parsed_source = urlparse(source_url.strip())
                    if source_url.strip() and (parsed_source.scheme != "https"
                                               or not parsed_source.hostname
                                               or parsed_source.username or parsed_source.password):
                        st.error("Use a complete HTTPS source URL, or leave it blank.")
                    elif status == "Ready for sales review" and not (company_name.strip() and source_url.strip()):
                        st.error("Add a company name and source URL before marking this ready for sales review.")
                    else:
                        st.session_state.research[domain] = {
                            "status": status, "note": note.strip(),
                            "company_name": company_name.strip(), "source_url": source_url.strip(),
                        }
                        st.success("Research update saved for export.")
        if len(assessment):
            ai = assessment.iloc[0]
            st.info(f"**AI research summary**\n\n{ai.reason}\n\n**Suggested next check:** {ai.next_action}")
            evidence_count = len(ai.evidence_ids)
            st.caption(f"Generated offline from {evidence_count} selected historical "
                       f"observation{'s' if evidence_count != 1 else ''} shown below and checked before publication. "
                       "Advisory only—verify before outreach.")
        else:
            st.caption("Rules only: no AI research summary is available for this domain.")

        st.markdown("**Evidence to verify**")
        st.caption("Up to three observations are shown. Scanner labels and domain matches are evidence, "
                   "not proof that the business is affected.")
        compact_evidence = evidence.assign(
            service=evidence["ip_address"].astype(str) + ":" + evidence["port"].astype(str),
            unverified_labels=(evidence["vulnerability_count"] -
                               evidence["verified_vulnerability_count"]).clip(lower=0),
            scanner_ids=evidence["scanner_label_ids"].map(scanner_ids_preview),
            domain_link=[
                "Host + certificate" if host and cert else "One field" if host or cert else "Unresolved"
                for host, cert in zip(evidence["http_domain_match"], evidence["cert_domain_match"])
            ],
        )[["product", "domain_link", "scanner_ids", "unverified_labels",
            "verified_vulnerability_count", "observed_at", "service", "http_title"]].rename(columns={
                "observed_at": "Observed", "service": "Service", "domain_link": "Domain link",
                "unverified_labels": "Unverified labels",
                "verified_vulnerability_count": "Verified labels", "product": "Product",
                "scanner_ids": "Scanner-listed IDs",
                "http_title": "Page title",
            })
        st.dataframe(compact_evidence, hide_index=True, width="stretch")
        st.caption("Scanner-listed IDs are historical metadata. Check each finding against the current "
                   "service and operator; a listed ID is not a confirmed vulnerability.")
        with st.expander("Technical evidence details"):
            st.dataframe(evidence.drop(columns=["evidence_id"]), hide_index=True, width="stretch")
else:
    st.info("No candidate domains match these filters. Choose All candidates, clear the product search, "
            "or use Reset filters above. Filters are combined.")

with st.sidebar:
    st.header(f"Shortlist · {len(st.session_state.shortlist)}")
    st.caption("Saved for this browser session only. Export a research brief to keep it.")
    if st.session_state.shortlist:
        for shortlisted_domain in st.session_state.shortlist:
            st.write(shortlisted_domain)
            st.caption(st.session_state.research.get(shortlisted_domain, {}).get("status", "Researching"))
        st.download_button("Download research brief CSV", shortlist_csv(DB, st.session_state.shortlist,
                           st.session_state.research),
                           file_name="welook-research-brief.csv", mime="text/csv")
        remove = st.selectbox("Remove a domain", st.session_state.shortlist)
        if st.button("Remove selected"):
            st.session_state.shortlist.remove(remove)
            st.session_state.research.pop(remove, None)
            st.rerun()
    else:
        st.write("Select a candidate and add it here.")

st.caption("WeLook · Cybersecurity account research")
