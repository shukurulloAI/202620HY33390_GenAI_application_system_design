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
