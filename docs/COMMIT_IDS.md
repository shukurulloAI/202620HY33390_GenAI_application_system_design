# Commit IDs before and after 2026-11-09

On 2026-11-09 the commit messages on the `shukurullo` branch were edited: one trailer line was
removed from 16 messages. Two more commits (`77790b7`, `da82337`) have new IDs only because their
parent changed. Nothing else changed: every commit has the same file tree, author and dates as before
(checked when the history was rewritten).

Run records written before that date store the old IDs. These are `eval/reports/*/report.json` and
`report.md`, and `experiments/results/**/manifest.json`, `summary.md` and the probe files. They were
left as recorded. Use this table to find the current commit.

| Old ID | Current ID | Commit |
|---|---|---|
| `3f4936b` | `7f4e8f5` | Stages 4-6: the single test run, stress tests, final report and slides |
| `cf047ff` | `f0faba6` | Stage 3: freeze the configuration (prompt v5, router repair) before the test run |
| `5e9159e` | `6550f00` | Stage 3: measure the fixes on dev; connect the website (Stage 6) |
| `3a4d287` | `48edb0a` | Stage 3 (in progress): fixes from the dev failure analysis, not yet measured |
| `2d7b521` | `d4e0b16` | Add the evaluation runner and metrics, with baseline and full-system numbers on dev |
| `375e7d2` | `19f079d` | Add the evaluation set v1 and freeze its dev/test split before tuning |
| `359a1d8` | `3442ed9` | Make the system website-ready: answer contract, service module, six languages |
| `aceeac8` | `b92f855` | Merge branch 'naura': Streamlit website prototype on mock answers |
| `4cb7080` | `a639207` | Merge branch 'vitou': EDA README and split_dongs/province fixes |
| `5fff49e` | `9342add` | Keep broken Korean out of the handoff sentence; add model guide |
| `da82337` | `289c972` | completed model |
| `aee2366` | `d27b76c` | Add final E4 results and rewrite Phase 2 notes |
| `27ff6a4` | `09179b4` | Send Vietnamese and Russian schedule method text to English |
| `77790b7` | `369c4e8` | updated |
| `d492c1e` | `3f51463` | Add E4 vector variants; write schedule answers in code |
| `9572515` | `6468631` | Add Phase 2 experiment results and notes |
| `fa50916` | `e8bc797` | Add Phase 2 pipeline: router, hybrid retrieval, gate, validation |
| `ccb7f6a` | `12a452e` | Add preprocessing: schedule table, lookups, glossary, item chunks |
