"""The answer contract the website relies on (rag/contract.py, docs/answer_schema.json)."""
from __future__ import annotations

import copy
import json

import pytest

from rag.contract import SCHEMA_FILE, ContractError, check, json_schema, problems
from rag.service import examples


def test_schema_file_is_up_to_date():
    """Changing a model means regenerating the schema: python -m rag.contract."""
    assert json.loads(SCHEMA_FILE.read_text(encoding="utf-8")) == json_schema()


def test_recorded_examples_fit_and_cover_every_status():
    recorded = examples()
    for example in recorded:
        assert problems(example["answer"]) == [], example["name"]
    assert {e["answer"]["status"] for e in recorded} == {
        "ANSWER", "CLARIFY", "INSUFFICIENT_CONTEXT", "OUT_OF_SCOPE"}


def _answer(status: str) -> dict:
    return copy.deepcopy(next(e["answer"] for e in examples() if e["answer"]["status"] == status))


@pytest.mark.parametrize("change, expected", [
    (lambda a: a.pop("trace_id"), "trace_id"),
    (lambda a: a.update(extra_field=1), "extra_field"),
    (lambda a: a.update(status="MAYBE"), "status"),
    (lambda a: a.update(bin="plastic"), "unknown bin"),
    (lambda a: a.update(citations=[]), "cites nothing"),
])
def test_broken_answers_are_caught(change, expected):
    answer = _answer("ANSWER")
    change(answer)
    with pytest.raises(ContractError, match=expected):
        check(answer)


def test_rules_between_fields():
    abstain = _answer("INSUFFICIENT_CONTEXT")
    abstain["handoff"] = None
    assert any("handoff" in p for p in problems(abstain))
    abstain = _answer("INSUFFICIENT_CONTEXT")
    abstain["bin"] = "종이"
    assert any("names a bin" in p for p in problems(abstain))
    clarify = _answer("CLARIFY")
    clarify["clarify"] = None
    assert any("without a question" in p for p in problems(clarify))
