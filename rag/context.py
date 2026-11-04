"""
Context construction under a token budget (PLAN.md §4.7, Lessons 2 and 4).

    input_budget = max_context - reserved_output

Tokens are counted with the generator's own tokenizer (not word counts). If the
evidence does not fit, the lowest-ranked item chunks are dropped first and the drop
is recorded; nothing is truncated silently.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from functools import lru_cache

from rag import config


@dataclass(frozen=True)
class ContextBudget:
    max_context: int = config.LLM_CONTEXT
    reserved_output: int = config.LLM_OUTPUT_RESERVE

    @property
    def input_budget(self) -> int:
        return self.max_context - self.reserved_output


class TokenCounter:
    """Counts tokens with the generator's tokenizer; falls back to a labelled
    character estimate (1 token per character, an upper bound for Korean)."""

    def __init__(self, tokenizer_id: str = config.LLM_TOKENIZER):
        self.tokenizer_id = tokenizer_id
        try:
            from transformers import AutoTokenizer
            self._tok = AutoTokenizer.from_pretrained(tokenizer_id)
            self.exact = True
        except Exception:
            self._tok = None
            self.exact = False

    def count(self, text: str) -> int:
        if self._tok is None:
            return len(text)
        return len(self._tok(text, add_special_tokens=False)["input_ids"])


@lru_cache(maxsize=2)
def default_counter(tokenizer_id: str = config.LLM_TOKENIZER) -> TokenCounter:
    return TokenCounter(tokenizer_id)


@dataclass
class EvidenceItem:
    n: int                      # citation number shown to the model: [n]
    kind: str                   # "item" (guide chunk) | "schedule" (district row)
    ref: str                    # chunk_id or 관리번호
    label: str                  # human-readable source
    text: str
    metadata: dict = field(default_factory=dict)

    def block(self) -> str:
        return f"[{self.n}] ({self.label})\n{self.text}"

    def to_citation(self) -> dict:
        return {"n": self.n, "kind": self.kind, "ref": self.ref, "source": self.label}


def item_label(metadata: dict) -> str:
    where = f"p.{metadata['page']}" if metadata.get("page") else ""
    if metadata.get("doc_type") in ("rule", "note") and metadata.get("section"):
        where = metadata["section"]
    return f"{metadata.get('source', 'unknown source')} {where}".strip()


def pack_evidence(item_candidates: list, schedule_rows: list, waste_type: str | None,
                  fixed_text: str, counter: TokenCounter,
                  budget: ContextBudget = ContextBudget()):
    """Number the evidence and keep what fits.

    Order: item chunks by retrieval rank, then district schedule rows. Schedule rows
    are kept before item chunks when space runs out, because they are the only
    source for when/where questions.
    Returns (kept EvidenceItems, evidence text, budget record for the trace).
    """
    pool = [("item", c) for c in item_candidates] + [("schedule", r) for r in schedule_rows]
    used = counter.count(fixed_text)
    blocks, dropped = [], []
    # admit schedule rows first, then items in rank order
    for kind, obj in sorted(pool, key=lambda p: 0 if p[0] == "schedule" else 1):
        if kind == "item":
            item = EvidenceItem(0, "item", obj.chunk_id, item_label(obj.metadata),
                                obj.text, obj.metadata)
        else:
            item = EvidenceItem(0, "schedule", obj.row_id,
                                f"District data, {obj.province} {obj.district}, "
                                f"관리번호 {obj.row_id}, data date {obj.data_date}",
                                obj.to_evidence(waste_type),
                                {"data_date": obj.data_date, "phone": obj.phone,
                                 "office": obj.office, "stale": obj.is_stale()})
        cost = counter.count(f"[99] ({item.label})\n{item.text}\n\n")
        if used + cost > budget.input_budget:
            dropped.append(item.ref)
            continue
        used += cost
        blocks.append(item)
    # restore display order: items (by rank) first, then schedule rows
    blocks.sort(key=lambda e: 0 if e.kind == "item" else 1)
    for n, item in enumerate(blocks, 1):
        item.n = n
    record = {
        "tokenizer": counter.tokenizer_id if counter.exact else "char-estimate",
        "tokens_exact": counter.exact,
        "max_context": budget.max_context,
        "reserved_output": budget.reserved_output,
        "input_budget": budget.input_budget,
        "input_tokens_estimated": used,
        "fits": used <= budget.input_budget,
        "dropped_refs": dropped,
    }
    return blocks, "\n\n".join(b.block() for b in blocks), record
