"""Prepare or run a bounded offline LLM assessment for ambiguous accounts.

The default is a free dry run that writes selected evidence bundles. Add --live
only after label review, API setup, and an explicit budget decision.
"""

import argparse
from collections import defaultdict
from datetime import datetime, timezone
import json
from pathlib import Path
import sys

import duckdb
from openai import APIConnectionError, AuthenticationError, RateLimitError


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from welook.llm_client import BudgetedAssessor  # noqa: E402


def selected_bundles(db: Path, limit: int) -> list[dict]:
    with duckdb.connect(str(db), read_only=True) as con:
        rows = con.execute("""
            WITH selected AS (
                SELECT candidate_domain FROM analytics.fct_accounts
                WHERE priority_tier = 'research' AND attribution_status = 'partial'
                ORDER BY investigation_score DESC, candidate_domain LIMIT ?
            ), ranked AS (
                SELECT e.*, row_number() OVER (
                    PARTITION BY e.candidate_domain
                    ORDER BY e.evidence_score DESC, e.observed_at DESC, e.source_record_id
                ) AS evidence_rank
                FROM analytics.int_account_evidence e
                JOIN selected s USING (candidate_domain)
            )
            SELECT candidate_domain, source_line, infrastructure_org, http_host,
                   http_title, certificate_cn, product, vulnerability_count,
                   verified_vulnerability_count, http_domain_match,
                   cert_domain_match, listed_provider_domain
            FROM ranked WHERE evidence_rank <= 3 ORDER BY candidate_domain, evidence_rank
        """, [limit]).fetchall()
    bundles = defaultdict(list)
    for row in rows:
        domain, line, org, host, title, cert, product, vulns, verified, hm, cm, provider = row
        bundles[domain].append({"evidence_id": f"source-line-{line}",
            "source_line": line, "infrastructure_org": org,
            "http_host": host, "http_title": title[:180] if title else None,
            "certificate_cn": cert, "product": product,
            "vulnerability_count": vulns, "verified_vulnerability_count": verified,
            "rule_flags": {"http_domain_match": hm, "cert_domain_match": cm,
                           "listed_provider_domain": provider}})
    return [{"candidate_domain": domain, "evidence": evidence}
            for domain, evidence in sorted(bundles.items())]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, default=ROOT / "artifacts" / "warehouse" / "full.duckdb")
    parser.add_argument("--limit", type=int, default=100)
    parser.add_argument("--prompt", choices=["v1", "v2", "v3"], default="v3")
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--output", type=Path, default=ROOT / "artifacts" / "ai" / "assessments.jsonl")
    args = parser.parse_args()
    if not 1 <= args.limit <= 1_000:
        parser.error("--limit must be 1–1000")
    bundles = selected_bundles(args.db, args.limit)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    if not args.live:
        planned = args.output.with_name("planned_bundles.jsonl")
        with planned.open("w") as out:
            for bundle in bundles:
                out.write(json.dumps(bundle, ensure_ascii=False) + "\n")
        print(json.dumps({"mode": "dry_run_no_api_calls", "planned_accounts": len(bundles),
                          "output": str(planned)}))
        return
    assessor = BudgetedAssessor()
    with args.output.open("a") as out:
        for index, bundle in enumerate(bundles, 1):
            fatal_error = False
            fatal_error_name = ""
            try:
                assessed = assessor.assess(bundle, args.prompt)
                record = {"candidate_domain": bundle["candidate_domain"],
                          "assessed_at_utc": datetime.now(timezone.utc).isoformat(),
                          "prompt_version": args.prompt, "model": assessor.model,
                          "status": assessed["status"], "cache_key": assessed["cache_key"],
                          "result": assessed["result"]}
            except Exception as exc:
                record = {"candidate_domain": bundle["candidate_domain"],
                          "assessed_at_utc": datetime.now(timezone.utc).isoformat(),
                          "prompt_version": args.prompt, "model": assessor.model,
                          "status": "failed", "error": f"{type(exc).__name__}: {str(exc)[:200]}"}
                fatal_error = isinstance(exc, (APIConnectionError, AuthenticationError, RateLimitError))
                fatal_error = fatal_error or "API cost ceiling reached" in str(exc)
                fatal_error_name = type(exc).__name__
            out.write(json.dumps(record, ensure_ascii=False) + "\n")
            out.flush()
            print(f"{index}/{len(bundles)} {record['status']}", flush=True)
            if fatal_error:
                raise SystemExit(f"Stopping AI batch after {fatal_error_name}; check connectivity, API access, or budget")


if __name__ == "__main__":
    main()
