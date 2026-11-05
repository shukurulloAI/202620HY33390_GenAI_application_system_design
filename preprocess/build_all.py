"""
Build every preprocessed file, the source manifest and the data-quality report.

    python item_guide/build_item_chunks.py      # only when the PDFs or the parser change
    python -m preprocess.build_all
    python -m ingest.build_index && python -m ingest.build_index --embedding bge-small-en

Outputs (preprocess/): item_chunks.jsonl, schedule.csv, schedule_chunks.jsonl,
dong_lookup.json, district_aliases.json, locations.json, manifest.json,
reports/data_quality.json and reports/data_quality.md. glossary.json and manual/ are
hand-written inputs (checked here, not generated).
"""
from __future__ import annotations

import json
from datetime import datetime
from zoneinfo import ZoneInfo

from preprocess import build_items, build_schedule
from preprocess.common import OUT, ROOT, SOURCES, doc_id, git_added_date, sha256_file, write_json
from rag.bins import BINS


def pdf_pages(path) -> int | None:
    try:
        import pdfplumber
        with pdfplumber.open(path) as pdf:
            return len(pdf.pages)
    except Exception:
        return None


def check_glossary() -> dict:
    data = json.loads((OUT / "glossary.json").read_text(encoding="utf-8"))
    langs = ("ko", "en", "zh", "vi", "uz", "ru")
    terms = data["terms"]
    return {"terms": len(terms),
            "all_languages_filled": all(t.get(l) for t in terms for l in langs),
            "bins_valid": all(t["bin"] in BINS or t["bin"] == "" for t in terms),
            "ko_unique": len({t["ko"] for t in terms}) == len(terms),
            "needs_native_check": data.get("needs_native_check", [])}


def manifest(items: dict, schedule: dict) -> dict:
    sources = []
    for key, src in SOURCES.items():
        record = {"key": key, "doc_id": doc_id(key),
                  **{k: v for k, v in src.items() if k != "path"},
                  "path": str(src["path"].relative_to(ROOT)),
                  "sha256": sha256_file(src["path"]), "bytes": src["path"].stat().st_size,
                  "added_to_repo": git_added_date(src["path"])}
        if src["media_type"] == "application/pdf":
            record["pages"] = pdf_pages(src["path"])
        else:
            record["rows"] = schedule["rows"]
            record["data_date_range"] = [min(schedule["data_year_counts"]),
                                         max(schedule["data_year_counts"])]
        sources.append(record)
    outputs = {"item_chunks.jsonl": items["sha256"], **schedule["outputs"],
               "glossary.json": sha256_file(OUT / "glossary.json"),
               "manual/food_waste_table_2018.json": items["inputs"]["manual_table_sha256"]}
    return {"manifest_version": 1,
            "built_at": datetime.now(ZoneInfo("Asia/Seoul")).isoformat(timespec="seconds"),
            "sources": sources,
            "outputs": {name: {"path": f"preprocess/{name}", "sha256": sha} for name, sha in outputs.items()},
            "not_included": [
                "data.go.kr recycling item API (~770 items): needs an API key; take a dated snapshot, never call it live",
                "schedules for Seoul 도봉구 and 강동구: not in the national CSV"]}


def markdown(report: dict) -> str:
    i, s, g = report["items"], report["schedule"], report["glossary"]
    lines = [
        "# Data quality report", "",
        f"Built {report['built_at']} by `python -m preprocess.build_all`. Numbers for the report (Anar).", "",
        "## Item chunks (`preprocess/item_chunks.jsonl`)", "",
        f"- {i['chunks']} chunks: " + ", ".join(f"{k} {v}" for k, v in i["by_doc_type"].items()),
        f"- IDs: UUIDv5 of source + chunker + span + text digest; old IDs kept as `legacy_id`. "
        f"All checks pass: {all(i['checks'].values())} ({', '.join(k for k, v in i['checks'].items() if v)})",
        f"- Text length: mean {i['chars_mean']} characters, max {i['chars_max']}",
        "- 9 `table` chunks transcribed by hand from the 2018 guide p.17-18 (food-waste tables), "
        "because PDF extraction loses the table layout. Source wording kept; editor search words are labelled.",
        "", "## District schedule (`preprocess/schedule.csv`)", "",
        f"- {s['rows']} rows, {s['province_district_pairs']} districts in {s['provinces']} provinces",
        f"- District names in several provinces (need the province): "
        + ", ".join(f"{d} ({n})" for d, n in s["district_names_in_several_provinces"].items()),
        f"- Seoul districts with no data: {', '.join(s['seoul_districts_without_data'])}",
        f"- District names fixed: {s['district_name_fixes'] or 'none'}; rows with district '없음': {s['rows_with_district_none']}",
        f"- Whole-district rows ('전체', '16개동'): {s['rows_whole_district']}; rows with area notes "
        f"('… 제외'): {s['rows_with_area_notes']}; rows without area names: {s['rows_without_area_names']}",
        f"- Rows with irregular days ('기타'): {s['rows_days_irregular']}; rows without phone: {s['rows_without_phone']}",
        f"- Data dates by year: " + ", ".join(f"{y}: {n}" for y, n in s["data_year_counts"].items()),
        f"- Rows older than 1 year (flagged `오래된데이터`): {s['rows_stale']} "
        f"({100 * s['rows_stale'] / s['rows']:.0f}%); median age {s['data_age_days_median']} days",
        f"- {s['area_names']} area names in `dong_lookup.json`; {s['ambiguous_area_names']} map to "
        "more than one district (the assistant must ask)",
        f"- {s['district_aliases']} romanised district aliases (`district_aliases.json`)",
        f"- Place types: " + ", ".join(f"{k} {v}" for k, v in s["place_types"].items()),
        "", "## Glossary (`preprocess/glossary.json`)", "",
        f"- {g['terms']} terms in ko/en/zh/vi/uz/ru; bins valid: {g['bins_valid']}; "
        f"needs a native-speaker check: {', '.join(g['needs_native_check'])}",
        "", "## Not included", "",
        *[f"- {x}" for x in report["manifest"]["not_included"]], "",
    ]
    return "\n".join(lines)


def main() -> None:
    items = build_items.build()
    schedule = build_schedule.build()
    glossary = check_glossary()
    man = manifest(items, schedule)
    write_json(OUT / "manifest.json", man)
    report = {"built_at": man["built_at"], "items": items, "schedule": schedule,
              "glossary": glossary, "manifest": man}
    write_json(OUT / "reports" / "data_quality.json", report)
    (OUT / "reports" / "data_quality.md").write_text(markdown(report), encoding="utf-8")
    print(markdown(report))


if __name__ == "__main__":
    main()
