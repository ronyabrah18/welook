"""Small contract checks for file-level incremental loading and validation."""

import json
import hashlib
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

import duckdb
import pyarrow.parquet as pq

from scripts.ingest_full import ROOT, build_silver, ingest, ingest_bronze
from welook.lineage import source_registry_hash


def observation(domain: str, port: int = 443) -> dict:
    return {"ip_str": "203.0.113.10", "port": port, "transport": "tcp",
            "timestamp": "2026-09-21T10:00:00", "domains": [domain],
            "http": {"host": f"www.{domain}", "title": "Example"},
            "ssl": {"cert": {"subject": {"CN": domain}}}}


def write_jsonl(path: Path, rows: list[dict]):
    with path.open("w") as stream:
        for row in rows:
            stream.write(json.dumps(row) + "\n")


class IngestionContractTest(unittest.TestCase):
    def test_second_arrival_updates_gold_and_serving_once(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            runs = root / "runs"
            db = root / "incremental.duckdb"
            serving = root / "serving.duckdb"
            assessments = root / "published-ai.jsonl"
            first, second = root / "first.jsonl", root / "second.jsonl"
            write_jsonl(first, [{**observation("example.com"),
                                 "http": {"host": "www.example.com", "title": "Admin login"}}])
            write_jsonl(second, [
                {**observation("example.com", 8443), "domains": ["example.com", "EXAMPLE.COM"]},
                {**observation("other.co.uk"), "vulns": {"CVE-2026-0001": {"verified": True}}},
                {**observation("example.com", 9443),
                 "http": {"host": "unrelated.net", "title": "Example"},
                 "ssl": {"cert": {"subject": {"CN": "unrelated.net"}}},
                 "vulns": {"CVE-2026-0002": {"verified": True}}},
            ])

            def refresh(run_dir):
                subprocess.run([sys.executable, str(ROOT / "scripts" / "register_silver.py"),
                                "--run", str(run_dir), "--db", str(db)],
                               check=True, capture_output=True)
                env = {**os.environ, "FIRMABLE_DB_PATH": str(db)}
                subprocess.run([str(ROOT / ".venv" / "bin" / "dbt"), "build",
                                "--profiles-dir", "."], cwd=ROOT / "transform", env=env,
                               check=True, capture_output=True)
                subprocess.run([sys.executable, str(ROOT / "scripts" / "register_ai_gold.py"),
                                "--db", str(db), "--assessments", str(assessments)],
                               check=True, capture_output=True)
                subprocess.run([sys.executable, str(ROOT / "scripts" / "export_serving.py"),
                                "--db", str(db), "--output", str(serving)],
                               check=True, capture_output=True)

            first_run = ingest(first, runs)
            first_record_id = hashlib.sha256(f"{first_run['source_sha256']}:1".encode()).hexdigest()
            assessments.write_text(json.dumps({
                "candidate_domain": "example.com", "status": "completed",
                "review_status": "reviewed_for_demo", "prompt_version": "v2",
                "model": "fixture", "assessed_at_utc": "2026-09-21T11:00:00+00:00",
                "source_registry_hash": source_registry_hash([first_run["source_sha256"]]),
                "result": {"decision": "supported", "evidence_ids": [f"source-record-{first_record_id}"],
                           "reason": "Host and certificate match", "next_action": "Confirm the operator"},
            }) + "\n")
            refresh(runs / first_run["run_id"])
            with duckdb.connect(str(db), read_only=True) as con:
                self.assertEqual(con.execute("SELECT count(*) FROM analytics.account_ai_assessments").fetchone()[0], 1)
            with duckdb.connect(str(serving), read_only=True) as con:
                self.assertEqual(con.execute("SELECT count(*) FROM accounts").fetchone()[0], 1)
                self.assertEqual(con.execute("SELECT observation_count FROM accounts WHERE candidate_domain='example.com'").fetchone()[0], 1)
                self.assertEqual(con.execute("SELECT priority_tier FROM accounts WHERE candidate_domain='example.com'").fetchone()[0], "research")
                self.assertEqual(con.execute("SELECT count(*) FROM assessments").fetchone()[0], 1)

            second_run = ingest(second, runs)
            refresh(runs / second_run["run_id"])
            with duckdb.connect(str(db), read_only=True) as con:
                self.assertEqual(con.execute("SELECT count(*) FROM analytics.account_ai_assessments").fetchone()[0], 0)
                self.assertEqual(con.execute("SELECT stale_ai_notes_skipped FROM analytics.ai_assessment_build_info").fetchone()[0], 1)
            with duckdb.connect(str(serving), read_only=True) as con:
                self.assertEqual(con.execute("SELECT count(*) FROM accounts").fetchone()[0], 2)
                self.assertEqual(con.execute("SELECT observation_count FROM accounts WHERE candidate_domain='example.com'").fetchone()[0], 3)
                self.assertEqual(con.execute("SELECT priority_tier FROM accounts WHERE candidate_domain='example.com'").fetchone()[0], "research")
                self.assertEqual(con.execute("SELECT verified_vulnerability_association_count, directly_supported_verified_observation_count FROM accounts WHERE candidate_domain='example.com'").fetchone(), (1, 0))
                self.assertEqual(con.execute("SELECT priority_tier FROM accounts WHERE candidate_domain='other.co.uk'").fetchone()[0], "investigate_first")
                self.assertEqual(con.execute("SELECT count(*) FROM evidence WHERE candidate_domain='example.com'").fetchone()[0], 3)
                self.assertEqual(con.execute("SELECT count(DISTINCT source_record_id) FROM evidence WHERE candidate_domain='example.com'").fetchone()[0], 3)
                self.assertEqual(con.execute("SELECT count(*) FROM evidence WHERE candidate_domain='example.com' AND source_line=1").fetchone()[0], 2)
                self.assertEqual(con.execute("SELECT count(*) FROM assessments").fetchone()[0], 0)
                self.assertEqual(con.execute("SELECT stale_ai_notes_skipped FROM build_info").fetchone()[0], 1)

            repeated = ingest(second, runs)
            self.assertEqual(repeated["result"], "skipped_existing_complete_run")
            refresh(runs / second_run["run_id"])
            with duckdb.connect(str(serving), read_only=True) as con:
                self.assertEqual(con.execute("SELECT count(*) FROM evidence WHERE candidate_domain='example.com'").fetchone()[0], 3)

    def test_new_file_repeat_and_second_arrival(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            output = root / "runs"
            first = root / "first.jsonl"
            second = root / "second.jsonl"
            write_jsonl(first, [observation("example.com")])
            initial = ingest(first, output)
            repeated = ingest(first, output)
            self.assertEqual(initial["counts"]["silver_rows"], 1)
            self.assertEqual(repeated["result"], "skipped_existing_complete_run")
            write_jsonl(second, [observation("example.com", 8443), observation("other.co.uk")])
            arrival = ingest(second, output)
            self.assertNotEqual(initial["run_id"], arrival["run_id"])
            self.assertEqual(arrival["counts"]["silver_rows"], 2)
            self.assertEqual(len(list(output.glob("*/manifest.json"))), 2)
            part = next((output / arrival["run_id"] / "silver").glob("*.parquet"))
            self.assertEqual(pq.read_table(part).num_rows, 2)
            db = root / "combined.duckdb"
            subprocess.run([sys.executable, str(ROOT / "scripts" / "register_silver.py"),
                            "--run", str(output / arrival["run_id"]), "--db", str(db)],
                           check=True, capture_output=True)
            with duckdb.connect(str(db), read_only=True) as con:
                self.assertEqual(con.execute("SELECT count(*) FROM raw.observations").fetchone()[0], 3)
                self.assertEqual(con.execute("SELECT count(*) FROM raw.ingestion_manifest").fetchone()[0], 2)

    def test_invalid_core_is_retained_in_bronze_and_flagged(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "bad.jsonl"
            write_jsonl(source, [observation("example.com", 70000)])
            result = ingest(source, root / "runs")
            self.assertEqual(result["status"], "needs_review")
            self.assertEqual(result["counts"]["bronze_rows"], 1)
            self.assertEqual(result["counts"]["core_rejects"], 1)
            self.assertEqual(result["counts"]["silver_rows"], 0)
            self.assertEqual(json.loads((root / "runs" / result["run_id"] / "quarantine.jsonl").read_text())["stage"], "core")

    def test_silver_replays_completed_bronze_without_landing_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "source.jsonl"
            write_jsonl(source, [observation("example.com")])
            bronze = ingest_bronze(source, root / "runs")
            run_dir = root / "runs" / bronze["run_id"]
            self.assertTrue((run_dir / "bronze_manifest.json").exists())
            self.assertFalse((run_dir / "silver").exists())
            source.unlink()
            silver = build_silver(run_dir)
            self.assertEqual(silver["counts"]["silver_rows"], 1)
            self.assertEqual(pq.read_table(next((run_dir / "silver").glob("*.parquet"))).num_rows, 1)

    def test_malformed_source_record_goes_to_bronze_and_quarantine(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "bad.jsonl"
            source.write_bytes(b"{invalid json}\n\xff\n")
            result = ingest(source, root / "runs")
            run_dir = root / "runs" / result["run_id"]
            self.assertEqual(result["status"], "needs_review")
            self.assertEqual(result["counts"]["bronze_rows"], 2)
            self.assertEqual(result["counts"]["parse_rejects"], 2)
            self.assertEqual(result["counts"]["silver_rows"], 0)
            self.assertEqual(len((run_dir / "quarantine.jsonl").read_text().splitlines()), 2)


if __name__ == "__main__":
    unittest.main()
