"""Evidence gate decisions."""
from __future__ import annotations

from rag.gate import decide
from rag.schedule_tool import ScheduleResult, default_table
from tests.helpers import cand


def test_gate_decisions():
    sel = [cand("a", 1, 0.9)]
    assert decide("out_of_scope", [], None, None, None, 0.05).status == "OUT_OF_SCOPE"
    assert decide("item", sel, None, None, None, 0.05).status == "ANSWER"
    low = decide("item", [cand("a", 1, 0.01)], None, None, None, 0.05)
    assert low.status == "INSUFFICIENT_CONTEXT" and low.item == "abstain"
    assert decide("schedule", [], None, None, None, 0.05).status == "CLARIFY"
    no_data = ScheduleResult("NO_DATA", {}, message="no schedule data")
    assert decide("schedule", [], no_data, "강동구", None, 0.05).status == "INSUFFICIENT_CONTEXT"
    both = decide("both", sel, no_data, "강동구", None, 0.05)
    assert both.status == "ANSWER" and both.schedule == "abstain"


def test_gate_many_rows_in_one_area():
    """Only MAX_ZONES rows reach the answer, so the gate must not answer for the rest."""
    table = default_table()

    def gate(district, dong, waste):
        return decide("schedule", [], table.lookup(district, None, dong, waste), district, dong, 0.15)

    one_name = gate("고흥군", "도덕면", "food")          # 287 collection points, Mon-Fri
    assert (one_name.status, one_name.schedule, one_name.schedule_varies) == (
        "INSUFFICIENT_CONTEXT", "abstain", True)
    names = gate("양평군", "오빈리", "general")          # 오빈1리, 오빈2리, 오빈3리
    assert names.status == "CLARIFY" and names.clarify["options"] == ["오빈1리", "오빈2리", "오빈3리"]
    assert gate("정선군", "정선읍", "food").schedule == "answer"      # same days in every row
    # Whether the rows differ depends on the waste type asked about.
    assert gate("고창군", "고창읍", "general").schedule == "answer"
    assert gate("고창군", "고창읍", "food").schedule == "abstain"
