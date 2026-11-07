"""Rank fusion and tokenisers (no index needed)."""
from __future__ import annotations

from rag.retrieve import rrf, tokenize_bigram
from tests.helpers import cand


def test_rrf_keeps_ranks():
    fused = rrf({"a": [cand("x", 1), cand("y", 2)], "b": [cand("y", 1)]})
    assert [c.chunk_id for c in fused] == ["y", "x"]
    assert fused[0].ranks == {"a": 2, "b": 1}


def test_bigram_tokens():
    assert tokenize_bigram("스티로폼 PET") == ["스티", "티로", "로폼", "pet"]
