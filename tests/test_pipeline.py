"""Pipeline helpers that need no models."""
from __future__ import annotations

from rag.pipeline import day_asked, item_only_question
from rag.router import Route


def test_item_only_question():
    route = Route(valid=True, item="pizza box")
    asked = item_only_question("Where does a pizza box go, and when is food waste day?", route)
    assert asked.startswith("How do I throw away pizza box?") and "food waste day" not in asked
    assert "food waste day" in item_only_question("When is food waste day?", Route(valid=True))


def test_day_named_in_question_beats_router():
    assert day_asked("화요일에 음식물쓰레기 버려도 되나요?", "wed") == "tue"
    assert day_asked("Can I put it out on Sunday?", "sat") == "sun"
    assert day_asked("Can I put it out tonight?", "tonight") == "tonight"
    assert day_asked("월요일이나 수요일에 버려도 되나요?", "mon") == "mon"       # two days: the router's
