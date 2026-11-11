"""
Waste-Sorting Assistant: the website (Streamlit), connected to the RAG system through
rag/service.py (docs/WEBSITE.md). Its parts are in app/ui/: state.py (the rules, testable
without a browser), components.py (render functions) and style.css.

    streamlit run app/streamlit_app.py                  # full system (Ollama + index)
    RAG_OFFLINE=1 streamlit run app/streamlit_app.py    # recorded answers, no models
    RAG_ADMIN=1 streamlit run app/streamlit_app.py      # + a maintainer panel at the bottom

A question is answered in two runs of this script: the button only stores the request
(`pending`), and the next run shows every input disabled while it answers. So nothing the
user clicks can interrupt a question halfway.
"""
import json
import logging
import os
import sys
import threading
import time
import uuid
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))   # run from any folder

from app.ui import components as ui  # noqa: E402
from app.ui import state  # noqa: E402
from rag import service  # noqa: E402
from rag.texts import page_text  # noqa: E402

try:                                   # what Streamlit raises to rerun or stop a script
    from streamlit.runtime.scriptrunner_utils.exceptions import ScriptControlException
except ImportError:                    # moved: then nothing is caught, as before
    ScriptControlException = ()

STYLE = Path(__file__).parent / "ui" / "style.css"
ADMIN = os.environ.get("RAG_ADMIN") == "1"     # models, digests, data reviews: not for visitors
log = logging.getLogger("app")


@st.cache_data(show_spinner=False)
def location_tree():
    return state.location_tree(service.locations())


@st.cache_resource(show_spinner=False)
def visitor_log() -> state.VisitorLog:
    return state.VisitorLog()                    # one per server process, for every session


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
# The question box loses what was typed when it is disabled right after "type, then click"
# (Streamlit 1.67 in Chromium; tests/e2e). Setting it through the session state makes
# Streamlit send the text to the browser again.
if (shown := st.session_state.pop("show_question", None)) is not None:
    st.session_state.question_input = shown


def t(key: str, **args) -> str:
    return page_text(key, lang, **args)


st.set_page_config(page_title=t("page_title"), page_icon=ui.favicon_svg(), layout="wide")
st.markdown(f"<style>{STYLE.read_text(encoding='utf-8')}</style>", unsafe_allow_html=True)
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


def queue(request: dict) -> None:
    """Answer `request` on the next run, unless this tab or this visitor is over its limit."""
    now = time.time()
    visitor = state.visitor_id(st.context.ip_address, st.context.headers,
                               st.session_state.visitor)
    if not state.allow_question(st.session_state.asked, now):
        st.session_state.flash = ("rate_limited", state.rate_message_args())
    elif not visitor_log().allow(visitor, now):
        st.session_state.flash = ("rate_limited", state.rate_message_args(state.VISITOR_LIMIT))
    else:
        st.session_state.pending = request


def submit_question() -> None:
    s = st.session_state
    question = (s.question_input or "").strip()
    if not question:
        s.flash = ("empty_question", {})
        return
    s.question_input = question                      # shown while it is answered
    queue({"question": question, "lang": s.lang,
           **state.area_request(tree, s.area_province, s.area_district, s.area_dong)})


def pick_option(kind: str, option: str) -> None:
    """A clarify button: the same question again, with the chosen place filled in."""
    request = st.session_state.request or {}
    if kind == "province":
        province, _, district = option.partition(" ")
        area = {"province": province, "district": district, "dong": None}
    else:
        area = {"province": request.get("province"), "district": request.get("district"),
                "dong": option}
    queue({"question": request["question"], "lang": request["lang"], **area})


# ---------- PAGE ----------
# A wide page with one centred column (at most --page-width in style.css): on a computer the
# question and the answer sit side by side, so the answer appears without scrolling; on a
# phone the columns stack.
page = st.container(key="page")
with page:
    with st.container(key="topbar"):
        brand, chooser = st.columns([4, 1], vertical_alignment="center")
        with brand:
            ui.show_header(t)
        with chooser:
            st.selectbox(f":material/language: {t('language')}", list(languages), key="lang",
                         on_change=on_lang, format_func=lambda code: languages[code],
                         disabled=busy)

    health = service.health()
    if health["ollama"] and not health["offline"]:
        start_warm_up()
    ui.show_hero(t, "offline" if health["offline"] else "live" if health["ollama"] else "down")

    with st.container(key="examples"):
        st.header(t("examples_heading"))
        for column, n in zip(st.columns(3), (1, 2, 3), strict=True):
            column.button(t(f"ex{n}_label"), icon=t(f"ex{n}_icon"), key=f"example_{n}",
                          width="stretch", disabled=busy, on_click=choose_question,
                          args=(t(f"ex{n}_q"),))

    ask_column, answer_column = st.columns([5, 7], gap="large")


# ---------- QUESTION ----------
# No st.form: a form does not rerun when a selectbox changes, so the district list would
# stay on the old province (a mismatched pair finds no data).
with ask_column, st.container(key="question_panel", border=True):
    st.header(t("ask_heading"))
    st.text_area(t("question_label"), placeholder=t("question_placeholder"), height=105,
                 key="question_input", max_chars=service.MAX_QUESTION_CHARS, disabled=busy)
    with st.expander(f":material/location_on: {t('area_heading')}"):
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
        areas = chosen["areas"] if chosen else []
        # An empty list says why: no district yet, or a district whose data has no
        # neighbourhoods (39 of 222: one schedule for the whole district, or zones the answer
        # lists one by one), so there is nothing to choose.
        unset = state.dong_prompt(chosen)
        st.selectbox(t("dong"), [None, *areas], key="area_dong", disabled=busy or not areas,
                     format_func=lambda d: t(unset) if d is None else d)
    st.button(t("submit"), type="primary", width="stretch", disabled=busy,
              on_click=submit_question)
    days = health["trace_retention_days"]
    st.caption(t("privacy", days=days) if days > 0 else t("privacy_kept"))
    if st.session_state.flash:
        key, args = st.session_state.flash
        st.warning(t(key, **args), icon=":material/info:")
        st.session_state.flash = None


# ---------- ANSWER ----------
def answer_pending() -> None:
    """Answer the stored request in a status box that names each stage as it starts
    ("Reading your question…", "Searching the official guides…", or "Another question is
    being answered. Yours is next…"), then rerun with the inputs enabled again.
    service.ask() never raises for a question; if this code fails anyway, the user gets the
    same "not available" answer with a handoff, never a page with every input disabled."""
    request = st.session_state.pending
    with st.status(t("stage_route")) as box:
        def update(stage: str) -> None:
            try:
                box.update(label=t(f"stage_{stage}"))
            except ScriptControlException:   # a rerun request: this run reruns anyway
                pass
        try:
            result = service.ask(**request, progress=update)
        except service.Busy:                 # too many waiting: ask again, keep the last answer
            st.session_state.pending = None
            st.session_state.flash = ("site_busy", {})
            st.session_state.show_question = request["question"]
            st.rerun()
        except Exception:
            trace_id = str(uuid.uuid4())
            log.exception("answering failed in the page (%s)", trace_id)
            result = service.unavailable_answer(request.get("lang"), request.get("district"),
                                                request.get("dong"), trace_id)
        finally:
            st.session_state.pending = None
        box.update(label=t("stage_done"), state="complete")
    st.session_state.request, st.session_state.result = request, result
    st.session_state.show_question = request["question"]
    st.rerun()


with answer_column:
    if busy:
        answer_pending()
    if st.session_state.result:
        ui.show_result(st.session_state.result, st.session_state.request or {}, t, pick_option)
    else:
        ui.show_placeholder(t)


# ---------- BOTTOM ----------
with page:
    st.write("")
    ui.show_glossary(lang, t, languages)
    st.caption(t("footer"))
    if ADMIN:
        ui.show_maintainer(health, service.data_reviews(), service.pipeline_settings())
