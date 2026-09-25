"""Small contract checks for file-level incremental loading and validation."""

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

import duckdb
import pyarrow.parquet as pq

from scripts.ingest_full import ROOT, ingest


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


if __name__ == "__main__":
    unittest.main()
