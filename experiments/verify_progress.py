"""
Check that the website's progress callback (Pipeline.answer(..., progress=...)) changes no
answer: every dev case runs with a callback set and is compared with the saved traces of
eval/reports/dev-v2.1 (the same system, run without one).

    python -m experiments.verify_progress        # dev split; LLM replies from .cache/llm when
                                                 # recorded, otherwise from Ollama (temperature 0)

Compares status, bin, bin_en, preparation steps, answer text and cited sources, and records
the stages each case reported. Writes experiments/results/dev/perf/progress_callback.json.
A replay with any difference exits with status 1.
"""
from __future__ import annotations

import json
import sys
from collections import Counter
from datetime import datetime

from eval.cases import load_cases
from eval.provenance import snapshot
from rag import config, paths
from rag.files import read_jsonl, sha256_file

REFERENCE = paths.ROOT / "eval" / "reports" / "dev-v2.1" / "traces.jsonl"
OUT = paths.RESULTS_DIR / "dev" / "perf" / "progress_callback.json"
FIELDS = ("status", "bin", "bin_en", "how_to_prepare", "answer_text")


def visible(answer: dict) -> dict:
    """What a user sees, minus the per-request trace_id."""
    return {**{k: answer.get(k) for k in FIELDS},
            "citations": [(c["kind"], c["ref"]) for c in answer.get("citations") or []]}


def main() -> None:
    from rag.llm_client import CachedClient, make_client
    from rag.pipeline import Pipeline
    provenance = snapshot()
    reference = {t["case_id"]: t for t in read_jsonl(REFERENCE)}
    llm = CachedClient(make_client("ollama", config.DEFAULT.llm_model))
    pipeline = Pipeline(config.DEFAULT, llm, write_traces=False)
    differ, sequences, n = [], Counter(), 0
    for case in load_cases(paths.DEV_CASES):
        stages: list[str] = []
        location = case.get("location") or {}
        trace = pipeline.run(case["question"], case.get("lang"), location.get("district"),
                             location.get("province"), location.get("dong"),
                             case.get("waste_type"), progress=stages.append)
        n += 1
        sequences[" > ".join(stages)] += 1
        if visible(trace["answer"]) != visible(reference[case["case_id"]]["answer"]):
            differ.append(case["case_id"])
        print(f"\r{n} {case['case_id']:8} differ={len(differ)}", end="", flush=True)
    print()
    record = {"question": "Does the progress callback change any answer?",
              "cases": paths.relative(paths.DEV_CASES),
              "cases_sha256": sha256_file(paths.DEV_CASES), "reference": paths.relative(REFERENCE),
              "compared": [*FIELDS, "citations"], "n": n, "identical": n - len(differ),
              "differ": differ, "stage_sequences": dict(sequences.most_common()),
              "llm_replayed": llm.cached, **provenance,
              "time": datetime.now().isoformat(timespec="seconds")}
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(record, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(json.dumps({k: record[k] for k in ("n", "identical", "differ", "llm_replayed")}),
          f"-> {paths.relative(OUT)}")
    sys.exit(1 if differ else 0)


if __name__ == "__main__":
    main()
