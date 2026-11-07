"""Fields of the answer contract."""
from __future__ import annotations

from types import SimpleNamespace

from rag.answer import handoff, schedule_fields
from rag.gate import GateDecision
from rag.router import Route
from rag.schedule_tool import default_table


def test_answer_schedule_fields():
    """The flat §4.8 fields the website reads; values come from the rows, never the LLM."""
    table = default_table()
    one = table.lookup("성동구", dong="행당동", waste_type="food").rows
    fields = schedule_fields(one, ["food"])
    assert fields["days"] == "Mon, Wed, Fri" and fields["time"] and fields["place"]
    assert fields["data_date"] == one[0].data_date and fields["office_phone"] == one[0].phone
    several = table.lookup("노원구").rows                              # one entry per zone
    assert len(several) > 1
    many = schedule_fields(several, ["food"])
    assert all(r.zone in many["days"] for r in several if r.rules["food"].days)
    assert schedule_fields([], ["food"])["days"] is None


def test_handoff_keeps_broken_korean_away_from_the_user():
    route = Route(valid=True, item="nail polish bottles", item_ko="네일 pol리스 병",
                  checks={"item_in_question": True})
    request = SimpleNamespace(district=None, dong=None, waste_type=None)
    gate = GateDecision("INSUFFICIENT_CONTEXT", "abstain", "skip")
    sentence = handoff(request, route, gate, None)["korean_sentence"]
    assert "pol리스" not in sentence and "nail polish bottles" in sentence
