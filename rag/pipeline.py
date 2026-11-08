"""
End-to-end pipeline (PLAN.md §4). Every stage is set by one PipelineConfig
(rag/config.py), so an experiment changes one field (PLAN.md §6).

    question
      -> router: intent, item, Korean rewrite, location, waste type, day   (LLM call 1)
      -> item retrieval: dense / BM25 / hybrid RRF -> rerank -> top k_final
      -> schedule tool: typed lookup + date check (deterministic)
      -> gate: answer / abstain / clarify / out of scope, per part
           (nothing answerable -> fixed message + handoff, no LLM call)
      -> context under token budget -> generator (LLM call 2, JSON schema), items only
      -> parse + citation check -> validation (allowed bins, support)
      -> schedule text: days, times, places by code; method translated (small LLM call)
      -> answer dict (+ handoff, notes) and one JSON trace per request

Interfaces for teammates:
    Pipeline().answer(question, lang, district, dong)  -> answer dict   (website)
    Pipeline().run_case(case)                          -> full trace    (evaluation)
    Pipeline(config.BASELINE)                          -> the Phase 1 system

Command line: python -m rag "..." (rag/__main__.py).
"""
from __future__ import annotations

import time
import uuid
from dataclasses import asdict, dataclass
from datetime import UTC, datetime

from rag import config
from rag.answer import build_answer
from rag.config import PipelineConfig
from rag.context import ContextBudget, default_counter, pack_evidence, schedule_evidence
from rag.contract import problems
from rag.gate import MAX_ZONES, GateDecision, decide
from rag.generate import ANSWER_SCHEMA, build_prompt, parse_answer
from rag.handoff import message
from rag.llm_client import LLMClient, make_client
from rag.retrieve import ItemRetriever
from rag.router import Route, Router
from rag.schedule_text import ScheduleWriter, merge_schedule
from rag.schedule_tool import (
    DAY_EN,
    DayRef,
    ScheduleResult,
    ScheduleRow,
    default_table,
    resolve_day,
    waste_types,
)
from rag.schedule_vector import ScheduleVectorSearch
from rag.tracing import timed, write_trace
from rag.validate import days_mentioned, validate

PIPELINE_VERSION = "v2"


@dataclass(frozen=True)
class Request:
    """One question with its inputs settled. Explicit inputs (website dropdowns, an eval
    case) win over what the router read."""
    question: str
    intent: str
    lang: str | None
    district: str | None
    province: str | None
    dong: str | None
    waste_type: str | None
    day_ref: str | None
    location_source: str | None        # input | router | None

    @classmethod
    def resolve(cls, question: str, route: Route, lang: str | None, district: str | None,
                province: str | None, dong: str | None, waste_type: str | None) -> Request:
        same_district = not district or not route.district or route.district == district
        return cls(question=question,
                   intent=route.intent if route.valid else "unknown",
                   lang=lang or route.lang,
                   district=district or route.district or None,
                   province=province,
                   dong=dong or (route.dong if same_district else "") or None,
                   waste_type=waste_type or route.waste_type,
                   day_ref=day_asked(question, route.day_ref),
                   location_source=("input" if district else
                                    "router" if route.district else None))

    def to_trace(self) -> dict:
        return {k: v for k, v in asdict(self).items() if k != "question"}


class Pipeline:
    def __init__(self, cfg: PipelineConfig | None = None, llm: LLMClient | None = None,
                 write_traces: bool = True, router_llm: LLMClient | None = None):
        self.cfg = cfg or config.DEFAULT
        self.llm = llm or make_client("ollama", self.cfg.llm_model)
        self.retriever = ItemRetriever(self.cfg)
        self.schedule = default_table()
        self.schedule_search = (None if self.cfg.schedule_retrieval == "structured"
                                else ScheduleVectorSearch(self.schedule, self.cfg))
        self.writer = ScheduleWriter(self.llm, self.cfg.temperature, self.cfg.seed)
        self.router = None
        if self.cfg.router:
            if router_llm is None:
                router_llm = (make_client("ollama", self.cfg.router_model)
                              if self.cfg.router_model else self.llm)
            self.router = Router(router_llm, temperature=self.cfg.temperature,
                                 seed=self.cfg.seed)
        self.counter = default_counter(
            config.LLM_TOKENIZERS.get(self.llm.model_id, config.LLM_TOKENIZER))
        self.budget = ContextBudget()
        self.write_traces = write_traces

    def settings(self) -> dict:
        return {"pipeline_version": PIPELINE_VERSION, "config": self.cfg.to_dict(),
                "retriever": self.retriever.name, "collection": self.retriever.collection,
                "router": self.router.name if self.router else None,
                "llm": self.llm.model_id, "schedule_source": self.schedule.source,
                "schedule_retriever": (self.schedule_search.name if self.schedule_search
                                       else "structured lookup")}

    # ------------------------------------------------------------------ entry points
    def answer(self, question: str, lang: str | None = None, district: str | None = None,
               dong: str | None = None, province: str | None = None,
               waste_type: str | None = None) -> dict:
        """Website interface (PLAN.md §4.12): returns only the answer dict."""
        return self.run(question, lang, district, province, dong, waste_type)["answer"]

    def run_case(self, case: dict, stop_after_retrieval: bool = False) -> dict:
        """Evaluation interface (PLAN.md §7.1): case -> full trace (+ case_id)."""
        location = case.get("location") or {}
        trace = self.run(case["question"], case.get("lang"), location.get("district"),
                         location.get("province"), location.get("dong"),
                         case.get("waste_type"), stop_after_retrieval)
        trace["case_id"] = case.get("case_id") or case.get("probe_id")
        return trace

    def run(self, question: str, lang: str | None = None, district: str | None = None,
            province: str | None = None, dong: str | None = None,
            waste_type: str | None = None, stop_after_retrieval: bool = False) -> dict:
        """Full trace for one request (everything needed to explain the answer)."""
        start = time.perf_counter()
        timings: dict[str, float] = {}
        trace = {"trace_id": str(uuid.uuid4()),
                 "time": datetime.now(UTC).isoformat(timespec="seconds"),
                 "settings": self.settings(),
                 "input": {"question": question, "lang": lang, "district": district,
                           "province": province, "dong": dong, "waste_type": waste_type}}

        with timed(timings, "route_s"):
            route = self.route(question)
        trace["route"] = route.to_trace()
        request = Request.resolve(question, route, lang, district, province, dong, waste_type)
        trace["resolved"] = request.to_trace()

        selected = self._retrieve_items(request, route, trace, timings)
        if stop_after_retrieval:
            timings["total_s"] = round(time.perf_counter() - start, 3)
            trace["timings"] = timings
            return trace

        with timed(timings, "schedule_s"):
            schedule, day = self._lookup_schedule(request, route, trace)

        tau = self.cfg.gate_tau if self.cfg.rerank else None
        gate = decide(request.intent, selected, schedule, request.district, request.dong, tau,
                      route.item_ko)
        trace["gate"] = gate.to_trace()
        rows = schedule.rows[:MAX_ZONES] if gate.schedule == "answer" else []

        draft, evidence = self._draft(request, route, gate, selected, rows, day, trace, timings)
        if self._code_writes_schedule(rows):
            draft, evidence = self._add_schedule_text(draft, evidence, request, gate, rows, day,
                                                      trace, timings)

        timings["total_s"] = round(time.perf_counter() - start, 3)
        trace["timings"] = timings
        trace["answer"] = build_answer(draft, evidence, request=request, route=route, gate=gate,
                                       schedule=schedule, rows=rows, day=day,
                                       trace_id=trace["trace_id"])
        trace["contract_problems"] = problems(trace["answer"])
        if self.write_traces:
            write_trace(trace)
        return trace

    # ------------------------------------------------------------------ stages
    def route(self, question: str) -> Route:
        if self.router is None:
            return Route(valid=False, checks={"fallback": "router off"})
        return self.router.route(question)

    def retrieve(self, question: str, route: Route):
        rewrite_ok = route.valid and route.checks.get("rewrite_usable", False)
        queries = {}
        if self.cfg.query_mode in ("original", "both") or not rewrite_ok:
            queries["original"] = question
        if self.cfg.query_mode in ("rewrite", "both") and rewrite_ok:
            queries["rewrite"] = route.ko_query
        mode = self.cfg.rerank_query if rewrite_ok else "original"
        rerank_queries = {"original": [question], "rewrite": [route.ko_query],
                          "max": [question, route.ko_query]}[mode]
        return self.retriever.search(queries, rerank_queries)

    def _retrieve_items(self, request: Request, route: Route, trace: dict,
                        timings: dict[str, float]) -> list:
        candidates, selected = [], []
        if request.intent in ("item", "both", "unknown"):
            candidates, selected, record = self.retrieve(request.question, route)
            timings.update(record.pop("timings"))
            trace["retrieval"] = record
        trace["candidates"] = [c.to_trace() for c in candidates]
        trace["selected"] = [c.chunk_id for c in selected]
        return selected

    def _lookup_schedule(self, request: Request, route: Route,
                         trace: dict) -> tuple[ScheduleResult | None, DayRef | None]:
        wanted = request.intent in ("schedule", "both") or (
            request.intent == "unknown" and request.district)
        if not wanted or not request.district:
            return None, None
        if self.schedule_search:                       # E4 only
            usable = route.valid and route.checks.get("rewrite_usable", False)
            schedule = self.schedule_search.search(
                route.ko_query if usable else request.question, request.district,
                request.province, request.dong, request.waste_type)
        else:
            schedule = self.schedule.lookup(request.district, request.province, request.dong,
                                            request.waste_type)
        trace["schedule"] = schedule.to_trace()
        return schedule, resolve_day(request.day_ref)

    def _code_writes_schedule(self, rows: list[ScheduleRow]) -> bool:
        """With schedule_text = code the generator never sees days, times or places."""
        return self.cfg.schedule_text == "code" and bool(rows)

    def _draft(self, request: Request, route: Route, gate: GateDecision, selected: list,
               rows: list[ScheduleRow], day: DayRef | None, trace: dict,
               timings: dict[str, float]) -> tuple[dict | None, list]:
        """The answer before any code-written schedule text. None: the schedule is all
        there is to say, and code writes it."""
        trace["llm"], trace["checks"], trace["evidence"] = None, {}, []
        if gate.status != "ANSWER":                    # nothing answerable: no LLM call
            return fixed_answer(gate, request.lang), []
        item_evidence = selected if gate.item == "answer" else []
        llm_rows = [] if self._code_writes_schedule(rows) else rows
        if not item_evidence and not llm_rows:
            return None, []
        return self._generate(request, route, gate, item_evidence, llm_rows, day, trace, timings)

    def _generate(self, request: Request, route: Route, gate: GateDecision, item_evidence: list,
                  llm_rows: list[ScheduleRow], day: DayRef | None, trace: dict,
                  timings: dict[str, float]) -> tuple[dict, list]:
        """LLM call 2, then parsing, citation check and validation."""
        asked = request.question
        if self.cfg.schedule_text == "code" and gate.schedule != "skip":
            asked = item_only_question(request.question, route)

        def prompt_with(evidence_text: str) -> tuple[str, str]:
            return build_prompt(self.cfg.prompt_version, asked, evidence_text, request.lang,
                                self.cfg.conflict_policy)

        system, empty = prompt_with("")
        evidence, evidence_text, budget = pack_evidence(
            item_evidence, llm_rows, request.waste_type, system + "\n" + empty,
            self.counter, self.budget, day)
        trace["evidence"] = [e.to_citation() for e in evidence]
        trace["budget"] = budget
        system, prompt = prompt_with(evidence_text)
        with timed(timings, "generate_s"):
            result = self.llm.generate(system=system, prompt=prompt, json_schema=ANSWER_SCHEMA,
                                       temperature=self.cfg.temperature, seed=self.cfg.seed)
        draft, checks = parse_answer(result.text, len(evidence))
        checks["output_truncated"] = result.done_reason == "length"
        trace["llm"] = {"model_id": result.model_id, "raw_output": result.text,
                        "prompt_tokens_measured": result.prompt_tokens,
                        "completion_tokens": result.completion_tokens,
                        "done_reason": result.done_reason}
        # A schedule question with no rows shown: any day the model states is invented.
        days = (schedule_days(llm_rows, request.waste_type) if llm_rows
                else set() if gate.schedule != "skip" else None)
        draft, validation = validate(draft, evidence, days, self.cfg.validation,
                                     item_question=gate.item == "answer")
        if draft.get("status") not in ("ANSWER", "INSUFFICIENT_CONTEXT"):
            # Not JSON, or a status outside the schema: say nothing rather than guess.
            validation["unusable_output"] = draft.get("status")
            draft.update(status="INSUFFICIENT_CONTEXT", bin="", bin_en="", citations=[],
                         missing=draft.get("missing") or "model output was unusable")
            validation["downgraded"] = True
        if validation.get("downgraded"):
            draft["answer_text"] = message("INSUFFICIENT_CONTEXT", request.lang)
        trace["checks"] = {**checks, "validation": validation}
        return draft, evidence

    def _add_schedule_text(self, draft: dict | None, evidence: list, request: Request,
                           gate: GateDecision, rows: list[ScheduleRow], day: DayRef | None,
                           trace: dict, timings: dict[str, float]) -> tuple[dict, list]:
        with timed(timings, "schedule_text_s"):
            item_missing = ""
            if draft and draft.get("status") != "ANSWER":   # the schedule stands without it
                item_missing, draft, evidence = draft.get("missing", ""), None, []
                gate.item = "abstain"
                gate.reasons.append("item answer did not pass; schedule answered alone")
                trace["gate"] = gate.to_trace()
            first_number = len(evidence) + 1
            row_evidence = [schedule_evidence(r, request.waste_type, day) for r in rows]
            for number, item in enumerate(row_evidence, first_number):
                item.n = number
            written, record = self.writer.write(rows, request.waste_type, request.lang, day,
                                                first_number)
            draft = merge_schedule(draft, written)
            draft["missing"] = draft["missing"] or item_missing
        evidence = evidence + row_evidence
        trace["evidence"] = [e.to_citation() for e in evidence]
        trace["schedule_text"] = record
        return draft, evidence


def fixed_answer(gate: GateDecision, lang: str | None) -> dict:
    key = "SCHEDULE_VARIES" if gate.schedule_varies else gate.status
    return {"status": gate.status, "bin": "", "bin_en": "", "how_to_prepare": [],
            "answer_text": message(key, lang), "citations": [],
            "missing": "; ".join(gate.reasons)}


def day_asked(question: str, routed: str | None) -> str | None:
    """One weekday named in the question beats the router, which read 화요일 as Wednesday."""
    named = days_mentioned(question)
    return DAY_EN[next(iter(named))].lower() if len(named) == 1 else routed


def item_only_question(question: str, route: Route) -> str:
    """What the generator is asked when the schedule part is not its job. Asked the whole
    question with no schedule to read, it copied the days of its few-shot example."""
    rule = "Answer only about the item. Do not mention days or times."
    return f"How do I throw away {route.item}? {rule}" if route.item else f"{question}\n({rule})"


def schedule_days(rows: list[ScheduleRow], waste_type: str | None) -> set[int]:
    return {d for r in rows for t in waste_types(waste_type) for d in r.rules[t].days}
