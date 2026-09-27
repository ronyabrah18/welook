# WeLook architecture

WeLook separates a local batch pipeline from a lightweight hosted app. The [architecture diagram](../README.md#architecture) shows the implemented flow. Python streams the source into Parquet, DuckDB/dbt builds candidate-domain marts, and Streamlit reads a compact exported database. There is no live scanner, scheduler, warehouse server, or API call on an app page view.

## Components and storage

| Component | Responsibility | Location |
| --- | --- | --- |
| Landing | Immutable supplied JSONL.zst file | Local input path; default `b2_download_file_by_id` |
| Bronze | One row per source line: original text, or undecodable bytes, with file/record hashes and lineage | `artifacts/runs/<run-id>/bronze/*.parquet` |
| Silver | Typed observations with core validation, selected nested fields, and original vulnerability metadata | `artifacts/runs/<run-id>/silver/*.parquet` |
| Quarantine | Rejected-record IDs and reasons; original content remains in bronze | `artifacts/runs/<run-id>/quarantine.jsonl` |
| Warehouse | Registered silver views, dbt models, ingestion registry and gold AI table | `artifacts/warehouse/full.duckdb` |
| Offline AI | Selected bundles, raw results, JSONL traces, SQLite cache and spend ledger | Ignored `artifacts/ai/` |
| Publication inputs | Curated notes, batch notes that passed checks, and legacy citation mapping | `app/data/*assessments.jsonl`, `legacy_ai_source.json` |
| Serving | `accounts`, `evidence`, `assessments`, `build_info` | `app/data/welook_serving.duckdb` |
| App | Read-only queries, browser-session shortlist and CSV handoff | `app/app.py`, Streamlit Community Cloud |

`uv.lock` fixes the development dependencies. Hosting uses the smaller `app/requirements.txt`. Python generators and bounded PyArrow batches keep ingestion memory independent of the full decompressed file. DuckDB handles SQL aggregation; dbt supplies model dependencies and data tests. The sequential runner is sufficient for the supplied snapshot.

## Pipeline order and quality gates

[`scripts/run_pipeline.py`](../scripts/run_pipeline.py) executes these steps:

1. **Landing → bronze.** Hash the immutable input, stream-decompress it, and preserve each line with a globally unique source-record ID. Publish the bronze manifest after writing the parts.
2. **Bronze → silver.** Read completed bronze parts, verify content hashes, parse JSON, and validate IP, port, transport, and timestamp. Record optional-field type issues; route parsing/core failures to quarantine.
3. **Register silver.** Create `raw.observations` over completed arrivals and reconcile counts against `raw.ingestion_manifest` in a transaction.
4. **Build and test dbt models.** `stg_observations` deduplicates content hashes; `int_account_evidence` normalises domains and evaluates source links; `fct_accounts` aggregates one candidate per domain and assigns priority.
5. **Register gold AI assessments.** Validate existing publication inputs against current evidence and the source-set hash. This step does not call an LLM.
6. **Export serving.** Write a pending database, copy the selected accounts and evidence, then atomically replace the app snapshot.

The reconciliations are `source lines = bronze rows` and `bronze rows = silver rows + rejected rows`. Any parse/core rejection marks the run `needs_review` and stops the runner before downstream publication. dbt failures also stop release. Optional-field issues are recorded but do not automatically reject an otherwise valid row. The full supplied run accepted all 11,768,718 rows; fixtures exercise malformed data and quarantine.

Bronze preserves line content without the line-ending bytes. Silver is a typed projection, not a second full copy of every JSON field: optional text is bounded and some fields are omitted. Source timestamps are preserved without an assumed timezone; timezone-aware inputs require an explicit policy. Records over 64 MiB stop ingestion rather than being truncated.

## Incremental loading and recovery

The contract is **new immutable files**, not CDC or replacement snapshots. Each file's checksum and schema version identify its run. A repeated completed file skips bronze and silver. A new file adds parts; registration uses all completed arrivals, choosing only the latest complete schema version for each source.

The derived dbt marts are **fully rebuilt** from cumulative silver. This is incremental source loading with a full mart refresh. Corrections and deletions need a future snapshot/retraction contract.

A completed bronze stage can build silver without the landing file:

```bash
uv run python scripts/ingest_full.py --stage silver --run artifacts/runs/<run-id>
```

An incomplete stage leaves pending files for inspection; automatic mid-file resume is not implemented. A failed landing-to-bronze run may need to decompress the file again. Inspect incomplete outputs before retrying. Failures leave the last published serving database available to the app.

The [two-file integration fixture](../tests/test_ingest.py) checks repeat-file idempotence, account updates, case-normalised domain deduplication, globally unique citations, and stale-AI removal through gold and serving.

## Prioritisation

A candidate domain comes from an observation's `domains` array. It is an evidence grouping key, not a resolved legal entity. The link model compares the domain with the HTTP host and certificate common name on each observation. A small explicit provider-domain list takes precedence over those matches.

| Match status | App label | Meaning |
| --- | --- | --- |
| `supported` | Both fields match | HTTP host and certificate name match on an observation, outside the known provider list. |
| `partial` | One field matches | Only one of those fields matches. |
| `unresolved` | No direct match | Neither matches. |
| `provider_only` | Known provider domain | The domain is on the provider list; that list is incomplete. |

The account retains its strongest match status. A double match can still identify a provider-operated service; it does not verify business ownership.

Priority is evaluated in order:

| Tier | Required evidence |
| --- | --- |
| `investigate_first` | At least one non-provider double-match observation carrying a scanner-verified vulnerability label. |
| `review_next` | No direct verified label, but a double-match observation carrying vulnerability metadata. |
| `research` | At least a partial account match, plus a vulnerability association or admin/login title. These can be on different observations; the tier therefore requires more research. |
| `low_evidence` | All other candidates. |

The **research score** adds points per observation: HTTP-host match +20; certificate match +20; scanner-verified label +30, otherwise vulnerability metadata +5; admin/login title +10; non-null product +5. The SQL caps at 100, although the current terms total at most 85. An account uses its **maximum observation score**, not a sum across services. Queue order is tier, score, then domain. The export breaks score ties by supported-observation count before domain when selecting the hosted subset.

The exact rules live in [int_account_evidence.sql](../transform/models/int_account_evidence.sql) and [fct_accounts.sql](../transform/models/fct_accounts.sql). Weights are uncalibrated heuristics. A scanner's `verified` flag is retained as metadata; it does not prove current applicability. A login page alone is not a vulnerability.

## Offline AI workflow

Rules determine the queue. GPT-4.1 mini interprets a compact bundle of up to three observations for a selected domain and returns `decision`, `evidence_ids`, `reason`, and `next_action`. The default batch targets `review_next`; `ambiguous` and `investigate_first` are also supported. [The versioned skill](../skills/account-research/SKILL.md) defines the workflow; [prompt files](../prompts/account-research/) retain v1–v5.

No dedicated IP or port fields are sent to the model. The adapter redacts IP literals in evidence text and treats page titles/banners as untrusted data. Structured output and local validation check the result schema and cited IDs. The cache includes evidence, source-set hash, model, prompt version/content hash, and schema version.

Publication is separate from generation:

- `publish_assessments.py` selects cautious batch results and combines them with individually curated demo notes. Unreviewed `supported` batch decisions are withheld. V5 also uses a lexical wording gate; it is a guardrail, not proof of good prose.
- `register_ai_gold.py` checks status, citations visible in serving evidence, supported attribution, and source freshness. It stores one latest note per domain in `analytics.account_ai_assessments`.
- `export_serving.py` copies current notes for hosted domains. Raw traces and rejected responses stay outside gold and outside the app.

A new source file changes the source-set hash and invalidates older notes, including those for unchanged accounts. This conservative choice keeps stale suggestions out of serving. Account-level evidence hashes are a future optimisation.

The snapshot contains 46 notes: 37 passed batch publication checks and nine were individually curated for the demo, including the seven top-tier candidates. `reviewed_for_demo` does not mean independently verified ownership or security findings. The [25-case eval](../evals/README.md) records the prompt comparison and its limitations; draft labels still need independent human review.

After building the warehouse, the offline commands are:

```bash
# Free: select bundles for inspection
uv run python scripts/enrich_accounts.py --limit 5 --prompt v5
# Paid: requires OPENAI_API_KEY in the ignored .env file
uv run python scripts/enrich_accounts.py --limit 5 --prompt v5 --live
# Review results, then apply publication checks and refresh serving
uv run python scripts/publish_assessments.py
uv run python scripts/register_ai_gold.py
uv run python scripts/export_serving.py
```

## Tracing and cost

Every API attempt writes `artifacts/ai/traces.jsonl` with call ID/time, request, response, model, prompt/schema version, latency, input/output tokens, reservation, calculated cost, decision, validation outcome, and error. Cache hits make no API call. `ledger.sqlite3` holds both the cache and a persisted **US$10 cumulative ceiling**, including conservative reservations for failed calls with unknown usage. The hosted app needs no API key.

The configured mini rate card is $0.40 per million input tokens and $1.60 per million output tokens. For an illustrative 1,000-account batch at 2,000 input and 300 output tokens per account:

`1,000 × (2,000 × $0.40 + 300 × $1.60) / 1,000,000 = $1.28`

At one such batch per month, that is $1.28/month before retries. The measured 100-account v5 batch used smaller bundles and cost $0.054862. Across the recorded experiments and eval, 313 completed calls totalled $0.132145; 102 failed attempts retained $0.141941 of reservations, which are not confirmed charges. The rate card is in [llm_client.py](../welook/llm_client.py); review provider pricing before future runs.

The client also supports a priced GPT-4.1 snapshot, but the published workflow uses mini. Stronger-model escalation would require evidence that it improves useful output. A production pilot could use a separate $25 monthly cap with a $15 alert; that policy is proposed, not implemented.

## Serving boundaries and next steps

The export retains up to three evidence rows per domain, including the qualifying direct label for `review_next`. The app's product filter searches those selected rows only. AI notes are advisory and do not change priority. Shortlist/research updates live in Streamlit session state and must be exported to persist. CSV text is escaped to reduce spreadsheet-formula risk.

The source does not establish buying intent, legal identity, contacts, company territory, or change over time. Priorities should be validated with sales users. Future work includes sourced business/operator enrichment, independent eval adjudication, full-evidence product summaries, persistent team workflows, and targeted mart/AI refreshes. For a recurring deployment, Airflow could schedule the existing stages over S3 and a warehouse; those services are outside this implementation.
