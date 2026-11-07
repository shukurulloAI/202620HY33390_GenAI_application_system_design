"""
Counts over traces (PLAN.md §7.3). Each function takes traces and the cases they ran on.

So far: the first-look summaries the experiment runner prints.
"""
from __future__ import annotations

from collections import Counter

from eval.cases import by_id, gold_chunks

EXPECTED_STATUS = {"answer": "ANSWER", "abstain": "INSUFFICIENT_CONTEXT", "clarify": "CLARIFY"}


def gold_rank(gold: list[str], trace: dict) -> int | None:
    """1-based rank of the first gold chunk in the final candidate order; None = not in R."""
    wanted = set(gold)
    for candidate in trace.get("candidates", []):
        if candidate["chunk_id"] in wanted or candidate["metadata"].get("legacy_id") in wanted:
            return candidate["rank"]
    return None


def quick_summary(traces: list[dict], cases: list[dict], k: int) -> dict:
    cases_by_id = by_id(cases)
    hits, reciprocal_ranks, n_gold = 0, 0.0, 0
    for trace in traces:
        gold = gold_chunks(cases_by_id.get(trace["case_id"], {}))
        if not gold:
            continue
        n_gold += 1
        rank = gold_rank(gold, trace)
        hits += bool(rank and rank <= k)
        reciprocal_ranks += 1 / rank if rank else 0.0
    statuses = Counter((t.get("answer") or {}).get("status", "retrieval-only") for t in traces)
    totals = [t["timings"]["total_s"] for t in traces]
    return {"cases": len(traces), "gold_cases": n_gold,
            f"recall@{k}": round(hits / n_gold, 3) if n_gold else None,
            "mrr": round(reciprocal_ranks / n_gold, 3) if n_gold else None,
            "statuses": dict(statuses),
            "mean_total_s": round(sum(totals) / len(totals), 2) if totals else None}


def schedule_summary(traces: list[dict], cases: list[dict], table) -> dict:
    """E4, as counts. `expected_schedule.row_ids` come from a scan of the table, never from
    the tool being measured. Rows are scored as shown to the user: an answer that was refused
    shows none.

    A row with another district's identical days still counts as a day/time match, because
    the rows are near-duplicates. So wrong_place is counted apart: the days may be right by
    luck, but the place and the office phone are not."""
    cases_by_id = by_id(cases)
    out = Counter()
    for trace in traces:
        case = cases_by_id.get(trace["case_id"], {})
        if not case.get("expected_schedule"):
            continue
        answer = trace.get("answer") or {}
        zones = (answer.get("schedule") or {}).get("zones") or []
        shown = [z["row_id"] for z in zones] if answer.get("status") == "ANSWER" else []
        gold = set(case["expected_schedule"]["row_ids"])
        places = {(table.by_id[i].province, table.by_id[i].district) for i in gold}
        out["cases"] += 1
        out["behaviour_ok"] += answer.get("status") == EXPECTED_STATUS[case["expected_behavior"]]
        out["wrong_place"] += any((table.by_id[i].province, table.by_id[i].district) not in places
                                  for i in shown)
        if case["expected_behavior"] != "answer":
            continue
        out["answerable"] += 1
        out["empty"] += not shown
        out["row_found"] += bool(gold & set(shown))
        out["top_row"] += bool(shown) and shown[0] in gold
        out["only_correct_rows"] += bool(shown) and set(shown) <= gold
        out["day_time_match"] += bool(shown) and _when(table, shown[0], case) in {
            _when(table, i, case) for i in gold}
    return dict(out)


def _when(table, row_id: str, case: dict) -> tuple:
    rule = table.by_id[row_id].rules[case["waste_type"]]
    return tuple(rule.days), rule.start, rule.end
