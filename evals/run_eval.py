"""Re-run the account-research prompt comparison on the labelled evidence set.

Without --live, score the committed predictions without an API key or paid calls.
With --live, run both prompt versions through the production budgeted/traced
adapter, then replace the committed predictions and report.
"""

from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.publish_assessments import cautious_v5_note  # noqa: E402
from welook.llm_client import DEFAULT_MODEL, redact_network_literals, validate_result  # noqa: E402


LABELS = ("supported", "needs_review", "insufficient_evidence")
CASES_PATH = ROOT / "evals" / "labelled_cases.jsonl"
PREDICTIONS_PATH = ROOT / "evals" / "predictions.jsonl"
RESULTS_PATH = ROOT / "evals" / "results.json"
REPORT_PATH = ROOT / "evals" / "results.md"


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def bundle_sha256(bundle: dict) -> str:
    encoded = json.dumps(bundle, sort_keys=True, ensure_ascii=False).encode()
    return hashlib.sha256(encoded).hexdigest()


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def load_cases(path: Path = CASES_PATH) -> list[dict]:
    cases = read_jsonl(path)
    if not 20 <= len(cases) <= 30:
        raise ValueError("The labelled eval set must contain 20–30 cases")
    if len({case["id"] for case in cases}) != len(cases):
        raise ValueError("Eval case IDs must be unique")
    for case in cases:
        if case["expected_decision"] not in LABELS:
            raise ValueError(f"Unknown expected decision: {case['id']}")
        if redact_network_literals(case["bundle"]) != case["bundle"]:
            raise ValueError(f"Unredacted IP literal in eval input: {case['id']}")
        evidence_ids = {item["evidence_id"] for item in case["bundle"]["evidence"]}
        if len(evidence_ids) != len(case["bundle"]["evidence"]):
            raise ValueError(f"Duplicate source evidence IDs: {case['id']}")
        if not set(case["acceptable_citation_ids"]) <= evidence_ids:
            raise ValueError(f"Unrecognised acceptable citation: {case['id']}")
        if case["expected_decision"] != "insufficient_evidence" and not case["acceptable_citation_ids"]:
            raise ValueError(f"Missing labelled citation anchor: {case['id']}")
    return cases


def run_live(cases: list[dict], versions: tuple[str, str]) -> list[dict]:
    # This is the same shared ledger and $10 cap as offline production batches.
    from welook.llm_client import BudgetedAssessor

    assessor = BudgetedAssessor()
    records = []
    for version in versions:
        for index, case in enumerate(cases, 1):
            try:
                response = assessor.assess(case["bundle"], version)
                record = {"case_id": case["id"], "bundle_sha256": bundle_sha256(case["bundle"]),
                          "prompt_version": version,
                          "model": assessor.model, "status": response["status"],
                          "cache_key": response["cache_key"], "result": response["result"]}
                if "call_id" in response:
                    record["call_id"] = response["call_id"]
            except Exception as exc:
                record = {"case_id": case["id"], "bundle_sha256": bundle_sha256(case["bundle"]),
                          "prompt_version": version,
                          "model": assessor.model, "status": "failed",
                          "error": f"{type(exc).__name__}: {str(exc)[:200]}"}
            records.append(record)
            print(f"{version} {index}/{len(cases)} {record['status']}", flush=True)
            if record["status"] == "failed":
                # A failed connection could have incurred a charge. Stop instead
                # of retrying the rest of the set and depleting reservations.
                break
        if records[-1]["status"] == "failed":
            break
    return records


def score_version(cases: list[dict], predictions: list[dict], version: str) -> dict:
    by_id = {item["case_id"]: item for item in predictions if item["prompt_version"] == version}
    if len(by_id) != len([item for item in predictions if item["prompt_version"] == version]):
        raise ValueError(f"Duplicate predictions for {version}")
    confusion = {label: Counter() for label in LABELS}
    errors = []
    correct = valid_citations = acceptable_citations = safety_proxy_pass = 0
    completed = 0
    research_count = sum(case["expected_decision"] != "insufficient_evidence" for case in cases)
    direct_unverified_count = sum(case["segment"] == "review_next" for case in cases)

    for case in cases:
        prediction = by_id.get(case["id"])
        if prediction is None or prediction.get("status") not in ("completed", "cache_hit"):
            errors.append({"case_id": case["id"], "expected": case["expected_decision"],
                           "predicted": "missing_or_failed"})
            continue
        result = prediction["result"]
        completed += 1
        try:
            validate_result(result, {item["evidence_id"] for item in case["bundle"]["evidence"]})
            valid_citations += 1
        except ValueError as exc:
            errors.append({"case_id": case["id"], "expected": case["expected_decision"],
                           "predicted": result.get("decision"), "error": str(exc)})
            continue
        predicted = result["decision"]
        expected = case["expected_decision"]
        confusion[expected][predicted] += 1
        correct += predicted == expected
        if expected != "insufficient_evidence":
            acceptable_citations += bool(set(result["evidence_ids"]) & set(case["acceptable_citation_ids"]))
        if case["segment"] == "review_next":
            safety_proxy_pass += cautious_v5_note(result)
        if predicted != expected:
            errors.append({"case_id": case["id"], "expected": expected, "predicted": predicted})

    per_class = {}
    for label in LABELS:
        tp = confusion[label][label]
        fp = sum(confusion[other][label] for other in LABELS if other != label)
        fn = sum(confusion[label][other] for other in LABELS if other != label)
        # Missing/failed cases count as false negatives, never silently disappear.
        fn += sum(case["expected_decision"] == label for case in cases) - sum(confusion[label].values())
        precision = tp / (tp + fp) if tp + fp else 0.0
        recall = tp / (tp + fn) if tp + fn else 0.0
        f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
        per_class[label] = {"support": sum(case["expected_decision"] == label for case in cases),
                            "precision": precision, "recall": recall, "f1": f1,
                            "tp": tp, "fp": fp, "fn": fn}
    return {
        "cases": len(cases), "completed": completed, "accuracy": correct / len(cases),
        "macro_f1": sum(row["f1"] for row in per_class.values()) / len(LABELS),
        "per_class": per_class,
        "citation_validity_rate": valid_citations / len(cases),
        "labelled_anchor_citation_rate": acceptable_citations / research_count,
        "direct_unverified_wording_gate_rate": safety_proxy_pass / direct_unverified_count,
        "confusion": {label: dict(confusion[label]) for label in LABELS},
        "errors": errors,
    }


def make_report(results: dict) -> str:
    previous, current = results["prompt_versions"]
    p, c = results["metrics"][previous], results["metrics"][current]
    def pct(value):
        return f"{value * 100:.1f}%"

    rows = [
        "# Account-research prompt eval",
        "",
        f"Run: {results['run_at_utc']} · model: `{results['model']}` · {results['case_count']} labelled cases",
        "",
        "| Metric | Previous " + previous + " | Current " + current + " |",
        "| --- | ---: | ---: |",
        f"| Decision accuracy | {pct(p['accuracy'])} | {pct(c['accuracy'])} |",
        f"| Macro F1 | {pct(p['macro_f1'])} | {pct(c['macro_f1'])} |",
        f"| Supported precision | {pct(p['per_class']['supported']['precision'])} | {pct(c['per_class']['supported']['precision'])} |",
        f"| Supported recall | {pct(p['per_class']['supported']['recall'])} | {pct(c['per_class']['supported']['recall'])} |",
        f"| Acceptable evidence citation | {pct(p['labelled_anchor_citation_rate'])} | {pct(c['labelled_anchor_citation_rate'])} |",
        f"| Unverified-label wording gate (lexical proxy) | {pct(p['direct_unverified_wording_gate_rate'])} | {pct(c['direct_unverified_wording_gate_rate'])} |",
        "",
        f"Macro F1 change: **{(c['macro_f1'] - p['macro_f1']) * 100:+.1f} percentage points**.",
        "",
        "## Per-class decision metrics",
        "",
        "| Prompt | Label | Cases | Precision | Recall | F1 |",
        "| --- | --- | ---: | ---: | ---: | ---: |",
    ]
    for version in (previous, current):
        for label in LABELS:
            row = results["metrics"][version]["per_class"][label]
            rows.append(f"| {version} | {label} | {row['support']} | {pct(row['precision'])} | {pct(row['recall'])} | {pct(row['f1'])} |")
    rows += ["", "## Current-prompt errors", ""]
    if c["errors"]:
        rows += [f"- `{item['case_id']}`: expected `{item['expected']}`, got `{item['predicted']}`"
                 for item in c["errors"]]
    else:
        rows.append("- No decision or schema errors on this small set.")
    rows += [
        "", "## What this does and does not measure", "",
        "Twenty-two cases have Codex-curated draft decision labels from the supplied snapshot; three are marked synthetic negative controls. The labels have not been independently human-adjudicated; `label_review.md` is provided for applicant review. Cases were deliberately chosen to stress direct, unverified, and partial matches. They are not a random sample of 425,121 candidate domains. The citation metric checks whether a response cites one of the reviewed evidence rows, not whether the service operator is known. The wording gate is the published lexical safety proxy, not a human judgement of prose quality. Outputs are advisory and require human verification. See `labelled_cases.jsonl` for input evidence and label rationales and `predictions.jsonl` for exact model outputs.",
        "",
    ]
    return "\n".join(rows)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true", help="Call the API via the shared budgeted client")
    parser.add_argument("--previous", default="v4")
    parser.add_argument("--current", default="v5")
    args = parser.parse_args()
    versions = (args.previous, args.current)
    if versions[0] == versions[1]:
        parser.error("Previous and current prompt versions must differ")
    prompt_hashes = {}
    for version in versions:
        prompt = ROOT / "prompts" / "account-research" / f"{version}.md"
        if not prompt.is_file():
            parser.error(f"Missing prompt: {prompt}")
        prompt_hashes[version] = sha256_file(prompt)
    cases = load_cases()
    if args.live:
        predictions = run_live(cases, versions)
        for record in predictions:
            record["prompt_sha256"] = prompt_hashes[record["prompt_version"]]
        # Preserve a failed run's partial outputs for inspection without
        # replacing the last complete, reviewable comparison.
        if len(predictions) != len(cases) * len(versions) or any(
            row["status"] == "failed" for row in predictions
        ):
            partial = ROOT / "artifacts" / "ai" / "eval_partial.jsonl"
            partial.parent.mkdir(parents=True, exist_ok=True)
            partial.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in predictions))
            print(f"Incomplete eval; previous results retained. Inspect {partial}", file=sys.stderr)
            return 1
        temp = PREDICTIONS_PATH.with_suffix(".jsonl.tmp")
        temp.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in predictions))
        temp.replace(PREDICTIONS_PATH)
    else:
        predictions = read_jsonl(PREDICTIONS_PATH)
        cases_by_id = {case["id"]: case for case in cases}
        for row in predictions:
            if row["prompt_version"] in prompt_hashes and row.get("prompt_sha256") != prompt_hashes[row["prompt_version"]]:
                raise ValueError("Saved prediction uses a different prompt file; re-run with --live")
            case = cases_by_id.get(row["case_id"])
            if case is None or row.get("bundle_sha256") != bundle_sha256(case["bundle"]):
                raise ValueError("Saved prediction uses a different evidence bundle; re-run with --live")
    metrics = {version: score_version(cases, predictions, version) for version in versions}
    result = {
        "run_at_utc": datetime.now(timezone.utc).isoformat(),
        "model": predictions[0]["model"] if predictions else DEFAULT_MODEL,
        "case_count": len(cases), "case_set_sha256": sha256_file(CASES_PATH),
        "label_counts": dict(Counter(case["expected_decision"] for case in cases)),
        "origin_counts": dict(Counter(case["origin"] for case in cases)),
        "prompt_versions": versions, "prompt_sha256": prompt_hashes,
        "metrics": metrics,
        "delta_macro_f1": metrics[versions[1]]["macro_f1"] - metrics[versions[0]]["macro_f1"],
    }
    RESULTS_PATH.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n")
    REPORT_PATH.write_text(make_report(result))
    print(make_report(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
