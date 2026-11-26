# Evaluation: gemma4-12-dev2

Cases: `eval/cases/v2/dev.jsonl` (151 cases, sha256 `cfd5b83f8b03`), commit `dc31aaf` (uncommitted changes), 2026-11-16T16:46:08.

## Overall

| Metric | Value |
|---|---|
| Case correct | 119/151 (79%), 95% CI 72%–85% |
| Expected behaviour (answer / abstain / clarify / out of scope) | 132/151 (87%), 95% CI 81%–92% |
| Bin correct (answerable item cases) | 80/104 (77%), 95% CI 68%–84% |
| Every expected bin named (multi-item / vague-item cases) | 10/18 (56%) |
| **False answers** (answered when it should not, or wrong bin) | 6/151 (4%), 95% CI 2%–8% |
| Abstained when it should | 23/24 (96%) |
| Asked back when it should | 7/7 (100%) |
| Gold schedule row shown | 25/28 (89%) |
| Only gold rows shown | 25/28 (89%) |
| Router intent | 138/141 (98%) |
| Router district / dong (place only in the question) | 16/19 (84%) / 6/19 (32%) |
| Retrieval Recall@5 / Hit@5 / MRR / nDCG@5 / P@5 (n=104) | 0.783 / 0.923 / 0.796 / 0.683 / 0.41 |
| Gate TP / FP / FN / TN (n=120) | 100 / 11 / 4 / 5 (FP rate 0.688, FN rate 0.038) |
| Cites a gold chunk (answers citing an item chunk) | 79/84 (94%) |
| Citation precision (cited claims supported by their cited sources, judge) | not judged (python -m eval.answer_judge <traces>, then --rescore) |
| Citation coverage (all claims supported by their own citations, judge) | not judged (python -m eval.answer_judge <traces>, then --rescore) |
| Answer in the asked language (script) | 83/87 (95%) |
| JSON valid | 112/113 (99%) |
| Downgraded by validation | 10 |
| Item part withheld, schedule only (not a false answer) | 2 |
| Contract problems | 0 |
| Latency mean / median / p90 (s) | 7.79 / 7.67 / 12.08 |

## By slice

| | Cases | Correct | Behaviour | Bin | False answers | Recall@5 |
|---|---|---|---|---|---|---|
| ambiguous_location | 7 | 7/7 (100%) | 7/7 (100%) | – | 0/7 (0%) | None |
| analogy | 11 | 8/11 (73%) | 8/11 (73%) | 2/5 (40%) | 0/11 (0%) | 0.6 |
| bulky | 7 | 4/7 (57%) | 5/7 (71%) | 5/7 (71%) | 0/7 (0%) | 0.571 |
| combined | 10 | 6/10 (60%) | 10/10 (100%) | 8/10 (80%) | 0/10 (0%) | 1.0 |
| condition | 10 | 7/10 (70%) | 7/10 (70%) | 7/10 (70%) | 0/10 (0%) | 0.707 |
| conflict | 10 | 6/10 (60%) | 9/10 (90%) | 6/10 (60%) | 3/10 (30%) | 0.63 |
| false_premise | 8 | 7/8 (88%) | 7/8 (88%) | 7/8 (88%) | 0/8 (0%) | 0.729 |
| item_direct | 17 | 15/17 (88%) | 15/17 (88%) | 15/17 (88%) | 1/17 (6%) | 0.843 |
| item_tricky | 14 | 13/14 (93%) | 13/14 (93%) | 13/14 (93%) | 0/14 (0%) | 0.976 |
| multi_item | 8 | 6/8 (75%) | 6/8 (75%) | 6/8 (75%) | 0/8 (0%) | 0.804 |
| natural_phrasing | 10 | 7/10 (70%) | 8/10 (80%) | 5/8 (62%) | 1/10 (10%) | 0.833 |
| no_evidence | 10 | 9/10 (90%) | 9/10 (90%) | – | 1/10 (10%) | None |
| out_of_scope | 7 | 7/7 (100%) | 7/7 (100%) | – | 0/7 (0%) | None |
| schedule | 15 | 15/15 (100%) | 15/15 (100%) | – | 0/15 (0%) | None |
| vague_item | 7 | 2/7 (29%) | 6/7 (86%) | 6/7 (86%) | 0/7 (0%) | 0.583 |

## By language

| | Cases | Correct | Behaviour | Bin | False answers | Recall@5 |
|---|---|---|---|---|---|---|
| en | 33 | 28/33 (85%) | 30/33 (91%) | 18/21 (86%) | 0/33 (0%) | 0.693 |
| ko | 30 | 25/30 (83%) | 27/30 (90%) | 12/17 (71%) | 1/30 (3%) | 0.78 |
| ru | 22 | 17/22 (77%) | 19/22 (86%) | 13/17 (76%) | 1/22 (4%) | 0.827 |
| uz | 16 | 10/16 (62%) | 12/16 (75%) | 10/14 (71%) | 3/16 (19%) | 0.738 |
| vi | 24 | 20/24 (83%) | 21/24 (88%) | 14/18 (78%) | 0/24 (0%) | 0.843 |
| zh | 26 | 19/26 (73%) | 23/26 (88%) | 13/17 (76%) | 1/26 (4%) | 0.824 |

## Earliest failed stage (slice × stage)

| Slice | gate | generation | retrieval | router | validation |
|---|---|---|---|---|---|
| analogy |  | 2 | 1 |  |  |
| bulky |  | 1 | 1 | 1 |  |
| combined | 2 |  |  | 2 |  |
| condition |  | 2 |  |  | 1 |
| conflict |  | 3 | 1 |  |  |
| false_premise |  |  |  | 1 |  |
| item_direct |  | 1 | 1 |  |  |
| item_tricky |  |  |  |  | 1 |
| multi_item |  |  |  |  | 2 |
| natural_phrasing | 1 |  | 1 | 1 |  |
| no_evidence | 1 |  |  |  |  |
| vague_item |  | 4 |  |  | 1 |

## Latency by stage (median s)

generate_retry_s 4.049 · generate_s 3.993 · rerank_s 0.394 · retrieve_s 0.08 · route_s 3.384 · schedule_s 0.0 · schedule_text_s 2.529 · total_s 7.665

## Failed cases

| Case | Slice | Lang | Expected | Got | Bin | Stage |
|---|---|---|---|---|---|---|
| c04 | condition | uz | answer | INSUFFICIENT_CONTEXT |  | validation |
| c07 | condition | ko | answer | INSUFFICIENT_CONTEXT |  | generation |
| c14 | condition | uz | answer | INSUFFICIENT_CONTEXT |  | generation |
| m09 | multi_item | zh | answer | INSUFFICIENT_CONTEXT |  | validation |
| m12 | multi_item | ru | answer | INSUFFICIENT_CONTEXT |  | validation |
| v01 | vague_item | en | answer | ANSWER | 유리병 | generation |
| v05 | vague_item | uz | answer | ANSWER | 불연성종량제 | generation |
| v06 | vague_item | ru | answer | ANSWER | 종이 | generation |
| v07 | vague_item | en | answer | ANSWER | 대형폐기물 | generation |
| v08 | vague_item | ko | answer | INSUFFICIENT_CONTEXT |  | validation |
| t17 | item_tricky | uz | answer | INSUFFICIENT_CONTEXT |  | validation |
| k04 | conflict | ko | answer | ANSWER | 투명페트병 | retrieval |
| k05 | conflict | vi | answer | INSUFFICIENT_CONTEXT |  | generation |
| k07 | conflict | ru | answer | ANSWER | 플라스틱 | generation |
| k08 | conflict | zh | answer | ANSWER | 발포합성수지 | generation |
| f04 | false_premise | vi | answer | INSUFFICIENT_CONTEXT |  | router |
| n06 | no_evidence | uz | abstain | ANSWER |  | gate |
| b02 | combined | ko | answer | ANSWER |  | gate |
| b03 | combined | zh | answer | ANSWER | 종이 | router |
| b09 | combined | zh | answer | ANSWER | 전용함 | router |
| b10 | combined | vi | answer | ANSWER |  | gate |
| y01 | bulky | en | answer | INSUFFICIENT_CONTEXT |  | retrieval |
| y06 | bulky | ru | answer | INSUFFICIENT_CONTEXT |  | generation |
| y10 | bulky | zh | answer | ANSWER | 대형폐기물 | router |
| p04 | natural_phrasing | zh | answer | INSUFFICIENT_CONTEXT |  | retrieval |
| p06 | natural_phrasing | uz | answer | ANSWER | 발포합성수지 | router |
| p13 | natural_phrasing | en | answer | INSUFFICIENT_CONTEXT |  | gate |
| an01 | analogy | en | answer | INSUFFICIENT_CONTEXT |  | generation |
| an03 | analogy | zh | answer | INSUFFICIENT_CONTEXT |  | generation |
| an08 | analogy | ko | answer | INSUFFICIENT_CONTEXT |  | retrieval |
| item03 | item_direct | vi | answer | INSUFFICIENT_CONTEXT |  | retrieval |
| item11 | item_direct | ru | answer | INSUFFICIENT_CONTEXT |  | generation |
