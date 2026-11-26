"""Claim splitting and the judge step of eval/answer_judge.py (fake judge, no Ollama)."""
from __future__ import annotations

import json

from eval.answer_judge import claims, judge_trace
from eval.metrics import score
from rag.llm_client import LLMResult


def test_claims_split_sentences_and_lines_and_keep_their_marks():
    text = ("Put the receipt in the general waste bag [1]. Remove personal details first [1, 2]."
            " Check your district rules. Rinse it.[3-4]")
    got = claims(text)
    assert [c["cited"] for c in got] == [[1], [1, 2], [], [3, 4]]
    assert got[0]["text"] == "Put the receipt in the general waste bag."
    # A mark after the full stop belongs to the sentence before it; CJK stops and lines split.
    assert claims("It goes in the bag. [2]") == [{"text": "It goes in the bag.", "cited": [2]}]
    assert [c["cited"] for c in claims("放进垃圾袋[1]。周一收集[2]。")] == [[1], [2]]
    assert [c["cited"] for c in claims("Bag [1]\nBox [2]")] == [[1], [2]]


class _Judge:
    model_id = "fake"

    def __init__(self, replies):
        self.replies, self.prompts = list(replies), []

    def generate(self, *, system, prompt, **_):
        self.prompts.append(prompt)
        return LLMResult(text=self.replies.pop(0), model_id="fake")


def _yes(ok: bool) -> str:
    return json.dumps({"reason": "", "supported": ok})


def _trace(llm_text: str, shown: str | None = None, citations=()) -> dict:
    return {"case_id": "c1",
            "llm": {"raw_output": json.dumps({"answer_text": llm_text})},
            "answer": {"status": "ANSWER", "answer_text": shown or llm_text,
                       "citations": list(citations)}}


def test_claims_come_from_the_llm_text_and_see_only_their_sources():
    trace = _trace("Bag [1]. Help desk [2]. Closes at 20:00. Renewals unlimited [3].",
                   shown="Bag [1]. Help desk [2]. Closes at 20:00. Renewals unlimited [3].\n"
                         "Recycling: Tue, Thu [6]",              # written by code: not a claim
                   citations=[{"n": 1, "text": "SOURCE-A"}, {"n": 2, "text": "SOURCE-D"},
                              {"n": 6, "text": "ROW"}])
    judge = _Judge([_yes(True), _yes(False)])
    result = judge_trace(judge, trace)
    assert "SOURCE-A" in judge.prompts[0] and "SOURCE-D" not in judge.prompts[0]
    # [3] has no source: unsupported without a judge call. Lesson 6's example numbers:
    # precision 1/3 (cited claims), coverage 1/4 (all claims).
    assert (result["supported"], result["cited"], result["claims_judged"]) == (1, 3, 4)
    assert result["uncited"] == 1 and len(judge.prompts) == 2


def test_unparsed_reply_is_failed_not_unsupported_and_refusals_are_skipped():
    result = judge_trace(_Judge(["not json"]), _trace("Bag [1].", citations=[{"n": 1, "text": "S"}]))
    assert (result["cited"], result["claims_judged"], result["failed"]) == (0, 0, 1)
    assert judge_trace(_Judge([]), {"answer": {"status": "INSUFFICIENT_CONTEXT"}}) is None


def test_judged_counts_are_pooled_in_the_report():
    cases = [{"case_id": "c1", "slice": "item_direct", "lang": "en", "expected_behavior": "answer"}]
    trace = {"case_id": "c1", "answer": {"status": "ANSWER", "bin": "", "citations": []},
             "timings": {"total_s": 1.0}}
    labels = {"c1": {"cited": 3, "supported": 1, "claims_judged": 4}}
    o = score([trace], cases, labels)["overall"]
    assert (o["citation_precision"]["rate"], o["citation_coverage"]["rate"]) == (0.333, 0.25)

