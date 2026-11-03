import json
from pathlib import Path

import streamlit as st


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

    .stFormSubmitButton > button {
        background: #438b32 !important;
        border: 1px solid #438b32 !important;
        border-radius: 9px !important;
        min-height: 48px;
    }

    .stFormSubmitButton > button p {
        color: #ffffff !important;
        font-weight: 700;
    }

    .stFormSubmitButton > button:hover {
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


# ---------- SESSION STATE ----------
if "result" not in st.session_state:
    st.session_state.result = None

if "feedback" not in st.session_state:
    st.session_state.feedback = {}


def choose_question(text):
    st.session_state.question_input = text


# ---------- LOAD MOCK JSON ----------
def get_mock_answer(question, lang, district, dong):
    mock_file = Path(__file__).parent / "mock_answer.json"

    with mock_file.open("r", encoding="utf-8") as file:
        scenarios = json.load(file)

    result = scenarios["INSUFFICIENT_CONTEXT"] 

    if not isinstance(result, dict):
        raise ValueError("The mock JSON must contain one answer object.")

    request_number = st.session_state.get("request_number", 0) + 1
    st.session_state.request_number = request_number

    result["trace_id"] = f"demo-{request_number}"
    result["submitted_question"] = question
    result["submitted_language"] = lang
    result["submitted_district"] = district
    result["submitted_neighbourhood"] = dong

    return result


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


# ---------- BANNER ----------
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
                and check collection details in your neighbourhood.
            </p>
        </div>
        <div class="hero-art" aria-hidden="true">
            <span>♻</span>
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)

st.caption("Prototype · Using mock answers, not the live RAG system.")


# ---------- EXAMPLE QUESTIONS ----------
st.subheader("What are you throwing away?")

examples = [
    (
        "🧴 Plastic bottle",
        "How should I dispose of a plastic bottle?",
    ),
    (
        "🍎 Food scraps",
        "How should I dispose of food scraps?",
    ),
    (
        "🔋 Batteries",
        "Where should I dispose of used batteries?",
    ),
]

for column, (label, text) in zip(st.columns(3), examples):
    column.button(
        label,
        on_click=choose_question,
        args=(text,),
        use_container_width=True,
    )


# ---------- QUESTION FORM ----------
with st.container(key="question_panel"):
    st.subheader("Ask about an item")

    with st.form("question_form", border=False):
        question = st.text_area(
            "Your question",
            placeholder=(
                "For example: How should I dispose "
                "of a plastic bottle?"
            ),
            height=105,
            key="question_input",
        )

        language = st.selectbox(
            "Answer language",
            ["English", "한국어"],
        )

        st.caption(
            "The mock answer does not change with the question "
            "or selected language."
        )

        with st.expander("Add location for collection times"):
            st.caption(
                "Optional. Please do not enter your street address."
            )

            district = st.selectbox(
                "District",
                ["Not selected", "Seongdong-gu (sample)"],
            )

            neighbourhood = st.text_input(
                "Neighbourhood",
                placeholder="e.g. Haengdang-dong",
            )

            st.caption(
                "The complete location list will be added later."
            )

        submitted = st.form_submit_button(
            "Find disposal guidance",
            type="primary",
            use_container_width=True,
        )

    if submitted:
        if not question.strip():
            st.warning("Please enter an item or question.")
        else:
            try:
                # Later, replace this with the real answer() call.
                result = get_mock_answer(
                    question=question.strip(),
                    lang=language,
                    district=district,
                    dong=neighbourhood.strip(),
                )

            except FileNotFoundError:
                st.session_state.result = None
                st.error(
                    "mock_answer.json was not found. "
                    "Place it in the same folder as streamlit_app.py."
                )

            except json.JSONDecodeError as error:
                st.session_state.result = None
                st.error(
                    f"Check mock_answer.json: invalid JSON "
                    f"near line {error.lineno}."
                )

            except (OSError, ValueError) as error:
                st.session_state.result = None
                st.error(f"Could not load the mock answer: {error}")

            else:
                st.session_state.result = result


# ---------- DISPLAY RESULT ----------
result = st.session_state.result

if result:
    with st.container(key="answer_panel"):
        st.caption("YOUR QUESTION")
        st.write(result["submitted_question"])

        st.subheader("Disposal guide")

        st.warning(
            "Demo data only — not verified disposal advice. "
            "The same mock answer is used for every question."
        )
        
        status = result.get("status", "INSUFFICIENT_CONTEXT")
        answer_text = result.get("answer_text")

        if answer_text:
            if status == "CLARIFY":
                st.info(answer_text)
            elif status == "INSUFFICIENT_CONTEXT":
                st.warning(answer_text)
            else:
                st.write(answer_text)

        # Item details remain visible whenever provided.
        bin_en = result.get("bin_en")
        bin_ko = result.get("bin")

        if bin_en or bin_ko:
            st.divider()
            st.write("**♻️ Where it goes**")

            if bin_en:
                st.write(bin_en)

            if bin_ko:
                st.caption(bin_ko)

        preparation_steps = result.get("how_to_prepare") or []

        if preparation_steps:
            st.write("**How to prepare it**")

            for number, step in enumerate(
                preparation_steps,
                start=1,
            ):
                st.write(f"{number}. {step}")

        # Schedule details are handled independently.
        st.divider()
        st.write("**Collection details**")

        if result["submitted_district"] != "Not selected":
            location = result["submitted_district"]

            if result["submitted_neighbourhood"]:
                location += (
                    " / " + result["submitted_neighbourhood"]
                )

            st.caption(f"Submitted location: {location}")

        schedule = result.get("schedule") or {}
        schedule_fields = [
            ("Days", "days"),
            ("Time", "time"),
            ("Place", "place"),
        ]

        if any(schedule.get(field) for _, field in schedule_fields):
            for label, field in schedule_fields:
                if schedule.get(field):
                    st.write(f"**{label}:** {schedule[field]}")
        else:
            st.caption("No collection schedule provided.")

        if result.get("missing"):
            st.write("**Missing information:**", result["missing"])

        st.caption(
            "Data as of: "
            + (result.get("data_date") or "Not available")
        )

        with st.expander("Contact the district office"):
            phone = result.get("office_phone")

            if phone:
                st.write("**Phone:**", phone)
            else:
                st.write("No office contact provided.")

            st.caption(
                "A Korean handoff sentence will be added "
                "when supplied by the system."
            )

        st.divider()
        st.write("**Was this helpful?**")

        trace_id = result["trace_id"]
        positive, negative, _ = st.columns([1, 1, 3])

        if positive.button(
            "👍 Yes",
            key=f"positive_{trace_id}",
            use_container_width=True,
        ):
            st.session_state.feedback[trace_id] = {
                "trace_id": trace_id,
                "rating": "positive",
            }

        if negative.button(
            "👎 No",
            key=f"negative_{trace_id}",
            use_container_width=True,
        ):
            st.session_state.feedback[trace_id] = {
                "trace_id": trace_id,
                "rating": "negative",
            }

        if trace_id in st.session_state.feedback:
            st.caption(
                "Thank you. Feedback is saved in this demo "
                "session only, not in the system trace yet."
            )


# ---------- GLOSSARY ----------
st.write("")

with st.expander("Useful Korean terms"):
    st.write("**분리배출** — separate waste disposal")
    st.write("**음식물쓰레기** — food waste")
    st.write("**종량제봉투** — designated pay-as-you-throw bag")

st.caption("Midterm group project · Household waste guidance")