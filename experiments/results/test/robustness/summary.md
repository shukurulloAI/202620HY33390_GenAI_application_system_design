# Robustness probes (PLAN.md §7.6)

Cases `eval/cases/test.jsonl` (sha256 `c3be328d06ca`): 19 answer cases with an expected bin and gold chunks. Run at commit `cf047ff`; outcomes relabelled from the saved traces at commit `cf047ff` (an ANSWER with no bin counts as abstaining on the item).

| Probe | Outcomes |
|---|---|
| clean | right bin 11/19, abstained 7/19, wrong bin 1/19 |
| noise | same bin 11/19, abstained, as clean 6/19, answered (clean abstained) 1/19, abstained (clean answered) 1/19 |
| negative | abstained 9/19, right bin anyway 6/19, wrong bin 4/19 |
| counterfactual | followed the false chunk 12/19, abstained 4/19, right bin 3/19 |
