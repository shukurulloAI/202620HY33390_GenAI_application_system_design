"""Parsing of the generator's JSON."""
from __future__ import annotations

import json

from rag.generate import parse_answer


def test_parse_answer_citations():
    text = json.dumps({"status": "ANSWER", "bin": "종이", "bin_en": "", "how_to_prepare": [],
                       "answer_text": "Paper [1] [7].", "citations": [1, 9], "missing": ""})
    answer, checks = parse_answer(text, n_evidence=2)
    assert answer["citations"] == [1] and sorted(checks["invalid_citations"]) == [7, 9]
    answer, checks = parse_answer("not json", 2)
    assert answer["status"] == "INVALID_OUTPUT" and not checks["json_valid"]


def test_v6_items_and_v5_output_have_the_same_shape():
    from rag.generate import ANSWER_SCHEMA, ANSWER_SCHEMA_V6, answer_schema
    assert answer_schema("v5") is ANSWER_SCHEMA and answer_schema("v6") is ANSWER_SCHEMA_V6
    v6 = json.dumps({"status": "ANSWER", "answer_text": "Rod [1], balls [2].", "citations": [1, 2],
                     "missing": "", "items": [
                         {"item": "fishing rod", "bin": "대형폐기물", "how_to_prepare": [],
                          "citations": [1]},
                         {"item": "golf balls", "bin": "종량제봉투", "how_to_prepare": ["bag them"],
                          "citations": [2, 9]}]})
    answer, checks = parse_answer(v6, 2)
    assert [i["bin"] for i in answer["items"]] == ["대형폐기물", "종량제봉투"]
    assert answer["items"][1]["citations"] == [2] and 9 in checks["invalid_citations"]
    assert (answer["bin"], answer["bin_en"]) == ("대형폐기물", "bulky waste (disposal sticker required)")
    v5 = json.dumps({"status": "ANSWER", "bin": "종이", "bin_en": "paper", "how_to_prepare": ["fold"],
                     "answer_text": "Paper [1].", "citations": [1], "missing": ""})
    answer, _ = parse_answer(v5, 1)
    assert answer["items"] == [{"item": "", "bin": "종이", "how_to_prepare": ["fold"],
                                "citations": [1]}]
