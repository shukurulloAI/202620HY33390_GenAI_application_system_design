# v3: fixing the failures that change answers

v2 is the system frozen at `f0faba6` and run once on test (`eval/reports/test-final`). Its main
failures need **data that people review**, not more code (REPORT §9, §11):

| Failure | Evidence | Fix |
|---|---|---|
| The router mistranslates item names (uz, ru, vi, rare items) | 5 of 8 test failures | A reviewed table of item names, Korean ↔ user languages |
| A 2018 entry outranks the 2026 rule for its group | Conflict slice 0/2 test, 0/6 dev; h25 | A reviewed map from 2018 entries to 2026 rules |
| A cited chunk states a bin but is about another item | item08; 12/19 follow a planted chunk | Validation: the cited chunk must name the asked item |

## Order of work

**1. Data first.** People fill the sheets in `data/manual/drafts/`
(`python -m preprocess.review_templates` makes them):
- **`item_names_review.csv`** (322 names). Native speakers fill `zh`, `vi`, `uz`, `ru`, and
  someone fills `en`. Leave a cell empty rather than guess. The common items come first.
- **`category_map_review.csv`** (293 entries from the 2018 guide). Put the 2026 rule that now
  covers each item in `rule_2026` (IDs in `rules_2026.txt`), or `none`. In `same_bin_in_2026`,
  write `y` or `n`. One person fills it and a second checks it.

A reviewed sheet then moves to `data/manual/` (for example as `item_names.json`). The code reads
it, and `stewardship.json` gets an entry for it.

**2. A new held-out set, frozen before any v3 tuning.** About 30 cases, built like this:
- some are written by people who did not build the system;
- some are real questions from international students: the `real_users` slice, empty in v2;
- languages and slices are spread as in v2, with at least 3 Uzbek cases (v2 test has none).

Freeze it with `eval/make_cases.py` (seed and SHA-256 in a manifest) before anyone looks at v3
results. The old test split is no longer held out for v3. The v3 item-name table may contain
names from the v2 test failures, which the report described.

**3. Code changes, one at a time, measured on dev**
(`python -m experiments.run_experiment ... --cases eval/cases/dev.jsonl`):
- router: look the item name up in the table before asking the LLM, and keep the LLM as the
  fallback;
- retrieval: when a 2018 entry is retrieved, add the 2026 rule it maps to;
- validation: refuse an answer whose cited chunk is about another item (`item_match` in
  `rag/gate.py` already computes this);
- gate: use `item_match` in the decision.

Each change is reported on dev with the paired test against the previous step
(`python -m eval.compare`) and the cases it gained or lost.

**4. One run of the frozen v3 on the new held-out set.** It is reported next to v2 on the same
set, with intervals and the paired test. `test-final` stays the v2 result.

## The human audit (independent of v3)

The v2 audit can be done now: see [AUDIT_GUIDE.md](AUDIT_GUIDE.md). It checks the judge that v3
will also use.
