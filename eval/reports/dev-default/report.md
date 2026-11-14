# Evaluation: dev-default

Cases: `eval/cases/dev.jsonl` (70 cases, sha256 `5a62a1c6b684`), commit `375e7d2` (uncommitted changes), 2026-11-08T18:01:16.

## Overall

| Metric | Value |
|---|---|
| Case correct | 48/70 (69%), 95% CI 57%–78% |
| Expected behaviour (answer / abstain / clarify / out of scope) | 56/70 (80%), 95% CI 69%–88% |
| Bin correct (answerable item cases) | 24/45 (53%), 95% CI 39%–67% |
| **False answers** (answered when it should not, or wrong bin) | 6/70 (9%), 95% CI 4%–17% |
| Abstained when it should | 9/10 (90%) |
| Asked back when it should | 4/4 (100%) |
| Gold schedule row shown | 19/19 (100%) |
| Only gold rows shown | 18/19 (95%) |
| Router intent | 62/63 (98%) |
| Router district / dong (place only in the question) | 4/4 (100%) / 3/4 (75%) |
| Retrieval Recall@5 / Hit@5 / MRR / nDCG@5 / P@5 (n=44) | 0.607 / 0.795 / 0.678 / 0.582 / 0.259 |
| Gate TP / FP / FN / TN (n=46) | 40 / 0 / 4 / 2 (FP rate 0.0, FN rate 0.091) |
| Cites a gold chunk (answers citing an item chunk) | 24/32 (75%) |
| Citation precision (cited claims supported by their cited sources, judge) | 25/36 (69%) |
| Citation coverage (all claims supported by their own citations, judge) | 25/46 (54%) |
| Answer in the asked language (script) | 31/32 (97%) |
| JSON valid | 40/40 (100%) |
| Downgraded by validation | 5 |
| Item part withheld, schedule only (not a false answer) | 2 |
| Contract problems | 0 |
| Latency mean / median / p90 (s) | 15.73 / 20.87 / 26.45 |

## By slice

| | Cases | Correct | Behaviour | Bin | False answers | Recall@5 |
|---|---|---|---|---|---|---|
| ambiguous_location | 4 | 4/4 (100%) | 4/4 (100%) | – | 0/4 (0%) | None |
| combined | 8 | 8/8 (100%) | 8/8 (100%) | 8/8 (100%) | 0/8 (0%) | 0.74 |
| conflict | 6 | 1/6 (17%) | 4/6 (67%) | 1/6 (17%) | 3/6 (50%) | 0.5 |
| false_premise | 6 | 1/6 (17%) | 1/6 (17%) | 1/6 (17%) | 0/6 (0%) | 0.661 |
| item_direct | 14 | 6/14 (43%) | 9/14 (64%) | 6/14 (43%) | 1/14 (7%) | 0.333 |
| item_tricky | 11 | 8/11 (73%) | 10/11 (91%) | 8/11 (73%) | 2/11 (18%) | 0.864 |
| no_evidence | 7 | 6/7 (86%) | 6/7 (86%) | – | 0/7 (0%) | None |
| out_of_scope | 3 | 3/3 (100%) | 3/3 (100%) | – | 0/3 (0%) | None |
| schedule | 11 | 11/11 (100%) | 11/11 (100%) | – | 0/11 (0%) | None |

## By language

| | Cases | Correct | Behaviour | Bin | False answers | Recall@5 |
|---|---|---|---|---|---|---|
| en | 25 | 14/25 (56%) | 17/25 (68%) | 9/19 (47%) | 2/25 (8%) | 0.535 |
| ko | 22 | 20/22 (91%) | 22/22 (100%) | 10/12 (83%) | 1/22 (4%) | 0.812 |
| ru | 6 | 4/6 (67%) | 4/6 (67%) | 1/3 (33%) | 0/6 (0%) | 0.556 |
| uz | 7 | 3/7 (43%) | 5/7 (71%) | 0/4 (0%) | 2/7 (29%) | 0.167 |
| vi | 4 | 3/4 (75%) | 3/4 (75%) | 2/3 (67%) | 0/4 (0%) | 0.5 |
| zh | 6 | 4/6 (67%) | 5/6 (83%) | 2/4 (50%) | 1/6 (17%) | 0.875 |

## Earliest failed stage (slice × stage)

| Slice | gate | generation | other | retrieval | router | validation |
|---|---|---|---|---|---|---|
| conflict |  | 3 |  | 2 |  |  |
| false_premise |  | 3 |  | 1 |  | 1 |
| item_direct |  | 1 |  | 6 | 1 |  |
| item_tricky | 1 | 2 |  |  |  |  |
| no_evidence |  |  | 1 |  |  |  |

## Latency by stage (median s)

generate_s 13.469 · rerank_s 3.355 · retrieve_s 0.109 · route_s 6.752 · schedule_s 0.0 · schedule_text_s 0.0 · total_s 20.867

## Failed cases

| Case | Slice | Lang | Expected | Got | Bin | Stage |
|---|---|---|---|---|---|---|
| h03 | item_tricky | en | answer | ANSWER | 종량제봉투 | generation |
| h07 | item_tricky | en | answer | ANSWER | 음식물 | generation |
| h08 | item_tricky | uz | answer | INSUFFICIENT_CONTEXT |  | gate |
| h21 | conflict | en | answer | INSUFFICIENT_CONTEXT |  | generation |
| h22 | conflict | ko | answer | ANSWER | 플라스틱 | generation |
| h23 | conflict | ru | answer | INSUFFICIENT_CONTEXT |  | retrieval |
| h24 | conflict | uz | answer | ANSWER | 플라스틱 | retrieval |
| h26 | conflict | zh | answer | ANSWER | 종량제봉투 | generation |
| h31 | false_premise | en | answer | INSUFFICIENT_CONTEXT |  | retrieval |
| h33 | false_premise | en | answer | INSUFFICIENT_CONTEXT |  | generation |
| h34 | false_premise | zh | answer | INSUFFICIENT_CONTEXT |  | generation |
| h35 | false_premise | en | answer | INSUFFICIENT_CONTEXT |  | validation |
| h37 | false_premise | ru | answer | INSUFFICIENT_CONTEXT |  | generation |
| h46 | no_evidence | en | abstain | CLARIFY |  | other |
| item06 | item_direct | en | answer | OUT_OF_SCOPE |  | router |
| item08 | item_direct | uz | answer | ANSWER | 전용함 | retrieval |
| item09 | item_direct | en | answer | INSUFFICIENT_CONTEXT |  | retrieval |
| item10 | item_direct | en | answer | ANSWER |  | retrieval |
| item13 | item_direct | en | answer | INSUFFICIENT_CONTEXT |  | retrieval |
| item14 | item_direct | uz | answer | INSUFFICIENT_CONTEXT |  | retrieval |
| item16 | item_direct | vi | answer | INSUFFICIENT_CONTEXT |  | retrieval |
| item20 | item_direct | ko | answer | ANSWER |  | generation |
