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


def test_several_items_are_searched_one_by_one_and_taken_in_turn():
    from types import SimpleNamespace

    from rag.pipeline import Pipeline
    from rag.router import Route, check_invariants
    from tests.helpers import cand

    class PerItem:
        def __init__(self):
            self.calls = []

        def search(self, queries, rerank_queries=None, doc_types=None, item_names=None):
            self.calls.append(queries)
            tag = "rod" if "낚싯대" in queries.get("rewrite", "") else "ball"
            cands = [cand(f"{tag}{i}", i) for i in range(1, 6)] + [cand("shared", 6)]
            return cands, cands[:5], {"queries": queries, "timings": {"retrieve_s": 0.1}}

    pipe = Pipeline.__new__(Pipeline)
    pipe.cfg = SimpleNamespace(query_mode="both", rerank_query="max", rerank_item=True, k_final=5)
    pipe.retriever = PerItem()
    route = Route(valid=True, intent="item", item="fishing rod", item_ko="낚싯대",
                  ko_query="낚싯대 분리배출", lang="en",
                  items=[{"item": "fishing rod", "item_ko": "낚싯대", "ko_query": "낚싯대 분리배출"},
                         {"item": "golf balls", "item_ko": "골프공", "ko_query": "골프공 분리배출"}])
    route.checks = check_invariants("Where do a fishing rod and golf balls go?", route)
    candidates, selected, record = pipe.retrieve("Where do a fishing rod and golf balls go?",
                                                 route)
    assert len(pipe.retriever.calls) == 2 and record["share"] == 3
    assert [c.chunk_id for c in selected] == ["rod1", "ball1", "rod2", "ball2", "rod3"]
    assert [c.rank for c in candidates] == list(range(1, len(candidates) + 1))
    assert len({c.chunk_id for c in candidates}) == len(candidates)        # "shared" once
    assert record["timings"]["retrieve_s"] == 0.2

    route.items = route.items[:1]                       # one item: the usual single search
    pipe.retriever.calls.clear()
    pipe.retrieve("Where does a fishing rod go?", route)
    assert len(pipe.retriever.calls) == 1


def test_an_item_with_a_garbled_rewrite_is_searched_with_the_question():
    from types import SimpleNamespace

    from rag.pipeline import Pipeline
    from rag.router import Route, check_invariants
    from tests.helpers import FakeRetriever, cand

    pipe = Pipeline.__new__(Pipeline)
    pipe.cfg = SimpleNamespace(query_mode="both", rerank_query="max", rerank_item=True, k_final=5)
    pipe.retriever = FakeRetriever([cand("a", 1), cand("b", 2)])
    question = "Vỏ trứng và vỏ cam bỏ vào đâu?"
    route = Route(valid=True, intent="item", item="Vỏ trứng", item_ko="계란 скорлуп",
                  ko_query="계란 скорлуп 분리배출", lang="vi",
                  items=[{"item": "Vỏ trứng", "item_ko": "계란 скорлуп",
                          "ko_query": "계란 скорлуп 분리배출"},
                         {"item": "vỏ cam", "item_ko": "귤껍질", "ko_query": "귤껍질 분리배출"}])
    route.checks = check_invariants(question, route)
    pipe.retrieve(question, route)
    assert pipe.retriever.queries == [{"original": question},
                                      {"original": "vỏ cam", "rewrite": "귤껍질 분리배출"}]
