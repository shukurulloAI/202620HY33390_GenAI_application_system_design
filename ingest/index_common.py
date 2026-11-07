"""Helpers for writing an index, shared by build_index.py and verify_index.py."""
from __future__ import annotations

import json
import uuid

from rag import config, paths

FLAT_TYPES = (str, int, float, bool, type(None))

# Fixed namespace for deterministic point IDs (never change it: IDs would change).
POINT_NAMESPACE = uuid.UUID("6f1d3c9e-2b7a-5e4f-9c8d-1a2b3c4d5e6f")


def point_id(chunk_id: str) -> str:
    """Qdrant point ID. UUID chunk IDs are used as-is; others map through UUIDv5,
    so the same chunk ID always gives the same point ID (no loop-order dependence)."""
    try:
        return str(uuid.UUID(chunk_id))
    except ValueError:
        return str(uuid.uuid5(POINT_NAMESPACE, chunk_id))


def collection_name(spec: config.EmbeddingSpec, revision: str, corpus_sha: str,
                    corpus: str = "items") -> str:
    return f"{corpus}_{spec.key}_{revision[:8]}_{corpus_sha[:8]}"


def chunk_payload(chunk: dict) -> dict:
    return {"chunk_id": chunk["id"], "text": chunk["text"], **chunk["metadata"]}


def write_published(published: dict) -> None:
    paths.PUBLISHED_INDEXES.parent.mkdir(parents=True, exist_ok=True)
    paths.PUBLISHED_INDEXES.write_text(json.dumps(published, indent=2, ensure_ascii=False),
                                       encoding="utf-8")
