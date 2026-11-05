"""
Run one controlled experiment (PLAN.md §6): the same cases through every variant of one
config file, changing only the fields the variant lists.

    python -m experiments.run_experiment experiments/configs/E3_lexical_dense_hybrid.json
    python -m experiments.run_experiment experiments/configs/E1_prompt.json --cases eval/cases/dev.jsonl
    python -m experiments.run_experiment <config> --variants dense hybrid-rrf --limit 10

Output (for Anar's metrics):
    experiments/results/<id>/<variant>.jsonl   one full trace per case (case_id included)
    experiments/results/<id>/manifest.json     configs, models, cases file + SHA-256, git commit

Rules enforced here:
    - cases default to the dev split; a test file needs --allow-test (Lesson 6: run the
      frozen configuration on test once, at the end)
    - every variant = base config + "fixed" fields + its own fields, nothing else
"""
from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import subprocess
from collections import Counter
from datetime import datetime
from pathlib import Path

from rag import config
from rag.config import PipelineConfig
from rag.llm_client import make_client
from rag.pipeline import Pipeline

RESULTS = Path(__file__).with_name("results")
DEV_CASES = config.ROOT / "eval" / "cases" / "dev.jsonl"
PROBES = Path(__file__).with_name("probes.jsonl")


def load_cases(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip()]


def expand_variants(spec: dict) -> dict[str, dict]:
    if "grid" in spec:
        keys = list(spec["grid"])
        return {"-".join(f"{k}={v}" for k, v in zip(keys, combo)): dict(zip(keys, combo))
                for combo in itertools.product(*(spec["grid"][k] for k in keys))}
    return spec["variants"]


def base_config(spec: dict) -> PipelineConfig:
    base = spec.get("base", "default")
    if base == "baseline":
        return config.BASELINE
    if isinstance(base, dict):
        return config.DEFAULT.replace(**base)
    return config.DEFAULT


def gold_ids(case: dict) -> list[str]:
    """UUID chunk IDs or legacy IDs (e.g. item2018_0278); both are matched."""
    return case.get("expected_chunk_ids") or case.get("gold_chunks") or []


def quick_summary(traces: list[dict], cases: list[dict], k: int) -> dict:
    """A first look only; the official metrics are Anar's (eval/metrics.py)."""
    by_id = {c.get("case_id") or c.get("probe_id"): c for c in cases}
    hits, rr, n_gold = 0, 0.0, 0
    for t in traces:
        gold = gold_ids(by_id.get(t["case_id"], {}))
        if not gold:
            continue
        n_gold += 1
        rank = next((c["rank"] for c in t.get("candidates", [])
                     if c["chunk_id"] in gold or c["metadata"].get("legacy_id") in gold), None)
        hits += bool(rank and rank <= k)
        rr += 1 / rank if rank else 0.0
    statuses = Counter((t.get("answer") or {}).get("status", "retrieval-only") for t in traces)
    totals = [t["timings"]["total_s"] for t in traces]
    return {"cases": len(traces), "gold_cases": n_gold,
            f"recall@{k}": round(hits / n_gold, 3) if n_gold else None,
            "mrr": round(rr / n_gold, 3) if n_gold else None,
            "statuses": dict(statuses),
            "mean_total_s": round(sum(totals) / len(totals), 2) if totals else None}


def git_commit() -> str | None:
    try:
        return subprocess.run(["git", "rev-parse", "HEAD"], cwd=config.ROOT, text=True,
                              capture_output=True, check=True).stdout.strip()
    except Exception:
        return None


def git_dirty() -> bool | None:
    """True if tracked code (rag/, preprocess/, experiments/*.py, prompts) has uncommitted
    changes: then `git_commit` alone does not reproduce the run."""
    try:
        out = subprocess.run(["git", "status", "--porcelain", "--", "rag", "preprocess",
                              "ingest", "experiments/*.py", "experiments/configs"],
                             cwd=config.ROOT, text=True, capture_output=True, check=True).stdout
        return bool(out.strip())
    except Exception:
        return None


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("config", type=Path)
    parser.add_argument("--cases", type=Path)
    parser.add_argument("--variants", nargs="*")
    parser.add_argument("--limit", type=int)
    parser.add_argument("--allow-test", action="store_true")
    parser.add_argument("--llm", default="ollama", choices=["ollama", "fixture"])
    args = parser.parse_args()

    spec = json.loads(args.config.read_text(encoding="utf-8"))
    cases_path = args.cases or (DEV_CASES if DEV_CASES.exists() else PROBES)
    if cases_path == PROBES:
        print(f"note: {DEV_CASES.relative_to(config.ROOT)} not found; using the developer "
              "probes. Numbers from probes are not evaluation results.")
    if "test" in cases_path.name and not args.allow_test:
        raise SystemExit("refusing to run on a test split without --allow-test")
    cases = load_cases(cases_path)
    limit = args.limit or spec.get("limit")
    if limit:
        cases = cases[:limit]

    variants = expand_variants(spec)
    if args.variants:
        variants = {name: v for name, v in variants.items() if name in args.variants}
    out_dir = RESULTS / spec["id"]
    out_dir.mkdir(parents=True, exist_ok=True)
    manifest = {"id": spec["id"], "question": spec.get("question"), "stage": spec["stage"],
                "spec_file": str(args.config), "cases": str(cases_path),
                "cases_sha256": hashlib.sha256(cases_path.read_bytes()).hexdigest(),
                "n_cases": len(cases), "git_commit": git_commit(), "git_dirty": git_dirty(),
                "started": datetime.now().isoformat(timespec="seconds"), "variants": {}}

    base = base_config(spec)
    for name, fields in variants.items():
        cfg = base.replace(**spec.get("fixed", {}), **fields)
        pipeline = Pipeline(cfg, make_client(args.llm, cfg.llm_model), write_traces=False)
        traces = []
        path = out_dir / f"{name}.jsonl"
        with path.open("w", encoding="utf-8") as f:
            for i, case in enumerate(cases, 1):
                trace = pipeline.run_case(case, stop_after_retrieval=spec["stage"] == "retrieval")
                f.write(json.dumps(trace, ensure_ascii=False) + "\n")
                traces.append(trace)
                print(f"\r{spec['id']} {name}: {i}/{len(cases)}", end="", flush=True)
        summary = quick_summary(traces, cases, cfg.k_final)
        manifest["variants"][name] = {"config": cfg.to_dict(), "settings": pipeline.settings(),
                                      "traces": str(path.relative_to(config.ROOT)),
                                      "quick_summary": summary}
        print(f"\r{spec['id']} {name}: {json.dumps(summary, ensure_ascii=False)}")
    manifest["finished"] = datetime.now().isoformat(timespec="seconds")
    (out_dir / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2),
                                           encoding="utf-8")
    print(f"-> {out_dir.relative_to(config.ROOT)}/")


if __name__ == "__main__":
    main()
