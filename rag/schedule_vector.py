"""
Vector retrieval of schedule rows, for E4 only (PLAN.md §6, Lesson 5).

The system answers schedule questions with the typed lookup (rag/schedule_tool.py). These
variants exist to measure what that choice is worth:

    vector      search all district chunks, no location filter
    postfilter  search the top k_retrieve, then keep rows of the asked district
                (the right row can fall outside the top k: candidate starvation)
    prefilter   search only the asked district's chunks (Qdrant payload filter)

All three get the location in the query text, so none is penalised for a fact the lookup
receives as an argument. Each returns at most MAX_ZONES rows, best first, the most the
lookup can pass to the generator. The rows come from the same table as the lookup's, so
the answer differs only by which rows were chosen.
"""
from __future__ import annotations

from rag.config import PipelineConfig
from rag.gate import MAX_ZONES
from rag.retrieve import DenseRetriever
from rag.schedule_tool import ScheduleResult, ScheduleTable


class ScheduleVectorSearch:
    def __init__(self, table: ScheduleTable, cfg: PipelineConfig):
        self.table = table
        self.mode = cfg.schedule_retrieval
        self.k_retrieve = cfg.k_retrieve
        self.dense = DenseRetriever(cfg.embedding, corpus="schedule")
        self.collection = self.dense.collection
        self.name = f"{self.mode}: {self.dense.name}"

    def search(self, question: str, district: str, province: str | None = None,
               dong: str | None = None, waste_type: str | None = None) -> ScheduleResult:
        asked = self.table.district_rows(district, province)
        place = asked[0].district if asked else district
        text = " ".join(part for part in (province, place, dong, question) if part)
        if self.mode == "vector":
            hits = self.dense.search(text, MAX_ZONES)
        elif self.mode == "postfilter":
            ids = {r.row_id for r in asked}
            hits = [c for c in self.dense.search(text, self.k_retrieve)
                    if c.metadata["row_id"] in ids][:MAX_ZONES]
        elif asked:
            hits = self.dense.search(text, MAX_ZONES,
                                     where={"province": sorted({r.province for r in asked}),
                                            "district": sorted({r.district for r in asked})})
        else:
            hits = []
        rows = [self.table.by_id[c.metadata["row_id"]] for c in hits]
        query = {"district": district, "province": province, "dong": dong,
                 "waste_type": waste_type, "text": text}
        return ScheduleResult("OK" if rows else "NO_DATA", query, rows, matched_on=self.mode,
                              message="" if rows else f"no rows retrieved for '{district}'")
