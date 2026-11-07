"""
Every location in the repository, in one place.

Layout rule: code folders hold code. Generated files go under data/ or experiments/results/,
and what each machine rebuilds for itself (the vector index, traces) is gitignored.
"""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# --- Data flow: raw -> interim -> processed (preprocess/). manual/ joins at the processed step.
DATA_DIR = ROOT / "data"
RAW_DIR = DATA_DIR / "raw"              # official sources, never edited
MANUAL_DIR = DATA_DIR / "manual"        # written by hand and reviewed, never generated
INTERIM_DIR = DATA_DIR / "interim"      # PDF parser output
PROCESSED_DIR = DATA_DIR / "processed"  # built by python -m preprocess.build_all
REPORT_DIR = DATA_DIR / "reports"       # data quality and index verification evidence
INDEX_REPORT_DIR = REPORT_DIR / "index"

GUIDE_2018_PDF = RAW_DIR / "item_guides" / "moe_recycling_guideline_2018.pdf"
ANNEX_2026_PDF = RAW_DIR / "item_guides" / "moe_separation_directive_annex1_2026.pdf"
RAW_SCHEDULE_CSV = RAW_DIR / "korean_waste_policies.csv"

GLOSSARY = MANUAL_DIR / "glossary.json"
FOOD_WASTE_TABLE = MANUAL_DIR / "food_waste_table_2018.json"

PARSED_ITEM_CHUNKS = INTERIM_DIR / "parsed_item_chunks.jsonl"

ITEM_CHUNKS = PROCESSED_DIR / "item_chunks.jsonl"
SCHEDULE_CSV = PROCESSED_DIR / "schedule.csv"
SCHEDULE_CHUNKS = PROCESSED_DIR / "schedule_chunks.jsonl"  # gitignored; only E4 reads it
DISTRICT_ALIASES = PROCESSED_DIR / "district_aliases.json"
DONG_LOOKUP = PROCESSED_DIR / "dong_lookup.json"
LOCATIONS = PROCESSED_DIR / "locations.json"
MANIFEST = PROCESSED_DIR / "manifest.json"

# --- Local state (gitignored)
QDRANT_DIR = ROOT / "qdrant_data"
PUBLISHED_INDEXES = QDRANT_DIR / "published.json"  # embedding key -> verified collection
TRACE_DIR = ROOT / "traces"

# --- Code assets
PROMPT_DIR = ROOT / "rag" / "prompts"

# --- Evaluation and experiments
DEV_CASES = ROOT / "eval" / "cases" / "dev.jsonl"
PROBES = ROOT / "experiments" / "probes" / "probes.jsonl"
SCHEDULE_PROBES = ROOT / "experiments" / "probes" / "probes_schedule.jsonl"
RESULTS_DIR = ROOT / "experiments" / "results"
PROBE_RESULTS_DIR = RESULTS_DIR / "probes"


def relative(path: Path) -> str:
    """Repo-relative form of a path, for manifests, traces and reports."""
    return path.relative_to(ROOT).as_posix()
