# Account-research prompt eval

Run: 2026-09-26T14:59:24.243188+00:00 · model: `gpt-4.1-mini-2025-04-14` · 25 labelled cases

| Metric | Previous v4 | Current v5 |
| --- | ---: | ---: |
| Decision accuracy | 60.0% | 96.0% |
| Macro F1 | 69.4% | 92.3% |
| Supported precision | 41.2% | 100.0% |
| Supported recall | 100.0% | 100.0% |
| Acceptable evidence citation | 100.0% | 100.0% |
| Unverified-label wording gate (lexical proxy) | 0.0% | 0.0% |

Macro F1 change: **+22.8 percentage points**.

## Per-class decision metrics

| Prompt | Label | Cases | Precision | Recall | F1 |
| --- | --- | ---: | ---: | ---: | ---: |
| v4 | supported | 7 | 41.2% | 100.0% | 58.3% |
| v4 | needs_review | 15 | 100.0% | 33.3% | 50.0% |
| v4 | insufficient_evidence | 3 | 100.0% | 100.0% | 100.0% |
| v5 | supported | 7 | 100.0% | 100.0% | 100.0% |
| v5 | needs_review | 15 | 93.8% | 100.0% | 96.8% |
| v5 | insufficient_evidence | 3 | 100.0% | 66.7% | 80.0% |

## Current-prompt errors

- `edge-product-and-org-only`: expected `insufficient_evidence`, got `needs_review`

## What this does and does not measure

Twenty-two cases have Codex-curated draft decision labels from the supplied snapshot; three are marked synthetic negative controls. The labels have not been independently human-adjudicated; `label_review.md` is provided for applicant review. Cases were deliberately chosen to stress direct, unverified, and partial matches. They are not a random sample of 425,121 candidate domains. The citation metric checks whether a response cites one of the reviewed evidence rows, not whether the service operator is known. The wording gate is the published lexical safety proxy, not a human judgement of prose quality. Outputs are advisory and require human verification. See `labelled_cases.jsonl` for input evidence and label rationales and `predictions.jsonl` for exact model outputs.
