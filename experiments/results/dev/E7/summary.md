# E7: Is the answer stable across sampling?

Cases `eval/cases/dev.jsonl` (20, sha256 `5a62a1c6b684`), commit `cf047ff` (uncommitted changes). Reference variant: `temperature=0.0-seed=1`.

| Variant | Correct | False answers | Bin | Behaviour | Abstain ok | Clarify ok | Cites gold | Cit. precision | Language ok | JSON valid | Downgraded | Item withheld | Median s |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| temperature=0.0-seed=1 | 12/20 (60%) | 1/20 (5%) | 12/20 (60%) | 13/20 (65%) | – | – | 11/13 (85%) | 0.7 | 13/13 (100%) | 17/18 (94%) | 5 | 0 | 25.1 |
| temperature=0.0-seed=2 | 12/20 (60%) | 1/20 (5%) | 12/20 (60%) | 13/20 (65%) | – | – | 11/13 (85%) | 0.7 | 13/13 (100%) | 17/18 (94%) | 5 | 0 | 25.29 |
| temperature=0.0-seed=3 | 12/20 (60%) | 1/20 (5%) | 12/20 (60%) | 13/20 (65%) | – | – | 11/13 (85%) | 0.7 | 13/13 (100%) | 17/18 (94%) | 5 | 0 | 25.3 |
| temperature=0.0-seed=4 | 12/20 (60%) | 1/20 (5%) | 12/20 (60%) | 13/20 (65%) | – | – | 11/13 (85%) | 0.7 | 13/13 (100%) | 17/18 (94%) | 5 | 0 | 25.31 |
| temperature=0.0-seed=5 | 12/20 (60%) | 1/20 (5%) | 12/20 (60%) | 13/20 (65%) | – | – | 11/13 (85%) | 0.7 | 13/13 (100%) | 17/18 (94%) | 5 | 0 | 25.33 |
| temperature=0.7-seed=1 | 8/20 (40%) | 4/20 (20%) | 8/20 (40%) | 12/20 (60%) | – | – | 10/12 (83%) | 0.653 | 11/12 (92%) | 19/19 (100%) | 7 | 0 | 24.79 |
| temperature=0.7-seed=2 | 8/20 (40%) | 4/20 (20%) | 8/20 (40%) | 12/20 (60%) | – | – | 11/12 (92%) | 0.722 | 12/12 (100%) | 18/18 (100%) | 5 | 0 | 25.6 |
| temperature=0.7-seed=3 | 11/20 (55%) | 1/20 (5%) | 11/20 (55%) | 12/20 (60%) | – | – | 9/12 (75%) | 0.611 | 11/12 (92%) | 18/18 (100%) | 6 | 0 | 24.89 |
| temperature=0.7-seed=4 | 6/20 (30%) | 3/20 (15%) | 6/20 (30%) | 9/20 (45%) | – | – | 8/9 (89%) | 0.704 | 9/9 (100%) | 17/17 (100%) | 8 | 0 | 25.96 |
| temperature=0.7-seed=5 | 7/20 (35%) | 3/20 (15%) | 7/20 (35%) | 10/20 (50%) | – | – | 6/10 (60%) | 0.48 | 10/10 (100%) | 16/16 (100%) | 6 | 0 | 25.46 |
| temperature=1.0-seed=1 | 8/20 (40%) | 2/20 (10%) | 8/20 (40%) | 10/20 (50%) | – | – | 8/10 (80%) | 0.667 | 9/10 (90%) | 17/17 (100%) | 7 | 0 | 26.08 |
| temperature=1.0-seed=2 | 8/20 (40%) | 2/20 (10%) | 8/20 (40%) | 10/20 (50%) | – | – | 9/10 (90%) | 0.6 | 9/10 (90%) | 18/18 (100%) | 7 | 0 | 24.82 |
| temperature=1.0-seed=3 | 9/20 (45%) | 5/20 (25%) | 9/20 (45%) | 14/20 (70%) | – | – | 9/14 (64%) | 0.543 | 14/14 (100%) | 18/18 (100%) | 4 | 0 | 25.12 |
| temperature=1.0-seed=4 | 8/20 (40%) | 6/20 (30%) | 8/20 (40%) | 14/20 (70%) | – | – | 9/14 (64%) | 0.429 | 14/14 (100%) | 17/17 (100%) | 3 | 0 | 26.01 |
| temperature=1.0-seed=5 | 9/20 (45%) | 6/20 (30%) | 9/20 (45%) | 15/20 (75%) | – | – | 8/15 (53%) | 0.461 | 15/15 (100%) | 18/18 (100%) | 3 | 0 | 26.02 |

Correct by slice:

| Variant | conflict | false_premise | item_tricky |
|---|---|---|---|
| temperature=0.0-seed=1 | 0/6 (0%) | 1/3 (33%) | 11/11 (100%) |
| temperature=0.0-seed=2 | 0/6 (0%) | 1/3 (33%) | 11/11 (100%) |
| temperature=0.0-seed=3 | 0/6 (0%) | 1/3 (33%) | 11/11 (100%) |
| temperature=0.0-seed=4 | 0/6 (0%) | 1/3 (33%) | 11/11 (100%) |
| temperature=0.0-seed=5 | 0/6 (0%) | 1/3 (33%) | 11/11 (100%) |
| temperature=0.7-seed=1 | 0/6 (0%) | 1/3 (33%) | 7/11 (64%) |
| temperature=0.7-seed=2 | 1/6 (17%) | 1/3 (33%) | 6/11 (55%) |
| temperature=0.7-seed=3 | 1/6 (17%) | 1/3 (33%) | 9/11 (82%) |
| temperature=0.7-seed=4 | 0/6 (0%) | 1/3 (33%) | 5/11 (46%) |
| temperature=0.7-seed=5 | 0/6 (0%) | 1/3 (33%) | 6/11 (55%) |
| temperature=1.0-seed=1 | 1/6 (17%) | 1/3 (33%) | 6/11 (55%) |
| temperature=1.0-seed=2 | 0/6 (0%) | 1/3 (33%) | 7/11 (64%) |
| temperature=1.0-seed=3 | 0/6 (0%) | 1/3 (33%) | 8/11 (73%) |
| temperature=1.0-seed=4 | 1/6 (17%) | 1/3 (33%) | 6/11 (55%) |
| temperature=1.0-seed=5 | 1/6 (17%) | 1/3 (33%) | 7/11 (64%) |

Stability across seeds (a case agrees when every seed gives the same status and bin; a flip is a case answered under some seeds and not under others):

| Temperature | Seeds | Cases | Same status and bin | Abstention flips | Bin changes among answers |
|---|---|---|---|---|---|
| 0.0 | 5 | 20 | 20/20 | 0/20 | 0/20 |
| 0.7 | 5 | 20 | 8/20 | 11/20 | 2/20 |
| 1.0 | 5 | 20 | 6/20 | 12/20 | 4/20 |

## Changes against `temperature=0.0-seed=1`

- `temperature=0.0-seed=2`: worse on 0 (–); better on 0 (–)
- `temperature=0.0-seed=3`: worse on 0 (–); better on 0 (–)
- `temperature=0.0-seed=4`: worse on 0 (–); better on 0 (–)
- `temperature=0.0-seed=5`: worse on 0 (–); better on 0 (–)
- `temperature=0.7-seed=1`: worse on 4 (h01, h06, h07, h13); better on 0 (–)
- `temperature=0.7-seed=2`: worse on 5 (h03, h06, h08, h13, h16); better on 1 (h28)
- `temperature=0.7-seed=3`: worse on 2 (h06, h07); better on 1 (h28)
- `temperature=0.7-seed=4`: worse on 6 (h01, h03, h06, h08, h11, h16); better on 0 (–)
- `temperature=0.7-seed=5`: worse on 5 (h03, h06, h07, h08, h13); better on 0 (–)
- `temperature=1.0-seed=1`: worse on 5 (h01, h11, h12, h13, h16); better on 1 (h28)
- `temperature=1.0-seed=2`: worse on 4 (h01, h11, h13, h16); better on 0 (–)
- `temperature=1.0-seed=3`: worse on 3 (h03, h06, h08); better on 0 (–)
- `temperature=1.0-seed=4`: worse on 5 (h01, h06, h07, h08, h13); better on 1 (h28)
- `temperature=1.0-seed=5`: worse on 4 (h06, h07, h08, h13); better on 1 (h28)
