"""Per-request traces (PLAN.md §4.11): one JSON line per question in traces/<date>.jsonl.

Traces, errors.jsonl and feedback.jsonl hold the users' own words, so they are kept for
TRACE_RETENTION_DAYS (environment variable RAG_TRACE_RETENTION_DAYS; 0 keeps everything)
and then deleted by prune(), which the website runs at start (rag/service.py).
"""
from __future__ import annotations

import os
import re
import time
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

from rag import paths
from rag.files import append_jsonl, read_jsonl, write_jsonl

TRACE_RETENTION_DAYS = int(os.environ.get("RAG_TRACE_RETENTION_DAYS", "30"))
_DAILY = re.compile(r"^(\d{4}-\d{2}-\d{2})\.jsonl$")
_LOGS = ("errors.jsonl", "feedback.jsonl")      # one record per line, each with a "time"


@contextmanager
def timed(timings: dict[str, float], name: str) -> Iterator[None]:
    """Record how long the block took, in seconds, as timings[name]."""
    start = time.perf_counter()
    yield
    timings[name] = round(time.perf_counter() - start, 3)


def write_trace(trace: dict) -> None:
    append_jsonl(paths.TRACE_DIR / f"{trace['time'][:10]}.jsonl", trace)


def prune(days: int = TRACE_RETENTION_DAYS, directory: Path | None = None,
          today: date | None = None) -> dict:
    """Delete daily trace files, and error and feedback records, older than `days`.
    Returns what was removed. days <= 0 keeps everything."""
    directory = directory or paths.TRACE_DIR
    removed = {"trace_files": [], "records": 0}
    if days <= 0 or not directory.exists():
        return removed
    cutoff = (today or datetime.now(UTC).date()) - timedelta(days=days)
    for path in sorted(directory.glob("*.jsonl")):
        match = _DAILY.match(path.name)
        if match and date.fromisoformat(match[1]) < cutoff:
            path.unlink()
            removed["trace_files"].append(path.name)
    for name in _LOGS:
        path = directory / name
        if not path.exists():
            continue
        rows = read_jsonl(path)
        kept = [r for r in rows if str(r.get("time", ""))[:10] >= cutoff.isoformat()]
        if len(kept) < len(rows):
            write_jsonl(path, kept)
            removed["records"] += len(rows) - len(kept)
    return removed
