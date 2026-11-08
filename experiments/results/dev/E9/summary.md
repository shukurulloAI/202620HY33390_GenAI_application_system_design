# E9: Does searching the router's item name against chunk names help retrieval?

Cases `eval/cases/dev.jsonl` (70, sha256 `5a62a1c6b684`), commit `3a4d287` (uncommitted changes). Reference variant: `off`.

| Variant | Recall@5 | MRR | nDCG@5 | P@5 | R@5 en | R@5 ko | R@5 ru | R@5 uz | R@5 vi | R@5 zh | Retrieve s (median) |
|---|---|---|---|---|---|---|---|---|---|---|---|
| off | 0.795 | 0.678 | 0.582 | 0.259 | 0.778 | 1.0 | 0.667 | 0.25 | 0.667 | 1.0 | 0.113 |
| names | 0.818 | 0.709 | 0.624 | 0.277 | 0.778 | 1.0 | 0.667 | 0.5 | 0.667 | 1.0 | 0.104 |
| names+rerank-item | 0.841 | 0.73 | 0.646 | 0.282 | 0.833 | 1.0 | 0.667 | 0.5 | 0.667 | 1.0 | 0.108 |
| dense | 0.818 | 0.693 | 0.613 | 0.282 | 0.778 | 1.0 | 0.667 | 0.5 | 0.667 | 1.0 | 0.062 |
| dense+names+rerank-item | 0.818 | 0.713 | 0.64 | 0.282 | 0.833 | 1.0 | 0.667 | 0.5 | 0.667 | 0.75 | 0.108 |

n = 44 cases with gold chunks.

## Changes against `off`

- `names`: worse on 0 (–); better on 1 (item14)
- `names+rerank-item`: worse on 0 (–); better on 2 (h31, item14)
- `dense`: worse on 0 (–); better on 1 (h24)
- `dense+names+rerank-item`: worse on 1 (h26); better on 2 (h31, item14)
