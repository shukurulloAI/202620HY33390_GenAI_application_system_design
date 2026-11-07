"""
Item retrieval (PLAN.md §4.4, Lessons 4-5).

Stages, each switchable so it can be measured on its own:

    queries (original question and/or the router's Korean rewrite)
      -> dense (bge-m3 + Qdrant)  and/or  BM25 (kiwi morphemes | character bigrams)
      -> Reciprocal Rank Fusion of all lists           = candidate set R (k_retrieve)
      -> cross-encoder rerank of R (bge-reranker-v2-m3) [optional]
      -> top k_final                                   = evidence set E

Every candidate keeps its rank in each list (`ranks`) and its rerank score, so a
trace shows why a chunk was selected (Lesson 4: R is not E).

CLI (retrieval only, no LLM):
    python -m rag.retrieve "택배 스티로폼 상자" --retrieval hybrid --rerank
"""
from __future__ import annotations

import argparse
import atexit
import math
import re
import shutil
import sys
import tempfile
import time
from dataclasses import asdict, dataclass, field
from functools import lru_cache
from pathlib import Path

from qdrant_client import QdrantClient, models

from rag import config, paths
from rag.embeddings import Embedder
from rag.files import read_jsonl, sha256_file
from rag.index_registry import corpus_path, published_record


@dataclass
class Candidate:
    chunk_id: str
    text: str
    metadata: dict
    score: float          # meaning depends on `retriever` (cosine, BM25, RRF)
    rank: int             # 1-based rank in the current list
    retriever: str
    ranks: dict = field(default_factory=dict)   # list name -> rank in that list
    rerank_score: float | None = None

    def to_trace(self) -> dict:
        record = asdict(self)
        record["text"] = self.text[:200]
        return record


def _copy(c: Candidate, **changes) -> Candidate:
    return Candidate(**{**asdict(c), **changes})


# ---------------------------------------------------------------- dense

class DenseRetriever:
    """Searches the published (verified) collection for one embedding contract."""

    def __init__(self, embedding_key: str = config.DEFAULT_EMBEDDING, corpus: str = "items"):
        record = published_record(embedding_key, corpus)
        self.spec = config.EMBEDDING_MODELS[embedding_key]
        self.collection = record["collection"]
        self.revision = record["revision"]
        self.corpus_sha256 = record["corpus_sha256"]
        self.embedder = _embedder(embedding_key, self.revision)
        self.client = _qdrant_client()
        self.name = f"dense:{self.spec.key}@{self.revision[:8]}"

    def search(self, query: str, k: int = config.K_RETRIEVE,
               doc_types: list[str] | None = None,
               where: dict[str, list[str]] | None = None) -> list[Candidate]:
        """`where`: payload field -> allowed values, applied during the search."""
        fields = {**({"doc_type": doc_types} if doc_types else {}), **(where or {})}
        query_filter = None
        if fields:                                      # prefilter (Lesson 5)
            query_filter = models.Filter(must=[
                models.FieldCondition(key=key, match=models.MatchAny(any=values))
                for key, values in fields.items()])
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
        pass   # the Qdrant client is shared (local mode allows one client per folder)


@lru_cache(maxsize=2)
def _embedder(embedding_key: str, revision: str) -> Embedder:
    return Embedder(config.EMBEDDING_MODELS[embedding_key], revision)


@lru_cache(maxsize=1)
def _qdrant_client() -> QdrantClient:
    """Local Qdrant allows one process per folder. If another process (the website, an
    eval run) holds it, open a temporary copy instead: published collections are never
    modified, so a copy is an exact read-only snapshot."""
    try:
        client = QdrantClient(path=str(paths.QDRANT_DIR))
    except RuntimeError as exc:
        if "already accessed" not in str(exc):
            raise
        snapshot = Path(tempfile.mkdtemp(prefix="qdrant_snapshot_")) / "qdrant_data"
        shutil.copytree(paths.QDRANT_DIR, snapshot,
                        ignore=shutil.ignore_patterns(".lock"))
        print(f"note: {paths.QDRANT_DIR.name}/ is in use by another process; "
              f"reading a snapshot copy at {snapshot}", file=sys.stderr)
        client = QdrantClient(path=str(snapshot))
        atexit.register(shutil.rmtree, snapshot.parent, True)
    atexit.register(client.close)          # close before interpreter shutdown
    return client


# ---------------------------------------------------------------- lexical

# Kiwi tags kept for BM25: nouns, verb/adjective stems, roots, foreign words, numbers,
# hanja. Particles (조사), endings (어미) and punctuation are dropped.
_KIWI_KEEP = ("NNG", "NNP", "NNB", "NR", "NP", "VV", "VA", "XR", "SL", "SN", "SH", "MAG")
_WORD = re.compile(r"[가-힣]+|[a-zA-Z]+|\d+")


@lru_cache(maxsize=1)
def _kiwi():
    from kiwipiepy import Kiwi
    return Kiwi()


def tokenize_kiwi(text: str) -> list[str]:
    return [t.form.lower() for t in _kiwi().tokenize(text) if t.tag in _KIWI_KEEP]


def tokenize_bigram(text: str) -> list[str]:
    """Character bigrams inside Hangul words; Latin words and numbers kept whole."""
    tokens = []
    for word in _WORD.findall(text.lower()):
        if "가" <= word[0] <= "힣" and len(word) > 1:
            tokens.extend(word[i:i + 2] for i in range(len(word) - 1))
        else:
            tokens.append(word)
    return tokens


TOKENIZERS = {"kiwi": tokenize_kiwi, "bigram": tokenize_bigram}


class BM25Retriever:
    """Okapi BM25 over the same chunk file the dense index was built from.

    Hits with score 0 are dropped (no shared token): an English query against the
    Korean corpus returns nothing instead of an arbitrary ranking.
    """

    def __init__(self, tokenizer: str = "kiwi", expected_sha256: str | None = None):
        from rank_bm25 import BM25Okapi
        path = corpus_path("items")
        sha = sha256_file(path)
        if expected_sha256 and sha != expected_sha256:
            raise RuntimeError(
                f"{path} changed since the dense index was built "
                f"({sha[:8]} != {expected_sha256[:8]}); rebuild the index first")
        self.chunks = read_jsonl(path)
        self.corpus_sha256 = sha
        self.tokenize = TOKENIZERS[tokenizer]
        self.bm25 = BM25Okapi([self.tokenize(c["text"]) for c in self.chunks])
        self.name = f"bm25:{tokenizer}"

    def search(self, query: str, k: int = config.K_RETRIEVE,
               doc_types: list[str] | None = None) -> list[Candidate]:
        tokens = self.tokenize(query)
        if not tokens:
            return []
        scores = self.bm25.get_scores(tokens)
        order = sorted(range(len(scores)), key=lambda i: -scores[i])
        out = []
        for i in order:
            if scores[i] <= 0 or len(out) == k:
                break
            chunk = self.chunks[i]
            if doc_types and chunk["metadata"].get("doc_type") not in doc_types:
                continue
            out.append(Candidate(chunk["id"], chunk["text"], dict(chunk["metadata"]),
                                 round(float(scores[i]), 4), len(out) + 1, self.name))
        return out


# ---------------------------------------------------------------- fusion + rerank

def rrf(lists: dict[str, list[Candidate]], k: int = config.RRF_K) -> list[Candidate]:
    """Reciprocal Rank Fusion: score(d) = sum over lists of 1 / (k + rank_list(d))."""
    fused: dict[str, Candidate] = {}
    scores: dict[str, float] = {}
    for name, candidates in lists.items():
        for c in candidates:
            if c.chunk_id not in fused:
                fused[c.chunk_id] = _copy(c, ranks={})
                scores[c.chunk_id] = 0.0
            fused[c.chunk_id].ranks[name] = c.rank
            scores[c.chunk_id] += 1.0 / (k + c.rank)
    order = sorted(fused, key=lambda cid: (-scores[cid], cid))
    label = "rrf(" + "+".join(lists) + ")"
    return [_copy(fused[cid], score=round(scores[cid], 6), rank=r, retriever=label)
            for r, cid in enumerate(order, 1)]


class Reranker:
    """Cross-encoder: reads (query, chunk) together and returns a relevance score in
    [0, 1] (sigmoid). Slower than embeddings, so it only sees the candidate set R."""

    def __init__(self, model_id: str = config.RERANKER_MODEL,
                 revision: str = config.RERANKER_REVISION,
                 max_length: int = config.RERANKER_MAX_LENGTH):
        from sentence_transformers import CrossEncoder
        self.model = CrossEncoder(model_id, revision=revision, max_length=max_length)
        self.name = f"rerank:{model_id.split('/')[-1]}@{revision[:8]}"

    def score(self, query: str, candidates: list[Candidate]) -> list[float]:
        raw = self.model.predict([(query, c.text) for c in candidates],
                                 batch_size=16, show_progress_bar=False)
        scores = [float(s) for s in raw]
        if any(s < 0 or s > 1 for s in scores):          # logits -> probability
            scores = [1 / (1 + math.exp(-s)) for s in scores]
        return scores

    def rerank(self, queries: list[str], candidates: list[Candidate]) -> list[Candidate]:
        """Several queries (original + rewrite): each chunk keeps its best score, so a
        bad rewrite cannot push the right chunk down."""
        if not candidates:
            return []
        per_query = [self.score(q, candidates) for q in queries if q]
        scores = [max(col) for col in zip(*per_query, strict=True)]
        order = sorted(range(len(candidates)), key=lambda i: -scores[i])
        return [_copy(candidates[i], rank=r, rerank_score=round(scores[i], 4),
                      ranks={**candidates[i].ranks, "fused": candidates[i].rank})
                for r, i in enumerate(order, 1)]


@lru_cache(maxsize=1)
def default_reranker() -> Reranker:
    return Reranker()


# ---------------------------------------------------------------- composed retriever

class ItemRetriever:
    """Dense / BM25 / hybrid retrieval with optional reranking, set by PipelineConfig."""

    def __init__(self, cfg: config.PipelineConfig = config.DEFAULT):
        self.cfg = cfg
        self.dense = DenseRetriever(cfg.embedding) if cfg.retrieval in ("dense", "hybrid") else None
        expected = self.dense.corpus_sha256 if self.dense else None
        self.bm25 = (_bm25(cfg.bm25_tokenizer, expected)
                     if cfg.retrieval in ("bm25", "hybrid") else None)
        self.reranker = default_reranker() if cfg.rerank else None
        parts = [p.name for p in (self.dense, self.bm25, self.reranker) if p]
        self.name = " | ".join(parts)
        self.collection = self.dense.collection if self.dense else None

    def search(self, queries: dict[str, str], rerank_queries: list[str] | None = None,
               doc_types: list[str] | None = None) -> tuple[list[Candidate], list[Candidate], dict]:
        """queries: {"original": ..., "rewrite": ...} (empty values skipped).
        Returns (candidate set R, evidence set E, trace record)."""
        timings, lists = {}, {}
        queries = {name: q for name, q in queries.items() if q}
        t = time.perf_counter()
        for qname, query in queries.items():
            if self.dense:
                lists[f"dense/{qname}"] = self.dense.search(query, self.cfg.k_retrieve, doc_types)
            if self.bm25:
                lists[f"bm25/{qname}"] = self.bm25.search(query, self.cfg.k_retrieve, doc_types)
        timings["retrieve_s"] = round(time.perf_counter() - t, 3)

        fused = rrf(lists, self.cfg.rrf_k)[:self.cfg.k_retrieve]
        if len(lists) == 1:                         # single list: keep its own scores
            only = next(iter(lists.values()))
            fused = [_copy(c, ranks={next(iter(lists)): c.rank}) for c in only]
        candidates = fused
        if self.reranker:
            t = time.perf_counter()
            rerank_queries = rerank_queries or [next(iter(queries.values()), "")]
            candidates = self.reranker.rerank(rerank_queries, fused)
            timings["rerank_s"] = round(time.perf_counter() - t, 3)
        selected = candidates[:self.cfg.k_final]
        record = {"queries": queries,
                  "rerank_queries": rerank_queries if self.reranker else None,
                  "lists": {name: [c.chunk_id for c in cands] for name, cands in lists.items()},
                  "timings": timings}
        return candidates, selected, record


@lru_cache(maxsize=4)
def _bm25(tokenizer: str, expected_sha256: str | None) -> BM25Retriever:
    return BM25Retriever(tokenizer, expected_sha256)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("query")
    parser.add_argument("--retrieval", default="hybrid", choices=["dense", "bm25", "hybrid"])
    parser.add_argument("--tokenizer", default="kiwi", choices=sorted(TOKENIZERS))
    parser.add_argument("--embedding", default=config.DEFAULT_EMBEDDING)
    parser.add_argument("--rerank", action="store_true")
    parser.add_argument("-k", type=int, default=10)
    args = parser.parse_args()
    cfg = config.PipelineConfig(embedding=args.embedding, retrieval=args.retrieval,
                                bm25_tokenizer=args.tokenizer, rerank=args.rerank,
                                router=False, k_final=args.k)
    retriever = ItemRetriever(cfg)
    _, selected, record = retriever.search({"original": args.query}, [args.query])
    print(retriever.name, record["timings"])
    for c in selected:
        label = c.metadata.get("item") or c.metadata.get("section") or c.metadata.get("topic")
        rs = f"rerank={c.rerank_score:.3f} " if c.rerank_score is not None else ""
        print(f"{c.rank:2d} {c.chunk_id:15s} {rs}score={c.score:<8} {c.ranks} {label}")


if __name__ == "__main__":
    main()
