# E4: How should schedule questions be retrieved?

Cases `eval/cases/dev.jsonl` (23, sha256 `5a62a1c6b684`), commit `5e9159e` (uncommitted changes). Reference variant: `structured-lookup`.

| Variant | Correct | False answers | Bin | Behaviour | Abstain ok | Clarify ok | Cites gold | Cit. precision | Language ok | JSON valid | Downgraded | Item withheld | Median s |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| structured-lookup | 23/23 (100%) | 0/23 (0%) | 8/8 (100%) | 23/23 (100%) | – | 4/4 (100%) | 8/8 (100%) | 0.833 | 8/8 (100%) | 8/8 (100%) | 0 | 0 | 0.0 |
| vector | 18/23 (78%) | 4/23 (17%) | 8/8 (100%) | 19/23 (83%) | – | 0/4 (0%) | 8/8 (100%) | 0.833 | 8/8 (100%) | 8/8 (100%) | 0 | 0 | 0.97 |
| postfilter | 19/23 (83%) | 4/23 (17%) | 8/8 (100%) | 19/23 (83%) | – | 0/4 (0%) | 8/8 (100%) | 0.833 | 8/8 (100%) | 8/8 (100%) | 0 | 0 | 0.04 |
| prefilter | 19/23 (83%) | 4/23 (17%) | 8/8 (100%) | 19/23 (83%) | – | 0/4 (0%) | 8/8 (100%) | 0.833 | 8/8 (100%) | 8/8 (100%) | 0 | 0 | 0.09 |

Correct by slice:

| Variant | ambiguous_location | combined | schedule |
|---|---|---|---|
| structured-lookup | 4/4 (100%) | 8/8 (100%) | 11/11 (100%) |
| vector | 0/4 (0%) | 7/8 (88%) | 11/11 (100%) |
| postfilter | 0/4 (0%) | 8/8 (100%) | 11/11 (100%) |
| prefilter | 0/4 (0%) | 8/8 (100%) | 11/11 (100%) |

Schedule rows (counts):

| Variant | cases | answerable | row_found | top_row | only_correct_rows | day_time_match | empty | wrong_place | behaviour_ok |
|---|---|---|---|---|---|---|---|---|---|
| structured-lookup | 19 | 19 | 19 | 18 | 18 | 18 | 0 | 0 | 19 |
| vector | 19 | 19 | 18 | 14 | 0 | 15 | 0 | 8 | 19 |
| postfilter | 19 | 19 | 19 | 15 | 2 | 16 | 0 | 0 | 19 |
| prefilter | 19 | 19 | 19 | 15 | 2 | 16 | 0 | 0 | 19 |

## Changes against `structured-lookup`

- `vector`: worse on 5 (h51, h52, h55, h56, h75); better on 0 (–)
- `postfilter`: worse on 4 (h51, h52, h55, h56); better on 0 (–)
- `prefilter`: worse on 4 (h51, h52, h55, h56); better on 0 (–)
