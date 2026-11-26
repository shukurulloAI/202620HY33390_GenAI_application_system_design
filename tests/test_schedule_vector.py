"""E4 vector variants, with a stub in place of Qdrant."""
from __future__ import annotations

from types import SimpleNamespace

from rag.schedule_tool import default_table
from rag.schedule_vector import ScheduleVectorSearch
from tests.helpers import cand


def vector_search(mode, table):
    """The search logic with a stub in place of Qdrant, which returns rows of two districts."""
    calls = []
    top = [r for r in table.rows if r.district == "마포구"][:1] + table.lookup("성동구").rows

    def search(text, k, where=None):
        calls.append((text, k, where))
        keep = [r for r in top if not where or r.district in where["district"]]
        return [cand(r.row_id, i, row_id=r.row_id) for i, r in enumerate(keep, 1)][:k]

    engine = ScheduleVectorSearch.__new__(ScheduleVectorSearch)
    engine.table, engine.mode, engine.k_retrieve = table, mode, 20
    engine.dense = SimpleNamespace(search=search)
    return engine, calls


def test_vector_variants_choose_rows():
    table = default_table()
    wanted = {r.row_id for r in table.lookup("성동구").rows}

    engine, calls = vector_search("vector", table)
    result = engine.search("언제 버려요", "seongdong-gu", dong="행당1동")
    assert calls[0][0] == "성동구 행당1동 언제 버려요"           # canonical name in the query text
    assert calls[0][2] is None
    assert result.rows[0].district == "마포구"                 # no filter: the wrong district stays

    engine, calls = vector_search("postfilter", table)
    result = engine.search("언제 버려요", "성동구")
    assert calls[0][1] == 20 and {r.row_id for r in result.rows} == wanted

    engine, calls = vector_search("prefilter", table)
    result = engine.search("언제 버려요", "성동구")
    assert calls[0][2] == {"province": ["서울특별시"], "district": ["성동구"]}
    assert {r.row_id for r in result.rows} == wanted

    for mode in ("postfilter", "prefilter"):
        engine, calls = vector_search(mode, table)
        result = engine.search("언제 버려요", "강동구")           # no such rows, so nothing to show
        assert result.status == "NO_DATA" and not result.rows
