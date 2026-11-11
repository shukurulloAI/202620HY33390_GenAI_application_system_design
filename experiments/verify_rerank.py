"""
Check that the batched reranker (one model call over all distinct query-chunk pairs) gives
exactly the candidates the frozen system gave, and measure the time saved.

    python -m experiments.verify_rerank                  # dev split, router replies from cache

For every dev case that reaches the reranker, retrieval runs twice in one process, with the
current Reranker.rerank and with the per-query version of the frozen configuration (f0faba6).
Both are compared with the saved traces of eval/reports/dev-s3e-final (same configuration):
candidate order and rerank scores. Writes experiments/results/dev/perf/rerank_batching.json.
A replay with any difference exits with status 1.
"""
from __future__ import annotations

import json
import math
import statistics
import sys
from datetime import datetime

from eval.cases import load_cases
from eval.provenance import snapshot
from rag import config, paths, retrieve
from rag.files import read_jsonl, sha256_file

REFERENCE = paths.ROOT / "eval" / "reports" / "dev-s3e-final" / "traces.jsonl"
OUT = paths.RESULTS_DIR / "dev" / "perf" / "rerank_batching.json"


def per_query_rerank(self, queries, candidates):
    """Reranker.rerank as frozen at f0faba6: one model call per query."""
    if not candidates:
        return []

    def score(query):
        raw = self.model.predict([(query, c.text) for c in candidates], batch_size=16,
                                 show_progress_bar=False)
        s = [float(x) for x in raw]
        return [1 / (1 + math.exp(-x)) for x in s] if any(x < 0 or x > 1 for x in s) else s

    per_query = [score(q) for q in queries if q]
    scores = [max(col) for col in zip(*per_query, strict=True)]
    order = sorted(range(len(candidates)), key=lambda i: -scores[i])
    return [retrieve._copy(candidates[i], rank=r, rerank_score=round(scores[i], 4),
                           ranks={**candidates[i].ranks, "fused": candidates[i].rank})
            for r, i in enumerate(order, 1)]


def compare(trace: dict, reference: dict) -> tuple[bool, float]:
    ids = [c["chunk_id"] for c in trace["candidates"]]
    ref = {c["chunk_id"]: c["rerank_score"] for c in reference["candidates"]}
    same_order = ids == [c["chunk_id"] for c in reference["candidates"]]
    diff = max((abs(c["rerank_score"] - ref.get(c["chunk_id"], math.inf))
                for c in trace["candidates"]), default=0.0)
    return same_order, diff


def main() -> None:
    from rag.llm_client import CachedClient, make_client
    from rag.pipeline import Pipeline
    provenance = snapshot()
    reference = {t["case_id"]: t for t in read_jsonl(REFERENCE)}
    llm = CachedClient(make_client("ollama", config.DEFAULT.llm_model))
    pipeline = Pipeline(config.DEFAULT, llm, write_traces=False)
    batched = retrieve.Reranker.rerank
    versions = {"batched": batched, "per_query": per_query_rerank}
    result = {v: {"same_order": 0, "max_score_diff": 0.0, "rerank_s": []} for v in versions}
    differ, n = [], 0
    for case in load_cases(paths.DEV_CASES):
        ref = reference[case["case_id"]]
        if not ref.get("candidates"):
            continue
        n += 1
        for name, function in versions.items():
            retrieve.Reranker.rerank = function
            trace = pipeline.run_case(case, stop_after_retrieval=True)
            same, diff = compare(trace, ref)
            r = result[name]
            r["same_order"] += same
            r["max_score_diff"] = max(r["max_score_diff"], diff)
            r["rerank_s"].append(trace["timings"].get("rerank_s", 0.0))
            if name == "batched" and (not same or diff > 1e-4):
                differ.append(case["case_id"])
        print(f"\r{n} {case['case_id']:8} differ={len(differ)}", end="", flush=True)
    print()
    retrieve.Reranker.rerank = batched
    for r in result.values():
        times = r.pop("rerank_s")
        r["rerank_s"] = {"median": round(statistics.median(times), 3),
                         "mean": round(statistics.mean(times), 3)}
    record = {"question": "Does the batched reranker reproduce the frozen system's candidates?",
              "cases": paths.relative(paths.DEV_CASES),
              "cases_sha256": sha256_file(paths.DEV_CASES), "reference": paths.relative(REFERENCE),
              "cases_reranked": n, "differ": differ, "versions": result,
              "llm_replayed": llm.cached, **provenance,
              "time": datetime.now().isoformat(timespec="seconds")}
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(record, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(json.dumps(record["versions"], indent=1), f"-> {paths.relative(OUT)}")
    sys.exit(1 if differ else 0)


if __name__ == "__main__":
    main()
