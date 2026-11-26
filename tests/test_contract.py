"""The answer contract the website relies on (rag/contract.py, docs/answer_schema.json)."""
from __future__ import annotations

import copy
import json

import pytest

from rag.contract import (
    SCHEMA_FILE,
    ContractError,
    answer_bins,
    check,
    first_bin,
    json_schema,
    problems,
)
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
    (lambda a: a["items"][0].update(bin="plastic"), "unknown bin"),
    (lambda a: a.update(bin="종이"), "bin"),                  # 1.0 field: gone in 2.0
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
    abstain["items"] = [{"item": "box", "bin": "종이", "bin_en": "paper", "how_to_prepare": [],
                         "citations": [1]}]
    assert any("lists items" in p for p in problems(abstain))
    clarify = _answer("CLARIFY")
    clarify["clarify"] = None
    assert any("without a question" in p for p in problems(clarify))


def test_bins_are_read_from_items_and_from_saved_1_0_answers():
    two = {"items": [{"bin": "종이"}, {"bin": "비닐"}]}
    assert answer_bins(two) == ["종이", "비닐"] and first_bin(two) == "종이"
    assert answer_bins({"bin": "고철", "items": []}) == ["고철"]       # a 1.0 trace
    assert first_bin({"items": []}) == "" and answer_bins({"bin": ""}) == []
