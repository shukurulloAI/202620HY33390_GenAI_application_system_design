"""
Build every processed file, the source manifest and the data-quality report.

    python -m preprocess.parse_item_guides      # only when the PDFs or the parser change
    python -m preprocess.build_all
    python -m ingest.build_index && python -m ingest.build_index --embedding bge-small-en

Outputs: data/processed/ (item_chunks.jsonl, schedule.csv, schedule_chunks.jsonl,
dong_lookup.json, district_aliases.json, locations.json, manifest.json) and data/reports/
(data_quality.json, data_quality.md). data/manual/ holds hand-written inputs, which are
checked here and never generated.
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pdfplumber

from preprocess import build_items, build_schedule
from preprocess.common import SOURCES, doc_id, write_json
from rag import paths
from rag.bins import BINS
from rag.files import sha256_file

GLOSSARY_LANGUAGES = ("ko", "en", "zh", "vi", "uz", "ru")


def pdf_pages(path: Path) -> int:
    with pdfplumber.open(path) as pdf:
        return len(pdf.pages)


def check_glossary() -> dict:
    data = json.loads(paths.GLOSSARY.read_text(encoding="utf-8"))
    terms = data["terms"]
    return {"terms": len(terms),
            "all_languages_filled": all(t.get(lang) for t in terms for lang in GLOSSARY_LANGUAGES),
            "bins_valid": all(t["bin"] in BINS or t["bin"] == "" for t in terms),
            "ko_unique": len({t["ko"] for t in terms}) == len(terms),
            "needs_native_check": data.get("needs_native_check", [])}


def source_record(key: str, source: dict, schedule: dict) -> dict:
    path = source["path"]
    record = {"key": key, "doc_id": doc_id(key),
              **{k: v for k, v in source.items() if k != "path"},
              "path": paths.relative(path), "sha256": sha256_file(path),
              "bytes": path.stat().st_size}
    if source["media_type"] == "application/pdf":
        record["pages"] = pdf_pages(path)
    else:
        record["rows"] = schedule["rows"]
        record["data_date_range"] = [min(schedule["data_year_counts"]),
                                     max(schedule["data_year_counts"])]
    return record


def manifest(items: dict, schedule: dict) -> dict:
    hashes = {paths.ITEM_CHUNKS: items["sha256"],
              **{paths.PROCESSED_DIR / name: sha for name, sha in schedule["outputs"].items()},
              paths.GLOSSARY: sha256_file(paths.GLOSSARY),
              paths.FOOD_WASTE_TABLE: items["inputs"]["manual_table_sha256"]}
    return {"manifest_version": 1,
            "built_at": datetime.now(ZoneInfo("Asia/Seoul")).isoformat(timespec="seconds"),
            "sources": [source_record(key, src, schedule) for key, src in SOURCES.items()],
            "outputs": {path.name: {"path": paths.relative(path), "sha256": sha}
                        for path, sha in hashes.items()},
            "not_included": [
                "data.go.kr recycling item API (~770 items): needs an API key; take a dated "
                "snapshot, never call it live",
                "schedules for Seoul 도봉구 and 강동구: not in the national CSV"]}


def counts(values: dict) -> str:
    return ", ".join(f"{name}: {n}" for name, n in values.items())


def items_section(i: dict) -> list[str]:
    passed = ", ".join(name for name, ok in i["checks"].items() if ok)
    return [
        f"## Item chunks (`{paths.relative(paths.ITEM_CHUNKS)}`)", "",
        f"- {i['chunks']} chunks: " + ", ".join(f"{k} {v}" for k, v in i["by_doc_type"].items()),
        "- IDs: UUIDv5 of source + chunker + span + text digest; old IDs kept as `legacy_id`. "
        f"All checks pass: {all(i['checks'].values())} ({passed})",
        f"- Text length: mean {i['chars_mean']} characters, max {i['chars_max']}",
        "- 9 `table` chunks transcribed by hand from the 2018 guide p.17-18 (food-waste tables), "
        "because PDF extraction loses the table layout. Source wording kept; editor search "
        "words are labelled.",
    ]


def schedule_section(s: dict) -> list[str]:
    repeated = ", ".join(f"{d} ({n})" for d, n in s["district_names_in_several_provinces"].items())
    return [
        f"## District schedule (`{paths.relative(paths.SCHEDULE_CSV)}`)", "",
        f"- {s['rows']} rows, {s['province_district_pairs']} districts in "
        f"{s['provinces']} provinces",
        f"- District names in several provinces (need the province): {repeated}",
        f"- Seoul districts with no data: {', '.join(s['seoul_districts_without_data'])}",
        f"- District names fixed: {s['district_name_fixes'] or 'none'}; "
        f"rows with district '없음': {s['rows_with_district_none']}",
        f"- Whole-district rows ('전체', '16개동'): {s['rows_whole_district']}; rows with area "
        f"notes ('… 제외'): {s['rows_with_area_notes']}; "
        f"rows without area names: {s['rows_without_area_names']}",
        f"- Rows with irregular days ('기타'): {s['rows_days_irregular']}; "
        f"rows without phone: {s['rows_without_phone']}",
        f"- Data dates by year: {counts(s['data_year_counts'])}",
        f"- Rows older than 1 year (flagged `오래된데이터`): {s['rows_stale']} "
        f"({100 * s['rows_stale'] / s['rows']:.0f}%); median age "
        f"{s['data_age_days_median']} days",
        f"- {s['area_names']} area names in `dong_lookup.json`; {s['ambiguous_area_names']} map "
        "to more than one district (the assistant must ask)",
        f"- {s['district_aliases']} romanised district aliases (`district_aliases.json`)",
        f"- Place types: {', '.join(f'{k} {v}' for k, v in s['place_types'].items())}",
    ]


def glossary_section(g: dict) -> list[str]:
    return [
        f"## Glossary (`{paths.relative(paths.GLOSSARY)}`)", "",
        f"- {g['terms']} terms in {'/'.join(GLOSSARY_LANGUAGES)}; bins valid: {g['bins_valid']}; "
        f"needs a native-speaker check: {', '.join(g['needs_native_check'])}",
    ]


def markdown(report: dict) -> str:
    lines = [
        "# Data quality report", "",
        f"Built {report['built_at']} by `python -m preprocess.build_all`.", "",
        *items_section(report["items"]), "",
        *schedule_section(report["schedule"]), "",
        *glossary_section(report["glossary"]), "",
        "## Not included", "",
        *[f"- {x}" for x in report["manifest"]["not_included"]], "",
    ]
    return "\n".join(lines)


def main() -> None:
    items = build_items.build()
    schedule = build_schedule.build()
    glossary = check_glossary()
    man = manifest(items, schedule)
    write_json(paths.MANIFEST, man)
    report = {"built_at": man["built_at"], "items": items, "schedule": schedule,
              "glossary": glossary, "manifest": man}
    write_json(paths.REPORT_DIR / "data_quality.json", report)
    text = markdown(report)
    (paths.REPORT_DIR / "data_quality.md").write_text(text, encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
