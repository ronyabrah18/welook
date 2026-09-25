"""Register all completed immutable silver arrivals as DuckDB's raw source."""

import argparse
import json
from pathlib import Path

import duckdb


ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", required=True, type=Path,
                        help="A completed run; all completed sibling runs are registered")
    parser.add_argument("--db", type=Path, default=ROOT / "artifacts" / "warehouse" / "sales.duckdb")
    args = parser.parse_args()
    selected = json.loads((args.run / "manifest.json").read_text())
    if selected["status"] != "complete":
        raise ValueError("Run needs quality review before registering")
    runs = []
    for manifest_path in sorted(args.run.parent.glob("*/manifest.json")):
        manifest = json.loads(manifest_path.read_text())
        if manifest["status"] == "complete" and manifest.get("max_records") is None:
            runs.append((manifest_path.parent, manifest))
    if not runs:
        raise ValueError("No completed full arrivals to register")
    patterns = [str((run_dir / "silver" / "*.parquet").resolve()).replace("'", "''")
                for run_dir, _ in runs]
    sql_patterns = "[" + ", ".join(f"'{pattern}'" for pattern in patterns) + "]"
    args.db.parent.mkdir(parents=True, exist_ok=True)
    with duckdb.connect(str(args.db)) as con:
        con.execute("CREATE SCHEMA IF NOT EXISTS raw")
        prior = con.execute("SELECT table_type FROM information_schema.tables WHERE table_schema = 'raw' AND table_name = 'observations'").fetchone()
        if prior:
            con.execute("DROP VIEW raw.observations" if prior[0] == "VIEW" else "DROP TABLE raw.observations")
        con.execute(f"CREATE OR REPLACE VIEW raw.observations AS SELECT * FROM read_parquet({sql_patterns})")
        con.execute("CREATE OR REPLACE TABLE raw.ingestion_manifest (run_id VARCHAR, source_sha256 VARCHAR, source_lines BIGINT, accepted_rows BIGINT)")
        con.executemany("INSERT INTO raw.ingestion_manifest VALUES (?, ?, ?, ?)", [
            (manifest["run_id"], manifest["source_sha256"],
             manifest["counts"]["source_lines"], manifest["counts"]["silver_rows"])
            for _, manifest in runs])
        count = con.execute("SELECT count(*) FROM raw.observations").fetchone()[0]
        if count != sum(manifest["counts"]["silver_rows"] for _, manifest in runs):
            raise ValueError("Registered silver count differs from manifest")
    print(json.dumps({"db": str(args.db), "source_files": len(runs), "silver_rows": count}))


if __name__ == "__main__":
    main()
