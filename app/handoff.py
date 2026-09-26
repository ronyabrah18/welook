"""Build a cited, spreadsheet-safe research handoff from the serving snapshot."""

import csv
from io import StringIO
from pathlib import Path

import duckdb


SIGNAL_CASE = """CASE
    WHEN a.directly_supported_verified_observation_count > 0 THEN 'Direct verified label'
    WHEN a.directly_supported_vulnerability_observation_count > 0 THEN 'Direct scanner label; verify'
    WHEN a.verified_vulnerability_association_count > 0 THEN 'Verified label; check operator'
    WHEN a.vulnerability_association_count > 0 THEN 'Vulnerability metadata'
    WHEN a.admin_or_login_observation_count > 0 THEN 'Admin/login page'
    ELSE 'Observed service' END"""


def csv_cell(value):
    """Keep spreadsheet applications from interpreting exported text as formulas."""
    if value is None:
        return ""
    if not isinstance(value, str):
        return value
    if value.lstrip().startswith(("=", "+", "-", "@")) or value.startswith(("\t", "\r")):
        return "'" + value
    return value


def shortlist_csv(db_path: Path, domains: list[str],
                  research: dict[str, dict[str, str]] | None = None) -> str:
    if not domains:
        return ""
    research = research or {}
    placeholders = ",".join("?" for _ in domains)
    sql = (
        "SELECT a.candidate_domain, a.priority_tier, a.attribution_status, "
        f"{SIGNAL_CASE} AS research_signal, a.last_observed_at, "
        "(SELECT string_agg('source-record-' || e.source_record_id, '; ') "
        " FROM (SELECT source_record_id FROM evidence "
        "       WHERE candidate_domain = a.candidate_domain "
        "       ORDER BY evidence_score DESC, observed_at DESC, source_record_id LIMIT 3) e) "
        "AS selected_evidence_ids, "
        "(SELECT string_agg(id, '; ' ORDER BY id) FROM "
        " (SELECT DISTINCT id FROM evidence e CROSS JOIN unnest(e.scanner_label_ids) AS labels(id) "
        "  WHERE e.candidate_domain = a.candidate_domain ORDER BY id LIMIT 5) labels) "
        "AS scanner_listed_ids, a.next_action, "
        "assessment.decision AS ai_decision, assessment.reason AS ai_note, "
        "assessment.next_action AS ai_next_action, "
        "'Unverified candidate domain' AS dataset_identity_status "
        f"FROM accounts a LEFT JOIN assessments assessment USING (candidate_domain) WHERE a.candidate_domain IN ({placeholders}) "
        "ORDER BY CASE a.priority_tier WHEN 'investigate_first' THEN 0 "
        "WHEN 'review_next' THEN 1 WHEN 'research' THEN 2 ELSE 3 END, "
        "a.investigation_score DESC"
    )
    with duckdb.connect(str(db_path), read_only=True) as con:
        result = con.execute(sql, domains)
        columns = [item[0] for item in result.description]
        rows = result.fetchall()
    out = StringIO()
    writer = csv.writer(out)
    writer.writerow([*columns, "research_status", "researched_company_name",
                     "identity_source_url", "research_note"])
    for row in rows:
        domain = row[0]
        decision = research.get(domain, {})
        writer.writerow([csv_cell(value) for value in (*row,
                        decision.get("status", "Researching"), decision.get("company_name", ""),
                        decision.get("source_url", ""), decision.get("note", ""))])
    return out.getvalue()
