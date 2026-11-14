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


def test_a_row_that_excludes_clear_pet_bottles_is_plastics():
    """The 2026 row "무색 투명한 ... PET병을 제외한 PET 용기 ..." names clear PET bottles only
    to exclude them; it is the plastics group, not the clear-PET bin."""
    excluding = "무색 투명한 먹는샘물, 음료 폴리에틸렌테레 프탈레이트(PET)병을 제외한 PET 용기"
    assert canonical_bin(excluding) is None
    assert evidence_bins({"doc_type": "rule", "item": "합성수지 용기· 트레이류",
                          "sub_item": excluding}) == {"플라스틱"}
    assert evidence_bins({"doc_type": "rule", "item": "합성 수지류",
                          "sub_item": f"PVC, PE 재질의용기, {excluding}"}) == {"플라스틱"}
    # The clear-PET row itself keeps its bin.
    assert canonical_bin("무색 투명한 먹는샘물, 음료 폴리에틸렌테레 프탈레이트(PET)병") == "투명페트병"
