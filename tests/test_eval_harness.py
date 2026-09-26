"""Check the denominator and confusion-matrix behavior of the eval harness."""

import unittest

from evals.run_eval import score_version


def case(case_id, decision, segment):
    evidence_id = f"evidence-{case_id}"
    return {"id": case_id, "expected_decision": decision, "segment": segment,
            "acceptable_citation_ids": [evidence_id] if decision != "insufficient_evidence" else [],
            "bundle": {"evidence": [{"evidence_id": evidence_id}]}}


def prediction(case_id, decision, reason="Historical service association"):
    return {"case_id": case_id, "prompt_version": "v5", "status": "completed",
            "result": {"decision": decision, "evidence_ids": [f"evidence-{case_id}"],
                       "reason": reason, "next_action": "Verify the finding and operator"}}


class EvalHarnessTest(unittest.TestCase):
    def test_false_positive_and_missing_prediction_are_counted(self):
        cases = [case("direct", "supported", "investigate_first"),
                 case("unverified", "needs_review", "review_next"),
                 case("unlinked", "insufficient_evidence", "negative")]
        predictions = [prediction("direct", "supported"),
                       prediction("unverified", "supported")]
        metrics = score_version(cases, predictions, "v5")
        self.assertAlmostEqual(metrics["accuracy"], 1 / 3)
        self.assertAlmostEqual(metrics["per_class"]["supported"]["precision"], 0.5)
        self.assertEqual(metrics["per_class"]["needs_review"]["fn"], 1)
        self.assertEqual(metrics["per_class"]["insufficient_evidence"]["fn"], 1)
        self.assertEqual(metrics["completed"], 2)

    def test_cautious_direct_note_passes_lexical_proxy(self):
        cases = [case("unverified", "needs_review", "review_next")]
        predictions = [prediction("unverified", "needs_review",
                                  "The direct observation has an unverified scanner label.")]
        metrics = score_version(cases, predictions, "v5")
        self.assertEqual(metrics["accuracy"], 1)
        self.assertEqual(metrics["labelled_anchor_citation_rate"], 1)
        self.assertEqual(metrics["direct_unverified_wording_gate_rate"], 1)


if __name__ == "__main__":
    unittest.main()
