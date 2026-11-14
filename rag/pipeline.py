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
    Pipeline().answer(..., progress=callback)          -> callback("route"), ("retrieve"),
                                                          ("schedule"), ("write") as each
                                                          stage starts (the page's status box)
    Pipeline().run_case(case)                          -> full trace    (evaluation)
    Pipeline(config.BASELINE)                          -> the Phase 1 system

Command line: python -m rag "..." (rag/__main__.py).
"""
from __future__ import annotations

import time
import uuid
from collections.abc import Callable
from dataclasses import asdict, dataclass, replace
from datetime import UTC, datetime

from rag import config
from rag.answer import build_answer
from rag.bins import BIN_WASTE_TYPE
from rag.config import PipelineConfig
from rag.context import ContextBudget, default_counter, pack_evidence, schedule_evidence
from rag.contract import answer_bins, problems
from rag.gate import MAX_ZONES, GateDecision, decide
from rag.generate import answer_schema, build_prompt, parse_answer
from rag.handoff import message
from rag.llm_client import LLMClient, make_client, model_digest
from rag.places import read_place
from rag.retrieve import ItemRetriever
from rag.router import ASKS_WHEN, Route, Router
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
ITEM_INTENTS = ("item", "both", "unknown")

# Told the name of each stage as it starts. It only observes: the answer is the same with or
# without it (tests/test_pipeline_run.py).
Progress = Callable[[str], None]
STAGES = ("route", "retrieve", "schedule", "write")


def _no_progress(stage: str) -> None:
    pass


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
                 write_traces: bool = True, router_llm: LLMClient | None = None, *,
                 retriever=None, schedule=None, counter=None):
        """`retriever`, `schedule` and `counter` replace the defaults (index-backed retriever,
        the processed table, the generator's tokenizer); tests hand in stand-ins."""
        self.cfg = cfg or config.DEFAULT
        self.llm = llm or make_client("ollama", self.cfg.llm_model)
        self.retriever = retriever or ItemRetriever(self.cfg)
        self.schedule = schedule or default_table()
        self.schedule_search = (None if self.cfg.schedule_retrieval == "structured"
                                else ScheduleVectorSearch(self.schedule, self.cfg))
        self.writer = ScheduleWriter(self.llm, self.cfg.temperature, self.cfg.seed)
        self.router = None
        if self.cfg.router:
            if router_llm is None:
                router_llm = (make_client("ollama", self.cfg.router_model)
                              if self.cfg.router_model else self.llm)
            self.router = Router(router_llm, temperature=self.cfg.temperature,
                                 seed=self.cfg.seed, repair=self.cfg.router_repair,
                                 prompt_version=self.cfg.router_prompt)
        self.counter = counter or default_counter(
            config.LLM_TOKENIZERS.get(self.llm.model_id, config.LLM_TOKENIZER))
        self.budget = ContextBudget()
        self.write_traces = write_traces
        # Robustness probes only (experiments/robustness.py, PLAN.md §7.6): a function
        # (selected, trace) -> selected that changes the evidence before the gate.
        self.evidence_hook = None

    def settings(self) -> dict:
        return {"pipeline_version": PIPELINE_VERSION, "config": self.cfg.to_dict(),
                "retriever": self.retriever.name, "collection": self.retriever.collection,
                "router": self.router.name if self.router else None,
                "llm": self.llm.model_id, "llm_digest": model_digest(self.llm),
                "router_digest": model_digest(self.router.llm) if self.router else None,
                "schedule_source": self.schedule.source,
                "schedule_retriever": (self.schedule_search.name if self.schedule_search
                                       else "structured lookup")}

    # ------------------------------------------------------------------ entry points
    def answer(self, question: str, lang: str | None = None, district: str | None = None,
               dong: str | None = None, province: str | None = None,
               waste_type: str | None = None, *, progress: Progress | None = None) -> dict:
        """Website interface (PLAN.md §4.12): returns only the answer dict."""
        return self.run(question, lang, district, province, dong, waste_type,
                        progress=progress)["answer"]

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
            waste_type: str | None = None, stop_after_retrieval: bool = False, *,
            progress: Progress | None = None) -> dict:
        """Full trace for one request (everything needed to explain the answer)."""
        emit = progress or _no_progress
        start = time.perf_counter()
        timings: dict[str, float] = {}
        trace = {"trace_id": str(uuid.uuid4()),
                 "time": datetime.now(UTC).isoformat(timespec="seconds"),
                 "settings": self.settings(),
                 "input": {"question": question, "lang": lang, "district": district,
                           "province": province, "dong": dong, "waste_type": waste_type}}

        emit("route")
        with timed(timings, "route_s"):
            route = self.route(question)
        trace["route"] = route.to_trace()
        if self.cfg.place_reader and not district:
            place = read_place(question)
            trace["place"] = place.to_trace() if place else None
            if place:
                # Read by code from the table's own names: it wins over the router's guess.
                # A name in several provinces keeps them all, so the schedule tool asks.
                router_place = (route.district, route.dong)
                route.district = place.district
                route.dong = place.dong or (route.dong if router_place[0] == place.district
                                            else "")
                if len(place.provinces) == 1:
                    province = place.provinces[0]
                trace["place"]["router_had"] = list(router_place)
        request = Request.resolve(question, route, lang, district, province, dong, waste_type)
        trace["resolved"] = request.to_trace()

        if request.intent in ITEM_INTENTS:
            emit("retrieve")
        selected = self._retrieve_items(request, route, trace, timings)
        if self.evidence_hook is not None:
            selected = self.evidence_hook(selected, trace)
            trace["selected"] = [c.chunk_id for c in selected]
        if stop_after_retrieval:
            timings["total_s"] = round(time.perf_counter() - start, 3)
            trace["timings"] = timings
            return trace

        if self._wants_schedule(request):
            emit("schedule")
        with timed(timings, "schedule_s"):
            schedule, day = self._lookup_schedule(request, route, trace)

        tau = self.cfg.gate_tau if self.cfg.rerank else None
        gate = decide(request.intent, selected, schedule, request.district, request.dong, tau,
                      route.item_ko)
        trace["gate"] = gate.to_trace()
        rows = schedule.rows[:MAX_ZONES] if gate.schedule == "answer" else []

        if gate.status == "ANSWER":
            emit("write")
        draft, evidence = self._draft(request, route, gate, selected, rows, day, trace, timings)
        if self._adds_local_days(request, draft):
            request, schedule, day, rows, gate = self._local_days(request, draft, gate,
                                                                  schedule, day, rows, trace)
        if self._code_writes_schedule(rows):
            draft, evidence, gate = self._add_schedule_text(draft, evidence, request, gate, rows,
                                                            day, trace, timings)

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
        names = []
        if route.valid and route.item:                 # the item as the user named it
            names.append(route.item)
            if route.item_ko and route.checks.get("item_ko_korean"):
                names.append(route.item_ko)
        if self.cfg.rerank_item and names:
            rerank_queries = [*rerank_queries, *names]
        if not (route.valid and route.intent != "out_of_scope" and len(route.items) > 1):
            return self.retriever.search(queries, rerank_queries, item_names=names)
        return self._retrieve_each(question, route)

    def _retrieve_each(self, question: str, route: Route):
        """Several items: one search per item, then the reranked lists taken in turn
        (round-robin, no repeats), so every item has evidence in the top k_final. An item
        whose Korean rewrite failed the checks is searched with the question instead."""
        usable = [route.checks.get("rewrite_usable", False),
                  *(c.get("rewrite_usable", False) for c in route.checks.get("items", []))]
        items = route.items
        per_item, runs, timings = [], [], {}
        for entry, ok in zip(items, usable, strict=False):
            names = [entry["item"]] + ([entry["item_ko"]] if ok and entry["item_ko"] else [])
            if ok:
                queries = {"original": entry["item"], "rewrite": entry["ko_query"]}
                rerank = [q for q in (entry["ko_query"], entry["item_ko"], entry["item"]) if q]
            else:
                queries, rerank = {"original": question}, [question, entry["item"]]
            candidates, _, record = self.retriever.search(queries, rerank,
                                                          item_names=[n for n in names if n])
            for key, value in record.pop("timings").items():
                timings[key] = round(timings.get(key, 0.0) + value, 3)
            per_item.append({"item": entry["item"], **record,
                             "top": [c.chunk_id for c in candidates[:self.cfg.k_final]]})
            runs.append(candidates)
        share = max(2, -(-self.cfg.k_final // len(items)))       # ceil(k_final / n)
        merged, seen = [], set()
        for depth in range(max(len(r) for r in runs)):
            for run in runs:
                if depth < len(run) and run[depth].chunk_id not in seen:
                    seen.add(run[depth].chunk_id)
                    merged.append((depth, run[depth]))
        # the first `share` of each item first, then everything else in turn
        merged.sort(key=lambda dc: dc[0] >= share)
        candidates = [replace(c, rank=r) for r, (_, c) in enumerate(merged, 1)]
        record = {"per_item": per_item, "share": share, "timings": timings}
        return candidates, candidates[:self.cfg.k_final], record

    def _retrieve_items(self, request: Request, route: Route, trace: dict,
                        timings: dict[str, float]) -> list:
        candidates, selected = [], []
        if request.intent in ITEM_INTENTS:
            candidates, selected, record = self.retrieve(request.question, route)
            timings.update(record.pop("timings"))
            trace["retrieval"] = record
        trace["candidates"] = [c.to_trace() for c in candidates]
        trace["selected"] = [c.chunk_id for c in selected]
        return selected

    def _lookup_schedule(self, request: Request, route: Route,
                         trace: dict) -> tuple[ScheduleResult | None, DayRef | None]:
        if not self._wants_schedule(request):
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

    @staticmethod
    def _wants_schedule(request: Request) -> bool:
        wanted = request.intent in ("schedule", "both") or (
            request.intent == "unknown" and request.district)
        return bool(wanted and request.district)

    def _adds_local_days(self, request: Request, draft: dict | None) -> bool:
        """An item question with an area chosen on the page (not read from the question):
        the answer also gets the collection days of the answered bin there."""
        return (request.intent == "item" and request.location_source == "input"
                and bool(request.district) and self.cfg.schedule_text == "code"
                and bool(draft) and draft.get("status") == "ANSWER")

    def _local_days(self, request: Request, draft: dict, gate: GateDecision,
                    schedule: ScheduleResult | None, day: DayRef | None,
                    rows: list[ScheduleRow], trace: dict):
        """The collection days for the answered bin's type (rag.bins.BIN_WASTE_TYPE) in the
        chosen area, written by code like any schedule answer. Added only when the gate would
        answer that schedule question as it is (one province, at most MAX_ZONES zones, same
        days); otherwise the item answer stays as it was and nothing is asked."""
        types = sorted({BIN_WASTE_TYPE[b] for b in answer_bins(draft) if b in BIN_WASTE_TYPE})
        record = {"bins": answer_bins(draft), "types": types, "added": False}
        trace["local_days"] = record
        if not types:
            record["why"] = "no collection type for the bin"
            return request, schedule, day, rows, gate
        waste_type = types[0] if len(types) == 1 else None          # several: every type
        local = self.schedule.lookup(request.district, request.province, request.dong,
                                     waste_type)
        verdict = decide("schedule", [], local, request.district, request.dong, None, "")
        if verdict.schedule != "answer":
            record["why"] = "; ".join(verdict.reasons)
            return request, schedule, day, rows, gate
        record["added"] = True
        trace["schedule"] = local.to_trace()
        gate = replace(gate, schedule="answer", reasons=[
            *gate.reasons, f"area chosen: {waste_type or 'all'} collection days added"])
        trace["gate"] = gate.to_trace()
        request = replace(request, waste_type=waste_type)
        return request, local, resolve_day(request.day_ref), local.rows[:MAX_ZONES], gate

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
        if (self.cfg.schedule_text == "code" and gate.schedule != "skip"
                and route.checks.get("intent_repaired") != ASKS_WHEN):
            asked = item_only_question(request.question, route)

        def prompt_with(evidence_text: str, question: str = asked) -> tuple[str, str]:
            return build_prompt(self.cfg.prompt_version, question, evidence_text, request.lang,
                                self.cfg.conflict_policy)

        system, empty = prompt_with("")
        evidence, evidence_text, budget = pack_evidence(
            item_evidence, llm_rows, request.waste_type, system + "\n" + empty,
            self.counter, self.budget, day)
        trace["evidence"] = [e.to_citation() for e in evidence]
        trace["budget"] = budget
        system, prompt = prompt_with(evidence_text)
        with timed(timings, "generate_s"):
            result = self.llm.generate(system=system, prompt=prompt,
                                       json_schema=answer_schema(self.cfg.prompt_version),
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
        model_answered = draft.get("status") == "ANSWER"       # before validation downgrades
        draft, validation = validate(draft, evidence, days, self.cfg.validation,
                                     item_question=gate.item == "answer")
        conflict = bool(validation.get("bin_text_conflict"))
        rejected = (self.cfg.generation_retry == "rejected" and model_answered
                    and bool(validation.get("reasons")))
        if validation.get("downgraded") and (conflict or rejected):
            # Ask once more, saying why the answer was rejected; keep the new answer only if
            # it passes every check. Only answers that would be withheld are retried.
            #   conflict: the text names another bin than the bin field, e.g. a pizza box
            #     (종이) whose greasy inner paper goes in 종량제봉투, with only the second in
            #     the text (always on).
            #   rejected (generation_retry = "rejected"): any other check failed, most often
            #     a bin that the cited evidence does not state. On dev v2 (v5) 10 of the 13
            #     withheld answers had a gold chunk in the evidence: 6 named the right bin
            #     but cited another number, 4 named another bin.
            note = (BIN_CONFLICT_NOTE.format(bin=validation["bin"],
                                             named=", ".join(validation["bins_in_text"]))
                    if conflict else REJECTED_NOTE.format(
                        # with "(they state [...])": dev v2 (v6 + router v2) 7 retried answers
                        # became correct, 4 became false (the chunk was about another item).
                        # Without it the model repeated itself: 0 correct, 0 false.
                        reasons="; ".join(validation["reasons"])))
            retry_system, retry_prompt = prompt_with(evidence_text, f"{asked}\n({note})")
            with timed(timings, "generate_retry_s"):
                retry = self.llm.generate(system=retry_system, prompt=retry_prompt,
                                          json_schema=answer_schema(self.cfg.prompt_version),
                                          temperature=self.cfg.temperature, seed=self.cfg.seed)
            retry_draft, retry_checks = parse_answer(retry.text, len(evidence))
            retry_draft, retry_validation = validate(
                retry_draft, evidence, days, self.cfg.validation,
                item_question=gate.item == "answer")
            passed = (retry_draft.get("status") == "ANSWER"
                      and not retry_validation.get("downgraded"))
            trace["llm"]["retry"] = {
                "kind": "bin_conflict" if conflict else "rejected", "note": note,
                "raw_output": retry.text, "done_reason": retry.done_reason,
                "first_reasons": validation["reasons"], "passed": passed}
            if passed:
                retry_checks["output_truncated"] = retry.done_reason == "length"
                draft, checks = retry_draft, retry_checks
                validation = {**retry_validation, "retried_after": validation["reasons"]}
        if draft.get("status") not in ("ANSWER", "INSUFFICIENT_CONTEXT"):
            # Not JSON, or a status outside the schema: say nothing rather than guess.
            validation["unusable_output"] = draft.get("status")
            draft.update(status="INSUFFICIENT_CONTEXT", bin="", bin_en="", citations=[], items=[],
                         missing=draft.get("missing") or "model output was unusable")
            validation["downgraded"] = True
        if validation.get("downgraded"):
            draft["answer_text"] = message("INSUFFICIENT_CONTEXT", request.lang)
        trace["checks"] = {**checks, "validation": validation}
        return draft, evidence

    def _add_schedule_text(self, draft: dict | None, evidence: list, request: Request,
                           gate: GateDecision, rows: list[ScheduleRow], day: DayRef | None,
                           trace: dict, timings: dict[str, float]
                           ) -> tuple[dict, list, GateDecision]:
        """Returns the merged draft, the evidence and the gate decision as it now stands."""
        with timed(timings, "schedule_text_s"):
            item_missing = ""
            if draft and draft.get("status") != "ANSWER":   # the schedule stands without it
                item_missing, draft, evidence = draft.get("missing", ""), None, []
                gate = replace(gate, item="abstain", reasons=[
                    *gate.reasons, "item answer did not pass; schedule answered alone"])
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
        return draft, evidence, gate


def fixed_answer(gate: GateDecision, lang: str | None) -> dict:
    key = "SCHEDULE_VARIES" if gate.schedule_varies else gate.status
    return {"status": gate.status, "bin": "", "bin_en": "", "how_to_prepare": [],
            "answer_text": message(key, lang), "citations": [],
            "missing": "; ".join(gate.reasons)}


def day_asked(question: str, routed: str | None) -> str | None:
    """One weekday named in the question beats the router, which read 화요일 as Wednesday."""
    named = days_mentioned(question)
    return DAY_EN[next(iter(named))].lower() if len(named) == 1 else routed


BIN_CONFLICT_NOTE = (
    "Your previous answer gave the bin {bin} but its text named only {named}. Name the bin "
    "for the item itself in the text too; if the source puts a part of the item in another "
    "bin, name both and say which part goes where.")
REJECTED_NOTE = (
    "Your previous answer was rejected: {reasons}. Answer again from the same evidence. "
    "Each bin must be the 구분 category of the evidence you cite for it.")


def item_only_question(question: str, route: Route) -> str:
    """What the generator is asked when the schedule part is not its job. Asked the whole
    question with no schedule to read, it copied the days of its few-shot example.
    Not for an item question that also asks when (router.ASKS_WHEN): the router used to send
    it as an item question, and this wording lost its bin ("…pizza box? Answer only about the
    item…" -> a second bin in the text -> downgraded), so it keeps the question it had then.
    Any day it states is still checked against the rows (none), so none can be invented."""
    rule = "Answer only about the item. Do not mention days or times."
    return f"How do I throw away {route.item}? {rule}" if route.item else f"{question}\n({rule})"


def schedule_days(rows: list[ScheduleRow], waste_type: str | None) -> set[int]:
    return {d for r in rows for t in waste_types(waste_type) for d in r.rules[t].days}
