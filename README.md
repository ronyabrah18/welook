# WeLook — cybersecurity account research

WeLook turns the supplied internet-service observations into an evidence-backed prospect queue for a team selling external attack-surface monitoring. Reps can filter candidate domains, switch to direct domain matches, inspect why an account appears, move uncertain cases to research, save a session shortlist, and export a CSV brief. The direct-match switch uses host and certificate rules; it does not verify business identity. Technical observations are leads for investigation, not confirmed vulnerabilities or buying intent.

**Hosted app:** [welook.streamlit.app](https://welook.streamlit.app/). The app is deployed from `main` and also runs locally from the committed serving snapshot.

## How it works

![WeLook architecture overview](docs/diagrams/welook-architecture-preview.png)

[Download the editable Excalidraw diagram](docs/diagrams/welook-architecture.excalidraw) and open it in Excalidraw to move or annotate each component.

The full data path is running end to end. The serving snapshot includes 35 offline AI research notes: 33 guarded batch notes for ambiguous accounts and two individually reviewed examples. The rule-based queue remains authoritative. See the [system architecture](docs/architecture.md) for the data contracts, incremental-load behavior, and cost controls.

## What has been built

- Streamed the **entire 12.44 GB compressed source** into 656 bronze Parquet parts, then read those parts to build typed silver Parquet: 11,768,718 source, bronze, and accepted silver rows; zero rejected rows. The full v2 run took 3.4 minutes for bronze and 6.0 minutes for silver on a 48 GB laptop. Malformed records remain in bronze and are routed to a separate quarantine during silver validation.
- Built 9,334,905 distinct domain-observation evidence links and 425,121 candidate domains with DuckDB/dbt. All 15 dbt model/test steps passed on the full run.
- Exported an approximately 22 MB read-only serving snapshot with the top 50,000 candidates and 96,107 selected evidence rows. The app states that the hosted view is a ranked subset of the full processed universe.
- Deployed the Streamlit account queue, research queue, evidence detail, session shortlist, and CSV export; verified the hosted app starts against the full serving snapshot.
- Added a reusable account-research skill, three prompt versions, and budgeted/traced offline API code. Of 100 v2 batch outputs, 33 cautious notes passed the publication gate and 67 overconfident `supported` outputs were withheld. A labelled evaluation set and prompt-quality results are **not included**, so the AI assessment is not presented as validated.

The source file, full bronze/silver data, analytical build database, API secrets, and raw traces are not in Git. The compact serving snapshot is included for a reproducible app demo.

## Run locally

Requires Python 3.12, [uv](https://docs.astral.sh/uv/), and the `zstd` command for the full compressed input. Place the supplied file at `b2_download_file_by_id` in this repo, or pass its path with `--input`.

```bash
uv sync --locked --cache-dir .uv-cache
uv run python scripts/run_pipeline.py
uv run streamlit run app/app.py
```

The pipeline registers immutable source-file checksums. A repeated completed file skips both bronze and silver; a completed bronze run can build or retry silver without the landing file. Run `uv run python scripts/run_pipeline.py --input /path/to/new-arrival.jsonl.zst` for each new immutable arrival. Its silver parts join the registered source, then dbt rebuilds the account marts from cumulative silver and the serving snapshot is atomically replaced. When a source is rebuilt with a newer schema, DuckDB registers only the latest complete version. An end-to-end two-file fixture checks account updates, duplicate-domain normalization, idempotence, and invalidation of stale AI notes. A replacement snapshot or deletion requires a separate source contract.

## Checks and AI workflow

```bash
uv run python -m unittest discover -s tests -v
```

The optional AI workflow selects ambiguous accounts offline. `uv run python scripts/enrich_accounts.py --limit 100` previews selected evidence bundles without an API call. After setting `OPENAI_API_KEY` in the ignored `.env`, `--live` makes budgeted calls and writes local traces. `uv run python scripts/publish_assessments.py` extracts only cautious batch outputs and combines them with the individually reviewed examples; `scripts/export_serving.py` checks the citations and supported-attribution rule before building the app snapshot. Raw local outputs never publish automatically. The notes are not a labelled quality evaluation. API billing is separate from a ChatGPT/Codex subscription.

## Submission documents

- [Planning and sales use cases](docs/planning.md)
- [System architecture](docs/architecture.md)
- [Skill](skills/account-research/SKILL.md) and [prompts](prompts/account-research/)
- [How I built it reflection](docs/how-i-built.md)

The candidate domain is an evidence grouping key, not a resolved legal entity. Shared platforms, CDN infrastructure, scanner labels, and missing firmographics remain visible limitations.
