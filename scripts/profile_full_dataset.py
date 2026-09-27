"""One-pass profiling and seeded reservoir sampling of compressed JSONL.

Each valid record has equal probability of entering the final sample. This is
a sample of observations, not unique businesses. No full decompressed copy is
written. Run from the repository root: uv run python scripts/profile_full_dataset.py
"""
import argparse
from collections import Counter
from datetime import datetime, timezone
import json
from pathlib import Path
import random
import subprocess
import time


def main():
    root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', type=Path, default=root / 'b2_download_file_by_id')
    parser.add_argument('--output', type=Path, default=root / 'artifacts' / 'full_scan')
    parser.add_argument('--size', type=int, default=5000)
    parser.add_argument('--seed', type=int, default=20260924)
    args = parser.parse_args()
    if args.size < 1:
        parser.error('--size must be positive')
    args.output.mkdir(parents=True, exist_ok=True)
    rng = random.Random(args.seed)
    reservoir = []
    reservoir_bytes = 0
    fields = ['org', 'domains', 'hostnames', 'product', 'version', 'vulns',
              'http', 'ssl', 'cloud', 'tags', 'timestamp']
    coverage = Counter()
    countries = Counter()
    totals = Counter()
    minimum = maximum = None
    first_schema = set()
    examples = {name: [] for name in ['vulnerability_metadata', 'domain_http_cert_match',
                                     'no_domains', 'generic_cert_organisation']}
    start = last_report = time.monotonic()
    stderr_path = args.output / 'decompression.log'
    with stderr_path.open('w') as err:
        proc = subprocess.Popen(['zstd', '-dc', str(args.input)], stdout=subprocess.PIPE,
                                stderr=err)
        try:
            while True:
                raw = proc.stdout.readline(64 * 1024 * 1024 + 1)
                if not raw:
                    break
                if len(raw) > 64 * 1024 * 1024:
                    raise ValueError('Record exceeds 64 MiB; stopped rather than truncate')
                totals['lines'] += 1
                totals['decompressed_bytes'] += len(raw)
                try:
                    row = json.loads(raw)
                    if not isinstance(row, dict):
                        raise ValueError('Non-object record')
                except (ValueError, UnicodeDecodeError):
                    totals['invalid_records'] += 1
                    continue
                totals['valid_records'] += 1
                n = totals['valid_records']
                j = n - 1 if n <= args.size else rng.randrange(n)
                if j < args.size:
                    if n <= args.size:
                        reservoir.append((totals['lines'], raw))
                    else:
                        reservoir_bytes -= len(reservoir[j][1])
                        reservoir[j] = (totals['lines'], raw)
                    reservoir_bytes += len(raw)
                    if reservoir_bytes > 512 * 1024 * 1024:
                        raise ValueError('Sample exceeds 512 MiB memory guard')
                first_schema.update(row)
                for key in fields:
                    if row.get(key):
                        coverage[key] += 1
                location = row.get('location') or {}
                countries[str(location.get('country_code') or 'unknown')] += 1
                ts = row.get('timestamp')
                if isinstance(ts, str):
                    minimum = min(minimum, ts) if minimum else ts
                    maximum = max(maximum, ts) if maximum else ts
                tags = row.get('tags') or []
                if 'cloud' in tags or 'cdn' in tags:
                    totals['cloud_or_cdn_tag'] += 1
                domains = row.get('domains') or []
                http = row.get('http') or {}
                cert = ((row.get('ssl') or {}).get('cert') or {})
                subject = cert.get('subject') or {}
                host = str(http.get('host') or '').lower().rstrip('.')
                cn = str(subject.get('CN') or '').lower().rstrip('.').removeprefix('*.')
                match = any((host == d or host.endswith('.' + d)) and
                            (cn == d or cn.endswith('.' + d))
                            for d in (str(x).lower().rstrip('.') for x in domains))
                if match:
                    totals['domain_http_cert_match'] += 1
                categories = {
                    'vulnerability_metadata': bool(row.get('vulns')),
                    'domain_http_cert_match': match,
                    'no_domains': not domains,
                    'generic_cert_organisation': str(subject.get('O') or '').lower()
                        in {'company', 'organization', 'internet widgits pty ltd'},
                }
                for category, applies in categories.items():
                    if applies and len(examples[category]) < 5:
                        examples[category].append({'source_line': totals['lines'],
                            'org': row.get('org'), 'domains': domains, 'port': row.get('port'),
                            'product': row.get('product'), 'http_host': host,
                            'http_title': str(http.get('title') or '')[:200],
                            'cert_subject': subject, 'timestamp': ts})
                now = time.monotonic()
                if now - last_report >= 20:
                    status = {'records': n, 'decompressed_gb': round(totals['decompressed_bytes']/1e9, 2),
                              'elapsed_seconds': round(now-start), 'sample_mb': round(reservoir_bytes/1e6, 2)}
                    (args.output / 'progress.json').write_text(json.dumps(status, indent=2)+'\n')
                    print(json.dumps(status), flush=True)
                    last_report = now
            if proc.wait() != 0:
                raise RuntimeError('Decompression failed; see decompression.log')
        finally:
            proc.stdout.close()
            if proc.poll() is None:
                proc.terminate()
            proc.wait()
    ordered = sorted(reservoir)
    sample_path = args.output / 'sample_5000.jsonl'
    with sample_path.open('wb') as out:
        for _, raw in ordered:
            out.write(raw.rstrip(b'\r\n') + b'\n')
    (args.output / 'sample_source_lines.json').write_text(json.dumps([i for i,_ in ordered]))
    report = {'completed_utc': datetime.now(timezone.utc).isoformat(),
        'source': str(args.input.resolve()), 'compressed_bytes': args.input.stat().st_size,
        'method': 'Algorithm R uniform reservoir over valid records, sorted back into source order',
        'limitations': 'Observation sample, not unique accounts. Attribution matches are heuristics, not verified ownership. Targeted examples are first matches and are not representative.',
        'seed': args.seed, 'sample_records': len(ordered), 'sample_bytes': sample_path.stat().st_size,
        'elapsed_seconds': round(time.monotonic()-start, 1), 'totals': dict(totals),
        'nonempty_field_counts': dict(coverage), 'timestamp_range_lexical': [minimum, maximum],
        'countries': countries.most_common(), 'top_level_fields': sorted(first_schema),
        'targeted_examples': examples}
    (args.output / 'profile.json').write_text(json.dumps(report, indent=2, ensure_ascii=False)+'\n')
    print(json.dumps({k:report[k] for k in ['sample_records','elapsed_seconds','totals','nonempty_field_counts']},indent=2),flush=True)


if __name__ == '__main__':
    main()
