"""Load the saved representative sample; run with uv run python scripts/load_sample.py.

Builds a typed Parquet file and transactionally replaces the raw DuckDB table.
No API calls. This initial loader targets the sample, not the full source file.
"""
import hashlib
import ipaddress
import json
from datetime import datetime
from pathlib import Path

import duckdb
import pyarrow as pa
import pyarrow.parquet as pq

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = pa.schema([
    ('observation_id', pa.string()), ('source_line', pa.int64()),
    ('sample_line', pa.int64()), ('ip_address', pa.string()), ('port', pa.int32()),
    ('transport', pa.string()), ('observed_at', pa.timestamp('us')),
    ('infrastructure_org', pa.string()), ('infrastructure_country', pa.string()),
    ('domains', pa.list_(pa.string())), ('hostnames', pa.list_(pa.string())),
    ('tags', pa.list_(pa.string())), ('product', pa.string()), ('version', pa.string()),
    ('http_host', pa.string()), ('http_title', pa.string()),
    ('certificate_cn', pa.string()), ('certificate_org', pa.string()),
    ('vulnerabilities_json', pa.string()),
])


def normalise(row, source_line, sample_line, raw):
    ip = str(ipaddress.ip_address(row.get('ip_str') or row.get('ipv6')))
    port = row['port']
    if isinstance(port, bool) or not isinstance(port, int) or not 0 <= port <= 65535:
        raise ValueError('Invalid port')
    transport = row['transport']
    if transport not in ('tcp', 'udp'):
        raise ValueError('Unknown transport')
    timestamp = datetime.fromisoformat(row['timestamp'])
    if timestamp.tzinfo is not None:
        raise ValueError('Timezone-aware timestamp requires an explicit normalisation policy')
    http = row.get('http') or {}
    subject = (((row.get('ssl') or {}).get('cert') or {}).get('subject') or {})
    return dict(
        observation_id=hashlib.sha256(raw.rstrip(b'\r\n')).hexdigest(),
        source_line=source_line, sample_line=sample_line, ip_address=ip, port=port,
        transport=transport, observed_at=timestamp,
        infrastructure_org=row.get('org'),
        infrastructure_country=(row.get('location') or {}).get('country_code'),
        domains=row.get('domains') or [], hostnames=row.get('hostnames') or [],
        tags=row.get('tags') or [], product=row.get('product'), version=row.get('version'),
        http_host=http.get('host'), http_title=http.get('title'),
        certificate_cn=subject.get('CN'), certificate_org=subject.get('O'),
        vulnerabilities_json=json.dumps(row.get('vulns'), sort_keys=True),
    )


def main():
    source = ROOT / 'artifacts/full_scan/sample_5000.jsonl'
    lines = json.loads(source.with_name('sample_source_lines.json').read_text())
    rows, rejected = [], []
    count = 0
    with source.open('rb') as stream:
        for count, raw in enumerate(stream, 1):
            try:
                rows.append(normalise(json.loads(raw), lines[count-1], count, raw))
            except (ValueError, KeyError, TypeError) as exc:
                rejected.append({'sample_line': count, 'error': str(exc)})
    if count != len(lines):
        raise ValueError('Source-line manifest does not match sample length')
    out = ROOT / 'artifacts/warehouse'
    out.mkdir(parents=True, exist_ok=True)
    (out / 'rejected_records.json').write_text(json.dumps(rejected, indent=2)+'\n')
    if rejected:
        raise ValueError(f'{len(rejected)} rejected records; inspect report before publishing')
    table = pa.Table.from_pylist(rows, schema=SCHEMA)
    temporary = out / 'observations.pending.parquet'
    pq.write_table(table, temporary, compression='zstd')
    with duckdb.connect(str(out / 'sales.duckdb')) as con:
        con.execute('BEGIN')
        con.execute('CREATE SCHEMA IF NOT EXISTS raw')
        con.execute('CREATE OR REPLACE TABLE raw.observations AS SELECT * FROM read_parquet(?)',
                    [str(temporary)])
        loaded = con.execute('SELECT count(*) FROM raw.observations').fetchone()[0]
        if loaded != count:
            raise ValueError('Row reconciliation failed')
        con.execute('COMMIT')
    temporary.replace(out / 'observations.parquet')
    report = {'source': str(source), 'input_rows': count, 'loaded_rows': loaded,
              'rejected_rows': len(rejected), 'columns': len(SCHEMA),
              'source_sample_sha256': hashlib.sha256(source.read_bytes()).hexdigest(),
              'timestamp_policy': 'Preserve source time; source does not specify a timezone'}
    (out / 'load_report.json').write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
