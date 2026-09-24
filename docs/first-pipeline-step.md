# First pipeline step

This stage processes the saved 5,000-record sample. It does not yet load the full source or produce sales accounts.

## Run

From the `Task` directory:

```bash
uv sync --cache-dir .uv-cache
uv run --cache-dir .uv-cache python scripts/load_sample.py
cd transform
../.venv/bin/dbt build --profiles-dir .
```

The local environment is `.venv`. The lockfile records exact dependency versions. Data remains under ignored `artifacts/` paths.

## What each component does

- Python validates IPs, ports, transport, and timestamp shape. It extracts 19 typed fields, retains complete vulnerability metadata as JSON, and writes Parquet. Invalid input is reported and prevents publication.
- Parquet stores the selected data in a column-oriented format. It is an artifact, not a running database service.
- DuckDB stores `raw.observations` in `artifacts/warehouse/sales.duckdb`. A transaction replaces the table on a successful load. Sample-to-source line mappings preserve provenance; hashes identify identical source-record content.
- dbt runs `stg_observations.sql` to produce `analytics.stg_observations`. Its `source()` reference identifies the input. The model is a view, so it stores a SQL definition rather than another data copy.
- dbt tests fail when a query returns problematic rows: missing/duplicate IDs, missing timestamps or provenance, invalid transports, ports, IP presence, or malformed vulnerability JSON.

Exact-content deduplication is intentionally limited. Equivalent records with different JSON key order can have different hashes. Account/entity deduplication is a later, separate step. Source timestamps lack an explicit timezone, so this loader does not silently assign UTC.

## Planned data model

| Table | Grain | Purpose |
| --- | --- | --- |
| observations (implemented) | Source record | Typed facts and provenance |
| stg_observations (implemented) | Distinct source content | First clean SQL layer |
| account_candidates (planned) | Candidate account/domain | Identity evidence and review state |
| account_observations (planned) | Candidate–observation association | Attribution method, evidence, ambiguity |
| signals (planned) | Signal attached to an observation | Supported condition, date, verification status |
| ai_decisions (planned) | Evidence bundle and model/prompt version | Structured assessment, review outcome, trace reference |

The sample loader is a learning/reference implementation: it holds the small sample in memory. Full ingestion will use bounded batches and partitioned outputs. The source streaming sampler already processes the full compressed file without materialising it.

## Recovery limitation

Database replacement is transactional, and Parquet is written via a temporary file. There is no cross-file transaction: a failure between database commit and Parquet rename can leave artifacts from different runs. Rerunning this deterministic sample loader reconciles them; a full pipeline should publish a completed run manifest pointing to versioned artifacts.

## Learn by reading

Start with `transform/models/stg_observations.sql`: it is ordinary SQL plus a dbt input reference. Then read `transform/tests/valid_observations.sql`: the returned rows are the failures. This is the foundation before adding account-resolution logic.

DuckDB supports reading Parquet and querying Arrow tables through Python: [official Python documentation](https://duckdb.org/docs/current/clients/python/overview).
