# Evaluation: cmp-post-dev2

Cases: `eval/cases/v2/dev.jsonl` (151 cases, sha256 `cfd5b83f8b03`), commit `dc31aaf` (uncommitted changes), 2026-11-16T10:59:05.

## Overall

| Metric | Value |
|---|---|
| Case correct | 100/151 (66%), 95% CI 58%–73% |
| Expected behaviour (answer / abstain / clarify / out of scope) | 122/151 (81%), 95% CI 74%–86% |
| Bin correct (answerable item cases) | 64/104 (62%), 95% CI 52%–70% |
| Every expected bin named (multi-item / vague-item cases) | 6/18 (33%) |
| **False answers** (answered when it should not, or wrong bin) | 18/151 (12%), 95% CI 8%–18% |
| Abstained when it should | 21/24 (88%) |
| Asked back when it should | 7/7 (100%) |
| Gold schedule row shown | 25/28 (89%) |
| Only gold rows shown | 25/28 (89%) |
| Router intent | 139/141 (99%) |
| Router district / dong (place only in the question) | 16/19 (84%) / 6/19 (32%) |
| Retrieval Recall@5 / Hit@5 / MRR / nDCG@5 / P@5 (n=104) | 0.653 / 0.798 / 0.655 / 0.574 / 0.348 |
| Gate TP / FP / FN / TN (n=118) | 89 / 7 / 15 / 7 (FP rate 0.5, FN rate 0.144) |
| Cites a gold chunk (answers citing an item chunk) | 65/78 (83%) |
| Citation precision (cited claims supported by their cited sources, judge) | not judged (python -m eval.answer_judge <traces>, then --rescore) |
| Citation coverage (all claims supported by their own citations, judge) | not judged (python -m eval.answer_judge <traces>, then --rescore) |
| Answer in the asked language (script) | 81/81 (100%) |
| JSON valid | 93/96 (97%) |
| Downgraded by validation | 9 |
| Item part withheld, schedule only (not a false answer) | 0 |
| Contract problems | 0 |
| Latency mean / median / p90 (s) | 6.88 / 6.84 / 11.02 |

## By slice

| | Cases | Correct | Behaviour | Bin | False answers | Recall@5 |
|---|---|---|---|---|---|---|
| ambiguous_location | 7 | 7/7 (100%) | 7/7 (100%) | – | 0/7 (0%) | None |
| analogy | 11 | 6/11 (55%) | 7/11 (64%) | 2/5 (40%) | 3/11 (27%) | 0.5 |
| bulky | 7 | 4/7 (57%) | 6/7 (86%) | 5/7 (71%) | 1/7 (14%) | 0.571 |
| combined | 10 | 8/10 (80%) | 10/10 (100%) | 10/10 (100%) | 0/10 (0%) | 0.95 |
| condition | 10 | 5/10 (50%) | 7/10 (70%) | 5/10 (50%) | 3/10 (30%) | 0.81 |
| conflict | 10 | 6/10 (60%) | 10/10 (100%) | 6/10 (60%) | 4/10 (40%) | 0.423 |
| false_premise | 8 | 2/8 (25%) | 5/8 (62%) | 2/8 (25%) | 3/8 (38%) | 0.417 |
| item_direct | 17 | 13/17 (76%) | 14/17 (82%) | 13/17 (76%) | 1/17 (6%) | 0.686 |
| item_tricky | 14 | 7/14 (50%) | 8/14 (57%) | 7/14 (50%) | 1/14 (7%) | 0.643 |
| multi_item | 8 | 4/8 (50%) | 5/8 (62%) | 5/8 (62%) | 0/8 (0%) | 0.637 |
| natural_phrasing | 10 | 6/10 (60%) | 8/10 (80%) | 5/8 (62%) | 1/10 (10%) | 0.771 |
| no_evidence | 10 | 9/10 (90%) | 9/10 (90%) | – | 1/10 (10%) | None |
| out_of_scope | 7 | 7/7 (100%) | 7/7 (100%) | – | 0/7 (0%) | None |
| schedule | 15 | 15/15 (100%) | 15/15 (100%) | – | 0/15 (0%) | None |
| vague_item | 7 | 1/7 (14%) | 4/7 (57%) | 4/7 (57%) | 0/7 (0%) | 0.619 |

## By language

| | Cases | Correct | Behaviour | Bin | False answers | Recall@5 |
|---|---|---|---|---|---|---|
| en | 33 | 22/33 (67%) | 25/33 (76%) | 12/21 (57%) | 3/33 (9%) | 0.634 |
| ko | 30 | 27/30 (90%) | 30/30 (100%) | 15/17 (88%) | 2/30 (7%) | 0.712 |
| ru | 22 | 14/22 (64%) | 16/22 (73%) | 10/17 (59%) | 3/22 (14%) | 0.604 |
| uz | 16 | 6/16 (38%) | 10/16 (62%) | 4/14 (29%) | 4/16 (25%) | 0.649 |
| vi | 24 | 17/24 (71%) | 22/24 (92%) | 14/18 (78%) | 4/24 (17%) | 0.741 |
| zh | 26 | 14/26 (54%) | 19/26 (73%) | 9/17 (53%) | 2/26 (8%) | 0.578 |

## Earliest failed stage (slice × stage)

| Slice | gate | generation | retrieval | router | validation |
|---|---|---|---|---|---|
| analogy | 3 |  | 2 |  |  |
| bulky |  |  | 2 | 1 |  |
| combined |  |  |  | 2 |  |
| condition | 2 | 2 | 1 |  |  |
| conflict |  | 2 | 2 |  |  |
| false_premise | 1 | 1 | 2 | 1 | 1 |
| item_direct | 1 |  | 3 |  |  |
| item_tricky | 1 | 1 | 5 |  |  |
| multi_item | 1 | 2 | 1 |  |  |
| natural_phrasing | 1 | 2 | 1 |  |  |
| no_evidence | 1 |  |  |  |  |
| vague_item |  | 4 | 1 |  | 1 |

## Latency by stage (median s)

generate_retry_s 3.507 · generate_s 3.524 · rerank_s 0.398 · retrieve_s 0.08 · route_s 3.045 · schedule_s 0.0 · schedule_text_s 2.363 · total_s 6.843

## Failed cases

| Case | Slice | Lang | Expected | Got | Bin | Stage |
|---|---|---|---|---|---|---|
| c01 | condition | en | answer | INSUFFICIENT_CONTEXT |  | gate |
| c02 | condition | vi | answer | ANSWER | 종이 | generation |
| c04 | condition | uz | answer | INSUFFICIENT_CONTEXT |  | generation |
| c09 | condition | en | answer | INSUFFICIENT_CONTEXT |  | gate |
| c14 | condition | uz | answer | ANSWER | 고철 | retrieval |
| m03 | multi_item | zh | answer | INSUFFICIENT_CONTEXT |  | generation |
| m04 | multi_item | vi | answer | ANSWER | 종량제봉투 | generation |
| m09 | multi_item | zh | answer | INSUFFICIENT_CONTEXT |  | gate |
| m12 | multi_item | ru | answer | INSUFFICIENT_CONTEXT |  | retrieval |
| v01 | vague_item | en | answer | ANSWER | 유리병 | generation |
| v05 | vague_item | uz | answer | INSUFFICIENT_CONTEXT |  | generation |
| v06 | vague_item | ru | answer | INSUFFICIENT_CONTEXT |  | retrieval |
| v07 | vague_item | en | answer | INSUFFICIENT_CONTEXT |  | validation |
| v08 | vague_item | ko | answer | ANSWER | 고철 | generation |
| v09 | vague_item | zh | answer | ANSWER | 불연성종량제 | generation |
| t02 | item_tricky | en | answer | INSUFFICIENT_CONTEXT |  | retrieval |
| t08 | item_tricky | ko | answer | ANSWER | 비닐 | retrieval |
| t10 | item_tricky | zh | answer | INSUFFICIENT_CONTEXT |  | retrieval |
| t11 | item_tricky | zh | answer | INSUFFICIENT_CONTEXT |  | retrieval |
| t17 | item_tricky | uz | answer | INSUFFICIENT_CONTEXT |  | generation |
| t18 | item_tricky | uz | answer | INSUFFICIENT_CONTEXT |  | gate |
| t20 | item_tricky | ru | answer | INSUFFICIENT_CONTEXT |  | retrieval |
| k01 | conflict | en | answer | ANSWER | 유리병 | retrieval |
| k03 | conflict | uz | answer | ANSWER | 플라스틱 | generation |
| k07 | conflict | ru | answer | ANSWER | 종량제봉투 | generation |
| k08 | conflict | zh | answer | ANSWER | 플라스틱 | retrieval |
| f01 | false_premise | en | answer | INSUFFICIENT_CONTEXT |  | validation |
| f03 | false_premise | zh | answer | INSUFFICIENT_CONTEXT |  | generation |
| f04 | false_premise | vi | answer | ANSWER | 종량제봉투 | router |
| f07 | false_premise | en | answer | ANSWER | 비닐 | retrieval |
| f11 | false_premise | vi | answer | INSUFFICIENT_CONTEXT |  | gate |
| f12 | false_premise | ru | answer | ANSWER | 종량제봉투 | retrieval |
| n11 | no_evidence | ru | abstain | ANSWER |  | gate |
| b03 | combined | zh | answer | ANSWER | 종이 | router |
| b09 | combined | zh | answer | ANSWER | 전용함 | router |
| y01 | bulky | en | answer | INSUFFICIENT_CONTEXT |  | retrieval |
| y05 | bulky | uz | answer | ANSWER | 종량제봉투 | retrieval |
| y10 | bulky | zh | answer | ANSWER | 대형폐기물 | router |
| p04 | natural_phrasing | zh | answer | INSUFFICIENT_CONTEXT |  | retrieval |
| p05 | natural_phrasing | vi | answer | ANSWER | 종이 | generation |
| p06 | natural_phrasing | uz | answer | ANSWER | 발포합성수지 | generation |
| p13 | natural_phrasing | en | answer | INSUFFICIENT_CONTEXT |  | gate |
| d07 | item_direct | uz | answer | INSUFFICIENT_CONTEXT |  | retrieval |
| an03 | analogy | zh | answer | INSUFFICIENT_CONTEXT |  | gate |
| an05 | analogy | uz | answer | INSUFFICIENT_CONTEXT |  | retrieval |
| an08 | analogy | ko | answer | ANSWER | 종량제봉투 | retrieval |
| at04 | analogy | vi | abstain | ANSWER |  | gate |
| at07 | analogy | en | abstain | ANSWER |  | gate |
| item03 | item_direct | vi | answer | ANSWER | 종량제봉투 | retrieval |
| item05 | item_direct | ru | answer | INSUFFICIENT_CONTEXT |  | retrieval |
| item11 | item_direct | ru | answer | INSUFFICIENT_CONTEXT |  | gate |
