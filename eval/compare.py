"""
Paired comparison of two evaluation reports on the same cases (Lesson 6). Reads the per-case
rows already in report.json, so it needs no models and does not rerun anything.

    python -m eval.compare test-final test-baseline
    python -m eval.compare dev-s3e-final dev-baseline --out docs/compare_dev.md

For each metric: both rates with a 95% Wilson interval, the discordant cases (only A is
right / only B is right), and the exact McNemar p. A metric that is undefined for a case
in either report (e.g. bin_ok for a schedule case) leaves that case out of that row.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from eval.stats import fmt_interval, mcnemar_exact, wilson
from rag import paths

REPORT_DIR = paths.ROOT / "eval" / "reports"
METRICS = {"case_ok": "Case correct", "behaviour_ok": "Expected behaviour",
           "bin_ok": "Bin correct (answerable item cases)",
           "false_answer": "False answers (fewer is better)"}


def load(name: str) -> tuple[dict, dict[str, dict]]:
    report = json.loads((REPORT_DIR / name / "report.json").read_text(encoding="utf-8"))
    return report["meta"], {row["case_id"]: row for row in report["rows"]}


def compare(a_rows: dict[str, dict], b_rows: dict[str, dict]) -> dict[str, dict]:
    if set(a_rows) != set(b_rows):
        raise ValueError("the reports ran on different cases")
    out = {}
    for metric in METRICS:
        pairs = [(a_rows[c][metric], b_rows[c][metric]) for c in sorted(a_rows)
                 if a_rows[c].get(metric) is not None and b_rows[c].get(metric) is not None]
        n = len(pairs)
        ka, kb = sum(bool(a) for a, _ in pairs), sum(bool(b) for _, b in pairs)
        only_a = sum(bool(a) and not b for a, b in pairs)
        only_b = sum(bool(b) and not a for a, b in pairs)
        out[metric] = {"n": n, "a": ka, "b": kb, "a_ci": wilson(ka, n), "b_ci": wilson(kb, n),
                       "only_a": only_a, "only_b": only_b,
                       "p": mcnemar_exact(only_a, only_b)}
    return out


def fmt_p(p: float) -> str:
    return "< 0.0001" if p < 0.0001 else f"{p:.4f}"


def markdown(a: str, b: str, result: dict[str, dict]) -> str:
    lines = [f"Paired comparison: **{a}** (A) vs **{b}** (B), same cases. 95% Wilson "
             "intervals; exact McNemar test on the discordant cases.", "",
             "| Metric | n | A | B | Only A | Only B | p |", "|---|---|---|---|---|---|---|"]
    for metric, r in result.items():
        lines.append(f"| {METRICS[metric]} | {r['n']} | "
                     f"{r['a']}/{r['n']} ({fmt_interval(r['a_ci'])}) | "
                     f"{r['b']}/{r['n']} ({fmt_interval(r['b_ci'])}) | {r['only_a']} | "
                     f"{r['only_b']} | {fmt_p(r['p'])} |")
    lines += ["", "For false answers, fewer is better: \"Only B\" counts cases where only B "
              "answered falsely. p ≥ 0.05 means the sample cannot separate the two systems on "
              "that metric.", ""]
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("a", help="report folder under eval/reports/ (the new system)")
    parser.add_argument("b", help="report folder under eval/reports/ (the reference)")
    parser.add_argument("--out", type=Path, help="also write the table to this file")
    args = parser.parse_args()
    meta_a, rows_a = load(args.a)
    meta_b, rows_b = load(args.b)
    if meta_a["cases_sha256"] != meta_b["cases_sha256"]:
        raise SystemExit("the two reports used different case files")
    text = markdown(args.a, args.b, compare(rows_a, rows_b))
    print(text)
    if args.out:
        args.out.write_text(text, encoding="utf-8")


if __name__ == "__main__":
    main()
