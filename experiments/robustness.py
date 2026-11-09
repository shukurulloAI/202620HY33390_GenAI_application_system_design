"""
Robustness probes (PLAN.md §7.6, RGB-style; Lesson 6): the same answerable item cases with
the evidence changed on purpose, between retrieval and the gate (Pipeline.evidence_hook).

    python -m experiments.robustness --cases eval/cases/dev.jsonl --limit 3     # smoke test
    python -m experiments.robustness --cases eval/cases/test.jsonl --allow-test  # Stage 4

Probes (each case once per probe, plus one clean run):
    clean           no change
    noise           3 unrelated chunks appended (chunks that state other bins); the answer
                    should not change
    negative        every gold chunk removed (the next candidates move up); the system
                    should not answer with a bin
    counterfactual  a false chunk at rank 1 that names the asked item with a wrong bin,
                    written like a 2018 guide entry; the real evidence stays. The system
                    should keep the right bin, abstain, or flag the conflict, not follow it

Information integration (item + schedule from two sources) is the `combined` slice of the
main evaluation, so it is not repeated here.

Writes experiments/results/<split>/robustness/<probe>.jsonl and summary.md. Cases: answer
cases with an expected bin and gold chunks.
"""
from __future__ import annotations

import argparse
import json
import random
from collections import Counter
from pathlib import Path

from eval.cases import gold_chunks, load_cases
from eval.metrics import score_case
from eval.provenance import git_commit, git_dirty
from rag import config, paths
from rag.bins import BINS, evidence_bins
from rag.files import read_jsonl, sha256_file
from rag.retrieve import Candidate

SEED = 20261108
PROBES = ("clean", "noise", "negative", "counterfactual")


def _is_gold(candidate: Candidate, gold: set[str]) -> bool:
    return candidate.chunk_id in gold or candidate.metadata.get("legacy_id") in gold


def wrong_bin(expected: list[str]) -> str:
    """A bin the case does not accept, fixed per case: food waste, else paper."""
    return "음식물" if "음식물" not in expected else "종이"


def false_chunk(case: dict, item: str) -> Candidate:
    wrong = wrong_bin(case["expected_bin"])
    text = (f"[분리배출 품목] {item}\n구분: {wrong} ({BINS[wrong]})\n"
            f"배출방법: {wrong}(으)로 배출\n출처: 환경부 재활용품 분리배출 가이드라인 (2018) p.40")
    return Candidate(
        chunk_id=f"counterfactual-{case['case_id']}", text=text,
        metadata={"doc_type": "item", "item": item, "categories": wrong, "source_year": 2018,
                  "page": 40, "legacy_id": "counterfactual",
                  "source": "환경부 재활용품 분리배출 가이드라인 (2018)"},
        score=1.0, rank=0, retriever="probe", rerank_score=0.99)


def make_hook(probe: str, case: dict, noise_pool: list[Candidate]):
    gold = set(gold_chunks(case))
    rng = random.Random(f"{SEED}-{case['case_id']}")

    def hook(selected: list[Candidate], trace: dict) -> list[Candidate]:
        k = len(selected) or config.K_FINAL
        info = {"probe": probe}
        if probe == "noise":
            wanted = set(case["expected_bin"])
            pool = [c for c in noise_pool if not (evidence_bins(c.metadata) & wanted)
                    and c.chunk_id not in {s.chunk_id for s in selected}]
            added = rng.sample(pool, 3)
            selected = [*selected, *added]
            info["added"] = [c.chunk_id for c in added]
        elif probe == "negative":
            rest = [c for c in trace_candidates(trace) if not _is_gold(c, gold)]
            info["removed"] = [c.chunk_id for c in selected if _is_gold(c, gold)]
            selected = rest[:k]
        elif probe == "counterfactual":
            item = next((c.metadata.get("item") for c in selected
                         if _is_gold(c, gold) and c.metadata.get("item")), None) \
                or (trace.get("route") or {}).get("item_ko") or case["question"]
            fake = false_chunk(case, item)
            selected = [fake, *selected[:k - 1]]
            info["false_bin"] = wrong_bin(case["expected_bin"])
            info["item"] = item
        trace["perturbation"] = info
        return selected

    return hook


_CANDIDATES: dict[str, list[Candidate]] = {}


def trace_candidates(trace: dict) -> list[Candidate]:
    """The full candidates of this request (the trace keeps only 200 characters)."""
    return _CANDIDATES.get(trace["trace_id"], [])


def outcome(probe: str, row: dict, trace: dict, case: dict, clean_bin: str | None) -> str:
    """An ANSWER with no bin (the item part withheld, only the schedule given) names no bin,
    so it counts as abstaining on the item, as in eval/metrics.py."""
    answer = trace["answer"]
    answered, bin_key = answer["status"] == "ANSWER", answer.get("bin") or ""
    named = answered and bool(bin_key)
    if probe == "negative":
        return "abstained" if not named else (
            "right bin anyway" if row.get("bin_ok") else "wrong bin")
    if probe == "counterfactual":
        if named and bin_key == wrong_bin(case["expected_bin"]):
            return "followed the false chunk"
        return "right bin" if row.get("bin_ok") else ("abstained" if not named else
                                                       "other wrong bin")
    if probe == "noise":                       # compared with the clean run of the case
        if not named:
            return "abstained, as clean" if not clean_bin else "abstained (clean answered)"
        if not clean_bin:
            return "answered (clean abstained)"
        return "same bin" if bin_key == clean_bin else "changed bin"
    return "right bin" if row.get("bin_ok") else ("abstained" if not named else "wrong bin")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--cases", type=Path, default=paths.DEV_CASES)
    parser.add_argument("--allow-test", action="store_true")
    parser.add_argument("--limit", type=int)
    parser.add_argument("--config", help="'baseline' or a JSON file of PipelineConfig fields")
    parser.add_argument("--set", action="append", default=[], metavar="FIELD=VALUE")
    parser.add_argument("--relabel", action="store_true",
                        help="label the saved probe traces again; no model calls")
    args = parser.parse_args()
    if "test" in args.cases.name and not args.allow_test:
        raise SystemExit("refusing to run on the test split without --allow-test")
    if args.relabel:
        relabel(args.cases)
        return

    from rag.llm_client import CachedClient, make_client
    from rag.pipeline import Pipeline
    cfg = config.load_config(args.config, args.set)
    llm = CachedClient(make_client("ollama", cfg.llm_model))
    pipeline = Pipeline(cfg, llm, write_traces=False)
    original_search = pipeline.retriever.search

    def keep_candidates(*a, **kw):          # remember full candidates for the negative probe
        candidates, selected, record = original_search(*a, **kw)
        keep_candidates.last = candidates
        return candidates, selected, record

    pipeline.retriever.search = keep_candidates
    cases = [c for c in load_cases(args.cases) if c["expected_behavior"] == "answer"
             and c.get("expected_bin") and gold_chunks(c)][:args.limit]
    noise_pool = [Candidate(chunk_id=c["id"], text=c["text"], metadata=c["metadata"], score=0.0,
                            rank=0, retriever="probe-noise", rerank_score=0.0)
                  for c in read_jsonl(paths.ITEM_CHUNKS) if c["metadata"]["doc_type"] == "item"]
    out = paths.RESULTS_DIR / args.cases.stem / "robustness"
    out.mkdir(parents=True, exist_ok=True)
    results: dict[str, Counter] = {}
    clean_bins: dict[str, str] = {}
    for probe in PROBES:
        counts = Counter()
        with (out / f"{probe}.jsonl").open("w", encoding="utf-8") as f:
            for i, case in enumerate(cases, 1):
                hook = None if probe == "clean" else make_hook(probe, case, noise_pool)

                def wrapped(selected, trace, hook=hook):
                    _CANDIDATES[trace["trace_id"]] = getattr(keep_candidates, "last", [])
                    return hook(selected, trace) if hook else selected

                pipeline.evidence_hook = wrapped
                trace = pipeline.run_case(case)
                row = score_case(trace, case)
                if probe == "clean":
                    clean_bins[case["case_id"]] = trace["answer"].get("bin") or ""
                result = outcome(probe, row, trace, case, clean_bins.get(case["case_id"]))
                trace["probe_outcome"] = result
                counts[result] += 1
                f.write(json.dumps(trace, ensure_ascii=False) + "\n")
                print(f"\r{probe} {i}/{len(cases)} {case['case_id']:8} {result:28}", end="",
                      flush=True)
        print()
        results[probe] = counts
    run = (f"Commit `{(git_commit() or '')[:7]}`{' (uncommitted changes)' if git_dirty() else ''}"
           f". Config overrides: {args.set or 'none'}.")
    write_summary(out, args.cases, len(cases), results, cfg.to_dict(), run)


def write_summary(out: Path, cases_path: Path, n: int, results: dict[str, Counter],
                  cfg: dict, run: str) -> None:
    lines = ["# Robustness probes (PLAN.md §7.6)", "",
             f"Cases `{paths.relative(cases_path.resolve())}` (sha256 "
             f"`{sha256_file(cases_path)[:12]}`): {n} answer cases with an expected bin and "
             f"gold chunks. {run}", "", "| Probe | Outcomes |", "|---|---|"]
    for probe, counts in results.items():
        lines.append(f"| {probe} | " + ", ".join(f"{k} {v}/{n}"
                                                 for k, v in counts.most_common()) + " |")
    (out / "summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    (out / "summary.json").write_text(json.dumps(
        {"cases": n, "config": cfg, "results": {p: dict(c) for p, c in results.items()}},
        ensure_ascii=False, indent=1), encoding="utf-8")
    print("\n".join(lines))


def relabel(cases_path: Path) -> None:
    """Label the saved probe traces again with the current outcome() (no model calls)."""
    from eval.cases import by_id
    out = paths.RESULTS_DIR / cases_path.stem / "robustness"
    cases = by_id(load_cases(cases_path))
    old = (out / "summary.md").read_text(encoding="utf-8")
    run_at = old.split("Commit `", 1)[1].split("`", 1)[0] if "Commit `" in old else "?"
    results: dict[str, Counter] = {}
    clean_bins: dict[str, str] = {}
    n = 0
    for probe in PROBES:
        counts = Counter()
        traces = read_jsonl(out / f"{probe}.jsonl")
        for trace in traces:
            case = cases[trace["case_id"]]
            if probe == "clean":
                clean_bins[case["case_id"]] = trace["answer"].get("bin") or ""
            row = score_case(trace, case)
            trace["probe_outcome"] = outcome(probe, row, trace, case,
                                             clean_bins.get(case["case_id"]))
            counts[trace["probe_outcome"]] += 1
        with (out / f"{probe}.jsonl").open("w", encoding="utf-8") as f:
            f.writelines(json.dumps(t, ensure_ascii=False) + "\n" for t in traces)
        results[probe] = counts
        n = len(traces)
    cfg = json.loads((out / "summary.json").read_text(encoding="utf-8"))["config"]
    write_summary(out, cases_path, n, results, cfg,
                  f"Run at commit `{run_at}`; outcomes relabelled from the saved traces at "
                  f"commit `{(git_commit() or '')[:7]}` (an ANSWER with no bin counts as "
                  f"abstaining on the item).")


if __name__ == "__main__":
    main()
