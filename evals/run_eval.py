"""Validate cases or run a budgeted v1/v2 LLM evaluation in one command.

Dry-run (no API key or charges): uv run python evals/run_eval.py
Live evaluation: uv run python evals/run_eval.py --live
"""

import argparse
from collections import Counter
from datetime import datetime, timezone
import json
from pathlib import Path

from llm_client import BudgetedAssessor, validate_result


ROOT = Path(__file__).resolve().parents[1]
LABELS = ("supported", "needs_review", "insufficient_evidence")


def load_cases(path: Path) -> list[dict]:
    cases = [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
    ids = set()
    for case in cases:
        if case["case_id"] in ids:
            raise ValueError(f"Duplicate case ID: {case['case_id']}")
        ids.add(case["case_id"])
        if case["expected"] not in LABELS:
            raise ValueError(f"Unknown label in {case['case_id']}")
        if case["split"] not in ("development", "held_out"):
            raise ValueError(f"Unknown split in {case['case_id']}")
        evidence = case["evidence"]
        if not evidence or len({item["evidence_id"] for item in evidence}) != len(evidence):
            raise ValueError(f"Missing or repeated evidence IDs in {case['case_id']}")
    return cases


def metrics(cases: list[dict], predictions: list[dict]) -> dict:
    by_id = {item["case_id"]: item for item in predictions}
    result = {"cases": len(cases), "successful_outputs": 0, "missing_outputs": 0,
              "evidence_reference_validity": None, "per_class": {}}
    grounded = 0
    for label in LABELS:
        tp = fp = fn = 0
        for case in cases:
            pred = by_id.get(case["case_id"], {}).get("predicted")
            if pred == label and case["expected"] == label:
                tp += 1
            elif pred == label:
                fp += 1
            elif case["expected"] == label:
                fn += 1
        precision = tp / (tp + fp) if tp + fp else 0.0
        recall = tp / (tp + fn) if tp + fn else 0.0
        f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
        result["per_class"][label] = {"support": sum(c["expected"] == label for c in cases),
                                       "precision": precision, "recall": recall, "f1": f1}
    for case in cases:
        pred = by_id.get(case["case_id"], {})
        if pred.get("predicted") in LABELS:
            result["successful_outputs"] += 1
            if pred.get("evidence_valid"):
                grounded += 1
        else:
            result["missing_outputs"] += 1
    result["response_coverage"] = result["successful_outputs"] / len(cases) if cases else 0
    result["evidence_reference_validity"] = grounded / result["successful_outputs"] if result["successful_outputs"] else 0
    result["macro_f1"] = sum(result["per_class"][label]["f1"] for label in LABELS) / len(LABELS)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cases", type=Path, default=ROOT / "evals" / "labelled_cases.jsonl")
    parser.add_argument("--prompt", choices=["v1", "v2", "both"], default="both")
    parser.add_argument("--live", action="store_true", help="Make real paid API calls under the US$10 ledger")
    parser.add_argument("--output-dir", type=Path, default=ROOT / "artifacts" / "ai" / "eval_runs")
    args = parser.parse_args()
    cases = load_cases(args.cases)
    counts = Counter(case["expected"] for case in cases)
    if not args.live:
        print(json.dumps({"mode": "dry_run_no_api_calls", "cases": len(cases),
                          "split_counts": dict(Counter(c["split"] for c in cases)),
                          "label_counts": dict(counts)}, indent=2))
        return
    assessor = BudgetedAssessor()
    versions = ["v1", "v2"] if args.prompt == "both" else [args.prompt]
    args.output_dir.mkdir(parents=True, exist_ok=True)
    report = {"at_utc": datetime.now(timezone.utc).isoformat(), "model": assessor.model,
              "case_count": len(cases), "versions": {}}
    for version in versions:
        predictions = []
        for index, case in enumerate(cases, 1):
            bundle = {"candidate_domain": case["candidate_domain"], "evidence": case["evidence"]}
            try:
                output = assessor.assess(bundle, version)
                result = output["result"]
                validate_result(result, {e["evidence_id"] for e in case["evidence"]})
                predictions.append({"case_id": case["case_id"], "expected": case["expected"],
                                    "predicted": result["decision"], "evidence_valid": True,
                                    "result": result, "call_status": output["status"]})
            except Exception as exc:
                predictions.append({"case_id": case["case_id"], "expected": case["expected"],
                                    "predicted": None, "evidence_valid": False,
                                    "error": f"{type(exc).__name__}: {str(exc)[:200]}"})
            print(f"{version}: {index}/{len(cases)}", flush=True)
        version_metrics = metrics(cases, predictions)
        version_metrics["by_split"] = {
            split: metrics([case for case in cases if case["split"] == split], predictions)
            for split in ("development", "held_out")
        }
        report["versions"][version] = version_metrics
        with (args.output_dir / f"predictions_{version}.jsonl").open("w") as out:
            for prediction in predictions:
                out.write(json.dumps(prediction, ensure_ascii=False) + "\n")
    if len(versions) == 2:
        report["comparison"] = {
            "macro_f1_delta_v2_minus_v1":
                report["versions"]["v2"]["macro_f1"] - report["versions"]["v1"]["macro_f1"],
            "held_out_macro_f1_delta_v2_minus_v1":
                report["versions"]["v2"]["by_split"]["held_out"]["macro_f1"]
                - report["versions"]["v1"]["by_split"]["held_out"]["macro_f1"],
        }
    (args.output_dir / "results.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
