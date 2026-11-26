"""Romanisation, place matching and Korean particles."""
from __future__ import annotations

from rag.korean import fit_to_show, mentions_place, object_particle, romanize


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


def test_fit_to_show():
    """Item names the router really produced (experiments/results/)."""
    for name in ("피자 상자", "닭뼈", "만료된 약", "투명 PET 병"):
        assert fit_to_show(name), name
    for name in ("네일 pol리스 병", "바attery(번역 필요)", "계란 скор대", "닭骨头汤", ""):
        assert not fit_to_show(name), name
