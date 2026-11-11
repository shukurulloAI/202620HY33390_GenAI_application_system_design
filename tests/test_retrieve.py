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


class FakeCrossEncoder:
    """Scores a (query, text) pair from a table; records how it was called."""

    def __init__(self, table):
        self.table, self.calls = table, []

    def predict(self, pairs, batch_size=16, show_progress_bar=False):
        self.calls.append(list(pairs))
        return [self.table.get(pair, 0.0) for pair in pairs]


def fake_reranker(table):
    from rag.retrieve import Reranker
    reranker = Reranker.__new__(Reranker)          # no model download
    reranker.model, reranker.name = FakeCrossEncoder(table), "rerank:fake"
    return reranker


def test_rerank_keeps_the_best_score_over_queries():
    a, b = cand("a", 1, text="A"), cand("b", 2, text="B")
    reranker = fake_reranker({("q1", "A"): 0.2, ("q1", "B"): 0.9,
                              ("q2", "A"): 0.95, ("q2", "B"): 0.1})
    out = reranker.rerank(["q1", "q2"], [a, b])
    assert [c.chunk_id for c in out] == ["a", "b"]
    assert [c.rerank_score for c in out] == [0.95, 0.9]
    assert out[0].ranks["fused"] == 1 and out[1].rank == 2


def test_rerank_scores_each_distinct_pair_once():
    reranker = fake_reranker({("q", "A"): 0.5})
    out = reranker.rerank(["q", "q", ""], [cand("a", 1, text="A")])
    assert out[0].rerank_score == 0.5
    assert sum(len(call) for call in reranker.model.calls) == 1


def test_rerank_turns_logits_into_probabilities():
    reranker = fake_reranker({("q", "A"): 2.0, ("q", "B"): -2.0})
    out = reranker.rerank(["q"], [cand("a", 1, text="A"), cand("b", 2, text="B")])
    assert out[0].rerank_score == 0.8808 and out[1].rerank_score == 0.1192


def test_bm25_only_retrieval_on_the_real_corpus():
    from rag.config import PipelineConfig
    from rag.retrieve import ItemRetriever
    cfg = PipelineConfig(retrieval="bm25", rerank=False, name_search=False, router=False)
    retriever = ItemRetriever(cfg)                       # no dense index needed
    candidates, selected, record = retriever.search({"original": "계란껍질 버리는 법"})
    assert "계란껍질" in [c.metadata.get("item") for c in selected]   # (알껍질, a table row, is 1st)
    assert selected[0].ranks == {"bm25/original": 1}     # single list: its own ranks
    assert len(selected) == cfg.k_final and record["rerank_queries"] is None
    _, nothing, _ = retriever.search({"original": "eggshells"})   # no shared token
    assert nothing == []
