"""
End-to-end pipeline (PLAN.md §4). Phase 1 baseline:

    question -> dense retrieval (top K_RETRIEVE) -> keep K_FINAL
             -> schedule tool (if a district is given)
             -> context under token budget -> LLM (JSON) -> parse + citation check
             -> answer dict + JSON trace

Not in the baseline yet (Phase 2, one at a time): router/rewriter, BM25 + fusion,
reranker, evidence gate, conflict policy, output validation against allowed bins.

Interfaces for teammates:
    Pipeline().answer(question, lang, district, dong)  -> answer dict   (website, Naura)
    Pipeline().run_case(case)                          -> full trace    (evaluation, Anar)

CLI:
    python -m rag.pipeline "Where do I throw away a pizza box?"
    python -m rag.pipeline "When can I put out food waste?" --district 성동구 --dong 행당동
    python -m rag.pipeline "..." --llm fixture        # offline contract test, no Ollama
"""
from __future__ import annotations

import argparse
import json
import time
import uuid
from datetime import datetime, timezone

from rag import config
from rag.context import ContextBudget, default_counter, pack_evidence
from rag.generate import ANSWER_SCHEMA, build_prompt, parse_answer
from rag.llm_client import LLMClient, make_client
from rag.retrieve import DenseRetriever
from rag.schedule_tool import WASTE_TYPES, default_table, put_out_days

PIPELINE_VERSION = "baseline-v1"


class Pipeline:
    def __init__(self, embedding_key: str = config.DEFAULT_EMBEDDING,
                 llm: LLMClient | None = None, prompt_version: str = "v1",
                 k_retrieve: int = config.K_RETRIEVE, k_final: int = config.K_FINAL,
                 write_traces: bool = True):
        self.retriever = DenseRetriever(embedding_key)
        self.schedule = default_table()
        self.llm = llm or make_client("ollama")
        self.prompt_version = prompt_version
        self.k_retrieve, self.k_final = k_retrieve, k_final
        self.counter = default_counter(
            config.LLM_TOKENIZERS.get(self.llm.model_id, config.LLM_TOKENIZER))
        self.budget = ContextBudget()
        self.write_traces = write_traces

    def settings(self) -> dict:
        return {"pipeline_version": PIPELINE_VERSION,
                "retriever": self.retriever.name, "collection": self.retriever.collection,
                "llm": self.llm.model_id, "prompt_version": self.prompt_version,
                "k_retrieve": self.k_retrieve, "k_final": self.k_final,
                "temperature": config.TEMPERATURE, "seed": config.SEED,
                "schedule_source": self.schedule.source}

    # ------------------------------------------------------------------ main entry
    def run(self, question: str, lang: str | None = None, district: str | None = None,
            province: str | None = None, dong: str | None = None,
            waste_type: str | None = None) -> dict:
        """Full trace for one request (everything needed to explain the answer)."""
        timings = {}
        trace = {"trace_id": str(uuid.uuid4()),
                 "time": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                 "settings": self.settings(),
                 "input": {"question": question, "lang": lang, "district": district,
                           "province": province, "dong": dong, "waste_type": waste_type}}

        t = time.perf_counter()
        candidates = self.retriever.search(question, self.k_retrieve)
        timings["retrieve_s"] = round(time.perf_counter() - t, 3)
        selected = candidates[:self.k_final]
        trace["candidates"] = [c.to_trace() for c in candidates]

        t = time.perf_counter()
        schedule = None
        if district:
            schedule = self.schedule.lookup(district, province, dong, waste_type)
            trace["schedule"] = schedule.to_trace()
        timings["schedule_s"] = round(time.perf_counter() - t, 3)
        schedule_rows = schedule.rows[:4] if schedule and schedule.status == "OK" else []

        system, empty_prompt = build_prompt(self.prompt_version, question, "", lang)
        evidence, evidence_text, budget = pack_evidence(
            selected, schedule_rows, waste_type, system + "\n" + empty_prompt,
            self.counter, self.budget)
        trace["evidence"] = [e.to_citation() for e in evidence]
        trace["budget"] = budget
        system, prompt = build_prompt(self.prompt_version, question, evidence_text, lang)

        t = time.perf_counter()
        result = self.llm.generate(system=system, prompt=prompt, json_schema=ANSWER_SCHEMA)
        timings["generate_s"] = round(time.perf_counter() - t, 3)
        answer, checks = parse_answer(result.text, len(evidence))
        checks["output_truncated"] = result.done_reason == "length"
        trace["llm"] = {"model_id": result.model_id, "raw_output": result.text,
                        "prompt_tokens_measured": result.prompt_tokens,
                        "completion_tokens": result.completion_tokens,
                        "done_reason": result.done_reason}
        trace["checks"] = checks
        trace["timings"] = timings
        trace["answer"] = self._final_answer(answer, evidence, schedule, schedule_rows,
                                             waste_type, trace["trace_id"])
        if self.write_traces:
            write_trace(trace)
        return trace

    def answer(self, question: str, lang: str | None = None, district: str | None = None,
               dong: str | None = None, province: str | None = None,
               waste_type: str | None = None) -> dict:
        """Website interface (PLAN.md §4.12): returns only the answer dict."""
        return self.run(question, lang, district, province, dong, waste_type)["answer"]

    def run_case(self, case: dict) -> dict:
        """Evaluation interface (PLAN.md §7.1): case -> full trace (+ case_id)."""
        location = case.get("location") or {}
        trace = self.run(case["question"], case.get("lang"), location.get("district"),
                         location.get("province"), location.get("dong"),
                         case.get("waste_type"))
        trace["case_id"] = case.get("case_id")
        return trace

    # ------------------------------------------------------------------ helpers
    @staticmethod
    def _final_answer(answer, evidence, schedule, schedule_rows, waste_type, trace_id):
        by_n = {e.n: e for e in evidence}
        citations = [by_n[n].to_citation() for n in answer.get("citations", []) if n in by_n]
        final = {
            "status": answer.get("status"),
            "bin": answer.get("bin", ""),
            "bin_en": answer.get("bin_en", ""),
            "how_to_prepare": answer.get("how_to_prepare", []),
            "answer_text": answer.get("answer_text", ""),
            "citations": citations,
            "missing": answer.get("missing", ""),
            "schedule": None,
            "trace_id": trace_id,
        }
        if schedule is not None:
            # Days, times, phone and date come from the tool, never from the LLM.
            types = [waste_type] if waste_type in WASTE_TYPES else list(WASTE_TYPES)
            final["schedule"] = {
                "status": schedule.status,
                "message": schedule.message,
                "options": schedule.options,
                "zones": [{
                    "province": r.province, "district": r.district, "zone": r.zone,
                    "areas": r.area_names, "place": f"{r.place_type} / {r.place}",
                    "by_type": {t: {"days": r.rules[t].days_en(),
                                    "start": r.rules[t].start, "end": r.rules[t].end,
                                    "next_dates": put_out_days(r, t)}
                                for t in types if r.rules[t].days},
                    "no_collection": r.no_collection_days,
                    "office": r.office, "phone": r.phone,
                    "data_date": r.data_date, "stale": r.is_stale(),
                    "row_id": r.row_id,
                } for r in schedule_rows],
            }
        return final


def write_trace(trace: dict) -> None:
    config.TRACE_DIR.mkdir(parents=True, exist_ok=True)
    path = config.TRACE_DIR / f"{trace['time'][:10]}.jsonl"
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(trace, ensure_ascii=False) + "\n")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("question")
    parser.add_argument("--lang", help="answer language code (en, ko, zh, uz, vi, ...)")
    parser.add_argument("--district")
    parser.add_argument("--province")
    parser.add_argument("--dong")
    parser.add_argument("--waste-type", choices=sorted(WASTE_TYPES))
    parser.add_argument("--embedding", default=config.DEFAULT_EMBEDDING,
                        choices=sorted(config.EMBEDDING_MODELS))
    parser.add_argument("--llm", default="ollama", choices=["ollama", "fixture"])
    parser.add_argument("--model", help=f"Ollama model (default {config.LLM_MODEL})")
    parser.add_argument("--prompt", default="v1", help="prompt version")
    parser.add_argument("--show-trace", action="store_true")
    args = parser.parse_args()

    pipeline = Pipeline(args.embedding, make_client(args.llm, args.model), args.prompt)
    trace = pipeline.run(args.question, args.lang, args.district, args.province,
                         args.dong, args.waste_type)
    print(json.dumps(trace if args.show_trace else trace["answer"],
                     ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
