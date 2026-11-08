"""
Human handoff and fixed messages (PLAN.md §4.10; Lesson 7, Klarna: when the assistant
cannot answer, hand over cleanly instead of guessing).

When the answer is not a full ANSWER, the user gets:
    - the district office and phone (only from the district data, never invented)
    - a short Korean sentence to show or say at the office / 주민센터
    - what was already checked, so they do not start from zero

Everything here is written by code (no LLM), in the user's language (rag/texts.py). The
Korean sentence is always Korean: it is for the person at the office.
"""
from __future__ import annotations

from rag.korean import object_particle
from rag.schedule_tool import WASTE_TYPES
from rag.texts import TEXTS, text


def message(status: str, lang: str | None) -> str:
    """The fixed answer for a status (OUT_OF_SCOPE, CLARIFY, ...), in the user's language."""
    return text(status if status in TEXTS["en"] else "INSUFFICIENT_CONTEXT", lang)


def korean_sentence(item_ko: str, waste_type: str | None, district: str | None,
                    dong: str | None, asks_schedule: bool, item_asked: str = "") -> str:
    """`item_ko`: the Korean item name, empty if unusable. `item_asked`: the item in the
    user's own words, so the sentence still names it when there is no Korean name."""
    parts = ["안녕하세요."]
    if item_ko:
        parts.append(f"{item_ko}{object_particle(item_ko)} 어떻게 버려야 하는지 알고 싶습니다.")
    elif item_asked:
        parts.append(f"이 물건을 어떻게 버려야 하는지 알고 싶습니다: {item_asked}.")
    if asks_schedule:
        what = WASTE_TYPES.get(waste_type or "", "쓰레기")
        parts.append(f"{what} 배출 요일과 시간, 장소를 알고 싶습니다.")
    if not item_ko and not item_asked and not asks_schedule:
        parts.append("쓰레기 분리배출 방법을 알고 싶습니다.")
    place = " ".join(p for p in (district, dong) if p)
    if place:
        parts.append(f"저는 {place}에 살고 있습니다.")
    return " ".join(parts)


def build_handoff(*, item_ko: str, item_asked: str, waste_type: str | None,
                  district: str | None, dong: str | None, schedule, asks_schedule: bool,
                  checked: list[str], lang: str | None = None) -> dict:
    office = phone = None
    if schedule is not None and schedule.rows:
        row = schedule.rows[0]
        office, phone = f"{row.district} {row.office}".strip(), row.phone or None
    contact = (text("contact_phone", lang, office=office, phone=phone) if phone else
               text("contact_none", lang))
    return {"office": office, "phone": phone, "contact": contact,
            "korean_sentence": korean_sentence(item_ko, waste_type, district, dong,
                                               asks_schedule, item_asked),
            "checked": checked}
