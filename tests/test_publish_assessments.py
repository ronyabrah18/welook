"""The offline publication step must not promote unreviewed supported claims."""

import json
from pathlib import Path
import tempfile
import unittest

from scripts.publish_assessments import publish, stable_evidence_id


class PublishAssessmentsTest(unittest.TestCase):
    def test_newer_prompt_replaces_old_account_note(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            batch, reviewed, output = (root / name for name in ("batch.jsonl", "reviewed.jsonl", "out.jsonl"))
            reviewed.write_text("")
            records = [
                {"candidate_domain": "a.example", "prompt_version": "v2", "status": "completed",
                 "assessed_at_utc": "2026-09-25T00:00:00+00:00", "model": "test-model",
                 "result": {"decision": "supported", "evidence_ids": ["source-line-1"]}},
                {"candidate_domain": "a.example", "prompt_version": "v4", "status": "completed",
                 "assessed_at_utc": "2026-09-26T00:00:00+00:00", "model": "test-model",
                 "source_registry_hash": "new-source-set",
                 "result": {"decision": "needs_review", "evidence_ids": ["source-record-new"]}},
            ]
            batch.write_text("".join(json.dumps(record) + "\n" for record in records))
            report = publish(batch, reviewed, output, "a" * 64)
            published = json.loads(output.read_text().strip())
            self.assertEqual(report["published"], 1)
            self.assertEqual(published["prompt_version"], "v4")
            self.assertEqual(published["source_registry_hash"], "new-source-set")

    def test_only_cautious_batch_results_are_selected(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            batch, reviewed, output = (root / name for name in ("batch.jsonl", "reviewed.jsonl", "out.jsonl"))
            reviewed.write_text("")
            records = [
                {"candidate_domain": "a.example", "prompt_version": "v2", "status": "completed",
                 "assessed_at_utc": "2026-09-26T00:00:00+00:00", "model": "test-model",
                 "result": {"decision": "supported", "evidence_ids": ["source-line-1"]}},
                {"candidate_domain": "b.example", "prompt_version": "v2", "status": "completed",
                 "assessed_at_utc": "2026-09-26T00:00:00+00:00", "model": "test-model",
                 "result": {"decision": "needs_review", "evidence_ids": ["source-line-2"]}},
                {"candidate_domain": "c.example", "prompt_version": "v2", "status": "failed",
                 "result": {"decision": "insufficient_evidence"}},
            ]
            batch.write_text("".join(json.dumps(record) + "\n" for record in records))
            report = publish(batch, reviewed, output, "a" * 64)
            published = [json.loads(line) for line in output.read_text().splitlines()]
            self.assertEqual(report["withheld_supported_batch_outputs"], 1)
            self.assertEqual([record["candidate_domain"] for record in published], ["b.example"])
            self.assertEqual(published[0]["review_status"], "guardrail_checked")
            self.assertEqual(published[0]["result"]["evidence_ids"],
                             [stable_evidence_id("source-line-2", "a" * 64)])


if __name__ == "__main__":
    unittest.main()
