"""Counts over traces."""
from __future__ import annotations

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
