"""
The one module the website imports (PLAN.md §4.12; how to use it: docs/WEBSITE.md).

    from rag import service
    answer = service.ask("Where do I throw away a pizza box?", lang="en",
                         district="성동구", dong="행당1동")
    service.ask(question, progress=print)        # "queued", "loading", "route", "retrieve",
                                                 # "schedule", "write" as they happen
    service.save_feedback(answer["trace_id"], "up", "clear answer")
    service.source_text(answer["citations"][0])   # full text for a source card
    service.locations()                           # dropdowns: province -> district -> areas
    service.glossary()                            # waste terms in six languages
    service.languages()                           # {"en": "English", "ko": "한국어", ...}
    service.health()                              # for a status line: offline? Ollama up?
    service.pipeline_settings()                   # models and digests, once loaded (maintainers)
    service.warm_up()                             # load everything before the first question

Every answer fits the contract in rag/contract.py (schema: docs/answer_schema.json). `ask()`
does not raise for a question: if the pipeline fails (Ollama down, a bug), the user gets an
abstention with a handoff and the error goes to traces/errors.jsonl. The one exception is
`Busy`: MAX_QUEUE questions are already running or waiting, so the page asks the visitor to
try again in a minute instead of making them wait several minutes.

A question asked again on the same day, with the same language and area, is answered from
memory at once (the answer cache below): the pipeline would give the same answer anyway.

Offline mode (environment variable RAG_OFFLINE=1, or `configure(offline=True)`): `ask()`
returns the recorded answers in docs/answer_examples.json, so the page can be built and
demonstrated without Ollama or the 4.6 GB of models. RAG_OFFLINE_DELAY_S=1 makes each
recorded answer take that long per stage and report the stages, as the live system does
(for demos and the browser tests of the progress box).

The pipeline loads two models (about 20 s), so it is created once, on the first question,
and shared. Questions are answered one at a time: the local LLM serves one request anyway.
A question that has to wait for another one is told "queued" through `progress`.
"""
from __future__ import annotations

import copy
import json
import logging
import os
import threading
import time
import traceback
import uuid
from collections import OrderedDict
from collections.abc import Callable
from datetime import UTC, datetime
from functools import lru_cache
from urllib.error import URLError
from urllib.request import urlopen
from zoneinfo import ZoneInfo

from rag import config, paths
from rag.contract import check
from rag.files import append_jsonl, read_jsonl
from rag.handoff import korean_sentence
from rag.texts import LANGUAGES, lang_or_default, text
from rag.tracing import TRACE_RETENTION_DAYS, write_trace

log = logging.getLogger(__name__)

EXAMPLES_FILE = paths.ROOT / "docs" / "answer_examples.json"
FEEDBACK_FILE = paths.TRACE_DIR / "feedback.jsonl"
ERRORS_FILE = paths.TRACE_DIR / "errors.jsonl"
MAX_QUESTION_CHARS = 500
MAX_COMMENT_CHARS = 1000
RATINGS = ("up", "down")

# What `progress` can be told: the wait, then the pipeline's stages (rag/pipeline.py STAGES).
STAGES = ("queued", "loading", "route", "retrieve", "schedule", "write")
OFFLINE_STAGES = ("route", "retrieve", "write")
OFFLINE_DELAY_S = float(os.environ.get("RAG_OFFLINE_DELAY_S", "0"))

HEALTH_TTL_S = 10.0             # the page asks on every click; Ollama is asked at most this often

# One question runs at a time (about 25 s); more than this many running or waiting are
# refused with Busy, so nobody waits for minutes (RAG_MAX_QUEUE changes it).
MAX_QUEUE = int(os.environ.get("RAG_MAX_QUEUE", "5"))

# The answer cache. The pipeline gives the same answer to the same request on the same day:
# the LLM runs at temperature 0 with a fixed seed, and dates ("today", the next collection
# days, how old the data is) are resolved by day in Korean time (rag/schedule_tool.py). So the
# key is (KST date, question, language, area). It lives in this process: a restart, needed
# anyway after a model or data change, empties it. Failures are never cached.
CACHE_SIZE = 512
KST = ZoneInfo("Asia/Seoul")

_lock = threading.Lock()
_state: dict = {"pipeline": None, "offline": os.environ.get("RAG_OFFLINE") == "1"}
_probe: dict = {"at": None, "up": False}          # the last Ollama check (monotonic time)
_answers: OrderedDict[tuple, dict] = OrderedDict()   # cache key -> answer, oldest first
_answers_lock = threading.Lock()
_inflight = {"n": 0}                                  # questions running or waiting
_inflight_lock = threading.Lock()


class Busy(Exception):
    """MAX_QUEUE questions are already running or waiting: try again shortly."""


def configure(*, offline: bool | None = None, pipeline=None) -> None:
    """Switch offline mode, or hand in a ready Pipeline (tests, a non-default config)."""
    if offline is not None:
        _state["offline"] = offline
    if pipeline is not None:
        _state["pipeline"] = pipeline
    _probe["at"] = None                           # check Ollama again
    with _answers_lock:                           # answers of another pipeline do not count
        _answers.clear()


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
        waste_type: str | None = None, progress: Callable[[str], None] | None = None) -> dict:
    """Answer one question. `lang` is the answer language (one of languages(); None = the
    question's). `district`/`dong`/`province` come from the dropdowns, in Korean
    (locations()); empty means the user did not choose, and the question is read instead.
    `progress(stage)` is told what is happening; an error in it is logged, never raised.
    Raises Busy when MAX_QUEUE questions are already running or waiting (not for a question
    answered from the cache, which costs nothing)."""
    question = (question or "").strip()[:MAX_QUESTION_CHARS]
    lang = lang if lang in LANGUAGES else None
    district, dong, province = (district or None), (dong or None), (province or None)
    if not question:
        raise ValueError("empty question")
    report = _reporter(progress)
    if _state["offline"]:
        if OFFLINE_DELAY_S > 0:
            for stage in OFFLINE_STAGES:
                report(stage)
                time.sleep(OFFLINE_DELAY_S)
        return offline_answer(question, lang)
    key = (_today(), question, lang, province, district, dong, waste_type)
    if (hit := _from_cache(key)) is not None:
        return hit
    with _inflight_lock:
        if _inflight["n"] >= MAX_QUEUE:
            raise Busy
        _inflight["n"] += 1
    try:
        if not _lock.acquire(blocking=False):    # another question, or the warm-up, is running
            report("queued" if _state["pipeline"] is not None else "loading")
            _lock.acquire()
        try:
            if (hit := _from_cache(key)) is not None:   # answered while this one waited
                return hit
            if _state["pipeline"] is None:
                report("loading")
            extra = {"progress": report} if progress else {}
            answer = check(_pipeline().answer(question, lang=lang, district=district,
                                              dong=dong, province=province,
                                              waste_type=waste_type, **extra))
        finally:
            _lock.release()
        _remember(key, answer)
        return answer
    except Exception as exc:                     # the user gets a handoff, never a traceback
        trace_id = str(uuid.uuid4())
        log.exception("ask failed (%s)", trace_id)
        append_jsonl(ERRORS_FILE, {"trace_id": trace_id, "time": _now(), "question": question,
                                   "lang": lang, "district": district, "dong": dong,
                                   "error": repr(exc), "traceback": traceback.format_exc()})
        return unavailable_answer(lang, district, dong, trace_id)
    finally:
        with _inflight_lock:
            _inflight["n"] -= 1


def _today() -> str:
    return datetime.now(KST).date().isoformat()


def _from_cache(key: tuple) -> dict | None:
    """The cached answer for `key` (a copy), recorded as a request in the traces."""
    with _answers_lock:
        answer = _answers.get(key)
        if answer is None:
            return None
        _answers.move_to_end(key)
        answer = copy.deepcopy(answer)
    _, question, lang, province, district, dong, waste_type = key
    try:                                         # eval/ops_summary.py counts it as a request
        write_trace({"trace_id": str(uuid.uuid4()), "time": _now(),
                     "cached_from": answer.get("trace_id"),
                     "input": {"question": question, "lang": lang, "district": district,
                               "province": province, "dong": dong, "waste_type": waste_type},
                     "resolved": {"lang": answer.get("lang")},
                     "answer": {"status": answer.get("status")}})
    except OSError:
        log.exception("could not record a cached answer")
    return answer


def _remember(key: tuple, answer: dict) -> None:
    with _answers_lock:
        _answers[key] = copy.deepcopy(answer)
        _answers.move_to_end(key)
        while len(_answers) > CACHE_SIZE:
            _answers.popitem(last=False)


def _reporter(progress: Callable[[str], None] | None) -> Callable[[str], None]:
    """`progress` wrapped so that a broken status box cannot break an answer."""
    def report(stage: str) -> None:
        if progress is None:
            return
        try:
            progress(stage)
        except Exception:
            log.exception("progress callback failed at %s", stage)
    return report


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
    sources = _stewardship(paths.STEWARDSHIP.stat().st_mtime_ns)["sources"]
    return [{"source": key, **record, "overdue": record["next_review"] < today}
            for key, record in sources.items()]


@lru_cache(maxsize=2)
def _stewardship(mtime_ns: int) -> dict:
    """The parsed file, read again only when it changes."""
    return json.loads(paths.STEWARDSHIP.read_text(encoding="utf-8"))


def _ollama_up() -> bool:
    """Whether Ollama answers, asked at most once per HEALTH_TTL_S."""
    now = time.monotonic()
    if _probe["at"] is not None and now - _probe["at"] < HEALTH_TTL_S:
        return _probe["up"]
    try:
        with urlopen(f"{config.OLLAMA_URL}/api/tags", timeout=2) as response:
            up = response.status == 200
    except (URLError, OSError):
        up = False
    _probe.update(at=now, up=up)
    return up


def health() -> dict:
    """What the page can show in a status line. Never loads the models; Ollama is asked at
    most every HEALTH_TTL_S seconds, so calling this on every page run is cheap."""
    return {"offline": _state["offline"],
            "ollama": False if _state["offline"] else _ollama_up(),
            "pipeline_loaded": _state["pipeline"] is not None, "model": config.LLM_MODEL,
            "trace_retention_days": TRACE_RETENTION_DAYS,
            "data_review_overdue": [r["source"] for r in data_reviews() if r["overdue"]]}


def pipeline_settings() -> dict | None:
    """The loaded pipeline's settings (models, Ollama digests, configuration), or None
    before the first question or the warm-up. For the maintainer view; never loads."""
    pipeline = _state["pipeline"]
    settings = getattr(pipeline, "settings", None)
    return settings() if callable(settings) else None


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")
