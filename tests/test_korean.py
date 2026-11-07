"""Romanisation, place matching and Korean particles."""
from __future__ import annotations

from rag.korean import mentions_place, object_particle, romanize


def test_romanize_and_place_mentions():
    assert romanize("성동구") == "seongdonggu"
    assert romanize("종로구") == "jongnogu"          # ㅇ + ㄹ -> n
    assert romanize("신림동") == "sillimdong"        # ㄴ + ㄹ -> ll
    assert mentions_place("I live in Seongdong-gu", "성동구")
    assert mentions_place("I live in Jung-gu", "중구")
    assert not mentions_place("I live in Jungnang-gu", "중구")
    assert not mentions_place("When is food waste collected?", "성동구")


def test_object_particle():
    assert object_particle("우산") == "을" and object_particle("닭뼈") == "를"
