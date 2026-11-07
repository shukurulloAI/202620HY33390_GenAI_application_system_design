"""Handoff sentence."""
from __future__ import annotations

from rag.handoff import korean_sentence


def test_handoff_sentence():
    s = korean_sentence("우산", None, "성동구", "행당동", asks_schedule=False)
    assert s == "안녕하세요. 우산을 어떻게 버려야 하는지 알고 싶습니다. 저는 성동구 행당동에 살고 있습니다."


def test_handoff_sentence_uses_own_words_without_a_korean_name():
    s = korean_sentence("", None, None, None, asks_schedule=False,
                        item_asked="nail polish bottles")
    assert s == "안녕하세요. 이 물건을 어떻게 버려야 하는지 알고 싶습니다: nail polish bottles."
