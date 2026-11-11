"""
Run the evaluation (PLAN.md §7): cases through one configuration, scored with eval/metrics.py.

    python -m eval.run_eval --name baseline --config baseline       # Phase 1 system, dev split
    python -m eval.run_eval --name default                          # full system, dev split
    python -m eval.run_eval --name x --set gate_tau=0.3             # one field changed
    python -m eval.run_eval --name e3-dense --traces experiments/results/E3/dense.jsonl
                                                                    # score traces, no run
    python -m eval.run_eval --name final --cases eval/cases/test.jsonl --allow-test

Writes eval/reports/<name>/:
    traces.jsonl    one full trace per case (only when it ran the pipeline)
    report.json     settings, case-file hash, git commit, every metric, one row per case
    report.md       the tables for people: overall, by slice, by language, failure stages

The test split is refused without --allow-test (Lesson 6: one run, at the end, with the
frozen configuration). A report on test lists no per-case rows in report.md, so nobody
tunes on it by reading it.
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path

from eval.cases import load_cases
from eval.metrics import score
from eval.provenance import snapshot
from eval.stats import fmt_interval, wilson
from rag import paths
from rag.config import load_config
from rag.files import read_jsonl, sha256_file

REPORT_DIR = paths.ROOT / "eval" / "reports"
REPLAYED = " (not valid: some LLM replies were replayed from the cache)"


def run(cases: list[dict], config_base: str | None, overrides: list[str], llm: str,
        out: Path, cache: bool = False) -> tuple[list[dict], dict, int]:
    from rag.llm_client import CachedClient, make_client
    from rag.pipeline import Pipeline
    cfg = load_config(config_base, overrides)
    client = make_client(llm, cfg.llm_model)
    if cache:
        client = CachedClient(client)
    pipeline = Pipeline(cfg, client, write_traces=False)
    traces = []
    with out.open("w", encoding="utf-8") as f:
        for i, case in enumerate(cases, 1):
            trace = pipeline.run_case(case)
            f.write(json.dumps(trace, ensure_ascii=False) + "\n")
            f.flush()
            traces.append(trace)
            status = trace["answer"]["status"]
            print(f"\r{i}/{len(cases)} {case['case_id']:8} {status:22}", end="", flush=True)
    print()
    return traces, pipeline.settings(), client.cached if cache else 0


def fmt(rate: dict | None) -> str:
    return "–" if not rate else f"{rate['k']}/{rate['n']} ({rate['rate']:.0%})"


def fmt_ci(rate: dict | None) -> str:
    """fmt plus the 95% Wilson interval, for the headline rates."""
    return "–" if not rate else f"{fmt(rate)}, 95% CI {fmt_interval(wilson(rate['k'], rate['n']))}"


def markdown(name: str, result: dict, meta: dict, show_rows: bool) -> str:
    o = result["overall"]
    r, g, lat = o["retrieval"], o["gate"], o["latency_s"]
    lines = [f"# Evaluation: {name}", "",
             f"Cases: `{meta['cases_file']}` ({o['cases']} cases, sha256 "
             f"`{meta['cases_sha256'][:12]}`), commit `{(meta['git_commit'] or '')[:7]}`"
             f"{' (uncommitted changes)' if meta['git_dirty'] else ''}, {meta['time']}.", "",
             "## Overall", "", "| Metric | Value |", "|---|---|",
             f"| Case correct | {fmt_ci(o['case_ok'])} |",
             f"| Expected behaviour (answer / abstain / clarify / out of scope) | "
             f"{fmt_ci(o['behaviour_ok'])} |",
             f"| Bin correct (answerable item cases) | {fmt_ci(o['bin_ok'])} |",
             f"| **False answers** (answered when it should not, or wrong bin) | "
             f"{fmt_ci(o['false_answer'])} |",
             f"| Abstained when it should | {fmt(o['abstain_ok'])} |",
             f"| Asked back when it should | {fmt(o['clarify_ok'])} |",
             f"| Gold schedule row shown | {fmt(o['rows_found'])} |",
             f"| Only gold rows shown | {fmt(o['only_gold_rows'])} |",
             f"| Router intent | {fmt(o['intent_ok'])} |",
             f"| Router district / dong (place only in the question) | {fmt(o['district_ok'])} / "
             f"{fmt(o['dong_ok'])} |",
             f"| Retrieval Recall@5 / MRR / nDCG@5 / P@5 (n={r['n']}) | {r['recall@5']} / "
             f"{r['mrr']} / {r['ndcg@5']} / {r['precision@5']} |",
             f"| Gate TP / FP / FN / TN (n={g['n']}) | {g['tp']} / {g['fp']} / {g['fn']} / "
             f"{g['tn']} (FP rate {g['fp_rate']}, FN rate {g['fn_rate']}) |",
             f"| Cites a gold chunk / citation precision | {fmt(o['cites_gold'])} / "
             f"{o['citation_precision']} |",
             f"| Answer in the asked language (script) | {fmt(o['language_ok'])} |",
             f"| JSON valid | {fmt(o['json_valid'])} |",
             f"| Downgraded by validation | {o['downgraded']} |",
             f"| Item part withheld, schedule only (not a false answer) | "
             f"{o.get('item_withheld', 0)} |",
             f"| Contract problems | {o['contract_problems']} |",
             f"| Latency mean / median / p90 (s) | {lat['mean']} / {lat['median']} / "
             f"{lat['p90']}{REPLAYED if meta.get('llm_replayed') else ''} |",
             ""]
    for key, title in (("by_slice", "By slice"), ("by_lang", "By language")):
        lines += [f"## {title}", "",
                  "| | Cases | Correct | Behaviour | Bin | False answers | Recall@5 |",
                  "|---|---|---|---|---|---|---|"]
        for value, agg in result[key].items():
            lines.append(f"| {value} | {agg['cases']} | {fmt(agg['case_ok'])} | "
                         f"{fmt(agg['behaviour_ok'])} | {fmt(agg['bin_ok'])} | "
                         f"{fmt(agg['false_answer'])} | {agg['retrieval']['recall@5']} |")
        lines.append("")
    stages = sorted({s for row in result["failure_heatmap"].values() for s in row})
    if stages:
        lines += ["## Earliest failed stage (slice × stage)", "",
                  "| Slice | " + " | ".join(stages) + " |", "|---|" + "---|" * len(stages)]
        for slice_name, counts in result["failure_heatmap"].items():
            lines.append(f"| {slice_name} | " + " | ".join(str(counts.get(s, "")) for s in stages)
                         + " |")
        lines.append("")
    lines += ["## Latency by stage (median s)", "",
              " · ".join(f"{k} {v['median']}" for k, v in result["stage_latency_s"].items()), ""]
    if show_rows:
        lines += ["## Failed cases", "", "| Case | Slice | Lang | Expected | Got | Bin | Stage |",
                  "|---|---|---|---|---|---|---|"]
        for row in result["rows"]:
            if not row["case_ok"]:
                lines.append(f"| {row['case_id']} | {row['slice']} | {row['lang']} | "
                             f"{row['expected']} | {row['status']} | {row.get('bin', '')} | "
                             f"{row['failure_stage']} |")
        lines.append("")
    if result["missing_cases"]:
        lines += [f"Missing traces: {', '.join(result['missing_cases'])}", ""]
    return "\n".join(lines)


def rescore(name: str) -> None:
    out = REPORT_DIR / name
    meta = json.loads((out / "report.json").read_text(encoding="utf-8"))["meta"]
    cases = load_cases(paths.ROOT / meta["cases_file"])[:meta["n_cases"]]
    result = score(read_jsonl(paths.ROOT / meta["traces_file"]), cases)
    meta["rescored"] = {"time": datetime.now().isoformat(timespec="seconds"), **snapshot()}
    (out / "report.json").write_text(json.dumps({"meta": meta, **result}, ensure_ascii=False,
                                                indent=1), encoding="utf-8")
    (out / "report.md").write_text(markdown(name, result, meta, "test" not in meta["cases_file"]),
                                   encoding="utf-8")
    o = result["overall"]
    print(f"{name} (rescored): correct {fmt(o['case_ok'])}, false answers "
          f"{fmt(o['false_answer'])}, item withheld {o['item_withheld']}, bin {fmt(o['bin_ok'])}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--name", required=True, help="report folder under eval/reports/")
    parser.add_argument("--cases", type=Path, default=paths.DEV_CASES)
    parser.add_argument("--config", help="'baseline' or a JSON file of PipelineConfig fields")
    parser.add_argument("--set", action="append", default=[], metavar="FIELD=VALUE")
    parser.add_argument("--traces", type=Path, help="score these traces instead of running")
    parser.add_argument("--llm", default="ollama", choices=["ollama", "fixture"])
    parser.add_argument("--allow-test", action="store_true")
    parser.add_argument("--limit", type=int)
    parser.add_argument("--rescore", action="store_true",
                        help="score the report's own traces again with the current metrics, "
                             "keeping its metadata (after a metric fix)")
    parser.add_argument("--cache", action="store_true",
                        help="replay identical temperature-0 LLM requests from .cache/llm "
                             "(tuning runs; latency is then not valid)")
    args = parser.parse_args()

    if args.rescore:
        rescore(args.name)
        return
    if "test" in args.cases.name and not args.allow_test:
        raise SystemExit("refusing to run on the test split without --allow-test")
    cases = load_cases(args.cases)[:args.limit] if args.limit else load_cases(args.cases)
    provenance = snapshot()                    # before anything is written
    out = REPORT_DIR / args.name
    out.mkdir(parents=True, exist_ok=True)
    replayed = 0
    if args.traces:
        traces, settings = read_jsonl(args.traces), None
    else:
        traces, settings, replayed = run(cases, args.config, args.set, args.llm,
                                         out / "traces.jsonl", args.cache)
    result = score(traces, cases)
    meta = {"name": args.name, "cases_file": paths.relative(args.cases.resolve()),
            "cases_sha256": sha256_file(args.cases), "n_cases": len(cases),
            "traces_file": (str(args.traces) if args.traces
                            else f"{paths.relative(out)}/traces.jsonl"),
            "settings": settings or (traces[0].get("settings") if traces else None),
            "config": args.config, "overrides": args.set, **provenance,
            "llm_replayed": replayed,
            "time": datetime.now().isoformat(timespec="seconds")}
    (out / "report.json").write_text(json.dumps({"meta": meta, **result}, ensure_ascii=False,
                                                indent=1), encoding="utf-8")
    is_test = "test" in args.cases.name
    (out / "report.md").write_text(markdown(args.name, result, meta, not is_test),
                                   encoding="utf-8")
    o = result["overall"]
    print(f"{args.name}: correct {fmt(o['case_ok'])}, false answers {fmt(o['false_answer'])}, "
          f"bin {fmt(o['bin_ok'])}, recall@5 {o['retrieval']['recall@5']} -> "
          f"{paths.relative(out)}/report.md")


if __name__ == "__main__":
    main()
