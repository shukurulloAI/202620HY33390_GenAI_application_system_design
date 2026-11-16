# E1: Does the prompt contract help?

Cases `eval/cases/v2/dev.jsonl` (151, sha256 `cfd5b83f8b03`), commit `dc31aaf` (uncommitted changes). Reference variant: `v6-items`.

| Variant | Correct | False answers | Bin | Behaviour | Abstain ok | Clarify ok | Cites gold | Cit. precision | Language ok | JSON valid | Downgraded | Item withheld | Median s |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| v5-balanced-examples | 121/151 (80%) | 6/151 (4%) | 82/104 (79%) | 136/151 (90%) | 24/24 (100%) | 7/7 (100%) | 82/88 (93%) | – | 84/89 (94%) | 113/113 (100%) | 6 | 1 | 7.59 |
| v6-items | 119/151 (79%) | 6/151 (4%) | 80/104 (77%) | 132/151 (87%) | 23/24 (96%) | 7/7 (100%) | 79/84 (94%) | – | 83/87 (95%) | 112/113 (99%) | 10 | 2 | 7.67 |

Correct by slice:

| Variant | ambiguous_location | analogy | bulky | combined | condition | conflict | false_premise | item_direct | item_tricky | multi_item | natural_phrasing | no_evidence | out_of_scope | schedule | vague_item |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| v5-balanced-examples | 7/7 (100%) | 8/11 (73%) | 4/7 (57%) | 7/10 (70%) | 8/10 (80%) | 5/10 (50%) | 7/8 (88%) | 14/17 (82%) | 13/14 (93%) | 7/8 (88%) | 7/10 (70%) | 10/10 (100%) | 7/7 (100%) | 15/15 (100%) | 2/7 (29%) |
| v6-items | 7/7 (100%) | 8/11 (73%) | 4/7 (57%) | 6/10 (60%) | 7/10 (70%) | 6/10 (60%) | 7/8 (88%) | 15/17 (88%) | 13/14 (93%) | 6/8 (75%) | 7/10 (70%) | 9/10 (90%) | 7/7 (100%) | 15/15 (100%) | 2/7 (29%) |

## Changes against `v6-items`

- `v5-balanced-examples`: worse on 3 (d07, k14, m10); better on 5 (b02, c07, m09, m12, n06)
