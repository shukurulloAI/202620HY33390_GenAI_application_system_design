"""
Waste-Sorting Assistant: the website (Streamlit), connected to the RAG
system through rag/service.py (docs/WEBSITE.md).

    streamlit run app/streamlit_app.py                  # full system (Ollama + index)
    RAG_OFFLINE=1 streamlit run app/streamlit_app.py    # recorded answers, no models
"""
import re
import sys
import threading
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))   # run from any folder

from app.ui import state  # noqa: E402
from app.ui.state import NOT_SELECTED  # noqa: E402
from rag import service  # noqa: E402

st.set_page_config(
    page_title="Waste-Sorting Assistant",
    page_icon="♻️",
    layout="centered",
)


# ---------- STYLE ----------
st.markdown(
    """
    <style>
    :root {
        color-scheme: light;
    }

    .stApp,
    [data-testid="stMain"],
    [data-testid="stHeader"] {
        background: #f5f8f2 !important;
        color: #243426;
    }

    .block-container {
        max-width: 920px;
        padding-top: 5rem !important;
        padding-bottom: 2.5rem;
    }

    html, body, input, textarea, button,
    [data-testid="stMarkdownContainer"],
    [data-testid="stWidgetLabel"],
    [data-testid="stCaptionContainer"],
    [data-baseweb="select"] {
        font-family: Arial, Helvetica, sans-serif !important;
    }

    h1, h2, h3,
    [data-testid="stMarkdownContainer"],
    [data-testid="stWidgetLabel"] p {
        color: #243426 !important;
    }

    h2, h3 {
        font-family: Arial, Helvetica, sans-serif !important;
        font-weight: 700 !important;
        letter-spacing: -0.025em;
    }

    [data-testid="stCaptionContainer"] p {
        color: #63705f !important;
    }

    .brand {
        display: flex;
        align-items: center;
        gap: 10px;
        margin-bottom: 22px;
    }

    .brand-icon {
        color: #438b32;
        font-size: 36px;
        line-height: 1;
    }

    .brand-name {
        color: #294627;
        font-size: 19px;
        font-weight: 700;
    }

    .brand-note {
        color: #63705f;
        font-size: 12px;
        margin-top: 3px;
    }

    .hero {
        background: linear-gradient(115deg, #59ac48, #83c558);
        border-radius: 18px;
        padding: 32px;
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 20px;
        overflow: hidden;
        margin-bottom: 22px;
    }

    .hero-copy {
        max-width: 440px;
    }

    .hero-label {
        color: #ffffff;
        font-size: 12px;
        font-weight: 700;
        margin-bottom: 12px;
    }

    .hero-title {
        color: #ffffff;
        font-size: clamp(28px, 5vw, 39px);
        font-weight: 700;
        line-height: 1.12;
        letter-spacing: -1px;
        margin-bottom: 14px;
    }

    .hero-description {
        color: #ffffff;
        font-size: 15px;
        line-height: 1.6;
        margin: 0;
    }

    .hero-art {
        flex-shrink: 0;
        width: 150px;
        height: 150px;
        background: #ffffff26;
        border: 1px solid #ffffff45;
        border-radius: 50%;
        display: flex;
        align-items: center;
        justify-content: center;
    }

    .hero-art span {
        color: white;
        font-size: 100px;
        line-height: 1;
    }

    .st-key-question_panel {
        background: #ffffff;
        padding: 24px;
        border: 1px solid #e1e8dc;
        border-radius: 14px;
        margin-top: 10px;
    }

    .st-key-answer_panel {
        background: #ffffff;
        padding: 24px;
        border: 1px solid #e1e8dc;
        border-top: 4px solid #62b34a;
        border-radius: 14px;
        margin-top: 22px;
    }

    [data-testid="stTextArea"] > div,
    [data-testid="stTextInput"] > div {
        background: #f8faf6 !important;
        border-color: #aab8a3 !important;
        border-radius: 9px !important;
    }

    textarea, input {
        background: #f8faf6 !important;
        color: #243426 !important;
        -webkit-text-fill-color: #243426 !important;
        caret-color: #243426;
    }

    textarea::placeholder,
    input::placeholder {
        color: #697565 !important;
        -webkit-text-fill-color: #697565 !important;
        opacity: 1;
    }

    [data-baseweb="select"] > div {
        background: #f3f7ef !important;
        color: #243426 !important;
        border-color: #aab8a3 !important;
        border-radius: 9px !important;
    }

    [data-baseweb="select"] span {
        color: #243426 !important;
    }

    [data-baseweb="select"] svg {
        fill: #438b32 !important;
    }

    [data-baseweb="popover"],
    [data-baseweb="popover"] > div,
    [role="listbox"],
    [role="option"] {
        background: #ffffff !important;
        color: #243426 !important;
    }

    [role="option"]:hover,
    [role="option"][aria-selected="true"] {
        background: #eaf5e3 !important;
    }

    .stButton > button {
        background: #eaf4e3 !important;
        color: #335e29 !important;
        border: 1px solid #cbdcbe !important;
        border-radius: 10px !important;
        min-height: 46px;
    }

    .stButton > button p {
        color: #335e29 !important;
        font-weight: 600;
    }

    .stButton > button:hover {
        background: #dcedd1 !important;
        border-color: #6c9a55 !important;
    }

    .stButton > button[data-testid="stBaseButton-primary"] {
        background: #438b32 !important;
        border: 1px solid #438b32 !important;
        border-radius: 9px !important;
        min-height: 48px;
    }

    .stButton > button[data-testid="stBaseButton-primary"] p {
        color: #ffffff !important;
        font-weight: 700;
    }

    .stButton > button[data-testid="stBaseButton-primary"]:hover {
        background: #367428 !important;
    }

    [data-testid="stExpander"] {
        background: transparent !important;
        border-color: #dce5d5 !important;
        border-radius: 8px !important;
    }

    [data-testid="stExpander"] summary p {
        color: #335e29 !important;
    }

    button:focus-visible,
    input:focus-visible,
    textarea:focus-visible,
    summary:focus-visible {
        outline: 3px solid #3166a0 !important;
        outline-offset: 3px;
    }

    hr {
        border-color: #dce5d5 !important;
    }

    @media (max-width: 600px) {
        .block-container {
            padding-top: 4.5rem !important;
        }

        .hero {
            padding: 24px;
        }

        .hero-art {
            width: 75px;
            height: 75px;
        }

        .hero-art span {
            font-size: 52px;
        }

        .st-key-question_panel,
        .st-key-answer_panel {
            padding: 18px;
        }
    }
    </style>
    """,
    unsafe_allow_html=True,
)

st.markdown(
    """
    <style>
    .bin-card {background:#eef7e8;border:1px solid #cfe3c2;border-radius:12px;
               padding:14px 18px;margin:8px 0 14px 0;}
    .bin-en {color:#243426;font-size:22px;font-weight:700;line-height:1.25;}
    .bin-ko {color:#4d6b45;font-size:15px;margin-top:4px;}
    .zone-card {border:1px solid #dce5d5;border-radius:10px;padding:12px 16px;margin:8px 0;
                background:#fbfdf9;}
    .zone-title {font-weight:700;color:#294627;}
    .handoff {background:#fff8ec;border:1px solid #f0dcb4;border-radius:12px;
              padding:14px 18px;margin:10px 0;}
    .status-line {color:#63705f;font-size:12px;}
    </style>
    """,
    unsafe_allow_html=True,
)

WASTE_TYPE_NAMES = {"general": "General waste", "food": "Food waste",
                    "recycling": "Recycling", "bulky": "Bulky waste"}


# ---------- SESSION STATE ----------
for key, default in (("result", None), ("request", None), ("feedback", {})):
    if key not in st.session_state:
        st.session_state[key] = default


def choose_question(text):
    st.session_state.question_input = text


def md(text: str) -> str:
    """Model text as Markdown: escape Markdown characters, keep the line breaks."""
    escaped = re.sub(r"([\\`*_{}\[\]<>#|~])", r"\\\1", text or "")
    return escaped.replace("\n", "  \n")


# ---------- DATA FOR THE FORM ----------
@st.cache_data(show_spinner=False)
def location_tree():
    return state.location_tree(service.locations())


def reset_district():
    """A new province: its own districts, nothing chosen yet."""
    st.session_state.area_district = None
    st.session_state.area_dong = NOT_SELECTED


def reset_dong():
    st.session_state.area_dong = NOT_SELECTED


def ask(question, lang, province=None, district=None, dong=None):
    request = {"question": question, "lang": lang, "province": province,
               "district": district, "dong": dong}
    first = not service.health()["pipeline_loaded"] and not service.health()["offline"]
    note = ("Loading the models for the first question (about 20 s)..." if first
            else "Looking it up in the official guides...")
    with st.spinner(note):
        result = service.ask(**request)
    st.session_state.request = request
    st.session_state.result = result


# ---------- BRAND ----------
st.markdown(
    """
    <div class="brand">
        <div class="brand-icon" aria-hidden="true">♻</div>
        <div>
            <div class="brand-name">Waste-Sorting Assistant</div>
            <div class="brand-note">Household waste in Korea</div>
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)

st.markdown(
    """
    <div class="hero">
        <div class="hero-copy">
            <div class="hero-label">SORTING & RECYCLING</div>
            <div class="hero-title">
                Know where<br>your waste goes.
            </div>
            <p class="hero-description">
                Find out how to prepare an item for disposal
                and check collection days in your neighbourhood,
                from the official Korean guides and district data.
            </p>
        </div>
        <div class="hero-art" aria-hidden="true">
            <span>♻</span>
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)

@st.cache_resource(show_spinner=False)
def start_warm_up() -> bool:
    """Once per server process: load the models in the background while the page renders."""
    threading.Thread(target=service.warm_up, name="warm-up", daemon=True).start()
    return True


health = service.health()
if health["ollama"] and not health["offline"]:
    start_warm_up()
if health["offline"]:
    status_line = "Offline demo: answers are recorded examples, not live answers."
elif health["ollama"]:
    status_line = f"Live system · model {health['model']} running on this computer."
else:
    status_line = ("The language model is not running (start Ollama). "
                   "Questions will get a contact for the district office instead.")
if health["data_review_overdue"]:
    status_line += (" Data review overdue: " + ", ".join(health["data_review_overdue"])
                    + " (data/manual/stewardship.json).")
st.markdown(f'<div class="status-line">{status_line}</div>', unsafe_allow_html=True)


# ---------- EXAMPLE QUESTIONS ----------
st.subheader("What are you throwing away?")

examples = [
    ("🍕 Pizza box", "Where do I throw away a pizza box?"),
    ("🍗 Chicken bones", "닭뼈는 음식물쓰레기인가요?"),
    ("🥬 Food waste days", "When can I put out food waste?"),
]
for column, (label, text) in zip(st.columns(3), examples, strict=True):
    column.button(label, on_click=choose_question, args=(text,), use_container_width=True)


# ---------- QUESTION FORM ----------
languages = service.languages()
tree = location_tree()

if "area_province" not in st.session_state:
    st.session_state.area_province = "서울특별시" if "서울특별시" in tree else NOT_SELECTED

# No st.form here: a form does not rerun when a selectbox changes, so the district list
# would stay on the old province (a mismatched pair finds no data).
with st.container(key="question_panel"):
    st.subheader("Ask about an item or a collection day")
    st.text_area(
        "Your question",
        placeholder="For example: How should I dispose of a plastic bottle?",
        height=105,
        key="question_input",
        max_chars=500,
    )
    lang = st.selectbox("Answer language", list(languages),
                        format_func=lambda code: languages[code])

    with st.expander("Your area (for collection days)"):
        st.caption("Optional. Choose your district, not your street address. "
                   "You can also write it in the question.")
        province = st.selectbox("Province / city", [NOT_SELECTED, *tree], key="area_province",
                                on_change=reset_district)
        districts = {d["district"]: d for d in tree.get(province, [])}
        district = st.selectbox(
            "District", [None, *districts], key="area_district", on_change=reset_dong,
            format_func=lambda name: NOT_SELECTED if name is None else
            districts[name]["label"] + ("" if districts[name]["has_data"] else " - no data"))
        areas = districts[district]["areas"] if district in districts else []
        dong = st.selectbox("Neighbourhood (동) or zone", [NOT_SELECTED, *areas],
                            key="area_dong")

    if st.button("Find disposal guidance", type="primary", width="stretch"):
        question = (st.session_state.question_input or "").strip()
        if not question:
            st.warning("Please enter an item or a question.")
        else:
            ask(question, lang, **state.area_request(tree, province, district, dong))


# ---------- RESULT PARTS ----------
def show_bin(result):
    if result.get("bin"):
        st.markdown(
            f'<div class="bin-card"><div class="bin-en">♻️ {result["bin_en"]}</div>'
            f'<div class="bin-ko">{result["bin"]} · the name on the bag or bin</div></div>',
            unsafe_allow_html=True)


def show_steps(result):
    steps = result.get("how_to_prepare") or []
    if steps:
        st.write("**How to prepare it**")
        st.markdown("\n".join(f"{i}. {md(step)}" for i, step in enumerate(steps, 1)))


def show_schedule(result):
    schedule = result.get("schedule") or {}
    zones = schedule.get("zones") or []
    if not zones:
        return
    st.write("**Collection in your area**")
    for zone in zones:
        lines = [f'<div class="zone-title">{zone["district"]} · {zone["zone"]}</div>']
        if zone.get("areas"):
            shown = ", ".join(zone["areas"][:12]) + (" ..." if len(zone["areas"]) > 12 else "")
            lines.append(f"<div>Areas: {shown}</div>")
        if zone.get("place"):
            lines.append(f"<div>Where: {zone['place']}</div>")
        for waste_type, rule in (zone.get("by_type") or {}).items():
            when = rule.get("days") or "days not listed"
            if rule.get("start"):
                when += f", {rule['start']}–{rule.get('end') or ''}"
            nxt = ", ".join(rule.get("next_dates") or [])
            lines.append(f"<div><b>{WASTE_TYPE_NAMES.get(waste_type, waste_type)}:</b> {when}"
                         + (f" · next: {nxt}" if nxt else "") + "</div>")
        for check in zone.get("day_check") or []:
            mark = "✅" if check["allowed"] else "⛔"
            lines.append(f"<div>{mark} {check['text']}</div>")
        if zone.get("no_collection"):
            lines.append(f"<div>No collection: {zone['no_collection']}</div>")
        office = " ".join(x for x in (zone.get("office"), zone.get("phone")) if x)
        if office:
            lines.append(f"<div>Office: {office}</div>")
        date = f"Data as of {zone.get('data_date') or 'unknown'}"
        if zone.get("stale"):
            date += " · <b>this data is over a year old; check with the office</b>"
        lines.append(f'<div class="status-line">{date}</div>')
        st.markdown(f'<div class="zone-card">{"".join(lines)}</div>', unsafe_allow_html=True)


def show_sources(result):
    citations = result.get("citations") or []
    if not citations:
        return
    st.write("**Sources**")
    for c in citations:
        where = " · ".join(str(x) for x in (
            f"p.{c['page']}" if c.get("page") else None,
            c.get("year"),
            f"data date {c['data_date']}" if c.get("data_date") else None) if x)
        with st.expander(f"[{c['n']}] {c['source']}" + (f" · {where}" if where else "")):
            st.text(service.source_text(c)["text"])


def show_handoff(result):
    handoff = result.get("handoff")
    if not handoff:
        return
    phone = handoff.get("phone")
    contact = md(handoff.get("contact") or "")
    if phone:
        contact += f" · [{phone}](tel:{phone.replace('-', '')})"
    st.markdown('<div class="handoff"><b>Ask a person</b></div>', unsafe_allow_html=True)
    st.markdown(contact)
    if handoff.get("korean_sentence"):
        st.caption("Show or read this to the office staff (copy button on the right):")
        st.code(handoff["korean_sentence"], language=None, wrap_lines=True)
    if handoff.get("checked"):
        st.caption("What the assistant checked: " + "; ".join(handoff["checked"]))


def show_clarify(result):
    clarify = result.get("clarify")
    if not clarify:
        return
    st.info(clarify["question"])
    request = st.session_state.request or {}
    options = clarify.get("options") or []
    if clarify["kind"] == "district" or not options:
        st.caption("Choose your district under “Your area” above and ask again.")
        return
    columns = st.columns(min(3, len(options)))
    for i, option in enumerate(options[:30]):
        if columns[i % len(columns)].button(option, key=f"clarify_{i}_{option}",
                                            use_container_width=True):
            if clarify["kind"] == "province":
                province_name, _, district_name = option.partition(" ")
                ask(request["question"], request["lang"], province=province_name,
                    district=district_name)
            else:
                ask(request["question"], request["lang"], province=request.get("province"),
                    district=request.get("district"), dong=option)
            st.rerun()


def show_feedback(result):
    st.divider()
    st.write("**Was this helpful?**")
    trace_id = result["trace_id"]
    if trace_id in st.session_state.feedback:
        st.caption("Thank you. Your rating is saved with this answer.")
        return
    comment = st.text_input("Comment (optional)", key=f"comment_{trace_id}", max_chars=300)
    up, down, _ = st.columns([1, 1, 3])
    for column, rating, label in ((up, "up", "👍 Yes"), (down, "down", "👎 No")):
        if column.button(label, key=f"{rating}_{trace_id}", use_container_width=True):
            service.save_feedback(trace_id, rating, comment)
            st.session_state.feedback[trace_id] = rating
            st.rerun()


# ---------- DISPLAY RESULT ----------
result = st.session_state.result
if result:
    request = st.session_state.request or {}
    with st.container(key="answer_panel"):
        st.caption("YOUR QUESTION")
        st.write(request.get("question", ""))
        status = result["status"]
        if status == "ANSWER":
            st.subheader("Disposal guide")
            show_bin(result)
            st.markdown(md(result["answer_text"]))
            show_steps(result)
            show_schedule(result)
            show_clarify(result)
            show_handoff(result)
            show_sources(result)
        elif status == "CLARIFY":
            st.subheader("One more detail")
            st.write(md(result["answer_text"]))
            show_clarify(result)
        elif status == "INSUFFICIENT_CONTEXT":
            st.subheader("I can't answer this one safely")
            st.warning(result["answer_text"])
            show_handoff(result)
        else:
            st.subheader("Outside what I can help with")
            st.info(result["answer_text"])
        for note in result.get("notes") or []:
            st.caption(note)
        show_feedback(result)


# ---------- GLOSSARY ----------
st.write("")
with st.expander("Useful Korean terms"):
    chosen = (st.session_state.request or {}).get("lang") or "en"
    column = chosen if chosen in ("en", "zh", "vi", "uz", "ru") else "en"
    rows = [f"| {t['ko']} | {md(t.get(column) or t['en'])} |" for t in service.glossary()]
    st.markdown("| 한국어 | " + languages.get(column, "English") + " |\n|---|---|\n"
                + "\n".join(rows))
    if column != "en":
        st.caption("These translations have not yet been checked by a native speaker.")

st.caption("Answers come from the Ministry of Environment guides (2018), the 2026 national "
           "separation rules and district data from data.go.kr. Rules can differ in your "
           "building or district; when unsure, ask the district office.")
