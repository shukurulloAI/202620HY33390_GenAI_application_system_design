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
        assert at.header[-1].value == TITLES[example["answer"]["status"]]


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


def test_the_neighbourhood_box_says_why_it_has_nothing_to_choose(offline):
    """A district whose data has no neighbourhoods (구로구: one schedule for the whole
    district) used to show an empty list with "Not selected"."""
    at = AppTest.from_file(APP, default_timeout=60)
    at.run()
    captions = lambda: [c.value for c in at.caption]                         # noqa: E731
    assert "Collection days are known for 222 of 224 districts." in captions()
    dong = at.selectbox(key="area_dong")
    assert dong.disabled and dong.options == ["Choose a district first"]
    at.selectbox(key="area_province").select("서울특별시").run()
    at.selectbox(key="area_district").select("구로구").run()
    dong = at.selectbox(key="area_dong")
    assert dong.disabled and dong.options == ["Not needed: the answer covers the whole district"]
    assert any("구로구" in c and "its collection days are in the data." in c for c in captions())
    at.selectbox(key="area_district").select("강서구").run()
    dong = at.selectbox(key="area_dong")
    assert not dong.disabled and dong.options[0] == "Not selected" and "등촌2동" in dong.options
    at.selectbox(key="area_district").select("도봉구").run()
    assert any("no collection data" in c for c in captions())
    tree = state.location_tree(service.locations())
    assert state.dong_prompt(next(d for d in tree["서울특별시"] if d["district"] == "도봉구")) \
        == "not_selected"                                   # no data at all: not "not needed"


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
    assert state.area_request(tree, None, None, None) == none
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


def test_the_page_speaks_every_language(offline):
    from rag.texts import PAGE
    for lang in service.languages():
        at = AppTest.from_file(APP, default_timeout=60)
        at.query_params["lang"] = lang                       # a shared link: ?lang=ru
        at.run()
        assert not at.exception, (lang, at.exception)
        assert at.session_state["lang"] == lang
        assert PAGE[lang]["submit"] in [b.label for b in at.button]
        assert at.text_area(key="question_input").label == PAGE[lang]["question_label"]


def test_choosing_a_language_switches_page_and_answer(offline, monkeypatch):
    from rag.texts import PAGE
    asked = []
    monkeypatch.setattr(service, "ask", lambda **kw: asked.append(kw) or service.examples()[0]
                        ["answer"])
    at = AppTest.from_file(APP, default_timeout=60)
    at.run()
    at.selectbox(key="lang").select("ru").run()
    assert at.query_params["lang"] in ("ru", ["ru"])
    at.text_area(key="question_input").input("Куда выбрасывать батарейки?")
    next(b for b in at.button if b.label == PAGE["ru"]["submit"]).click().run()
    assert asked[-1]["lang"] == "ru"
    assert at.header[-1].value == PAGE["ru"]["title_ANSWER"]


def test_locale_picks_the_starting_language():
    offered = service.languages()
    assert state.pick_lang(None, "ru-RU", offered) == "ru"
    assert state.pick_lang(None, "uz_Latn_UZ", offered) == "uz"
    assert state.pick_lang("vi", "ru-RU", offered) == "vi"            # the link wins
    assert state.pick_lang("xx", "ja-JP", offered) == "en"
    assert state.pick_lang(None, None, offered) == "en"


HOSTILE = '<img src=x onerror=alert(1)>[click](javascript:alert(1)) $x$ :red[red]'


def hostile_answer() -> dict:
    """A recorded schedule answer with markup in every field the page shows."""
    import copy
    example = next(e for e in service.examples()
                   if e["answer"]["status"] == "ANSWER" and e["answer"].get("schedule"))
    a = copy.deepcopy(example["answer"])
    a.update(bin="종량제봉투" + HOSTILE, bin_en="bag" + HOSTILE, answer_text="text" + HOSTILE,
             how_to_prepare=["step" + HOSTILE], notes=["note" + HOSTILE])
    for zone in a["schedule"]["zones"]:
        zone.update(district=HOSTILE, zone=HOSTILE, place=HOSTILE, office=HOSTILE,
                    phone="02-" + HOSTILE, areas=[HOSTILE], no_collection=HOSTILE,
                    data_date=HOSTILE, day_check=[{"allowed": True, "text": HOSTILE}])
        for rule in zone["by_type"].values():
            rule.update(days=HOSTILE, start=HOSTILE, next_dates=[HOSTILE])
    for c in a["citations"]:
        c.update(source=HOSTILE, text=HOSTILE)
    a["handoff"] = {"office": HOSTILE, "phone": "02-" + HOSTILE, "contact": HOSTILE,
                    "korean_sentence": HOSTILE, "checked": [HOSTILE]}
    a["clarify"] = {"kind": "names", "question": HOSTILE, "options": [HOSTILE]}
    return a


def test_markup_in_an_answer_stays_text(offline, monkeypatch):
    import re
    monkeypatch.setattr(service, "ask", lambda **kw: hostile_answer())
    at = submit("anything")
    assert not at.exception
    shown = [*at.markdown, *at.caption, *at.warning, *at.info, *at.header]
    assert any("onerror" in str(m.value) for m in shown)           # it is on the page...
    for m in at.markdown:
        if getattr(m, "allow_html", False):                         # ...never as raw HTML
            assert "onerror" not in m.value and "javascript" not in m.value
    for m in shown:                                                 # ...and only escaped
        value = str(m.value)
        assert not re.search(r"(?<!\\)<img", value), value
        assert not re.search(r"(?<!\\)\]\(javascript", value), value
        assert not re.search(r"(?<!\\):red\[", value), value
        assert "tel:" not in value or re.search(r"\(tel:\+?\d+\)", value), value


def test_text_helpers():
    from app.ui.components import md, tel_href
    assert md("a*b_c [x](y) <b> $1 :red[z]\nnext") == \
        r"a\*b\_c \[x\]\(y\) \<b\> \$1 \:red\[z\]" + "  \nnext"
    assert md(None) == "" and md(3) == "3"
    assert tel_href("02-2286-5114") == "tel:0222865114"
    assert tel_href("+82 2 123") == "tel:+822123"
    assert tel_href("call the office") is None and tel_href(None) is None


def test_a_question_reports_progress_and_then_shows_the_answer(offline, monkeypatch):
    stages = []

    def ask(progress=None, **kw):
        for stage in ("queued", "route", "retrieve", "write"):
            progress(stage)                            # relabels the status box
            stages.append(stage)
        return service.examples()[0]["answer"]
    monkeypatch.setattr(service, "ask", ask)
    at = submit("Where do I throw away a pizza box?")
    assert not at.exception and stages == ["queued", "route", "retrieve", "write"]
    assert at.header[-1].value == TITLES["ANSWER"]
    assert at.session_state["pending"] is None
    assert not at.text_area(key="question_input").disabled           # enabled again


def test_inputs_are_disabled_while_a_question_runs_and_never_stay_stuck(offline, monkeypatch):
    called = []

    def broken(**kw):
        called.append(kw)
        raise RuntimeError("a bug in the page's call")
    monkeypatch.setattr(service, "ask", broken)
    at = AppTest.from_file(APP, default_timeout=60)
    at.run()
    at.text_area(key="question_input").input("Where do I throw away a pizza box?")
    at.session_state["pending"] = {"question": "Where do I throw away a pizza box?",
                                   "lang": "en", "province": None, "district": None,
                                   "dong": None}
    at.run()
    assert called and not at.exception
    assert at.header[-1].value == TITLES["INSUFFICIENT_CONTEXT"]     # a handoff, not a trace
    assert at.session_state["pending"] is None
    assert not at.text_area(key="question_input").disabled            # usable again
    assert not any(b.disabled for b in at.button)


def test_while_answering_every_input_is_disabled(offline, monkeypatch):
    """The run that answers shows the inputs disabled, so no click can interrupt it."""
    from streamlit.runtime.scriptrunner_utils.exceptions import StopException

    def stop_midway(**kw):
        raise StopException()                         # end the run while it is answering
    monkeypatch.setattr(service, "ask", stop_midway)
    at = AppTest.from_file(APP, default_timeout=60)
    at.run()
    at.session_state["pending"] = {"question": "q", "lang": "en", "province": None,
                                   "district": None, "dong": None}
    at.run()
    assert at.text_area(key="question_input").disabled
    assert all(b.disabled for b in at.button)
    assert at.selectbox(key="lang").disabled and at.selectbox(key="area_province").disabled


def test_a_session_over_the_rate_limit_is_asked_to_wait(offline, monkeypatch):
    from rag.texts import PAGE
    monkeypatch.setattr(state, "RATE_LIMIT", 2)
    asked = []
    monkeypatch.setattr(service, "ask", lambda **kw: asked.append(kw) or service.examples()[0]
                        ["answer"])
    at = submit("first")
    for question in ("second", "third"):
        at.text_area(key="question_input").input(question)
        next(b for b in at.button if "Find disposal" in str(b.label)).click().run()
    assert [a["question"] for a in asked] == ["first", "second"]
    assert at.warning[0].value == PAGE["en"]["rate_limited"].format(n=2, minutes=5)


def test_rate_limit_window():
    asked = []
    assert all(state.allow_question(asked, t) for t in range(state.RATE_LIMIT))
    assert not state.allow_question(asked, state.RATE_LIMIT)
    assert state.allow_question(asked, state.RATE_WINDOW_S + 1)        # the oldest expired


def test_maintainer_details_only_with_rag_admin(offline, monkeypatch):
    from datetime import date
    due = service.data_reviews(today=date(2026, 12, 15))           # schedule_csv overdue
    monkeypatch.setattr(service, "data_reviews", lambda today=None: due)
    visitor = AppTest.from_file(APP, default_timeout=60)
    visitor.run()
    text = " ".join(str(e.value) for e in [*visitor.caption, *visitor.markdown, *visitor.warning])
    assert "overdue" not in text and "stewardship" not in text
    assert not [e for e in visitor.expander if "Maintainer" in e.label]
    from rag.texts import PAGE
    from rag.tracing import TRACE_RETENTION_DAYS
    privacy = PAGE["en"]["privacy"].format(days=TRACE_RETENTION_DAYS)
    assert privacy in [c.value for c in visitor.caption]             # what is kept, how long

    monkeypatch.setenv("RAG_ADMIN", "1")
    admin = AppTest.from_file(APP, default_timeout=60)
    admin.run()
    panel = next(e for e in admin.expander if e.label.endswith(" Maintainer"))
    assert "schedule\\_csv" in panel.warning[0].value and not admin.exception


def test_a_source_label_does_not_repeat_its_page_year_or_date(offline):
    for question in ("Where do I throw away a pizza box?", "When can I put out food waste?"):
        example = next(e for e in service.examples() if e["question"] == question)
        at = submit(question)
        labels = [e.label.replace("\\", "") for e in at.expander       # after the icon
                  if e.label.startswith(":material/description: \\[")]
        assert len(labels) == len(example["answer"]["citations"])
        for c, label in zip(example["answer"]["citations"], labels, strict=True):
            assert label.count(f"p. {c['page']}") + label.count(f"p.{c['page']}") <= 1 \
                if c.get("page") else True
            assert label.count(c["data_date"]) == 1 if c.get("data_date") else True


def test_a_busy_site_asks_to_try_again_and_keeps_the_question(offline, monkeypatch):
    from rag.texts import PAGE

    def busy(**kwargs):
        raise service.Busy
    monkeypatch.setattr(service, "ask", busy)
    at = submit("Where do batteries go?")
    assert not at.exception
    assert at.warning[0].value == PAGE["en"]["site_busy"]
    box = at.text_area(key="question_input")
    assert box.value == "Where do batteries go?" and not box.disabled    # ask again in a click
    assert at.session_state.pending is None and at.session_state.result is None


def test_one_visitor_with_many_tabs_shares_one_limit(offline, monkeypatch):
    import streamlit as st

    from rag.texts import PAGE
    st.cache_resource.clear()                                  # a fresh visitor log
    monkeypatch.setattr(state, "VISITOR_LIMIT", 1)
    monkeypatch.setattr(state, "visitor_id", lambda ip, headers, session: "203.0.113.7")
    asked = []
    monkeypatch.setattr(service, "ask", lambda **kw: asked.append(kw) or service.examples()[0]
                        ["answer"])
    submit("first tab")
    second_tab = submit("second tab")                          # a new session, same visitor
    assert [a["question"] for a in asked] == ["first tab"]
    assert second_tab.warning[0].value == PAGE["en"]["rate_limited"].format(n=1, minutes=5)
    st.cache_resource.clear()


def test_visitor_log_and_who_the_visitor_is():
    log = state.VisitorLog()
    assert all(log.allow("a", t) for t in range(state.VISITOR_LIMIT))
    assert not log.allow("a", state.VISITOR_LIMIT) and log.allow("b", state.VISITOR_LIMIT)
    assert log.allow("a", state.RATE_WINDOW_S + state.VISITOR_LIMIT)   # the window moved on
    log.allow("c", 10 * state.RATE_WINDOW_S)
    assert set(log._times) == {"c"}                             # idle visitors are forgotten
    cf = {"CF-Connecting-IP": "8.8.4.4"}
    assert state.visitor_id("1.1.1.1", cf, "s") == "1.1.1.1"    # the public address Streamlit saw
    assert state.visitor_id(None, cf, "s") == "8.8.4.4"         # from this machine (Streamlit: None)
    assert state.visitor_id("2606:4700::1111", None, "s") == "2606:4700::1111"
    for shared in ("::ffff:127.0.0.1", "172.17.0.1", "192.168.65.1", "10.0.0.5", "100.64.0.1"):
        assert state.visitor_id(shared, None, "s") == "s"       # this machine, Docker, LAN, CGNAT
    assert state.visitor_id(None, {"CF-Connecting-IP": "not an ip"}, "s") == "s"
    assert state.visitor_id(None, None, "session-9") == "session-9"
