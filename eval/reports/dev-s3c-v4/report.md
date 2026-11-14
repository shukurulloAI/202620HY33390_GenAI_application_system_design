# Evaluation: dev-s3c-v4

Cases: `eval/cases/dev.jsonl` (70 cases, sha256 `5a62a1c6b684`), commit `3a4d287` (uncommitted changes), 2026-11-08T22:39:37.

## Overall

| Metric | Value |
|---|---|
| Case correct | 51/70 (73%), 95% CI 61%–82% |
| Expected behaviour (answer / abstain / clarify / out of scope) | 54/70 (77%), 95% CI 66%–85% |
| Bin correct (answerable item cases) | 27/45 (60%), 95% CI 45%–73% |
| **False answers** (answered when it should not, or wrong bin) | 2/70 (3%), 95% CI 1%–10% |
| Abstained when it should | 9/10 (90%) |
| Asked back when it should | 4/4 (100%) |
| Gold schedule row shown | 19/19 (100%) |
| Only gold rows shown | 18/19 (95%) |
| Router intent | 62/63 (98%) |
| Router district / dong (place only in the question) | 4/4 (100%) / 3/4 (75%) |
| Retrieval Recall@5 / Hit@5 / MRR / nDCG@5 / P@5 (n=44) | 0.672 / 0.841 / 0.73 / 0.646 / 0.282 |
| Gate TP / FP / FN / TN (n=46) | 39 / 0 / 5 / 2 (FP rate 0.0, FN rate 0.114) |
| Cites a gold chunk (answers citing an item chunk) | 26/29 (90%) |
| Citation precision (cited claims supported by their cited sources, judge) | 27/30 (90%) |
| Citation coverage (all claims supported by their own citations, judge) | 27/40 (68%) |
| Answer in the asked language (script) | 30/30 (100%) |
| JSON valid | 40/40 (100%) |
| Downgraded by validation | 10 |
| Item part withheld, schedule only (not a false answer) | 1 |
| Contract problems | 0 |
| Latency mean / median / p90 (s) | 4.41 / 4.7 / 8.26 (not valid: some LLM replies were replayed from the cache) |

## By slice

| | Cases | Correct | Behaviour | Bin | False answers | Recall@5 |
|---|---|---|---|---|---|---|
| ambiguous_location | 4 | 4/4 (100%) | 4/4 (100%) | – | 0/4 (0%) | None |
| combined | 8 | 7/8 (88%) | 8/8 (100%) | 7/8 (88%) | 0/8 (0%) | 0.802 |
| conflict | 6 | 0/6 (0%) | 1/6 (17%) | 0/6 (0%) | 1/6 (17%) | 0.5 |
| false_premise | 6 | 3/6 (50%) | 3/6 (50%) | 3/6 (50%) | 0/6 (0%) | 0.856 |
| item_direct | 14 | 7/14 (50%) | 8/14 (57%) | 7/14 (50%) | 1/14 (7%) | 0.41 |
| item_tricky | 11 | 10/11 (91%) | 10/11 (91%) | 10/11 (91%) | 0/11 (0%) | 0.879 |
| no_evidence | 7 | 6/7 (86%) | 6/7 (86%) | – | 0/7 (0%) | None |
| out_of_scope | 3 | 3/3 (100%) | 3/3 (100%) | – | 0/3 (0%) | None |
| schedule | 11 | 11/11 (100%) | 11/11 (100%) | – | 0/11 (0%) | None |

## By language

| | Cases | Correct | Behaviour | Bin | False answers | Recall@5 |
|---|---|---|---|---|---|---|
| en | 25 | 17/25 (68%) | 18/25 (72%) | 12/19 (63%) | 1/25 (4%) | 0.637 |
| ko | 22 | 21/22 (96%) | 21/22 (96%) | 11/12 (92%) | 0/22 (0%) | 0.812 |
| ru | 6 | 3/6 (50%) | 4/6 (67%) | 0/3 (0%) | 0/6 (0%) | 0.667 |
| uz | 7 | 3/7 (43%) | 3/7 (43%) | 0/4 (0%) | 0/7 (0%) | 0.333 |
| vi | 4 | 2/4 (50%) | 2/4 (50%) | 1/3 (33%) | 0/4 (0%) | 0.5 |
| zh | 6 | 5/6 (83%) | 6/6 (100%) | 3/4 (75%) | 1/6 (17%) | 0.875 |

## Earliest failed stage (slice × stage)

| Slice | gate | generation | other | retrieval | router |
|---|---|---|---|---|---|
| combined | 1 |  |  |  |  |
| conflict |  | 4 |  | 2 |  |
| false_premise | 1 | 2 |  |  |  |
| item_direct | 1 |  |  | 5 | 1 |
| item_tricky | 1 |  |  |  |  |
| no_evidence |  |  | 1 |  |  |

## Latency by stage (median s)

generate_s 0.001 · rerank_s 6.804 · retrieve_s 0.188 · route_s 0.0 · schedule_s 0.0 · schedule_text_s 0.0 · total_s 4.699

## Failed cases

| Case | Slice | Lang | Expected | Got | Bin | Stage |
|---|---|---|---|---|---|---|
| h08 | item_tricky | uz | answer | INSUFFICIENT_CONTEXT |  | gate |
| h21 | conflict | en | answer | INSUFFICIENT_CONTEXT |  | generation |
| h22 | conflict | ko | answer | INSUFFICIENT_CONTEXT |  | generation |
| h23 | conflict | ru | answer | INSUFFICIENT_CONTEXT |  | retrieval |
| h24 | conflict | uz | answer | INSUFFICIENT_CONTEXT |  | retrieval |
| h26 | conflict | zh | answer | ANSWER | 종량제봉투 | generation |
| h28 | conflict | vi | answer | INSUFFICIENT_CONTEXT |  | generation |
| h31 | false_premise | en | answer | INSUFFICIENT_CONTEXT |  | gate |
| h33 | false_premise | en | answer | INSUFFICIENT_CONTEXT |  | generation |
| h37 | false_premise | ru | answer | INSUFFICIENT_CONTEXT |  | generation |
| h46 | no_evidence | en | abstain | CLARIFY |  | other |
| h79 | combined | ru | answer | ANSWER |  | gate |
| item06 | item_direct | en | answer | OUT_OF_SCOPE |  | router |
| item08 | item_direct | uz | answer | INSUFFICIENT_CONTEXT |  | retrieval |
| item09 | item_direct | en | answer | INSUFFICIENT_CONTEXT |  | retrieval |
| item10 | item_direct | en | answer | ANSWER | 종량제봉투 | retrieval |
| item13 | item_direct | en | answer | INSUFFICIENT_CONTEXT |  | retrieval |
| item14 | item_direct | uz | answer | INSUFFICIENT_CONTEXT |  | gate |
| item16 | item_direct | vi | answer | INSUFFICIENT_CONTEXT |  | retrieval |
