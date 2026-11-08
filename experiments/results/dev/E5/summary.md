# E5: Does reranking help (for dense and for hybrid retrieval), and what gate threshold?

Cases `eval/cases/dev.jsonl` (70, sha256 `5a62a1c6b684`), commit `3a4d287`. Reference variant: `rerank-on`.

| Variant | Recall@5 | MRR | nDCG@5 | P@5 | R@5 en | R@5 ko | R@5 ru | R@5 uz | R@5 vi | R@5 zh | Retrieve s (median) |
|---|---|---|---|---|---|---|---|---|---|---|---|
| rerank-off | 0.773 | 0.583 | 0.504 | 0.223 | 0.722 | 1.0 | 0.667 | 0.25 | 0.667 | 1.0 | 0.046 |
| rerank-on | 0.795 | 0.678 | 0.582 | 0.259 | 0.778 | 1.0 | 0.667 | 0.25 | 0.667 | 1.0 | 0.06 |
| dense-rerank-off | 0.705 | 0.6 | 0.493 | 0.214 | 0.667 | 1.0 | 0.333 | 0.25 | 0.667 | 0.75 | 0.046 |
| dense-rerank-on | 0.818 | 0.693 | 0.613 | 0.282 | 0.778 | 1.0 | 0.667 | 0.5 | 0.667 | 1.0 | 0.056 |

n = 44 cases with gold chunks.

## Changes against `rerank-on`

- `rerank-off`: worse on 2 (h33, h73); better on 1 (item10)
- `dense-rerank-off`: worse on 5 (h26, h33, h73, h79, h81); better on 1 (item10)
- `dense-rerank-on`: worse on 0 (–); better on 1 (h24)
