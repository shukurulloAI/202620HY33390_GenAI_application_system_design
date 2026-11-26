"""
Grounded answer generation (PLAN.md §4.8; Lessons 1, 2, 4).

Prompts live in rag/prompts/answer_<version>.md with SYSTEM and USER sections, so
every trace records which prompt version produced an answer (E1 compares versions).
The model must return JSON matching answer_schema(version); Ollama enforces the schema.

From v6 the model returns `items`, one entry per item or part (its bin, steps and
citations), so a question about several items gets several bins. parse_answer turns every
version's output into the same shape: `items` plus the first item's bin and steps in the
v5 fields `bin` / `how_to_prepare`, which the rest of the system still reads.
"""
from __future__ import annotations

import json
import re
from functools import lru_cache

from rag import paths
from rag.bins import BINS

LANGUAGE_NAMES = {"en": "English", "ko": "Korean", "zh": "Chinese", "uz": "Uzbek",
                  "vi": "Vietnamese", "ru": "Russian", "ja": "Japanese"}
STATUSES = ("ANSWER", "INSUFFICIENT_CONTEXT")

ANSWER_SCHEMA = {
    "type": "object",
    "properties": {
        "status": {"type": "string", "enum": list(STATUSES)},
        "bin": {"type": "string", "enum": [""] + list(BINS)},   # constrained decoding
        "bin_en": {"type": "string"},
        "how_to_prepare": {"type": "array", "items": {"type": "string"}},
        "answer_text": {"type": "string"},
        "citations": {"type": "array", "items": {"type": "integer"}},
        "missing": {"type": "string"},
    },
    "required": ["status", "bin", "bin_en", "how_to_prepare", "answer_text",
                 "citations", "missing"],
}

ITEM_SCHEMA = {
    "type": "object",
    "properties": {
        "item": {"type": "string"},
        "bin": {"type": "string", "enum": list(BINS)},
        "how_to_prepare": {"type": "array", "items": {"type": "string"}},
        "citations": {"type": "array", "items": {"type": "integer"}},
    },
    "required": ["item", "bin", "how_to_prepare", "citations"],
}
ANSWER_SCHEMA_V6 = {
    "type": "object",
    "properties": {
        "status": {"type": "string", "enum": list(STATUSES)},
        "items": {"type": "array", "items": ITEM_SCHEMA},
        "answer_text": {"type": "string"},
        "citations": {"type": "array", "items": {"type": "integer"}},
        "missing": {"type": "string"},
    },
    "required": ["status", "items", "answer_text", "citations", "missing"],
}


def answer_schema(version: str) -> dict:
    """The JSON schema the model's output must follow for this prompt version."""
    return ANSWER_SCHEMA_V6 if _version_number(version) >= 6 else ANSWER_SCHEMA


def _version_number(version: str) -> int:
    match = re.match(r"v(\d+)", version or "")
    return int(match.group(1)) if match else 0


@lru_cache(maxsize=8)
def load_prompt(name: str) -> tuple[str, str]:
    """(system, user) of rag/prompts/<name>.md. HTML comments are notes for us, not the LLM."""
    raw = (paths.PROMPT_DIR / f"{name}.md").read_text(encoding="utf-8")
    raw = re.sub(r"<!--.*?-->", "", raw, flags=re.S)
    system, user = raw.split("=== USER ===")
    return system.replace("=== SYSTEM ===", "").strip(), user.strip()


CONFLICT_RULES = {
    "prefer_2026": ("- If a 2026 rule and a 2018 rule disagree, follow the 2026 rule and say "
                    "that the rule changed in 2026."),
    "none": "",
}


def build_prompt(version: str, question: str, evidence_text: str,
                 lang: str | None, conflict_policy: str = "prefer_2026") -> tuple[str, str]:
    system, user = load_prompt(f"answer_{version}")
    language = LANGUAGE_NAMES.get(lang or "", "the same language as the question")
    prompt = (user.replace("{conflict_rule}\n", CONFLICT_RULES[conflict_policy] + "\n"
                           if CONFLICT_RULES[conflict_policy] else "")
                  .replace("{evidence}", evidence_text or "(no evidence found)")
                  .replace("{language}", language)
                  .replace("{question}", question))
    return system, prompt


def parse_answer(text: str, n_evidence: int) -> tuple[dict, dict]:
    """Parse the model's JSON and check the contract. Returns (answer, checks)."""
    checks = {"json_valid": True, "status_valid": True, "invalid_citations": [],
              "uncited_answer": False}
    try:
        answer = json.loads(text)
        if not isinstance(answer, dict):
            raise ValueError("not an object")
    except (json.JSONDecodeError, ValueError):
        checks["json_valid"] = False
        return {"status": "INVALID_OUTPUT", "bin": "", "bin_en": "", "how_to_prepare": [],
                "items": [], "answer_text": "", "citations": [],
                "missing": "model output was not JSON"}, checks
    if answer.get("status") not in STATUSES:
        checks["status_valid"] = False
    cited = []
    for n in answer.get("citations") or []:
        if isinstance(n, int) and 1 <= n <= n_evidence:
            cited.append(n)
        else:
            checks["invalid_citations"].append(n)
    # numbers cited inline in the text count too
    for n in re.findall(r"\[(\d+)\]", answer.get("answer_text", "")):
        n = int(n)
        if 1 <= n <= n_evidence and n not in cited:
            cited.append(n)
        elif not 1 <= n <= n_evidence:
            checks["invalid_citations"].append(n)
    answer["citations"] = sorted(set(cited))
    answer["items"] = _items(answer, n_evidence, checks)
    first = answer["items"][0] if answer["items"] else {}
    answer["bin"] = first.get("bin", answer.get("bin") or "")
    answer["bin_en"] = BINS.get(answer["bin"], answer.get("bin_en") or "")
    answer["how_to_prepare"] = first.get("how_to_prepare", answer.get("how_to_prepare") or [])
    checks["uncited_answer"] = answer.get("status") == "ANSWER" and not cited
    return answer, checks


def _items(answer: dict, n_evidence: int, checks: dict) -> list[dict]:
    """The `items` list for any prompt version. v6 output is cleaned (citation numbers out of
    range dropped, entries without a bin skipped); v5 output, which has one bin, becomes one
    entry with the answer's own citations."""
    if "items" not in answer:
        if not answer.get("bin"):
            return []
        return [{"item": "", "bin": answer["bin"],
                 "how_to_prepare": list(answer.get("how_to_prepare") or []),
                 "citations": list(answer["citations"])}]
    items = []
    for entry in answer.get("items") or []:
        if not isinstance(entry, dict) or not entry.get("bin"):
            continue
        cites = []
        for n in entry.get("citations") or []:
            if isinstance(n, int) and 1 <= n <= n_evidence:
                cites.append(n)
            else:
                checks["invalid_citations"].append(n)
        items.append({"item": str(entry.get("item") or ""), "bin": str(entry["bin"]),
                      "how_to_prepare": [str(s) for s in entry.get("how_to_prepare") or []],
                      "citations": sorted(set(cites))})
    return items
