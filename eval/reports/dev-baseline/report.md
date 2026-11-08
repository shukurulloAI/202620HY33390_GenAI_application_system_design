# Evaluation: dev-baseline

Cases: `eval/cases/dev.jsonl` (70 cases, sha256 `5a62a1c6b684`), commit `375e7d2` (uncommitted changes), 2026-11-08T18:01:15.

## Overall

| Metric | Value |
|---|---|
| Case correct | 32/70 (46%) |
| Expected behaviour (answer / abstain / clarify / out of scope) | 52/70 (74%) |
| Bin correct (answerable item cases) | 17/45 (38%) |
| **False answers** (answered when it should not, or wrong bin) | 13/70 (19%) |
| Abstained when it should | 6/10 (60%) |
| Asked back when it should | 0/4 (0%) |
| Gold schedule row shown | 14/19 (74%) |
| Only gold rows shown | 14/19 (74%) |
| Router intent | – |
| Router district / dong (place only in the question) | – / – |
| Retrieval Recall@5 / MRR / nDCG@5 / P@5 (n=45) | 0.556 / 0.466 / 0.366 / 0.156 |
| Gate TP / FP / FN / TN (n=70) | 45 / 25 / 0 / 0 (FP rate 1.0, FN rate 0.0) |
| Cites a gold chunk / citation precision | 24/34 (71%) / 0.604 |
| Answer in the asked language (script) | 45/49 (92%) |
| JSON valid | 69/70 (99%) |
| Downgraded by validation | 1 |
| Item part withheld, schedule only (not a false answer) | 8 |
| Contract problems | 0 |
| Latency mean / median / p90 (s) | 10.63 / 10.31 / 13.46 |

## By slice

| | Cases | Correct | Behaviour | Bin | False answers | Recall@5 |
|---|---|---|---|---|---|---|
| ambiguous_location | 4 | 0/4 (0%) | 0/4 (0%) | – | 2/4 (50%) | None |
| combined | 8 | 3/8 (38%) | 5/8 (62%) | 5/8 (62%) | 0/8 (0%) | 0.5 |
| conflict | 6 | 0/6 (0%) | 5/6 (83%) | 0/6 (0%) | 4/6 (67%) | 0.167 |
| false_premise | 6 | 2/6 (33%) | 4/6 (67%) | 2/6 (33%) | 2/6 (33%) | 0.667 |
| item_direct | 14 | 5/14 (36%) | 11/14 (79%) | 5/14 (36%) | 1/14 (7%) | 0.571 |
| item_tricky | 11 | 5/11 (46%) | 10/11 (91%) | 5/11 (46%) | 3/11 (27%) | 0.727 |
| no_evidence | 7 | 6/7 (86%) | 6/7 (86%) | – | 1/7 (14%) | None |
| out_of_scope | 3 | 0/3 (0%) | 0/3 (0%) | – | 0/3 (0%) | None |
| schedule | 11 | 11/11 (100%) | 11/11 (100%) | – | 0/11 (0%) | None |

## By language

| | Cases | Correct | Behaviour | Bin | False answers | Recall@5 |
|---|---|---|---|---|---|---|
| en | 25 | 10/25 (40%) | 19/25 (76%) | 6/19 (32%) | 4/25 (16%) | 0.421 |
| ko | 22 | 16/22 (73%) | 21/22 (96%) | 8/12 (67%) | 1/22 (4%) | 1.0 |
| ru | 6 | 1/6 (17%) | 3/6 (50%) | 1/3 (33%) | 4/6 (67%) | 0.333 |
| uz | 7 | 2/7 (29%) | 4/7 (57%) | 0/4 (0%) | 3/7 (43%) | 0.25 |
| vi | 4 | 1/4 (25%) | 2/4 (50%) | 1/3 (33%) | 0/4 (0%) | 0.333 |
| zh | 6 | 2/6 (33%) | 3/6 (50%) | 1/4 (25%) | 1/6 (17%) | 0.5 |

## Earliest failed stage (slice × stage)

| Slice | gate | generation | retrieval | schedule_tool |
|---|---|---|---|---|
| ambiguous_location | 4 |  |  |  |
| combined |  |  | 3 | 2 |
| conflict |  | 1 | 5 |  |
| false_premise |  | 2 | 2 |  |
| item_direct |  | 4 | 5 |  |
| item_tricky |  | 3 | 3 |  |
| no_evidence | 1 |  |  |  |
| out_of_scope | 3 |  |  |  |

## Latency by stage (median s)

generate_s 10.251 · retrieve_s 0.062 · route_s 0.0 · schedule_s 0.0 · total_s 10.311

## Failed cases

| Case | Slice | Lang | Expected | Got | Bin | Stage |
|---|---|---|---|---|---|---|
| h01 | item_tricky | en | answer | ANSWER | 종이 | retrieval |
| h02 | item_tricky | ko | answer | ANSWER |  | generation |
| h03 | item_tricky | en | answer | ANSWER |  | retrieval |
| h07 | item_tricky | en | answer | ANSWER | 음식물 | generation |
| h08 | item_tricky | uz | answer | ANSWER | 종량제봉투 | generation |
| h13 | item_tricky | zh | answer | INSUFFICIENT_CONTEXT |  | retrieval |
| h21 | conflict | en | answer | ANSWER | 종량제봉투 | retrieval |
| h22 | conflict | ko | answer | ANSWER | 플라스틱 | generation |
| h23 | conflict | ru | answer | ANSWER | 플라스틱 | retrieval |
| h24 | conflict | uz | answer | INSUFFICIENT_CONTEXT |  | retrieval |
| h26 | conflict | zh | answer | ANSWER | 종량제봉투 | retrieval |
| h28 | conflict | vi | answer | ANSWER |  | retrieval |
| h31 | false_premise | en | answer | INSUFFICIENT_CONTEXT |  | retrieval |
| h33 | false_premise | en | answer | ANSWER | 종량제봉투 | retrieval |
| h34 | false_premise | zh | answer | INSUFFICIENT_CONTEXT |  | generation |
| h37 | false_premise | ru | answer | ANSWER | 종량제봉투 | generation |
| h48 | no_evidence | ru | abstain | ANSWER |  | gate |
| h51 | ambiguous_location | en | clarify | INSUFFICIENT_CONTEXT |  | gate |
| h52 | ambiguous_location | ko | clarify | INSUFFICIENT_CONTEXT |  | gate |
| h55 | ambiguous_location | uz | clarify | ANSWER |  | gate |
| h56 | ambiguous_location | ru | clarify | ANSWER |  | gate |
| h63 | out_of_scope | zh | out_of_scope | INSUFFICIENT_CONTEXT |  | gate |
| h64 | out_of_scope | vi | out_of_scope | INSUFFICIENT_CONTEXT |  | gate |
| h65 | out_of_scope | ru | out_of_scope | INSUFFICIENT_CONTEXT |  | gate |
| h71 | combined | en | answer | INSUFFICIENT_CONTEXT |  | retrieval |
| h72 | combined | ko | answer | ANSWER | 종이팩 | schedule_tool |
| h73 | combined | en | answer | INSUFFICIENT_CONTEXT |  | retrieval |
| h74 | combined | en | answer | ANSWER | 음식물 | schedule_tool |
| h81 | combined | en | answer | INSUFFICIENT_CONTEXT |  | retrieval |
| item02 | item_direct | ko | answer | ANSWER |  | generation |
| item06 | item_direct | en | answer | ANSWER |  | retrieval |
| item08 | item_direct | uz | answer | ANSWER | 유리병 | retrieval |
| item10 | item_direct | en | answer | INSUFFICIENT_CONTEXT |  | retrieval |
| item13 | item_direct | en | answer | ANSWER |  | generation |
| item14 | item_direct | uz | answer | INSUFFICIENT_CONTEXT |  | retrieval |
| item16 | item_direct | vi | answer | INSUFFICIENT_CONTEXT |  | retrieval |
| item19 | item_direct | en | answer | ANSWER |  | generation |
| item20 | item_direct | ko | answer | ANSWER |  | generation |
