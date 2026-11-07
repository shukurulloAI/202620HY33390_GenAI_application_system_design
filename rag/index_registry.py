"""
Which verified index to read (Lesson 3: only a published collection is ever searched).

The read side of the index, used at runtime. `ingest/` builds and publishes collections;
`rag/` never imports from `ingest/`.
"""
from __future__ import annotations

import json
from pathlib import Path

from rag import paths

CORPORA = {"items": paths.ITEM_CHUNKS,        # the system
           "schedule": paths.SCHEDULE_CHUNKS}  # E4 only


def corpus_path(corpus: str = "items") -> Path:
    path = CORPORA[corpus]
    if not path.exists():
        raise FileNotFoundError(f"{paths.relative(path)} is missing; "
                                "run python -m preprocess.build_all")
    return path


def read_published() -> dict:
    if paths.PUBLISHED_INDEXES.exists():
        return json.loads(paths.PUBLISHED_INDEXES.read_text(encoding="utf-8"))
    return {}


def published_key(embedding_key: str, corpus: str = "items") -> str:
    """Item indexes keep the bare embedding key, so existing registries stay valid."""
    return embedding_key if corpus == "items" else f"{corpus}:{embedding_key}"


def published_record(embedding_key: str, corpus: str = "items") -> dict:
    record = read_published().get(published_key(embedding_key, corpus))
    if record is None:
        raise SystemExit(f"No verified {corpus} index for '{embedding_key}'. Run: python -m "
                         f"ingest.build_index --embedding {embedding_key} --corpus {corpus}")
    return record
