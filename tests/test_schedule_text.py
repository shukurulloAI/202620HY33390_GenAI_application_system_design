"""Schedule answers written by code, and the method translation checks."""
from __future__ import annotations

import json
from datetime import date
from types import SimpleNamespace

from rag.schedule_text import (
    PLACE_TERMS,
    TERMS,
    TEXT,
    WASTE_TERMS,
    ScheduleWriter,
    glossary,
    merge_schedule,
    names_days,
    usable_translation,
    write_when,
    write_where,
)
from rag.schedule_tool import DayRef, default_table
from tests.helpers import StubLLM


def test_schedule_text_all_days_and_zones():
    table = default_table()
    rows = table.lookup("성동구", waste_type="food").rows        # two zones, different days
    numbers = {r.row_id: i for i, r in enumerate(rows, 1)}
    for lang, text in TEXT.items():
        lines = write_when(rows, "food", lang, None, numbers)
        assert len(lines) == 3, lang                             # a heading, then each zone
        for row, line in zip(rows, lines[1:], strict=True):
            assert all(text["days"][d] in line for d in row.rules["food"].days), (lang, line)
            assert f"[{numbers[row.row_id]}]" in line
    assert "2권역" in write_when(rows, "food", "en", None, numbers)[1]
    # Same days in every zone: one line, no zone labels (수성구, four zones).
    same = table.lookup("수성구", waste_type="general").rows
    lines = write_when(same, "general", "en", None, {r.row_id: i for i, r in enumerate(same, 1)})
    assert len(lines) == 1 and "[1][2][3][4]" in lines[0] and "Sun" in lines[0]


def test_schedule_text_day_check():
    row = default_table().lookup("성동구", dong="행당1동", waste_type="food").rows[0]   # Mon, Wed, Fri
    numbers = {row.row_id: 1}
    friday = DayRef("tonight", date(2026, 11, 6))
    lines = write_when([row], "food", "en", friday, numbers)
    assert lines[0] == "Food waste (음식물쓰레기): Tonight (Fri 2026-11-06): yes"
    tuesday = DayRef("tue", date(2026, 11, 3))
    assert write_when([row], "food", "ko", tuesday, numbers)[0] == "음식물쓰레기: 화 (2026-11-03): 배출 불가"


def test_schedule_text_where():
    table = default_table()
    row = table.lookup("성동구", dong="행당1동").rows[0]
    assert write_where([row], "ko") == "장소: 문전수거 - 집앞"
    many = table.lookup("정선군", dong="정선읍").rows[:4]          # no one place to name
    assert " - " not in write_where(many, "ko")
    same = SimpleNamespace(place_type="문전수거", place="문전수거")   # the place repeats the type
    assert write_where([same], "ko") == "장소: 문전수거"


def test_schedule_method_translation():
    row = default_table().lookup("성동구", dong="행당1동", waste_type="food").rows[0]
    method = row.rules["food"].method
    llm = StubLLM(json.dumps({"text": "1) Houses: use the bag. 2) Flats: use the bin."}))
    answer, record = ScheduleWriter(llm).write([row], "food", "en", None, 3)
    assert not record["kept_korean"] and "Houses" in answer["how_to_prepare"][0]
    assert answer["citations"] == [3] and "[3]" in answer["answer_text"]
    prompt = llm.calls[0]["prompt"]
    assert method in prompt and "Mon" not in prompt and "20:00" not in prompt  # no facts to change
    llm = StubLLM("{}")
    assert ScheduleWriter(llm).write([row], "food", "ko", None, 1)[0]["how_to_prepare"] == [method]
    assert not llm.calls                                         # Korean needs no LLM
    for broken in ("not json", "{}", '{"text": ""}', '{"text": null}', '{"text": 1}',
                   '{"lines": ["a"]}'):                          # falls back to the Korean text
        answer, record = ScheduleWriter(StubLLM(broken)).write([row], "food", "en", None, 1)
        assert answer["how_to_prepare"] == [method] and record["kept_korean"] == [method], broken
        assert "Mon, Wed, Fri, 20:00-24:00" in answer["answer_text"]
    # A language without tables gets English, not a crash.
    assert "Mon, Wed, Fri" in ScheduleWriter(StubLLM("{}")).write([row], "food", "ja", None, 1)[0]["answer_text"]


def test_methods_that_name_days_are_not_translated():
    for method in ("수요일 저녁 : 투명페트병, 비닐 / 월,금 저녁 : 그 외", "규격봉투에 넣어 매일 배출(토요일 제외)",
                   "재활용 그물망에 넣어 배출(월, 목-기타재활용/화-스티로폼)", "저녁 6시 이후 배출(금, 토 제외)",
                   "일반종량제봉투에 담아 배출(월ㆍ수 가연성, 목 불연성)"):
        assert names_days(method), method
    for method in ("규격봉투에 넣어 지정된 요일에 배출", "물기를 최대한 줄여 음식물만 전용봉투에 넣어 배출",
                   "재활용품종류별로모아배출", "1)일반주택-음식물 종량제봉투에 넣어 배출", "음식물 수거통에 일반 배출"):
        assert not names_days(method), method
    llm = StubLLM(json.dumps({"text": "Thursday evening"}))
    lines, record = ScheduleWriter(llm).translate(["수요일 저녁 : 비닐"], "en")
    assert lines == ["수요일 저녁 : 비닐"] and not llm.calls and record["kept_korean"]


def test_translation_checks():
    def ok(text, lang="en", source="규격봉투 사용"):
        return usable_translation(source, text, lang)

    assert ok("use a pay-as-you-throw bag (규격봉투)")           # Korean in parentheses is asked for
    assert ok("使用计量收费袋", "zh")
    assert ok("положите в платный мешок", "ru")
    assert not ok("use规格式垃圾袋后投放")                        # the model drifted into Chinese
    assert not ok("выбросьте по指定的日期", "ru")
    assert not ok("규격봉투 사용")                                # returned untranslated
    assert not ok("Выposal после удаления", "ru")
    assert not ok("after 7 pm", source="저녁 6시 이후 배출")       # a number changed
    assert ok("after 6 pm", source="저녁 6시 이후 배출")


def test_translation_must_be_in_the_language_asked_for():
    def ok(text, lang):
        return usable_translation("물기를 최대한 제거한 후 배출", text, lang)

    romanised = "acjeoekkeul keutjian jeogjeo geuda hamyeon juneungyonggi(soktong) e baeotdal"
    assert not ok(romanised, "vi")                     # the real output for s04
    assert not ok(romanised, "zh") and not ok(romanised, "ru")
    assert ok("giảm tối đa độ ẩm rồi cho vào túi rác trả phí", "vi")
    assert ok("Dùng bao trong suốt đựng sau đó buộc lại trước khi bỏ ra ngoài", "vi")
    assert ok("尽量挤出水分后放入计量收费袋中排出", "zh")
    assert ok("положите PET-бутылки в прозрачный пакет", "ru")
    assert ok(romanised, "en")                         # no letters of its own to test: known gap


def test_failed_translation_tries_english_then_korean():
    class Queue(StubLLM):
        def generate(self, **kwargs):
            self.calls.append(kwargs)
            return SimpleNamespace(text=self.text.pop(0), model_id="stub", done_reason="stop")

    method = "규격봉투에 넣어 지정된 요일에 배출"
    llm = Queue([json.dumps({"text": "放入영营养郡"}), json.dumps({"text": "use the bag"})])
    assert ScheduleWriter(llm).translate([method], "zh")[0] == ["use the bag"]
    assert "into Chinese" in llm.calls[0]["prompt"] and "into English" in llm.calls[1]["prompt"]
    llm = Queue(['{"text": "放入영营养郡"}', '{"text": "use规格式"}'])
    lines, record = ScheduleWriter(llm).translate([method], "zh")
    assert lines == [method] and record["kept_korean"] == [method]


def test_method_text_goes_to_english_for_languages_qwen_gets_wrong():
    for lang in ("uz", "vi", "ru"):
        llm = StubLLM(json.dumps({"text": "use the bag"}))
        lines, record = ScheduleWriter(llm).translate(["규격봉투에 넣어 배출"], lang)
        assert lines == ["use the bag"] and record["language"] == "en", lang
        assert len(llm.calls) == 1 and "into English" in llm.calls[0]["prompt"], lang


def test_translation_sends_only_the_terms_of_the_line():
    llm = StubLLM(json.dumps({"text": "put it in the bag"}))
    ScheduleWriter(llm).translate(["음식물만 전용봉투에 넣어 배출"], "en")
    assert "dedicated food-waste bag" in llm.calls[0]["prompt"]
    assert "pay-as-you-throw bag =" not in llm.calls[0]["prompt"]
    assert "payment sticker" not in llm.calls[0]["prompt"]
    llm = StubLLM(json.dumps({"text": "food-waste pay-as-you-throw bag"}))
    ScheduleWriter(llm).translate(["음식물종량제봉투에담아배출"], "en")
    assert "food-waste pay-as-you-throw bag" in llm.calls[0]["prompt"]


def test_uzbek_method_text_is_english_but_days_are_uzbek():
    row = default_table().lookup("성동구", dong="행당1동", waste_type="food").rows[0]
    llm = StubLLM(json.dumps({"text": "1) Use the bag. 2) Use the bin."}))
    answer, record = ScheduleWriter(llm).write([row], "food", "uz", None, 1)
    assert record["language"] == "en" and "into English" in llm.calls[0]["prompt"]
    assert "dushanba, chorshanba, juma" in answer["answer_text"]


def test_schedule_terms_in_glossary():
    assert set(TEXT) - {"ko"} <= set(next(iter(glossary().values())))
    assert set(TERMS) | set(PLACE_TERMS) | set(WASTE_TERMS.values()) <= set(glossary())
    for lang, text in TEXT.items():
        assert len(text["days"]) == 7 and len(set(text["days"])) == 7, lang


def test_merge_schedule():
    written = {"status": "ANSWER", "bin": "", "bin_en": "", "how_to_prepare": ["put it out"],
               "answer_text": "Food waste: Mon [2]", "citations": [2], "missing": ""}
    assert merge_schedule(None, written) == written
    item = {"status": "ANSWER", "bin": "종이", "bin_en": "paper", "how_to_prepare": ["fold it"],
            "answer_text": "Paper bin [1].", "citations": [1], "missing": ""}
    both = merge_schedule(item, written)
    assert both["answer_text"] == "Paper bin [1].\n\nFood waste: Mon [2]"
    assert both["bin"] == "종이" and both["citations"] == [1, 2]
    assert both["how_to_prepare"] == ["fold it", "put it out"]


def test_no_collection_days_are_translated_only_when_every_part_is_known():
    from rag.schedule_text import no_collection_text, write_no_collection
    assert no_collection_text("토+일", "en") == "Sat, Sun (토+일)"
    assert no_collection_text("일요일, 명절(설,추석)", "en") == \
        "Sun, Seollal (Lunar New Year), Chuseok (일요일, 명절(설,추석))"
    assert no_collection_text("명절 및 일요일", "ru") == "праздники Соллаль и Чхусок, воскресенье (명절 및 일요일)"
    assert no_collection_text("토+일", "ko") == "토+일"
    assert no_collection_text("수요일 외 다른 요일", "en") == "수요일 외 다른 요일"   # not every part known
    rows = default_table().lookup("성동구", dong="행당1동", waste_type="food").rows
    assert write_no_collection(rows, "en").startswith("No collection: ")
