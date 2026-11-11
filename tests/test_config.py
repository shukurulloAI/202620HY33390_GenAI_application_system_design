"""Configuration rules."""
from __future__ import annotations

from rag import paths
from rag.config import BASELINE, DEFAULT, PipelineConfig


def test_config_contract():
    assert DEFAULT.replace(rerank=False).rerank is False
    assert BASELINE.router is False and BASELINE.query_mode == "original"
    try:
        PipelineConfig(retrieval="magic")
    except ValueError:
        pass
    else:
        raise AssertionError("invalid retrieval accepted")


def test_ollama_address_comes_from_the_environment():
    import os
    import subprocess
    import sys

    def url(**env):
        return subprocess.run([sys.executable, "-c", "from rag import config; print(config.OLLAMA_URL)"],
                              capture_output=True, text=True, check=True, cwd=paths.ROOT,
                              env={k: v for k, v in {**os.environ, **env}.items() if v is not None},
                              ).stdout.strip()
    assert url(RAG_OLLAMA_URL=None) == "http://localhost:11434"            # unchanged default
    assert url(RAG_OLLAMA_URL="http://ollama:11434") == "http://ollama:11434"
