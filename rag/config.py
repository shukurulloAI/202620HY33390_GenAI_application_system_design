"""
Shared paths and settings for the pipeline.

Every component reads its settings from here, so an experiment changes one value
in one place (PLAN.md §6).
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# --- Inputs (preprocessed outputs from Vitou take priority when they exist) ---
PREPROCESS_DIR = ROOT / "preprocess"
ITEM_CHUNK_PATHS = (
    PREPROCESS_DIR / "item_chunks.jsonl",                 # final, UUIDv5 IDs (Vitou)
    ROOT / "item_guide" / "output" / "item_chunks.jsonl",  # current builder output
)
SCHEDULE_PATHS = (
    PREPROCESS_DIR / "schedule.csv",                       # cleaned table (Vitou), UTF-8
    ROOT / "Data" / "korean_waste_policies.csv",           # raw data.go.kr file, CP949
)
DISTRICT_ALIASES_PATH = PREPROCESS_DIR / "district_aliases.json"  # optional (Vitou)

# --- Local state (gitignored) and evidence (committed) ---
QDRANT_DIR = ROOT / "qdrant_data"
PUBLISHED_PATH = QDRANT_DIR / "published.json"   # embedding key -> verified collection
INDEX_REPORT_DIR = ROOT / "ingest" / "reports"
TRACE_DIR = ROOT / "traces"
PROMPT_DIR = ROOT / "rag" / "prompts"

# Fixed namespace for deterministic point IDs (never change it: IDs would change).
POINT_NAMESPACE = uuid.UUID("6f1d3c9e-2b7a-5e4f-9c8d-1a2b3c4d5e6f")


@dataclass(frozen=True)
class EmbeddingSpec:
    """Representation contract (Lesson 2/3): change any field -> new collection."""
    key: str
    model_id: str
    dim: int
    query_prefix: str        # prepended to queries only, as the model card says
    max_seq_length: int
    languages: str


EMBEDDING_MODELS = {
    "bge-m3": EmbeddingSpec(
        key="bge-m3", model_id="BAAI/bge-m3", dim=1024,
        query_prefix="", max_seq_length=8192, languages="multilingual",
    ),
    # Course default; English-only. Kept as the E2 baseline (domain mismatch).
    "bge-small-en": EmbeddingSpec(
        key="bge-small-en", model_id="BAAI/bge-small-en-v1.5", dim=384,
        query_prefix="Represent this sentence for searching relevant passages: ",
        max_seq_length=512, languages="English",
    ),
}
DEFAULT_EMBEDDING = "bge-m3"

# --- Retrieval ---
K_RETRIEVE = 20     # candidate set R
K_FINAL = 5         # evidence set E sent to the generator

# --- Generator (Ollama) ---
OLLAMA_URL = "http://localhost:11434"
# qwen2.5:7b chosen over the course default qwen2.5:3b after the Phase 1 probes:
# 3b contradicted its evidence on pizza box / chicken bones (7/12 vs 9/12 correct,
# see experiments/results/PHASE1_NOTES.md). 3b stays available with --model.
LLM_MODEL = "qwen2.5:7b"
# Hugging Face tokenizer per Ollama model, used to count prompt tokens before sending.
LLM_TOKENIZERS = {
    "qwen2.5:3b": "Qwen/Qwen2.5-3B-Instruct",
    "qwen2.5:7b": "Qwen/Qwen2.5-7B-Instruct",
}
LLM_TOKENIZER = LLM_TOKENIZERS[LLM_MODEL]
LLM_CONTEXT = 8192                 # num_ctx sent to Ollama
LLM_OUTPUT_RESERVE = 768           # tokens reserved for the answer (Lesson 2)
TEMPERATURE = 0.0
SEED = 7
