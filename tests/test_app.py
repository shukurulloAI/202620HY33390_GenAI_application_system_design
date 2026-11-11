"""The website renders every recorded answer (offline mode: no Ollama, no models)."""
import pytest

pytest.importorskip("streamlit")

from streamlit.testing.v1 import AppTest  # noqa: E402

from app.ui import state  # noqa: E402
from rag import paths, service  # noqa: E402

APP = str(paths.ROOT / "app" / "streamlit_app.py")

TITLES = {"ANSWER": "Disposal guide", "CLARIFY": "One more detail",
          "INSUFFICIENT_CONTEXT": "I can't answer this one safely",
          "OUT_OF_SCOPE": "Outside what I can help with"}


@pytest.fixture
def offline(monkeypatch, tmp_path):
    monkeypatch.setattr(service, "FEEDBACK_FILE", tmp_path / "feedback.jsonl")
    service.configure(offline=True)
    yield tmp_path
    service.configure(offline=False)


def submit(question: str) -> AppTest:
    at = AppTest.from_file(APP, default_timeout=60)
    at.run()
    at.text_area(key="question_input").input(question)
    next(b for b in at.button if "Find disposal" in str(b.label)).click().run()
    return at


def test_every_example_renders(offline):
    for example in service.examples():
        at = submit(example["question"])
        assert not at.exception, at.exception[0].value
        assert at.subheader[-1].value == TITLES[example["answer"]["status"]]


def test_abstention_shows_the_korean_sentence(offline):
    example = next(e for e in service.examples()
                   if e["answer"]["status"] == "INSUFFICIENT_CONTEXT")
    at = submit(example["question"])
    assert at.code[0].value == example["answer"]["handoff"]["korean_sentence"]


def test_feedback_is_saved(offline):
    at = submit(service.examples()[0]["question"])
    next(b for b in at.button if "Yes" in str(b.label)).click().run()
    saved = (offline / "feedback.jsonl").read_text(encoding="utf-8")
    assert '"rating": "up"' in saved and service.examples()[0]["answer"]["trace_id"] in saved


def test_districts_follow_the_province(offline, monkeypatch):
    """Regression: inside st.form the district list stayed on Seoul after choosing 부산."""
    tree = state.location_tree(service.locations())
    asked = []
    monkeypatch.setattr(service, "ask", lambda **kw: asked.append(kw) or service.examples()[0]
                        ["answer"])
    at = AppTest.from_file(APP, default_timeout=60)
    at.run()
    at.selectbox(key="area_district").select_index(1).run()          # a Seoul district
    at.selectbox(key="area_province").select("부산광역시").run()
    busan = [d["label"] for d in tree["부산광역시"]]
    options = at.selectbox(key="area_district").options[1:]
    assert [o.removesuffix(" - no data") for o in options] == busan
    assert at.selectbox(key="area_district").value is None              # the Seoul choice is gone
    at.selectbox(key="area_district").select_index(1).run()
    at.text_area(key="question_input").input("When is food waste collected?")
    next(b for b in at.button if "Find disposal" in str(b.label)).click().run()
    assert asked[-1]["province"] == "부산광역시"
    assert asked[-1]["district"] == tree["부산광역시"][0]["district"]


def test_a_mismatched_area_is_not_sent():
    tree = state.location_tree(service.locations())
    seoul = next(d for d in tree["서울특별시"] if d["areas"])
    none = {"province": None, "district": None, "dong": None}
    assert state.area_request(tree, "부산광역시", "강남구", None) == none
    assert state.area_request(tree, state.NOT_SELECTED, None, None) == none
    assert state.area_request(tree, "서울특별시", seoul["district"], "없는동") == {
        "province": "서울특별시", "district": seoul["district"], "dong": None}
    assert state.area_request(tree, "서울특별시", seoul["district"], seoul["areas"][0])["dong"] \
        == seoul["areas"][0]


def test_a_clarify_option_asks_again(offline, monkeypatch):
    example = next(e for e in service.examples() if (e["answer"].get("clarify") or {})
                   .get("options"))
    asked = []
    real_ask = service.ask
    monkeypatch.setattr(service, "ask", lambda **kw: asked.append(kw) or real_ask(**kw))
    at = submit(example["question"])
    option = example["answer"]["clarify"]["options"][0]
    next(b for b in at.button if b.label == option).click().run()
    assert not at.exception
    assert asked[-1]["question"] == example["question"]
    assert option.split(" ")[-1] in (asked[-1]["district"], asked[-1]["dong"])
