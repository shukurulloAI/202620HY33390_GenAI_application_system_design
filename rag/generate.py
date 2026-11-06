"""
Grounded answer generation (PLAN.md §4.8; Lessons 1, 2, 4).

Prompts live in rag/prompts/answer_<version>.md with SYSTEM and USER sections, so
every trace records which prompt version produced an answer (E1 compares versions).
The model must return JSON matching ANSWER_SCHEMA; Ollama enforces the schema.
"""
from __future__ import annotations

import json
import re
from functools import lru_cache

from rag import config
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


@lru_cache(maxsize=8)
def load_prompt(name: str) -> tuple[str, str]:
    raw = (config.PROMPT_DIR / f"{name}.md").read_text(encoding="utf-8")
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
                "answer_text": "", "citations": [], "missing": "model output was not JSON",
                }, checks
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
    checks["uncited_answer"] = answer.get("status") == "ANSWER" and not cited
    return answer, checks
