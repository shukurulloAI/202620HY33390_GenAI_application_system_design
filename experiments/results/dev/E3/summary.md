# E3: Lexical vs dense vs hybrid?

Cases `eval/cases/dev.jsonl` (70, sha256 `5a62a1c6b684`), commit `3a4d287`. Reference variant: `dense`.

| Variant | Recall@5 | MRR | nDCG@5 | P@5 | R@5 en | R@5 ko | R@5 ru | R@5 uz | R@5 vi | R@5 zh | Retrieve s (median) |
|---|---|---|---|---|---|---|---|---|---|---|---|
| dense | 0.705 | 0.6 | 0.493 | 0.214 | 0.667 | 1.0 | 0.333 | 0.25 | 0.667 | 0.75 | 0.045 |
| bm25-kiwi | 0.561 | 0.433 | 0.394 | 0.185 | 0.444 | 0.833 | 0.5 | 0.0 | 0.333 | 0.75 | 0.001 |
| bm25-bigram | 0.585 | 0.494 | 0.407 | 0.18 | 0.444 | 1.0 | 0.0 | 0.0 | 0.333 | 0.75 | 0.001 |
| hybrid-rrf | 0.773 | 0.583 | 0.504 | 0.223 | 0.722 | 1.0 | 0.667 | 0.25 | 0.667 | 1.0 | 0.045 |

n = 44 cases with gold chunks.

## Changes against `dense`

- `bm25-kiwi`: worse on 10 (h03, h11, h12, h13, h21, h37, h75, h77, item17, item19); better on 3 (h26, h79, h81)
- `bm25-bigram`: worse on 9 (h03, h11, h12, h13, h16, h21, h37, h77, item19); better on 3 (h26, h73, h81)
- `hybrid-rrf`: worse on 0 (–); better on 3 (h26, h79, h81)
