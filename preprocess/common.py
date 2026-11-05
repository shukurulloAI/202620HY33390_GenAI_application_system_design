"""
Shared helpers for preprocessing (PLAN.md §3, §4.1; Lesson 3: manifest, stable IDs).

Every raw source is registered here once, with what we know about it. Document IDs
are UUIDv5 of the source URI; chunk IDs are UUIDv5 of
    doc_id | source sha256 | chunker_id | span | text digest
so they never depend on loop order (Lesson 3), and change only when the source,
the chunking policy, the location or the text changes.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import unicodedata
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "Data"
OUT = Path(__file__).resolve().parent

# Fixed namespace for document and chunk IDs. Never change it: every ID would change.
ID_NAMESPACE = uuid.UUID("3b6a2f40-9c1e-5d7a-8f2b-4e6c9a1d0b57")

SOURCES = {
    "guide2018": {
        "path": DATA / "item_guides" / "moe_recycling_guideline_2018.pdf",
        "source_uri": "data://item_guides/moe_recycling_guideline_2018.pdf",
        "media_type": "application/pdf",
        "title": "재활용품 분리배출 가이드라인",
        "publisher": "환경부 (Ministry of Environment)",
        "source_year": 2018, "effective_date": "2018",
        "parser_id": "pdfplumber-item-guide-v1 (item_guide/build_item_chunks.py)",
    },
    "annex2026": {
        "path": DATA / "item_guides" / "moe_separation_directive_annex1_2026.pdf",
        "source_uri": "data://item_guides/moe_separation_directive_annex1_2026.pdf",
        "media_type": "application/pdf",
        "title": "분리수거 등에 관한 지침 [별표 1] (기후에너지환경부훈령 제18호)",
        "publisher": "기후에너지환경부 (Ministry of Climate, Energy and Environment)",
        "source_year": 2026, "effective_date": "2026-01-01",
        "parser_id": "pdfplumber-annex-table-v1 (item_guide/build_item_chunks.py)",
    },
    "schedule_csv": {
        "path": DATA / "korean_waste_policies.csv",
        "source_uri": "data://korean_waste_policies.csv",
        "media_type": "text/csv; charset=cp949",
        "title": "생활쓰레기 배출정보 (district household-waste collection data)",
        "publisher": "공공데이터포털 data.go.kr (data from each 시군구)",
        "source_year": None, "effective_date": None,       # per-row 데이터기준일자
        "parser_id": "csv-schedule-v1 (preprocess/build_schedule.py)",
    },
}


def nfc(text: str) -> str:
    return unicodedata.normalize("NFC", text or "").strip()


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def doc_id(source_key: str) -> str:
    return str(uuid.uuid5(ID_NAMESPACE, SOURCES[source_key]["source_uri"]))


def chunk_id(source_key: str, source_sha: str, chunker_id: str, span: str, text: str) -> str:
    key = "|".join([doc_id(source_key), source_sha, chunker_id, span, sha256_text(text)[:16]])
    return str(uuid.uuid5(ID_NAMESPACE, key))


def git_added_date(path: Path) -> str | None:
    """Date the file was first committed (a stand-in for the download date)."""
    try:
        out = subprocess.run(["git", "log", "--diff-filter=A", "--format=%aI", "--", str(path)],
                             cwd=ROOT, capture_output=True, text=True, check=True).stdout
        dates = out.split()
        return dates[-1][:10] if dates else None
    except Exception:
        return None


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def write_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
