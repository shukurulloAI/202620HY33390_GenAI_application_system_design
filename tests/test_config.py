"""Configuration rules."""
from __future__ import annotations

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
