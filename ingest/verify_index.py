"""
Verify a Qdrant collection against its chunk file (Lesson 3: "an index is publishable
only when counts, dimensions, identifiers, provenance and persistence all pass").

Usage:
    python -m ingest.verify_index                 # verify the published bge-m3 index
    python -m ingest.verify_index --embedding bge-small-en
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

from qdrant_client import QdrantClient

from ingest.index_common import (chunk_payload, load_chunks, point_id, published_record,
                                 sha256_file)
from rag import config


def verify(collection: str, spec: config.EmbeddingSpec, chunks: list[dict],
           corpus_path: Path, corpus_sha: str) -> dict:
    """Reopen the stored collection and check it against the chunks it should hold."""
    expected = {point_id(c["id"]): c for c in chunks}
    client = QdrantClient(path=str(config.QDRANT_DIR))      # reopen = persistence check
    try:
        params = client.get_collection(collection).config.params.vectors
        stored_count = client.count(collection, exact=True).count
        points, offset = [], None
        while True:
            batch, offset = client.scroll(collection, limit=256, offset=offset,
                                          with_payload=True, with_vectors=True)
            points.extend(batch)
            if offset is None:
                break
    finally:
        client.close()

    ids = [str(p.id) for p in points]
    norms = [math.sqrt(sum(x * x for x in p.vector)) for p in points]
    payload_ok = all(
        p.payload.get("chunk_id") == expected.get(str(p.id), {}).get("id")
        and p.payload.get("text") == expected[str(p.id)]["text"]
        and p.payload.get("source")
        for p in points if str(p.id) in expected)

    checks = {
        "corpus_hash_matches": sha256_file(corpus_path) == corpus_sha,
        "count_matches_chunks": stored_count == len(chunks) == len(points),
        "ids_unique": len(set(ids)) == len(ids),
        "ids_match_chunks": set(ids) == set(expected),
        # IDs recomputed from a fresh read of the file must equal the stored ones
        "repeat_run_ids_match": sorted(point_id(c["id"]) for c in load_chunks(corpus_path))
                                == sorted(ids),
        "vector_size_matches_contract": params.size == spec.dim
                                        and all(len(p.vector) == spec.dim for p in points),
        "distance_is_cosine": str(params.distance).lower().endswith("cosine"),
        "vectors_normalized": all(abs(n - 1.0) < 1e-3 for n in norms),
        "payload_provenance": payload_ok,
        "payload_matches_chunks": all(
            {k: v for k, v in p.payload.items()} == chunk_payload(expected[str(p.id)])
            for p in points if str(p.id) in expected),
    }
    return {
        "collection": collection,
        "status": "PASS" if all(checks.values()) else "FAIL",
        "checks": checks,
        "stored_points": stored_count,
        "expected_points": len(chunks),
        "vector_size": params.size,
        "distance": str(params.distance),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--embedding", default=config.DEFAULT_EMBEDDING,
                        choices=sorted(config.EMBEDDING_MODELS))
    parser.add_argument("--corpus", default="items", choices=["items", "schedule"])
    args = parser.parse_args()
    record = published_record(args.embedding, args.corpus)
    corpus_path = config.ROOT / record["corpus_path"]
    report = verify(record["collection"], config.EMBEDDING_MODELS[args.embedding],
                    load_chunks(corpus_path), corpus_path, record["corpus_sha256"])
    print(json.dumps(report, indent=2, ensure_ascii=False))
    raise SystemExit(0 if report["status"] == "PASS" else 1)


if __name__ == "__main__":
    main()
