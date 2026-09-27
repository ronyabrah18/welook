# WeLook product plan

## User and problem

The primary user is a sales development representative selling **external attack-surface monitoring**. The job is to find accounts worth researching, understand the technical reason, and prepare a useful handoff to an IT/security buyer.

The provisional ideal customer profile is an organisation with identifiable business websites and externally visible services relevant to that product. Company size, sector, budget, and territory are not established by this dataset. IT or security owner is a suggested role to research, not a discovered contact.

## Research that informed the scope

This was desk research from vendor documentation, not salesperson interviews.

| Source | Product decision |
| --- | --- |
| [Salesforce: ideal customer profiles](https://www.salesforce.com/sales/ideal-customer-profile/) | State the target offering and customer hypothesis; leave unsupported firmographics unknown. |
| [HubSpot: lead scoring](https://knowledge.hubspot.com/scoring/understand-the-lead-scoring-tool) | Separate technical fit/evidence from engagement or buying intent. Show an explainable research priority. |
| [HubSpot: sales prospecting](https://www.hubspot.com/products/sales/ai-sales-prospecting) | Support discovery, account research, prioritisation, and a shortlist handoff. Make missing contacts explicit. |
| [Microsoft: external attack-surface management](https://learn.microsoft.com/en-us/azure/external-attack-surface-management/overview) | Use observed services and infrastructure relationships as context for an external-monitoring sales use case. |

## What the source supports

The full source contains 11,768,718 service observations. Recorded timestamps span 21 September 2026, 09:50:10–11:05:56; the pipeline makes no timezone assumption. Nonempty field coverage from the full scan is 70.84% for domains, 34.35% for HTTP, 16.88% for product, 6.72% for SSL, and 2.51% for vulnerability metadata. Roughly 67% of observations have cloud/CDN tags.

This supports technical research, but not automatic company identification. A provider organisation or server location may describe infrastructure used by many customers. A domain and certificate match can strengthen the service association without proving legal ownership.

[`profile_full_dataset.py`](../scripts/profile_full_dataset.py) streamed the full file and took a seeded 5,000-record reservoir sample for exploration. The sample was for development; the final pipeline processed the full source. Generated profiles and raw samples remain under ignored `artifacts/`.

## Three chosen use cases

1. **Find candidates to investigate.** Open on directly matched scanner signals, then filter by domain, priority view, technical signal, evidence match, or product in selected evidence. Keep weaker matches accessible for research.
2. **Understand the reason.** Show the source observations, match fields, observation date, scanner-listed IDs, and next verification step. Distinguish scanner-verified labels from unverified labels; avoid presenting a login page as a vulnerability.
3. **Prepare a sales handoff.** Shortlist domains, record research status and a sourced company name, and export a cited CSV. Require a name and HTTPS source URL before marking Ready for sales review. That is a research checkpoint, not verified ownership or permission to contact.

The single-page app supports this sequence. A concise User Guide explains the actual filters and score. Session-only notes keep the prototype lightweight; the app asks the user to export them.

## Rules and AI

Rules handle parsing, validation, deduplication, domain matching, provider screening, signals, and priority. The strongest tiers require the signal and direct domain match on the same observation. The [architecture document](architecture.md#prioritisation) records exact rules and weights.

The bounded AI feature interprets selected evidence and suggests the next research step. It returns a cited structured note, is cached and traced, and must pass publication checks. It never changes the account's priority. The [eval](../evals/README.md) measures decision-policy adherence and wording failures; its draft labels still need independent review.

## Deliberate limits

The snapshot cannot establish current exposure, historical change, purchase intent, verified legal identity, or named decision-makers. Infrastructure country is not company territory, so there is no territory filter. Product search is limited to selected evidence, so it is not a complete technology inventory. No active scanning, automated outreach, CRM sync, or real-time LLM calls are included.

The next product work would be independently sourced business/operator enrichment and testing the research queue with sales users. Better company data would support a commercial ICP, territory filters, and more specific outreach preparation. Those are future improvements rather than claims about the current prototype.
