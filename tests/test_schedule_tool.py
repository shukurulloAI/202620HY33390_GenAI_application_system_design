"""Schedule lookup over the processed table, and its date helpers."""
from __future__ import annotations

from datetime import date

from rag.schedule_tool import default_table, resolve_day


def test_schedule_lookup_and_dates():
    table = default_table()
    ok = table.lookup("성동구", dong="행당동", waste_type="food")
    assert ok.status == "OK" and ok.rows[0].rules["food"].days == [0, 2, 4]
    assert table.lookup("중구").status == "CLARIFY"
    assert table.lookup("강동구").status == "NO_DATA"
    wed = date(2026, 11, 4)
    assert resolve_day("tonight", wed).date == wed
    assert resolve_day("sun", wed).date == date(2026, 11, 8)
    assert resolve_day("none", wed) is None


def test_schedule_area_match():
    table = default_table()
    for dong in ("상계6동", "상계7동", "상계6.7동", "상계6·7동"):      # same zone, any spelling
        result = table.lookup("노원구", dong=dong)
        assert (result.status, result.matched_on, len(result.rows)) == ("OK", "area", 1), dong
        assert "상계6동" in result.rows[0].area_names
    for district, dong in (("사상구", "주례2동"), ("영도구", "청학2동"),
                           ("부산진구", "양정1동"), ("수성구", "수성2가동")):
        assert table.lookup(district, dong=dong).matched_on == "area", dong
    # An exact name wins over names that only share the base (상계1동, 상계2동, ...).
    assert len(table.lookup("노원구", dong="상계1동").rows) == 1
    assert len(table.lookup("노원구", dong="상계동").rows) > 1


def test_district_rows_same_names_as_lookup():
    table = default_table()

    def ids(*args):
        return {r.row_id for r in table.district_rows(*args)}

    assert ids("성동구") == ids("seongdong-gu") == ids("성동") == ids("서울특별시 성동구")
    assert ids("성동구") == {r.row_id for r in table.lookup("성동구").rows}
    assert len({table.by_id[i].province for i in ids("중구")}) == 5
    assert {table.by_id[i].province for i in ids("중구", "부산")} == {"부산광역시"}
    assert not ids("강동구")
