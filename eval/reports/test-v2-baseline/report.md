# Evaluation: test-v2-baseline

Cases: `eval/cases/v2/test.jsonl` (65 cases, sha256 `0d0a8e2918fc`), commit `ccb3966`, 2026-11-16T20:47:39.

## Overall

| Metric | Value |
|---|---|
| Case correct | 38/65 (58%), 95% CI 46%–70% |
| Expected behaviour (answer / abstain / clarify / out of scope) | 46/65 (71%), 95% CI 59%–80% |
| Bin correct (answerable item cases) | 28/44 (64%), 95% CI 49%–76% |
| Every expected bin named (multi-item / vague-item cases) | 3/8 (38%) |
| **False answers** (answered when it should not, or wrong bin) | 6/65 (9%), 95% CI 4%–19% |
| Abstained when it should | 6/10 (60%) |
| Asked back when it should | 0/3 (0%) |
| Gold schedule row shown | 12/14 (86%) |
| Only gold rows shown | 12/14 (86%) |
| Router intent | – |
| Router district / dong (place only in the question) | – / – |
| Retrieval Recall@5 / Hit@5 / MRR / nDCG@5 / P@5 (n=44) | 0.413 / 0.614 / 0.414 / 0.363 / 0.25 |
| Gate TP / FP / FN / TN (n=65) | 44 / 21 / 0 / 0 (FP rate 1.0, FN rate 0.0) |
| Cites a gold chunk (answers citing an item chunk) | 24/33 (73%) |
| Citation precision (cited claims supported by their cited sources, judge) | not judged (python -m eval.answer_judge <traces>, then --rescore) |
| Citation coverage (all claims supported by their own citations, judge) | not judged (python -m eval.answer_judge <traces>, then --rescore) |
| Answer in the asked language (script) | 41/41 (100%) |
| JSON valid | 65/65 (100%) |
| Downgraded by validation | 0 |
| Item part withheld, schedule only (not a false answer) | 0 |
| Contract problems | 0 |
| Latency mean / median / p90 (s) | 4.13 / 4.0 / 4.92 |

## By slice

| | Cases | Correct | Behaviour | Bin | False answers | Recall@5 |
|---|---|---|---|---|---|---|
| ambiguous_location | 3 | 0/3 (0%) | 0/3 (0%) | – | 0/3 (0%) | None |
| analogy | 5 | 2/5 (40%) | 2/5 (40%) | 1/3 (33%) | 1/5 (20%) | 0.333 |
| bulky | 3 | 3/3 (100%) | 3/3 (100%) | 3/3 (100%) | 0/3 (0%) | 0.5 |
| combined | 4 | 4/4 (100%) | 4/4 (100%) | 4/4 (100%) | 0/4 (0%) | 0.333 |
| condition | 4 | 3/4 (75%) | 3/4 (75%) | 3/4 (75%) | 0/4 (0%) | 0.417 |
| conflict | 4 | 1/4 (25%) | 3/4 (75%) | 1/4 (25%) | 2/4 (50%) | 0.625 |
| false_premise | 4 | 2/4 (50%) | 3/4 (75%) | 2/4 (50%) | 1/4 (25%) | 0.083 |
| item_direct | 7 | 4/7 (57%) | 5/7 (71%) | 4/7 (57%) | 1/7 (14%) | 0.524 |
| item_tricky | 6 | 4/6 (67%) | 5/6 (83%) | 4/6 (67%) | 1/6 (17%) | 0.583 |
| multi_item | 4 | 1/4 (25%) | 3/4 (75%) | 3/4 (75%) | 0/4 (0%) | 0.292 |
| natural_phrasing | 4 | 2/4 (50%) | 3/4 (75%) | 1/2 (50%) | 0/4 (0%) | 0.0 |
| no_evidence | 4 | 4/4 (100%) | 4/4 (100%) | – | 0/4 (0%) | None |
| out_of_scope | 3 | 0/3 (0%) | 0/3 (0%) | – | 0/3 (0%) | None |
| schedule | 7 | 6/7 (86%) | 6/7 (86%) | – | 0/7 (0%) | None |
| vague_item | 3 | 2/3 (67%) | 2/3 (67%) | 2/3 (67%) | 0/3 (0%) | 0.5 |

## By language

| | Cases | Correct | Behaviour | Bin | False answers | Recall@5 |
|---|---|---|---|---|---|---|
| en | 21 | 16/21 (76%) | 17/21 (81%) | 13/16 (81%) | 0/21 (0%) | 0.531 |
| ko | 13 | 10/13 (77%) | 11/13 (85%) | 8/10 (80%) | 1/13 (8%) | 0.583 |
| ru | 5 | 0/5 (0%) | 3/5 (60%) | 1/4 (25%) | 3/5 (60%) | 0.25 |
| uz | 11 | 5/11 (46%) | 7/11 (64%) | 3/5 (60%) | 1/11 (9%) | 0.267 |
| vi | 8 | 4/8 (50%) | 5/8 (62%) | 2/5 (40%) | 1/8 (12%) | 0.2 |
| zh | 7 | 3/7 (43%) | 3/7 (43%) | 1/4 (25%) | 0/7 (0%) | 0.125 |

## Earliest failed stage (slice × stage)

| Slice | gate | generation | other | retrieval | schedule_tool |
|---|---|---|---|---|---|
| ambiguous_location | 2 |  |  |  | 1 |
| analogy | 1 | 1 |  | 1 |  |
| condition |  |  |  | 1 |  |
| conflict |  | 2 |  | 1 |  |
| false_premise |  |  |  | 2 |  |
| item_direct |  | 1 |  | 2 |  |
| item_tricky |  |  |  | 2 |  |
| multi_item |  | 2 |  | 1 |  |
| natural_phrasing |  |  |  | 2 |  |
| out_of_scope | 3 |  |  |  |  |
| schedule |  |  | 1 |  |  |
| vague_item |  |  |  | 1 |  |

## Latency by stage (median s)

generate_s 3.95 · retrieve_s 0.021 · route_s 0.0 · schedule_s 0.0 · total_s 4.004
