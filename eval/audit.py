"""
Human audit of answers (PLAN.md §7.4): two people label the same answers on their own,
and their labels are compared with each other and with the Ragas judge.

    python -m eval.audit export <report name> [--n 20]   # two blank sheets, one per rater
    python -m eval.audit agree <report name>              # after both sheets are filled

`export` picks answered cases spread over slices (fixed seed) and writes
eval/reports/<name>/audit/sheet_rater_A.csv and sheet_rater_B.csv: the question, the
answer, and the full text of the evidence it was built from. The judge's scores are not
in the sheets, so a rater is not led by them. Per answer the rater fills:

    claims         number of factual statements in the answer (bin, steps, days, places ...)
    supported      how many of them the evidence states
    contradicted   how many the evidence contradicts
    bin_correct    y / n / na   (is the bin right for this item, by the evidence)
    notes          free text; every disagreement is explained here afterwards

Statements that are neither supported nor contradicted are "not in the evidence".
`agree` writes audit/agreement.json and agreement.md: human faithfulness
(supported / claims) per rater, Cohen's kappa between raters on "fully supported" and
on bin_correct, and the judge-human agreement on "fully supported" (judge >= 0.999).

Labels must come from people. This module never fills a sheet.
"""
from __future__ import annotations

import argparse
import csv
import json
import random
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPORTS = ROOT / "eval" / "reports"
SEED = 20261108
FIELDS = ["audit_id", "case_id", "slice", "lang", "question", "answer_text", "bin",
          "evidence", "claims", "supported", "contradicted", "bin_correct", "notes"]


def _evidence_texts(trace: dict) -> list[str]:
    from rag import paths
    from rag.files import read_jsonl
    chunks = {c["id"]: c["text"] for c in read_jsonl(paths.ITEM_CHUNKS)}
    rows = {c["ref"]: c.get("text", "") for c in trace["answer"].get("citations", [])
            if c["kind"] == "schedule"}
    out = []
    for e in trace.get("evidence", []):
        text = chunks.get(e["ref"]) if e["kind"] == "item" else rows.get(e["ref"])
        if text:
            out.append(f"[{e['n']}] {text}")
    return out


def pick(rows: list[dict], n: int) -> list[dict]:
    """Round-robin over slices in a fixed shuffled order, so every slice is represented."""
    rng = random.Random(SEED)
    by_slice: dict[str, list[dict]] = {}
    for row in rows:
        by_slice.setdefault(row["slice"] or "-", []).append(row)
    for group in by_slice.values():
        rng.shuffle(group)
    picked, names = [], sorted(by_slice)
    while len(picked) < n and any(by_slice.values()):
        for name in names:
            if by_slice[name] and len(picked) < n:
                picked.append(by_slice[name].pop())
    return picked


def export(name: str, n: int) -> Path:
    from eval.cases import by_id, load_cases
    from rag.files import read_jsonl
    report = json.loads((REPORTS / name / "report.json").read_text(encoding="utf-8"))
    cases = by_id(load_cases(ROOT / report["meta"]["cases_file"]))
    answered = []
    for trace in read_jsonl(ROOT / report["meta"]["traces_file"]):
        if (trace.get("answer") or {}).get("status") == "ANSWER":
            case = cases.get(trace["case_id"], {})
            answered.append({"trace": trace, "slice": case.get("slice"),
                             "lang": case.get("lang"), "question": case.get("question")})
    out = REPORTS / name / "audit"
    out.mkdir(parents=True, exist_ok=True)
    rows = []
    for i, item in enumerate(pick(answered, n), 1):
        answer = item["trace"]["answer"]
        rows.append({"audit_id": f"a{i:02d}", "case_id": item["trace"]["case_id"],
                     "slice": item["slice"], "lang": item["lang"],
                     "question": item["question"], "answer_text": answer["answer_text"],
                     "bin": answer.get("bin", ""),
                     "evidence": "\n\n".join(_evidence_texts(item["trace"])),
                     "claims": "", "supported": "", "contradicted": "", "bin_correct": "",
                     "notes": ""})
    for rater in ("A", "B"):
        with (out / f"sheet_rater_{rater}.csv").open("w", encoding="utf-8-sig",
                                                     newline="") as f:
            writer = csv.DictWriter(f, fieldnames=FIELDS)
            writer.writeheader()
            writer.writerows(rows)
    (out / "README.md").write_text(
        f"# Audit sheets for `{name}`\n\n"
        f"{len(rows)} answers, picked across slices with seed {SEED} "
        "(`python -m eval.audit export`).\n\n"
        "Two people fill one sheet each, **without talking about it and without looking at "
        "the judge scores**. Per answer: `claims` (factual statements in the answer), "
        "`supported` (stated by the evidence), `contradicted` (the evidence says otherwise), "
        "`bin_correct` (y / n / na), `notes`. Then run `python -m eval.audit agree "
        f"{name}` and explain every disagreement in `notes`.\n\n"
        "Status: **not yet labelled** until both sheets have numbers.\n", encoding="utf-8")
    print(f"{len(rows)} answers -> {out.relative_to(ROOT)}/sheet_rater_A.csv, _B.csv")
    return out


def _read(path: Path) -> dict[str, dict]:
    with path.open(encoding="utf-8-sig") as f:
        return {row["audit_id"]: row for row in csv.DictReader(f)}


def _int(value: str) -> int | None:
    try:
        return int(str(value).strip())
    except ValueError:
        return None


def kappa(a: list, b: list) -> float | None:
    """Cohen's kappa for two raters over the same items (labels any hashable)."""
    pairs = [(x, y) for x, y in zip(a, b, strict=True) if x is not None and y is not None]
    if not pairs:
        return None
    labels = sorted({x for p in pairs for x in p}, key=str)
    n = len(pairs)
    observed = sum(x == y for x, y in pairs) / n
    expected = sum((sum(x == lab for x, _ in pairs) / n) * (sum(y == lab for _, y in pairs) / n)
                   for lab in labels)
    return round((observed - expected) / (1 - expected), 3) if expected < 1 else 1.0


def agree(name: str) -> dict:
    out = REPORTS / name / "audit"
    sheets = {r: _read(out / f"sheet_rater_{r}.csv") for r in ("A", "B")}
    ids = sorted(sheets["A"])
    filled = {r: {i: row for i, row in s.items() if _int(row["claims"])} for r, s in
              sheets.items()}
    if not filled["A"] or not filled["B"]:
        raise SystemExit("the sheets are not filled yet (claims column is empty)")

    def fully(row):
        claims, supported = _int(row["claims"]), _int(row["supported"])
        return None if not claims or supported is None else supported == claims

    def faith(rows):
        values = [_int(r["supported"]) / _int(r["claims"]) for r in rows.values()
                  if _int(r["claims"]) and _int(r["supported"]) is not None]
        return round(sum(values) / len(values), 3) if values else None

    judge = {}
    ragas_file = REPORTS / name / "ragas.json"
    if ragas_file.exists():
        scores = {r["case_id"]: r["faithfulness"]
                  for r in json.loads(ragas_file.read_text(encoding="utf-8"))["rows"]}
        judge = {i: scores.get(sheets["A"][i]["case_id"]) for i in ids}
    both = [i for i in ids if i in filled["A"] and i in filled["B"]]
    a_full = [fully(sheets["A"][i]) for i in both]
    b_full = [fully(sheets["B"][i]) for i in both]
    result = {
        "report": name, "answers": len(ids), "labelled_by_both": len(both),
        "human_faithfulness": {r: faith(filled[r]) for r in ("A", "B")},
        "kappa_fully_supported": kappa(a_full, b_full),
        "kappa_bin_correct": kappa([sheets["A"][i]["bin_correct"].strip().lower() or None
                                    for i in both],
                                   [sheets["B"][i]["bin_correct"].strip().lower() or None
                                    for i in both]),
        "disagreements": [i for i, x, y in zip(both, a_full, b_full, strict=True) if x != y],
    }
    if judge:
        judged = [i for i in both if judge.get(i) is not None]
        result["judge_vs_A"] = kappa([fully(sheets["A"][i]) for i in judged],
                                     [judge[i] >= 0.999 for i in judged])
        result["judge_vs_B"] = kappa([fully(sheets["B"][i]) for i in judged],
                                     [judge[i] >= 0.999 for i in judged])
    (out / "agreement.json").write_text(json.dumps(result, indent=1), encoding="utf-8")
    print(json.dumps(result, indent=1))
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("step", choices=["export", "agree"])
    parser.add_argument("name")
    parser.add_argument("--n", type=int, default=20)
    args = parser.parse_args()
    if args.step == "export":
        export(args.name, args.n)
    else:
        agree(args.name)


if __name__ == "__main__":
    main()
