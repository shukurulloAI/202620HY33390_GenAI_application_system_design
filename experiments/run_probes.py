"""
Developer probe set: a small, fixed set of questions re-run after every pipeline change
to catch regressions quickly (Lesson 1: freeze cases, change one variable).

This is NOT the evaluation test set (that is Anar's eval/, with dev/test splits and
proper metrics). Checks here are simple keyword rules and still need a human look.

Usage:
    python -m experiments.run_probes                         # default (full) system
    python -m experiments.run_probes --baseline              # Phase 1 system
    python -m experiments.run_probes --set rerank=false      # one change
    python -m experiments.run_probes --retrieval-only        # router + retrieval, no generation
Results: experiments/results/probes_<label>_<timestamp>.json
"""
from __future__ import annotations

import argparse
import json
import statistics
from datetime import datetime
from pathlib import Path

from rag import config
from rag.llm_client import make_client
from rag.pipeline import Pipeline, config_from_args
from experiments.run_experiment import git_commit, git_dirty

PROBES = Path(__file__).with_name("probes.jsonl")
RESULTS = Path(__file__).with_name("results")


def check(probe: dict, answer: dict) -> dict:
    text = " ".join([answer.get("bin", ""), answer.get("answer_text", "")]).lower()
    expected = probe["expect_status"]
    expected = [expected] if isinstance(expected, str) else expected
    status_ok = answer.get("status") in expected
    expect_ok = (not probe["expect_any"]
                 or any(k.lower() in text for k in probe["expect_any"]))
    forbidden = [k for k in probe["forbid"] if k.lower() in text]
    return {"status_ok": status_ok, "expect_ok": expect_ok, "forbidden_found": forbidden,
            "pass": status_ok and expect_ok and not forbidden}


def gold_rank(probe: dict, trace: dict) -> int | None:
    """1-based rank of the first gold chunk in the final candidate order (None = not found
    in R; probes without gold chunks are skipped)."""
    gold = set(probe["gold_chunks"])
    for c in trace.get("candidates", []):
        if c["chunk_id"] in gold or c["metadata"].get("legacy_id") in gold:
            return c["rank"]
    return None


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--baseline", action="store_true")
    parser.add_argument("--config")
    parser.add_argument("--set", action="append", default=[], metavar="FIELD=VALUE")
    parser.add_argument("--retrieval-only", action="store_true")
    parser.add_argument("--only", nargs="*", help="probe ids to run")
    parser.add_argument("--label", help="name for the result file")
    args = parser.parse_args()

    cfg = config_from_args("baseline" if args.baseline else args.config, args.set)
    probes = [json.loads(l) for l in PROBES.read_text(encoding="utf-8").splitlines() if l]
    if args.only:
        probes = [p for p in probes if p["probe_id"] in args.only]
    pipeline = Pipeline(cfg, make_client("ollama", cfg.llm_model), write_traces=False)
    rows = []
    for probe in probes:
        trace = pipeline.run_case(probe, stop_after_retrieval=args.retrieval_only)
        rank = gold_rank(probe, trace) if probe["gold_chunks"] else None
        row = {"probe_id": probe["probe_id"], "question": probe["question"],
               "intent": trace["resolved"]["intent"],
               "rewrite": trace["route"].get("ko_query"),
               "rewrite_used": "rewrite" in (trace.get("retrieval") or {}).get("queries", {}),
               "gold_rank": rank, "has_gold": bool(probe["gold_chunks"]),
               "top_rerank": next((c["rerank_score"] for c in trace["candidates"][:1]), None),
               "selected": trace["selected"], "timings": trace["timings"]}
        if not args.retrieval_only:
            answer = trace["answer"]
            row.update(check(probe, answer), status=answer["status"], bin=answer["bin"],
                       answer=answer["answer_text"], gate=trace.get("gate"),
                       checks=trace.get("checks"), handoff=answer.get("handoff"),
                       clarify=answer.get("clarify"))
        rows.append(row)
        hit = ("-" if not row["has_gold"] else
               f"gold@{rank}" if rank else "gold missing")
        if args.retrieval_only:
            print(f"{probe['probe_id']} {probe['question'][:50]:50s} | {row['intent']:12s} "
                  f"| {hit:12s} | top={row['top_rerank']} | {row['rewrite']}")
        else:
            mark = "PASS" if row["pass"] else "FAIL"
            print(f"{mark} {probe['probe_id']} {probe['question'][:40]:40s} | {hit:12s} | "
                  f"{answer['status']:20s} | {answer['bin']:8s} | {answer['answer_text'][:80]}")

    with_gold = [r for r in rows if r["has_gold"]]
    k = cfg.k_final
    summary = {
        "label": args.label, "config": cfg.to_dict(), "settings": pipeline.settings(),
        "git_commit": git_commit(), "git_dirty": git_dirty(),
        "retrieval_only": args.retrieval_only, "total": len(rows),
        "hit_at_k_final": sum(1 for r in with_gold if r["gold_rank"] and r["gold_rank"] <= k),
        "gold_probes": len(with_gold),
        "mrr": round(sum(1 / r["gold_rank"] for r in with_gold if r["gold_rank"])
                     / max(len(with_gold), 1), 3),
        "median_total_s": statistics.median(r["timings"]["total_s"] for r in rows),
    }
    if not args.retrieval_only:
        summary["passed"] = sum(r["pass"] for r in rows)
    summary["rows"] = rows
    RESULTS.mkdir(exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    label = args.label or ("baseline" if args.baseline else "default")
    out = RESULTS / f"probes_{label}{'_retrieval' if args.retrieval_only else ''}_{stamp}.json"
    out.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nhit@{k}: {summary['hit_at_k_final']}/{len(with_gold)}  MRR: {summary['mrr']}  "
          f"median latency: {summary['median_total_s']:.1f}s"
          + (f"  passed: {summary['passed']}/{len(rows)}" if not args.retrieval_only else "")
          + f"\n-> {out.relative_to(config.ROOT)}")


if __name__ == "__main__":
    main()
