"""Validation of generated answers."""
from __future__ import annotations

from rag.bins import evidence_bins
from rag.context import EvidenceItem
from rag.validate import validate


def test_validate_downgrades_unsupported_bin():
    ev = [EvidenceItem(1, "item", "item2018_0010", "src", "[분리배출 품목] 계란껍질\n구분: 종량제봉투",
                       {"doc_type": "item", "categories": "종량제봉투"})]
    answer = {"status": "ANSWER", "bin": "음식물", "citations": [1], "answer_text": "x"}
    out, checks = validate(answer, ev, None, "enforce")
    assert checks["downgraded"] and out["status"] == "INSUFFICIENT_CONTEXT"
    out, checks = validate(answer, ev, None, "flag")
    assert not checks["downgraded"] and out["status"] == "ANSWER"


def test_validate_fills_empty_bin():
    ev = [EvidenceItem(1, "item", "item2018_0207", "src", "전지 구분: 전용함",
                       {"doc_type": "item", "categories": "전용함"})]
    out, checks = validate({"status": "ANSWER", "bin": "", "citations": [1],
                            "answer_text": "box [1]"}, ev, None, "enforce")
    assert out["bin"] == "전용함" and checks["bin_filled_from_evidence"] == "전용함"


def test_validate_bin_must_match_text_and_evidence():
    # p13: the 2026 table files styrofoam under 합성 수지류, but it goes out separately.
    meta = {"doc_type": "rule", "item": "합성 수지류", "sub_item": "스티로폼 완충재"}
    assert evidence_bins(meta) == {"발포합성수지"}
    ev = [EvidenceItem(1, "item", "rule2026_028", "src", "스티로폼 완충재 ... 종량제 봉투", meta)]
    # Empty bin, text names 종량제봉투, evidence states 발포합성수지 -> abstain.
    a, c = validate({"status": "ANSWER", "bin": "", "citations": [1],
                     "answer_text": "Put it in a general waste bag (종량제봉투) [1]."}, ev, None)
    assert a["status"] == "INSUFFICIENT_CONTEXT" and c["bin_supported"] is False
    # Bin field contradicts the text -> abstain.
    a, c = validate({"status": "ANSWER", "bin": "발포합성수지", "citations": [1],
                     "answer_text": "Put it in a general waste bag (종량제봉투) [1]."}, ev, None)
    assert a["status"] == "INSUFFICIENT_CONTEXT" and c["bin_text_conflict"]
    # v3 p06: the model's bin is only mentioned in running text, not stated -> abstain.
    guide = EvidenceItem(2, "item", "guide2018_p12", "src", "... 쓰레기종량제 봉투로 배출 ...",
                         {"doc_type": "guide"})
    a, c = validate({"status": "ANSWER", "bin": "종량제봉투", "citations": [1, 2],
                     "answer_text": "Put it in a general waste bag (종량제봉투) [1,2]."},
                    ev + [guide], None)
    assert a["status"] == "INSUFFICIENT_CONTEXT" and c["bin_supported"] is False
    # Text and evidence agree -> the empty bin is filled from the text.
    a, c = validate({"status": "ANSWER", "bin": "", "citations": [1],
                     "answer_text": "Rinse it and put it out as styrofoam (스티로폼) [1]."}, ev, None)
    assert a["status"] == "ANSWER" and a["bin"] == "발포합성수지"


def test_invented_schedule_is_refused():
    """The generator copied its few-shot example's days for a place with no schedule."""
    evidence = [EvidenceItem(1, "item", "c1", "guide", "피자박스 구분: 종이", {"categories": "종이"})]
    answer = {"status": "ANSWER", "bin": "종이", "citations": [1],
              "answer_text": "Paper bin (종이) [1]. Food waste: Tue, Thu or Sat, 19:00-23:00."}
    out, checks = validate(answer, evidence, set(), "enforce")
    assert checks["schedule_invented"] and out["status"] == "INSUFFICIENT_CONTEXT"
    out, checks = validate({**answer, "answer_text": "Between 19:00-23:00, paper bin (종이) [1]."},
                           evidence, set(), "enforce")
    assert checks["schedule_invented"]                  # a clock time alone counts
    clean = {**answer, "answer_text": "Paper bin (종이) [1]."}
    assert validate(clean, evidence, set(), "enforce")[0]["status"] == "ANSWER"
    # An item-only question is not checked: None means no schedule was asked for.
    assert validate(answer, evidence, None, "enforce")[0]["status"] == "ANSWER"
    # With rows shown, a day they contain is fine.
    assert validate(answer, evidence, {1, 3, 5}, "enforce")[0]["status"] == "ANSWER"
