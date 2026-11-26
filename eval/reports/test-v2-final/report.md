# Evaluation: test-v2-final

Cases: `eval/cases/v2/test.jsonl` (65 cases, sha256 `0d0a8e2918fc`), commit `dc31aaf` (uncommitted changes), 2026-11-16T20:42:53.

## Overall

| Metric | Value |
|---|---|
| Case correct | 46/65 (71%), 95% CI 59%–80% |
| Expected behaviour (answer / abstain / clarify / out of scope) | 51/65 (78%), 95% CI 67%–87% |
| Bin correct (answerable item cases) | 27/44 (61%), 95% CI 47%–74% |
| Every expected bin named (multi-item / vague-item cases) | 6/8 (75%) |
| **False answers** (answered when it should not, or wrong bin) | 6/65 (9%), 95% CI 4%–19% |
| Abstained when it should | 8/10 (80%) |
| Asked back when it should | 3/3 (100%) |
| Gold schedule row shown | 13/14 (93%) |
| Only gold rows shown | 13/14 (93%) |
| Router intent | 61/61 (100%) |
| Router district / dong (place only in the question) | 7/8 (88%) / 0/8 (0%) |
| Retrieval Recall@5 / Hit@5 / MRR / nDCG@5 / P@5 (n=44) | 0.689 / 0.841 / 0.787 / 0.634 / 0.345 |
| Gate TP / FP / FN / TN (n=51) | 40 / 5 / 4 / 2 (FP rate 0.714, FN rate 0.091) |
| Cites a gold chunk (answers citing an item chunk) | 25/30 (83%) |
| Citation precision (cited claims supported by their cited sources, judge) | not judged (python -m eval.answer_judge <traces>, then --rescore) |
| Citation coverage (all claims supported by their own citations, judge) | not judged (python -m eval.answer_judge <traces>, then --rescore) |
| Answer in the asked language (script) | 34/34 (100%) |
| JSON valid | 47/47 (100%) |
| Downgraded by validation | 6 |
| Item part withheld, schedule only (not a false answer) | 2 |
| Contract problems | 0 |
| Latency mean / median / p90 (s) | 8.06 / 8.09 / 11.69 |

## By slice

| | Cases | Correct | Behaviour | Bin | False answers | Recall@5 |
|---|---|---|---|---|---|---|
| ambiguous_location | 3 | 3/3 (100%) | 3/3 (100%) | – | 0/3 (0%) | None |
| analogy | 5 | 2/5 (40%) | 2/5 (40%) | 0/3 (0%) | 0/5 (0%) | 0.833 |
| bulky | 3 | 3/3 (100%) | 3/3 (100%) | 3/3 (100%) | 0/3 (0%) | 0.833 |
| combined | 4 | 2/4 (50%) | 4/4 (100%) | 2/4 (50%) | 0/4 (0%) | 0.417 |
| condition | 4 | 3/4 (75%) | 3/4 (75%) | 3/4 (75%) | 0/4 (0%) | 0.75 |
| conflict | 4 | 0/4 (0%) | 0/4 (0%) | 0/4 (0%) | 0/4 (0%) | 0.625 |
| false_premise | 4 | 1/4 (25%) | 2/4 (50%) | 1/4 (25%) | 1/4 (25%) | 0.625 |
| item_direct | 7 | 7/7 (100%) | 7/7 (100%) | 7/7 (100%) | 0/7 (0%) | 0.857 |
| item_tricky | 6 | 5/6 (83%) | 6/6 (100%) | 5/6 (83%) | 1/6 (17%) | 0.75 |
| multi_item | 4 | 3/4 (75%) | 4/4 (100%) | 3/4 (75%) | 1/4 (25%) | 0.625 |
| natural_phrasing | 4 | 3/4 (75%) | 3/4 (75%) | 1/2 (50%) | 1/4 (25%) | 0.333 |
| no_evidence | 4 | 2/4 (50%) | 2/4 (50%) | – | 2/4 (50%) | None |
| out_of_scope | 3 | 3/3 (100%) | 3/3 (100%) | – | 0/3 (0%) | None |
| schedule | 7 | 7/7 (100%) | 7/7 (100%) | – | 0/7 (0%) | None |
| vague_item | 3 | 2/3 (67%) | 2/3 (67%) | 2/3 (67%) | 0/3 (0%) | 0.667 |

## By language

| | Cases | Correct | Behaviour | Bin | False answers | Recall@5 |
|---|---|---|---|---|---|---|
| en | 21 | 16/21 (76%) | 17/21 (81%) | 11/16 (69%) | 1/21 (5%) | 0.729 |
| ko | 13 | 10/13 (77%) | 11/13 (85%) | 7/10 (70%) | 0/13 (0%) | 0.8 |
| ru | 5 | 3/5 (60%) | 4/5 (80%) | 2/4 (50%) | 2/5 (40%) | 0.667 |
| uz | 11 | 9/11 (82%) | 9/11 (82%) | 4/5 (80%) | 1/11 (9%) | 0.6 |
| vi | 8 | 4/8 (50%) | 5/8 (62%) | 2/5 (40%) | 1/8 (12%) | 0.6 |
| zh | 7 | 4/7 (57%) | 5/7 (71%) | 1/4 (25%) | 1/7 (14%) | 0.5 |

## Earliest failed stage (slice × stage)

| Slice | gate | generation | retrieval | router | validation |
|---|---|---|---|---|---|
| analogy |  | 2 |  |  | 1 |
| combined |  |  | 2 |  |  |
| condition |  |  |  |  | 1 |
| conflict | 1 | 3 |  |  |  |
| false_premise |  | 1 | 1 |  | 1 |
| item_tricky |  | 1 |  |  |  |
| multi_item |  |  | 1 |  |  |
| natural_phrasing |  |  |  | 1 |  |
| no_evidence | 2 |  |  |  |  |
| vague_item |  |  | 1 |  |  |

## Latency by stage (median s)

generate_retry_s 3.592 · generate_s 3.871 · rerank_s 0.771 · retrieve_s 0.079 · route_s 3.335 · schedule_s 0.0 · schedule_text_s 2.566 · total_s 8.086
