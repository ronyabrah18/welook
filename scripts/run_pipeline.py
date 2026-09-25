"""Build the full WeLook snapshot from one immutable source file.

Run: uv run python scripts/run_pipeline.py
The optional AI assessment is a separate, budgeted offline step.
"""

import argparse
import os
from pathlib import Path
import subprocess
import sys

from ingest_full import ROOT, ingest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=ROOT / "b2_download_file_by_id")
    parser.add_argument("--limit", type=int, default=50_000, help="Maximum hosted candidate domains")
    args = parser.parse_args()
    result = ingest(args.input, ROOT / "artifacts" / "runs")
    if result["status"] != "complete":
        raise RuntimeError("Ingestion needs quality review; serving snapshot not published")
    run_dir = ROOT / "artifacts" / "runs" / result["run_id"]
    db = ROOT / "artifacts" / "warehouse" / "full.duckdb"
    subprocess.run([sys.executable, str(ROOT / "scripts" / "register_silver.py"),
                    "--run", str(run_dir), "--db", str(db)], check=True)
    env = {**os.environ, "FIRMABLE_DB_PATH": str(db)}
    subprocess.run([str(ROOT / ".venv" / "bin" / "dbt"), "build", "--profiles-dir", "."],
                   cwd=ROOT / "transform", env=env, check=True)
    subprocess.run([sys.executable, str(ROOT / "scripts" / "export_serving.py"),
                    "--db", str(db), "--limit", str(args.limit)], check=True)
    print("Complete: app/data/welook_serving.duckdb is ready for Streamlit")


if __name__ == "__main__":
    main()
