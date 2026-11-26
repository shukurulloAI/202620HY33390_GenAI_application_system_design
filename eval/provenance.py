"""What a result file records so a run can be traced back to the code and data behind it."""
from __future__ import annotations

import subprocess

from rag import paths

# Anything here changing means `git_commit` alone no longer reproduces the run.
TRACKED = ("rag", "preprocess", "ingest", "eval", "experiments/*.py", "experiments/configs",
           "data/processed", "data/manual")
# Run output inside the tracked folders. A run writes here before it records git_dirty, so
# counting these made every record "dirty" (all reports up to 2026-11-11, docs/REPORT.md §8.1).
OUTPUTS = ("eval/reports", "experiments/results")


def _git(*args: str) -> str | None:
    try:
        return subprocess.run(["git", *args], cwd=paths.ROOT, text=True, capture_output=True,
                              check=True).stdout
    except (OSError, subprocess.CalledProcessError):
        return None


def git_commit() -> str | None:
    out = _git("rev-parse", "HEAD")
    return out.strip() if out else None


def dirty_pathspec() -> list[str]:
    return [*TRACKED, *(f":(exclude){p}" for p in OUTPUTS)]


def git_dirty() -> bool | None:
    """True when code or data that a run depends on differs from `git_commit`."""
    out = _git("status", "--porcelain", "--", *dirty_pathspec())
    return None if out is None else bool(out.strip())


def snapshot() -> dict:
    """Take this before a run writes anything: the code that ran, not the code after it."""
    return {"git_commit": git_commit(), "git_dirty": git_dirty()}
