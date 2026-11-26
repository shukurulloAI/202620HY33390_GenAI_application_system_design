"""The place reader (rag/places.py) on spellings from the dev questions."""
from __future__ import annotations

import pytest

from rag.places import cyrillic, read_place


def test_cyrillic_follows_kontsevich():
    assert (cyrillic("부천"), cyrillic("영등포"), cyrillic("광명")) == ("пучхон", "ёндынпхо", "кванмён")


@pytest.mark.parametrize("question, district, dong", [
    ("Mình ở Guro-gu, thứ bảy có được bỏ rác thường không?", "구로구", None),
    ("Пучхон, Вонджон 2-дон: когда выносить вторсырьё?", "부천시", "원종2동"),
    ("Живу в Кэяну. Куда деть пустые банки?", "계양구", None),             # case ending, э/е
    ("Где выбросить сковородку? Я в Кванмёне.", "광명시", None),
    ("부천 송내1동인데 우유팩 버리는 법 알려주세요", "부천시", "송내1동"),
    ("live in yongsan, can i still put my bag out tonight??", "용산구", None),
    ("When can I put out the trash? I'm in Siheung.", "시흥시", None),
    ("I live in Mok 1-dong, Yangcheon-gu.", "양천구", "목1동"),
    ("Busanjin-gu, Jeonpo 1-dong: which days?", "부산진구", "전포1동"),
])
def test_reads_districts_and_neighbourhoods(question, district, dong):
    place = read_place(question)
    assert place and (place.district, place.dong) == (district, dong)


def test_no_false_places():
    assert read_place("Куда выбрасывать куриные кости?") is None    # кури = 구리 (Guri)
    assert read_place("남동생이 버리래요") is None                     # 남동 = 남동구
    assert read_place("How do I throw away a bottle?") is None
    assert read_place("Where do I put jung things?") is None       # 중구 needs its suffix


def test_ambiguous_places_are_left_to_ask():
    seo = read_place("When is food waste collected in Seo-gu?")
    assert seo.district == "서구" and len(seo.provinces) > 1         # the tool asks which city
    assert read_place("I live in Songjeong-dong. What days?") is None  # in 5 districts
