"""Intervals and the paired test, checked against values computed by hand."""
from __future__ import annotations

import pytest

from eval.compare import compare
from eval.stats import mcnemar_exact, wilson


def test_wilson_interval():
    low, high = wilson(22, 30)
    assert low == pytest.approx(0.5555, abs=1e-4) and high == pytest.approx(0.8582, abs=1e-4)
    assert wilson(0, 5)[0] == 0.0 and wilson(5, 5)[1] == 1.0
    assert wilson(0, 0) is None


def test_mcnemar_exact():
    assert mcnemar_exact(13, 2) == pytest.approx(0.00739, abs=1e-5)   # test-final vs baseline
    assert mcnemar_exact(0, 3) == pytest.approx(0.25)
    assert mcnemar_exact(0, 0) == 1.0
    assert mcnemar_exact(5, 5) == 1.0


def test_compare_pairs_cases_and_skips_undefined():
    a = {"c1": {"case_ok": True, "bin_ok": None}, "c2": {"case_ok": True, "bin_ok": True}}
    b = {"c1": {"case_ok": False, "bin_ok": True}, "c2": {"case_ok": True, "bin_ok": False}}
    result = compare(a, b)
    assert result["case_ok"]["only_a"] == 1 and result["case_ok"]["only_b"] == 0
    assert result["bin_ok"]["n"] == 1                     # c1 has no bin in A
    with pytest.raises(ValueError):
        compare(a, {"c1": b["c1"]})
