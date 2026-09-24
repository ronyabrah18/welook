"""Stream a bounded JSONL sample from the supplied Zstandard file.

Run from any directory: python3 /path/to/Task/scripts/sample_data.py
Requires the zstd command; uses only Python's standard library.
"""
import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess


def main():
    root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', type=Path, default=root / 'b2_download_file_by_id')
    parser.add_argument('--rows', type=int, default=2000)
    parser.add_argument('--output', type=Path, default=root / 'artifacts')
    args = parser.parse_args()
    if args.rows < 1:
        parser.error('--rows must be positive')
    args.output.mkdir(parents=True, exist_ok=True)
    sample = args.output / 'sample.jsonl'
    fields = defaultdict(lambda: {'present': 0, 'null': 0, 'empty': 0, 'types': Counter()})
    counts = {k: Counter() for k in ['country', 'org', 'port', 'module']}
    ips, timestamps, examples = set(), [], []
    records = total_bytes = 0
    proc = subprocess.Popen(['zstd', '-dc', str(args.input)], stdout=subprocess.PIPE,
                            stderr=subprocess.DEVNULL)
    try:
        with sample.open('wb') as out:
            while records < args.rows:
                line = proc.stdout.readline(16 * 1024 * 1024 + 1)
                if not line:
                    break
                if len(line) > 16 * 1024 * 1024:
                    raise ValueError('Record exceeds 16 MiB safety limit')
                total_bytes += len(line)
                if total_bytes > 128 * 1024 * 1024:
                    raise ValueError('Sample exceeds 128 MiB safety limit')
                row = json.loads(line)
                if not isinstance(row, dict):
                    raise ValueError('Expected a JSON object per line')
                out.write(line)
                records += 1
                for key, value in row.items():
                    item = fields[key]
                    item['present'] += 1
                    item['null'] += value is None
                    item['empty'] += value == '' or value == [] or value == {}
                    item['types'][type(value).__name__] += 1
                location = row.get('location') or {}
                shodan = row.get('_shodan') or {}
                for key, value in [('country', location.get('country_code')),
                                   ('org', row.get('org')), ('port', row.get('port')),
                                   ('module', shodan.get('module'))]:
                    if value is not None:
                        counts[key][str(value)] += 1
                if row.get('ip_str'):
                    ips.add(row['ip_str'])
                if row.get('timestamp'):
                    timestamps.append(row['timestamp'])
                if len(examples) < 5:
                    examples.append({
                        'org': row.get('org'), 'country': location.get('country_code'),
                        'port': row.get('port'), 'module': shodan.get('module'),
                        'timestamp': row.get('timestamp'),
                        'domain_count': len(row.get('domains') or []),
                        'banner_characters': len(row.get('data') or ''),
                        'fields': sorted(row),
                    })
        # Detect an early decompression failure; deliberately stop after the target sample.
        if records < args.rows and proc.wait() != 0:
            raise RuntimeError('zstd failed before the requested sample was read')
    finally:
        proc.stdout.close()
        if proc.poll() is None:
            proc.terminate()
        proc.wait()
    for item in fields.values():
        item['missing'] = records - item['present']
    profile = {
        'created_utc': datetime.now(timezone.utc).isoformat(),
        'source': str(args.input.resolve()),
        'source_compressed_bytes': args.input.stat().st_size,
        'sampling': 'First N records; not a random or representative sample.',
        'records': records, 'sample_bytes': total_bytes, 'unique_ips': len(ips),
        'timestamp_range': [min(timestamps), max(timestamps)] if timestamps else None,
        'fields': dict(sorted(fields.items())),
        'top_values': {key: value.most_common(10) for key, value in counts.items()},
        'selected_examples': examples,
    }
    profile_path = args.output / 'profile.json'
    profile_path.write_text(json.dumps(profile, indent=2) + '\n')
    print(json.dumps({k: profile[k] for k in [
        'records', 'sample_bytes', 'unique_ips', 'timestamp_range', 'top_values'
    ]}, indent=2))
    print('Fields:', ', '.join(profile['fields']))
    print('Local sample:', sample)
    print('Compact profile:', profile_path)


if __name__ == '__main__':
    main()
