"""
Evaluation cases (PLAN.md §7.1) and the developer probes, which share most of the schema.

A case, as eval/make_cases.py writes it:

    case_id, version, split (dev | test), slice, lang, question, source (handwritten | template)
    location            {province?, district, dong?} given as dropdown input, or null: the
                        question itself names the place (or none)
    waste_type          general | food | recycling | null
    expected_behavior   answer | abstain | clarify | out_of_scope
    expected_bin        canonical bins (rag/bins.py) any of which is correct; [] if no bin
    expected_chunk_ids  gold chunk UUIDs (gold_legacy_ids: the same, readable). From v2 these
                        are the required chunks (they state the bin or method for this item,
                        eval/cases/LABELLING.md); Recall@k counts only them
    supporting_chunk_ids  v2, optional: chunks that help but do not by themselves answer
                        (group rules, guide pages); they count for precision and nDCG only
    expected_bins_all   v2, optional: every one of these bins must be named in the answer
                        (multi_item: one per item; vague_item: one per likely kind)
    expected_intent     v2, optional: the router intent, when the slice does not decide it
    analogy             v2 analogy slice: true = the guides do not list the item, and the answer
                        should say so and reason from the very similar item in the gold chunks;
                        false = a look-alike trap that must not be answered by analogy
    expected_schedule   {row_ids: [...], place?: {...}} or null
    reference_facts     what a correct answer says, in English, for the judge and the audit
    seen_in_development the item or place was used in the probes or the website examples
    notes
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from rag import paths
from rag.bins import BINS
from rag.files import read_jsonl
from rag.texts import LANGUAGES

SLICES = ("item_direct", "item_tricky", "schedule", "combined", "conflict", "no_evidence",
          "false_premise", "ambiguous_location", "out_of_scope", "real_users",
          # v2. natural_phrasing is written by us in the way people write (chatty, typos,
          # romanized Korean); real_users stays for questions actually collected from users.
          "multi_item", "condition", "vague_item", "bulky", "natural_phrasing", "analogy")
ITEM_SLICES = ("item_direct", "item_tricky", "conflict", "false_premise", "multi_item",
               "condition", "vague_item", "bulky", "natural_phrasing", "real_users", "combined")
BEHAVIOURS = ("answer", "abstain", "clarify", "out_of_scope")
WASTE_TYPES = ("general", "food", "recycling", "bulky", None)
INTENTS = ("item", "schedule", "both", "out_of_scope")
REQUIRED = ("case_id", "version", "split", "slice", "lang", "question", "location", "waste_type",
            "expected_behavior", "expected_bin", "expected_chunk_ids", "expected_schedule",
            "reference_facts", "seen_in_development", "notes", "source")


def load_cases(path: Path) -> list[dict]:
    return read_jsonl(path)


def case_id(case: dict) -> str | None:
    return case.get("case_id") or case.get("probe_id")


def by_id(cases: list[dict]) -> dict:
    return {case_id(c): c for c in cases}


def default_cases() -> Path:
    """The dev split once it exists, otherwise the developer probes."""
    return paths.DEV_CASES if paths.DEV_CASES.exists() else paths.PROBES


def gold_chunks(case: dict) -> list[str]:
    """UUID chunk IDs or legacy IDs (e.g. item2018_0278); both are matched."""
    return case.get("expected_chunk_ids") or case.get("gold_chunks") or []


@lru_cache(maxsize=1)
def _known_chunks() -> set[str]:
    return {c["id"] for c in read_jsonl(paths.ITEM_CHUNKS)}


@lru_cache(maxsize=1)
def _known_rows() -> set[str]:
    from rag.schedule_tool import default_table
    return set(default_table().by_id)


def validate_case(case: dict) -> None:
    """Raise ValueError if the case does not fit the schema or points at unknown data."""
    cid = case.get("case_id")
    problems = [f"missing {k}" for k in REQUIRED if k not in case]
    if problems:
        raise ValueError(f"{cid}: {problems}")
    if case["split"] not in ("dev", "test"):
        problems.append(f"split {case['split']!r}")
    if case["slice"] not in SLICES:
        problems.append(f"slice {case['slice']!r}")
    if case["lang"] not in LANGUAGES:
        problems.append(f"lang {case['lang']!r}")
    if case["expected_behavior"] not in BEHAVIOURS:
        problems.append(f"expected_behavior {case['expected_behavior']!r}")
    if case["waste_type"] not in WASTE_TYPES:
        problems.append(f"waste_type {case['waste_type']!r}")
    if not case["question"].strip():
        problems.append("empty question")
    unknown_bins = [b for b in case["expected_bin"] if b not in BINS]
    if unknown_bins:
        problems.append(f"unknown bins {unknown_bins}")
    supporting = case.get("supporting_chunk_ids") or []
    unknown_chunks = [c for c in case["expected_chunk_ids"] + supporting
                      if c not in _known_chunks()]
    if unknown_chunks:
        problems.append(f"unknown chunks {unknown_chunks}")
    if set(supporting) & set(case["expected_chunk_ids"]):
        problems.append("a chunk is both required and supporting")
    all_bins = case.get("expected_bins_all") or []
    if [b for b in all_bins if b not in BINS]:
        problems.append(f"unknown bins in expected_bins_all {all_bins}")
    if (case["slice"] in ("multi_item", "vague_item") and case["expected_behavior"] == "answer"
            and len(all_bins) < 2):
        problems.append(f"a {case['slice']} answer needs expected_bins_all with 2+ bins")
    if case["slice"] == "analogy" and not isinstance(case.get("analogy"), bool):
        problems.append("an analogy case needs analogy: true or false")
    if case.get("analogy") is True and not (case["expected_behavior"] == "answer"
                                            and case["expected_chunk_ids"]):
        problems.append("an analogy answer needs the similar item's chunks as gold")
    if case.get("analogy") is False and case["expected_behavior"] == "answer":
        problems.append("an analogy trap must not be answered")
    if case.get("expected_intent") not in (None, *INTENTS):
        problems.append(f"expected_intent {case.get('expected_intent')!r}")
    schedule = case["expected_schedule"]
    if schedule and [r for r in schedule["row_ids"] if r not in _known_rows()]:
        problems.append("unknown schedule rows")
    answerable = case["expected_behavior"] == "answer"
    item_part = case["slice"] != "schedule" and case.get("expected_intent") != "schedule"
    if answerable and item_part and not case["expected_bin"]:
        problems.append("an item answer needs expected_bin")
    if answerable and item_part and not case["expected_chunk_ids"]:
        problems.append("an item answer needs gold chunks")
    if case["slice"] in ("schedule", "combined") and not schedule:
        problems.append("a schedule case needs expected_schedule")
    if not answerable and (case["expected_bin"] or case["expected_chunk_ids"] or supporting):
        problems.append("a case that should not be answered has gold answers")
    location = case["location"]
    if location is not None and not location.get("district"):
        problems.append("location without district")
    if problems:
        raise ValueError(f"{cid}: {problems}")
