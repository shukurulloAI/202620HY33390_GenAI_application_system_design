"""
Build, verify and publish a Qdrant index (PLAN.md §4.1, Lesson 3): the item chunks, or
the district chunks that only E4's vector variants use.

Pipeline: chunk file -> input checks -> embed (pinned revision, normalised)
          -> Qdrant local collection (cosine) -> verification report -> publish.

The collection name contains the embedding key, model revision and corpus hash, so a
changed model or changed chunks always produce a new collection (never a mixed one).
An existing collection with the same name is reused after re-verification.

Usage (from the repo root):
    python -m ingest.build_index                          # bge-m3 (default)
    python -m ingest.build_index --embedding bge-small-en # course baseline for E2
    python -m ingest.build_index --rebuild                # re-embed even if present
    python -m ingest.build_index --corpus schedule        # district chunks, for E4
"""
from __future__ import annotations

import argparse
import json
import time
from datetime import UTC, datetime

from qdrant_client import QdrantClient, models

from ingest.index_common import (
    FLAT_TYPES,
    chunk_payload,
    collection_name,
    point_id,
    write_published,
)
from ingest.verify_index import verify
from rag import config, paths
from rag.embeddings import Embedder, resolve_revision
from rag.files import read_jsonl, sha256_file
from rag.index_registry import corpus_path, published_key, read_published


def check_chunks(chunks: list[dict]) -> dict:
    """Input contract: unique IDs, non-empty text, flat metadata with a source."""
    ids = [c.get("id") for c in chunks]
    return {
        "chunk_ids_present": all(ids),
        "chunk_ids_unique": len(set(ids)) == len(ids),
        "text_non_empty": all(c.get("text", "").strip() for c in chunks),
        "metadata_flat": all(isinstance(v, FLAT_TYPES)
                             for c in chunks for v in c.get("metadata", {}).values()),
        "source_present": all(c.get("metadata", {}).get("source") for c in chunks),
        "no_reserved_keys": all(not {"chunk_id", "text"} & set(c.get("metadata", {}))
                                for c in chunks),
    }


def build(embedding_key: str, revision: str | None, rebuild: bool,
          corpus: str = "items") -> dict:
    spec = config.EMBEDDING_MODELS[embedding_key]
    path = corpus_path(corpus)
    corpus_sha = sha256_file(path)
    chunks = read_jsonl(path)
    input_checks = check_chunks(chunks)
    if not all(input_checks.values()):
        raise SystemExit(f"Chunk file failed input checks: {input_checks}")

    revision = revision or resolve_revision(spec.model_id)
    name = collection_name(spec, revision, corpus_sha, corpus)
    paths.QDRANT_DIR.mkdir(parents=True, exist_ok=True)

    client = QdrantClient(path=str(paths.QDRANT_DIR))
    embed_info = {"reused_existing_collection": True}
    try:
        exists = client.collection_exists(name)
        if exists and not rebuild:
            print(f"Collection {name} exists; re-verifying instead of re-embedding.")
        else:
            if exists:
                client.delete_collection(name)
            print(f"Embedding {len(chunks)} chunks with {spec.model_id}@{revision[:8]} ...")
            started = time.perf_counter()
            embedder = Embedder(spec, revision)          # may download the model
            load_seconds = time.perf_counter() - started
            token_counts = [embedder.count_tokens(c["text"]) for c in chunks]
            started = time.perf_counter()
            vectors = embedder.encode_passages([c["text"] for c in chunks])
            client.create_collection(
                collection_name=name,
                vectors_config=models.VectorParams(size=spec.dim,
                                                   distance=models.Distance.COSINE))
            points = [models.PointStruct(id=point_id(c["id"]), vector=v,
                                         payload=chunk_payload(c))
                      for c, v in zip(chunks, vectors, strict=True)]
            for i in range(0, len(points), 128):
                client.upsert(collection_name=name, points=points[i:i + 128])
            embed_info = {
                "reused_existing_collection": False,
                "device": embedder.device,
                "model_load_seconds": round(load_seconds, 1),
                "embed_seconds": round(time.perf_counter() - started, 1),
                "chunk_tokens_max": max(token_counts),
                "chunk_tokens_mean": round(sum(token_counts) / len(token_counts), 1),
                "chunks_over_max_seq_length": sum(t > spec.max_seq_length
                                                  for t in token_counts),
            }
    finally:
        client.close()

    verification = verify(name, spec, chunks, path, corpus_sha)
    report = {
        "built_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "collection": name,
        "status": verification["status"],
        "representation_contract": {
            "embedding_key": spec.key, "model_id": spec.model_id, "revision": revision,
            "dimension": spec.dim, "normalized": True, "distance": "Cosine",
            "query_prefix": spec.query_prefix, "max_seq_length": spec.max_seq_length,
            "languages": spec.languages,
        },
        "corpus": {
            "path": paths.relative(path),
            "sha256": corpus_sha,
            "chunks": len(chunks),
            "doc_types": dict(sorted(
                {t: sum(c["metadata"].get("doc_type") == t for c in chunks)
                 for t in {c["metadata"].get("doc_type") for c in chunks}}.items())),
        },
        "input_checks": input_checks,
        "embedding_run": embed_info,
        "verification": verification,
    }
    paths.INDEX_REPORT_DIR.mkdir(parents=True, exist_ok=True)
    report_path = paths.INDEX_REPORT_DIR / f"{name}.json"
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n",
                           encoding="utf-8")

    if report["status"] == "PASS":           # publish only after PASS (Lesson 3)
        published = read_published()
        published[published_key(spec.key, corpus)] = {
            "collection": name, "model_id": spec.model_id, "revision": revision,
            "corpus_path": report["corpus"]["path"], "corpus_sha256": corpus_sha,
            "report": paths.relative(report_path),
        }
        write_published(published)
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--embedding", default=config.DEFAULT_EMBEDDING,
                        choices=sorted(config.EMBEDDING_MODELS))
    parser.add_argument("--revision", help="model commit SHA (default: current hub SHA)")
    parser.add_argument("--rebuild", action="store_true")
    parser.add_argument("--corpus", default="items", choices=["items", "schedule"])
    args = parser.parse_args()
    report = build(args.embedding, args.revision, args.rebuild, args.corpus)
    print(json.dumps({k: report[k] for k in ("collection", "status")}
                     | {"checks": report["verification"]["checks"],
                        "embedding_run": report["embedding_run"]},
                     indent=2, ensure_ascii=False))
    raise SystemExit(0 if report["status"] == "PASS" else 1)


if __name__ == "__main__":
    main()
