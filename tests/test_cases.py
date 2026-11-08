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
