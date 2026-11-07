"""Per-request traces (PLAN.md §4.11): one JSON line per question in traces/<date>.jsonl."""
from __future__ import annotations

import time
from collections.abc import Iterator
from contextlib import contextmanager

from rag import paths
from rag.files import append_jsonl


@contextmanager
def timed(timings: dict[str, float], name: str) -> Iterator[None]:
    """Record how long the block took, in seconds, as timings[name]."""
    start = time.perf_counter()
    yield
    timings[name] = round(time.perf_counter() - start, 3)


def write_trace(trace: dict) -> None:
    append_jsonl(paths.TRACE_DIR / f"{trace['time'][:10]}.jsonl", trace)
