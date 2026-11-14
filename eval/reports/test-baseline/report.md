# Evaluation: test-baseline

Cases: `eval/cases/test.jsonl` (30 cases, sha256 `c3be328d06ca`), commit `cf047ff` (uncommitted changes), 2026-11-09T00:57:07.

## Overall

| Metric | Value |
|---|---|
| Case correct | 11/30 (37%), 95% CI 22%–54% |
| Expected behaviour (answer / abstain / clarify / out of scope) | 20/30 (67%), 95% CI 49%–81% |
| Bin correct (answerable item cases) | 5/19 (26%), 95% CI 12%–49% |
| **False answers** (answered when it should not, or wrong bin) | 4/30 (13%), 95% CI 5%–30% |
| Abstained when it should | 3/5 (60%) |
| Asked back when it should | 0/2 (0%) |
| Gold schedule row shown | 7/8 (88%) |
| Only gold rows shown | 7/8 (88%) |
| Router intent | – |
| Router district / dong (place only in the question) | – / – |
| Retrieval Recall@5 / Hit@5 / MRR / nDCG@5 / P@5 (n=19) | 0.36 / 0.526 / 0.393 / 0.319 / 0.168 |
| Gate TP / FP / FN / TN (n=30) | 19 / 11 / 0 / 0 (FP rate 1.0, FN rate 0.0) |
| Cites a gold chunk (answers citing an item chunk) | 8/13 (62%) |
| Citation precision (cited claims supported by their cited sources, judge) | 15/21 (71%) |
| Citation coverage (all claims supported by their own citations, judge) | 15/35 (43%) |
| Answer in the asked language (script) | 18/18 (100%) |
| JSON valid | 30/30 (100%) |
| Downgraded by validation | 0 |
| Item part withheld, schedule only (not a false answer) | 5 |
| Contract problems | 0 |
| Latency mean / median / p90 (s) | 9.61 / 9.39 / 11.93 |

## By slice

| | Cases | Correct | Behaviour | Bin | False answers | Recall@5 |
|---|---|---|---|---|---|---|
| ambiguous_location | 2 | 0/2 (0%) | 0/2 (0%) | – | 1/2 (50%) | None |
| combined | 4 | 1/4 (25%) | 4/4 (100%) | 2/4 (50%) | 0/4 (0%) | 0.667 |
| conflict | 2 | 1/2 (50%) | 2/2 (100%) | 1/2 (50%) | 1/2 (50%) | 0.25 |
| false_premise | 2 | 0/2 (0%) | 0/2 (0%) | 0/2 (0%) | 0/2 (0%) | 0.5 |
| item_direct | 6 | 0/6 (0%) | 4/6 (67%) | 0/6 (0%) | 2/6 (33%) | 0.111 |
| item_tricky | 5 | 2/5 (40%) | 3/5 (60%) | 2/5 (40%) | 0/5 (0%) | 0.4 |
| no_evidence | 3 | 3/3 (100%) | 3/3 (100%) | – | 0/3 (0%) | None |
| out_of_scope | 2 | 0/2 (0%) | 0/2 (0%) | – | 0/2 (0%) | None |
| schedule | 4 | 4/4 (100%) | 4/4 (100%) | – | 0/4 (0%) | None |

## By language

| | Cases | Correct | Behaviour | Bin | False answers | Recall@5 |
|---|---|---|---|---|---|---|
| en | 15 | 7/15 (47%) | 11/15 (73%) | 3/9 (33%) | 2/15 (13%) | 0.315 |
| ko | 8 | 2/8 (25%) | 6/8 (75%) | 1/5 (20%) | 1/8 (12%) | 0.667 |
| ru | 2 | 0/2 (0%) | 0/2 (0%) | 0/2 (0%) | 0/2 (0%) | 0.0 |
| vi | 3 | 1/3 (33%) | 2/3 (67%) | 0/2 (0%) | 0/3 (0%) | 0.0 |
| zh | 2 | 1/2 (50%) | 1/2 (50%) | 1/1 (100%) | 1/2 (50%) | 0.667 |

## Earliest failed stage (slice × stage)

| Slice | gate | generation | retrieval | schedule_tool |
|---|---|---|---|---|
| ambiguous_location | 2 |  |  |  |
| combined |  | 1 | 1 | 1 |
| conflict |  |  | 1 |  |
| false_premise |  | 1 | 1 |  |
| item_direct |  | 2 | 4 |  |
| item_tricky |  | 1 | 2 |  |
| out_of_scope | 2 |  |  |  |

## Latency by stage (median s)

generate_s 9.329 · retrieve_s 0.061 · route_s 0.0 · schedule_s 0.0 · total_s 9.394
