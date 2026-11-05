"""
Gate threshold sweep (E5; PLAN.md §4.6, Lesson 6). No re-run needed: the gate only
compares the top rerank score with tau, so every tau can be scored from one set of
traces (rerank on).

    python -m experiments.tau_sweep experiments/results/E5/rerank-on.jsonl --cases eval/cases/dev.jsonl

Label per case: should the item part be answered?
    eval cases:  expected_behavior == "answer"        (Anar's schema, PLAN.md §7.1)
    probes:      expect_status == "ANSWER"
Only cases where item retrieval ran are counted (out-of-scope / schedule-only skip it).

Positive = gate answers. FP = answered without sufficient evidence (the costly error).
Pick tau on dev by the declared objective: lowest FP rate with FN rate <= a set limit.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path


def should_answer(case: dict) -> bool:
    if "expected_behavior" in case:
        return case["expected_behavior"] == "answer"
    status = case.get("expect_status")
    return status == "ANSWER" or (isinstance(status, list) and "ANSWER" in status)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("traces", type=Path)
    parser.add_argument("--cases", type=Path,
                        default=Path(__file__).with_name("probes.jsonl"))
    parser.add_argument("--fn-limit", type=float, default=0.2,
                        help="max false-negative rate allowed when choosing tau")
    args = parser.parse_args()

    cases = {}
    for line in args.cases.read_text(encoding="utf-8").splitlines():
        if line.strip():
            c = json.loads(line)
            cases[c.get("case_id") or c.get("probe_id")] = c
    points = []
    for line in args.traces.read_text(encoding="utf-8").splitlines():
        t = json.loads(line)
        if not t.get("candidates") or t["case_id"] not in cases:
            continue
        top = max((c["rerank_score"] or 0.0) for c in t["candidates"][:t["settings"]["config"]["k_final"]])
        points.append((top, should_answer(cases[t["case_id"]]), t["case_id"]))
    if not points:
        raise SystemExit("no traces with rerank scores (run with rerank on)")

    taus = sorted({0.0} | {round(x / 100, 2) for x in range(1, 100)} | {p[0] for p in points})
    pos = sum(1 for _, y, _ in points if y)
    neg = len(points) - pos
    print(f"{len(points)} cases with item retrieval: {pos} should answer, {neg} should abstain")
    print(f"{'tau':>7} {'TP':>4} {'FP':>4} {'FN':>4} {'TN':>4} {'FP rate':>8} {'FN rate':>8}")
    rows = []
    for tau in taus:
        tp = sum(1 for s, y, _ in points if s >= tau and y)
        fp = sum(1 for s, y, _ in points if s >= tau and not y)
        fn, tn = pos - tp, neg - fp
        fpr, fnr = (fp / neg if neg else 0.0), (fn / pos if pos else 0.0)
        rows.append((tau, tp, fp, fn, tn, fpr, fnr))
    scores = {p[0] for p in points}
    for tau, tp, fp, fn, tn, fpr, fnr in rows:
        if tau == 0.0 or round(tau * 100) % 5 == 0 or tau in scores:
            print(f"{tau:7.4f} {tp:4d} {fp:4d} {fn:4d} {tn:4d} {fpr:8.2f} {fnr:8.2f}")
    # Objective (PLAN.md §4.6): lowest FP rate with FN rate <= limit, then lowest FN rate.
    # Every tau between two neighbouring scores gives the same counts, so take the middle
    # of the winning interval (largest margin on both sides), not its edge.
    ok = [r for r in rows if r[6] <= args.fn_limit]
    if ok:
        target = min((r[5], r[6]) for r in ok)
        best = [r[0] for r in ok if (r[5], r[6]) == target]
        below = max((sc for sc in scores if sc < min(best)), default=0.0)
        above = min((sc for sc in scores if sc >= max(best)), default=1.0)
        tau = round((below + above) / 2, 3)
        print(f"\nchosen tau = {tau} (FP rate {target[0]:.2f}, FN rate {target[1]:.2f}, "
              f"FN limit {args.fn_limit}; any tau in ({below:.3f}, {above:.3f}] gives the same counts)")
    print("scores:", ", ".join(f"{cid}={s:.3f}{'+' if y else '-'}"
                               for s, y, cid in sorted(points)))


if __name__ == "__main__":
    main()
