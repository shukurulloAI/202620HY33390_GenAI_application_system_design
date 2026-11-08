"""
Developer probe set: a small, fixed set of questions re-run after every pipeline change
to catch regressions quickly (Lesson 1: freeze cases, change one variable).

This is NOT the evaluation test set (that is eval/, with dev/test splits and proper
metrics). Checks here are simple keyword rules and still need a human look.

Usage:
    python -m experiments.run_probes                         # default (full) system
    python -m experiments.run_probes --baseline              # Phase 1 system
    python -m experiments.run_probes --set rerank=false      # one change
    python -m experiments.run_probes --retrieval-only        # router + retrieval, no generation
Results: experiments/results/probes/probes_<label>_<timestamp>.json
"""
from __future__ import annotations

import argparse
import json
import statistics
from datetime import datetime

from eval.cases import load_cases
from eval.metrics import gold_rank
from eval.provenance import git_commit, git_dirty
from rag import paths
from rag.config import load_config
from rag.llm_client import make_client
from rag.pipeline import Pipeline


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


def run_probe(pipeline: Pipeline, probe: dict, retrieval_only: bool) -> dict:
    trace = pipeline.run_case(probe, stop_after_retrieval=retrieval_only)
    gold = probe["gold_chunks"]
    row = {"probe_id": probe["probe_id"], "question": probe["question"],
           "intent": trace["resolved"]["intent"],
           "rewrite": trace["route"].get("ko_query"),
           "rewrite_used": "rewrite" in (trace.get("retrieval") or {}).get("queries", {}),
           "gold_rank": gold_rank(gold, trace) if gold else None, "has_gold": bool(gold),
           "top_rerank": next((c["rerank_score"] for c in trace["candidates"][:1]), None),
           "selected": trace["selected"], "timings": trace["timings"]}
    if not retrieval_only:
        answer = trace["answer"]
        row.update(check(probe, answer), status=answer["status"], bin=answer["bin"],
                   answer=answer["answer_text"], gate=trace.get("gate"),
                   checks=trace.get("checks"), handoff=answer.get("handoff"),
                   clarify=answer.get("clarify"))
    return row


def print_row(row: dict, retrieval_only: bool) -> None:
    rank = row["gold_rank"]
    hit = "-" if not row["has_gold"] else f"gold@{rank}" if rank else "gold missing"
    question = row["question"]
    if retrieval_only:
        print(f"{row['probe_id']} {question[:50]:50s} | {row['intent']:12s} "
              f"| {hit:12s} | top={row['top_rerank']} | {row['rewrite']}")
    else:
        mark = "PASS" if row["pass"] else "FAIL"
        print(f"{mark} {row['probe_id']} {question[:40]:40s} | {hit:12s} | "
              f"{row['status']:20s} | {row['bin']:8s} | {row['answer'][:80]}")


def summarize(rows: list[dict], label: str | None, cfg, pipeline: Pipeline,
              retrieval_only: bool) -> dict:
    with_gold = [r for r in rows if r["has_gold"]]
    summary = {
        "label": label, "config": cfg.to_dict(), "settings": pipeline.settings(),
        "git_commit": git_commit(), "git_dirty": git_dirty(),
        "retrieval_only": retrieval_only, "total": len(rows),
        "hit_at_k_final": sum(1 for r in with_gold
                              if r["gold_rank"] and r["gold_rank"] <= cfg.k_final),
        "gold_probes": len(with_gold),
        "mrr": round(sum(1 / r["gold_rank"] for r in with_gold if r["gold_rank"])
                     / max(len(with_gold), 1), 3),
        "median_total_s": statistics.median(r["timings"]["total_s"] for r in rows),
    }
    if not retrieval_only:
        summary["passed"] = sum(r["pass"] for r in rows)
    summary["rows"] = rows
    return summary


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

    cfg = load_config("baseline" if args.baseline else args.config, args.set)
    probes = load_cases(paths.PROBES)
    if args.only:
        probes = [p for p in probes if p["probe_id"] in args.only]
    pipeline = Pipeline(cfg, make_client("ollama", cfg.llm_model), write_traces=False)
    rows = []
    for probe in probes:
        rows.append(run_probe(pipeline, probe, args.retrieval_only))
        print_row(rows[-1], args.retrieval_only)

    summary = summarize(rows, args.label, cfg, pipeline, args.retrieval_only)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    label = args.label or ("baseline" if args.baseline else "default")
    kind = "_retrieval" if args.retrieval_only else ""
    paths.PROBE_RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    out = paths.PROBE_RESULTS_DIR / f"probes_{label}{kind}_{stamp}.json"
    out.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    passed = f"  passed: {summary['passed']}/{len(rows)}" if not args.retrieval_only else ""
    print(f"\nhit@{cfg.k_final}: {summary['hit_at_k_final']}/{summary['gold_probes']}  "
          f"MRR: {summary['mrr']}  median latency: {summary['median_total_s']:.1f}s{passed}"
          f"\n-> {paths.relative(out)}")


if __name__ == "__main__":
    main()
