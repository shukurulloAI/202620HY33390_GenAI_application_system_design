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
