# WeLook architecture

WeLook has two parts:

1. A local batch pipeline processes the large source file, builds the research tables, and prepares AI notes.
2. A small hosted Streamlit app reads a compact DuckDB file.

The Streamlit app does not process the 12.44 GB source file and does not call OpenAI when someone opens a page. This keeps the demo fast and inexpensive. The [README diagram](../README.md#architecture) shows the complete flow and row counts.

## Main components

| Stage or table | What it contains | Full-run rows |
| --- | --- | ---: |
| Landing | Supplied compressed JSONL source | 11,768,718 lines |
| Bronze Parquet | Original record text, checksums, and source lineage | 11,768,718 |
| Silver Parquet | Parsed and typed service observations | 11,768,718 |
| Quarantine JSONL | IDs and reasons for rejected rows | 0 |
| `raw.observations` | DuckDB view over released Silver files | 11,768,718 |
| `analytics.stg_observations` | Deduplicated observations with verified-label count | 11,768,718 |
| `analytics.int_account_evidence` | One row for each candidate-domain/observation link | 9,334,905 |
| `analytics.fct_accounts` | One prioritised row per candidate domain | 425,121 |
| `analytics.account_ai_assessments` | AI notes that passed publication checks | 46 |
| Serving DuckDB | Hosted accounts, selected evidence, AI notes, and build metadata | 50,000 accounts |

Python and PyArrow stream the compressed file into Parquet without loading the decompressed file into memory. DuckDB runs the local SQL workload. dbt defines the model order and data tests. Streamlit reads only the serving database.

## Pipeline order

[`scripts/run_pipeline.py`](../scripts/run_pipeline.py) runs the deterministic stages in this order:

1. Calculate the source-file checksum.
2. Stream the source into Bronze Parquet and create stable source-record IDs.
3. Parse Bronze, validate the core fields, and write valid rows to Silver. Invalid rows go to quarantine.
4. Register all completed Silver files as `raw.observations`.
5. Run and test the three dbt models: staging, evidence, and accounts.
6. Register current published AI notes in the separate AI table. This step does not call an LLM.
7. Export a new serving database and replace the previous one only after every check passes.

The main ingestion check is:

```text
Bronze rows = Silver rows + quarantined rows
```

The supplied file had no parse or core-field rejects, so all 11,768,718 rows reached Silver. Test fixtures still exercise the quarantine path.

## One example: `3ds.com`

The source contains 627 observations linked with `3ds.com`.

```text
627 Bronze records
→ 627 Silver observations
→ 627 staged observations
→ 627 int_account_evidence rows
→ 1 fct_accounts row
→ strongest 3 evidence rows sent to the AI workflow
→ 1 reviewed AI note
→ 1 candidate shown in Streamlit
```

The account row contains 627 total observations. Of these, 218 have both the HTTP host and certificate matching the candidate domain, 99 carry scanner vulnerability metadata, and four directly matched observations carry a scanner-verified label. Its research score is 75 and its priority is `investigate_first`.

The AI does not receive all 627 rows. It receives the strongest three cited observations. The published note explains the historical domain-to-service link and asks the salesperson to check the scanner finding and current service operator before outreach. It does not claim that the company is currently vulnerable.

## Prioritisation

SQL rules assign every candidate to one tier:

| Tier | Rule |
| --- | --- |
| `investigate_first` | The same observation has both domain matches and a scanner-verified label. |
| `review_next` | A directly matched observation has unverified vulnerability metadata, with no directly matched verified label. |
| `research` | There is at least a partial domain match and either vulnerability metadata or an admin/login title, but the stronger rules do not apply. |
| `low_evidence` | The available evidence does not meet a higher tier. |

The evidence score adds 20 for an HTTP-host match, 20 for a certificate match, 30 for a scanner-verified label (otherwise 5 for vulnerability metadata), 10 for an admin/login title, and 5 for a product value. An account uses its strongest observation score. The formula can produce 0–85; the full run observed 0–75. This is a research score, not a risk percentage or likelihood to buy.

The exact rules are in [`int_account_evidence.sql`](../transform/models/int_account_evidence.sql) and [`fct_accounts.sql`](../transform/models/fct_accounts.sql).

## Rules and AI have different jobs

Rules handle work that must be repeatable:

- parsing and validation
- deduplication
- domain normalisation and provider screening
- host and certificate matching
- evidence scoring and priority
- selection of compact AI inputs

GPT-4.1 mini is used offline for one smaller task. It reads up to three observations and returns four structured fields: `decision`, `evidence_ids`, `reason`, and `next_action`. AI notes are advisory and never change the SQL priority.

Generation and publication are separate. [`publish_assessments.py`](../scripts/publish_assessments.py) withholds unsupported decisions or unsafe wording. [`register_ai_gold.py`](../scripts/register_ai_gold.py) checks the citations, attribution, review status, and source freshness before storing a note in Gold. Raw responses and rejected notes stay outside the app.

## AI controls and cost

The AI workflow includes:

- versioned prompts in `prompts/`
- a reusable workflow in `skills/account-research/SKILL.md`
- strict structured-output validation
- evidence-ID validation
- JSONL traces for API attempts
- a SQLite response cache and spend ledger
- a persisted US$10 total ceiling
- a source-set hash that prevents stale notes from reaching serving

Dedicated IP and port fields are not sent to the model. IP literals found inside text are redacted, and page titles are treated as untrusted data.

The configured GPT-4.1 mini rates are $0.40 per million input tokens and $1.60 per million output tokens. An example 1,000-account batch with 2,000 input and 300 output tokens per account is:

```text
1,000 × (2,000 × $0.40 + 300 × $1.60) / 1,000,000 = $1.28
```

The 100 completed calls in the measured v5 batch cost $0.054862. The hosted application needs no API key because all calls happen before publication. The 25-case eval compares prompt decisions and wording rules, but its labels are still draft labels awaiting independent review.

## New files and failures

The ingestion design supports new immutable files:

1. Identify each file by checksum and schema version.
2. Skip it if the same completed file is already registered.
3. Otherwise create new Bronze and Silver parts.
4. Register all completed arrivals together.
5. Rebuild the derived dbt tables from cumulative Silver data.
6. Invalidate AI notes when their source-set hash is stale.
7. Publish a new serving database only after all checks pass.

This is incremental source loading followed by a full analytics rebuild. It is simple and appropriate for the take-home, but it does not yet handle source deletions, corrections, or mid-file resume. If a stage fails, the pending build is not published and Streamlit keeps using the last successful serving database.

## Serving and limits

[`scripts/export_serving.py`](../scripts/export_serving.py) creates the small database used by Streamlit:

| Serving table | Purpose | Rows |
| --- | --- | ---: |
| `accounts` | Highest-ranked candidate domains | 50,000 |
| `evidence` | Up to three selected observations per hosted domain | 96,107 |
| `assessments` | Published AI research notes | 46 |
| `build_info` | Counts, source hash, and build time | 1 |

A candidate domain is not automatically a verified company. The source also cannot establish current exposure, buying intent, company territory, or a named contact. WeLook is therefore a research queue: the salesperson still has to confirm the company, current service operator, technical finding, and business context.
