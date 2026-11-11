"""
Router / query rewriter (PLAN.md §4.3; Lesson 1 prompt contract, Lesson 5 rewriting).

One LLM call turns the raw question into a typed route:

    intent      item | schedule | both | out_of_scope
    item        copied from the question;  item_ko  its Korean name
    ko_query    Korean search query (the corpus is Korean)
    district, dong, waste_type, day_ref, negation, lang

The rewrite is checked before use (invariants), because a rewrite that drops or
invents an entity silently changes the question:

    item_in_question        the item really appears in the question
    ko_query_has_item       the Korean query still contains item_ko (repaired if not)
    district_in_question    a district the router returns is named in the question,
                            in Korean or romanised (otherwise dropped: never guess a place)
    dong_in_question        same for the neighbourhood
    negation_kept           a negation word in the question -> negation = true
    asks_when               an item question that also asks when ("Where and when do I
                            throw away a pizza box?") -> intent both, so the schedule is
                            looked up too (qwen2.5:7b routes these as item only)

Fallbacks: invalid JSON -> one retry -> route.valid = False, and the pipeline searches
with the original question only (Phase 1 behaviour). The original question is always
kept next to the rewrite in the trace.
"""
from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field

from rag import config
from rag.generate import load_prompt
from rag.korean import mentions_place
from rag.llm_client import LLMClient

INTENTS = ("item", "schedule", "both", "out_of_scope")
WASTE_TYPE_VALUES = ("none", "general", "food", "recycling", "bulky")
DAY_REFS = ("none", "today", "tonight", "tomorrow", "mon", "tue", "wed", "thu", "fri",
            "sat", "sun")

ROUTER_SCHEMA = {
    "type": "object",
    "properties": {
        "intent": {"type": "string", "enum": list(INTENTS)},
        "item": {"type": "string"},
        "item_ko": {"type": "string"},
        "ko_query": {"type": "string"},
        "district": {"type": "string"},
        "dong": {"type": "string"},
        "waste_type": {"type": "string", "enum": list(WASTE_TYPE_VALUES)},
        "day_ref": {"type": "string", "enum": list(DAY_REFS)},
        "negation": {"type": "boolean"},
        "lang": {"type": "string"},
    },
    "required": ["intent", "item", "item_ko", "ko_query", "district", "dong",
                 "waste_type", "day_ref", "negation", "lang"],
}

_NEGATION = re.compile(
    r"\bnot\b|n't\b|\bnever\b|안\s|않|아니|아닌|못\s|\bemas\b|\bне\b|không|不|没",
    re.IGNORECASE)

ASKS_WHEN = "item -> both (question asks when)"     # route.checks["intent_repaired"]

# The question asks when (a day or a time), in the six languages. English "when" counts only
# as a question word: first, next to another question word ("where when and how", "where,
# when", "how/when") or before a verb ("when is", "when to"), not as a conjunction
# ("...chicken bones when I'm done").
_WHEN = re.compile(
    r"^\W*when\b|\b(?:and|or|where|how|what)\s*[,/&]?\s*when\b"
    r"|\bwhen\s*(?:[,/&?]|(?:and|or|where|how|is|are|do|does|can|could|should|will|would|"
    r"to|must)\b)|\bwhat\s+(?:day|days|time)\b|\bwhich\s+(?:day|days)\b"
    r"|\bcollection\s+(?:day|days|time|times)\b|\bpick[- ]?up\s+(?:day|days)\b"
    r"|언제|요일|몇\s*시|수거\s*일|배출\s*일|수거\s*시간|배출\s*시간"
    r"|什么时候|哪天|哪一天|几点|星期几|周几|什么时间"
    r"|khi\s+nào|lúc\s+nào|ngày\s+nào|mấy\s+giờ|thứ\s+mấy"
    r"|\bqachon\b|qaysi\s+kun|soat\s+nechada"
    r"|когда|в\s+какой\s+день|в\s+какие\s+дни|во\s+сколько|по\s+каким\s+дням",
    re.IGNORECASE)


@dataclass
class Route:
    valid: bool                       # False -> fall back to the original question
    intent: str = "unknown"           # unknown = router off or failed
    item: str = ""
    item_ko: str = ""
    ko_query: str = ""
    district: str = ""
    dong: str = ""
    waste_type: str | None = None
    day_ref: str | None = None
    negation: bool = False
    lang: str | None = None
    checks: dict = field(default_factory=dict)
    attempts: list = field(default_factory=list)   # raw outputs, for the trace

    def to_trace(self) -> dict:
        return asdict(self)


def script_lang(text: str) -> str | None:
    """Language from the writing system, when it is unambiguous."""
    letters = [ch for ch in text if ch.isalpha()]
    if not letters:
        return None

    def share(lo: str, hi: str) -> float:
        return sum(lo <= ch <= hi for ch in letters) / len(letters)

    if share("가", "힣") > 0.3:
        return "ko"
    if share("぀", "ヿ") > 0.1:
        return "ja"
    if share("一", "鿿") > 0.3:
        return "zh"
    if share("Ѐ", "ӿ") > 0.3:
        return "ru"
    if sum(ch.isascii() for ch in letters) / len(letters) > 0.9:
        return "latin"
    return None


REPAIR = ("\n\nYour last answer wrote item_ko = \"{item_ko}\" and ko_query = \"{ko_query}\", "
          "which are not plain Korean. Return the same JSON object again, with item_ko and "
          "ko_query written only in Korean (Hangul), using the usual Korean name of the item.")


class Router:
    def __init__(self, llm: LLMClient, prompt_version: str = "v1",
                 temperature: float = config.TEMPERATURE, seed: int = config.SEED,
                 repair: bool = False):
        self.llm = llm
        self.prompt_version = prompt_version
        self.temperature, self.seed = temperature, seed
        self.repair = repair             # one retry when the rewrite fails the Korean check
        self.name = f"router_{prompt_version}{'+repair' if repair else ''}:{llm.model_id}"

    def route(self, question: str) -> Route:
        system, user = load_prompt(f"router_{self.prompt_version}")
        prompt = user.replace("{question}", question)
        attempts, data = [], None
        for attempt in range(2):                         # one retry (PLAN.md §4.3)
            suffix = "" if attempt == 0 else "\n\nReturn only the JSON object."
            result = self.llm.generate(system=system, prompt=prompt + suffix,
                                       json_schema=ROUTER_SCHEMA, max_tokens=256,
                                       temperature=self.temperature, seed=self.seed)
            attempts.append({"raw": result.text, "latency_s": result.latency_s,
                             "prompt_tokens": result.prompt_tokens,
                             "completion_tokens": result.completion_tokens})
            data = _parse(result.text)
            if data is not None:
                break
        if data is None:
            return Route(valid=False, lang=script_lang(question), attempts=attempts,
                         checks={"fallback": "router output was not valid JSON twice"})
        route = Route(valid=True, attempts=attempts, **data)
        route.checks = check_invariants(question, route)
        if self.repair and needs_repair(route):
            repaired = self._repair(system, prompt, question, route)
            if repaired is not None:
                return repaired
            route.checks["repair"] = "tried; the second rewrite was not usable either"
        return route

    def _repair(self, system: str, prompt: str, question: str, route: Route) -> Route | None:
        """Ask once more for a Hangul-only rewrite (dev: qwen2.5:7b wrote '기름occo散布的纸张'
        for Uzbek frying oil and '#gaşorke su kapağı' for Russian soda bottles)."""
        suffix = REPAIR.format(item_ko=route.item_ko, ko_query=route.ko_query)
        result = self.llm.generate(system=system, prompt=prompt + suffix,
                                   json_schema=ROUTER_SCHEMA, max_tokens=256,
                                   temperature=self.temperature, seed=self.seed)
        attempts = [*route.attempts, {"raw": result.text, "latency_s": result.latency_s,
                                      "prompt_tokens": result.prompt_tokens,
                                      "completion_tokens": result.completion_tokens,
                                      "repair": True}]
        data = _parse(result.text)
        if data is None:
            route.attempts = attempts
            return None
        second = Route(valid=True, attempts=attempts, **data)
        second.checks = check_invariants(question, second)
        if not second.checks.get("rewrite_usable"):
            route.attempts = attempts
            return None
        second.checks["repair"] = (f"rewrite repaired: {route.item_ko!r} -> "
                                   f"{second.item_ko!r}")
        return second


def needs_repair(route: Route) -> bool:
    """A rewrite that exists but failed the Korean check (not out of scope, not empty)."""
    return (route.intent != "out_of_scope" and bool(route.item_ko or route.ko_query)
            and not route.checks.get("rewrite_usable", False)
            and (route.checks.get("item_ko_korean") is False
                 or route.checks.get("ko_query_korean") is False))


def _parse(text: str) -> dict | None:
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return None
    if not isinstance(data, dict) or set(ROUTER_SCHEMA["required"]) - set(data):
        return None
    if data["intent"] not in INTENTS:
        return None
    out = {k: (data[k].strip() if isinstance(data[k], str) else data[k])
           for k in ROUTER_SCHEMA["required"]}
    out["waste_type"] = None if out["waste_type"] in ("none", "", None) else out["waste_type"]
    out["day_ref"] = None if out["day_ref"] in ("none", "", None) else out["day_ref"]
    out["negation"] = bool(out["negation"])
    out["lang"] = (out["lang"] or "").lower()[:2] or None
    return out


def check_invariants(question: str, route: Route) -> dict:
    """Check (and where safe, repair) the rewrite against the original question."""
    checks = {}
    q = question.lower()
    if route.item:
        words = [w for w in re.findall(r"\w+", route.item.lower()) if len(w) > 1]
        checks["item_in_question"] = route.item.lower() in q or (
            bool(words) and all(w in q for w in words))
    if route.intent == "schedule" and route.item:      # an item was named -> both parts
        checks["intent_repaired"] = "schedule -> both (question names an item)"
        route.intent = "both"
    if route.intent == "item" and _WHEN.search(question):   # ...and it asks when -> both
        checks["intent_repaired"] = ASKS_WHEN
        route.intent = "both"
    if route.intent != "out_of_scope" and (route.item_ko or route.ko_query):
        # The rewrite is only used for search if it is really Korean (qwen2.5:7b sometimes
        # mixes Chinese characters into item_ko for low-resource languages).
        if route.item_ko:
            checks["item_ko_korean"] = is_korean(route.item_ko, strict=True)
        checks["ko_query_korean"] = is_korean(route.ko_query)
    if route.item_ko and route.intent != "out_of_scope":
        has = route.item_ko.replace(" ", "") in route.ko_query.replace(" ", "")
        checks["ko_query_has_item"] = has
        if not has:                                       # repair: put the item back
            route.ko_query = f"{route.item_ko} {route.ko_query}".strip()
    if route.district:
        checks["district_in_question"] = mentions_place(question, route.district)
        if not checks["district_in_question"]:
            checks["dropped_district"] = route.district
            route.district = ""
    if route.dong:
        checks["dong_in_question"] = mentions_place(question, route.dong)
        if not checks["dong_in_question"]:
            checks["dropped_dong"] = route.dong
            route.dong = ""
    cue = bool(_NEGATION.search(question))
    checks["negation_kept"] = route.negation or not cue
    if cue and not route.negation:
        route.negation = True
    detected = script_lang(question)
    if detected == "latin":                     # Latin script: en, uz, vi, ... but not ko/zh
        detected = "en" if route.lang in ("ko", "zh", "ja", "ru", None) else None
    if detected and route.lang != detected:
        checks["lang_corrected"] = f"{route.lang} -> {detected}"
        route.lang = detected
    checks["rewrite_usable"] = (route.intent != "out_of_scope"
                                and checks.get("item_ko_korean", True)
                                and checks.get("ko_query_korean", False))
    return checks


def is_korean(text: str, strict: bool = False) -> bool:
    """Hangul text (Latin letters/digits allowed, e.g. 'PET병'). strict: no other script
    at all; otherwise at least half of the letters must be Hangul."""
    letters = [ch for ch in text or "" if ch.isalpha()]
    if not letters:
        return False
    hangul = sum("가" <= ch <= "힣" for ch in letters)
    other = sum(not ("가" <= ch <= "힣") and not ch.isascii() for ch in letters)
    if strict:
        return hangul > 0 and other == 0
    return hangul / len(letters) >= 0.5 and other == 0
