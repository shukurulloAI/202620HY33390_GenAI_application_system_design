# Human audit of the test answers: rater guide

The LLM judge (Ragas, exaone3.5:7.8b) scored the 17 test answers that have evidence. Lesson 6:
"an evaluator is a measurement whose errors also need review". This audit measures how often
the judge is wrong, and gives the report a human faithfulness number. It takes about 1.5 hours
per rater.

**Sheets:** `eval/reports/test-final/audit/sheet_rater_A.csv` and `sheet_rater_B.csv`, one per
person. They open in Excel, Numbers or Google Sheets (UTF-8). At least one rater should read
Korean, because most of the evidence is Korean.

## Rules

1. **Work alone.** Do not discuss answers with the other rater until both sheets are done.
2. **Do not look at the judge scores** (`eval/reports/test-final/ragas.json`) or at the report's
   case studies before you finish.
3. **Judge only against the `evidence` column**: the text the system actually read. Do not use
   your own knowledge of Korean waste rules for `supported` and `contradicted`. Use it only for
   `bin_correct`.
4. Don't change any column except `claims`, `supported`, `contradicted`, `bin_correct`, `notes`.

## What to fill in, per row

| Column | What it means | How to count |
|---|---|---|
| `claims` | Material claims in `answer_text`: factual statements that matter to the user (the bin, a preparation step, a day, a place) | An integer. "Rinse it and put it in plastics" is 2 claims. Greetings and "check with your district" are not claims |
| `supported` | Claims the evidence states or directly implies | An integer, ≤ `claims` |
| `contradicted` | Claims the evidence says the opposite of | An integer, ≤ `claims - supported`. A claim the evidence neither states nor contradicts counts in neither column |
| `bin_correct` | Is the bin right for this item in Korea, by the current (2026) rules? | `y`, `n`, or `na` (no bin in the answer, or a schedule-only answer) |
| `notes` | Anything unclear: which claim, and why | Free text. Required when you hesitate |

### Worked example (from Lesson 6, slide 22)

Evidence: [1] "laptop loan: 3 days"; [2] "the library closes at 20:00"; [3] "return laptops to the
help desk". Answer: "The loan lasts 3 days [1]. Return it at the help desk [2]. The library closes
at 20:00. Renewals are unlimited [3]."

`claims` 4 · `supported` 3 (loan, help desk, closing time: the evidence states all three, even
with a wrong citation) · `contradicted` 0 (nothing says renewals are limited) · notes: "renewals
claim unsupported; help-desk claim cites [2] instead of [3]".

## After both sheets are done

```bash
python -m eval.audit agree test-final
```

This computes the following:
- human faithfulness (supported / claims) per rater and pooled;
- Cohen's κ between the raters, on "answer fully supported" (yes/no) and on `bin_correct`;
- the judge's agreement with each rater.

Then the two raters meet and settle every disagreement. Write the outcome in `notes`. The
report states the number before and after that discussion. Update
`eval/reports/test-final/audit/README.md` (status) and REPORT §8.3 and §11 with the numbers.
Leave the original sheets as they are and add the agreed values as new columns, so the
independent ratings stay on record.
