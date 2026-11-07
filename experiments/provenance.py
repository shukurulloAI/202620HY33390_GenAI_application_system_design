"""What a result file records so a run can be traced back to the code and data behind it."""
from __future__ import annotations

import subprocess

from rag import paths

# Anything here changing means `git_commit` alone no longer reproduces the run.
TRACKED = ("rag", "preprocess", "ingest", "eval", "experiments/*.py", "experiments/configs",
           "data/processed", "data/manual")


def _git(*args: str) -> str | None:
    try:
        return subprocess.run(["git", *args], cwd=paths.ROOT, text=True, capture_output=True,
                              check=True).stdout
    except (OSError, subprocess.CalledProcessError):
        return None


def git_commit() -> str | None:
    out = _git("rev-parse", "HEAD")
    return out.strip() if out else None


def git_dirty() -> bool | None:
    out = _git("status", "--porcelain", "--", *TRACKED)
    return None if out is None else bool(out.strip())
