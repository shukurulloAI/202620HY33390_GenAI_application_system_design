"""Stand-ins shared by the tests."""
from __future__ import annotations

from types import SimpleNamespace

from rag.retrieve import Candidate


def cand(cid, rank, score=None, **meta):
    return Candidate(cid, meta.pop("text", ""), meta, 0.0, rank, "t", rerank_score=score)


class StubLLM:
    model_id = "stub"

    def __init__(self, text):
        self.text, self.calls = text, []

    def generate(self, **kwargs):
        self.calls.append(kwargs)
        return SimpleNamespace(text=self.text, model_id=self.model_id, done_reason="stop")


class ScriptedLLM:
    """Replies in order, one per generate() call; records every call."""
    model_id = "scripted"

    def __init__(self, *replies):
        self.replies, self.calls = list(replies), []

    def generate(self, **kwargs):
        from rag.llm_client import LLMResult
        self.calls.append(kwargs)
        if not self.replies:
            raise AssertionError(f"unexpected LLM call {len(self.calls)}")
        return LLMResult(text=self.replies.pop(0), model_id=self.model_id, done_reason="stop")


class CharCounter:
    """Token counter without a tokenizer download."""
    tokenizer_id, exact = "chars", False

    def count(self, text):
        return len(text)


class FakeRetriever:
    """Returns fixed candidates (a full trace record, no index); records the queries."""
    name, collection = "fake", "fake_collection"

    def __init__(self, candidates):
        self.candidates, self.queries = candidates, []

    def search(self, queries, rerank_queries=None, doc_types=None, item_names=None):
        self.queries.append(dict(queries))
        return (list(self.candidates), self.candidates[:5],
                {"queries": queries, "timings": {"retrieve_s": 0.0}, "lists": {}})
