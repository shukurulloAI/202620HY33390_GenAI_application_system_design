"""
Developer probe set: a small, fixed set of questions re-run after every pipeline change
to catch regressions quickly (Lesson 1: freeze cases, change one variable).

This is NOT the evaluation test set (that is Anar's eval/, with dev/test splits and
proper metrics). Checks here are simple keyword rules and still need a human look.

Usage:
    python -m experiments.run_probes                      # default model
    python -m experiments.run_probes --model qwen2.5:7b
Results: experiments/results/probes_<model>_<prompt>_<timestamp>.json
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path

from rag import config
from rag.llm_client import make_client
from rag.pipeline import Pipeline

PROBES = Path(__file__).with_name("probes.jsonl")
RESULTS = Path(__file__).with_name("results")


def check(probe: dict, answer: dict) -> dict:
    text = " ".join([answer.get("bin", ""), answer.get("answer_text", "")]).lower()
    status_ok = answer.get("status") == probe["expect_status"]
    expect_ok = (not probe["expect_any"]
                 or any(k.lower() in text for k in probe["expect_any"]))
    forbidden = [k for k in probe["forbid"] if k.lower() in text]
    return {"status_ok": status_ok, "expect_ok": expect_ok, "forbidden_found": forbidden,
            "pass": status_ok and expect_ok and not forbidden}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--model", default=config.LLM_MODEL)
    parser.add_argument("--prompt", default="v1")
    parser.add_argument("--embedding", default=config.DEFAULT_EMBEDDING)
    args = parser.parse_args()

    probes = [json.loads(l) for l in PROBES.read_text(encoding="utf-8").splitlines() if l]
    pipeline = Pipeline(args.embedding, make_client("ollama", args.model), args.prompt,
                        write_traces=False)
    rows = []
    for probe in probes:
        trace = pipeline.run(probe["question"], probe.get("lang"), probe.get("district"),
                             probe.get("province"), probe.get("dong"),
                             probe.get("waste_type"))
        result = check(probe, trace["answer"])
        rows.append({"probe_id": probe["probe_id"], "question": probe["question"],
                     **result, "answer": trace["answer"]["answer_text"],
                     "bin": trace["answer"]["bin"], "status": trace["answer"]["status"],
                     "evidence": [e["ref"] for e in trace["evidence"]],
                     "checks": trace["checks"], "timings": trace["timings"]})
        mark = "PASS" if result["pass"] else "FAIL"
        print(f"{mark} {probe['probe_id']} {probe['question'][:45]:45s} | "
              f"{trace['answer']['status']:20s} | {trace['answer']['answer_text'][:90]}")

    passed = sum(r["pass"] for r in rows)
    summary = {"model": args.model, "prompt": args.prompt, "settings": pipeline.settings(),
               "passed": passed, "total": len(rows), "rows": rows}
    RESULTS.mkdir(exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    out = RESULTS / f"probes_{args.model.replace(':', '-')}_{args.prompt}_{stamp}.json"
    out.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n{passed}/{len(rows)} probes passed -> {out.relative_to(config.ROOT)}")


if __name__ == "__main__":
    main()
