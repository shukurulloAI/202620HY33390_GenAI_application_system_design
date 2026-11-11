"""
The one module the website imports (PLAN.md §4.12; how to use it: docs/WEBSITE.md).

    from rag import service
    answer = service.ask("Where do I throw away a pizza box?", lang="en",
                         district="성동구", dong="행당1동")
    service.save_feedback(answer["trace_id"], "up", "clear answer")
    service.source_text(answer["citations"][0])   # full text for a source card
    service.locations()                           # dropdowns: province -> district -> areas
    service.glossary()                            # waste terms in six languages
    service.languages()                           # {"en": "English", "ko": "한국어", ...}
    service.health()                              # for a status line: offline? Ollama up?
    service.warm_up()                             # load everything before the first question

Every answer fits the contract in rag/contract.py (schema: docs/answer_schema.json). `ask()`
never raises for a question: if the pipeline fails (Ollama down, a bug), the user gets an
abstention with a handoff and the error goes to traces/errors.jsonl.

Offline mode (environment variable RAG_OFFLINE=1, or `configure(offline=True)`): `ask()`
returns the recorded answers in docs/answer_examples.json, so the page can be built and
demonstrated without Ollama or the 4.6 GB of models.

The pipeline loads two models (about 20 s), so it is created once, on the first question,
and shared. Questions are answered one at a time: the local LLM serves one request anyway.
"""
from __future__ import annotations

import json
import logging
import os
import threading
import traceback
import uuid
from datetime import UTC, datetime
from functools import lru_cache
from urllib.error import URLError
from urllib.request import urlopen

from rag import config, paths
from rag.contract import check
from rag.files import append_jsonl, read_jsonl
from rag.handoff import korean_sentence
from rag.texts import LANGUAGES, lang_or_default, text

log = logging.getLogger(__name__)

EXAMPLES_FILE = paths.ROOT / "docs" / "answer_examples.json"
FEEDBACK_FILE = paths.TRACE_DIR / "feedback.jsonl"
ERRORS_FILE = paths.TRACE_DIR / "errors.jsonl"
MAX_QUESTION_CHARS = 500
MAX_COMMENT_CHARS = 1000
RATINGS = ("up", "down")

_lock = threading.Lock()
_state: dict = {"pipeline": None, "offline": os.environ.get("RAG_OFFLINE") == "1"}


def configure(*, offline: bool | None = None, pipeline=None) -> None:
    """Switch offline mode, or hand in a ready Pipeline (tests, a non-default config)."""
    if offline is not None:
        _state["offline"] = offline
    if pipeline is not None:
        _state["pipeline"] = pipeline


def _pipeline():
    if _state["pipeline"] is None:
        from rag.pipeline import Pipeline  # heavy imports only when really needed
        _prune_logs()
        _state["pipeline"] = Pipeline()
    return _state["pipeline"]


def _prune_logs() -> None:
    """Retention for traces, errors and feedback (rag/tracing.py), once per process."""
    from rag.tracing import prune
    try:
        removed = prune()
    except OSError:
        log.exception("could not prune traces")
        return
    if removed["trace_files"] or removed["records"]:
        log.info("pruned old traces: %s", removed)


def warm_up() -> None:
    """Build the pipeline (embedding model, reranker, indexes) and load the Ollama models,
    so the first question is not the slow one. Meant for a background thread at app start;
    a failure is logged, never raised (ask() still works, only slower)."""
    if _state["offline"]:
        return
    try:
        with _lock:
            pipeline = _pipeline()
        clients = [pipeline.llm, pipeline.router.llm if pipeline.router else None]
        for client in {id(c): c for c in clients if c is not None}.values():
            if hasattr(client, "warm_up"):
                client.warm_up()
    except Exception:
        log.exception("warm-up failed")


# ---------------------------------------------------------------------------- questions

def ask(question: str, lang: str | None = None, district: str | None = None,
        dong: str | None = None, province: str | None = None,
        waste_type: str | None = None) -> dict:
    """Answer one question. `lang` is the answer language (one of languages(); None = the
    question's). `district`/`dong`/`province` come from the dropdowns, in Korean
    (locations()); empty means the user did not choose, and the question is read instead."""
    question = (question or "").strip()[:MAX_QUESTION_CHARS]
    lang = lang if lang in LANGUAGES else None
    district, dong, province = (district or None), (dong or None), (province or None)
    if not question:
        raise ValueError("empty question")
    if _state["offline"]:
        return offline_answer(question, lang)
    try:
        with _lock:
            answer = _pipeline().answer(question, lang=lang, district=district, dong=dong,
                                        province=province, waste_type=waste_type)
        return check(answer)
    except Exception as exc:                     # the user gets a handoff, never a traceback
        trace_id = str(uuid.uuid4())
        log.exception("ask failed (%s)", trace_id)
        append_jsonl(ERRORS_FILE, {"trace_id": trace_id, "time": _now(), "question": question,
                                   "lang": lang, "district": district, "dong": dong,
                                   "error": repr(exc), "traceback": traceback.format_exc()})
        return unavailable_answer(lang, district, dong, trace_id)


def unavailable_answer(lang: str | None, district: str | None, dong: str | None,
                       trace_id: str) -> dict:
    return check({
        "contract_version": "1.0", "status": "INSUFFICIENT_CONTEXT", "lang": lang,
        "bin": "", "bin_en": "", "how_to_prepare": [],
        "answer_text": text("UNAVAILABLE", lang), "citations": [],
        "missing": "the assistant failed; see traces/errors.jsonl", "schedule": None,
        "data_date": None, "office_phone": None, "clarify": None, "notes": [],
        "handoff": {"office": None, "phone": None, "contact": text("contact_none", lang),
                    "korean_sentence": korean_sentence("", None, district, dong, False),
                    "checked": []},
        "trace_id": trace_id})


# ---------------------------------------------------------------------------- offline mode

@lru_cache(maxsize=1)
def examples() -> list[dict]:
    """Recorded real answers, one or more per status (python -m experiments.make_examples)."""
    return json.loads(EXAMPLES_FILE.read_text(encoding="utf-8"))["examples"]


def offline_answer(question: str, lang: str | None) -> dict:
    """The recorded answer to this exact question, else the first example in this language
    (else the first one), marked as an example."""
    for example in examples():
        if example["question"].strip().lower() == question.lower():
            return dict(example["answer"])
    pick = next((e for e in examples() if e["answer"]["lang"] == lang_or_default(lang)),
                examples()[0])
    answer = json.loads(json.dumps(pick["answer"]))
    answer["notes"] = [text("OFFLINE", lang), *answer["notes"]]
    return answer


# ---------------------------------------------------------------------------- feedback

def save_feedback(trace_id: str, rating: str, comment: str = "") -> dict:
    """👍/👎 for one answer, kept with its trace_id so evaluation can find the trace."""
    if rating not in RATINGS:
        raise ValueError(f"rating must be one of {RATINGS}")
    if not trace_id or len(trace_id) > 100:
        raise ValueError("trace_id missing or too long")
    record = {"trace_id": trace_id, "rating": rating,
              "comment": (comment or "").strip()[:MAX_COMMENT_CHARS], "time": _now()}
    append_jsonl(FEEDBACK_FILE, record)
    return record


# ---------------------------------------------------------------------------- page data

def source_text(citation: dict) -> dict:
    """The source behind a citation, for a source card: {source, page, year, text}.
    Answers already carry `text`; this also works for a bare {kind, ref}."""
    if citation.get("text"):
        return {k: citation.get(k) for k in ("source", "page", "year", "data_date", "text")}
    if citation["kind"] == "item":
        chunk = _chunks().get(citation["ref"])
        if chunk is None:
            raise KeyError(f"unknown chunk {citation['ref']!r}")
        meta = chunk["metadata"]
        return {"source": meta.get("source"), "page": meta.get("page"),
                "year": meta.get("source_year"), "data_date": None, "text": chunk["text"]}
    from rag.schedule_tool import default_table
    row = default_table().by_id[citation["ref"]]
    return {"source": f"District data, {row.province} {row.district}, 관리번호 {row.row_id}",
            "page": None, "year": None, "data_date": row.data_date,
            "text": row.to_evidence(None)}


@lru_cache(maxsize=1)
def _chunks() -> dict[str, dict]:
    return {c["id"]: c for c in read_jsonl(paths.ITEM_CHUNKS)}


@lru_cache(maxsize=1)
def locations() -> list[dict]:
    """Every district with its zones and areas, including the Seoul districts with no data
    (has_data = false), for the dropdowns. Names are Korean; *_en are romanised."""
    return json.loads(paths.LOCATIONS.read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def glossary() -> list[dict]:
    """Waste terms: {"ko", "en", "zh", "vi", "uz", "ru", "bin"?} (zh/vi/uz/ru unchecked)."""
    return json.loads(paths.GLOSSARY.read_text(encoding="utf-8"))["terms"]


def languages() -> dict[str, str]:
    return dict(LANGUAGES)


def data_reviews(today=None) -> list[dict]:
    """Each source with its owner and review dates (data/manual/stewardship.json);
    `overdue` once next_review has passed."""
    today = (today or datetime.now(UTC).date()).isoformat()
    sources = json.loads(paths.STEWARDSHIP.read_text(encoding="utf-8"))["sources"]
    return [{"source": key, **record, "overdue": record["next_review"] < today}
            for key, record in sources.items()]


def health() -> dict:
    """What the page can show in a status line. Never loads the models."""
    ollama = False
    if not _state["offline"]:
        try:
            with urlopen(f"{config.OLLAMA_URL}/api/tags", timeout=2) as response:
                ollama = response.status == 200
        except (URLError, OSError):
            ollama = False
    return {"offline": _state["offline"], "ollama": ollama,
            "pipeline_loaded": _state["pipeline"] is not None, "model": config.LLM_MODEL,
            "data_review_overdue": [r["source"] for r in data_reviews() if r["overdue"]]}


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")
