# Sales intelligence prototype: planning draft

Status: updated 25 September 2026 after full-data scope and US$10 API budget were confirmed. Target submission: 27 September 2026. This records design decisions, not completed features or validated sales outcomes. The [architecture](architecture.md) is the current implementation design and supersedes earlier sample-only serving assumptions.

## User and product hypothesis

Primary user: an outbound sales development representative selling external attack-surface monitoring software. Their daily task is to choose accounts worth investigating, understand the evidence, and prepare a relevant approach to an IT/security buyer.

Working product promise: identify accounts worth a cybersecurity conversation, explain why, and show the next step. Technical exposure is a potential need signal; it does not establish purchasing intent or a confirmed vulnerability.

Working ICP: organisations with identifiable business websites and externally visible services relevant to an external monitoring product. Company size, sector, budget, and company territory remain unknown unless supported by separately sourced enrichment. This is a provisional technical-fit definition, not a validated commercial ICP. Suggested buyer roles are Head of IT or Security Lead; these are role hypotheses, not discovered contacts.

## Research and implications

This is vendor documentation and desk research, not user interviews. Salesperson validation remains a limitation.

| Source | Finding | Design implication |
| --- | --- | --- |
| [Salesforce: ideal customer profiles](https://www.salesforce.com/sales/ideal-customer-profile/) | ICPs describe the kinds of customers that fit a product, including common needs and purchasing triggers. | State our target buyer and product explicitly; label unsupported firmographics unknown. |
| [HubSpot: scoring documentation](https://knowledge.hubspot.com/scoring/understand-the-lead-scoring-tool) | Fit and engagement are distinct scoring dimensions; configurable rules and score limits support prioritisation. | Keep technical relevance, attribution confidence, and evidence strength visible. Do not label a heuristic score purchase probability. |
| [HubSpot: AI sales prospecting](https://www.hubspot.com/products/sales/ai-sales-prospecting) | Prospecting spans identifying accounts, enriching contacts, prioritising leads, and personalising outreach. | Provide a shortlist-to-account-to-next-action workflow. Mark unavailable contacts explicitly. |
| [Microsoft: external attack-surface management](https://learn.microsoft.com/en-us/azure/external-attack-surface-management/overview) | The product category uses infrastructure discovery, relationships, inventory, and vulnerability context to help prioritise external risk. | This category aligns with the supplied observations. Our prototype supports sales research; it does not reproduce a live security monitoring platform. |

## Dataset evidence

The supplied Zstandard file contains 11,768,718 valid JSON objects over 88,527,136,570 decompressed bytes. The full stream was read successfully without a decompressed copy being saved. Recorded timestamp strings span 2026-09-21 09:50:10 to 11:05:56; no timezone assumption is added.

Full-file nonempty coverage: domains 70.84%, HTTP 34.35%, product 16.88%, SSL 6.72%, vulnerability metadata 2.51%. Roughly 67% of observations carry cloud or CDN tags. These are observation counts, not unique companies.

A seeded Algorithm R reservoir sampled 5,000 valid records across the file. A provisional provider-domain screen leaves 749 observations with domains outside the list; 65 match a candidate domain to HTTP host and certificate name. The list is incomplete and includes false candidate matches to shared platforms. None of these counts establishes business ownership.

Local supporting artifacts: `artifacts/full_scan/profile.json`, `artifacts/full_scan/sample_attribution.json`, and `scripts/profile_full_dataset.py`. Raw data and generated samples are excluded from Git.

## Chosen use cases

1. **Choose accounts to investigate.** Filter candidates by signal category, attribution status, evidence date, and review status. Display infrastructure country separately. Company-territory filtering uses only sourced company geography, with an explicit unknown group. Sector/size filters are only available if enrichment supports them.
2. **Understand why an account appears.** An account detail page shows observation references, timestamps, provider versus candidate business, signals, conflicting evidence, and missing information. Do not transfer all observations on a shared IP to every domain associated with it.
3. **Take the next useful action.** Save an account to a shortlist; mark needs research, reviewed for outreach, or dismissed; export a concise prospect brief. Provide a proposed buyer role and reviewed contact route when known. Otherwise, show the required contact research. Drafting must preserve uncertainty; sending email is outside scope.

## Proposed screens

- Account queue: candidate domain/name, technical relevance, attribution status, strongest signal, observed date, and next action.
- Account detail: evidence, possible business relevance, what remains unknown, suggested buyer role, research links, and a template-based outreach starter.
- Research queue: unresolved account ownership, unsupported signals, missing contact route, and reason for review.

## Rule and LLM split

Rules handle parsing, domain normalisation, provider/platform screening, observation deduplication, date calculations, deterministic signal extraction, filtering, and bounded priority calculations. Preserve original fields and source references. Rank distinct signal categories with caps so duplicated observations do not dominate. Weights remain explicit hypotheses until reviewed; no conversion-probability claims.

Proposed core LLM feature: interpret a compact evidence bundle and return a structured account research brief: evidence assessment (`supported`, `needs_review`, or `insufficient_evidence`), referenced observation IDs, a short explanation, and the next research action. Supported means supported by supplied evidence, not independently verified ownership or security status. Rules constrain progression to outreach review; the LLM does not override unresolved ownership.

Prefer one well-evaluated LLM feature for the deadline. Outreach starters can use deterministic templates populated with reviewed facts; a separate generative drafting feature is optional.

## AI engineering acceptance criteria

- A versioned `skills/account-research/SKILL.md` with triggers, input/output contract, prompt dependencies, and example invocation.
- Prompt files for v1 and v2, with actual measured comparisons rather than invented improvements.
- 25 human-reviewed evidence bundles with expected class, acceptable evidence IDs, and rationale. Include hosting-provider confusion, shared platforms, generic certificate fields, missing fields, unverified vulnerability associations, and credible domain matches.
- Keep a fixed held-out portion; do not tune prompts on its labels. Report class precision/recall, macro F1, evidence-reference validity, and unsupported-claim failures. Small-set uncertainty must be documented.
- One command to run the same cases across prompt versions and save per-case predictions, errors, aggregate metrics, and the comparison.
- Each LLM call logs request, response, model, prompt version, latency, token usage, calculated cost, decision, errors, and evidence references. Treat website text as untrusted data, never instructions.
- Cache results by evidence hash, prompt version, and model. Call the LLM for shortlisted accounts, not all 11.8 million observations.
- Cost model: calls = new/changed accounts per run × runs per month; cost = calls × (input tokens × input price + output tokens × output price) / 1,000,000. Include retry and evaluation budgets. Record current model prices and an explicit enforceable spend ceiling after budget/model selection.

## Scope and limitations

The snapshot does not establish new exposure, growth, historical change, purchase intent, headquarters, company size, named decision-makers, or budget. Server country is not sales territory. Certificates, banners, and dataset labels can be stale or misleading. Missing vulnerability metadata does not mean secure. A certificate/domain match does not attribute every service on a shared IP.

No active scanning, automated email sending, CRM integration, model training, or full-scale multi-tenant platform is needed for the prototype. Process the entire supplied dataset through landing, faithful bronze Parquet, validated silver, and derived gold. The 5,000-record sample is for development only. Retain unresolved observations with reasons. All eligible accounts receive rule-derived results; a budgeted subset receives AI assessment. Publish compact account tables and selected evidence, with any serving-detail limits and AI coverage stated explicitly.

## Delivery and next decisions

Deliver a hosted app; source repo with skills, prompts, labelled evals and measured results; this planning document; architecture and cost documentation; a half-to-one-page development reflection. Optional walkthrough at most five minutes.

Next: implement full-data streaming ingestion and schema validation, then review 10 diverse candidate-account evidence bundles to refine attribution/signal rules. The take-home API budget is US$10 total. Build the smallest end-to-end path, deploy early, and add evaluation and documentation alongside implementation. No paid calls have been made.

## Data-platform emphasis

The Senior Data Engineer — Data Platform role emphasises LLM extraction, enrichment, entity resolution, semantic validation, and regression gates within pipelines. Implement the evidence assessment as a cached pipeline enrichment/validation step; the UI consumes its structured results. An account narrative can be derived from that output. Prioritise typed models, provenance, quality checks, recoverable stages, and measured AI behaviour over extra UI features.
