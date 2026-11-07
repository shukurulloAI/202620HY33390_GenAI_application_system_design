"""Cleaning of the district table."""
from __future__ import annotations

from collections import defaultdict

from preprocess.build_schedule import clean_areas, schedule_chunk


def test_area_number_lists():
    def names(raw):
        return clean_areas(raw)[0]

    assert names("휘경1,2동") == ["휘경1동", "휘경2동"]
    assert names("상계6.7동") == ["상계6동", "상계7동"]
    assert names("청학1·2동+남항동") == ["청학1동", "청학2동", "남항동"]
    assert names("양정1ㆍ2동") == ["양정1동", "양정2동"]
    assert names("수성1,2.3,4가동") == ["수성1가동", "수성2가동", "수성3가동", "수성4가동"]
    assert names("중앙로1,2가") == ["중앙로1가", "중앙로2가"]
    assert names("강림1.2리") == ["강림1리", "강림2리"]
    assert names("제2,3공단") == ["제2공단", "제3공단"]
    assert names("대연1동,2동,3") == ["대연1동", "대연2동", "대연3동"]   # stem carried over
    assert names("행당동,2") == ["행당동", "2"]                          # no number to replace


def test_area_placeholders_mean_whole_district():
    for raw in ("없음", "해당없음", "전체"):
        assert clean_areas(raw) == ([], [], True), raw


def test_schedule_chunk_text():
    row = defaultdict(str, {"시도명": "서울특별시", "시군구명": "종로구", "관리번호": "1"})
    chunk = schedule_chunk(row)
    assert chunk["text"].splitlines()[:2] == ["[서울특별시 종로구] 쓰레기 배출 안내", "대상 지역: 전체"]
    row["관리구역명"] = "1권역"
    assert schedule_chunk(row)["text"].startswith("[서울특별시 종로구 1권역] ")
    assert "stale" not in chunk["metadata"]            # would tie the corpus hash to the build date
