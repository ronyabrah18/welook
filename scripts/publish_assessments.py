"""Publish cautious, evidence-linked offline AI notes from a local batch.

This gate deliberately withholds `supported` batch decisions. Those need
individual review because a fluent model answer can overstate attribution.
"""

import argparse
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def publish(batch: Path, reviewed: Path, output: Path) -> dict:
    manually_reviewed = [json.loads(line) for line in reviewed.read_text().splitlines() if line.strip()]
    latest_v2 = {}
    for line in batch.read_text().splitlines():
        if not line.strip():
            continue
        record = json.loads(line)
        if record.get("prompt_version") == "v2" and record.get("status") in ("completed", "cache_hit"):
            latest_v2[record["candidate_domain"]] = record

    published = {item["candidate_domain"]: item for item in manually_reviewed}
    withheld = 0
    for domain, record in sorted(latest_v2.items()):
        if domain in published:
            continue
        if record["result"]["decision"] not in ("needs_review", "insufficient_evidence"):
            withheld += 1
            continue
        published[domain] = {
            "candidate_domain": domain,
            "assessed_at_utc": record["assessed_at_utc"],
            "prompt_version": record["prompt_version"],
            "model": record["model"],
            "status": record["status"],
            "review_status": "guardrail_checked",
            "result": record["result"],
        }

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("".join(json.dumps(item, ensure_ascii=False) + "\n"
                              for item in sorted(published.values(), key=lambda item: item["candidate_domain"])))
    return {"batch_accounts": len(latest_v2), "published": len(published),
            "guardrail_checked": len(published) - len(manually_reviewed),
            "withheld_supported_batch_outputs": withheld}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--batch", type=Path, default=ROOT / "artifacts" / "ai" / "assessments.jsonl")
    parser.add_argument("--reviewed", type=Path, default=ROOT / "app" / "data" / "reviewed_assessments.jsonl")
    parser.add_argument("--output", type=Path, default=ROOT / "app" / "data" / "published_assessments.jsonl")
    args = parser.parse_args()
    print(json.dumps(publish(args.batch, args.reviewed, args.output), indent=2))


if __name__ == "__main__":
    main()
