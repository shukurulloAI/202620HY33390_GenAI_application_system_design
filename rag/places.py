"""
Place reader: the district and neighbourhood a question names, read by code from the
district table's own names (Lesson 1: deterministic logic for a fixed rule), before the
router's guess. On dev v2 the router read only about half of the districts and a quarter of
the neighbourhoods that questions named ("Guro-gu", "Пучхон", "부천 송내1동").

Spellings, all made from the table's Korean names:
    Korean       구로구 / 구로, 송내1동 / 송내동
    romanised    guro-gu / guro, songnae 1-dong (Revised Romanization, rag/korean.romanize)
    Cyrillic     Гуро-гу, Пучхон, Вонджон 2-дон (Kontsevich, the system Russian speakers
                 use); a Russian case ending may follow ("в Кванмёне")
Not covered: Chinese-character names (富平区 for 부평구); the router still reads those.

Guards against false hits: a one-syllable district (중구, 서구) only with its suffix
(Jung-gu, Seo-gu), a neighbourhood only with its suffix (-dong, 동, -дон). A district name
in several provinces is returned with every province, so the schedule tool asks which
(unless the question names the province). A neighbourhood named without a district is used
only if one district has it.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from functools import lru_cache

from rag.korean import romanize

# ---------------------------------------------------------------------------- Cyrillic

_CYR_INITIAL = ["к", "кк", "н", "т", "тт", "р", "м", "п", "пп", "с", "сс", "", "ч", "чч",
                "чх", "кх", "тх", "пх", "х"]
_CYR_VOICED = {0: "г", 3: "д", 7: "б", 12: "дж"}       # ㄱ ㄷ ㅂ ㅈ inside a word
_CYR_VOWEL = ["а", "э", "я", "йя", "о", "е", "ё", "е", "о", "ва", "вэ", "ве", "ё", "у", "во",
              "ве", "ви", "ю", "ы", "ый", "и"]
_CYR_FINAL = ["", "к", "к", "к", "н", "н", "н", "т", "ль", "к", "м", "ль", "ль", "ль", "п",
              "ль", "м", "п", "п", "т", "т", "н", "т", "т", "к", "т", "п", "т"]


def cyrillic(word: str) -> str:
    """'부천' -> 'пучхон', '영등포' -> 'ёндынпхо', '원종2동' -> 'вонджон2дон' (Kontsevich)."""
    out, prev_final = [], None
    for ch in word:
        code = ord(ch) - 0xAC00
        if not 0 <= code < 11172:
            out.append(ch.lower())
            prev_final = None
            continue
        ini, vow, fin = code // 588, (code % 588) // 28, code % 28
        initial = _CYR_INITIAL[ini]
        if prev_final is not None and ini in _CYR_VOICED:     # voiced between sounds
            initial = _CYR_VOICED[ini]
        if ini == 5 and prev_final in (8,):                   # ㄹ + ㄹ
            initial = "л"
        out.append(initial + _CYR_VOWEL[vow] + _CYR_FINAL[fin])
        prev_final = fin
    return "".join(out)


def _fold(text: str) -> str:
    """Spellings people mix up, made equal: ё/э -> е, й -> и, ь dropped."""
    return text.lower().translate(str.maketrans({"ё": "е", "э": "е", "й": "и", "ь": None}))


# ---------------------------------------------------------------------------- index

@dataclass
class Place:
    district: str | None = None
    provinces: list[str] = field(default_factory=list)
    dong: str | None = None
    matched: str = ""                        # the spelling found in the question

    def to_trace(self) -> dict:
        return {"district": self.district, "provinces": self.provinces, "dong": self.dong,
                "matched": self.matched}


_DISTRICT_SUFFIX = {"구": ("gu", "гу"), "군": ("gun", "гун"), "시": ("si", "си")}
_AREA = re.compile(r"^[가-힣]{1,6}\d{0,2}(동|읍|면|가)$")
_PROVINCE_SHORT = re.compile(r"(특별자치시|특별자치도|특별시|광역시|통합특별시|도)$")


def _province_names(province: str) -> set[str]:
    short = _PROVINCE_SHORT.sub("", province)
    short = {"전남광주": "광주"}.get(short, short)
    return {short, romanize(short), _fold(cyrillic(short))} if len(short) >= 2 else set()


@lru_cache(maxsize=1)
def _index():
    from rag.schedule_tool import default_table
    table = default_table()
    districts: dict[str, set[str]] = {}
    areas: dict[str, set[str]] = {}              # area name -> districts that have it
    for row in table.rows:
        districts.setdefault(row.district, set()).add(row.province)
        for name in row.area_names:
            name = name.replace(" ", "")
            if _AREA.match(name):
                areas.setdefault(name, set()).add(row.district)
                base = re.sub(r"\d+(?=동$)", "", name)
                if base != name:
                    areas.setdefault(base, set()).add(row.district)
    return districts, areas


def _district_patterns(district: str) -> list[tuple[str, re.Pattern]]:
    base, suffix = district[:-1], district[-1]
    roman_suffix, cyr_suffix = _DISTRICT_SUFFIX.get(suffix, ("", ""))
    one = len(base) < 2
    roman, cyr = romanize(base), _fold(cyrillic(base))
    out = [(district, re.compile(re.escape(district)))]
    if not one:
        # the base alone only before a particle or a pause: 구로에 / 구로 사는데, not the
        # first syllables of another word (남동 in 남동생, "younger brother")
        out.append((base, re.compile(re.escape(base) + _KO_AFTER)))
    opt = "" if one else "?"
    if roman:
        out.append((f"{roman}-{roman_suffix}", re.compile(
            rf"\b{re.escape(roman)}(?:[\s-]?{roman_suffix}){opt}\b")))
    if cyr:
        # a Russian case ending may follow (в Кванмёне), but not more of another word
        # (кури = 구리 must not match курица, "chicken")
        out.append((f"{cyr}-{cyr_suffix}", re.compile(
            rf"(?<![а-я]){re.escape(cyr)}(?:[\s-]?{cyr_suffix}){opt}{_RU_ENDING}(?![а-я])")))
    return out


_KO_AFTER = r"(?=$|[\s,.?!·]|에|은|는|이|인|의|에서|사|살|쪽|근처|구|시|군)"
_RU_ENDING = r"(?:е|у|а|и|ом|ой|ах|ами)?"


@lru_cache(maxsize=1)
def _patterns():
    districts, _ = _index()
    return {d: _district_patterns(d) for d in districts}


def _area_spellings(name: str) -> tuple[str, str, str]:
    """Korean, romanised and Cyrillic spelling with spaces and hyphens removed."""
    stem = re.sub(r"(동|읍|면|가)$", "", name)
    digits = re.search(r"\d+$", stem)
    word = stem[:digits.start()] if digits else stem
    number = digits.group() if digits else ""
    end = name[-1]
    roman_end = {"동": "dong", "읍": "eup", "면": "myeon", "가": "ga"}[end]
    cyr_end = {"동": "дон", "읍": "ып", "면": "мён", "가": "га"}[end]
    return (name, f"{romanize(word)}{number}{roman_end}",
            _fold(f"{cyrillic(word)}{number}{cyr_end}"))


@lru_cache(maxsize=1)
def _area_index() -> dict[str, tuple[str, str, str]]:
    _, areas = _index()
    return {name: _area_spellings(name) for name in areas}


def _squash(text: str) -> str:
    return re.sub(r"[\s\-'’.,]", "", text.lower())


def read_place(question: str) -> Place | None:
    """The place the question names, or None. Longest spelling wins; a neighbourhood found
    in the matched district confirms it."""
    districts, areas = _index()
    text = question.lower()
    folded = _fold(text)
    hits = []                                   # (district, spelling)
    for district, patterns in _patterns().items():
        for spelling, pattern in patterns:
            if pattern.search(question) or pattern.search(text) or pattern.search(folded):
                hits.append((district, spelling))
                break
    squashed, squashed_folded = _squash(question), _fold(_squash(question))
    found_areas = [name for name, (korean, roman, cyr) in _area_index().items()
                   if korean in squashed or roman in squashed or cyr in squashed_folded]
    found_areas.sort(key=len, reverse=True)

    if hits:
        hits.sort(key=lambda h: len(h[1]), reverse=True)
        names = {d for d, _ in hits}
        with_area = [d for d in names if any(d in areas[a] for a in found_areas)]
        district = with_area[0] if len(with_area) == 1 else hits[0][0]
        if len(names) > 1 and len(with_area) != 1 and len(hits[0][1]) == len(hits[1][1]):
            return None                         # two districts, no way to choose
        provinces = sorted(districts[district])
        named = [p for p in provinces if any(n and n in text for n in _province_names(p))]
        dong = next((a for a in found_areas if district in areas[a]), None)
        return Place(district, named or provinces, dong,
                     next(s for d, s in hits if d == district))
    if found_areas:
        owners = areas[found_areas[0]]
        if len(owners) == 1:                    # a neighbourhood only one district has
            district = next(iter(owners))
            return Place(district, sorted(districts[district]), found_areas[0], found_areas[0])
    return None
