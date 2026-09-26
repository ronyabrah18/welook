"""Publication controls for offline AI decisions."""

import json
from pathlib import Path
import tempfile
import unittest

import duckdb

from scripts.register_ai_gold import validate_published_assessments


class ServingAiTest(unittest.TestCase):
    def setUp(self):
        self.con = duckdb.connect()
        self.con.execute("CREATE SCHEMA analytics")
        self.con.execute("CREATE TABLE analytics.fct_accounts (candidate_domain VARCHAR, attribution_status VARCHAR)")
        self.con.execute("CREATE TABLE analytics.int_account_evidence (candidate_domain VARCHAR, source_record_id VARCHAR, http_domain_match BOOLEAN, cert_domain_match BOOLEAN, evidence_score INTEGER, observed_at TIMESTAMP)")
        self.con.execute("INSERT INTO analytics.fct_accounts VALUES ('platform.example', 'provider_only'), ('firm.example', 'partial'), ('direct.example', 'supported')")
        self.con.execute("INSERT INTO analytics.int_account_evidence VALUES ('platform.example', 'one', true, true, 1, now()), ('firm.example', 'two', false, true, 1, now()), ('direct.example', 'three', true, true, 1, now())")

    def tearDown(self):
        self.con.close()

    def check_record(self, domain, decision, evidence_ids, review_status="reviewed_for_demo"):
        record = {"candidate_domain": domain, "review_status": review_status, "status": "completed",
                  "prompt_version": "test-v1", "model": "test-model",
                  "assessed_at_utc": "2026-09-21T11:00:00+00:00",
                  "result": {"decision": decision, "evidence_ids": evidence_ids,
                             "reason": "Test reason", "next_action": "Check operator"}}
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "assessments.jsonl"
            path.write_text(json.dumps(record) + "\n")
            accepted, stale = validate_published_assessments(self.con, path)
            self.assertEqual((len(accepted), stale), (1, 0))

    def test_matching_review_evidence_is_publishable(self):
        self.check_record("firm.example", "needs_review", ["source-record-two"])

    def test_provider_supported_claim_is_blocked(self):
        with self.assertRaisesRegex(ValueError, "Provider-only"):
            self.check_record("platform.example", "supported", ["source-record-one"])

    def test_missing_cited_evidence_is_blocked(self):
        with self.assertRaisesRegex(ValueError, "absent"):
            self.check_record("firm.example", "supported", ["source-record-999"])

    def test_partial_supported_claim_is_blocked(self):
        with self.assertRaisesRegex(ValueError, "double domain match"):
            self.check_record("firm.example", "supported", ["source-record-two"])

    def test_batch_supported_claim_is_blocked_even_with_double_match(self):
        with self.assertRaisesRegex(ValueError, "individual review"):
            self.check_record("direct.example", "supported", ["source-record-three"], "guardrail_checked")

    def test_cautious_batch_note_is_publishable(self):
        self.check_record("firm.example", "needs_review", ["source-record-two"], "guardrail_checked")


if __name__ == "__main__":
    unittest.main()
