"""
Output validation (PLAN.md §4.9; Lesson 7, Siemens: validate generated output before use).

Checks on the parsed answer, after the JSON/citation checks in generate.parse_answer:

    bin_known        `bin` is in the canonical vocabulary (rag/bins.py) or empty
    bin filled       an item ANSWER with an empty bin gets the one bin its text names, or
                     else the one bin the cited chunks state (never one the text contradicts)
    bin_text_conflict  the bin field differs from the bin(s) named in answer_text
    bin_supported    the bin is one the cited chunks state (categories / 2026 group); only
                     if they state none, one of its names must appear in their text
    cited            an ANSWER cites at least one evidence block
    schedule_days    weekdays named in answer_text are days the tool returned

Modes (PipelineConfig.validation):
    off      no checks
    flag     record the checks in the trace only
    enforce  also downgrade ANSWER -> INSUFFICIENT_CONTEXT when the bin is unknown or
             unsupported, or the answer cites nothing. A wrong bin costs the user more
             than an abstention (PLAN.md §4.6), so a failed check means "do not answer".
"""
from __future__ import annotations

import re

from rag.bins import BINS, canonical_bin, evidence_bins, names_for

_DAY_PATTERNS = {
    0: r"\bmon(day)?\b|월요일", 1: r"\btue(s|sday)?\b|화요일", 2: r"\bwed(nesday)?\b|수요일",
    3: r"\bthu(r|rs|rsday)?\b|목요일", 4: r"\bfri(day)?\b|금요일",
    5: r"\bsat(urday)?\b|토요일", 6: r"\bsun(day)?\b|일요일",
}


def text_bins(text: str) -> set[str]:
    """Canonical bins named in parentheses in the answer, e.g. 'general waste bag (종량제봉투)'."""
    return {b for t in re.findall(r"\(([^()]+)\)", text or "") if (b := canonical_bin(t))}


def days_mentioned(text: str) -> set[int]:
    text = (text or "").lower()
    return {d for d, pattern in _DAY_PATTERNS.items() if re.search(pattern, text)}


def validate(answer: dict, evidence: list, schedule_days: set[int] | None,
             mode: str = "enforce", item_question: bool = True) -> tuple[dict, dict]:
    """Returns (answer, checks). `evidence` = EvidenceItems shown to the model;
    `schedule_days` = weekdays the tool returned for the asked waste type(s);
    `item_question` = the question asks about an item (so an answer needs a bin)."""
    if mode == "off":
        return answer, {"mode": "off"}
    checks = {"mode": mode, "bin_raw": answer.get("bin", ""), "bin": "",
              "bin_known": True, "bin_supported": None, "cited": True,
              "schedule_days_ok": None, "downgraded": False, "reasons": []}
    status = answer.get("status")
    by_n = {e.n: e for e in evidence}
    cited = [by_n[n] for n in answer.get("citations", []) if n in by_n]

    raw_bin = (answer.get("bin") or "").strip()
    bin_key = canonical_bin(raw_bin) if raw_bin else ""
    named = text_bins(answer.get("answer_text", ""))
    stated = set().union(*(evidence_bins(e.metadata) for e in cited if e.kind == "item"))
    checks["bins_in_text"], checks["bins_in_evidence"] = sorted(named), sorted(stated)
    if status == "ANSWER" and not raw_bin and item_question:
        # The model left the bin empty. The user reads the text, so use the one bin the
        # text names; else the one bin the cited chunks state, if the text does not
        # name a different one.
        if len(named) == 1:
            bin_key = next(iter(named))
            checks["bin_filled_from_text"] = bin_key
        elif len(stated) == 1 and (not named or stated <= named):
            bin_key = next(iter(stated))
            checks["bin_filled_from_evidence"] = bin_key
        else:
            checks["bin_missing"] = sorted(stated)
    if status == "ANSWER" and bin_key and named and bin_key not in named:
        checks["bin_text_conflict"] = True
        checks["reasons"].append(f"bin '{bin_key}' but the answer text names {sorted(named)}")
    if raw_bin and bin_key is None:
        checks["bin_known"] = False
        checks["reasons"].append(f"bin '{raw_bin}' is not a known category")
    checks["bin"] = bin_key or ""

    if status == "ANSWER" and bin_key:
        texts = re.sub(r"\s+", "", " ".join(e.text for e in cited))
        in_text = any(name.replace(" ", "") in texts for name in names_for(bin_key))
        # When the cited chunks state bins (categories / 2026 group), the bin must be one
        # of them: a passing mention in running text (e.g. an exception "else 종량제봉투"
        # on a guide page) is not enough. Text matching is only the fallback for cited
        # chunks that state no bin (guide pages, FAQ).
        checks["bin_supported"] = bin_key in stated if stated else in_text
        if not checks["bin_supported"]:
            checks["reasons"].append(f"bin '{bin_key}' is not stated in the cited evidence"
                                     + (f" (they state {sorted(stated)})" if stated else ""))

    if status == "ANSWER" and not cited:
        checks["cited"] = False
        checks["reasons"].append("answer cites no evidence")

    if schedule_days is not None and status == "ANSWER":
        named = days_mentioned(answer.get("answer_text", ""))
        wrong = sorted(named - schedule_days)
        checks["schedule_days_ok"] = not wrong
        if wrong:
            checks["reasons"].append(f"answer names days the tool did not return: {wrong}")

    answer = dict(answer)
    if bin_key:
        answer["bin"], answer["bin_en"] = bin_key, BINS[bin_key]
    failed = (not checks["bin_known"] or checks["bin_supported"] is False
              or not checks["cited"] or checks.get("bin_text_conflict", False))
    if mode == "enforce" and status == "ANSWER" and failed:
        checks["downgraded"] = True
        answer.update(status="INSUFFICIENT_CONTEXT", bin="", bin_en="",
                      missing="the answer could not be verified against the evidence: "
                              + "; ".join(checks["reasons"]))
    return answer, checks
