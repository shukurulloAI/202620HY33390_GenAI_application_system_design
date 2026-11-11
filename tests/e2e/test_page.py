"""The website in a browser: accessibility (axe-core), the phone layout, languages, the area
pickers and the question flow, against the offline demo (conftest.py)."""
from __future__ import annotations

import os
from pathlib import Path

import pytest

axe = pytest.importorskip("axe_playwright_python.sync_playwright")
playwright_errors = pytest.importorskip("playwright.sync_api")

from app.ui import state  # noqa: E402
from rag import service  # noqa: E402
from rag.texts import PAGE  # noqa: E402

pytestmark = pytest.mark.e2e

EN = PAGE["en"]
COMBINED = "Where does a pizza box go, and when is paper collected?"  # bin, steps, handoff
SCHEDULE = "When can I put out food waste?"                           # zone card, stale data
SIZES = {"desktop": (1280, 2600), "phone": (375, 4200)}   # tall: Streamlit scrolls inside


def ask(page, question: str, labels: dict = EN) -> None:
    page.get_by_label(labels["question_label"]).fill(question)
    page.wait_for_timeout(300)        # a click during the rerun the typing starts can be lost
    page.get_by_role("button", name=labels["submit"]).click()
    page.get_by_text(labels["helpful"]).wait_for(timeout=30000)


def open_list(page, label: str) -> list[str]:
    """Open a select box and return its options. A click that lands while the page is still
    rerunning is lost, so try again."""
    for _ in range(5):
        page.get_by_role("combobox", name=label).click()
        try:
            page.get_by_role("option").first.wait_for(timeout=2000)
            return page.get_by_role("option").all_inner_texts()
        except playwright_errors.TimeoutError:
            page.keyboard.press("Escape")
    pytest.fail(f"the {label!r} list does not open")


def choose(page, label: str, option: str) -> None:
    open_list(page, label)
    page.keyboard.type(option)
    page.keyboard.press("Enter")
    page.wait_for_timeout(600)                                # the rerun


def violations(page) -> list:
    page.wait_for_timeout(300)                                # transitions settle
    found = axe.Axe().run(page).response["violations"]
    return [(v["id"], v["impact"], [n["target"] for n in v["nodes"]][:3]) for v in found]


@pytest.mark.parametrize("question", [None, COMBINED, SCHEDULE],
                         ids=["home", "item-answer", "schedule-answer"])
@pytest.mark.parametrize("size", list(SIZES))
@pytest.mark.parametrize("scheme", ["light", "dark"])
def test_axe_finds_no_violations_and_nothing_scrolls_sideways(open_page, scheme, size,
                                                              question):
    width, height = SIZES[size]
    page = open_page(width=width, height=height, scheme=scheme)
    if question:
        ask(page, question)
    assert violations(page) == []
    assert not page.evaluate("document.documentElement.scrollWidth > window.innerWidth")
    if (out := os.environ.get("E2E_SCREENSHOTS")) and question == COMBINED:
        Path(out).mkdir(parents=True, exist_ok=True)
        bottom = page.evaluate("Math.max(...[...document.querySelectorAll('textarea, button, "
                               "details, p')].map(e => e.getBoundingClientRect().bottom))")
        page.screenshot(path=str(Path(out) / f"website_{size}_{scheme}.png"),
                        clip={"x": 0, "y": 0, "width": width, "height": min(height, bottom + 40)})


@pytest.mark.parametrize("lang", list(PAGE))
def test_every_language_sets_the_page_language_and_passes_axe(open_page, lang):
    labels = PAGE[lang]
    page = open_page(f"?lang={lang}")
    page.get_by_role("button", name=labels["submit"]).wait_for()
    assert page.evaluate("document.documentElement.lang") == lang   # the screen reader voice
    ask(page, labels["ex1_q"], labels)
    assert violations(page) == []


def test_choosing_a_language_relabels_the_page_and_the_link(open_page):
    page = open_page()
    choose(page, EN["language"], "Tiếng Việt")
    page.get_by_role("button", name=PAGE["vi"]["submit"]).wait_for()
    assert "lang=vi" in page.url
    assert page.evaluate("document.documentElement.lang") == "vi"


def test_districts_follow_the_province(open_page):
    tree = state.location_tree(service.locations())
    page = open_page()
    page.get_by_text(EN["area_heading"]).click()
    choose(page, EN["province"], "부산광역시")
    shown = open_list(page, EN["district"])
    page.keyboard.press("Escape")
    busan = [d["label"] + ("" if d["has_data"] else f" - {EN['no_data']}")
             for d in tree["부산광역시"]]
    assert shown == [EN["not_selected"], *busan]


def test_the_question_stays_and_the_inputs_wait_while_it_is_answered(open_page):
    """Regression: after "type, then click", the disabled box showed empty and the text was
    lost. The status box names each stage (the offline demo reports them slowly here)."""
    question = "Where do I throw away a pizza box?"
    page = open_page()
    box = page.get_by_label(EN["question_label"])
    box.fill(question)
    page.get_by_role("button", name=EN["submit"]).click()
    page.get_by_text(EN["stage_retrieve"]).wait_for(timeout=10000)
    assert box.is_disabled() and box.input_value() == question
    assert page.get_by_role("button", name=EN["submit"]).is_disabled()
    page.get_by_text(EN["helpful"]).wait_for(timeout=30000)
    assert not box.is_disabled() and box.input_value() == question


def test_a_question_can_be_asked_with_the_keyboard_alone(open_page):
    page = open_page()
    page.get_by_label(EN["question_label"]).focus()
    page.keyboard.type("Where do I throw away a pizza box?")
    for _ in range(15):
        page.keyboard.press("Tab")
        if page.evaluate("document.activeElement.innerText.trim()") == EN["submit"]:
            break
    else:
        pytest.fail("the button cannot be reached with Tab")
    assert page.evaluate("getComputedStyle(document.activeElement).outlineStyle") != "none" \
        or page.evaluate("getComputedStyle(document.activeElement).boxShadow") != "none"
    page.keyboard.press("Enter")
    page.get_by_text(EN["helpful"]).wait_for(timeout=30000)


@pytest.mark.parametrize("width, beside", [(1440, True), (1024, True), (820, False), (390, False)],
                         ids=["laptop-wide", "laptop", "tablet", "phone"])
def test_the_answer_sits_beside_the_question_on_a_laptop_and_below_it_on_a_phone(
        open_page, width, beside):
    """At most 1040 px wide. Two columns only while both fit (the question at least 320 px,
    the answer 440); on a tablet or a phone the answer comes below, as wide as the question."""
    page = open_page(width=width, height=900)
    ask(page, "Where do I throw away a pizza box?")
    question = page.locator(".st-key-question_panel").bounding_box()
    answer = page.locator(".st-key-answer_panel").bounding_box()
    assert page.locator(".st-key-page").bounding_box()["width"] <= 1040
    if beside:
        assert abs(answer["y"] - question["y"]) < 2
        assert answer["x"] > question["x"] + question["width"]
        assert answer["width"] > question["width"]               # the answer has the wider side
    else:
        assert answer["y"] >= question["y"] + question["height"]
        assert abs(answer["width"] - question["width"]) < 2
    assert page.locator(".bin-sign").is_visible()
    assert not page.evaluate("document.documentElement.scrollWidth > window.innerWidth")


def test_on_a_phone_a_new_answer_is_scrolled_into_view(open_page):
    """On a phone the answer comes below the question, out of sight: the page scrolls to it."""
    page = open_page(width=390, height=844)
    ask(page, "Where do I throw away a pizza box?")
    page.wait_for_function("() => { const top = document.querySelector('.st-key-answer_panel')"
                           ".getBoundingClientRect().top; return top >= 0 && top < innerHeight / 2 }",
                           timeout=5000)
