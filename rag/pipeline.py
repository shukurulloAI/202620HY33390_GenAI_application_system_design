"""
End-to-end pipeline (PLAN.md §4). Every stage is set by one PipelineConfig
(rag/config.py), so an experiment changes one field (PLAN.md §6).

    question
      -> router: intent, item, Korean rewrite, location, waste type, day   (LLM call 1)
      -> item retrieval: dense / BM25 / hybrid RRF -> rerank -> top k_final
      -> schedule tool: typed lookup + date check (deterministic)
      -> gate: answer / abstain / clarify / out of scope, per part
           (nothing answerable -> fixed message + handoff, no LLM call)
      -> context under token budget -> generator (LLM call 2, JSON schema)
      -> parse + citation check -> validation (allowed bins, support)
      -> answer dict (+ handoff, notes) and one JSON trace per request

Interfaces for teammates:
    Pipeline().answer(question, lang, district, dong)  -> answer dict   (website, Naura)
    Pipeline().run_case(case)                          -> full trace    (evaluation, Anar)
    Pipeline(config.BASELINE)                          -> the Phase 1 system

CLI:
    python -m rag.pipeline "Where do I throw away a pizza box?"
    python -m rag.pipeline "Can I put food waste out tonight? I live in Seongdong-gu Haengdang-dong"
    python -m rag.pipeline "..." --baseline                  # Phase 1 configuration
    python -m rag.pipeline "..." --set retrieval=dense --set rerank=false
    python -m rag.pipeline "..." --llm fixture               # offline contract test
"""
from __future__ import annotations

import argparse
import json
import time
import uuid
from datetime import datetime, timezone

from rag import config
from rag.config import PipelineConfig
from rag.context import ContextBudget, default_counter, pack_evidence
from rag.gate import MAX_ZONES, GateDecision, decide
from rag.generate import ANSWER_SCHEMA, build_prompt, parse_answer
from rag.handoff import build_handoff, message
from rag.llm_client import LLMClient, make_client
from rag.retrieve import ItemRetriever
from rag.router import Route, Router
from rag.schedule_tool import (WASTE_TYPE_EN, WASTE_TYPES, day_checks, default_table, put_out_days,
                               resolve_day)
from rag.validate import validate

PIPELINE_VERSION = "v2"


class Pipeline:
    def __init__(self, cfg: PipelineConfig | None = None, llm: LLMClient | None = None,
                 write_traces: bool = True, router_llm: LLMClient | None = None):
        self.cfg = cfg or config.DEFAULT
        self.llm = llm or make_client("ollama", self.cfg.llm_model)
        self.retriever = ItemRetriever(self.cfg)
        self.schedule = default_table()
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
                "llm": self.llm.model_id, "schedule_source": self.schedule.source}

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

    # ------------------------------------------------------------------ main entry
    def run(self, question: str, lang: str | None = None, district: str | None = None,
            province: str | None = None, dong: str | None = None,
            waste_type: str | None = None, stop_after_retrieval: bool = False) -> dict:
        """Full trace for one request (everything needed to explain the answer)."""
        start = time.perf_counter()
        timings = {}
        trace = {"trace_id": str(uuid.uuid4()),
                 "time": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                 "settings": self.settings(),
                 "input": {"question": question, "lang": lang, "district": district,
                           "province": province, "dong": dong, "waste_type": waste_type}}

        t = time.perf_counter()
        route = self.route(question)
        timings["route_s"] = round(time.perf_counter() - t, 3)
        trace["route"] = route.to_trace()
        intent = route.intent if route.valid else "unknown"

        # explicit inputs (website dropdowns, eval case) win over what the router read
        lang = lang or route.lang
        eff_district = district or route.district or None
        same_district = not district or not route.district or route.district == district
        eff_dong = dong or (route.dong if same_district else "") or None
        eff_waste = waste_type or route.waste_type
        trace["resolved"] = {"intent": intent, "lang": lang, "district": eff_district,
                             "province": province, "dong": eff_dong, "waste_type": eff_waste,
                             "day_ref": route.day_ref,
                             "location_source": ("input" if district else
                                                 "router" if route.district else None)}

        candidates, selected = [], []
        if intent in ("item", "both", "unknown"):
            candidates, selected, record = self.retrieve(question, route)
            timings.update(record.pop("timings"))
            trace["retrieval"] = record
        trace["candidates"] = [c.to_trace() for c in candidates]
        trace["selected"] = [c.chunk_id for c in selected]
        if stop_after_retrieval:
            timings["total_s"] = round(time.perf_counter() - start, 3)
            trace["timings"] = timings
            return trace

        t = time.perf_counter()
        schedule, day = None, None
        needs_schedule = intent in ("schedule", "both") or (intent == "unknown" and eff_district)
        if needs_schedule and eff_district:
            schedule = self.schedule.lookup(eff_district, province, eff_dong, eff_waste)
            trace["schedule"] = schedule.to_trace()
            day = resolve_day(route.day_ref)
        timings["schedule_s"] = round(time.perf_counter() - t, 3)

        tau = self.cfg.gate_tau if self.cfg.rerank else None
        gate = decide(intent, selected, schedule, eff_district, eff_dong, tau, route.item_ko)
        trace["gate"] = gate.to_trace()

        item_evidence = selected if gate.item == "answer" else []
        schedule_rows = schedule.rows[:MAX_ZONES] if gate.schedule == "answer" else []

        if gate.status != "ANSWER":                      # nothing answerable: no LLM call
            trace["llm"], trace["checks"], trace["evidence"] = None, {}, []
            answer = {"status": gate.status, "bin": "", "bin_en": "", "how_to_prepare": [],
                      "answer_text": message(gate.status, lang), "citations": [],
                      "missing": "; ".join(gate.reasons)}
            evidence = []
        else:
            system, empty = build_prompt(self.cfg.prompt_version, question, "", lang,
                                         self.cfg.conflict_policy)
            evidence, evidence_text, budget = pack_evidence(
                item_evidence, schedule_rows, eff_waste, system + "\n" + empty,
                self.counter, self.budget, day)
            trace["evidence"] = [e.to_citation() for e in evidence]
            trace["budget"] = budget
            system, prompt = build_prompt(self.cfg.prompt_version, question, evidence_text,
                                          lang, self.cfg.conflict_policy)
            t = time.perf_counter()
            result = self.llm.generate(system=system, prompt=prompt, json_schema=ANSWER_SCHEMA,
                                       temperature=self.cfg.temperature, seed=self.cfg.seed)
            timings["generate_s"] = round(time.perf_counter() - t, 3)
            answer, checks = parse_answer(result.text, len(evidence))
            checks["output_truncated"] = result.done_reason == "length"
            trace["llm"] = {"model_id": result.model_id, "raw_output": result.text,
                            "prompt_tokens_measured": result.prompt_tokens,
                            "completion_tokens": result.completion_tokens,
                            "done_reason": result.done_reason}
            days = _schedule_days(schedule_rows, eff_waste) if schedule_rows else None
            answer, validation = validate(answer, evidence, days, self.cfg.validation,
                                          item_question=gate.item == "answer")
            if validation.get("downgraded"):
                answer["answer_text"] = message("INSUFFICIENT_CONTEXT", lang)
            trace["checks"] = {**checks, "validation": validation}

        timings["total_s"] = round(time.perf_counter() - start, 3)
        trace["timings"] = timings
        trace["answer"] = self._final_answer(answer, evidence, gate, route, schedule,
                                             schedule_rows, eff_waste, day, lang,
                                             eff_district, eff_dong, trace["trace_id"])
        if self.write_traces:
            write_trace(trace)
        return trace

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

    # ------------------------------------------------------------------ helpers
    def _final_answer(self, answer: dict, evidence: list, gate: GateDecision, route: Route,
                      schedule, schedule_rows, waste_type, day, lang, district, dong,
                      trace_id) -> dict:
        by_n = {e.n: e for e in evidence}
        cited = [by_n[n] for n in answer.get("citations", []) if n in by_n]
        final = {
            "status": answer.get("status"),
            "lang": lang,
            "bin": answer.get("bin", ""),
            "bin_en": answer.get("bin_en", ""),
            "how_to_prepare": answer.get("how_to_prepare", []),
            "answer_text": answer.get("answer_text", ""),
            "citations": [e.to_citation() for e in cited],
            "missing": answer.get("missing", ""),
            "schedule": None,
            "data_date": None,
            "office_phone": None,
            "clarify": gate.clarify,
            "notes": [],
            "handoff": None,
            "trace_id": trace_id,
        }
        years = {e.metadata.get("source_year") for e in cited if e.kind == "item"}
        if years == {2018}:
            final["notes"].append("Based on the 2018 national guideline; your district may "
                                  "have newer local rules.")
        if 2026 in years:
            final["notes"].append("Uses the 2026 national rule (분리수거 등에 관한 지침, "
                                  "effective 2026-01-01).")
        if schedule is not None:
            # Days, times, phone and dates come from the tool, never from the LLM.
            types = [waste_type] if waste_type in WASTE_TYPES else list(WASTE_TYPES)
            final["schedule"] = {
                "status": schedule.status, "message": schedule.message,
                "options": schedule.options,
                "zones": [{
                    "province": r.province, "district": r.district, "zone": r.zone,
                    "areas": r.area_names, "place": f"{r.place_type} / {r.place}",
                    "by_type": {t: {"days": r.rules[t].days_en(),
                                    "start": r.rules[t].start, "end": r.rules[t].end,
                                    "next_dates": put_out_days(r, t)}
                                for t in types if r.rules[t].days},
                    "day_check": day_checks(r, types, day) if day else [],
                    "no_collection": r.no_collection_days,
                    "office": r.office, "phone": r.phone,
                    "data_date": r.data_date, "stale": r.is_stale(),
                    "row_id": r.row_id,
                } for r in schedule_rows],
            }
            flat = schedule_fields(schedule_rows, types)
            final["data_date"] = flat.pop("data_date")
            final["office_phone"] = flat.pop("office_phone")
            final["schedule"].update(flat)
            if any(r.is_stale() for r in schedule_rows):
                final["notes"].append(f"The district data is dated {schedule_rows[0].data_date} "
                                      "(more than a year old). Please confirm with the office.")
            if schedule.message and schedule_rows:
                final["notes"].append(schedule.message)

        # handoff when we could not answer, or answered only part of the question
        if final["status"] == "INSUFFICIENT_CONTEXT" or (
                final["status"] == "ANSWER" and "abstain" in (gate.item, gate.schedule)):
            checked = []
            if gate.item != "skip":
                checked.append("national sorting guides (2018 guideline, 2026 rules)")
            if schedule is not None:
                checked.append(f"district collection data for {district}"
                               + (f" {dong}" if dong else ""))
            final["handoff"] = build_handoff(
                item_ko=route.item_ko if route.checks.get("item_ko_korean") else "",
                waste_type=waste_type, district=district, dong=dong, schedule=schedule,
                asks_schedule=gate.schedule != "skip", checked=checked)
        return final


def schedule_fields(rows, types: list[str]) -> dict:
    """The flat fields of the answer contract (PLAN.md §4.8), from the tool's rows. With
    several zones or waste types each value gets a label, so none of them is dropped;
    `zones` in the answer keeps the full detail. Oldest date: it decides how far to trust."""
    days, times = [], []
    for row in rows:
        for t in types:
            rule = row.rules[t]
            if not rule.days:
                continue
            label = " ".join(x for x in (row.zone if len(rows) > 1 else "",
                                         WASTE_TYPE_EN[t] if len(types) > 1 else "") if x)
            prefix = f"{label}: " if label else ""
            days.append(prefix + rule.days_en())
            if rule.start and rule.end:
                times.append(f"{prefix}{rule.start}-{rule.end}")
    join = lambda values: "; ".join(dict.fromkeys(v for v in values if v)) or None
    return {"days": join(days), "time": join(times),
            "place": join(f"{r.place_type} / {r.place}" for r in rows),
            "data_date": min((r.data_date for r in rows if r.data_date), default=None),
            "office_phone": join(r.phone for r in rows)}


def _schedule_days(rows, waste_type) -> set[int]:
    types = [waste_type] if waste_type in WASTE_TYPES else list(WASTE_TYPES)
    return {d for r in rows for t in types for d in r.rules[t].days}


def write_trace(trace: dict) -> None:
    config.TRACE_DIR.mkdir(parents=True, exist_ok=True)
    path = config.TRACE_DIR / f"{trace['time'][:10]}.jsonl"
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(trace, ensure_ascii=False) + "\n")


def parse_overrides(pairs: list[str]) -> dict:
    """['retrieval=dense', 'rerank=false', 'gate_tau=0.2'] -> typed dict."""
    out = {}
    for pair in pairs or []:
        key, _, raw = pair.partition("=")
        try:
            out[key.strip()] = json.loads(raw)
        except json.JSONDecodeError:
            out[key.strip()] = raw
    return out


def config_from_args(base: str | None, sets: list[str]) -> PipelineConfig:
    if base == "baseline":
        cfg = config.BASELINE
    elif base:
        cfg = PipelineConfig.from_dict(json.loads(open(base, encoding="utf-8").read()))
    else:
        cfg = config.DEFAULT
    return cfg.replace(**parse_overrides(sets)) if sets else cfg


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("question")
    parser.add_argument("--lang", help="answer language code (en, ko, zh, uz, vi, ...)")
    parser.add_argument("--district")
    parser.add_argument("--province")
    parser.add_argument("--dong")
    parser.add_argument("--waste-type", choices=sorted(WASTE_TYPES))
    parser.add_argument("--baseline", action="store_true", help="Phase 1 configuration")
    parser.add_argument("--config", help="JSON file with PipelineConfig fields")
    parser.add_argument("--set", action="append", default=[], metavar="FIELD=VALUE",
                        help="override one config field, e.g. --set retrieval=dense")
    parser.add_argument("--llm", default="ollama", choices=["ollama", "fixture"])
    parser.add_argument("--show-trace", action="store_true")
    args = parser.parse_args()

    cfg = config_from_args("baseline" if args.baseline else args.config, args.set)
    llm = make_client(args.llm, cfg.llm_model)
    pipeline = Pipeline(cfg, llm)
    trace = pipeline.run(args.question, args.lang, args.district, args.province,
                         args.dong, args.waste_type)
    print(json.dumps(trace if args.show_trace else trace["answer"],
                     ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
