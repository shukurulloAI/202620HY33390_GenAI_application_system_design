# E2: Does the embedding model matter for Korean data + multilingual questions?

Cases `eval/cases/dev.jsonl` (70, sha256 `5a62a1c6b684`), commit `3a4d287`. Reference variant: `bge-small-en`.

| Variant | Recall@5 | MRR | nDCG@5 | P@5 | R@5 en | R@5 ko | R@5 ru | R@5 uz | R@5 vi | R@5 zh | Retrieve s (median) |
|---|---|---|---|---|---|---|---|---|---|---|---|
| bge-small-en | 0.068 | 0.064 | 0.038 | 0.018 | 0.111 | 0.0 | 0.333 | 0.0 | 0.0 | 0.0 | 0.007 |
| bge-m3 | 0.568 | 0.474 | 0.374 | 0.159 | 0.444 | 1.0 | 0.333 | 0.25 | 0.333 | 0.5 | 0.021 |
| bge-small-en+ko-rewrite | 0.068 | 0.069 | 0.037 | 0.014 | 0.167 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.007 |

n = 44 cases with gold chunks.

## Changes against `bge-small-en`

- `bge-m3`: worse on 0 (–); better on 22 (h02, h05, h06, h07, h08, h11, h12, h16, h22, h32, h34, h72, h75, h77, item02, item03, item11, item13, item17, item18, item19, item20)
- `bge-small-en+ko-rewrite`: worse on 2 (h37, h74); better on 2 (h16, h71)
