"""
Human handoff and fixed messages (PLAN.md §4.10; Lesson 7, Klarna: when the assistant
cannot answer, hand over cleanly instead of guessing).

When the answer is not a full ANSWER, the user gets:
    - the district office and phone (only from the district data, never invented)
    - a short Korean sentence to show or say at the office / 주민센터
    - what was already checked, so they do not start from zero

Messages are deterministic (no LLM), in English, or Korean when lang = "ko".
"""
from __future__ import annotations

from rag.korean import object_particle
from rag.schedule_tool import WASTE_TYPES

MESSAGES = {
    "OUT_OF_SCOPE": {
        "en": "I can only help with household waste in Korea: which bin an item goes in, "
              "and when and where to put waste out in your district.",
        "ko": "저는 한국의 생활폐기물 분리배출(품목별 배출 방법, 지역별 배출 요일·시간·장소)만 "
              "안내할 수 있습니다.",
    },
    "INSUFFICIENT_CONTEXT": {
        "en": "I could not find this in the official sources I use, so I will not guess.",
        "ko": "제가 사용하는 공식 자료에서 이 내용을 찾지 못해 추측하지 않겠습니다.",
    },
    "CLARIFY": {
        "en": "I need one more detail to answer.",
        "ko": "답변을 위해 정보가 하나 더 필요합니다.",
    },
    "SCHEDULE_VARIES": {
        "en": "Collection days differ between collection points in this area, so I will not "
              "give you one day. Your district office can tell you which point is yours.",
        "ko": "이 지역은 배출 장소마다 수거 요일이 달라 한 가지 요일로 안내하지 않겠습니다. "
              "이용하시는 배출 장소는 구청이나 군청에 문의해 주세요.",
    },
}


def message(status: str, lang: str | None) -> str:
    texts = MESSAGES.get(status, MESSAGES["INSUFFICIENT_CONTEXT"])
    return texts["ko"] if lang == "ko" else texts["en"]


def korean_sentence(item_ko: str, waste_type: str | None, district: str | None,
                    dong: str | None, asks_schedule: bool) -> str:
    parts = ["안녕하세요."]
    if item_ko:
        parts.append(f"{item_ko}{object_particle(item_ko)} 어떻게 버려야 하는지 알고 싶습니다.")
    if asks_schedule:
        what = WASTE_TYPES.get(waste_type or "", "쓰레기")
        parts.append(f"{what} 배출 요일과 시간, 장소를 알고 싶습니다.")
    if not item_ko and not asks_schedule:
        parts.append("쓰레기 분리배출 방법을 알고 싶습니다.")
    place = " ".join(p for p in (district, dong) if p)
    if place:
        parts.append(f"저는 {place}에 살고 있습니다.")
    return " ".join(parts)


def build_handoff(*, item_ko: str, waste_type: str | None, district: str | None,
                  dong: str | None, schedule, asks_schedule: bool, checked: list[str]) -> dict:
    office = phone = None
    if schedule is not None and schedule.rows:
        row = schedule.rows[0]
        office, phone = f"{row.district} {row.office}".strip(), row.phone or None
    contact = (f"Call {office} ({phone})." if phone else
               "Ask your district office (구청) or community service centre (주민센터).")
    return {"office": office, "phone": phone, "contact": contact,
            "korean_sentence": korean_sentence(item_ko, waste_type, district, dong,
                                               asks_schedule),
            "checked": checked}
