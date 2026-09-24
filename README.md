# WeLook — Cybersecurity Sales Intelligence

Find the right accounts. Understand the evidence. Prioritise your next move.

WeLook is a Firmable take-home prototype for turning internet-service observations
into evidence-backed account research for a cybersecurity sales team. It analyses
the supplied snapshot; it does not continuously scan businesses or send outreach.

## Current status

- Profiled all 11,768,718 records in the supplied compressed dataset.
- Created a seeded, uniform 5,000-record sample for development.
- Loaded the sample into typed Parquet and DuckDB tables.
- Built the first dbt staging model and passed six data checks.

Account attribution, prioritisation, AI validation, evaluation harness, and hosted
app are planned and are not yet implemented.

## Local setup

Requires Python 3.12 and uv. Source data and generated artifacts are not included
in this repository. Existing local sample artifacts are required for the loader.

```bash
uv sync --cache-dir .uv-cache
uv run --cache-dir .uv-cache python scripts/load_sample.py
cd transform
../.venv/bin/dbt build --profiles-dir .
```

See [the first pipeline step](docs/first-pipeline-step.md) for details, and
[the sampling script](scripts/profile_full_dataset.py) to generate the sample
from the supplied Zstandard file (requires the `zstd` command).

## Design and learning notes

- [System architecture and build order](docs/architecture.md)
- [Detailed architecture decisions](docs/architecture-notes.md)
- [Planning and research](docs/planning.md)
- [First pipeline step and data model](docs/first-pipeline-step.md)
