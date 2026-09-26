"""Publish cautious, evidence-linked offline AI notes from a local batch.

This gate deliberately withholds `supported` batch decisions. Those need
individual review because a fluent model answer can overstate attribution.
"""

import argparse
import hashlib
import json
from pathlib import Path
import re
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from welook.lineage import source_registry_hash  # noqa: E402


def cautious_v5_note(result: dict) -> bool:
    """Withhold wording that turns unverified scanner metadata into a finding."""
    reason = result.get("reason", "").lower()
    action = result.get("next_action", "").lower()
    return (result.get("decision") == "needs_review"
            and "unverified" in reason
            and any(word in reason for word in ("label", "finding", "report"))
            and not re.search(r"\bvulnerabilities\b|\bvulnerable\b|\bexposed\b|\baffected\b|\bhigh\b", reason)
            and "operator" in action
            and any(word in action for word in ("verify", "check", "confirm", "validate")))


def normalize_v5_action(action: str) -> str:
    """Keep a verification step without repeating the model's unsafe shorthand."""
    return re.sub(r"\bunverified vulnerabilities\b", "unverified scanner labels",
                  action, flags=re.IGNORECASE)


def stable_evidence_id(evidence_id: str, legacy_source_sha256: str) -> str:
    """Migrate citations from the original one-file batch to global record IDs."""
    if evidence_id.startswith("source-record-"):
        return evidence_id
    if not evidence_id.startswith("source-line-"):
        raise ValueError(f"Unrecognised evidence ID: {evidence_id}")
    line = int(evidence_id.removeprefix("source-line-"))
    if line < 1:
        raise ValueError("Source line must be positive")
    record_id = hashlib.sha256(f"{legacy_source_sha256}:{line}".encode()).hexdigest()
    return f"source-record-{record_id}"


def publish(batch: Path, reviewed: Path, output: Path, legacy_source_sha256: str) -> dict:
    legacy_registry_hash = source_registry_hash([legacy_source_sha256])
    manually_reviewed = [json.loads(line) for line in reviewed.read_text().splitlines() if line.strip()]
    for record in manually_reviewed:
        record.setdefault("source_registry_hash", legacy_registry_hash)
        record["result"]["evidence_ids"] = [
            stable_evidence_id(item, legacy_source_sha256)
            for item in record["result"]["evidence_ids"]
        ]
    latest = {}
    for line in batch.read_text().splitlines():
        if not line.strip():
            continue
        record = json.loads(line)
        version = record.get("prompt_version")
        if version in ("v2", "v3", "v4", "v5") and record.get("status") in ("completed", "cache_hit"):
            domain = record["candidate_domain"]
            prior = latest.get(domain)
            if prior is None or (version, record["assessed_at_utc"]) > (
                prior["prompt_version"], prior["assessed_at_utc"]
            ):
                latest[domain] = record

    published = {item["candidate_domain"]: item for item in manually_reviewed}
    withheld = 0
    withheld_wording = 0
    for domain, record in sorted(latest.items()):
        if domain in published:
            continue
        if record["result"]["decision"] not in ("needs_review", "insufficient_evidence"):
            withheld += 1
            continue
        if record["prompt_version"] == "v5" and not cautious_v5_note(record["result"]):
            withheld_wording += 1
            continue
        published_result = dict(record["result"])
        if record["prompt_version"] == "v5":
            published_result["next_action"] = normalize_v5_action(published_result["next_action"])
        published[domain] = {
            "candidate_domain": domain,
            "source_registry_hash": record.get("source_registry_hash", legacy_registry_hash),
            "assessed_at_utc": record["assessed_at_utc"],
            "prompt_version": record["prompt_version"],
            "model": record["model"],
            "status": record["status"],
            "review_status": "guardrail_checked",
            "result": {**published_result, "evidence_ids": [
                stable_evidence_id(item, legacy_source_sha256)
                for item in published_result["evidence_ids"]
            ]},
        }

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("".join(json.dumps(item, ensure_ascii=False) + "\n"
                              for item in sorted(published.values(), key=lambda item: item["candidate_domain"])))
    return {"batch_accounts": len(latest), "published": len(published),
            "guardrail_checked": len(published) - len(manually_reviewed),
            "withheld_supported_batch_outputs": withheld,
            "withheld_unsafe_wording": withheld_wording}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--batch", type=Path, default=ROOT / "artifacts" / "ai" / "assessments.jsonl")
    parser.add_argument("--reviewed", type=Path, default=ROOT / "app" / "data" / "reviewed_assessments.jsonl")
    parser.add_argument("--output", type=Path, default=ROOT / "app" / "data" / "published_assessments.jsonl")
    parser.add_argument("--legacy-source-manifest", type=Path,
                        default=ROOT / "app" / "data" / "legacy_ai_source.json")
    args = parser.parse_args()
    legacy_source_sha256 = json.loads(args.legacy_source_manifest.read_text())["source_sha256"]
    print(json.dumps(publish(args.batch, args.reviewed, args.output, legacy_source_sha256), indent=2))


if __name__ == "__main__":
    main()
