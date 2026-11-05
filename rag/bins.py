"""
Canonical bin vocabulary (PLAN.md §4.9).

The generator's `bin` must be one of these keys. The keys are the 2018 national
dictionary categories (`categories` in item chunks) plus the 2026 separate groups,
so the value can be checked against the cited evidence and scored exactly in
evaluation (bin correctness, PLAN.md §7.3). English names are fixed here, so
`bin_en` no longer depends on the model.
"""
from __future__ import annotations

import re

BINS: dict[str, str] = {
    "종이": "paper",
    "종이팩": "paper cartons (milk / juice cartons)",
    "금속캔": "metal cans",
    "고철": "scrap metal",
    "유리병": "glass bottles",
    "플라스틱": "plastics",
    "투명페트병": "clear PET bottles (collected separately)",
    "비닐": "plastic film and bags",
    "발포합성수지": "styrofoam",
    "의류": "clothing collection bin",
    "가전제품": "waste electronics and appliances",
    "대형폐기물": "bulky waste (disposal sticker required)",
    "음식물": "food waste",
    "종량제봉투": "general waste (pay-as-you-throw bag)",
    "불연성종량제": "non-combustible waste bag (특수규격마대)",
    "전용함": "dedicated collection box (e.g. batteries, lamps, medicine)",
    "전문시설": "specialised facility or retailer take-back",
    "재질별분리": "separate the parts by material",
}

# Other names for the same bin: model outputs, 2026 group names, everyday words.
ALIASES: dict[str, str] = {
    "대형": "대형폐기물", "대형생활폐기물": "대형폐기물",
    "음식물쓰레기": "음식물", "음식물류폐기물": "음식물", "음식물류": "음식물",
    "일반쓰레기": "종량제봉투", "생활쓰레기": "종량제봉투", "종량제": "종량제봉투",
    "일반종량제봉투": "종량제봉투", "쓰레기종량제봉투": "종량제봉투", "종량제봉투(일반쓰레기)": "종량제봉투",
    "전용수거함": "전용함", "전지수거함": "전용함", "폐의약품수거함": "전용함",
    "음식물전용용기": "음식물", "전용용기": "음식물",
    "불연성종량제봉투": "불연성종량제", "특수규격마대": "불연성종량제", "불연성마대": "불연성종량제",
    "스티로폼": "발포합성수지", "발포합성": "발포합성수지", "발포스티렌": "발포합성수지",
    "무색페트병": "투명페트병", "투명pet병": "투명페트병",
    "종이류": "종이", "골판지류": "종이", "골판지외종이류": "종이", "골판지": "종이",
    "캔류": "금속캔", "금속캔류": "금속캔", "고철류": "고철",
    "유리병류": "유리병",
    "플라스틱류": "플라스틱", "합성수지용기·트레이류": "플라스틱", "합성수지류": "플라스틱",
    "비닐류": "비닐", "합성수지비닐류": "비닐",
    "의류및원단류": "의류", "원단류": "의류",
    "전기·전자제품": "가전제품", "전자제품": "가전제품", "폐가전제품": "가전제품",
    "전지류": "전용함", "전지": "전용함", "조명제품": "전용함",
}


def _key(text: str) -> str:
    return re.sub(r"\s+", "", re.sub(r"\(.*?\)", "", text or "")).lower()


_LOOKUP = {**{_key(k): k for k in BINS}, **{_key(k): v for k, v in ALIASES.items()}}


def canonical_bin(text: str) -> str | None:
    """Map a bin name to its canonical key, or None if it is not a known bin."""
    key = _key(text)
    if not key:
        return None
    if key in _LOOKUP:
        return _LOOKUP[key]
    if re.search(r"(무색|투명).*(pet|페트)", re.sub(r"\s+", "", text).lower()):
        return "투명페트병"
    return None


def evidence_bins(metadata: dict) -> set[str]:
    """Bins a chunk states explicitly: its 2018 `categories`, or its 2026 rule group."""
    found = set()
    for part in (metadata.get("categories") or "").split(","):
        if canonical_bin(part):
            found.add(canonical_bin(part))
    if metadata.get("doc_type") == "rule":
        sub = re.sub(r"\s+", "", metadata.get("sub_item", ""))
        # The 2026 integrated-collection table files styrofoam under 합성 수지류, but it
        # is still put out separately (발포합성수지), so the sub-item decides.
        group = ("발포합성수지" if "스티로폼" in sub else None) \
            or canonical_bin(metadata.get("item", "")) \
            or canonical_bin(f"{metadata.get('item', '')} {metadata.get('sub_item', '')}")
        if group:
            found.add(group)
    return found


def names_for(bin_key: str) -> list[str]:
    """The canonical key and all aliases, for text search in evidence."""
    return [bin_key] + [alias for alias, target in ALIASES.items() if target == bin_key]
