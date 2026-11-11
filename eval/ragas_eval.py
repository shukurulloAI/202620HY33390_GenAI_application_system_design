"""
LLM-judge scores with Ragas (PLAN.md §7.4): faithfulness and context relevance of answered
cases, with a pinned local judge.

Ragas lives in its own environment (.venv-judge), because its LangChain dependencies would
change packages the pipeline relies on. Two steps:

    python -m eval.ragas_eval prepare <report name>           # main .venv: build judge input
    .venv-judge/bin/python -m eval.ragas_eval score <report name>   # judge env: Ragas

    setup once:  python3.12 -m venv .venv-judge
                 .venv-judge/bin/pip install -r requirements-judge.txt

Inputs per answered case: the question, answer_text, and the full text of every piece of
evidence the answer was built from (item chunks the generator read, district rows written
into the answer). Writes eval/reports/<name>/ragas.json (scores per case + means).

Judge: exaone3.5:7.8b in Ollama (LG AI Research), pinned by its digest, recorded in the
output. It is a different model family from the generator (qwen2.5:7b), so the system does
not grade its own answers; it is still a 7.8B model, which is why the human audit
(eval/audit.py) checks it. Faithfulness = supported statements / all statements (Ragas
definition); context relevance = Ragas' dual-judge 0-1 rating of the evidence.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import math
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPORTS = ROOT / "eval" / "reports"
JUDGE_MODEL = "exaone3.5:7.8b"
OLLAMA = "http://localhost:11434"


# ---------------------------------------------------------------------------- prepare (main env)

def prepare(name: str, cases_file: Path | None) -> Path:
    from eval.cases import by_id, load_cases
    from rag import paths
    from rag.files import read_jsonl
    report = json.loads((REPORTS / name / "report.json").read_text(encoding="utf-8"))
    traces = read_jsonl(ROOT / report["meta"]["traces_file"])
    cases = by_id(load_cases(cases_file or ROOT / report["meta"]["cases_file"]))
    chunks = {c["id"]: c["text"] for c in read_jsonl(paths.ITEM_CHUNKS)}
    out = REPORTS / name / "judge_input.jsonl"
    n = 0
    with out.open("w", encoding="utf-8") as f:
        for trace in traces:
            answer = trace.get("answer") or {}
            if answer.get("status") != "ANSWER":
                continue
            rows = {c["ref"]: c["text"] for c in answer.get("citations", [])
                    if c["kind"] == "schedule"}
            contexts = [chunks[e["ref"]] if e["kind"] == "item" else rows.get(e["ref"], "")
                        for e in trace.get("evidence", [])]
            contexts = [c for c in contexts if c]
            if not contexts:
                continue
            case = cases.get(trace["case_id"], {})
            f.write(json.dumps({"case_id": trace["case_id"], "slice": case.get("slice"),
                                "lang": case.get("lang"), "question": case.get("question"),
                                "response": answer["answer_text"], "contexts": contexts,
                                "reference_facts": case.get("reference_facts", [])},
                               ensure_ascii=False) + "\n")
            n += 1
    print(f"{n} answered cases -> {out.relative_to(ROOT)}")
    return out


# ---------------------------------------------------------------------------- score (judge env)

async def _score_all(rows: list[dict], model: str) -> list[dict]:
    from openai import AsyncOpenAI
    from ragas.llms import llm_factory
    from ragas.metrics.collections import ContextRelevance, Faithfulness
    client = AsyncOpenAI(base_url=f"{OLLAMA}/v1", api_key="ollama")
    llm = llm_factory(model, client=client, temperature=0.0, max_tokens=2048)
    faithfulness, relevance = Faithfulness(llm=llm), ContextRelevance(llm=llm)
    out = []
    for i, row in enumerate(rows, 1):
        record = {"case_id": row["case_id"], "slice": row["slice"], "lang": row["lang"]}
        for name, call in (
                ("faithfulness", lambda r=row: faithfulness.ascore(
                    user_input=r["question"], response=r["response"],
                    retrieved_contexts=r["contexts"])),
                ("context_relevance", lambda r=row: relevance.ascore(
                    user_input=r["question"], retrieved_contexts=r["contexts"]))):
            try:
                value = (await call()).value
                record[name] = None if value is None or math.isnan(value) else round(value, 3)
            except Exception as exc:            # one bad judge reply must not stop the run
                record[name], record[f"{name}_error"] = None, repr(exc)[:300]
        out.append(record)
        print(f"\r{i}/{len(rows)} {row['case_id']:8} faith={record['faithfulness']} "
              f"ctx={record['context_relevance']}   ", end="", flush=True)
    print()
    return out


def _mean(values: list) -> dict:
    defined = [v for v in values if v is not None]
    return {"mean": round(sum(defined) / len(defined), 3) if defined else None,
            "n": len(defined), "failed": len(values) - len(defined)}


def score(name: str, model: str, limit: int | None = None, out_name: str = "ragas.json") -> None:
    import ragas

    from rag.llm_client import ollama_digest  # stdlib only, so it runs in the judge env
    rows = [json.loads(line) for line in
            (REPORTS / name / "judge_input.jsonl").read_text(encoding="utf-8").splitlines()]
    rows = rows[:limit] if limit else rows
    scored = asyncio.run(_score_all(rows, model))
    by_slice = {}
    for slice_name in sorted({r["slice"] for r in scored if r["slice"]}):
        group = [r for r in scored if r["slice"] == slice_name]
        by_slice[slice_name] = {m: _mean([r[m] for r in group])
                                for m in ("faithfulness", "context_relevance")}
    result = {"report": name, "judge": {"model": model, "digest": ollama_digest(model, OLLAMA),
                                        "ragas": ragas.__version__, "temperature": 0.0},
              "time": datetime.now().isoformat(timespec="seconds"),
              "overall": {m: _mean([r[m] for r in scored])
                          for m in ("faithfulness", "context_relevance")},
              "by_slice": by_slice, "rows": scored}
    path = REPORTS / name / out_name
    path.write_text(json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(result["overall"]), "->", path.relative_to(ROOT))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("step", choices=["prepare", "score"])
    parser.add_argument("name", help="report folder under eval/reports/")
    parser.add_argument("--cases", type=Path)
    parser.add_argument("--judge", default=JUDGE_MODEL)
    parser.add_argument("--limit", type=int, help="score only the first N (smoke test)")
    args = parser.parse_args()
    if args.step == "prepare":
        prepare(args.name, args.cases)
    else:
        score(args.name, args.judge, args.limit,
              "ragas.json" if not args.limit else f"ragas_first{args.limit}.json")


if __name__ == "__main__":
    main()
