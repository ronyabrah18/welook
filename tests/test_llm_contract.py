"""Check that offline AI output cannot cite absent source evidence."""

import unittest

from welook.llm_client import redact_network_literals, validate_result


class LlmContractTest(unittest.TestCase):
    def test_unprovided_evidence_reference_is_rejected(self):
        result = {"decision": "supported", "evidence_ids": ["invented"],
                  "reason": "Match", "next_action": "Verify operator"}
        with self.assertRaises(ValueError):
            validate_result(result, {"provided"})

    def test_ip_literals_are_redacted_before_external_request(self):
        original = {"http_host": "192.0.2.1", "http_title": "at 198.51.100.8",
                    "certificate_cn": "[2001:db8::1]", "product": "nginx"}
        safe = redact_network_literals(original)
        self.assertEqual(safe["http_host"], "[IP address redacted]")
        self.assertEqual(safe["http_title"], "at [IP address redacted]")
        self.assertEqual(safe["certificate_cn"], "[IP address redacted]")
        self.assertEqual(original["http_host"], "192.0.2.1")


if __name__ == "__main__":
    unittest.main()
