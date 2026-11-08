# E1: Does the prompt contract help?

Cases `eval/cases/dev.jsonl` (70, sha256 `5a62a1c6b684`), commit `5e9159e` (uncommitted changes). Reference variant: `v2-few-shot-contract`.

| Variant | Correct | False answers | Bin | Behaviour | Abstain ok | Clarify ok | Cites gold | Cit. precision | Language ok | JSON valid | Downgraded | Item withheld | Median s |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| v0-minimal | 32/70 (46%) | 2/70 (3%) | 8/45 (18%) | 41/70 (59%) | 9/10 (90%) | 4/4 (100%) | 8/10 (80%) | 0.65 | 16/17 (94%) | 40/40 (100%) | 6 | 7 | 11.32 |
| v1-zero-shot-contract | 48/70 (69%) | 4/70 (6%) | 24/45 (53%) | 53/70 (76%) | 9/10 (90%) | 4/4 (100%) | 24/29 (83%) | 0.736 | 28/29 (97%) | 40/40 (100%) | 5 | 1 | 11.94 |
| v2-few-shot-contract | 51/70 (73%) | 4/70 (6%) | 27/45 (60%) | 56/70 (80%) | 9/10 (90%) | 4/4 (100%) | 24/31 (77%) | 0.622 | 32/32 (100%) | 40/40 (100%) | 7 | 1 | 4.67 |
| v3-few-shot-no-leak | 49/70 (70%) | 5/70 (7%) | 25/45 (56%) | 55/70 (79%) | 9/10 (90%) | 4/4 (100%) | 25/30 (83%) | 0.683 | 31/31 (100%) | 40/40 (100%) | 9 | 1 | 13.42 |
| v4-premise-rule | 51/70 (73%) | 2/70 (3%) | 27/45 (60%) | 54/70 (77%) | 9/10 (90%) | 4/4 (100%) | 26/29 (90%) | 0.761 | 30/30 (100%) | 40/40 (100%) | 10 | 1 | 4.66 |
| v5-balanced-examples | 54/70 (77%) | 3/70 (4%) | 30/45 (67%) | 57/70 (81%) | 9/10 (90%) | 4/4 (100%) | 28/33 (85%) | 0.71 | 32/33 (97%) | 39/40 (98%) | 5 | 0 | 13.3 |

Correct by slice:

| Variant | ambiguous_location | combined | conflict | false_premise | item_direct | item_tricky | no_evidence | out_of_scope | schedule |
|---|---|---|---|---|---|---|---|---|---|
| v0-minimal | 4/4 (100%) | 1/8 (12%) | 1/6 (17%) | 0/6 (0%) | 2/14 (14%) | 4/11 (36%) | 6/7 (86%) | 3/3 (100%) | 11/11 (100%) |
| v1-zero-shot-contract | 4/4 (100%) | 8/8 (100%) | 1/6 (17%) | 2/6 (33%) | 8/14 (57%) | 5/11 (46%) | 6/7 (86%) | 3/3 (100%) | 11/11 (100%) |
| v2-few-shot-contract | 4/4 (100%) | 7/8 (88%) | 0/6 (0%) | 3/6 (50%) | 8/14 (57%) | 9/11 (82%) | 6/7 (86%) | 3/3 (100%) | 11/11 (100%) |
| v3-few-shot-no-leak | 4/4 (100%) | 7/8 (88%) | 0/6 (0%) | 3/6 (50%) | 8/14 (57%) | 7/11 (64%) | 6/7 (86%) | 3/3 (100%) | 11/11 (100%) |
| v4-premise-rule | 4/4 (100%) | 7/8 (88%) | 0/6 (0%) | 3/6 (50%) | 7/14 (50%) | 10/11 (91%) | 6/7 (86%) | 3/3 (100%) | 11/11 (100%) |
| v5-balanced-examples | 4/4 (100%) | 8/8 (100%) | 0/6 (0%) | 4/6 (67%) | 8/14 (57%) | 10/11 (91%) | 6/7 (86%) | 3/3 (100%) | 11/11 (100%) |

## Changes against `v2-few-shot-contract`

- `v0-minimal`: worse on 20 (h01, h02, h06, h07, h16, h32, h34, h35, h72, h74, h75, h77, h79, h81, item02, item03, item11, item17, item18, item20); better on 1 (h22)
- `v1-zero-shot-contract`: worse on 5 (h06, h07, h11, h16, h34); better on 2 (h28, h73)
- `v3-few-shot-no-leak`: worse on 3 (h01, h06, h79); better on 1 (h73)
- `v4-premise-rule`: worse on 2 (h79, item09); better on 2 (h03, h73)
- `v5-balanced-examples`: worse on 0 (–); better on 3 (h03, h37, h73)
