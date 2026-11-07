"""
Run one controlled experiment (PLAN.md §6): the same cases through every variant of one
config file, changing only the fields the variant lists.

    python -m experiments.run_experiment experiments/configs/E3_lexical_dense_hybrid.json
    python -m experiments.run_experiment <config> --cases eval/cases/dev.jsonl
    python -m experiments.run_experiment <config> --variants dense hybrid-rrf --limit 10

Output:
    experiments/results/<id>/<variant>.jsonl   one full trace per case (case_id included)
    experiments/results/<id>/manifest.json     configs, models, cases file + SHA-256, git commit

Rules enforced here:
    - cases default to the dev split; a test file needs --allow-test (Lesson 6: run the
      frozen configuration on test once, at the end)
    - every variant = base config + "fixed" fields + its own fields, nothing else
"""
from __future__ import annotations

import argparse
import itertools
import json
from datetime import datetime
from pathlib import Path

from eval.cases import default_cases, load_cases
from eval.metrics import quick_summary, schedule_summary
from experiments.provenance import git_commit, git_dirty
from rag import config, paths
from rag.config import PipelineConfig
from rag.files import sha256_file
from rag.llm_client import make_client
from rag.pipeline import Pipeline


def expand_variants(spec: dict) -> dict[str, dict]:
    if "grid" in spec:
        keys = list(spec["grid"])
        return {"-".join(f"{k}={v}" for k, v in zip(keys, combo, strict=True)):
                dict(zip(keys, combo, strict=True))
                for combo in itertools.product(*(spec["grid"][k] for k in keys))}
    return spec["variants"]


def base_config(spec: dict) -> PipelineConfig:
    base = spec.get("base", "default")
    if base == "baseline":
        return config.BASELINE
    if isinstance(base, dict):
        return config.DEFAULT.replace(**base)
    return config.DEFAULT


def choose_cases(explicit: Path | None, allow_test: bool) -> Path:
    path = explicit or default_cases()
    if path == paths.PROBES:
        print(f"note: {paths.relative(paths.DEV_CASES)} not found; using the developer "
              "probes. Numbers from probes are not evaluation results.")
    if "test" in path.name and not allow_test:
        raise SystemExit("refusing to run on a test split without --allow-test")
    return path


def run_variant(spec: dict, name: str, cfg: PipelineConfig, cases: list[dict], llm_name: str,
                out_dir: Path) -> dict:
    """One variant over every case. Returns its entry for the manifest."""
    pipeline = Pipeline(cfg, make_client(llm_name, cfg.llm_model), write_traces=False)
    path = out_dir / f"{name}.jsonl"
    traces = []
    with path.open("w", encoding="utf-8") as f:
        for i, case in enumerate(cases, 1):
            trace = pipeline.run_case(case, stop_after_retrieval=spec["stage"] == "retrieval")
            f.write(json.dumps(trace, ensure_ascii=False) + "\n")
            traces.append(trace)
            print(f"\r{spec['id']} {name}: {i}/{len(cases)}", end="", flush=True)
    summary = quick_summary(traces, cases, cfg.k_final)
    if any(c.get("expected_schedule") for c in cases):
        summary["schedule"] = schedule_summary(traces, cases, pipeline.schedule)
    print(f"\r{spec['id']} {name}: {json.dumps(summary, ensure_ascii=False)}")
    return {"config": cfg.to_dict(), "settings": pipeline.settings(),
            "traces": paths.relative(path), "quick_summary": summary}


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
    cases_path = choose_cases(args.cases, args.allow_test)
    cases = load_cases(cases_path)
    limit = args.limit or spec.get("limit")
    if limit:
        cases = cases[:limit]

    variants = expand_variants(spec)
    if args.variants:
        variants = {name: v for name, v in variants.items() if name in args.variants}
    out_dir = paths.RESULTS_DIR / spec["id"]
    out_dir.mkdir(parents=True, exist_ok=True)
    manifest = {"id": spec["id"], "question": spec.get("question"), "stage": spec["stage"],
                "spec_file": str(args.config), "cases": str(cases_path),
                "cases_sha256": sha256_file(cases_path),
                "n_cases": len(cases), "git_commit": git_commit(), "git_dirty": git_dirty(),
                "started": datetime.now().isoformat(timespec="seconds"), "variants": {}}

    base = base_config(spec)
    for name, fields in variants.items():
        cfg = base.replace(**spec.get("fixed", {}), **fields)
        manifest["variants"][name] = run_variant(spec, name, cfg, cases, args.llm, out_dir)
    manifest["finished"] = datetime.now().isoformat(timespec="seconds")
    (out_dir / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2),
                                           encoding="utf-8")
    print(f"-> {paths.relative(out_dir)}/")


if __name__ == "__main__":
    main()
