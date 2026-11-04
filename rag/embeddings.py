"""
Text embeddings with a pinned model revision (Lesson 2/3 representation contract).

Passages and queries go through the same model, normalisation and metric; only the
query prefix differs, as the model card specifies.
"""
from __future__ import annotations

from rag.config import EmbeddingSpec


def resolve_revision(model_id: str) -> str:
    """Current commit SHA of a Hugging Face model, used to pin the build."""
    from huggingface_hub import HfApi
    try:
        return HfApi().model_info(model_id).sha
    except Exception as exc:  # offline or hub error: the caller must pin explicitly
        raise SystemExit(
            f"Could not resolve the revision of {model_id} ({exc}). "
            "Pass --revision <commit sha>.") from exc


class Embedder:
    def __init__(self, spec: EmbeddingSpec, revision: str):
        from sentence_transformers import SentenceTransformer
        if not revision:
            raise ValueError("a pinned model revision is required")
        self.spec = spec
        self.revision = revision
        self.model = SentenceTransformer(spec.model_id, revision=revision)
        self.model.max_seq_length = min(self.model.max_seq_length or spec.max_seq_length,
                                        spec.max_seq_length)
        self.device = str(self.model.device)

    def encode_passages(self, texts: list[str], batch_size: int = 16) -> list[list[float]]:
        vectors = self.model.encode(
            list(texts), batch_size=batch_size, normalize_embeddings=True,
            show_progress_bar=len(texts) > 50)
        return vectors.tolist()

    def encode_query(self, text: str) -> list[float]:
        vector = self.model.encode([self.spec.query_prefix + text],
                                   normalize_embeddings=True)[0]
        return vector.tolist()

    def count_tokens(self, text: str) -> int:
        """Tokens as this embedding model sees them (for max-length checks)."""
        return len(self.model.tokenizer(text, add_special_tokens=True)["input_ids"])
