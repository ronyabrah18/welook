"""Export a compact, read-only DuckDB snapshot for the hosted Streamlit app."""

import argparse
import json
from pathlib import Path
import sys

import duckdb


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from welook.lineage import source_registry_hash  # noqa: E402


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, default=ROOT / "artifacts" / "warehouse" / "full.duckdb")
    parser.add_argument("--output", type=Path, default=ROOT / "app" / "data" / "welook_serving.duckdb")
    parser.add_argument("--limit", type=int, default=50_000)
    args = parser.parse_args()
    if args.limit < 1:
        parser.error("--limit must be positive")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    pending = args.output.with_suffix(".pending.duckdb")
    if pending.exists():
        pending.unlink()
    with duckdb.connect(str(args.db)) as source:
        current_registry_hash = source_registry_hash(row[0] for row in source.execute(
            "SELECT source_sha256 FROM raw.ingestion_manifest"
        ).fetchall())
        escaped_pending = str(pending.resolve()).replace("'", "''")
        source.execute(f"ATTACH '{escaped_pending}' AS serving")
        total = source.execute("SELECT count(*) FROM analytics.fct_accounts").fetchone()[0]
        source.execute("""
            CREATE TABLE serving.accounts AS
            SELECT candidate_domain, observation_count, supported_observation_count,
                   vulnerability_association_count, verified_vulnerability_association_count,
                   directly_supported_verified_observation_count,
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
        ai_info = source.execute("""SELECT source_registry_hash, stale_ai_notes_skipped
            FROM analytics.ai_assessment_build_info""").fetchone()
        if ai_info is None or ai_info[0] != current_registry_hash:
            raise RuntimeError("Gold AI assessments are missing or stale; run register_ai_gold.py first")
        stale_ai = ai_info[1]
        source.execute("""
            CREATE TABLE serving.assessments AS
            SELECT ai.* FROM analytics.account_ai_assessments ai
            JOIN serving.accounts a USING (candidate_domain)
            WHERE ai.source_registry_hash = ?
        """, [current_registry_hash])
        selected = source.execute("SELECT count(*) FROM serving.accounts").fetchone()[0]
        evidence = source.execute("SELECT count(*) FROM serving.evidence").fetchone()[0]
        ai_count = source.execute("SELECT count(*) FROM serving.assessments").fetchone()[0]
        source_lines, accepted = source.execute("SELECT sum(source_lines), sum(accepted_rows) FROM raw.ingestion_manifest").fetchone()
        source.execute("CREATE TABLE serving.build_info AS SELECT ?::BIGINT AS source_lines, ?::BIGINT AS accepted_observations, ?::BIGINT AS candidate_accounts, ?::BIGINT AS hosted_accounts, ?::BIGINT AS hosted_evidence_rows, ?::BIGINT AS ai_assessed_accounts, ?::BIGINT AS stale_ai_notes_skipped, ?::VARCHAR AS source_registry_hash, current_timestamp AS built_at",
                       [source_lines, accepted, total, selected, evidence, ai_count, stale_ai, current_registry_hash])
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
              "stale_ai_notes_skipped": stale_ai,
              "source_lines": source_lines,
              "accepted_observations": accepted,
              "hosting_limit_applied": selected < total}
    (args.output.parent / "serving_report.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
