"""
Find gold labels for evaluation cases: the chunks that answer an item question, and the
district rows that answer a schedule question. Read-only, no models.

    python -m eval.label_helper item 피자 건전지           # chunks naming any of these words
    python -m eval.label_helper rows 성동구 --dong 행당1동  # rows a table scan finds

A person still decides: the helper lists candidates and the bins each chunk states
(rag/bins.evidence_bins); it does not choose. Gold labels come from these scans and never
from the system being measured (PLAN.md §7.1).
"""
from __future__ import annotations

import argparse
import re

from rag import paths
from rag.bins import evidence_bins
from rag.files import read_jsonl
from rag.schedule_tool import area_base, default_table


def item_chunks(words: list[str]) -> list[dict]:
    """Chunks whose item name or text contains any of `words` (spaces ignored)."""
    keys = [w.replace(" ", "") for w in words]
    out = []
    for chunk in read_jsonl(paths.ITEM_CHUNKS):
        meta = chunk["metadata"]
        name = re.sub(r"\s+", "", f"{meta.get('item', '')} {meta.get('sub_item', '')}")
        body = re.sub(r"\s+", "", chunk["text"])
        hits = [k for k in keys if k in name or k in body]
        if hits:
            out.append({"id": chunk["id"], "legacy_id": meta.get("legacy_id"),
                        "doc_type": meta["doc_type"], "year": meta.get("source_year"),
                        "item": meta.get("item") or meta.get("topic") or meta.get("section"),
                        "bins": sorted(evidence_bins(meta)),
                        "in_name": any(k in name for k in hits),
                        "text": chunk["text"]})
    return sorted(out, key=lambda c: (not c["in_name"], c["doc_type"] != "item", c["legacy_id"]))


def schedule_rows(district: str, province: str | None = None, dong: str | None = None) -> list:
    """Rows of the district table for this place: an exact area name, else its base name
    (상계동 for 상계1동), else the rows that cover the whole district (no area names). The
    same rule a person would use reading the CSV."""
    rows = [r for r in default_table().rows if r.district == district
            and (province is None or r.province == province)]
    if not dong:
        return rows
    exact = [r for r in rows if dong in r.area_names]
    base = [r for r in rows if any(area_base(a) == area_base(dong) for a in r.area_names)]
    return exact or base or [r for r in rows if not r.area_names]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="what", required=True)
    item = sub.add_parser("item")
    item.add_argument("words", nargs="+")
    item.add_argument("--full", action="store_true", help="print whole chunk texts")
    rows = sub.add_parser("rows")
    rows.add_argument("district")
    rows.add_argument("--province")
    rows.add_argument("--dong")
    args = parser.parse_args()

    if args.what == "item":
        for c in item_chunks(args.words):
            text = c["text"] if args.full else c["text"].replace("\n", " | ")[:160]
            print(f"{c['id']}  {c['legacy_id']:30} {c['doc_type']:6} {c['year']} "
                  f"bins={c['bins']}  {c['item']}\n    {text}")
    else:
        for r in schedule_rows(args.district, args.province, args.dong):
            rules = {t: (r.rules[t].days_en(), r.rules[t].start, r.rules[t].end)
                     for t in r.rules if r.rules[t].days}
            print(f"{r.row_id} {r.province} {r.district} {r.zone} areas={r.area_names[:6]} "
                  f"{rules} date={r.data_date}")


if __name__ == "__main__":
    main()
