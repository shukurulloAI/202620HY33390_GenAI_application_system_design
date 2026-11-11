"""The website's module: offline answers, failures turned into handoffs, feedback, page data."""
from __future__ import annotations

import json

import pytest

from rag import service
from rag.contract import problems
from rag.texts import TEXTS


@pytest.fixture
def offline():
    service.configure(offline=True)
    yield
    service.configure(offline=False)


def test_offline_answers_are_recorded_examples(offline):
    first = service.examples()[0]
    assert service.ask(first["question"]) == first["answer"]
    other = service.ask("something nobody recorded", lang="ko")
    assert other["notes"][0] == TEXTS["ko"]["OFFLINE"] and problems(other) == []
    with pytest.raises(ValueError):
        service.ask("   ")


def test_a_failing_pipeline_gives_a_handoff(tmp_path, monkeypatch):
    class Broken:
        def answer(self, *args, **kwargs):
            raise ConnectionError("ollama is down")
    monkeypatch.setattr(service, "ERRORS_FILE", tmp_path / "errors.jsonl")
    service.configure(offline=False, pipeline=Broken())
    try:
        answer = service.ask("Where do batteries go?", lang="vi", district="성동구")
    finally:
        service._state["pipeline"] = None
    assert answer["status"] == "INSUFFICIENT_CONTEXT" and problems(answer) == []
    assert answer["answer_text"] == TEXTS["vi"]["UNAVAILABLE"]
    assert "성동구" in answer["handoff"]["korean_sentence"]
    logged = json.loads((tmp_path / "errors.jsonl").read_text())
    assert logged["trace_id"] == answer["trace_id"] and "ollama is down" in logged["error"]


def test_feedback_is_saved_by_trace_id(tmp_path, monkeypatch):
    monkeypatch.setattr(service, "FEEDBACK_FILE", tmp_path / "feedback.jsonl")
    service.save_feedback("t-1", "up", " clear ")
    service.save_feedback("t-2", "down")
    rows = [json.loads(line) for line in (tmp_path / "feedback.jsonl").read_text().splitlines()]
    assert [(r["trace_id"], r["rating"], r["comment"]) for r in rows] == [
        ("t-1", "up", "clear"), ("t-2", "down", "")]
    with pytest.raises(ValueError):
        service.save_feedback("t-3", "meh")


def test_page_data():
    assert set(service.languages()) == {"en", "ko", "zh", "vi", "uz", "ru"}
    districts = service.locations()
    assert any(d["district"] == "성동구" and d["has_data"] for d in districts)
    assert any(d["district"] == "강동구" and not d["has_data"] for d in districts)
    assert all({"ko", "en", "uz"} <= set(t) for t in service.glossary())
    card = service.source_text({"kind": "item", "ref": service.examples()[0]["answer"]
                                ["citations"][0]["ref"]})
    assert card["text"]


def test_warm_up_loads_each_model_once_and_never_raises(monkeypatch):
    from types import SimpleNamespace
    loaded = []
    llm = SimpleNamespace(warm_up=lambda: loaded.append("llm"))
    pipeline = SimpleNamespace(llm=llm, router=SimpleNamespace(llm=llm))   # one shared model
    service.configure(offline=False, pipeline=pipeline)
    try:
        service.warm_up()
        assert loaded == ["llm"]

        def broken():
            raise ConnectionError("ollama is down")
        service.configure(pipeline=SimpleNamespace(llm=SimpleNamespace(warm_up=broken),
                                                   router=None))
        service.warm_up()                                # logged, not raised
    finally:
        service._state["pipeline"] = None


def test_every_source_has_an_owner_and_a_review_date():
    from datetime import date
    reviews = service.data_reviews(today=date(2026, 11, 11))
    assert {r["source"] for r in reviews} >= {"schedule_csv", "annex2026", "guide2018"}
    assert all(r["owner"] and r["next_review"] > r["last_reviewed"] for r in reviews)
    assert not any(r["overdue"] for r in reviews)
    later = service.data_reviews(today=date(2026, 12, 15))
    assert {r["source"] for r in later if r["overdue"]} == {"schedule_csv", "glossary"}
    assert "data_review_overdue" in service.health()


def wait_until(condition, seconds=5.0):
    import time
    deadline = time.monotonic() + seconds
    while not condition():
        assert time.monotonic() < deadline, "timed out"
        time.sleep(0.005)


class Recording:
    """A pipeline stand-in that reports two stages and returns a recorded answer."""
    def __init__(self, gate=None):
        self.gate = gate

    def answer(self, question, progress=None, **kwargs):
        if self.gate:
            self.gate.wait(5)
        for stage in ("route", "write"):
            progress and progress(stage)
        return service.examples()[0]["answer"]


def test_progress_reports_the_stages_and_a_wait_in_the_queue():
    import threading
    seen = []
    service.configure(offline=False, pipeline=Recording())
    try:
        service.ask("Where do batteries go?", progress=seen.append)
        assert seen == ["route", "write"]

        release = threading.Event()
        service.configure(pipeline=Recording(gate=release))
        first = threading.Thread(target=service.ask, args=("first question",))
        first.start()
        wait_until(service._lock.locked)
        waiting = []
        second = threading.Thread(target=service.ask, args=("second question",),
                                  kwargs={"progress": waiting.append})
        second.start()
        wait_until(lambda: waiting)
        assert waiting == ["queued"]                     # told before it waits
        release.set()
        first.join(5)
        second.join(5)
        assert waiting == ["queued", "route", "write"] and not service._lock.locked()
    finally:
        service._state["pipeline"] = None


def test_a_broken_progress_callback_does_not_break_the_answer():
    def broken(stage):
        raise RuntimeError("the status box is gone")
    service.configure(offline=False, pipeline=Recording())
    try:
        answer = service.ask("Where do batteries go?", progress=broken)
    finally:
        service._state["pipeline"] = None
    assert answer["status"] == service.examples()[0]["answer"]["status"]


def test_loading_is_reported_before_the_pipeline_is_built(monkeypatch):
    seen = []
    monkeypatch.setattr(service, "_pipeline", lambda: Recording())
    service.configure(offline=False)
    service.ask("Where do batteries go?", progress=seen.append)
    assert seen == ["loading", "route", "write"]

    seen.clear()                                  # the warm-up holds the lock: still loading
    with service._lock:
        import threading
        waiting = threading.Thread(target=service.ask, args=("q",),
                                   kwargs={"progress": seen.append})
        waiting.start()
        wait_until(lambda: seen)
        assert seen == ["loading"]
    waiting.join(5)
    assert seen == ["loading", "loading", "route", "write"]


def test_offline_demo_can_show_the_stages(offline, monkeypatch):
    seen = []
    service.ask("anything", progress=seen.append)
    assert seen == []                                    # no delay set: instant, no stages
    monkeypatch.setattr(service, "OFFLINE_DELAY_S", 0.001)
    answer = service.ask(service.examples()[0]["question"], progress=seen.append)
    assert seen == list(service.OFFLINE_STAGES) and answer == service.examples()[0]["answer"]


def test_health_asks_ollama_at_most_every_few_seconds(monkeypatch):
    calls = []

    class Response:
        status = 200
        def __enter__(self):
            return self
        def __exit__(self, *exc):
            return False

    monkeypatch.setattr(service, "urlopen", lambda url, timeout: calls.append(url) or Response())
    service.configure(offline=False)                    # also forgets the last check
    assert service.health()["ollama"] and service.health()["ollama"]
    assert len(calls) == 1
    monkeypatch.setattr(service, "HEALTH_TTL_S", 0.0)
    service.health()
    assert len(calls) == 2
    assert service.pipeline_settings() is None          # nothing loaded, nothing loads
    service.configure(offline=True)
    assert not service.health()["ollama"] and len(calls) == 2
    service.configure(offline=False)
