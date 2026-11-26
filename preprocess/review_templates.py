"""
Blank review sheets for the v3 data fixes (docs/V3_PLAN.md). People fill them in; the code
does not read them until they are reviewed and moved to data/manual/.

    python -m preprocess.review_templates          # writes data/manual/drafts/*.csv

    item_names_review.csv      every Korean item name in the corpus, with empty columns for
                               the user languages (the router's item-name translation caused
                               5 of the 8 failures on test, docs/REPORT.md §9)
    category_map_review.csv    every 2018 guide entry, with an empty column for the 2026 rule
                               that replaces it (the conflict slice is 0/8, §9)

The sheets are UTF-8 with a byte-order mark, so spreadsheet programs show Korean correctly.
Existing sheets are never overwritten: rename or delete one to make it again.
"""
from __future__ import annotations

import csv

from rag import paths
from rag.files import read_jsonl

DRAFTS = paths.MANUAL_DIR / "drafts"
LANGS = ("en", "zh", "vi", "uz", "ru")


def item_names(chunks: list[dict]) -> list[dict]:
    rows = {}
    for c in chunks:
        meta = c["metadata"]
        name = meta.get("item")
        if name and name not in rows:
            rows[name] = {"item_ko": name, "doc_type": meta["doc_type"],
                          "source_year": meta.get("source_year"), "example_ref": meta.get(
                              "legacy_id") or c["id"],
                          **{lang: "" for lang in LANGS}, "reviewer_initials": "", "notes": ""}
    return sorted(rows.values(), key=lambda r: r["item_ko"])


def category_map(chunks: list[dict]) -> tuple[list[dict], list[str]]:
    rules = [c for c in chunks if c["metadata"].get("source_year") == 2026
             and c["metadata"]["doc_type"] == "rule"]
    choices = [f"{c['metadata']['legacy_id']}: {c['metadata']['item']} / "
               f"{c['metadata'].get('sub_item') or ''}" for c in rules]
    rows = [{"legacy_id": c["metadata"].get("legacy_id"), "item_2018": c["metadata"]["item"],
             "bin_2018": c["metadata"].get("categories", ""), "page_2018": c["metadata"].get("page"),
             "rule_2026": "", "same_bin_in_2026": "", "reviewer_initials": "", "notes": ""}
            for c in chunks if c["metadata"].get("source_year") == 2018
            and c["metadata"]["doc_type"] == "item"]
    return rows, choices


def write(path, rows: list[dict]) -> bool:
    if path.exists():
        print(f"kept {paths.relative(path)} (exists)")
        return False
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    print(f"wrote {paths.relative(path)} ({len(rows)} rows)")
    return True


def main() -> None:
    chunks = read_jsonl(paths.ITEM_CHUNKS)
    DRAFTS.mkdir(parents=True, exist_ok=True)
    write(DRAFTS / "item_names_review.csv", item_names(chunks))
    rows, choices = category_map(chunks)
    if write(DRAFTS / "category_map_review.csv", rows):
        (DRAFTS / "rules_2026.txt").write_text(
            "The 2026 rules a 2018 entry can map to (rule_2026 column: the ID before the colon,\n"
            "or 'none' when no 2026 rule covers the item):\n\n" + "\n".join(choices) + "\n",
            encoding="utf-8")


if __name__ == "__main__":
    main()
