"""
The parts of the page, as render functions.

Rule: a value from an answer, the district table or the glossary reaches the page only as
escaped Markdown (md()) inside native Streamlit elements. No such value is ever put into
raw HTML, so a broken or hostile field cannot add markup (tests/test_app.py injects one).
The only raw HTML is the static brand and hero, whose page labels are html-escaped too.

`t(key, **args)` is the page label in the chosen language (rag/texts.py PAGE).
"""
from __future__ import annotations

import html
import re
from collections.abc import Callable

import streamlit as st

from rag import service
from rag.texts import PAGE

T = Callable[..., str]
GLOSSARY_LANGS = ("en", "zh", "vi", "uz", "ru")      # the glossary's translated columns
MAX_AREAS_SHOWN = 12
MAX_CLARIFY_OPTIONS = 30


def md(text) -> str:
    """Any text as literal Markdown: escape Markdown characters, keep the line breaks."""
    escaped = re.sub(r"([\\`*_{}\[\]()<>#+\-.!|~:$])", r"\\\1", str(text or ""))
    return escaped.replace("\n", "  \n")


def tel_href(phone: str | None) -> str | None:
    """A tel: link with only digits and '+', or None when there is no number in it."""
    digits = re.sub(r"[^\d+]", "", phone or "")
    return f"tel:{digits}" if re.search(r"\d", digits) else None


def waste_name(waste_type: str, t: T) -> str:
    key = f"waste_{waste_type}"
    return t(key) if key in PAGE["en"] else md(waste_type)


# ---------------------------------------------------------------------------- header

def show_header(t: T) -> None:
    e = html.escape
    st.markdown(
        f'<div class="brand"><div class="brand-icon" aria-hidden="true">♻</div><div>'
        f'<div class="brand-name">{e(t("page_title"))}</div>'
        f'<div class="brand-note">{e(t("brand_note"))}</div></div></div>',
        unsafe_allow_html=True)


def show_hero(t: T) -> None:
    e = html.escape
    st.markdown(
        f'<div class="hero"><div class="hero-copy">'
        f'<p class="hero-label">{e(t("hero_label"))}</p>'
        f'<h1 class="hero-title">{e(t("hero_title"))}</h1>'
        f'<p class="hero-description">{e(t("hero_text"))}</p></div>'
        f'<div class="hero-art" aria-hidden="true"><span>♻</span></div></div>',
        unsafe_allow_html=True)


# ---------------------------------------------------------------------------- answer parts

def show_bin(result: dict, t: T) -> None:
    if not result.get("bin"):
        return
    with st.container(border=True, key="bin_card"):
        st.markdown(f"#### {md(result.get('bin_en') or result['bin'])}")
        st.caption(f"{md(result['bin'])} · {t('bin_note')}")


def show_steps(result: dict, t: T) -> None:
    steps = result.get("how_to_prepare") or []
    if steps:
        st.markdown(f"**{t('prepare')}**")
        st.markdown("\n".join(f"{i}. {md(step)}" for i, step in enumerate(steps, 1)))


def zone_lines(zone: dict, t: T) -> list[str]:
    """One schedule card as Markdown lines (every value escaped)."""
    lines = [f"**{md(zone.get('district'))} · {md(zone.get('zone'))}**"]
    areas = zone.get("areas") or []
    if areas:
        shown = ", ".join(areas[:MAX_AREAS_SHOWN]) + (" …" if len(areas) > MAX_AREAS_SHOWN
                                                      else "")
        lines.append(t("zone_areas", areas=md(shown)))
    if zone.get("place"):
        lines.append(t("zone_where", place=md(zone["place"])))
    for waste_type, rule in (zone.get("by_type") or {}).items():
        when = md(rule.get("days")) if rule.get("days") else t("days_not_listed")
        if rule.get("start"):
            when += f", {md(rule['start'])}–{md(rule.get('end'))}"
        line = f"**{waste_name(waste_type, t)}:** {when}"
        if rule.get("next_dates"):
            line += " · " + t("zone_next", dates=md(", ".join(rule["next_dates"])))
        lines.append(line)
    for check in zone.get("day_check") or []:
        lines.append(("✅ " if check.get("allowed") else "⛔ ") + md(check.get("text")))
    if zone.get("no_collection"):
        lines.append(t("zone_no_collection", days=md(zone["no_collection"])))
    office = " ".join(str(x) for x in (zone.get("office"), zone.get("phone")) if x)
    if office:
        lines.append(t("zone_office", office=md(office)))
    return lines


def show_schedule(result: dict, t: T) -> None:
    zones = (result.get("schedule") or {}).get("zones") or []
    if not zones:
        return
    st.markdown(f"**{t('collection')}**")
    for i, zone in enumerate(zones):
        with st.container(border=True, key=f"zone_{i}"):
            st.markdown("  \n".join(zone_lines(zone, t)))
            if zone.get("stale"):
                st.warning(t("stale"))
            st.caption(t("data_as_of", date=md(zone.get("data_date")) or t("date_unknown")))


def show_sources(result: dict, t: T) -> None:
    citations = result.get("citations") or []
    if not citations:
        return
    st.markdown(f"**{t('sources')}**")
    for c in citations:
        where = " · ".join(str(x) for x in (
            t("source_page", page=c["page"]) if c.get("page") else None,
            c.get("year"),
            t("source_data_date", date=c["data_date"]) if c.get("data_date") else None) if x)
        label = f"[{c.get('n')}] {c.get('source') or ''}" + (f" · {where}" if where else "")
        with st.expander(md(label)):
            st.text(service.source_text(c)["text"])


def show_handoff(result: dict, t: T) -> None:
    handoff = result.get("handoff")
    if not handoff:
        return
    with st.container(border=True, key="handoff"):
        st.markdown(f"**{t('ask_person')}**")
        contact = md(handoff.get("contact"))
        href = tel_href(handoff.get("phone"))
        if href:
            contact += f" · [{md(handoff['phone'])}]({href})"
        if contact:
            st.markdown(contact)
        if handoff.get("korean_sentence"):
            st.caption(t("show_staff"))
            st.code(handoff["korean_sentence"], language=None, wrap_lines=True)
        if handoff.get("checked"):
            st.caption(t("checked", items=md("; ".join(handoff["checked"]))))


def show_clarify(result: dict, t: T, on_pick: Callable[[str, str], None],
                 disabled: bool = False) -> None:
    """The clarify question and one button per option; on_pick(kind, option) asks again."""
    clarify = result.get("clarify")
    if not clarify:
        return
    st.info(md(clarify.get("question")))
    options = (clarify.get("options") or [])[:MAX_CLARIFY_OPTIONS]
    if clarify.get("kind") == "district" or not options:
        st.caption(t("choose_district"))
        return
    columns = st.columns(min(3, len(options)))
    for i, option in enumerate(options):
        columns[i % len(columns)].button(
            md(option), key=f"clarify_{i}_{option}", width="stretch", disabled=disabled,
            on_click=on_pick, args=(clarify["kind"], option))


def save_rating(trace_id: str, rating: str) -> None:
    service.save_feedback(trace_id, rating, st.session_state.get(f"comment_{trace_id}", ""))
    st.session_state.feedback[trace_id] = rating


def show_feedback(result: dict, t: T, disabled: bool = False) -> None:
    st.divider()
    st.markdown(f"**{t('helpful')}**")
    trace_id = result["trace_id"]
    if trace_id in st.session_state.feedback:
        st.caption(t("thanks"))
        return
    st.text_input(t("comment"), key=f"comment_{trace_id}", max_chars=300, disabled=disabled)
    up, down, _ = st.columns([1, 1, 3])
    for column, rating, label, icon in ((up, "up", t("yes"), "👍"), (down, "down", t("no"), "👎")):
        column.button(label, icon=icon, key=f"{rating}_{trace_id}", width="stretch",
                      disabled=disabled, on_click=save_rating, args=(trace_id, rating))


def show_result(result: dict, request: dict, t: T, on_pick: Callable[[str, str], None],
                disabled: bool = False) -> None:
    """One answer, by status (docs/WEBSITE.md "What to show, by status")."""
    with st.container(border=True, key="answer_panel"):
        st.caption(t("your_question"))
        st.markdown(md(request.get("question")))
        status = result["status"]
        st.subheader(t(f"title_{status}"))
        text = md(result.get("answer_text"))
        if status == "ANSWER":
            show_bin(result, t)
            st.markdown(text)
            show_steps(result, t)
            show_schedule(result, t)
            show_clarify(result, t, on_pick, disabled)
            show_handoff(result, t)
            show_sources(result, t)
        elif status == "CLARIFY":
            st.markdown(text)
            show_clarify(result, t, on_pick, disabled)
        elif status == "INSUFFICIENT_CONTEXT":
            st.warning(text)
            show_handoff(result, t)
        else:
            st.info(text)
        for note in result.get("notes") or []:
            st.caption(md(note))
        show_feedback(result, t, disabled)


# ---------------------------------------------------------------------------- page bottom

def show_glossary(lang: str, t: T, languages: dict[str, str]) -> None:
    with st.expander(t("glossary")):
        column = lang if lang in GLOSSARY_LANGS else "en"
        rows = [f"| {md(term['ko'])} | {md(term.get(column) or term['en'])} |"
                for term in service.glossary()]
        st.markdown(f"| 한국어 | {md(languages.get(column, 'English'))} |\n|---|---|\n"
                    + "\n".join(rows))
        if column != "en":
            st.caption(t("glossary_unchecked"))
