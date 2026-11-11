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


def test_a_mixed_script_rewrite_is_repaired_once():
    from rag.llm_client import LLMResult
    from rag.router import Router

    replies = iter([
        '{"intent": "item", "item": "yog\'", "item_ko": "기름occo散布的纸张", '
        '"ko_query": "기름occo散布的纸张 분리배출", "district": "", "dong": "", '
        '"waste_type": "none", "day_ref": "none", "negation": false, "lang": "uz"}',
        '{"intent": "item", "item": "yog\'", "item_ko": "폐식용유", '
        '"ko_query": "폐식용유 분리배출 방법", "district": "", "dong": "", '
        '"waste_type": "none", "day_ref": "none", "negation": false, "lang": "uz"}'])

    class Scripted:
        model_id = "scripted"

        def generate(self, **kwargs):
            return LLMResult(text=next(replies), model_id="scripted")

    question = "Qovurishda ishlatilgan yog'ni qayerga to'kaman?"
    route = Router(Scripted(), repair=True).route(question)
    assert route.item_ko == "폐식용유" and route.checks["rewrite_usable"]
    assert "repaired" in route.checks["repair"] and len(route.attempts) == 2


def test_an_item_question_that_asks_when_gets_the_schedule_too():
    """qwen2.5:7b routes "Where and when do I throw away a pizza box?" as item only, so the
    collection days were never looked up. None of the recorded dev or test routes is an item
    question that asks when, so no recorded answer changes."""
    asks_when = [
        "Where and when do I throw away a pizza box?", "When can I put out a pizza box?",
        "Where when and how do I throw away a pizza box?", "Where, when and how: pizza box?",
        "Pizza box - where/when?", "How and when do I throw away a pizza box?",
        "What day do I put out pizza boxes?", "피자 박스는 언제 버려요?", "피자 박스 배출 요일은?",
        "披萨盒什么时候扔?", "Khi nào tôi bỏ hộp pizza?", "Pitsa qutisini qachon tashlayman?",
        "Когда выбрасывать коробку от пиццы?"]
    for question in asks_when:
        route = Route(valid=True, intent="item", item="pizza box", item_ko="피자 상자",
                      ko_query="피자 상자 분리배출")
        checks = check_invariants(question, route)
        assert route.intent == "both", question
        assert checks["intent_repaired"] == "item -> both (question asks when)"
    for question in ("Where do I throw away a pizza box?",
                     "What do I do with chicken bones when I'm done eating?",   # a conjunction
                     "Can I recycle a pizza box when it is greasy?",
                     "피자 박스는 어떻게 버려요?"):
        route = Route(valid=True, intent="item", item="pizza box", item_ko="피자 상자",
                      ko_query="피자 상자 분리배출")
        assert "intent_repaired" not in check_invariants(question, route)
        assert route.intent == "item", question
