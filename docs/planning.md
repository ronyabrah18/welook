# Sales intelligence prototype: planning draft

Status: updated 26 September 2026 after full-data ingestion, account modelling, and offline AI evaluation. Target submission: 28 September 2026. This records product hypotheses and implementation choices, not validated sales outcomes. The [architecture](architecture.md) tracks current implementation status.

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

1. **Choose accounts to investigate.** Open on a focused queue of seven directly matched scanner-verified labels and 5,411 directly matched unverified scanner labels, then filter by candidate domain, tier, attribution, and technical signal. Unverified labels require checking; neither tier proves current exposure. Dates remain visible in account detail. The source covers only a short snapshot window, so a recency filter would create false precision. Company territory, sector, and size are unknown; infrastructure country is shown only as observation evidence, never as a company-location filter.
2. **Understand why an account appears.** Account detail shows observation references, timestamps, infrastructure provider versus candidate domain, technical signals, and contradictory fields. Do not transfer all observations on a shared IP to every domain associated with it.
3. **Take the next useful action.** Save candidate domains in a session shortlist, record a human research status, a sourced company name, and a note, then export a cited handoff. A company name and source URL are required before marking a candidate ready for sales review. This is a human research checkpoint, not automatic verification of service operation. Account detail gives a provisional IT/security buyer role and a verification step, but does not invent a named decision-maker or contact route. Confirm the legal business and service operator before outreach. Drafting and sending email are outside this prototype.

## Implemented screen

The single discovery page opens on the seven `investigate_first` and 5,411 `review_next` candidates and shows the strongest research signal and evidence match. A product-name filter searches the evidence rows retained for hosted accounts, enabling a narrow technology-targeting use case without claiming a complete product inventory. The selected row opens an account brief with a reason to investigate, next verification step, likely buyer role, up to three cited observations, and an AI note when one exists. The full universe, weaker research cases, and AI-note cases remain accessible through the view selector. A shortlisted candidate can receive a human status, sourced name, and research note. The CSV handoff includes evidence IDs, any AI note, the researched name and source URL; the dataset identity remains labelled unverified. Session decisions are lost when the browser session ends unless exported.

## Rule and LLM split

Rules handle parsing, domain normalisation, provider/platform screening, observation deduplication, date calculations, deterministic signal extraction, filtering, and bounded priority calculations. Preserve original fields and source references. Rank distinct signal categories with caps so duplicated observations do not dominate. Weights remain explicit hypotheses until reviewed; no conversion-probability claims.

The strongest tier requires both a direct domain match and a scanner-verified vulnerability association on the same observation. The new review-next tier requires the same direct match with vulnerability metadata whose scanner-verified flag is false. It is an invitation to verify the label, not a claim that the account is vulnerable. A login/admin page title by itself is a research cue, not an outreach trigger. Even a scanner-verified flag requires checking whether the named business operates the service and whether the finding applies.

Proposed core LLM feature: interpret a compact evidence bundle and return a structured account research brief: evidence assessment (`supported`, `needs_review`, or `insufficient_evidence`), referenced observation IDs, a short explanation, and the next research action. Supported means supported by supplied evidence, not independently verified ownership or security status. Rules constrain progression to outreach review; the LLM does not override unresolved ownership.

The offline LLM feature remains advisory. The app's "AI notes" filter shows 33 guardrail-checked batch notes and nine individually reviewed briefs, including all seven `investigate_first` candidates; each appears in its account brief. None changes priority or permits outreach. Outreach starters can use deterministic templates populated with reviewed facts; a separate generative drafting feature is outside this prototype.

## AI workflow scope

- A versioned `skills/account-research/SKILL.md` with triggers, input/output contract, prompt dependencies, and example invocation.
- Prompt files for v1 through v5, retained for traceability; v5 addresses directly matched, unverified scanner labels. Four v5 notes passed the publication wording gate from a 100-account run; the other 96 were withheld.
- Each LLM call logs request, response, model, prompt version, latency, token usage, calculated cost, decision, errors, and evidence references. Treat website text as untrusted data, never instructions.
- Cache results by evidence hash, prompt version, and model. Call the LLM for shortlisted accounts, not all 11.8 million observations.
- Cost model: calls = new/changed accounts per run × runs per month; cost = calls × (input tokens × input price + output tokens × output price) / 1,000,000. Include retry budgets and enforce a spend ceiling.
- A 25-case curated eval compares v4 and v5 on the same evidence bundles with the pinned model. The harness reports decision precision/recall, citation agreement, and the publication wording gate. See [the eval report](../evals/results.md); the cases are a deliberately challenging sample, not a sales-outcome measure.

## Scope and limitations

The snapshot does not establish new exposure, growth, historical change, purchase intent, headquarters, company size, named decision-makers, or budget. Server country is not sales territory. Certificates, banners, and dataset labels can be stale or misleading. Missing vulnerability metadata does not mean secure. A certificate/domain match does not attribute every service on a shared IP.

No active scanning, automated email sending, CRM integration, model training, or full-scale multi-tenant platform is needed for the prototype. Process the entire supplied dataset through landing, faithful bronze Parquet, validated silver, and derived gold. The 5,000-record sample is for development only. Retain unresolved observations with reasons. All eligible accounts receive rule-derived results; selected accounts could receive offline AI assessment after a quality review. Publish compact account tables and selected evidence, with any serving-detail limits and AI coverage stated explicitly.

## Delivery and next decisions

The submitted scope is a hosted app; source repo with a skill, prompts, a labelled eval and one-command comparison; this planning document; architecture and cost documentation; and a half-to-one-page development reflection. Optional walkthrough at most five minutes.

Before using AI decisions to advance accounts toward outreach, confirm the operator and evidence with a person. The take-home API ceiling is US$10 total; 313 completed local calls have a calculated US$0.132145 cost according to the ledger. Another 102 failed attempts carry US$0.141941 in conservative reservations, not confirmed charges. After IP-literal redaction, the final 25-case v4/v5 comparison reused 36 cached predictions and required 14 new completed calls (US$0.006953).

## Data-platform emphasis

The Senior Data Engineer — Data Platform role emphasises LLM extraction, enrichment, entity resolution, semantic validation, and regression gates within pipelines. The current submission demonstrates typed models, provenance, quality checks, and recoverable stages. The offline AI adapter remains a research aid; verified operator data and sales-user feedback would be needed before relying on its suggestions for outreach.
