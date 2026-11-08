"""
Metrics over traces (PLAN.md §7.3, §7.5). Each function takes traces and the cases they ran on.

    score_case(trace, case)   one case: behaviour, bin, retrieval ranks, gate, schedule rows,
                              citations, language, latency, and the earliest failed stage
    score(traces, cases)      everything above, aggregated overall, by slice and by language
    quick_summary(...)        the first-look line the experiment runner prints
    schedule_summary(...)     E4 counts for schedule rows

Definitions (declared so that undefined values are counted, not hidden; §7.3):
    behaviour ok     answer -> ANSWER; abstain -> INSUFFICIENT_CONTEXT or OUT_OF_SCOPE (both
                     decline); clarify -> CLARIFY; out_of_scope -> OUT_OF_SCOPE
    bin ok           ANSWER and its bin is one of expected_bin (item cases only)
    false answer     ANSWER when the case should not be answered, or with a bin not in
                     expected_bin: the costly error (§4.6)
    retrieval        over cases with gold chunks, on the final candidate order (after rerank)
    gate             item part only, cases where the item gate decided (answer / abstain);
                     positive = the gate answered, label = the case should be answered
    case ok          answer cases: ANSWER, bin ok (if a bin is expected) and the gold row
                     shown (if a schedule is expected); other cases: behaviour ok
"""
from __future__ import annotations

import math
import re
import statistics
from collections import Counter, defaultdict

from eval.cases import by_id, case_id, gold_chunks

EXPECTED_STATUS = {"answer": "ANSWER", "abstain": "INSUFFICIENT_CONTEXT", "clarify": "CLARIFY",
                   "out_of_scope": "OUT_OF_SCOPE"}
ACCEPTED_STATUS = {"answer": {"ANSWER"}, "abstain": {"INSUFFICIENT_CONTEXT", "OUT_OF_SCOPE"},
                   "clarify": {"CLARIFY"}, "out_of_scope": {"OUT_OF_SCOPE"}}
EXPECTED_INTENT = {"item_direct": "item", "item_tricky": "item", "conflict": "item",
                   "false_premise": "item", "schedule": "schedule", "combined": "both",
                   "ambiguous_location": "schedule", "out_of_scope": "out_of_scope"}
STAGES = ("router", "retrieval", "schedule_tool", "gate", "generation", "validation", "other")
K = 5


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


# ---------------------------------------------------------------------------- one case

def _rank_of(gold: set[str], trace: dict) -> int | None:
    for candidate in trace.get("candidates", []):
        if candidate["chunk_id"] in gold or candidate["metadata"].get("legacy_id") in gold:
            return candidate["rank"]
    return None


def _retrieval(gold: list[str], trace: dict, k: int = K) -> dict:
    wanted = set(gold)
    top = trace.get("candidates", [])[:k]
    relevant = [c["chunk_id"] in wanted or c["metadata"].get("legacy_id") in wanted for c in top]
    rank = _rank_of(wanted, trace)
    dcg = sum(1 / math.log2(i + 2) for i, rel in enumerate(relevant) if rel)
    ideal = sum(1 / math.log2(i + 2) for i in range(min(len(wanted), k)))
    return {"gold_rank": rank, "hit": bool(rank and rank <= k), "rr": 1 / rank if rank else 0.0,
            "ndcg": dcg / ideal if ideal else 0.0, "precision": sum(relevant) / k}


_OWN = {"ko": r"[가-힣]", "zh": r"[\u4e00-\u9fff]", "ru": r"[а-яё]",
        "vi": r"[àáảãạăằắẳẵặâầấẩẫậèéẻẽẹêềếểễệìíỉĩịòóỏõọôồốổỗộơờớởỡợùúủũụưừứửữựỳýỷỹỵđ]"}
_FOREIGN = r"[\u0400-\u04ff\u0600-\u06ff\u4e00-\u9fff가-힣]"


def written_in(text: str, lang: str | None) -> bool | None:
    """Is the LLM's text in the asked language's script? Korean names in parentheses and
    citation marks are ignored. Script only: Uzbek and English cannot be told apart."""
    body = re.sub(r"\([^()]*\)|\[[\d,\s-]+\]", "", text or "")
    letters = re.findall(r"[^\W\d_]", body)
    if not letters or not lang:
        return None

    def share(pattern: str) -> float:
        return len(re.findall(pattern, body, re.IGNORECASE)) / len(letters)

    if lang in ("ko", "zh", "ru"):
        return share(_OWN[lang]) >= 0.5
    if lang == "vi":
        return share(_OWN["vi"]) >= 0.05 and share(_FOREIGN) < 0.05
    return share(_FOREIGN) < 0.05                       # en, uz: Latin script


def _llm_text(trace: dict) -> str | None:
    import json
    raw = (trace.get("llm") or {}).get("raw_output")
    try:
        return json.loads(raw).get("answer_text") if raw else None
    except (ValueError, AttributeError):
        return None


def score_case(trace: dict, case: dict) -> dict:
    answer = trace.get("answer") or {}
    status = answer.get("status")
    behaviour = case.get("expected_behavior")
    gate = trace.get("gate") or {}
    route = trace.get("route") or {}
    validation = (trace.get("checks") or {}).get("validation") or {}
    out = {"case_id": case_id(case), "slice": case.get("slice"), "lang": case.get("lang"),
           "split": case.get("split"), "expected": behaviour, "status": status,
           "behaviour_ok": status in ACCEPTED_STATUS.get(behaviour, set()),
           "intent": route.get("intent"), "intent_expected": EXPECTED_INTENT.get(case.get("slice")),
           "contract_problems": len(trace.get("contract_problems") or []),
           "json_valid": (trace.get("checks") or {}).get("json_valid"),
           "downgraded": bool(validation.get("downgraded")),
           "total_s": (trace.get("timings") or {}).get("total_s")}
    routed = bool((trace.get("settings") or {}).get("router"))
    out["intent_ok"] = (None if out["intent_expected"] is None or not routed
                        else out["intent"] == out["intent_expected"])
    place = (case.get("expected_schedule") or {}).get("place")
    if place and case.get("location") is None and routed:   # the router had to read the place
        resolved = trace.get("resolved") or {}
        out["district_ok"] = resolved.get("district") == place["district"]
        out["dong_ok"] = bool(resolved.get("dong")) and (
            resolved["dong"].replace(" ", "") == place.get("dong", "").replace(" ", ""))

    expected_bins = set(case.get("expected_bin") or [])
    answered = status == "ANSWER"
    if expected_bins:
        out["bin"] = answer.get("bin") or ""
        out["bin_ok"] = answered and out["bin"] in expected_bins
        raw = validation.get("bin_raw") or ""
        from rag.bins import canonical_bin
        out["raw_bin_ok"] = bool(raw) and canonical_bin(raw) in expected_bins
    out["false_answer"] = answered and (behaviour != "answer"
                                        or (bool(expected_bins) and not out.get("bin_ok")))
    gold = gold_chunks(case)
    if gold and trace.get("candidates"):
        out["retrieval"] = _retrieval(gold, trace)
        cited = [c["ref"] for c in answer.get("citations", []) if c["kind"] == "item"]
        if answered and cited:
            out["citation_precision"] = sum(c in set(gold) for c in cited) / len(cited)
            out["cites_gold"] = any(c in set(gold) for c in cited)
    if gate.get("item") in ("answer", "abstain"):
        out["gate_item"] = gate["item"]
        out["gate_should_answer"] = behaviour == "answer" and bool(expected_bins)
        out["top_rerank_score"] = gate.get("top_rerank_score")
    schedule = case.get("expected_schedule")
    if schedule and behaviour == "answer":
        shown = ([z["row_id"] for z in (answer.get("schedule") or {}).get("zones") or []]
                 if answered else [])
        wanted = set(schedule["row_ids"])
        out["rows_found"] = bool(wanted & set(shown))
        out["only_gold_rows"] = bool(shown) and set(shown) <= wanted
        tool_rows = (trace.get("schedule") or {}).get("row_ids", [])
        out["tool_rows_found"] = bool(wanted & set(tool_rows))
    text = _llm_text(trace)
    if answered and text:
        out["language_ok"] = written_in(text, case.get("lang"))
    if behaviour == "answer":
        out["case_ok"] = (answered and out.get("bin_ok", True) is not False
                          and out.get("rows_found", True) is not False)
    else:
        out["case_ok"] = out["behaviour_ok"]
    out["failure_stage"] = None if out["case_ok"] else failure_stage(out, trace, case)
    return out


def failure_stage(scored: dict, trace: dict, case: dict) -> str:
    """The earliest stage that went wrong (§7.5): router -> retrieval / schedule tool -> gate
    -> generation -> validation. Labelled by rule from the trace, not by a person."""
    behaviour = case["expected_behavior"]
    route = trace.get("route") or {}
    gate = trace.get("gate") or {}
    routed = bool((trace.get("settings") or {}).get("router"))
    if routed and (not route.get("valid", True) or scored.get("intent_ok") is False
                   or scored.get("district_ok") is False):
        return "router"
    if behaviour == "answer":
        retrieval = scored.get("retrieval")
        if retrieval and not retrieval["hit"]:
            return "retrieval"
        if scored.get("tool_rows_found") is False:
            return "schedule_tool"
        if (case.get("expected_bin") and gate.get("item") == "abstain") or (
                case.get("expected_schedule") and gate.get("schedule") in ("abstain", "clarify")):
            return "gate"
        if case.get("expected_bin"):
            if not scored.get("raw_bin_ok"):
                return "generation"
            if scored.get("downgraded"):
                return "validation"
        return "other"
    if behaviour in ("abstain", "out_of_scope"):
        return "gate" if gate.get("item") == "answer" or gate.get("schedule") == "answer" \
            else "other"
    if behaviour == "clarify":
        return "schedule_tool" if (trace.get("schedule") or {}).get("status") not in (
            None, "CLARIFY") else "gate"
    return "other"


# ---------------------------------------------------------------------------- aggregates

def _rate(values: list) -> dict | None:
    """{k, n, rate} over the defined values (None = undefined, counted apart)."""
    defined = [v for v in values if v is not None]
    if not defined:
        return None
    k = sum(bool(v) for v in defined)
    return {"k": k, "n": len(defined), "rate": round(k / len(defined), 3),
            "undefined": len(values) - len(defined)}


def _mean(values: list) -> float | None:
    defined = [v for v in values if v is not None]
    return round(sum(defined) / len(defined), 3) if defined else None


def aggregate(rows: list[dict]) -> dict:
    retrieval = [r["retrieval"] for r in rows if "retrieval" in r]
    gate = [r for r in rows if "gate_item" in r]
    tp = sum(r["gate_item"] == "answer" and r["gate_should_answer"] for r in gate)
    fp = sum(r["gate_item"] == "answer" and not r["gate_should_answer"] for r in gate)
    fn = sum(r["gate_item"] == "abstain" and r["gate_should_answer"] for r in gate)
    tn = sum(r["gate_item"] == "abstain" and not r["gate_should_answer"] for r in gate)
    totals = [r["total_s"] for r in rows if r.get("total_s") is not None]
    return {
        "cases": len(rows),
        "case_ok": _rate([r["case_ok"] for r in rows]),
        "behaviour_ok": _rate([r["behaviour_ok"] for r in rows]),
        "bin_ok": _rate([r.get("bin_ok") for r in rows if r["expected"] == "answer"]),
        "false_answer": _rate([r["false_answer"] for r in rows]),
        "abstain_ok": _rate([r["behaviour_ok"] for r in rows
                             if r["expected"] in ("abstain", "out_of_scope")]),
        "clarify_ok": _rate([r["behaviour_ok"] for r in rows if r["expected"] == "clarify"]),
        "intent_ok": _rate([r.get("intent_ok") for r in rows]),
        "district_ok": _rate([r.get("district_ok") for r in rows if "district_ok" in r]),
        "dong_ok": _rate([r.get("dong_ok") for r in rows if "dong_ok" in r]),
        "retrieval": {"n": len(retrieval),
                      "recall@5": _mean([x["hit"] for x in retrieval]),
                      "mrr": _mean([x["rr"] for x in retrieval]),
                      "ndcg@5": _mean([x["ndcg"] for x in retrieval]),
                      "precision@5": _mean([x["precision"] for x in retrieval])},
        "gate": {"tp": tp, "fp": fp, "fn": fn, "tn": tn, "n": len(gate),
                 "accuracy": round((tp + tn) / len(gate), 3) if gate else None,
                 "fp_rate": round(fp / (fp + tn), 3) if fp + tn else None,
                 "fn_rate": round(fn / (fn + tp), 3) if fn + tp else None},
        "rows_found": _rate([r.get("rows_found") for r in rows if "rows_found" in r]),
        "only_gold_rows": _rate([r.get("only_gold_rows") for r in rows if "rows_found" in r]),
        "citation_precision": _mean([r.get("citation_precision") for r in rows]),
        "cites_gold": _rate([r.get("cites_gold") for r in rows if "cites_gold" in r]),
        "language_ok": _rate([r.get("language_ok") for r in rows if "language_ok" in r]),
        "json_valid": _rate([r.get("json_valid") for r in rows if r.get("json_valid") is not None]),
        "downgraded": sum(r["downgraded"] for r in rows),
        "contract_problems": sum(r["contract_problems"] for r in rows),
        "latency_s": {"mean": round(statistics.mean(totals), 2) if totals else None,
                      "median": round(statistics.median(totals), 2) if totals else None,
                      "p90": round(sorted(totals)[int(0.9 * (len(totals) - 1))], 2)
                      if totals else None},
        "failure_stages": dict(Counter(r["failure_stage"] for r in rows if r["failure_stage"])),
    }


def stage_latency(traces: list[dict]) -> dict:
    by_stage = defaultdict(list)
    for trace in traces:
        for name, value in (trace.get("timings") or {}).items():
            by_stage[name].append(value)
    return {name: {"median": round(statistics.median(v), 3), "mean": round(statistics.mean(v), 3)}
            for name, v in sorted(by_stage.items())}


def score(traces: list[dict], cases: list[dict]) -> dict:
    """Everything, overall and by slice and language. Traces whose case is not in `cases`
    are ignored; cases with no trace are counted as missing."""
    cases_by_id = by_id(cases)
    rows = [score_case(t, cases_by_id[t["case_id"]]) for t in traces
            if t.get("case_id") in cases_by_id]
    seen = {r["case_id"] for r in rows}
    by = {key: {value: aggregate([r for r in rows if r[key] == value])
                for value in sorted({r[key] for r in rows if r[key]})}
          for key in ("slice", "lang")}
    heatmap = defaultdict(Counter)
    for r in rows:
        if r["failure_stage"]:
            heatmap[r["slice"]][r["failure_stage"]] += 1
    return {"overall": aggregate(rows), "by_slice": by["slice"], "by_lang": by["lang"],
            "failure_heatmap": {s: dict(c) for s, c in sorted(heatmap.items())},
            "stage_latency_s": stage_latency(traces),
            "missing_cases": sorted(c for c in cases_by_id if c not in seen),
            "rows": rows}
