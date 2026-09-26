"""The offline publication step must not promote unreviewed supported claims."""

import json
from pathlib import Path
import tempfile
import unittest

from scripts.publish_assessments import publish


class PublishAssessmentsTest(unittest.TestCase):
    def test_only_cautious_batch_results_are_selected(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            batch, reviewed, output = (root / name for name in ("batch.jsonl", "reviewed.jsonl", "out.jsonl"))
            reviewed.write_text("")
            records = [
                {"candidate_domain": "a.example", "prompt_version": "v2", "status": "completed",
                 "assessed_at_utc": "2026-09-26T00:00:00+00:00", "model": "test-model",
                 "result": {"decision": "supported"}},
                {"candidate_domain": "b.example", "prompt_version": "v2", "status": "completed",
                 "assessed_at_utc": "2026-09-26T00:00:00+00:00", "model": "test-model",
                 "result": {"decision": "needs_review"}},
                {"candidate_domain": "c.example", "prompt_version": "v2", "status": "failed",
                 "result": {"decision": "insufficient_evidence"}},
            ]
            batch.write_text("".join(json.dumps(record) + "\n" for record in records))
            report = publish(batch, reviewed, output)
            published = [json.loads(line) for line in output.read_text().splitlines()]
            self.assertEqual(report["withheld_supported_batch_outputs"], 1)
            self.assertEqual([record["candidate_domain"] for record in published], ["b.example"])
            self.assertEqual(published[0]["review_status"], "guardrail_checked")


if __name__ == "__main__":
    unittest.main()
