"""Evaluation checks that would otherwise make quality numbers misleading."""

import sys
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "evals"))
from llm_client import validate_result  # noqa: E402
from run_eval import metrics  # noqa: E402


class EvalContractTest(unittest.TestCase):
    def test_missing_prediction_reduces_recall_and_coverage(self):
        cases = [{"case_id": "a", "expected": "supported"},
                 {"case_id": "b", "expected": "supported"}]
        predictions = [{"case_id": "a", "predicted": "supported", "evidence_valid": True}]
        result = metrics(cases, predictions)
        self.assertEqual(result["response_coverage"], 0.5)
        self.assertEqual(result["per_class"]["supported"]["recall"], 0.5)

    def test_unprovided_evidence_reference_is_rejected(self):
        result = {"decision": "supported", "evidence_ids": ["invented"],
                  "reason": "Match", "next_action": "Verify operator"}
        with self.assertRaises(ValueError):
            validate_result(result, {"provided"})


if __name__ == "__main__":
    unittest.main()
