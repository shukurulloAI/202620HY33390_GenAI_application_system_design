# E10: Which local LLM should be the router and the generator?

Cases `eval/cases/v2/dev.jsonl` (151, sha256 `cfd5b83f8b03`), commit `dc31aaf` (uncommitted changes). Reference variant: `gemma4-12b`.

| Variant | Correct | False answers | Bin | Behaviour | Abstain ok | Clarify ok | Cites gold | Cit. precision | Language ok | JSON valid | Downgraded | Item withheld | Median s |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| qwen2.5-7b | 100/151 (66%) | 18/151 (12%) | 64/104 (62%) | 122/151 (81%) | 21/24 (88%) | 7/7 (100%) | 65/78 (83%) | – | 81/81 (100%) | 93/96 (97%) | 9 | 0 | 6.84 |
| gemma3-12b | 112/151 (74%) | 16/151 (11%) | 78/104 (75%) | 130/151 (86%) | 21/24 (88%) | 6/7 (86%) | 80/87 (92%) | – | 78/90 (87%) | 115/115 (100%) | 13 | 0 | 11.12 |
| gemma4-12b | 119/151 (79%) | 6/151 (4%) | 80/104 (77%) | 132/151 (87%) | 23/24 (96%) | 7/7 (100%) | 79/84 (94%) | – | 83/87 (95%) | 112/113 (99%) | 10 | 2 | 7.67 |

Correct by slice:

| Variant | ambiguous_location | analogy | bulky | combined | condition | conflict | false_premise | item_direct | item_tricky | multi_item | natural_phrasing | no_evidence | out_of_scope | schedule | vague_item |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| qwen2.5-7b | 7/7 (100%) | 6/11 (55%) | 4/7 (57%) | 8/10 (80%) | 5/10 (50%) | 6/10 (60%) | 2/8 (25%) | 13/17 (76%) | 7/14 (50%) | 4/8 (50%) | 6/10 (60%) | 9/10 (90%) | 7/7 (100%) | 15/15 (100%) | 1/7 (14%) |
| gemma3-12b | 6/7 (86%) | 7/11 (64%) | 5/7 (71%) | 8/10 (80%) | 7/10 (70%) | 4/10 (40%) | 5/8 (62%) | 16/17 (94%) | 11/14 (79%) | 5/8 (62%) | 8/10 (80%) | 8/10 (80%) | 7/7 (100%) | 15/15 (100%) | 0/7 (0%) |
| gemma4-12b | 7/7 (100%) | 8/11 (73%) | 4/7 (57%) | 6/10 (60%) | 7/10 (70%) | 6/10 (60%) | 7/8 (88%) | 15/17 (88%) | 13/14 (93%) | 6/8 (75%) | 7/10 (70%) | 9/10 (90%) | 7/7 (100%) | 15/15 (100%) | 2/7 (29%) |

## Changes against `gemma4-12b`

- `qwen2.5-7b`: worse on 27 (an05, at04, at07, c01, c02, c09, d07, f01, f03, f07, f11, f12, item05, k01, k03, m03, m04, n11, p05, t02, t08, t10, t11, t18, t20, v09, y05); better on 8 (an01, b02, b10, c07, k04, k05, n06, y06)
- `gemma3-12b`: worse on 18 (a05, at04, c01, c05, d07, f03, f07, k01, k03, m07, m10, n09, n11, p02, t10, t16, v03, v09); better on 11 (b02, b10, c07, c14, item03, item11, m09, n06, p04, p13, y06)
