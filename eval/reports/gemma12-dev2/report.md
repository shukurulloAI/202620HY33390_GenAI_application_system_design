# Evaluation: gemma12-dev2

Cases: `eval/cases/v2/dev.jsonl` (151 cases, sha256 `cfd5b83f8b03`), commit `dc31aaf` (uncommitted changes), 2026-11-16T16:23:22.

## Overall

| Metric | Value |
|---|---|
| Case correct | 112/151 (74%), 95% CI 67%–80% |
| Expected behaviour (answer / abstain / clarify / out of scope) | 130/151 (86%), 95% CI 80%–91% |
| Bin correct (answerable item cases) | 78/104 (75%), 95% CI 66%–82% |
| Every expected bin named (multi-item / vague-item cases) | 8/18 (44%) |
| **False answers** (answered when it should not, or wrong bin) | 16/151 (11%), 95% CI 7%–17% |
| Abstained when it should | 21/24 (88%) |
| Asked back when it should | 6/7 (86%) |
| Gold schedule row shown | 25/28 (89%) |
| Only gold rows shown | 25/28 (89%) |
| Router intent | 139/141 (99%) |
| Router district / dong (place only in the question) | 16/19 (84%) / 6/19 (32%) |
| Retrieval Recall@5 / Hit@5 / MRR / nDCG@5 / P@5 (n=104) | 0.782 / 0.942 / 0.757 / 0.66 / 0.394 |
| Gate TP / FP / FN / TN (n=120) | 102 / 13 / 2 / 3 (FP rate 0.812, FN rate 0.019) |
| Cites a gold chunk (answers citing an item chunk) | 80/87 (92%) |
| Citation precision (cited claims supported by their cited sources, judge) | not judged (python -m eval.answer_judge <traces>, then --rescore) |
| Citation coverage (all claims supported by their own citations, judge) | not judged (python -m eval.answer_judge <traces>, then --rescore) |
| Answer in the asked language (script) | 78/90 (87%) |
| JSON valid | 115/115 (100%) |
| Downgraded by validation | 13 |
| Item part withheld, schedule only (not a false answer) | 0 |
| Contract problems | 0 |
| Latency mean / median / p90 (s) | 11.4 / 11.12 / 18.04 |

## By slice

| | Cases | Correct | Behaviour | Bin | False answers | Recall@5 |
|---|---|---|---|---|---|---|
| ambiguous_location | 7 | 6/7 (86%) | 6/7 (86%) | – | 0/7 (0%) | None |
| analogy | 11 | 7/11 (64%) | 7/11 (64%) | 2/5 (40%) | 1/11 (9%) | 0.533 |
| bulky | 7 | 5/7 (71%) | 6/7 (86%) | 6/7 (86%) | 0/7 (0%) | 0.571 |
| combined | 10 | 8/10 (80%) | 10/10 (100%) | 10/10 (100%) | 0/10 (0%) | 0.95 |
| condition | 10 | 7/10 (70%) | 7/10 (70%) | 7/10 (70%) | 2/10 (20%) | 0.877 |
| conflict | 10 | 4/10 (40%) | 7/10 (70%) | 4/10 (40%) | 3/10 (30%) | 0.657 |
| false_premise | 8 | 5/8 (62%) | 6/8 (75%) | 5/8 (62%) | 1/8 (12%) | 0.646 |
| item_direct | 17 | 16/17 (94%) | 17/17 (100%) | 16/17 (94%) | 2/17 (12%) | 0.873 |
| item_tricky | 14 | 11/14 (79%) | 13/14 (93%) | 11/14 (79%) | 2/14 (14%) | 0.952 |
| multi_item | 8 | 5/8 (62%) | 6/8 (75%) | 6/8 (75%) | 1/8 (12%) | 0.588 |
| natural_phrasing | 10 | 8/10 (80%) | 10/10 (100%) | 6/8 (75%) | 2/10 (20%) | 0.958 |
| no_evidence | 10 | 8/10 (80%) | 8/10 (80%) | – | 2/10 (20%) | None |
| out_of_scope | 7 | 7/7 (100%) | 7/7 (100%) | – | 0/7 (0%) | None |
| schedule | 15 | 15/15 (100%) | 15/15 (100%) | – | 0/15 (0%) | None |
| vague_item | 7 | 0/7 (0%) | 5/7 (71%) | 5/7 (71%) | 0/7 (0%) | 0.583 |

## By language

| | Cases | Correct | Behaviour | Bin | False answers | Recall@5 |
|---|---|---|---|---|---|---|
| en | 33 | 23/33 (70%) | 28/33 (85%) | 15/21 (71%) | 4/33 (12%) | 0.674 |
| ko | 30 | 27/30 (90%) | 27/30 (90%) | 14/17 (82%) | 0/30 (0%) | 0.845 |
| ru | 22 | 17/22 (77%) | 19/22 (86%) | 14/17 (82%) | 2/22 (9%) | 0.741 |
| uz | 16 | 9/16 (56%) | 15/16 (94%) | 8/14 (57%) | 6/16 (38%) | 0.774 |
| vi | 24 | 20/24 (83%) | 21/24 (88%) | 15/18 (83%) | 2/24 (8%) | 0.843 |
| zh | 26 | 16/26 (62%) | 20/26 (77%) | 12/17 (71%) | 2/26 (8%) | 0.833 |

## Earliest failed stage (slice × stage)

| Slice | gate | generation | retrieval | router | schedule_tool | validation |
|---|---|---|---|---|---|---|
| ambiguous_location |  |  |  |  | 1 |  |
| analogy | 2 | 2 |  |  |  |  |
| bulky |  |  | 1 | 1 |  |  |
| combined |  |  |  | 2 |  |  |
| condition |  | 1 |  |  |  | 2 |
| conflict |  | 5 |  |  |  | 1 |
| false_premise |  |  |  | 1 |  | 2 |
| item_direct |  | 1 |  |  |  |  |
| item_tricky |  | 3 |  |  |  |  |
| multi_item |  | 2 | 1 |  |  |  |
| natural_phrasing |  | 2 |  |  |  |  |
| no_evidence | 2 |  |  |  |  |  |
| vague_item |  | 5 |  |  |  | 2 |

## Latency by stage (median s)

generate_retry_s 5.336 · generate_s 4.912 · rerank_s 2.582 · retrieve_s 0.078 · route_s 4.011 · schedule_s 0.0 · schedule_text_s 2.608 · total_s 11.12

## Failed cases

| Case | Slice | Lang | Expected | Got | Bin | Stage |
|---|---|---|---|---|---|---|
| c01 | condition | en | answer | INSUFFICIENT_CONTEXT |  | validation |
| c04 | condition | uz | answer | INSUFFICIENT_CONTEXT |  | generation |
| c05 | condition | ru | answer | INSUFFICIENT_CONTEXT |  | validation |
| m07 | multi_item | en | answer | ANSWER | 고철 | generation |
| m10 | multi_item | vi | answer | INSUFFICIENT_CONTEXT |  | generation |
| m12 | multi_item | ru | answer | INSUFFICIENT_CONTEXT |  | retrieval |
| v01 | vague_item | en | answer | ANSWER | 유리병 | generation |
| v03 | vague_item | zh | answer | INSUFFICIENT_CONTEXT |  | validation |
| v05 | vague_item | uz | answer | ANSWER | 불연성종량제 | generation |
| v06 | vague_item | ru | answer | ANSWER | 종이 | generation |
| v07 | vague_item | en | answer | ANSWER | 대형폐기물 | generation |
| v08 | vague_item | ko | answer | INSUFFICIENT_CONTEXT |  | validation |
| v09 | vague_item | zh | answer | ANSWER | 대형폐기물 | generation |
| t10 | item_tricky | zh | answer | INSUFFICIENT_CONTEXT |  | generation |
| t16 | item_tricky | uz | answer | ANSWER | 전용함 | generation |
| t17 | item_tricky | uz | answer | ANSWER | 플라스틱 | generation |
| k01 | conflict | en | answer | ANSWER | 플라스틱 | generation |
| k03 | conflict | uz | answer | ANSWER | 플라스틱 | generation |
| k04 | conflict | ko | answer | INSUFFICIENT_CONTEXT |  | validation |
| k05 | conflict | vi | answer | INSUFFICIENT_CONTEXT |  | generation |
| k07 | conflict | ru | answer | ANSWER | 종량제봉투 | generation |
| k08 | conflict | zh | answer | INSUFFICIENT_CONTEXT |  | generation |
| f03 | false_premise | zh | answer | INSUFFICIENT_CONTEXT |  | validation |
| f04 | false_premise | vi | answer | ANSWER | 종량제봉투 | router |
| f07 | false_premise | en | answer | INSUFFICIENT_CONTEXT |  | validation |
| n09 | no_evidence | zh | abstain | ANSWER |  | gate |
| n11 | no_evidence | ru | abstain | ANSWER |  | gate |
| b03 | combined | zh | answer | ANSWER | 종이 | router |
| b09 | combined | zh | answer | ANSWER | 전용함 | router |
| a05 | ambiguous_location | en | clarify | INSUFFICIENT_CONTEXT |  | schedule_tool |
| y01 | bulky | en | answer | INSUFFICIENT_CONTEXT |  | retrieval |
| y10 | bulky | zh | answer | ANSWER | 대형폐기물 | router |
| p02 | natural_phrasing | en | answer | ANSWER | 플라스틱 | generation |
| p06 | natural_phrasing | uz | answer | ANSWER | 발포합성수지 | generation |
| d07 | item_direct | uz | answer | ANSWER | 가전제품 | generation |
| an01 | analogy | en | answer | INSUFFICIENT_CONTEXT |  | generation |
| an03 | analogy | zh | answer | INSUFFICIENT_CONTEXT |  | generation |
| an08 | analogy | ko | answer | INSUFFICIENT_CONTEXT |  | gate |
| at04 | analogy | vi | abstain | ANSWER |  | gate |
