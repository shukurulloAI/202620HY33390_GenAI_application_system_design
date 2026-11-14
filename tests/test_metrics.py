"""Counts over traces."""
from __future__ import annotations

import math

import pytest

from eval.metrics import schedule_summary
from rag.schedule_tool import default_table


def test_schedule_summary_counts():
    table = default_table()
    first_seen = {}
    for row in table.rows:                             # two districts, one food schedule
        rule = row.rules["food"]
        twin = first_seen.setdefault((tuple(rule.days), rule.start, rule.end), row)
        if twin.district != row.district:
            one, same_days = twin.row_id, row.row_id
            break

    def trace(cid, status, shown):
        return {"case_id": cid, "answer": {"status": status, "schedule": {
            "zones": [{"row_id": i} for i in shown]}}}
    cases = [{"case_id": "a", "waste_type": "food", "expected_behavior": "answer",
              "expected_schedule": {"row_ids": [one]}},
             {"case_id": "b", "waste_type": "food", "expected_behavior": "abstain",
              "expected_schedule": {"row_ids": []}}]
    good = schedule_summary([trace("a", "ANSWER", [one]),
                             trace("b", "INSUFFICIENT_CONTEXT", [])], cases, table)
    assert good == {"cases": 2, "behaviour_ok": 2, "wrong_place": 0, "answerable": 1, "empty": 0,
                    "row_found": 1, "top_row": 1, "only_correct_rows": 1, "day_time_match": 1}
    # Another district's row with the same days: the day/time still matches, the place does not.
    lucky = schedule_summary([trace("a", "ANSWER", [same_days]),
                              trace("b", "ANSWER", [one])], cases, table)
    assert (lucky["day_time_match"], lucky["row_found"], lucky["wrong_place"]) == (1, 0, 2)
    # Rows of a refused answer are not shown to the user.
    refused = schedule_summary([trace("a", "INSUFFICIENT_CONTEXT", [one])], cases[:1], table)
    assert (refused["empty"], refused["row_found"]) == (1, 0)


def _trace(status, bin_key="", candidates=(), gate_item="answer", raw_bin=None, intent="item"):
    return {"case_id": "c1", "settings": {"router": "router_v1"},
            "route": {"valid": True, "intent": intent},
            "answer": {"status": status, "bin": bin_key, "citations": [], "schedule": None},
            "candidates": [{"chunk_id": cid, "rank": r, "metadata": {}}
                           for r, cid in enumerate(candidates, 1)],
            "gate": {"item": gate_item, "schedule": "skip", "top_rerank_score": 0.5},
            "checks": {"json_valid": True, "validation": {"bin_raw": raw_bin or bin_key}},
            "timings": {"total_s": 10.0}}


def test_score_case_bins_retrieval_and_failure_stage():
    from eval.metrics import score_case
    case = {"case_id": "c1", "slice": "item_tricky", "lang": "en", "expected_behavior": "answer",
            "expected_bin": ["종량제봉투"], "expected_chunk_ids": ["g"], "expected_schedule": None,
            "location": None}
    good = score_case(_trace("ANSWER", "종량제봉투", ["x", "g"]), case)
    assert good["case_ok"] and good["retrieval"]["gold_rank"] == 2 and good["retrieval"]["rr"] == 0.5
    wrong = score_case(_trace("ANSWER", "음식물", ["g"]), case)
    assert wrong["false_answer"] and wrong["failure_stage"] == "generation"
    missed = score_case(_trace("INSUFFICIENT_CONTEXT", "", ["x"], gate_item="abstain"), case)
    assert not missed["false_answer"] and missed["failure_stage"] == "retrieval"
    gated = score_case(_trace("INSUFFICIENT_CONTEXT", "", ["g"], gate_item="abstain"), case)
    assert gated["failure_stage"] == "gate"
    downgraded = _trace("INSUFFICIENT_CONTEXT", "", ["g"], raw_bin="종량제봉투")
    downgraded["checks"]["validation"]["downgraded"] = True
    assert score_case(downgraded, case)["failure_stage"] == "validation"
    withheld = score_case(_trace("ANSWER", "", ["g"]), case)   # schedule only, item withheld
    assert not withheld["case_ok"] and not withheld["false_answer"] and withheld["item_withheld"]
    misrouted = score_case(_trace("OUT_OF_SCOPE", intent="out_of_scope"), case)
    assert misrouted["failure_stage"] == "router"


def test_declining_counts_as_abstaining_and_aggregates_count():
    from eval.metrics import score
    case = {"case_id": "c1", "slice": "no_evidence", "lang": "ko", "expected_behavior": "abstain",
            "expected_bin": [], "expected_chunk_ids": [], "expected_schedule": None,
            "location": None}
    result = score([_trace("OUT_OF_SCOPE", intent="out_of_scope")], [case])
    assert result["overall"]["abstain_ok"]["k"] == 1 and result["overall"]["false_answer"]["k"] == 0
    answered = score([_trace("ANSWER", "종이", ["x"])], [case])["overall"]
    assert answered["false_answer"]["k"] == 1 and answered["gate"]["fp"] == 1


def test_language_check_reads_the_script():
    from eval.metrics import written_in
    assert written_in("Put it in the paper bin (종이) [1].", "en")
    assert not written_in("Plastik (플라스틱) келишикча чирикка", "uz")
    assert written_in("Положите в контейнер (유리병) [1].", "ru")
    assert not written_in("Put it in the paper bin.", "ko")


def test_audit_kappa_and_pick():
    from eval.audit import kappa, pick
    assert kappa([True, True, False, False], [True, True, False, False]) == 1.0
    assert kappa([True, False, True, False], [False, True, False, True]) == -1.0
    assert kappa([True, None], [True, False]) == 1.0          # unlabelled pairs are skipped
    rows = [{"slice": s, "i": i} for s in ("a", "b", "c") for i in range(5)]
    picked = pick(rows, 6)
    assert len(picked) == 6 and {r["slice"] for r in picked} == {"a", "b", "c"}
    assert pick(rows, 6) == picked                             # fixed seed


def test_recall_counts_every_gold_chunk_and_hit_counts_any():
    """Lesson 6: Recall@k = gold found in the top k / all gold. Finding 1 of 2 is a hit."""
    from eval.metrics import recall_at_k, score_case
    case = {"case_id": "c1", "slice": "item_direct", "expected_behavior": "answer",
            "expected_bin": ["종량제봉투"], "expected_chunk_ids": ["g1", "g2"]}
    one = score_case(_trace("ANSWER", "종량제봉투", ["x", "g1", "y"]), case)["retrieval"]
    assert (one["hit"], one["recall"]) == (True, 0.5)
    both = score_case(_trace("ANSWER", "종량제봉투", ["g2", "g1"]), case)["retrieval"]
    assert both["recall"] == 1.0
    # A gold chunk below the cutoff is not found; a repeated candidate is counted once.
    deep = [{"chunk_id": c, "rank": r, "metadata": {}} for r, c in
            enumerate(["g1", "g1", "a", "b", "c", "g2"], 1)]
    assert recall_at_k(["g1", "g2"], deep, k=5) == 0.5
    # Matched by legacy ID too; no gold = undefined.
    legacy = [{"chunk_id": "u", "rank": 1, "metadata": {"legacy_id": "item2018_0001"}}]
    assert recall_at_k(["item2018_0001"], legacy) == 1.0
    assert recall_at_k([], legacy) is None


def test_citation_precision_is_pooled_over_judged_claims():
    from eval.metrics import score
    cases = [{"case_id": c, "slice": "item_direct", "lang": "en", "expected_behavior": "answer",
              "expected_bin": ["종량제봉투"]} for c in ("a", "b", "c")]
    traces = []
    for cid in ("a", "b", "c"):
        t = _trace("ANSWER", "종량제봉투", [])
        t["case_id"] = cid
        traces.append(t)
    labels = {"a": {"cited": 3, "supported": 3}, "b": {"cited": 1, "supported": 0}}
    precision = score(traces, cases, labels)["overall"]["citation_precision"]
    assert precision == {"k": 3, "n": 4, "rate": 0.75, "cases": 2}   # not the case mean 0.5
    assert score(traces, cases)["overall"]["citation_precision"] is None   # not judged


def test_v2_graded_gold_and_every_bin_named():
    from eval.metrics import score_case
    case = {"case_id": "c1", "slice": "multi_item", "expected_behavior": "answer",
            "expected_bin": ["종이", "음식물"], "expected_bins_all": ["종이", "음식물"],
            "expected_chunk_ids": ["g1"], "supporting_chunk_ids": ["s1"]}
    trace = _trace("ANSWER", "종이", ["s1", "x", "g1"])
    trace["answer"]["answer_text"] = "Box with paper (종이) [1]; leftover pizza is food waste (음식물) [2]."
    row = score_case(trace, case)
    r = row["retrieval"]
    # Recall counts required chunks only; precision counts both grades; nDCG is graded.
    assert (r["recall"], r["precision"], r["gold_rank"]) == (1.0, 0.4, 3)
    best = 2 + 1 / math.log2(3)
    assert r["ndcg"] == pytest.approx((1 + 2 / math.log2(4)) / best)
    assert row["bins_all_ok"] and row["case_ok"]
    trace["answer"]["answer_text"] = "Put the box with paper (종이) [1]."
    missing = score_case(trace, case)
    assert (missing["bins_all_ok"], missing["bins_all_missing"]) == (False, ["음식물"])
    assert not missing["case_ok"] and missing["failure_stage"] == "generation"
