"""
Waste-Sorting Assistant: the website (Streamlit), connected to the RAG system through
rag/service.py (docs/WEBSITE.md). Its parts are in app/ui/: state.py (the rules, testable
without a browser), components.py (render functions) and style.css.

    streamlit run app/streamlit_app.py                  # full system (Ollama + index)
    RAG_OFFLINE=1 streamlit run app/streamlit_app.py    # recorded answers, no models

A question is answered in two runs of this script: the button only stores the request
(`pending`), and the next run shows every input disabled while it answers. So nothing the
user clicks can interrupt a question halfway.
"""
import json
import sys
import threading
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))   # run from any folder

from app.ui import components as ui  # noqa: E402
from app.ui import state  # noqa: E402
from rag import service  # noqa: E402
from rag.texts import page_text  # noqa: E402

STYLE = Path(__file__).parent / "ui" / "style.css"


@st.cache_data(show_spinner=False)
def location_tree():
    return state.location_tree(service.locations())


@st.cache_resource(show_spinner=False)
def start_warm_up() -> bool:
    """Once per server process: load the models in the background while the page renders."""
    threading.Thread(target=service.warm_up, name="warm-up", daemon=True).start()
    return True


languages = service.languages()
tree = location_tree()
state.init(st.session_state, tree)
if "lang" not in st.session_state:
    st.session_state.lang = state.pick_lang(st.query_params.get("lang"), st.context.locale,
                                            languages)
lang = st.session_state.lang
busy = st.session_state.pending is not None


def t(key: str, **args) -> str:
    return page_text(key, lang, **args)


st.set_page_config(page_title=t("page_title"), page_icon="♻️", layout="centered")
st.html(STYLE)
st.html(f"<script>document.documentElement.lang = {json.dumps(lang)};</script>",
        unsafe_allow_javascript=True)                 # screen readers pick the right voice


# ---------- CALLBACKS (run before the script, with the latest widget values) ----------
def on_lang() -> None:
    st.query_params["lang"] = st.session_state.lang


def choose_question(text: str) -> None:
    st.session_state.question_input = text


def reset_district() -> None:
    """A new province: its own districts, nothing chosen yet."""
    st.session_state.area_district = None
    st.session_state.area_dong = None


def reset_dong() -> None:
    st.session_state.area_dong = None


def submit_question() -> None:
    s = st.session_state
    question = (s.question_input or "").strip()
    if not question:
        s.flash = "empty_question"
        return
    s.pending = {"question": question, "lang": s.lang,
                 **state.area_request(tree, s.area_province, s.area_district, s.area_dong)}


def pick_option(kind: str, option: str) -> None:
    """A clarify button: the same question again, with the chosen place filled in."""
    request = st.session_state.request or {}
    if kind == "province":
        province, _, district = option.partition(" ")
        area = {"province": province, "district": district, "dong": None}
    else:
        area = {"province": request.get("province"), "district": request.get("district"),
                "dong": option}
    st.session_state.pending = {"question": request["question"], "lang": request["lang"],
                                **area}


# ---------- HEADER ----------
brand, chooser = st.columns([3, 1], vertical_alignment="center")
with brand:
    ui.show_header(t)
with chooser:
    st.selectbox(t("language"), list(languages), key="lang", on_change=on_lang,
                 format_func=lambda code: languages[code], disabled=busy)
ui.show_hero(t)

health = service.health()
if health["ollama"] and not health["offline"]:
    start_warm_up()
if health["offline"]:
    status_line = t("status_offline")
elif health["ollama"]:
    status_line = t("status_live")
else:
    status_line = t("status_down")
if health["data_review_overdue"]:
    status_line += (" Data review overdue: " + ", ".join(health["data_review_overdue"])
                    + " (data/manual/stewardship.json).")
st.caption(status_line)


# ---------- EXAMPLE QUESTIONS ----------
st.subheader(t("examples_heading"))
for column, n in zip(st.columns(3), (1, 2, 3), strict=True):
    column.button(t(f"ex{n}_label"), icon=t(f"ex{n}_icon"), key=f"example_{n}",
                  width="stretch", disabled=busy, on_click=choose_question,
                  args=(t(f"ex{n}_q"),))


# ---------- QUESTION ----------
# No st.form: a form does not rerun when a selectbox changes, so the district list would
# stay on the old province (a mismatched pair finds no data).
with st.container(key="question_panel"):
    st.subheader(t("ask_heading"))
    st.text_area(t("question_label"), placeholder=t("question_placeholder"), height=105,
                 key="question_input", max_chars=service.MAX_QUESTION_CHARS, disabled=busy)
    with st.expander(t("area_heading")):
        st.caption(t("area_help"))
        st.selectbox(t("province"), [None, *tree], key="area_province", disabled=busy,
                     on_change=reset_district,
                     format_func=lambda p: t("not_selected") if p is None else p)
        districts = {d["district"]: d for d in tree.get(st.session_state.area_province, [])}
        st.selectbox(
            t("district"), [None, *districts], key="area_district", disabled=busy,
            on_change=reset_dong,
            format_func=lambda name: t("not_selected") if name is None else
            districts[name]["label"] + ("" if districts[name]["has_data"]
                                        else f" - {t('no_data')}"))
        chosen = districts.get(st.session_state.area_district)
        st.selectbox(t("dong"), [None, *(chosen["areas"] if chosen else [])], key="area_dong",
                     disabled=busy, format_func=lambda d: t("not_selected") if d is None else d)
    st.button(t("submit"), type="primary", width="stretch", disabled=busy,
              on_click=submit_question)
    if st.session_state.flash:
        st.warning(t(st.session_state.flash))
        st.session_state.flash = None


# ---------- ANSWER ----------
if busy:
    request = st.session_state.pending
    first = not health["pipeline_loaded"] and not health["offline"]
    with st.spinner(t("stage_loading") if first else t("stage_retrieve")):
        try:
            result = service.ask(**request)
        finally:
            st.session_state.pending = None
    st.session_state.request, st.session_state.result = request, result
    st.rerun()                                         # inputs enabled again

if st.session_state.result:
    ui.show_result(st.session_state.result, st.session_state.request or {}, t, pick_option)


# ---------- BOTTOM ----------
st.write("")
ui.show_glossary(lang, t, languages)
st.caption(t("footer"))
