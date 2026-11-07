"""Evaluation cases (PLAN.md §7.1) and the developer probes, which share most of the schema."""
from __future__ import annotations

from pathlib import Path

from rag import paths
from rag.files import read_jsonl


def load_cases(path: Path) -> list[dict]:
    return read_jsonl(path)


def case_id(case: dict) -> str | None:
    return case.get("case_id") or case.get("probe_id")


def by_id(cases: list[dict]) -> dict:
    return {case_id(c): c for c in cases}


def default_cases() -> Path:
    """The dev split once it exists, otherwise the developer probes."""
    return paths.DEV_CASES if paths.DEV_CASES.exists() else paths.PROBES


def gold_chunks(case: dict) -> list[str]:
    """UUID chunk IDs or legacy IDs (e.g. item2018_0278); both are matched."""
    return case.get("expected_chunk_ids") or case.get("gold_chunks") or []
