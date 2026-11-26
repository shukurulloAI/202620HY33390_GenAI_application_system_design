"""
Gate threshold sweep (E5; PLAN.md §4.6, Lesson 6). No re-run needed: the gate only
compares the top rerank score with tau, so every tau can be scored from one set of
traces (rerank on).

    python -m experiments.tau_sweep <E5 rerank-on traces> --cases eval/cases/dev.jsonl

Label per case: should the item part be answered?
    eval cases:  expected_behavior == "answer"        (PLAN.md §7.1)
    probes:      expect_status == "ANSWER"
Only cases where item retrieval ran are counted (out-of-scope / schedule-only skip it).

Positive = gate answers. FP = answered without sufficient evidence (the costly error).
Pick tau on dev by the declared objective: lowest FP rate with FN rate <= a set limit.
"""
from __future__ import annotations

import argparse
from pathlib import Path
from typing import NamedTuple

from eval.cases import by_id, load_cases
from rag import paths
from rag.files import read_jsonl


class Point(NamedTuple):
    score: float               # top rerank score in the evidence set
    should_answer: bool
    case_id: str


class Row(NamedTuple):
    tau: float
    tp: int
    fp: int
    fn: int
    tn: int
    fp_rate: float
    fn_rate: float


def should_answer(case: dict) -> bool:
    if "expected_behavior" in case:
        return case["expected_behavior"] == "answer"
    status = case.get("expect_status")
    return status == "ANSWER" or (isinstance(status, list) and "ANSWER" in status)


def load_points(traces: list[dict], cases: dict) -> list[Point]:
    points = []
    for trace in traces:
        if not trace.get("candidates") or trace["case_id"] not in cases:
            continue
        k_final = trace["settings"]["config"]["k_final"]
        top = max((c["rerank_score"] or 0.0) for c in trace["candidates"][:k_final])
        points.append(Point(top, should_answer(cases[trace["case_id"]]), trace["case_id"]))
    return points


def sweep(points: list[Point]) -> list[Row]:
    taus = sorted({0.0} | {round(x / 100, 2) for x in range(1, 100)} | {p.score for p in points})
    positives = sum(p.should_answer for p in points)
    negatives = len(points) - positives
    rows = []
    for tau in taus:
        tp = sum(p.score >= tau and p.should_answer for p in points)
        fp = sum(p.score >= tau and not p.should_answer for p in points)
        fn, tn = positives - tp, negatives - fp
        rows.append(Row(tau, tp, fp, fn, tn, fp / negatives if negatives else 0.0,
                        fn / positives if positives else 0.0))
    return rows


def choose_tau(rows: list[Row], scores: set[float], fn_limit: float) -> dict | None:
    """Objective (PLAN.md §4.6): lowest FP rate with FN rate <= limit, then lowest FN rate.
    Every tau between two neighbouring scores gives the same counts, so take the middle
    of the winning interval (largest margin on both sides), not its edge."""
    allowed = [r for r in rows if r.fn_rate <= fn_limit]
    if not allowed:
        return None
    target = min((r.fp_rate, r.fn_rate) for r in allowed)
    best = [r.tau for r in allowed if (r.fp_rate, r.fn_rate) == target]
    below = max((s for s in scores if s < min(best)), default=0.0)
    above = min((s for s in scores if s >= max(best)), default=1.0)
    return {"tau": round((below + above) / 2, 3), "fp_rate": target[0], "fn_rate": target[1],
            "below": below, "above": above}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("traces", type=Path)
    parser.add_argument("--cases", type=Path, default=paths.PROBES)
    parser.add_argument("--fn-limit", type=float, default=0.2,
                        help="max false-negative rate allowed when choosing tau")
    args = parser.parse_args()

    points = load_points(read_jsonl(args.traces), by_id(load_cases(args.cases)))
    if not points:
        raise SystemExit("no traces with rerank scores (run with rerank on)")
    positives = sum(p.should_answer for p in points)
    print(f"{len(points)} cases with item retrieval: {positives} should answer, "
          f"{len(points) - positives} should abstain")
    print(f"{'tau':>7} {'TP':>4} {'FP':>4} {'FN':>4} {'TN':>4} {'FP rate':>8} {'FN rate':>8}")
    rows = sweep(points)
    scores = {p.score for p in points}
    for r in rows:
        if r.tau == 0.0 or round(r.tau * 100) % 5 == 0 or r.tau in scores:
            print(f"{r.tau:7.4f} {r.tp:4d} {r.fp:4d} {r.fn:4d} {r.tn:4d} "
                  f"{r.fp_rate:8.2f} {r.fn_rate:8.2f}")
    chosen = choose_tau(rows, scores, args.fn_limit)
    if chosen:
        print(f"\nchosen tau = {chosen['tau']} (FP rate {chosen['fp_rate']:.2f}, FN rate "
              f"{chosen['fn_rate']:.2f}, FN limit {args.fn_limit}; any tau in "
              f"({chosen['below']:.3f}, {chosen['above']:.3f}] gives the same counts)")
    print("scores:", ", ".join(f"{p.case_id}={p.score:.3f}{'+' if p.should_answer else '-'}"
                               for p in sorted(points)))


if __name__ == "__main__":
    main()
