"""Publication controls for offline AI decisions."""

import json
from pathlib import Path
import tempfile
import unittest

import duckdb

from scripts.export_serving import validate_published_assessments


class ServingAiTest(unittest.TestCase):
    def setUp(self):
        self.con = duckdb.connect()
        self.con.execute("ATTACH ':memory:' AS serving")
        self.con.execute("CREATE TABLE serving.accounts (candidate_domain VARCHAR, attribution_status VARCHAR)")
        self.con.execute("CREATE TABLE serving.evidence (candidate_domain VARCHAR, source_line BIGINT, http_domain_match BOOLEAN, cert_domain_match BOOLEAN)")
        self.con.execute("INSERT INTO serving.accounts VALUES ('platform.example', 'provider_only'), ('firm.example', 'partial'), ('direct.example', 'supported')")
        self.con.execute("INSERT INTO serving.evidence VALUES ('platform.example', 1, true, true), ('firm.example', 2, false, true), ('direct.example', 3, true, true)")

    def tearDown(self):
        self.con.close()

    def check_record(self, domain, decision, evidence_ids, review_status="reviewed_for_demo"):
        record = {"candidate_domain": domain, "review_status": review_status, "status": "completed",
                  "result": {"decision": decision, "evidence_ids": evidence_ids}}
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "assessments.jsonl"
            path.write_text(json.dumps(record) + "\n")
            validate_published_assessments(self.con, path)

    def test_matching_review_evidence_is_publishable(self):
        self.check_record("firm.example", "needs_review", ["source-line-2"])

    def test_provider_supported_claim_is_blocked(self):
        with self.assertRaisesRegex(ValueError, "Provider-only"):
            self.check_record("platform.example", "supported", ["source-line-1"])

    def test_missing_cited_evidence_is_blocked(self):
        with self.assertRaisesRegex(ValueError, "absent"):
            self.check_record("firm.example", "supported", ["source-line-999"])

    def test_partial_supported_claim_is_blocked(self):
        with self.assertRaisesRegex(ValueError, "double domain match"):
            self.check_record("firm.example", "supported", ["source-line-2"])

    def test_batch_supported_claim_is_blocked_even_with_double_match(self):
        with self.assertRaisesRegex(ValueError, "individual review"):
            self.check_record("direct.example", "supported", ["source-line-3"], "guardrail_checked")

    def test_cautious_batch_note_is_publishable(self):
        self.check_record("firm.example", "needs_review", ["source-line-2"], "guardrail_checked")


if __name__ == "__main__":
    unittest.main()
