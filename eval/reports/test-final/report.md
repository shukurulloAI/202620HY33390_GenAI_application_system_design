# Evaluation: test-final

Cases: `eval/cases/test.jsonl` (30 cases, sha256 `c3be328d06ca`), commit `cf047ff` (uncommitted changes), 2026-11-09T00:52:06.

## Overall

| Metric | Value |
|---|---|
| Case correct | 22/30 (73%), 95% CI 56%–86% |
| Expected behaviour (answer / abstain / clarify / out of scope) | 24/30 (80%), 95% CI 63%–90% |
| Bin correct (answerable item cases) | 11/19 (58%), 95% CI 36%–77% |
| **False answers** (answered when it should not, or wrong bin) | 1/30 (3%), 95% CI 1%–17% |
| Abstained when it should | 5/5 (100%) |
| Asked back when it should | 2/2 (100%) |
| Gold schedule row shown | 8/8 (100%) |
| Only gold rows shown | 8/8 (100%) |
| Router intent | 27/27 (100%) |
| Router district / dong (place only in the question) | 1/1 (100%) / 1/1 (100%) |
| Retrieval Recall@5 / Hit@5 / MRR / nDCG@5 / P@5 (n=19) | 0.526 / 0.684 / 0.47 / 0.422 / 0.221 |
| Gate TP / FP / FN / TN (n=22) | 15 / 1 / 4 / 2 (FP rate 0.333, FN rate 0.211) |
| Cites a gold chunk (answers citing an item chunk) | 7/12 (58%) |
| Citation precision (cited claims supported by their cited sources, judge) | 12/13 (92%) |
| Citation coverage (all claims supported by their own citations, judge) | 12/17 (71%) |
| Answer in the asked language (script) | 13/13 (100%) |
| JSON valid | 17/17 (100%) |
| Downgraded by validation | 3 |
| Item part withheld, schedule only (not a false answer) | 1 |
| Contract problems | 0 |
| Latency mean / median / p90 (s) | 18.03 / 21.68 / 28.58 |

## By slice

| | Cases | Correct | Behaviour | Bin | False answers | Recall@5 |
|---|---|---|---|---|---|---|
| ambiguous_location | 2 | 2/2 (100%) | 2/2 (100%) | – | 0/2 (0%) | None |
| combined | 4 | 3/4 (75%) | 4/4 (100%) | 3/4 (75%) | 0/4 (0%) | 0.583 |
| conflict | 2 | 0/2 (0%) | 1/2 (50%) | 0/2 (0%) | 1/2 (50%) | 0.0 |
| false_premise | 2 | 1/2 (50%) | 1/2 (50%) | 1/2 (50%) | 0/2 (0%) | 0.833 |
| item_direct | 6 | 3/6 (50%) | 3/6 (50%) | 3/6 (50%) | 0/6 (0%) | 0.583 |
| item_tricky | 5 | 4/5 (80%) | 4/5 (80%) | 4/5 (80%) | 0/5 (0%) | 0.5 |
| no_evidence | 3 | 3/3 (100%) | 3/3 (100%) | – | 0/3 (0%) | None |
| out_of_scope | 2 | 2/2 (100%) | 2/2 (100%) | – | 0/2 (0%) | None |
| schedule | 4 | 4/4 (100%) | 4/4 (100%) | – | 0/4 (0%) | None |

## By language

| | Cases | Correct | Behaviour | Bin | False answers | Recall@5 |
|---|---|---|---|---|---|---|
| en | 15 | 10/15 (67%) | 10/15 (67%) | 4/9 (44%) | 0/15 (0%) | 0.556 |
| ko | 8 | 7/8 (88%) | 8/8 (100%) | 4/5 (80%) | 1/8 (12%) | 0.667 |
| ru | 2 | 2/2 (100%) | 2/2 (100%) | 2/2 (100%) | 0/2 (0%) | 0.0 |
| vi | 3 | 1/3 (33%) | 2/3 (67%) | 0/2 (0%) | 0/3 (0%) | 0.333 |
| zh | 2 | 2/2 (100%) | 2/2 (100%) | 1/1 (100%) | 0/2 (0%) | 1.0 |

## Earliest failed stage (slice × stage)

| Slice | gate | retrieval | validation |
|---|---|---|---|
| combined |  | 1 |  |
| conflict |  | 2 |  |
| false_premise | 1 |  |  |
| item_direct | 1 | 1 | 1 |
| item_tricky |  |  | 1 |

## Latency by stage (median s)

generate_s 13.792 · rerank_s 5.864 · retrieve_s 0.143 · route_s 6.601 · schedule_s 0.0 · schedule_text_s 1.274 · total_s 21.681
