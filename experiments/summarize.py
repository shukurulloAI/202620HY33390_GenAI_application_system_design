"""
One table per experiment (PLAN.md §6: record metrics, latency and regressions).

    python -m experiments.summarize experiments/results/dev/E3     # rewrite summary.md

experiments/run_experiment.py calls this after a run on evaluation cases. The table has
one row per variant; the regressions list the cases a variant got wrong that the reference
variant got right (and the other way round), so a mean that hides a slice loss is visible
(Lesson 6). Reference = the variant named "reference" in the spec, else the variant whose
config equals the full system's, else the first.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from eval.cases import load_cases
from eval.metrics import score
from rag import config, paths
from rag.files import read_jsonl


def _pct(rate: dict | None) -> str:
    return "–" if not rate else f"{rate['k']}/{rate['n']} ({rate['rate']:.0%})"


def reference(spec: dict, manifest: dict) -> str:
    variants = manifest["variants"]
    if spec.get("reference") in variants:
        return spec["reference"]
    full = config.DEFAULT.to_dict()
    return next((name for name, v in variants.items() if v["config"] == full), next(iter(variants)))


def _ok(row: dict, stage: str) -> bool | None:
    if stage == "retrieval":
        return row["retrieval"]["hit"] if "retrieval" in row else None
    return row["case_ok"]


def write_summary(spec: dict, manifest: dict, cases: list[dict], out_dir: Path) -> Path:
    stage = spec["stage"]
    results = {name: score(read_jsonl(paths.ROOT / v["traces"]), cases)
               for name, v in manifest["variants"].items()}
    ref = reference(spec, manifest)
    lines = [f"# {spec['id']}: {spec.get('question', '')}", "",
             f"Cases `{manifest['cases']}` ({manifest['n_cases']}, sha256 "
             f"`{manifest['cases_sha256'][:12]}`), commit `{(manifest['git_commit'] or '')[:7]}`"
             f"{' (uncommitted changes)' if manifest['git_dirty'] else ''}. "
             f"Reference variant: `{ref}`.", ""]
    if stage == "retrieval":
        langs = sorted({c["lang"] for c in cases})
        lines += ["| Variant | Recall@5 | MRR | nDCG@5 | P@5 | " + " | ".join(
                      f"R@5 {lang}" for lang in langs) + " | Retrieve s (median) |",
                  "|---|---|---|---|---|" + "---|" * len(langs) + "---|"]
        for name, result in results.items():
            r = result["overall"]["retrieval"]
            by_lang = [str(result["by_lang"].get(lang, {}).get("retrieval", {}).get("recall@5"))
                       for lang in langs]
            retrieve = result["stage_latency_s"].get("retrieve_s", {}).get("median")
            lines.append(f"| {name} | {r['recall@5']} | {r['mrr']} | {r['ndcg@5']} | "
                         f"{r['precision@5']} | " + " | ".join(by_lang) + f" | {retrieve} |")
        lines.append(f"\nn = {results[ref]['overall']['retrieval']['n']} cases with gold chunks.")
    else:
        lines += ["| Variant | Correct | False answers | Bin | Behaviour | Abstain ok | "
                  "Clarify ok | Cites gold | Cit. precision | Language ok | JSON valid | "
                  "Downgraded | Median s |", "|---|" + "---|" * 12]
        for name, result in results.items():
            o = result["overall"]
            lines.append(
                f"| {name} | {_pct(o['case_ok'])} | {_pct(o['false_answer'])} | "
                f"{_pct(o['bin_ok'])} | {_pct(o['behaviour_ok'])} | {_pct(o['abstain_ok'])} | "
                f"{_pct(o['clarify_ok'])} | {_pct(o['cites_gold'])} | "
                f"{o['citation_precision']} | {_pct(o['language_ok'])} | "
                f"{_pct(o['json_valid'])} | {o['downgraded']} | {o['latency_s']['median']} |")
        slices = sorted({c["slice"] for c in cases})
        lines += ["", "Correct by slice:", "", "| Variant | " + " | ".join(slices) + " |",
                  "|---|" + "---|" * len(slices)]
        for name, result in results.items():
            lines.append(f"| {name} | " + " | ".join(
                _pct(result["by_slice"].get(s, {}).get("case_ok")) for s in slices) + " |")
    schedule = {name: v["quick_summary"].get("schedule")
                for name, v in manifest["variants"].items() if v["quick_summary"].get("schedule")}
    if schedule and spec["id"] == "E4":
        keys = ["cases", "answerable", "row_found", "top_row", "only_correct_rows",
                "day_time_match", "empty", "wrong_place", "behaviour_ok"]
        lines += ["", "Schedule rows (counts):", "", "| Variant | " + " | ".join(keys) + " |",
                  "|---|" + "---|" * len(keys)]
        for name, counts in schedule.items():
            lines.append(f"| {name} | " + " | ".join(str(counts.get(k, 0)) for k in keys) + " |")

    ref_ok = {r["case_id"]: _ok(r, stage) for r in results[ref]["rows"]}
    lines += ["", f"## Changes against `{ref}`", ""]
    for name, result in results.items():
        if name == ref:
            continue
        ok = {r["case_id"]: _ok(r, stage) for r in result["rows"]}
        worse = sorted(c for c in ok if ref_ok.get(c) is True and ok[c] is False)
        better = sorted(c for c in ok if ref_ok.get(c) is False and ok[c] is True)
        lines.append(f"- `{name}`: worse on {len(worse)} ({', '.join(worse) or '–'}); "
                     f"better on {len(better)} ({', '.join(better) or '–'})")
    path = out_dir / "summary.md"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("results_dir", type=Path)
    args = parser.parse_args()
    manifest = json.loads((args.results_dir / "manifest.json").read_text(encoding="utf-8"))
    spec = json.loads((paths.ROOT / manifest["spec_file"]).read_text(encoding="utf-8"))
    cases = load_cases(paths.ROOT / manifest["cases"])
    if manifest.get("slices"):
        cases = [c for c in cases if c.get("slice") in manifest["slices"]]
    cases = cases[:manifest["limit"]] if manifest.get("limit") else cases
    print(write_summary(spec, manifest, cases, args.results_dir))


if __name__ == "__main__":
    main()
