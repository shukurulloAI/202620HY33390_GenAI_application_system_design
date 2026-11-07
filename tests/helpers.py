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
