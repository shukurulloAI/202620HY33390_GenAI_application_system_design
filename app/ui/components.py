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

STATUSES = ("live", "offline", "down")
# The icons are Material Symbols Rounded, the set Streamlit itself uses (":material/<name>:"),
# so they look the same on every device and need no download. The app icon is that set's
# "recycling" symbol as an SVG path (Apache License 2.0), drawn on a 960 x 960 grid.
RECYCLING_PATH = (
    "M389 334 457 221 398 123Q386 103 363.5 103Q341 103 329 123L252 252Q244 266 247.5 "
    "282.5Q251 299 265 307L334 348Q348 356 364.5 352Q381 348 389 334ZM755 640 687 527Q678 "
    "513 682.5 496.5Q687 480 701 472L771 432Q785 424 801 428Q817 432 825 446L869 519Q880 "
    "536 881 557Q882 578 872 596Q862 616 842.5 628Q823 640 800 640ZM606 886 508 788Q496 776 "
    "496 760Q496 744 508 732L606 634Q616 624 628 629Q640 634 640 648V680H830L772 796Q761 "
    "816 742 828Q723 840 700 840H640V872Q640 886 628 891Q616 896 606 886ZM253 840Q233 840 "
    "216.5 829.5Q200 819 192 802Q184 786 184.5 768.5Q185 751 194 736L228 680H360Q377 680 "
    "388.5 691.5Q400 703 400 720V800Q400 817 388.5 828.5Q377 840 360 840ZM154 726 89 596Q80 "
    "578 80.5 557.5Q81 537 92 519L108 492L81 476Q70 469 72 455.5Q74 442 87 439L220 406Q236 "
    "402 250.5 410.5Q265 419 269 435L302 569Q305 582 294 590Q283 598 272 591L245 574ZM655 "
    "374 522 341Q509 338 507.5 324.5Q506 311 517 304L544 288L419 80H560Q581 80 599.5 "
    "90.5Q618 101 629 119L681 206L707 190Q718 183 729 191Q740 199 737 212L704 345Q700 361 "
    "685.5 369.5Q671 378 655 374Z")
GRADIENT = ("#34c759", "#0a84ff")    # Apple green to Apple blue, as in style.css


def icon_svg() -> str:
    """The recycling symbol in the current text colour (inside the app icon tile)."""
    return ('<svg viewBox="0 0 960 960" focusable="false" aria-hidden="true">'
            f'<path fill="currentColor" d="{RECYCLING_PATH}"/></svg>')


def favicon_svg() -> str:
    """The app icon for the browser tab: the symbol in white on the green-blue tile."""
    start, end = GRADIENT
    return ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64">'
            '<defs><linearGradient id="g" x1="0.2" y1="0" x2="0.8" y2="1">'
            f'<stop offset="0" stop-color="{start}"/><stop offset="1" stop-color="{end}"/>'
            '</linearGradient></defs><rect width="64" height="64" rx="14" fill="url(#g)"/>'
            '<svg x="11" y="11" width="42" height="42" viewBox="0 0 960 960">'
            f'<path fill="#ffffff" d="{RECYCLING_PATH}"/></svg></svg>')


def show_header(t: T) -> None:
    e = html.escape
    st.markdown(
        f'<div class="brand"><div class="brand-icon">{icon_svg()}</div><div>'
        f'<div class="brand-name">{e(t("page_title"))}</div>'
        f'<div class="brand-note">{e(t("brand_note"))}</div></div></div>',
        unsafe_allow_html=True)


def show_hero(t: T, status: str) -> None:
    """The app icon, the headline and a pill saying whether answers are live (`status` is
    one of STATUSES)."""
    if status not in STATUSES:
        raise ValueError(f"unknown status {status!r}")
    e = html.escape
    st.markdown(
        f'<div class="hero"><div class="hero-icon">{icon_svg()}</div>'
        f'<p class="hero-label">{e(t("hero_label"))}</p>'
        f'<h1 class="hero-title">{e(t("hero_title"))}</h1>'
        f'<p class="hero-description">{e(t("hero_text"))}</p>'
        f'<div class="hero-status hero-status-{status}">'
        f'<span class="hero-status-dot" aria-hidden="true"></span>'
        f'{e(t(f"status_{status}"))}</div></div>',
        unsafe_allow_html=True)


# ---------------------------------------------------------------------------- answer parts

def show_bin(result: dict, t: T) -> None:
    if not result.get("bin"):
        return
    with st.container(border=True, key="bin_card"):
        st.markdown(f"### :material/delete: {md(result.get('bin_en') or result['bin'])}")
        st.caption(f"{md(result['bin'])} · {t('bin_note')}")


def show_steps(result: dict, t: T) -> None:
    steps = result.get("how_to_prepare") or []
    if steps:
        st.markdown(f":material/checklist: **{t('prepare')}**")
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
        lines.append((":green[:material/check_circle:] " if check.get("allowed")
                      else ":red[:material/block:] ") + md(check.get("text")))
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
    st.markdown(f":material/calendar_month: **{t('collection')}**")
    for i, zone in enumerate(zones):
        with st.container(border=True, key=f"zone_{i}"):
            st.markdown("  \n".join(zone_lines(zone, t)))
            if zone.get("stale"):
                st.warning(t("stale"), icon=":material/history:")
            st.caption(t("data_as_of", date=md(zone.get("data_date")) or t("date_unknown")))


def show_sources(result: dict, t: T) -> None:
    citations = result.get("citations") or []
    if not citations:
        return
    st.markdown(f":material/menu_book: **{t('sources')}**")
    for c in citations:
        source = str(c.get("source") or "")
        compact = source.replace(" ", "")
        where = " · ".join(str(x) for x in (       # only what the name does not say
            t("source_page", page=c["page"]) if c.get("page")
            and f"p.{c['page']}" not in compact else None,
            c.get("year") if c.get("year") and str(c["year"]) not in source else None,
            t("source_data_date", date=c["data_date"]) if c.get("data_date")
            and str(c["data_date"]) not in source else None) if x)
        label = f"[{c.get('n')}] {source}" + (f" · {where}" if where else "")
        with st.expander(f":material/description: {md(label)}"):   # icon=… would hide the arrow
            st.text(service.source_text(c)["text"])


def show_handoff(result: dict, t: T) -> None:
    handoff = result.get("handoff")
    if not handoff:
        return
    with st.container(border=True, key="handoff"):
        st.markdown(f":material/support_agent: **{t('ask_person')}**")
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
    st.info(md(clarify.get("question")), icon=":material/help:")
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
    for column, rating, label, icon in ((up, "up", t("yes"), ":material/thumb_up:"),
                                       (down, "down", t("no"), ":material/thumb_down:")):
        column.button(label, icon=icon, key=f"{rating}_{trace_id}", width="stretch",
                      disabled=disabled, on_click=save_rating, args=(trace_id, rating))


def show_placeholder(t: T) -> None:
    """Where the answer will appear, before the first question (hidden on a phone, where the
    answer comes below the question anyway)."""
    with st.container(key="answer_placeholder", border=True):
        st.markdown(f"### :material/forum: {t('placeholder_title')}")
        st.caption(t("placeholder_text"))


def show_result(result: dict, request: dict, t: T, on_pick: Callable[[str, str], None],
                disabled: bool = False) -> None:
    """One answer, by status (docs/WEBSITE.md "What to show, by status")."""
    with st.container(border=True, key="answer_panel"):
        st.caption(t("your_question"))
        st.markdown(md(request.get("question")))
        status = result["status"]
        st.header(t(f"title_{status}"))
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
            st.warning(text, icon=":material/info:")
            show_handoff(result, t)
        else:
            st.info(text, icon=":material/info:")
        for note in result.get("notes") or []:
            st.caption(md(note))
        show_feedback(result, t, disabled)


# ---------------------------------------------------------------------------- page bottom

def show_glossary(lang: str, t: T, languages: dict[str, str]) -> None:
    with st.expander(f":material/translate: {t('glossary')}"):
        column = lang if lang in GLOSSARY_LANGS else "en"
        rows = [f"| {md(term['ko'])} | {md(term.get(column) or term['en'])} |"
                for term in service.glossary()]
        st.markdown(f"| 한국어 | {md(languages.get(column, 'English'))} |\n|---|---|\n"
                    + "\n".join(rows))
        if column != "en":
            st.caption(t("glossary_unchecked"))


def show_maintainer(health: dict, reviews: list[dict], settings: dict | None) -> None:
    """RAG_ADMIN=1 only, in English: what runs, which data is due for review, where the
    numbers are. Open by itself when a data review is overdue."""
    overdue = [r for r in reviews if r["overdue"]]
    with st.expander(":material/build: Maintainer", expanded=bool(overdue)):
        mode = "offline demo" if health["offline"] else "live"
        st.markdown(md(f"Mode: {mode} · Ollama: {'up' if health['ollama'] else 'down'} · "
                       f"pipeline: {'loaded' if health['pipeline_loaded'] else 'not loaded yet'}"))
        if settings:
            st.markdown(md(f"Generator {settings.get('llm')} ({settings.get('llm_digest')}) · "
                           f"router digest {settings.get('router_digest')} · "
                           f"pipeline {settings.get('pipeline_version')}"))
        else:
            st.markdown(md(f"Generator {health['model']} (digests once the pipeline loads)"))
        days = health["trace_retention_days"]
        st.markdown(md(f"Traces, errors and feedback are kept {days} days" if days
                       else "Traces, errors and feedback are kept without a limit"))
        if overdue:
            st.warning(md("Data review overdue: " + ", ".join(
                f"{r['source']} (due {r['next_review']}, {r['owner']})" for r in overdue)
                + ". See data/manual/stewardship.json."))
        rows = [f"| {md(r['source'])} | {md(r['owner'])} | {md(r['last_reviewed'])} | "
                f"{md(r['next_review'])}{' ⚠' if r['overdue'] else ''} |" for r in reviews]
        st.markdown("| Source | Owner | Last reviewed | Next review |\n|---|---|---|---|\n"
                    + "\n".join(rows))
        st.code("python -m eval.ops_summary --days 7    # live use: requests, latency, feedback",
                language="bash")
