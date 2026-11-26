"""Canonical bin names."""
from __future__ import annotations

from rag.bins import canonical_bin, evidence_bins


def test_canonical_bins():
    assert canonical_bin("종량제봉투 (종량제봉투)") == "종량제봉투"
    assert canonical_bin("일반쓰레기") == "종량제봉투"
    assert canonical_bin("대형") == "대형폐기물"
    assert canonical_bin("찌꺼기") is None
    assert evidence_bins({"doc_type": "rule", "item": "무색 폴리 에틸렌테레프탈 레이트 (PET)병"}) \
        == {"투명페트병"}
    assert evidence_bins({"doc_type": "item", "categories": "음식물, 종량제봉투"}) \
        == {"음식물", "종량제봉투"}


def test_a_2026_sub_item_that_is_a_bin_decides():
    """종이팩 sits under 골판지 외 종이류 in the 2026 table but has its own box."""
    assert evidence_bins({"doc_type": "rule", "item": "골판지 외 종이류",
                          "sub_item": "종이팩 (살균팩, 멸균팩)"}) == {"종이팩"}
    assert evidence_bins({"doc_type": "rule", "item": "골판지 외 종이류",
                          "sub_item": "신문지"}) == {"종이"}


def test_bins_named_in_text_longest_first():
    from rag.bins import bins_named_in
    assert bins_named_in("폐가전제품으로 배출") == {"가전제품"}
    assert bins_named_in("종이팩은 따로") == {"종이팩"}
    assert bins_named_in("Put it in the paper bin") == set()
