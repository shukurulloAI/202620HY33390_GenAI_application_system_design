"""The frozen evaluation set: valid cases, a split that matches its recorded hashes."""
from __future__ import annotations

import json

import pytest

from eval.cases import load_cases, validate_case
from eval.make_cases import MANIFEST, TEST_CASES, build
from rag import paths
from rag.files import sha256_file


def test_split_files_match_the_manifest():
    """Nobody edited dev.jsonl or test.jsonl after the split was frozen."""
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    assert manifest["frozen"]
    assert sha256_file(paths.DEV_CASES) == manifest["sha256"]["dev"]
    assert sha256_file(TEST_CASES) == manifest["sha256"]["test"]


def test_every_case_is_valid_and_unseen_cases_only_in_test():
    dev, test = load_cases(paths.DEV_CASES), load_cases(TEST_CASES)
    for case in dev + test:
        validate_case(case)
    assert not any(c["seen_in_development"] for c in test)
    assert not {c["case_id"] for c in dev} & {c["case_id"] for c in test}


def test_the_build_is_reproducible():
    rebuilt = build()
    assert [c["case_id"] for c in rebuilt if c["split"] == "test"] == \
        [c["case_id"] for c in load_cases(TEST_CASES)]


def test_validation_catches_bad_cases():
    case = load_cases(paths.DEV_CASES)[0]
    with pytest.raises(ValueError, match="unknown bins"):
        validate_case({**case, "expected_bin": ["plastic"]})
    with pytest.raises(ValueError, match="missing"):
        validate_case({k: v for k, v in case.items() if k != "slice"})


def _v2_case(**changes):
    case = {"case_id": "x1", "version": "v2", "split": "dev", "slice": "multi_item",
            "lang": "en", "question": "Pizza box and the leftover pizza?", "location": None,
            "waste_type": None, "expected_behavior": "answer", "expected_bin": ["종이", "음식물"],
            "expected_bins_all": ["종이", "음식물"], "expected_chunk_ids": [],
            "supporting_chunk_ids": [], "expected_schedule": None, "reference_facts": [],
            "seen_in_development": False, "notes": "", "source": "handwritten"}
    gold = load_cases(paths.DEV_CASES)[0]["expected_chunk_ids"]
    return {**case, "expected_chunk_ids": gold, **changes}


def test_v2_schema_checks_graded_gold_and_all_bins():
    validate_case(_v2_case())
    validate_case(_v2_case(slice="bulky", waste_type="bulky", expected_bins_all=[],
                           expected_bin=["대형폐기물"]))
    gold = _v2_case()["expected_chunk_ids"]
    with pytest.raises(ValueError, match="both required and supporting"):
        validate_case(_v2_case(supporting_chunk_ids=gold))
    with pytest.raises(ValueError, match="needs expected_bins_all"):
        validate_case(_v2_case(expected_bins_all=["종이"]))
    with pytest.raises(ValueError, match="expected_intent"):
        validate_case(_v2_case(expected_intent="items"))
    with pytest.raises(ValueError, match="gold answers"):
        validate_case(_v2_case(slice="no_evidence", expected_behavior="abstain", expected_bin=[],
                               expected_bins_all=[], expected_chunk_ids=[],
                               supporting_chunk_ids=gold))


def test_v2_templates_avoid_v1_items_and_districts():
    from eval.make_cases import V1, _chunks_by_legacy, sample_items, version
    v2 = version("v2")
    v1_gold = {g for path in (V1.dev, V1.test) for c in load_cases(path)
               for g in c["gold_legacy_ids"]}
    picked = sample_items(_chunks_by_legacy(), v2)
    assert len(picked) == v2.n_items and not set(picked) & v1_gold
    assert len(v2.template_langs) == v2.n_items + v2.n_schedule
    assert {"성동구", "광진구"} <= v2.used_districts and v2.out_dir.name == "v2"


def test_v2_files_are_valid_reproducible_and_keep_seen_cases_in_dev():
    from eval.make_cases import _dump, build, version
    v2 = version("v2")
    if not v2.dev.exists():
        pytest.skip("v2 not built yet")
    dev, test = load_cases(v2.dev), load_cases(v2.test)
    for case in dev + test:
        validate_case(case)
    assert len(dev) + len(test) == json.loads(v2.manifest.read_text(encoding="utf-8"))["n"]["all"]
    assert not any(c["seen_in_development"] for c in test)
    rebuilt = build(v2)
    assert _dump([c for c in rebuilt if c["split"] == "test"]) == v2.test.read_text(encoding="utf-8")
    manifest = json.loads(v2.manifest.read_text(encoding="utf-8"))
    if manifest["frozen"]:
        assert sha256_file(v2.dev) == manifest["sha256"]["dev"]
        assert sha256_file(v2.test) == manifest["sha256"]["test"]
