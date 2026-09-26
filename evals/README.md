# Account-research evaluation

This evaluates the **offline AI research note**, not whether an organisation owns a service or needs to buy software. The labelled target is the note's `decision`: `supported` for a historical direct domain-service association with a scanner-verified label, `needs_review` for an unverified direct label or one-sided domain link, and `insufficient_evidence` when the supplied observations have no meaningful domain link. `supported` never means a confirmed current vulnerability.

`labelled_cases.jsonl` contains **25 manually curated draft labels**: 22 compact, IP-redacted evidence bundles from the supplied snapshot and three clearly marked synthetic negative controls. Codex proposed the decisions after inspecting the evidence; they have not been independently human-adjudicated. Each record includes the expected decision, a written rationale, and acceptable supporting evidence IDs. [label_review.md](label_review.md) makes them easy for the applicant to review. Cases were deliberately chosen to challenge attribution and scanner-label wording; this is not a prevalence-weighted sample of all 425,121 candidate domains. The bundled inputs make the eval rerunnable without the 12.44 GB source file or local warehouse.

Run the same 25 cases against the previous v4 prompt and the app's current v5 prompt, using the pinned production model and shared US$10 ledger:

```bash
UV_CACHE_DIR=.uv-cache uv run --no-sync python evals/run_eval.py --live
```

This command needs the ignored local `.env` API key and can make up to 50 paid calls; cached responses are reused. It writes exact model outputs to `predictions.jsonl` and the measured comparison to `results.json` and `results.md`. Every new API call uses the same structured-output schema, local trace, cache, and spend ceiling as the offline enrichment pipeline. If connectivity or a model call fails, the script leaves the prior complete comparison intact and writes partial outputs under ignored `artifacts/ai/` for inspection.

After a successful live run, anyone can re-score the committed predictions with **no key and no API cost**:

```bash
UV_CACHE_DIR=.uv-cache uv run --no-sync python evals/run_eval.py
```

The report gives three-class precision/recall/F1, exact decision accuracy, citation agreement with the reviewed evidence rows, and a lexical wording-gate rate for unverified direct labels. A missed/failed case counts against recall and overall accuracy. The wording gate catches specific overstatements but cannot establish that prose is safe or useful. The cases have no externally verified service-owner or vulnerability ground truth, so these metrics cannot measure real-world sales conversion or technical finding accuracy. Review false positives and generated prose before publishing any new note.

In the final IP-redacted v4/v5 run, decision accuracy improved from **60% to 96%** and supported precision from **41.2% to 100%**. V5 still gave one no-link negative control `needs_review`, and **0 of 10** unverified-direct notes passed the strict publication wording gate. Several rejected notes called unverified scanner *labels* “vulnerabilities found”; the decision metric must not be read as note safety. Those outputs remain in this eval for inspection, not in the hosted app.

V4 did not yet encode the product rule that an unverified direct scanner label requires `needs_review`. The measured v4-to-v5 gain is therefore evidence that v5 follows the newer **decision policy** on these cases, not evidence of a general improvement in vulnerability detection. Neither prompt can verify a security finding from this dataset alone.

For a concrete example, `real-10` contains a `7-eleven.com` HTTP host and matching certificate, but its 36 scanner labels have **zero verified labels**. The proposed decision is `needs_review`. V4 answered `supported`; v5 answered `needs_review`. Across the set, supported-decision precision means “correct supported decisions divided by all supported decisions”: v4 made 7 correct supported decisions out of 17; v5 made 7 out of 7. The small sample and unreviewed prose still limit what that number proves.
