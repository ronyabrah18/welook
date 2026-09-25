# Preliminary account-research eval · 25 September 2026

These are real OpenAI API outputs from the 25 source-derived cases, using pinned `gpt-4.1-mini-2025-04-14`. The cases are **draft labels pending manual review**. Metrics must be recalculated after any label changes; they are not a production accuracy estimate.

| Metric | Prompt v1 | Prompt v2 |
| --- | ---: | ---: |
| Macro F1, all 25 | 0.558 | 0.610 |
| Macro F1, held-out 10 | 0.448 | 0.578 |
| `supported` precision | 0.444 | 0.500 |
| `needs_review` recall | 0.111 | 0.222 |
| Valid evidence references | 25/25 | 25/25 |
| Completed structured outputs | 25/25 | 25/25 |

Version 2 improves the measured classification, especially on the held-out split, but it still calls many ambiguous platform or single-certificate cases `supported`. Its `needs_review` recall is only 2/9. This is why WeLook does not promote an LLM decision into a confirmed asset or an outreach-ready account. Rules and a human verification step retain control over that decision.

Three draft-labelled disagreements explain the guardrail. R01 is a tenant page on `mybigcommerce.com`: v2 correctly sees a domain-to-service link but calls it `supported` without identifying the merchant sales prospect. I03 has no candidate HTTP host or certificate, yet v2 inferred support from an infrastructure organisation name. R08 has the candidate in a shared CDN DNS list and was called `insufficient_evidence`; that DNS clue is a reason to research, not strong attribution. R01 in particular shows that the final human labels must settle whether the target is domain association or a specific buyer account.

One evaluation case, R08, initially omitted the source DNS list that its draft rationale relied on. The input was corrected from source line 7,127,446, and both versions were rerun on the same 25 cases; unchanged inputs were served from the prompt/model/evidence cache. The committed JSON and prediction files are from that corrected run. The development and held-out split is recorded per case; the held-out set was not used to rewrite v2. Results are exploratory because the sample is small and the labels have not yet been approved by a person.

The local SQLite ledger recorded 52 completed API requests (50 initial unique prompt-case pairs plus two corrected R08 inputs) with calculated cost **US$0.013798**. The uncommitted JSONL traces contain the full request, response, model, prompt/schema version, latency, tokens, cost, validation, decision, and error fields. They stay local because raw evidence and model responses may contain service data. The report and per-case predictions here contain no API key.

Reproduce after setting the ignored `.env` and reviewing labels:

```bash
uv run python evals/run_eval.py --live
```

The harness compares v1 with v2 in one run, reports per-class precision/recall/F1 and macro F1 for all cases and each split, and marks results provisional while any label has not been reviewed. Cached input/prompt/model/schema combinations avoid repeat charges.
