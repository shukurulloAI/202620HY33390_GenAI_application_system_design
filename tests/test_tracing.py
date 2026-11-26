"""Retention of traces, errors and feedback."""
from __future__ import annotations

from datetime import date

from rag.files import append_jsonl, read_jsonl
from rag.tracing import prune


def test_prune_keeps_recent_traces_and_records(tmp_path):
    for day in ("2026-09-01", "2026-11-01", "2026-11-11"):
        append_jsonl(tmp_path / f"{day}.jsonl", {"trace_id": day})
    append_jsonl(tmp_path / "feedback.jsonl", {"trace_id": "a", "time": "2026-09-01T10:00:00+00:00"})
    append_jsonl(tmp_path / "feedback.jsonl", {"trace_id": "b", "time": "2026-11-10T10:00:00+00:00"})
    (tmp_path / "notes.txt").write_text("not a trace")

    removed = prune(30, tmp_path, today=date(2026, 11, 11))
    assert removed == {"trace_files": ["2026-09-01.jsonl"], "records": 1}
    assert sorted(p.name for p in tmp_path.iterdir()) == [
        "2026-11-01.jsonl", "2026-11-11.jsonl", "feedback.jsonl", "notes.txt"]
    assert [r["trace_id"] for r in read_jsonl(tmp_path / "feedback.jsonl")] == ["b"]


def test_prune_zero_keeps_everything(tmp_path):
    append_jsonl(tmp_path / "2020-01-01.jsonl", {})
    assert prune(0, tmp_path) == {"trace_files": [], "records": 0}
    assert (tmp_path / "2020-01-01.jsonl").exists()
