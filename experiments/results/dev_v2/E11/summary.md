# E11: Does one router entry and one search per item (router v2) help?

Cases `eval/cases/v2/dev.jsonl` (151, sha256 `cfd5b83f8b03`), commit `dc31aaf` (uncommitted changes). Reference variant: `v2-items`.

| Variant | Correct | False answers | Bin | Behaviour | Abstain ok | Clarify ok | Cites gold | Cit. precision | Language ok | JSON valid | Downgraded | Item withheld | Median s |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| v1-one-item | 116/151 (77%) | 5/151 (3%) | 77/104 (74%) | 128/151 (85%) | 23/24 (96%) | 7/7 (100%) | 76/81 (94%) | – | 82/85 (96%) | 112/113 (99%) | 14 | 1 | 7.39 |
| v2-items | 119/151 (79%) | 6/151 (4%) | 80/104 (77%) | 132/151 (87%) | 23/24 (96%) | 7/7 (100%) | 79/84 (94%) | – | 83/87 (95%) | 112/113 (99%) | 10 | 2 | 7.67 |

Correct by slice:

| Variant | ambiguous_location | analogy | bulky | combined | condition | conflict | false_premise | item_direct | item_tricky | multi_item | natural_phrasing | no_evidence | out_of_scope | schedule | vague_item |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| v1-one-item | 7/7 (100%) | 8/11 (73%) | 4/7 (57%) | 7/10 (70%) | 7/10 (70%) | 5/10 (50%) | 6/8 (75%) | 15/17 (88%) | 12/14 (86%) | 5/8 (62%) | 7/10 (70%) | 9/10 (90%) | 7/7 (100%) | 15/15 (100%) | 2/7 (29%) |
| v2-items | 7/7 (100%) | 8/11 (73%) | 4/7 (57%) | 6/10 (60%) | 7/10 (70%) | 6/10 (60%) | 7/8 (88%) | 15/17 (88%) | 13/14 (93%) | 6/8 (75%) | 7/10 (70%) | 9/10 (90%) | 7/7 (100%) | 15/15 (100%) | 2/7 (29%) |

## Changes against `v2-items`

- `v1-one-item`: worse on 5 (f03, k01, m02, m10, t10); better on 2 (b02, m09)
