"""
Settings for the pipeline; locations are in rag/paths.py.

Every component reads its settings from here, so an experiment changes one value
in one place (PLAN.md §6).
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path


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
RRF_K = 60          # Reciprocal Rank Fusion constant (Cormack et al., 2009)

# Cross-encoder reranker (multilingual, scores Korean chunks against any query).
RERANKER_MODEL = "BAAI/bge-reranker-v2-m3"
RERANKER_REVISION = "953dc6f6f85a1b2dbfca4c34a2796e7dde08d41e"
RERANKER_MAX_LENGTH = 512

# --- Generator (Ollama) ---
OLLAMA_URL = "http://localhost:11434"
# qwen2.5:7b chosen over the course default qwen2.5:3b after the Phase 1 probes:
# 3b contradicted its evidence on pizza box / chicken bones (7/12 vs 9/12 correct,
# see docs/PHASE1_NOTES.md). 3b stays available with --set llm_model.
LLM_MODEL = "qwen2.5:7b"
# Hugging Face tokenizer per Ollama model, used to count prompt tokens before sending.
LLM_TOKENIZERS = {
    "qwen2.5:3b": "Qwen/Qwen2.5-3B-Instruct",
    "qwen2.5:7b": "Qwen/Qwen2.5-7B-Instruct",
    "exaone3.5:7.8b": "LGAI-EXAONE/EXAONE-3.5-7.8B-Instruct",   # LG AI Research, Korean/English
}
LLM_TOKENIZER = LLM_TOKENIZERS[LLM_MODEL]
LLM_CONTEXT = 8192                 # num_ctx sent to Ollama
LLM_OUTPUT_RESERVE = 768           # tokens reserved for the answer (Lesson 2)
TEMPERATURE = 0.0
SEED = 7


# --- One object per pipeline configuration (PLAN.md §6: change one field per experiment) ---
@dataclass(frozen=True)
class PipelineConfig:
    embedding: str = DEFAULT_EMBEDDING
    retrieval: str = "hybrid"           # dense | bm25 | hybrid (RRF of dense + bm25)
    bm25_tokenizer: str = "kiwi"        # kiwi (morphemes) | bigram (character bigrams)
    query_mode: str = "both"            # original | rewrite | both  (rewrite needs router)
    rerank: bool = True                 # cross-encoder over the candidate set R
    rerank_query: str = "max"           # original | rewrite | max (best score of both)
    name_search: bool = True            # add a list: the router's item name against chunk
                                        # names only (rag/retrieve.NameIndex). E9 on dev:
                                        # Recall@5 0.795 -> 0.841 with rerank_item, no case
                                        # worse; full system 49 -> 51/70 correct
    rerank_item: bool = True            # also rerank with the item name alone (E9)
    k_retrieve: int = K_RETRIEVE
    k_final: int = K_FINAL
    rrf_k: int = RRF_K
    router: bool = True                 # LLM router / rewriter (PLAN.md §4.3)
    gate_tau: float | None = 0.15       # min rerank score to answer; None = gate off.
                                        # Provisional: middle of the gap between the highest
                                        # negative (0.039) and the next positive (0.264) on
                                        # the 22 probes (experiments/tau_sweep.py). Re-pick on
                                        # dev (E5) once eval/cases/dev.jsonl exists.
    llm_model: str = LLM_MODEL
    router_model: str | None = None     # None = same model as the generator
    router_repair: bool = False         # one retry when the Korean rewrite fails the script
                                        # check (Stage 3; rag/router.Router._repair)
    prompt_version: str = "v2"          # v0 minimal | v1 zero-shot | v2 few-shot | v3, v4 fixes
    conflict_policy: str = "prefer_2026"  # prefer_2026 | none   (E8)
    validation: str = "enforce"         # off | flag | enforce   (PLAN.md §4.9)
    schedule_retrieval: str = "structured"  # structured (typed lookup) | vector | postfilter |
                                            # prefilter; the last three exist only for E4
    schedule_text: str = "code"         # code: days, times and places written by code, the LLM
                                        # only translates the method text | llm: the generator
                                        # writes them (Phase 1 behaviour)
    temperature: float = TEMPERATURE
    seed: int = SEED

    CHOICES = {"retrieval": ("dense", "bm25", "hybrid"),
               "bm25_tokenizer": ("kiwi", "bigram"),
               "query_mode": ("original", "rewrite", "both"),
               "rerank_query": ("original", "rewrite", "max"),
               "prompt_version": ("v0", "v1", "v2", "v3", "v4"),
               "conflict_policy": ("prefer_2026", "none"),
               "validation": ("off", "flag", "enforce"),
               "schedule_retrieval": ("structured", "vector", "postfilter", "prefilter"),
               "schedule_text": ("code", "llm")}

    def __post_init__(self):
        for name, allowed in self.CHOICES.items():
            if getattr(self, name) not in allowed:
                raise ValueError(f"{name}={getattr(self, name)!r}; allowed: {allowed}")
        if self.embedding not in EMBEDDING_MODELS:
            raise ValueError(f"unknown embedding {self.embedding!r}")
        if self.query_mode != "original" and not self.router:
            object.__setattr__(self, "query_mode", "original")   # no rewrite without router

    @classmethod
    def from_dict(cls, values: dict) -> PipelineConfig:
        known = set(cls.__dataclass_fields__)
        unknown = set(values) - known
        if unknown:
            raise ValueError(f"unknown config fields: {sorted(unknown)}")
        return cls(**values)

    def replace(self, **changes) -> PipelineConfig:
        return PipelineConfig.from_dict({**self.to_dict(), **changes})

    def to_dict(self) -> dict:
        return {name: getattr(self, name) for name in self.__dataclass_fields__}


# The Phase 1 system, kept runnable as the baseline for every comparison.
BASELINE = PipelineConfig(retrieval="dense", rerank=False, router=False, gate_tau=None,
                          query_mode="original", prompt_version="v1", validation="off",
                          schedule_text="llm")
DEFAULT = PipelineConfig()


def parse_overrides(pairs: list[str] | None) -> dict:
    """['retrieval=dense', 'rerank=false', 'gate_tau=0.2'] -> typed dict."""
    out = {}
    for pair in pairs or []:
        key, _, raw = pair.partition("=")
        try:
            out[key.strip()] = json.loads(raw)
        except json.JSONDecodeError:
            out[key.strip()] = raw
    return out


def load_config(base: str | None = None, overrides: list[str] | None = None) -> PipelineConfig:
    """`base`: None (the full system), "baseline", or a JSON file of PipelineConfig fields."""
    if base == "baseline":
        cfg = BASELINE
    elif base:
        cfg = PipelineConfig.from_dict(json.loads(Path(base).read_text(encoding="utf-8")))
    else:
        cfg = DEFAULT
    return cfg.replace(**parse_overrides(overrides)) if overrides else cfg
