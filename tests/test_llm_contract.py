"""Check that offline AI output cannot cite absent source evidence."""

import unittest

from welook.llm_client import validate_result


class LlmContractTest(unittest.TestCase):
    def test_unprovided_evidence_reference_is_rejected(self):
        result = {"decision": "supported", "evidence_ids": ["invented"],
                  "reason": "Match", "next_action": "Verify operator"}
        with self.assertRaises(ValueError):
            validate_result(result, {"provided"})


if __name__ == "__main__":
    unittest.main()
