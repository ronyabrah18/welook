# Account-research evaluation

This evaluates the **offline AI research note**, not whether an organisation owns a service or needs to buy software. The labelled target is the note's `decision`: `supported` for a historical direct domain-service association with a scanner-verified label, `needs_review` for an unverified direct label or one-sided domain link, and `insufficient_evidence` when the supplied observations have no meaningful domain link. `supported` never means a confirmed current vulnerability.

`labelled_cases.jsonl` contains **25 draft-labelled cases**: 22 compact, IP-redacted evidence bundles from the supplied snapshot and three clearly marked synthetic negative controls. Codex proposed the decisions after inspecting the evidence; they have not been independently human-adjudicated. Each record includes the expected decision, a written rationale, and acceptable supporting evidence IDs. [label_review.md](label_review.md) makes them easy to review. Cases were deliberately chosen to challenge attribution and scanner-label wording; this is not a prevalence-weighted sample of all 425,121 candidate domains. The bundled inputs make the eval rerunnable without the 12.44 GB source file or local warehouse.

## Re-score saved predictions for free

After `uv sync --locked`, run from the repository root:

```bash
uv run python evals/run_eval.py
```

This uses the committed predictions without an API key or paid calls. It verifies prompt/evidence hashes and rewrites `results.json` and `results.md` with the recalculated metrics and a new report timestamp. Saved predictions are unchanged.

## Run the models again

To compare the same 25 cases against v4 and the batch workflow's current v5 prompt:

```bash
uv run python evals/run_eval.py --live
```

This requires `OPENAI_API_KEY` in the ignored `.env` file and can make up to 50 paid calls, reusing cache entries when available. It uses the same pinned model, structured-output schema, traces, and shared US$10 ledger as offline enrichment. A successful run replaces `predictions.jsonl` and both reports. A failed run keeps the previous complete comparison and saves partial output under ignored `artifacts/ai/`.

## Interpret the results

The report gives three-class precision/recall/F1, exact decision accuracy, citation agreement with the labelled evidence anchors, and a lexical wording-gate rate for unverified direct labels. A missed/failed case counts against recall and overall accuracy. The wording gate catches specific overstatements but cannot establish that prose is safe or useful. The cases have no externally verified service-owner or vulnerability ground truth, so these metrics cannot measure real-world sales conversion or technical finding accuracy. Review false positives and generated prose before publishing any new note.

In the final IP-redacted v4/v5 run, decision accuracy improved from **60% to 96%** and supported precision from **41.2% to 100%**. V5 still gave one no-link negative control `needs_review`, and **0 of 10** unverified-direct notes passed the strict publication wording gate. Several rejected notes called unverified scanner *labels* “vulnerabilities found”; the decision metric must not be read as note safety. Those outputs remain in this eval for inspection, not in the hosted app.

V4 did not yet encode the product rule that an unverified direct scanner label requires `needs_review`. The measured v4-to-v5 gain is therefore evidence that v5 follows the newer **decision policy** on these cases, not evidence of a general improvement in vulnerability detection. Neither prompt can verify a security finding from this dataset alone.

For a concrete example, `real-10` contains a `7-eleven.com` HTTP host and matching certificate, but its 36 scanner labels have **zero verified labels**. The proposed decision is `needs_review`. V4 answered `supported`; v5 answered `needs_review`. Across the set, supported-decision precision means “correct supported decisions divided by all supported decisions”: v4 made 7 correct supported decisions out of 17; v5 made 7 out of 7. The small sample and unreviewed prose still limit what that number proves.
