# E12: Should an answer that validation withholds be asked once more?

Cases `eval/cases/v2/dev.jsonl` (151, sha256 `cfd5b83f8b03`), commit `dc31aaf` (uncommitted changes). Reference variant: `rejected`.

| Variant | Correct | False answers | Bin | Behaviour | Abstain ok | Clarify ok | Cites gold | Cit. precision | Language ok | JSON valid | Downgraded | Item withheld | Median s |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| conflict | 111/151 (74%) | 2/151 (1%) | 71/104 (68%) | 122/151 (81%) | 24/24 (100%) | 7/7 (100%) | 69/73 (94%) | – | 71/75 (95%) | 112/113 (99%) | 21 | 2 | 7.6 |
| rejected | 119/151 (79%) | 6/151 (4%) | 80/104 (77%) | 132/151 (87%) | 23/24 (96%) | 7/7 (100%) | 79/84 (94%) | – | 83/87 (95%) | 112/113 (99%) | 10 | 2 | 7.67 |
| condition | 121/151 (80%) | 7/151 (5%) | 82/104 (79%) | 135/151 (89%) | 23/24 (96%) | 7/7 (100%) | 82/87 (94%) | – | 86/90 (96%) | 112/113 (99%) | 7 | 2 | 7.57 |

Correct by slice:

| Variant | ambiguous_location | analogy | bulky | combined | condition | conflict | false_premise | item_direct | item_tricky | multi_item | natural_phrasing | no_evidence | out_of_scope | schedule | vague_item |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| conflict | 7/7 (100%) | 7/11 (64%) | 4/7 (57%) | 6/10 (60%) | 7/10 (70%) | 3/10 (30%) | 6/8 (75%) | 13/17 (76%) | 12/14 (86%) | 6/8 (75%) | 7/10 (70%) | 10/10 (100%) | 7/7 (100%) | 15/15 (100%) | 1/7 (14%) |
| rejected | 7/7 (100%) | 8/11 (73%) | 4/7 (57%) | 6/10 (60%) | 7/10 (70%) | 6/10 (60%) | 7/8 (88%) | 15/17 (88%) | 13/14 (93%) | 6/8 (75%) | 7/10 (70%) | 9/10 (90%) | 7/7 (100%) | 15/15 (100%) | 2/7 (29%) |
| condition | 7/7 (100%) | 8/11 (73%) | 4/7 (57%) | 6/10 (60%) | 8/10 (80%) | 7/10 (70%) | 7/8 (88%) | 14/17 (82%) | 13/14 (93%) | 6/8 (75%) | 8/10 (80%) | 9/10 (90%) | 7/7 (100%) | 15/15 (100%) | 2/7 (29%) |

## Changes against `rejected`

- `conflict`: worse on 9 (an05, d05, d07, f03, k02, k03, k14, t10, v03); better on 1 (n06)
- `condition`: worse on 2 (d05, t10); better on 4 (c04, k08, p06, t17)
