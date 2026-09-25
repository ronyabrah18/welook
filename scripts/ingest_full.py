"""Stream an immutable JSONL or JSONL.zst arrival into faithful bronze and typed silver.

Run from the repository root:
    uv run python scripts/ingest_full.py

Outputs are published as a complete, checksum-addressed directory. Repeating an
identical successful arrival is a no-op. This command never loads the whole file.
"""

from __future__ import annotations

import argparse
from collections import Counter
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import ipaddress
import json
from pathlib import Path
import subprocess
import time
import uuid

import pyarrow as pa
import pyarrow.parquet as pq


ROOT = Path(__file__).resolve().parents[1]
SCHEMA_VERSION = "1"
MAX_RECORD_BYTES = 64 * 1024 * 1024
BRONZE_SCHEMA = pa.schema([
    ("source_file_id", pa.string()), ("source_line", pa.int64()),
    ("source_record_id", pa.string()), ("raw_content_sha256", pa.string()),
    ("ingestion_run_id", pa.string()), ("ingested_at_utc", pa.string()),
    ("raw_json", pa.large_string()),
])
SILVER_SCHEMA = pa.schema([
    ("source_file_id", pa.string()), ("source_line", pa.int64()),
    ("source_record_id", pa.string()), ("observation_id", pa.string()),
    ("ip_address", pa.string()), ("port", pa.int32()),
    ("transport", pa.string()), ("observed_at", pa.timestamp("us")),
    ("infrastructure_org", pa.string()), ("infrastructure_country", pa.string()),
    ("domains", pa.list_(pa.string())), ("hostnames", pa.list_(pa.string())),
    ("tags", pa.list_(pa.string())), ("product", pa.string()),
    ("version", pa.string()), ("scanner_module", pa.string()),
    ("http_host", pa.string()), ("http_title", pa.string()),
    ("certificate_cn", pa.string()), ("certificate_org", pa.string()),
    ("vulnerabilities_json", pa.large_string()), ("vulnerability_count", pa.int32()),
])


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(8 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


@contextmanager
def source_lines(path: Path, error_log: Path, allow_early_stop: bool = False):
    with path.open("rb") as probe:
        is_zstd = probe.read(4) == b"\x28\xb5\x2f\xfd"
    if not is_zstd:
        with path.open("rb") as source:
            yield source
        return
    with error_log.open("wb") as errors:
        proc = subprocess.Popen(["zstd", "-dc", str(path)], stdout=subprocess.PIPE,
                                stderr=errors)
        try:
            yield proc.stdout
            if allow_early_stop:
                if proc.poll() is None:
                    proc.terminate()
                proc.wait()
            elif proc.wait() != 0:
                raise RuntimeError(f"Decompression failed; inspect {error_log}")
        finally:
            proc.stdout.close()
            if proc.poll() is None:
                proc.terminate()
            proc.wait()


def optional_object(value, field: str, issues: Counter) -> dict:
    if value is None:
        return {}
    if isinstance(value, dict):
        return value
    issues[f"optional_type:{field}"] += 1
    return {}


def optional_text(value, field: str, issues: Counter) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        return value[:1000]
    issues[f"optional_type:{field}"] += 1
    return None


def string_list(value, field: str, issues: Counter) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, list):
        issues[f"optional_type:{field}"] += 1
        return []
    result = [item[:500] for item in value if isinstance(item, str)]
    if len(result) != len(value):
        issues[f"optional_item_type:{field}"] += len(value) - len(result)
    return result


def typed_observation(row: dict, identity: dict, issues: Counter) -> dict:
    ip_value = row.get("ip_str") or row.get("ipv6")
    ip = str(ipaddress.ip_address(ip_value))
    port = row.get("port")
    if isinstance(port, bool) or not isinstance(port, int) or not 0 <= port <= 65535:
        raise ValueError("invalid_port")
    transport = row.get("transport")
    if transport not in ("tcp", "udp"):
        raise ValueError("invalid_transport")
    timestamp = row.get("timestamp")
    if not isinstance(timestamp, str):
        raise ValueError("invalid_timestamp")
    try:
        observed_at = datetime.fromisoformat(timestamp)
    except ValueError as exc:
        raise ValueError("invalid_timestamp") from exc
    if observed_at.tzinfo is not None:
        raise ValueError("timezone_aware_timestamp_requires_policy")
    location = optional_object(row.get("location"), "location", issues)
    http = optional_object(row.get("http"), "http", issues)
    ssl = optional_object(row.get("ssl"), "ssl", issues)
    cert = optional_object(ssl.get("cert"), "ssl.cert", issues)
    subject = optional_object(cert.get("subject"), "ssl.cert.subject", issues)
    shodan = optional_object(row.get("_shodan"), "_shodan", issues)
    vulns = row.get("vulns")
    if vulns is not None and not isinstance(vulns, dict):
        issues["optional_type:vulns"] += 1
        vulns = None
    return {
        **{k: identity[k] for k in ("source_file_id", "source_line", "source_record_id")},
        "observation_id": identity["raw_content_sha256"],
        "ip_address": ip, "port": port, "transport": transport,
        "observed_at": observed_at,
        "infrastructure_org": optional_text(row.get("org"), "org", issues),
        "infrastructure_country": optional_text(location.get("country_code"), "location.country_code", issues),
        "domains": string_list(row.get("domains"), "domains", issues),
        "hostnames": string_list(row.get("hostnames"), "hostnames", issues),
        "tags": string_list(row.get("tags"), "tags", issues),
        "product": optional_text(row.get("product"), "product", issues),
        "version": optional_text(row.get("version"), "version", issues),
        "scanner_module": optional_text(shodan.get("module"), "_shodan.module", issues),
        "http_host": optional_text(http.get("host"), "http.host", issues),
        "http_title": optional_text(http.get("title"), "http.title", issues),
        "certificate_cn": optional_text(subject.get("CN"), "ssl.cert.subject.CN", issues),
        "certificate_org": optional_text(subject.get("O"), "ssl.cert.subject.O", issues),
        "vulnerabilities_json": json.dumps(vulns, ensure_ascii=False) if vulns else None,
        "vulnerability_count": len(vulns) if vulns else 0,
    }


class PartWriter:
    def __init__(self, root: Path):
        self.root = root
        self.part = 0
        self.raw_bytes = 0
        self.bronze = self.silver = None
        (root / "bronze").mkdir(parents=True)
        (root / "silver").mkdir(parents=True)

    def write(self, bronze_rows: list[dict], silver_rows: list[dict], raw_bytes: int):
        if not bronze_rows:
            return
        if self.bronze is None:
            name = f"part-{self.part:05d}.parquet"
            self.bronze = pq.ParquetWriter(self.root / "bronze" / name, BRONZE_SCHEMA,
                                           compression="zstd", compression_level=3)
            self.silver = pq.ParquetWriter(self.root / "silver" / name, SILVER_SCHEMA,
                                           compression="zstd", compression_level=3)
        self.bronze.write_table(pa.Table.from_pylist(bronze_rows, schema=BRONZE_SCHEMA))
        if silver_rows:
            self.silver.write_table(pa.Table.from_pylist(silver_rows, schema=SILVER_SCHEMA))
        self.raw_bytes += raw_bytes
        if self.raw_bytes >= 128 * 1024 * 1024:
            self.close_part()

    def close_part(self):
        if self.bronze is not None:
            self.bronze.close()
            self.silver.close()
            self.bronze = self.silver = None
            self.part += 1
            self.raw_bytes = 0


def ingest(source: Path, output: Path, max_records: int | None = None) -> dict:
    started = time.monotonic()
    source_id = file_sha256(source)
    run_id = f"{source_id[:20]}-v{SCHEMA_VERSION}" + (f"-first{max_records}" if max_records else "")
    final = output / run_id
    if (final / "manifest.json").exists():
        prior = json.loads((final / "manifest.json").read_text())
        if prior.get("status") == "complete" and prior.get("source_sha256") == source_id:
            return {**prior, "result": "skipped_existing_complete_run"}
    if final.exists():
        raise RuntimeError(f"Incomplete output exists: {final}; inspect before retry")
    output.mkdir(parents=True, exist_ok=True)
    stage = output / f".{run_id}.{uuid.uuid4().hex}.pending"
    stage.mkdir()
    writer = PartWriter(stage)
    counters = Counter()
    issues = Counter()
    bronze_batch: list[dict] = []
    silver_batch: list[dict] = []
    batch_bytes = 0
    ingested_at = datetime.now(timezone.utc).isoformat()
    try:
        with (stage / "quarantine.jsonl").open("w", encoding="utf-8") as quarantine:
            with source_lines(source, stage / "decompression.log", bool(max_records)) as stream:
                while True:
                    raw = stream.readline(MAX_RECORD_BYTES + 1)
                    if not raw:
                        break
                    counters["source_lines"] += 1
                    line = counters["source_lines"]
                    if len(raw) > MAX_RECORD_BYTES:
                        raise ValueError(f"Source line {line} exceeds 64 MiB; no truncated record published")
                    counters["decompressed_bytes"] += len(raw)
                    content = raw.rstrip(b"\r\n")
                    content_hash = hashlib.sha256(content).hexdigest()
                    try:
                        decoded = content.decode("utf-8")
                        row = json.loads(decoded)
                        if not isinstance(row, dict):
                            raise ValueError("non_object_json")
                    except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
                        counters["parse_rejects"] += 1
                        quarantine.write(json.dumps({"source_line": line, "stage": "parse",
                                                     "reason": type(exc).__name__,
                                                     "content_sha256": content_hash}) + "\n")
                        continue
                    identity = {"source_file_id": source_id, "source_line": line,
                                "source_record_id": hashlib.sha256(f"{source_id}:{line}".encode()).hexdigest(),
                                "raw_content_sha256": content_hash}
                    bronze_batch.append({**identity, "ingestion_run_id": run_id,
                                         "ingested_at_utc": ingested_at, "raw_json": decoded})
                    counters["bronze_rows"] += 1
                    batch_bytes += len(raw)
                    try:
                        silver_batch.append(typed_observation(row, identity, issues))
                        counters["silver_rows"] += 1
                    except (ValueError, TypeError, KeyError) as exc:
                        counters["core_rejects"] += 1
                        quarantine.write(json.dumps({"source_line": line, "stage": "core",
                                                     "reason": str(exc)[:200],
                                                     "content_sha256": content_hash}) + "\n")
                    if len(bronze_batch) >= 10_000 or batch_bytes >= 32 * 1024 * 1024:
                        writer.write(bronze_batch, silver_batch, batch_bytes)
                        bronze_batch, silver_batch, batch_bytes = [], [], 0
                    if line % 500_000 == 0:
                        print(json.dumps({"source_lines": line, "silver_rows": counters["silver_rows"],
                                          "elapsed_seconds": round(time.monotonic() - started)}), flush=True)
                    if max_records and line >= max_records:
                        break
            writer.write(bronze_batch, silver_batch, batch_bytes)
            writer.close_part()
        if counters["source_lines"] != counters["bronze_rows"] + counters["parse_rejects"]:
            raise AssertionError("Source-to-bronze reconciliation failed")
        if counters["bronze_rows"] != counters["silver_rows"] + counters["core_rejects"]:
            raise AssertionError("Bronze-to-silver reconciliation failed")
        quality_status = "needs_review" if counters["parse_rejects"] or counters["core_rejects"] else "complete"
        counts = {name: int(counters[name]) for name in (
            "source_lines", "decompressed_bytes", "bronze_rows", "parse_rejects",
            "silver_rows", "core_rejects")}
        manifest = {"status": quality_status, "schema_version": SCHEMA_VERSION,
                    "run_id": run_id, "source_path": str(source.resolve()),
                    "source_sha256": source_id, "source_bytes": source.stat().st_size,
                    "max_records": max_records, "ingested_at_utc": ingested_at,
                    "elapsed_seconds": round(time.monotonic() - started, 2),
                    "parts": writer.part, "counts": counts, "optional_issues": dict(issues),
                    "timestamp_policy": "source timestamp preserved without assumed timezone"}
        (stage / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
        stage.rename(final)
        return {**manifest, "result": "created", "output": str(final)}
    except Exception:
        writer.close_part()
        (stage / "failed.json").write_text(json.dumps({"counts": dict(counters),
                                                      "issues": dict(issues)}, indent=2) + "\n")
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=ROOT / "b2_download_file_by_id")
    parser.add_argument("--output", type=Path, default=ROOT / "artifacts" / "runs")
    parser.add_argument("--max-records", type=int, help="Development-only first N source lines")
    args = parser.parse_args()
    if args.max_records is not None and args.max_records < 1:
        parser.error("--max-records must be positive")
    print(json.dumps(ingest(args.input, args.output, args.max_records), indent=2), flush=True)


if __name__ == "__main__":
    main()
