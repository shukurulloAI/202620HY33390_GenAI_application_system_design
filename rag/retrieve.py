"""
Item retrieval (PLAN.md §4.4, Lessons 4-5).

Phase 1 baseline: dense retrieval only (bge-m3 + Qdrant, cosine).
Phase 2 adds BM25, RRF fusion and cross-encoder reranking as separate, switchable
stages so each one can be measured on its own (E3, E5).
"""
from __future__ import annotations

from dataclasses import asdict, dataclass

from qdrant_client import QdrantClient, models

from ingest.index_common import published_record
from rag import config
from rag.embeddings import Embedder


@dataclass
class Candidate:
    chunk_id: str
    text: str
    metadata: dict
    score: float          # meaning depends on `retriever` (cosine for dense)
    rank: int             # 1-based rank in this retriever's list
    retriever: str

    def to_trace(self) -> dict:
        record = asdict(self)
        record["text"] = self.text[:200]
        return record


class DenseRetriever:
    """Searches the published (verified) collection for one embedding contract."""

    def __init__(self, embedding_key: str = config.DEFAULT_EMBEDDING):
        record = published_record(embedding_key)
        self.spec = config.EMBEDDING_MODELS[embedding_key]
        self.collection = record["collection"]
        self.revision = record["revision"]
        self.embedder = Embedder(self.spec, self.revision)
        self.client = QdrantClient(path=str(config.QDRANT_DIR))
        self.name = f"dense:{self.spec.key}@{self.revision[:8]}"

    def search(self, query: str, k: int = config.K_RETRIEVE,
               doc_types: list[str] | None = None) -> list[Candidate]:
        query_filter = None
        if doc_types:                                   # prefilter (Lesson 5)
            query_filter = models.Filter(must=[models.FieldCondition(
                key="doc_type", match=models.MatchAny(any=doc_types))])
        result = self.client.query_points(
            collection_name=self.collection, query=self.embedder.encode_query(query),
            query_filter=query_filter, limit=k, with_payload=True)
        candidates = []
        for rank, point in enumerate(result.points, 1):
            payload = dict(point.payload)
            candidates.append(Candidate(
                chunk_id=payload.pop("chunk_id"), text=payload.pop("text"),
                metadata=payload, score=round(float(point.score), 4), rank=rank,
                retriever=self.name))
        return candidates

    def close(self) -> None:
        self.client.close()
