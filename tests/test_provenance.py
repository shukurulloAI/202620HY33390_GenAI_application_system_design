"""What a run records about the code it ran on."""
from __future__ import annotations

import shutil
import subprocess

import pytest

from eval import provenance
from rag.llm_client import CachedClient, FixtureClient, model_digest


@pytest.fixture
def repo(tmp_path, monkeypatch):
    if shutil.which("git") is None:
        pytest.skip("git not installed")

    def git(*args):
        subprocess.run(["git", *args], cwd=tmp_path, check=True, capture_output=True)

    git("init", "-q")
    git("config", "user.email", "test@example.com")
    git("config", "user.name", "test")
    (tmp_path / "rag").mkdir()
    (tmp_path / "rag" / "x.py").write_text("x = 1\n")
    git("add", ".")
    git("commit", "-qm", "init")
    monkeypatch.setattr(provenance.paths, "ROOT", tmp_path)
    return tmp_path


def test_run_output_does_not_make_the_tree_dirty(repo):
    assert provenance.git_dirty() is False
    for folder in ("eval/reports/my-run", "experiments/results/dev/E1"):
        (repo / folder).mkdir(parents=True)
        (repo / folder / "traces.jsonl").write_text("{}\n")
    assert provenance.git_dirty() is False


def test_a_code_change_makes_the_tree_dirty(repo):
    (repo / "rag" / "x.py").write_text("x = 2\n")
    snap = provenance.snapshot()
    assert snap["git_dirty"] is True and len(snap["git_commit"]) == 40


def test_only_ollama_models_have_a_digest():
    assert model_digest(FixtureClient()) is None
    assert model_digest(CachedClient(FixtureClient(), directory=None)) is None
