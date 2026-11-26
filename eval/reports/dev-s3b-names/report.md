# Evaluation: dev-s3b-names

Cases: `eval/cases/dev.jsonl` (70 cases, sha256 `5a62a1c6b684`), commit `3a4d287` (uncommitted changes), 2026-11-08T22:34:13.

## Overall

| Metric | Value |
|---|---|
| Case correct | 51/70 (73%), 95% CI 61%–82% |
| Expected behaviour (answer / abstain / clarify / out of scope) | 56/70 (80%), 95% CI 69%–88% |
| Bin correct (answerable item cases) | 27/45 (60%), 95% CI 45%–73% |
| **False answers** (answered when it should not, or wrong bin) | 4/70 (6%), 95% CI 2%–14% |
| Abstained when it should | 9/10 (90%) |
| Asked back when it should | 4/4 (100%) |
| Gold schedule row shown | 19/19 (100%) |
| Only gold rows shown | 18/19 (95%) |
| Router intent | 62/63 (98%) |
| Router district / dong (place only in the question) | 4/4 (100%) / 3/4 (75%) |
| Retrieval Recall@5 / Hit@5 / MRR / nDCG@5 / P@5 (n=44) | 0.672 / 0.841 / 0.73 / 0.646 / 0.282 |
| Gate TP / FP / FN / TN (n=46) | 39 / 0 / 5 / 2 (FP rate 0.0, FN rate 0.114) |
| Cites a gold chunk (answers citing an item chunk) | 24/31 (77%) |
| Citation precision (cited claims supported by their cited sources, judge) | 29/36 (81%) |
| Citation coverage (all claims supported by their own citations, judge) | 29/46 (63%) |
| Answer in the asked language (script) | 32/32 (100%) |
| JSON valid | 40/40 (100%) |
| Downgraded by validation | 7 |
| Item part withheld, schedule only (not a false answer) | 1 |
| Contract problems | 0 |
| Latency mean / median / p90 (s) | 3.6 / 4.63 / 6.84 (not valid: some LLM replies were replayed from the cache) |

## By slice

| | Cases | Correct | Behaviour | Bin | False answers | Recall@5 |
|---|---|---|---|---|---|---|
| ambiguous_location | 4 | 4/4 (100%) | 4/4 (100%) | – | 0/4 (0%) | None |
| combined | 8 | 7/8 (88%) | 8/8 (100%) | 7/8 (88%) | 0/8 (0%) | 0.802 |
| conflict | 6 | 0/6 (0%) | 2/6 (33%) | 0/6 (0%) | 2/6 (33%) | 0.5 |
| false_premise | 6 | 3/6 (50%) | 3/6 (50%) | 3/6 (50%) | 0/6 (0%) | 0.856 |
| item_direct | 14 | 8/14 (57%) | 9/14 (64%) | 8/14 (57%) | 1/14 (7%) | 0.41 |
| item_tricky | 11 | 9/11 (82%) | 10/11 (91%) | 9/11 (82%) | 1/11 (9%) | 0.879 |
| no_evidence | 7 | 6/7 (86%) | 6/7 (86%) | – | 0/7 (0%) | None |
| out_of_scope | 3 | 3/3 (100%) | 3/3 (100%) | – | 0/3 (0%) | None |
| schedule | 11 | 11/11 (100%) | 11/11 (100%) | – | 0/11 (0%) | None |

## By language

| | Cases | Correct | Behaviour | Bin | False answers | Recall@5 |
|---|---|---|---|---|---|---|
| en | 25 | 16/25 (64%) | 18/25 (72%) | 11/19 (58%) | 1/25 (4%) | 0.637 |
| ko | 22 | 21/22 (96%) | 21/22 (96%) | 11/12 (92%) | 0/22 (0%) | 0.812 |
| ru | 6 | 4/6 (67%) | 4/6 (67%) | 1/3 (33%) | 0/6 (0%) | 0.667 |
| uz | 7 | 3/7 (43%) | 5/7 (71%) | 0/4 (0%) | 2/7 (29%) | 0.333 |
| vi | 4 | 2/4 (50%) | 2/4 (50%) | 1/3 (33%) | 0/4 (0%) | 0.5 |
| zh | 6 | 5/6 (83%) | 6/6 (100%) | 3/4 (75%) | 1/6 (17%) | 0.875 |

## Earliest failed stage (slice × stage)

| Slice | gate | generation | other | retrieval | router |
|---|---|---|---|---|---|
| combined | 1 |  |  |  |  |
| conflict |  | 4 |  | 2 |  |
| false_premise | 1 | 2 |  |  |  |
| item_direct | 1 |  |  | 4 | 1 |
| item_tricky | 1 | 1 |  |  |  |
| no_evidence |  |  | 1 |  |  |

## Latency by stage (median s)

generate_s 0.001 · rerank_s 6.353 · retrieve_s 0.111 · route_s 0.0 · schedule_s 0.0 · schedule_text_s 0.0 · total_s 4.633

## Failed cases

| Case | Slice | Lang | Expected | Got | Bin | Stage |
|---|---|---|---|---|---|---|
| h03 | item_tricky | en | answer | ANSWER | 종량제봉투 | generation |
| h08 | item_tricky | uz | answer | INSUFFICIENT_CONTEXT |  | gate |
| h21 | conflict | en | answer | INSUFFICIENT_CONTEXT |  | generation |
| h22 | conflict | ko | answer | INSUFFICIENT_CONTEXT |  | generation |
| h23 | conflict | ru | answer | INSUFFICIENT_CONTEXT |  | retrieval |
| h24 | conflict | uz | answer | ANSWER | 플라스틱 | retrieval |
| h26 | conflict | zh | answer | ANSWER | 종량제봉투 | generation |
| h28 | conflict | vi | answer | INSUFFICIENT_CONTEXT |  | generation |
| h31 | false_premise | en | answer | INSUFFICIENT_CONTEXT |  | gate |
| h33 | false_premise | en | answer | INSUFFICIENT_CONTEXT |  | generation |
| h37 | false_premise | ru | answer | INSUFFICIENT_CONTEXT |  | generation |
| h46 | no_evidence | en | abstain | CLARIFY |  | other |
| h73 | combined | en | answer | ANSWER |  | gate |
| item06 | item_direct | en | answer | OUT_OF_SCOPE |  | router |
| item08 | item_direct | uz | answer | ANSWER | 전용함 | retrieval |
| item10 | item_direct | en | answer | INSUFFICIENT_CONTEXT |  | retrieval |
| item13 | item_direct | en | answer | INSUFFICIENT_CONTEXT |  | retrieval |
| item14 | item_direct | uz | answer | INSUFFICIENT_CONTEXT |  | gate |
| item16 | item_direct | vi | answer | INSUFFICIENT_CONTEXT |  | retrieval |
