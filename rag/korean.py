"""
Small Korean text helpers (no models).

- romanize(): Revised Romanization with the common sound changes, used to check that
  a district the router returns ("성동구") is really in the question ("Seongdong-gu").
- mentions_place(): that check.
- object_particle(): 을/를 for the handoff sentence (PLAN.md §4.10).
"""
from __future__ import annotations

import re

_INITIAL = ["g", "kk", "n", "d", "tt", "r", "m", "b", "pp", "s", "ss", "", "j", "jj",
            "ch", "k", "t", "p", "h"]
_VOWEL = ["a", "ae", "ya", "yae", "eo", "e", "yeo", "ye", "o", "wa", "wae", "oe", "yo",
          "u", "wo", "we", "wi", "yu", "eu", "ui", "i"]
# final consonant index -> (sound at the end of a syllable, sound when it links to a vowel)
_FINAL = [("", ""), ("k", "g"), ("k", "kk"), ("k", "gs"), ("n", "n"), ("n", "nj"),
          ("n", "nh"), ("t", "d"), ("l", "r"), ("k", "lg"), ("m", "lm"), ("l", "lb"),
          ("l", "ls"), ("l", "lt"), ("p", "lp"), ("l", "lh"), ("m", "m"), ("p", "b"),
          ("p", "bs"), ("t", "s"), ("t", "ss"), ("ng", "ng"), ("t", "j"), ("t", "ch"),
          ("k", "k"), ("t", "t"), ("p", "p"), ("t", "")]
_N, _R, _M, _SILENT = 2, 5, 6, 11            # initial indices for ㄴ ㄹ ㅁ ㅇ


def _syllables(word: str):
    for ch in word:
        code = ord(ch) - 0xAC00
        if 0 <= code < 11172:
            yield code // 588, (code % 588) // 28, code % 28
        else:
            yield None, ch, None


def romanize(word: str) -> str:
    """'성동구' -> 'seongdonggu', '종로구' -> 'jongnogu', '신림동' -> 'sillimdong'."""
    sylls = list(_syllables(word))
    out = []
    for i, (ini, vow, fin) in enumerate(sylls):
        if ini is None:
            out.append(vow.lower())
            continue
        nxt = sylls[i + 1][0] if i + 1 < len(sylls) else None
        prev_fin = sylls[i - 1][2] if i > 0 and sylls[i - 1][0] is not None else 0
        # initial, after sound changes caused by the previous final
        if ini == _R and prev_fin in (4, 8):          # ㄴ/ㄹ + ㄹ -> l-l
            initial = "l"
        elif ini == _R and prev_fin:                  # ㅇ/ㅁ/ㄱ/ㅂ + ㄹ -> n
            initial = "n"
        elif ini == _N and prev_fin == 8:             # ㄹ + ㄴ -> l-l
            initial = "l"
        elif ini == _SILENT and prev_fin and _FINAL[prev_fin][1] not in ("", "ng"):
            initial = ""                              # linked into the previous syllable
        else:
            initial = _INITIAL[ini]
        # final, looking ahead at the next initial
        end, linked = _FINAL[fin]
        if fin and nxt == _SILENT and linked not in ("", "ng"):
            end = linked                              # liaison: 목요일 -> mogyoil
        elif fin and nxt in (_N, _M, _R):             # nasalisation
            end = {"k": "ng", "t": "n", "p": "m"}.get(end, end)
            if fin == 4 and nxt == _R:                # ㄴ + ㄹ -> l-l
                end = "l"
        out.append(initial + _VOWEL[vow] + end)
    return "".join(out)


_SUFFIXES = ("gu", "gun", "si", "dong", "eup", "myeon")


def _base(name: str) -> str:
    name = re.sub(r"\(.*?\)", "", name).replace(" ", "")
    name = re.sub(r"제?\d+가?(?=동$)", "", name)      # 행당1동 -> 행당동
    return re.sub(r"(구|시|군|동|읍|면)$", "", name)


def mentions_place(question: str, korean_name: str) -> bool:
    """True if the question names this place in Korean or in romanised form."""
    if not korean_name:
        return False
    base = _base(korean_name)
    compact = question.replace(" ", "")
    if korean_name.replace(" ", "") in compact or (len(base) >= 2 and base in compact):
        return True
    roman = romanize(base)
    if len(roman) < 3:
        return False
    text = question.lower().replace("'", "")
    pattern = rf"\b{re.escape(roman)}(?:[\s-]?(?:{'|'.join(_SUFFIXES)}))?\b"
    return re.search(pattern, re.sub(r"(?<=[a-z])-(?=[a-z])", "", text)) is not None or \
        re.search(pattern, text) is not None


def has_final_consonant(word: str) -> bool:
    last = next((ch for ch in reversed(word) if "가" <= ch <= "힣"), None)
    return last is not None and (ord(last) - 0xAC00) % 28 != 0


def object_particle(word: str) -> str:
    return "을" if has_final_consonant(word) else "를"
