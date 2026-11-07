"""
Final item chunks for the index (PLAN.md §3.1, §4.1).

Input:  data/interim/parsed_item_chunks.jsonl (PDF parser output, parse-order IDs)
        data/manual/food_waste_table_2018.json (manual table transcription)
Output: data/processed/item_chunks.jsonl

Changes:
  - chunk IDs -> UUIDv5(doc_id | source sha256 | chunker_id | span | text digest);
    the old ID is kept as metadata.legacy_id (readable, used by the probes)
  - provenance on every chunk: doc_id, chunker_id, span, lang
  - text normalised to Unicode NFC
  - + "table" chunks for the 2018 food-waste tables (p.17-18)

    python -m preprocess.build_items
"""
from __future__ import annotations

import json
from collections import Counter

from preprocess.common import SOURCES, chunk_id, doc_id, nfc
from rag import paths
from rag.files import read_jsonl, sha256_file, write_jsonl

PARSED = paths.PARSED_ITEM_CHUNKS
MANUAL_TABLE = paths.FOOD_WASTE_TABLE
OUT_PATH = paths.ITEM_CHUNKS

CHUNKERS = {"item": "item-dict-v1", "faq": "faq-pair-v1", "guide": "guide-page-v1",
            "rule": "annex-row-v1", "note": "annex-note-v1"}
FLAT = (str, int, float, bool, type(None))


def source_key(meta: dict) -> str:
    return "guide2018" if meta.get("source_year") == 2018 else "annex2026"


def span_of(meta: dict) -> str:
    t, page = meta["doc_type"], meta.get("page")
    if t == "item":
        return f"p.{page}|item={meta['item']}"
    if t == "faq":
        return f"p.{page}|faq|{meta.get('topic', '')}"
    if t == "guide":
        return f"p.{page}"
    if t == "rule":
        return f"p.{page}|{meta.get('section', '')[:2]}|{meta.get('item')}|{meta.get('sub_item')}"
    return f"{meta.get('section', '')}"


def table_chunks(source_sha: dict) -> list[dict]:
    spec = json.loads(MANUAL_TABLE.read_text(encoding="utf-8"))
    src = SOURCES[spec["source_key"]]
    source = f"환경부 재활용품 분리배출 가이드라인 ({src['source_year']})"
    chunks = []
    for row in spec["rows"]:
        lines = [f"[음식물류폐기물 분리배출 기준 표] {row['title']}"]
        lines += [nfc(ln) for ln in row["lines"]]
        if row.get("bin_note"):
            lines.append(f"배출방법: {row['bin_note']}")
        lines.append("검색어(편집자 추가): " + ", ".join(row["search_terms"]))
        lines.append(f"출처: {source} p.{row['page']} (표를 옮겨 적음)")
        text = "\n".join(lines)
        span = f"p.{row['page']}|table={row['key']}"
        chunks.append({
            "id": chunk_id(spec["source_key"], source_sha[spec["source_key"]],
                           spec["chunker_id"], span, text),
            "text": text,
            "metadata": {
                "doc_type": "table", "item": row["title"].split(" - ")[-1],
                "categories": row["bin"], "section": "05. 음식물류폐기물",
                "source": source, "source_year": src["source_year"],
                "page": int(row["page"]), "legacy_id": f"table2018_{row['key']}",
                "doc_id": doc_id(spec["source_key"]), "chunker_id": spec["chunker_id"],
                "span": span, "lang": "ko",
            },
        })
    return chunks


def build() -> dict:
    source_sha = {key: sha256_file(SOURCES[key]["path"]) for key in ("guide2018", "annex2026")}
    chunks = []
    for c in read_jsonl(PARSED):
        meta = dict(c["metadata"])
        key, chunker, span = source_key(meta), CHUNKERS[meta["doc_type"]], span_of(meta)
        text = nfc(c["text"])
        meta.update(legacy_id=c["id"], doc_id=doc_id(key), chunker_id=chunker, span=span,
                    lang="ko")
        chunks.append({"id": chunk_id(key, source_sha[key], chunker, span, text),
                       "text": text, "metadata": meta})
    chunks += table_chunks(source_sha)

    ids = [c["id"] for c in chunks]
    checks = {
        "ids_unique": len(set(ids)) == len(ids),
        "legacy_ids_unique": len({c["metadata"]["legacy_id"] for c in chunks}) == len(chunks),
        "text_non_empty": all(c["text"].strip() for c in chunks),
        "metadata_flat": all(isinstance(v, FLAT) for c in chunks for v in c["metadata"].values()),
        "source_present": all(c["metadata"].get("source") for c in chunks),
        "no_reserved_keys": all(not {"chunk_id", "text"} & set(c["metadata"]) for c in chunks),
    }
    if not all(checks.values()):
        raise SystemExit(f"item chunks failed checks: {checks}")
    write_jsonl(OUT_PATH, chunks)
    lengths = [len(c["text"]) for c in chunks]
    return {
        "output": paths.relative(OUT_PATH), "sha256": sha256_file(OUT_PATH),
        "inputs": {"parsed": paths.relative(PARSED), "parsed_sha256": sha256_file(PARSED),
                   "manual_table": paths.relative(MANUAL_TABLE),
                   "manual_table_sha256": sha256_file(MANUAL_TABLE),
                   "source_sha256": source_sha},
        "chunks": len(chunks),
        "by_doc_type": dict(Counter(c["metadata"]["doc_type"] for c in chunks)),
        "chars_mean": round(sum(lengths) / len(lengths), 1), "chars_max": max(lengths),
        "items_without_categories": sum(1 for c in chunks if c["metadata"]["doc_type"] == "item"
                                        and not c["metadata"].get("categories")),
        "checks": checks,
    }


if __name__ == "__main__":
    print(json.dumps(build(), ensure_ascii=False, indent=2))
