"""Pipeline.run end to end, with a scripted LLM, real chunks and the real schedule table
(no index, no models, no Ollama)."""
from __future__ import annotations

import json
from functools import lru_cache

import pytest

from rag import paths
from rag.config import PipelineConfig
from rag.files import read_jsonl
from rag.pipeline import Pipeline
from rag.retrieve import Candidate
from rag.schedule_tool import default_table
from tests.helpers import CharCounter, FakeRetriever, ScriptedLLM

EGGSHELL = "item2018_0010"          # 계란껍질 -> 종량제봉투 (2018 guide, p.28)


@lru_cache(maxsize=1)
def chunks_by_legacy_id():
    return {c["metadata"].get("legacy_id"): c for c in read_jsonl(paths.ITEM_CHUNKS)}


def candidate(legacy_id, rerank_score):
    c = chunks_by_legacy_id()[legacy_id]
    return Candidate(c["id"], c["text"], dict(c["metadata"]), 0.0, 1, "fake",
                     ranks={"fake": 1}, rerank_score=rerank_score)


def route(**fields):
    base = {"intent": "item", "item": "", "item_ko": "", "ko_query": "", "district": "",
            "dong": "", "waste_type": "none", "day_ref": "none", "negation": False, "lang": "en"}
    return json.dumps({**base, **fields}, ensure_ascii=False)


def answer(**fields):
    base = {"status": "ANSWER", "bin": "", "bin_en": "", "how_to_prepare": [],
            "answer_text": "", "citations": [], "missing": ""}
    return json.dumps({**base, **fields}, ensure_ascii=False)


EGG_ROUTE = route(item="eggshells", item_ko="계란껍질", ko_query="계란껍질 분리배출 방법")
EGG_ANSWER = answer(bin="종량제봉투", bin_en="general waste bag",
                    answer_text="Eggshells go in the general waste bag [1].", citations=[1])


@pytest.fixture(scope="module")
def table():
    return default_table()


def run(replies, candidates, table, question="Where do eggshells go?", **inputs):
    llm = ScriptedLLM(*replies)
    retriever = FakeRetriever(candidates)
    pipeline = Pipeline(PipelineConfig(), llm, write_traces=False, retriever=retriever,
                        schedule=table, counter=CharCounter())
    trace = pipeline.run(question, **inputs)
    assert trace["contract_problems"] == []
    return trace, llm, retriever


def test_item_answer(table):
    trace, llm, retriever = run([EGG_ROUTE, EGG_ANSWER], [candidate(EGGSHELL, 0.9)], table)
    a = trace["answer"]
    assert (a["status"], a["bin"]) == ("ANSWER", "종량제봉투")
    assert trace["gate"]["item"] == "answer" and len(llm.calls) == 2
    assert set(retriever.queries[0]) == {"original", "rewrite"}
    assert trace["evidence"][0]["ref"] == chunks_by_legacy_id()[EGGSHELL]["id"]


def test_gate_abstains_without_calling_the_generator(table):
    trace, llm, _ = run([EGG_ROUTE], [candidate(EGGSHELL, 0.05)], table)   # tau is 0.15
    assert trace["answer"]["status"] == "INSUFFICIENT_CONTEXT" and trace["answer"]["bin"] == ""
    assert trace["gate"]["item"] == "abstain" and len(llm.calls) == 1   # the router only
    assert trace["llm"] is None


def test_out_of_scope_is_refused(table):
    trace, llm, retriever = run([route(intent="out_of_scope")], [], table,
                                question="What is the capital of France?")
    assert trace["answer"]["status"] == "OUT_OF_SCOPE" and len(llm.calls) == 1
    assert retriever.queries == []


def test_unusable_generator_output_is_downgraded(table):
    trace, _, _ = run([EGG_ROUTE, "not json"], [candidate(EGGSHELL, 0.9)], table)
    assert trace["answer"]["status"] == "INSUFFICIENT_CONTEXT" and trace["answer"]["bin"] == ""
    assert trace["checks"]["validation"]["downgraded"]


def test_a_bin_the_cited_chunk_does_not_state_is_refused(table):
    wrong = answer(bin="음식물", bin_en="food waste", answer_text="Food waste [1].", citations=[1])
    trace, _, _ = run([EGG_ROUTE, wrong], [candidate(EGGSHELL, 0.9)], table)
    assert trace["answer"]["status"] == "INSUFFICIENT_CONTEXT" and trace["answer"]["bin"] == ""


def test_router_failure_falls_back_to_the_question(table):
    trace, _, retriever = run(["no json", "still no json", EGG_ANSWER],
                              [candidate(EGGSHELL, 0.9)], table)
    assert trace["route"]["valid"] is False and set(retriever.queries[0]) == {"original"}
    assert trace["answer"]["status"] == "ANSWER"


COMBINED_Q = "계란껍질은 어디에 버려요? 그리고 성동구 행당동 음식물 쓰레기는 언제 버려요?"
COMBINED_ROUTE = route(intent="both", item="계란껍질", item_ko="계란껍질",
                       ko_query="계란껍질 분리배출 방법", district="성동구", dong="행당동",
                       waste_type="food", lang="ko")


def test_combined_question_schedule_is_written_by_code(table):
    trace, llm, _ = run([COMBINED_ROUTE, EGG_ANSWER], [candidate(EGGSHELL, 0.9)], table,
                        question=COMBINED_Q, lang="ko", district="성동구", dong="행당동")
    a = trace["answer"]
    assert a["status"] == "ANSWER" and a["bin"] == "종량제봉투"
    assert "Do not mention days" in llm.calls[1]["prompt"]       # the generator sees no days
    assert {e["kind"] for e in trace["evidence"]} == {"item", "schedule"}
    assert len(llm.calls) == 2                                    # Korean: nothing to translate


def test_combined_question_keeps_the_schedule_when_the_item_fails(table):
    unsure = answer(status="INSUFFICIENT_CONTEXT", missing="not in the evidence")
    trace, _, _ = run([COMBINED_ROUTE, unsure], [candidate(EGGSHELL, 0.9)], table,
                      question=COMBINED_Q, lang="ko", district="성동구", dong="행당동")
    assert trace["answer"]["status"] == "ANSWER" and trace["answer"]["bin"] == ""
    assert trace["gate"]["item"] == "abstain"
    assert "schedule answered alone" in trace["gate"]["reasons"][-1]
    assert {e["kind"] for e in trace["evidence"]} == {"schedule"}
