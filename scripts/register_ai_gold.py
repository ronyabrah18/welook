"""Validate curated offline AI notes and publish a separate gold assessment table."""

import argparse
import json
from pathlib import Path
import sys

import duckdb


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from welook.lineage import source_registry_hash  # noqa: E402


def validate_published_assessments(source: duckdb.DuckDBPyConnection, path: Path,
                                   current_registry_hash: str | None = None) -> tuple[list[tuple], int]:
    """Return publishable rows and stale count; reject unsupported claims."""
    accepted = []
    stale = 0
    if not path.exists():
        return accepted, stale
    for line_number, line in enumerate(path.read_text().splitlines(), 1):
        if not line.strip():
            continue
        record = json.loads(line)
        review_status = record.get("review_status")
        if review_status not in {"reviewed_for_demo", "guardrail_checked"}:
            raise ValueError(f"Unknown publication status on line {line_number}")
        if record.get("status") not in {"completed", "cache_hit"}:
            raise ValueError(f"Unsuccessful AI result on line {line_number}")
        if current_registry_hash is not None:
            if not record.get("source_registry_hash"):
                raise ValueError(f"Published AI result lacks source lineage on line {line_number}")
            if record["source_registry_hash"] != current_registry_hash:
                stale += 1
                continue
        domain = record["candidate_domain"]
        result = record["result"]
        decision = result["decision"]
        evidence_ids = result["evidence_ids"]
        account = source.execute(
            "SELECT attribution_status, priority_tier FROM analytics.fct_accounts WHERE candidate_domain = ?", [domain]
        ).fetchone()
        if account is None or decision not in {"supported", "needs_review", "insufficient_evidence"}:
            raise ValueError(f"Invalid reviewed assessment on line {line_number}: account or decision")
        if decision == "supported" and account[0] == "provider_only":
            raise ValueError(f"Provider-only account cannot receive supported AI claim: {domain}")
        if review_status == "guardrail_checked" and decision == "supported":
            raise ValueError(f"Batch-supported claim needs individual review: {domain}")
        evidence = {f"source-record-{row[0]}": (row[1], row[2]) for row in source.execute("""
            SELECT source_record_id, http_domain_match, cert_domain_match
            FROM (
                SELECT source_record_id, http_domain_match, cert_domain_match,
                       row_number() OVER (
                           ORDER BY CASE WHEN ? = 'review_next'
                                             AND attribution_status = 'supported'
                                             AND vulnerability_count > 0 THEN 0 ELSE 1 END,
                                    evidence_score DESC, observed_at DESC, source_record_id
                       ) AS rank_in_account
                FROM analytics.int_account_evidence
                WHERE candidate_domain = ?
            ) selected
            WHERE rank_in_account <= 3
        """, [account[1], domain]).fetchall()}
        if not evidence_ids or not set(evidence_ids).issubset(evidence):
            raise ValueError(f"Reviewed assessment cites evidence absent from serving snapshot: {domain}")
        if decision == "supported" and not any(
            evidence[evidence_id] == (True, True) for evidence_id in evidence_ids
        ):
            raise ValueError(f"Supported claim lacks a cited double domain match: {domain}")
        accepted.append((domain, decision, result["reason"], result["next_action"], evidence_ids,
                         record["prompt_version"], record["model"], record["assessed_at_utc"],
                         review_status, record.get("source_registry_hash")))
    return accepted, stale


def register_ai_gold(db: Path, assessments: Path) -> dict:
    with duckdb.connect(str(db)) as source:
        current_hash = source_registry_hash(row[0] for row in source.execute(
            "SELECT source_sha256 FROM raw.ingestion_manifest"
        ).fetchall())
        accepted, stale = validate_published_assessments(source, assessments, current_hash)
        source.execute("BEGIN TRANSACTION")
        try:
            source.execute("""CREATE OR REPLACE TABLE analytics.account_ai_assessments (
                candidate_domain VARCHAR, decision VARCHAR, reason VARCHAR,
                next_action VARCHAR, evidence_ids VARCHAR[], prompt_version VARCHAR,
                model VARCHAR, assessed_at_utc VARCHAR, review_status VARCHAR,
                source_registry_hash VARCHAR)""")
            if accepted:
                source.executemany("INSERT INTO analytics.account_ai_assessments VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", accepted)
                source.execute("""CREATE OR REPLACE TEMP TABLE latest_ai AS
                    SELECT * EXCLUDE (rank_in_account) FROM (
                        SELECT *, row_number() OVER (PARTITION BY candidate_domain
                            ORDER BY assessed_at_utc DESC) AS rank_in_account
                        FROM analytics.account_ai_assessments
                    ) WHERE rank_in_account = 1""")
                source.execute("CREATE OR REPLACE TABLE analytics.account_ai_assessments AS SELECT * FROM latest_ai")
            source.execute("""CREATE OR REPLACE TABLE analytics.ai_assessment_build_info AS
                SELECT ?::VARCHAR AS source_registry_hash,
                       ?::BIGINT AS stale_ai_notes_skipped,
                       (SELECT count(*) FROM analytics.account_ai_assessments)::BIGINT AS ai_assessed_accounts,
                       current_timestamp AS built_at""", [current_hash, stale])
            source.execute("COMMIT")
        except Exception:
            source.execute("ROLLBACK")
            raise
        count = source.execute("SELECT count(*) FROM analytics.account_ai_assessments").fetchone()[0]
    return {"gold_ai_assessments": count, "stale_ai_notes_skipped": stale,
            "source_registry_hash": current_hash}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, default=ROOT / "artifacts" / "warehouse" / "full.duckdb")
    parser.add_argument("--assessments", type=Path,
                        default=ROOT / "app" / "data" / "published_assessments.jsonl")
    args = parser.parse_args()
    print(json.dumps(register_ai_gold(args.db, args.assessments), indent=2))


if __name__ == "__main__":
    main()
