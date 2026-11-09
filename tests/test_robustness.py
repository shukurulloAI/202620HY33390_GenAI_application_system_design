"""Probe outcome labels (experiments/robustness.py)."""
from __future__ import annotations

from experiments.robustness import outcome, wrong_bin

CASE = {"case_id": "c1", "expected_bin": ["고철"]}


def _trace(status: str, bin_key: str = "") -> dict:
    return {"answer": {"status": status, "bin": bin_key}}


def test_an_answer_without_a_bin_counts_as_abstaining_on_the_item():
    withheld = _trace("ANSWER", "")             # schedule only, item part withheld
    assert outcome("clean", {"bin_ok": False}, withheld, CASE, None) == "abstained"
    assert outcome("negative", {"bin_ok": False}, withheld, CASE, None) == "abstained"
    assert outcome("counterfactual", {"bin_ok": False}, withheld, CASE, None) == "abstained"


def test_counterfactual_and_noise_labels():
    followed = _trace("ANSWER", wrong_bin(CASE["expected_bin"]))
    assert outcome("counterfactual", {"bin_ok": False}, followed, CASE, None) == \
        "followed the false chunk"
    assert outcome("noise", {"bin_ok": True}, _trace("ANSWER", "고철"), CASE, "고철") == "same bin"
    assert outcome("noise", {"bin_ok": False}, _trace("INSUFFICIENT_CONTEXT"), CASE, "") == \
        "abstained, as clean"
    assert outcome("noise", {"bin_ok": False}, _trace("INSUFFICIENT_CONTEXT"), CASE, "고철") == \
        "abstained (clean answered)"
    assert outcome("noise", {"bin_ok": False}, _trace("ANSWER", "종이"), CASE, "고철") == \
        "changed bin"
