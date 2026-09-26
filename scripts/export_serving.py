"""Export a compact, read-only DuckDB snapshot for the hosted Streamlit app."""

import argparse
import json
from pathlib import Path

import duckdb


ROOT = Path(__file__).resolve().parents[1]


def validate_published_assessments(source: duckdb.DuckDBPyConnection, path: Path) -> None:
    """Fail the export if a published AI claim lacks visible source evidence."""
    for line_number, line in enumerate(path.read_text().splitlines(), 1):
        if not line.strip():
            continue
        record = json.loads(line)
        review_status = record.get("review_status")
        if review_status not in {"reviewed_for_demo", "guardrail_checked"}:
            raise ValueError(f"Unknown publication status on line {line_number}")
        if record.get("status") not in {"completed", "cache_hit"}:
            raise ValueError(f"Unsuccessful AI result on line {line_number}")
        domain = record["candidate_domain"]
        result = record["result"]
        decision = result["decision"]
        evidence_ids = result["evidence_ids"]
        account = source.execute(
            "SELECT attribution_status FROM serving.accounts WHERE candidate_domain = ?", [domain]
        ).fetchone()
        if account is None or decision not in {"supported", "needs_review", "insufficient_evidence"}:
            raise ValueError(f"Invalid reviewed assessment on line {line_number}: account or decision")
        if decision == "supported" and account[0] == "provider_only":
            raise ValueError(f"Provider-only account cannot receive supported AI claim: {domain}")
        if review_status == "guardrail_checked" and decision == "supported":
            raise ValueError(f"Batch-supported claim needs individual review: {domain}")
        evidence = {f"source-line-{row[0]}": (row[1], row[2]) for row in source.execute(
            "SELECT source_line, http_domain_match, cert_domain_match FROM serving.evidence WHERE candidate_domain = ?", [domain]
        ).fetchall()}
        if not evidence_ids or not set(evidence_ids).issubset(evidence):
            raise ValueError(f"Reviewed assessment cites evidence absent from serving snapshot: {domain}")
        if decision == "supported" and not any(
            evidence[evidence_id] == (True, True) for evidence_id in evidence_ids
        ):
            raise ValueError(f"Supported claim lacks a cited double domain match: {domain}")


# Keep the old import name for callers using the earlier reviewed-only gate.
validate_reviewed_assessments = validate_published_assessments


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, default=ROOT / "artifacts" / "warehouse" / "sales.duckdb")
    parser.add_argument("--output", type=Path, default=ROOT / "app" / "data" / "welook_serving.duckdb")
    parser.add_argument("--limit", type=int, default=50_000)
    parser.add_argument("--assessments", type=Path, default=ROOT / "app" / "data" / "published_assessments.jsonl")
    args = parser.parse_args()
    if args.limit < 1:
        parser.error("--limit must be positive")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    pending = args.output.with_suffix(".pending.duckdb")
    if pending.exists():
        pending.unlink()
    with duckdb.connect(str(args.db)) as source:
        escaped_pending = str(pending.resolve()).replace("'", "''")
        source.execute(f"ATTACH '{escaped_pending}' AS serving")
        total = source.execute("SELECT count(*) FROM analytics.fct_accounts").fetchone()[0]
        source.execute("""
            CREATE TABLE serving.accounts AS
            SELECT candidate_domain, observation_count, supported_observation_count,
                   vulnerability_association_count, verified_vulnerability_association_count,
                   admin_or_login_observation_count,
                   first_observed_at, last_observed_at, investigation_score,
                   example_http_title, example_product, attribution_status,
                   priority_tier, next_action
            FROM analytics.fct_accounts
            ORDER BY CASE priority_tier WHEN 'investigate_first' THEN 0
                        WHEN 'research' THEN 1 ELSE 2 END,
                     investigation_score DESC, supported_observation_count DESC,
                     candidate_domain
            LIMIT ?
        """, [args.limit])
        source.execute("""
            CREATE TABLE serving.evidence AS
            SELECT candidate_domain, source_record_id, source_line, observed_at,
                   ip_address, port, infrastructure_org, infrastructure_country,
                   product, http_host, http_title, certificate_cn,
                   vulnerability_count, verified_vulnerability_count,
                   http_domain_match, cert_domain_match,
                   admin_or_login_title, attribution_status, evidence_score
            FROM (
                SELECT e.*, row_number() OVER (
                    PARTITION BY e.candidate_domain
                    ORDER BY e.evidence_score DESC, e.observed_at DESC, e.source_record_id
                ) AS rank_in_account
                FROM analytics.int_account_evidence e
                JOIN serving.accounts a USING (candidate_domain)
            ) selected
            WHERE rank_in_account <= 3
        """)
        if args.assessments.exists() and args.assessments.stat().st_size:
            validate_published_assessments(source, args.assessments)
            assessment_path = str(args.assessments.resolve()).replace("'", "''")
            source.execute(f"""
                CREATE TABLE serving.assessments AS
                SELECT candidate_domain, result.decision AS decision,
                       result.reason AS reason, result.next_action AS next_action,
                       result.evidence_ids AS evidence_ids, prompt_version, model,
                       assessed_at_utc, review_status
                FROM read_json_auto('{assessment_path}', format='newline_delimited') ai
                JOIN serving.accounts a USING (candidate_domain)
                WHERE status IN ('completed', 'cache_hit')
                  AND review_status IN ('reviewed_for_demo', 'guardrail_checked')
                  AND result.decision IS NOT NULL
                  AND NOT (result.decision = 'supported' AND a.attribution_status = 'provider_only')
                QUALIFY row_number() OVER (PARTITION BY candidate_domain
                    ORDER BY assessed_at_utc DESC) = 1
            """)
        else:
            source.execute("""CREATE TABLE serving.assessments (
                candidate_domain VARCHAR, decision VARCHAR, reason VARCHAR,
                next_action VARCHAR, evidence_ids VARCHAR[], prompt_version VARCHAR,
                model VARCHAR, assessed_at_utc VARCHAR, review_status VARCHAR)""")
        selected = source.execute("SELECT count(*) FROM serving.accounts").fetchone()[0]
        evidence = source.execute("SELECT count(*) FROM serving.evidence").fetchone()[0]
        ai_count = source.execute("SELECT count(*) FROM serving.assessments").fetchone()[0]
        source_lines, accepted = source.execute("SELECT sum(source_lines), sum(accepted_rows) FROM raw.ingestion_manifest").fetchone()
        source.execute("CREATE TABLE serving.build_info AS SELECT ?::BIGINT AS source_lines, ?::BIGINT AS accepted_observations, ?::BIGINT AS candidate_accounts, ?::BIGINT AS hosted_accounts, ?::BIGINT AS hosted_evidence_rows, ?::BIGINT AS ai_assessed_accounts, current_timestamp AS built_at",
                       [source_lines, accepted, total, selected, evidence, ai_count])
        source.execute("CREATE INDEX accounts_domain_idx ON serving.accounts(candidate_domain)")
        source.execute("CREATE INDEX evidence_domain_idx ON serving.evidence(candidate_domain)")
        source.execute("DETACH serving")
    pending.replace(args.output)
    try:
        report_output = str(args.output.resolve().relative_to(ROOT))
    except ValueError:
        report_output = str(args.output)
    report = {"output": report_output, "size_bytes": args.output.stat().st_size,
              "candidate_accounts": total, "hosted_accounts": selected,
              "hosted_evidence_rows": evidence, "ai_assessed_accounts": ai_count,
              "source_lines": source_lines,
              "accepted_observations": accepted,
              "hosting_limit_applied": selected < total}
    (args.output.parent / "serving_report.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
