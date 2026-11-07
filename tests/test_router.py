"""Rewrite invariants."""
from __future__ import annotations

from rag.router import Route, check_invariants, is_korean


def test_router_invariants():
    route = Route(valid=True, intent="schedule", item="chicken bones", item_ko="닭骨头",
                  ko_query="닭 뼈", district="성동구", lang="ko")
    checks = check_invariants("Where do chicken bones go?", route)
    assert route.intent == "both"                         # item named -> both
    assert checks["district_in_question"] is False and route.district == ""
    assert checks["item_ko_korean"] is False and checks["rewrite_usable"] is False
    assert route.lang == "en"                             # Latin script, not Korean
    assert is_korean("투명 PET병", strict=True)
