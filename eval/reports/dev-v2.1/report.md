# Evaluation: dev-v2.1

Cases: `eval/cases/dev.jsonl` (70 cases, sha256 `5a62a1c6b684`), commit `f691792`, 2026-11-11T17:17:33.

## Overall

| Metric | Value |
|---|---|
| Case correct | 56/70 (80%), 95% CI 69%–88% |
| Expected behaviour (answer / abstain / clarify / out of scope) | 59/70 (84%), 95% CI 74%–91% |
| Bin correct (answerable item cases) | 32/45 (71%), 95% CI 57%–82% |
| **False answers** (answered when it should not, or wrong bin) | 3/70 (4%), 95% CI 1%–12% |
| Abstained when it should | 9/10 (90%) |
| Asked back when it should | 4/4 (100%) |
| Gold schedule row shown | 19/19 (100%) |
| Only gold rows shown | 18/19 (95%) |
| Router intent | 62/63 (98%) |
| Router district / dong (place only in the question) | 4/4 (100%) / 3/4 (75%) |
| Retrieval Recall@5 / MRR / nDCG@5 / P@5 (n=44) | 0.841 / 0.737 / 0.649 / 0.282 |
| Gate TP / FP / FN / TN (n=46) | 42 / 0 / 2 / 2 (FP rate 0.0, FN rate 0.045) |
| Cites a gold chunk / citation precision | 30/35 (86%) / 0.712 |
| Answer in the asked language (script) | 34/35 (97%) |
| JSON valid | 41/42 (98%) |
| Downgraded by validation | 5 |
| Item part withheld, schedule only (not a false answer) | 0 |
| Contract problems | 0 |
| Latency mean / median / p90 (s) | 16.42 / 21.18 / 27.19 |

## By slice

| | Cases | Correct | Behaviour | Bin | False answers | Recall@5 |
|---|---|---|---|---|---|---|
| ambiguous_location | 4 | 4/4 (100%) | 4/4 (100%) | – | 0/4 (0%) | None |
| combined | 8 | 8/8 (100%) | 8/8 (100%) | 8/8 (100%) | 0/8 (0%) | 1.0 |
| conflict | 6 | 0/6 (0%) | 1/6 (17%) | 0/6 (0%) | 1/6 (17%) | 0.667 |
| false_premise | 6 | 4/6 (67%) | 4/6 (67%) | 4/6 (67%) | 0/6 (0%) | 1.0 |
| item_direct | 14 | 9/14 (64%) | 11/14 (79%) | 9/14 (64%) | 2/14 (14%) | 0.615 |
| item_tricky | 11 | 11/11 (100%) | 11/11 (100%) | 11/11 (100%) | 0/11 (0%) | 1.0 |
| no_evidence | 7 | 6/7 (86%) | 6/7 (86%) | – | 0/7 (0%) | None |
| out_of_scope | 3 | 3/3 (100%) | 3/3 (100%) | – | 0/3 (0%) | None |
| schedule | 11 | 11/11 (100%) | 11/11 (100%) | – | 0/11 (0%) | None |

## By language

| | Cases | Correct | Behaviour | Bin | False answers | Recall@5 |
|---|---|---|---|---|---|---|
| en | 25 | 18/25 (72%) | 19/25 (76%) | 13/19 (68%) | 1/25 (4%) | 0.833 |
| ko | 22 | 21/22 (96%) | 21/22 (96%) | 11/12 (92%) | 0/22 (0%) | 1.0 |
| ru | 6 | 5/6 (83%) | 5/6 (83%) | 2/3 (67%) | 0/6 (0%) | 0.667 |
| uz | 7 | 5/7 (71%) | 6/7 (86%) | 2/4 (50%) | 1/7 (14%) | 0.5 |
| vi | 4 | 2/4 (50%) | 2/4 (50%) | 1/3 (33%) | 0/4 (0%) | 0.667 |
| zh | 6 | 5/6 (83%) | 6/6 (100%) | 3/4 (75%) | 1/6 (17%) | 1.0 |

## Earliest failed stage (slice × stage)

| Slice | gate | generation | other | retrieval | router |
|---|---|---|---|---|---|
| conflict |  | 4 |  | 2 |  |
| false_premise | 1 | 1 |  |  |  |
| item_direct |  |  |  | 4 | 1 |
| no_evidence |  |  | 1 |  |  |

## Latency by stage (median s)

generate_s 13.114 · rerank_s 2.771 · retrieve_s 0.177 · route_s 6.781 · schedule_s 0.0 · schedule_text_s 0.0 · total_s 21.176

## Failed cases

| Case | Slice | Lang | Expected | Got | Bin | Stage |
|---|---|---|---|---|---|---|
| h21 | conflict | en | answer | INSUFFICIENT_CONTEXT |  | generation |
| h22 | conflict | ko | answer | INSUFFICIENT_CONTEXT |  | generation |
| h23 | conflict | ru | answer | INSUFFICIENT_CONTEXT |  | retrieval |
| h24 | conflict | uz | answer | INSUFFICIENT_CONTEXT |  | retrieval |
| h26 | conflict | zh | answer | ANSWER | 종량제봉투 | generation |
| h28 | conflict | vi | answer | INSUFFICIENT_CONTEXT |  | generation |
| h31 | false_premise | en | answer | INSUFFICIENT_CONTEXT |  | gate |
| h33 | false_premise | en | answer | INSUFFICIENT_CONTEXT |  | generation |
| h46 | no_evidence | en | abstain | CLARIFY |  | other |
| item06 | item_direct | en | answer | OUT_OF_SCOPE |  | router |
| item08 | item_direct | uz | answer | ANSWER | 전용함 | retrieval |
| item10 | item_direct | en | answer | ANSWER | 종량제봉투 | retrieval |
| item13 | item_direct | en | answer | INSUFFICIENT_CONTEXT |  | retrieval |
| item16 | item_direct | vi | answer | INSUFFICIENT_CONTEXT |  | retrieval |
