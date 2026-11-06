"""Helpers shared by build_index.py, verify_index.py and the retriever."""
from __future__ import annotations

import hashlib
import json
import uuid
from pathlib import Path

from rag import config

FLAT_TYPES = (str, int, float, bool, type(None))


def item_chunk_path() -> Path:
    """Preprocessed chunks (Vitou) if present, otherwise the current builder output."""
    for path in config.ITEM_CHUNK_PATHS:
        if path.exists():
            return path
    raise FileNotFoundError("no item chunk file; run item_guide/build_item_chunks.py")


def corpus_path(corpus: str) -> Path:
    """Chunk file of a corpus: `items` (the system) or `schedule` (E4 only)."""
    if corpus == "items":
        return item_chunk_path()
    if config.SCHEDULE_CHUNK_PATH.exists():
        return config.SCHEDULE_CHUNK_PATH
    raise FileNotFoundError("no schedule chunk file; run python -m preprocess.build_all")


def load_chunks(path: Path) -> list[dict]:
    with path.open(encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def point_id(chunk_id: str) -> str:
    """Qdrant point ID. UUID chunk IDs are used as-is; others map through UUIDv5,
    so the same chunk ID always gives the same point ID (no loop-order dependence)."""
    try:
        return str(uuid.UUID(chunk_id))
    except ValueError:
        return str(uuid.uuid5(config.POINT_NAMESPACE, chunk_id))


def collection_name(spec: config.EmbeddingSpec, revision: str, corpus_sha: str,
                    corpus: str = "items") -> str:
    return f"{corpus}_{spec.key}_{revision[:8]}_{corpus_sha[:8]}"


def chunk_payload(chunk: dict) -> dict:
    return {"chunk_id": chunk["id"], "text": chunk["text"], **chunk["metadata"]}


def read_published() -> dict:
    if config.PUBLISHED_PATH.exists():
        return json.loads(config.PUBLISHED_PATH.read_text(encoding="utf-8"))
    return {}


def write_published(published: dict) -> None:
    config.PUBLISHED_PATH.parent.mkdir(parents=True, exist_ok=True)
    config.PUBLISHED_PATH.write_text(json.dumps(published, indent=2, ensure_ascii=False),
                                     encoding="utf-8")


def published_key(embedding_key: str, corpus: str = "items") -> str:
    """Item indexes keep the bare embedding key, so existing registries stay valid."""
    return embedding_key if corpus == "items" else f"{corpus}:{embedding_key}"


def published_record(embedding_key: str, corpus: str = "items") -> dict:
    record = read_published().get(published_key(embedding_key, corpus))
    if record is None:
        raise SystemExit(f"No verified {corpus} index for '{embedding_key}'. Run: python -m "
                         f"ingest.build_index --embedding {embedding_key} --corpus {corpus}")
    return record
