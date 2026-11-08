# E8: Does the conflict policy matter?

Cases `eval/cases/dev.jsonl` (70, sha256 `5a62a1c6b684`), commit `5e9159e` (uncommitted changes). Reference variant: `prefer-2026`.

| Variant | Correct | False answers | Bin | Behaviour | Abstain ok | Clarify ok | Cites gold | Cit. precision | Language ok | JSON valid | Downgraded | Item withheld | Median s |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| prefer-2026 | 56/70 (80%) | 3/70 (4%) | 32/45 (71%) | 59/70 (84%) | 9/10 (90%) | 4/4 (100%) | 30/35 (86%) | 0.712 | 34/35 (97%) | 41/42 (98%) | 5 | 0 | 4.83 |
| no-year-preference | 57/70 (81%) | 4/70 (6%) | 33/45 (73%) | 61/70 (87%) | 9/10 (90%) | 4/4 (100%) | 31/37 (84%) | 0.677 | 37/37 (100%) | 42/42 (100%) | 3 | 0 | 15.08 |

Correct by slice:

| Variant | ambiguous_location | combined | conflict | false_premise | item_direct | item_tricky | no_evidence | out_of_scope | schedule |
|---|---|---|---|---|---|---|---|---|---|
| prefer-2026 | 4/4 (100%) | 8/8 (100%) | 0/6 (0%) | 4/6 (67%) | 9/14 (64%) | 11/11 (100%) | 6/7 (86%) | 3/3 (100%) | 11/11 (100%) |
| no-year-preference | 4/4 (100%) | 8/8 (100%) | 1/6 (17%) | 4/6 (67%) | 9/14 (64%) | 11/11 (100%) | 6/7 (86%) | 3/3 (100%) | 11/11 (100%) |

## Changes against `prefer-2026`

- `no-year-preference`: worse on 0 (–); better on 1 (h28)
