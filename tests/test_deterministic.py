"""
Tests for the deterministic parts of the pipeline (no models, no Ollama, < 2 s).

    python -m tests.test_deterministic          # plain runner
    python -m pytest tests                      # if pytest is installed
"""
from __future__ import annotations

import json
from collections import defaultdict
from datetime import date
from types import SimpleNamespace

from rag.bins import canonical_bin, evidence_bins
from rag.config import BASELINE, DEFAULT, PipelineConfig
from rag.context import EvidenceItem
from rag.gate import decide
from rag.generate import parse_answer
from rag.handoff import korean_sentence
from experiments.run_experiment import schedule_summary
from preprocess.build_schedule import clean_areas, schedule_chunk
from rag.korean import mentions_place, object_particle, romanize
from rag.retrieve import Candidate, rrf, tokenize_bigram
from rag.router import Route, check_invariants, is_korean
from rag.pipeline import day_asked, item_only_question, schedule_fields
from rag.schedule_text import (PLACE_TERMS, TERMS, TEXT, WASTE_TERMS, ScheduleWriter, glossary,
                               merge_schedule, names_days, usable_translation, write_when,
                               write_where)
from rag.schedule_tool import DayRef, ScheduleResult, default_table, resolve_day
from rag.schedule_vector import ScheduleVectorSearch
from rag.validate import validate


def cand(cid, rank, score=None, **meta):
    return Candidate(cid, meta.pop("text", ""), meta, 0.0, rank, "t", rerank_score=score)


def test_romanize_and_place_mentions():
    assert romanize("성동구") == "seongdonggu"
    assert romanize("종로구") == "jongnogu"          # ㅇ + ㄹ -> n
    assert romanize("신림동") == "sillimdong"        # ㄴ + ㄹ -> ll
    assert mentions_place("I live in Seongdong-gu", "성동구")
    assert mentions_place("I live in Jung-gu", "중구")
    assert not mentions_place("I live in Jungnang-gu", "중구")
    assert not mentions_place("When is food waste collected?", "성동구")


def test_object_particle():
    assert object_particle("우산") == "을" and object_particle("닭뼈") == "를"


def test_canonical_bins():
    assert canonical_bin("종량제봉투 (종량제봉투)") == "종량제봉투"
    assert canonical_bin("일반쓰레기") == "종량제봉투"
    assert canonical_bin("대형") == "대형폐기물"
    assert canonical_bin("찌꺼기") is None
    assert evidence_bins({"doc_type": "rule", "item": "무색 폴리 에틸렌테레프탈 레이트 (PET)병"}) \
        == {"투명페트병"}
    assert evidence_bins({"doc_type": "item", "categories": "음식물, 종량제봉투"}) \
        == {"음식물", "종량제봉투"}


def test_rrf_keeps_ranks():
    fused = rrf({"a": [cand("x", 1), cand("y", 2)], "b": [cand("y", 1)]})
    assert [c.chunk_id for c in fused] == ["y", "x"]
    assert fused[0].ranks == {"a": 2, "b": 1}


def test_bigram_tokens():
    assert tokenize_bigram("스티로폼 PET") == ["스티", "티로", "로폼", "pet"]


def test_parse_answer_citations():
    text = json.dumps({"status": "ANSWER", "bin": "종이", "bin_en": "", "how_to_prepare": [],
                       "answer_text": "Paper [1] [7].", "citations": [1, 9], "missing": ""})
    answer, checks = parse_answer(text, n_evidence=2)
    assert answer["citations"] == [1] and sorted(checks["invalid_citations"]) == [7, 9]
    answer, checks = parse_answer("not json", 2)
    assert answer["status"] == "INVALID_OUTPUT" and not checks["json_valid"]


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


def test_gate_decisions():
    sel = [cand("a", 1, 0.9)]
    assert decide("out_of_scope", [], None, None, None, 0.05).status == "OUT_OF_SCOPE"
    assert decide("item", sel, None, None, None, 0.05).status == "ANSWER"
    low = decide("item", [cand("a", 1, 0.01)], None, None, None, 0.05)
    assert low.status == "INSUFFICIENT_CONTEXT" and low.item == "abstain"
    assert decide("schedule", [], None, None, None, 0.05).status == "CLARIFY"
    no_data = ScheduleResult("NO_DATA", {}, message="no schedule data")
    assert decide("schedule", [], no_data, "강동구", None, 0.05).status == "INSUFFICIENT_CONTEXT"
    both = decide("both", sel, no_data, "강동구", None, 0.05)
    assert both.status == "ANSWER" and both.schedule == "abstain"


def test_schedule_lookup_and_dates():
    table = default_table()
    ok = table.lookup("성동구", dong="행당동", waste_type="food")
    assert ok.status == "OK" and ok.rows[0].rules["food"].days == [0, 2, 4]
    assert table.lookup("중구").status == "CLARIFY"
    assert table.lookup("강동구").status == "NO_DATA"
    wed = date(2026, 11, 4)
    assert resolve_day("tonight", wed).date == wed
    assert resolve_day("sun", wed).date == date(2026, 11, 8)
    assert resolve_day("none", wed) is None


def test_area_number_lists():
    names = lambda raw: clean_areas(raw)[0]
    assert names("휘경1,2동") == ["휘경1동", "휘경2동"]
    assert names("상계6.7동") == ["상계6동", "상계7동"]
    assert names("청학1·2동+남항동") == ["청학1동", "청학2동", "남항동"]
    assert names("양정1ㆍ2동") == ["양정1동", "양정2동"]
    assert names("수성1,2.3,4가동") == ["수성1가동", "수성2가동", "수성3가동", "수성4가동"]
    assert names("중앙로1,2가") == ["중앙로1가", "중앙로2가"]
    assert names("강림1.2리") == ["강림1리", "강림2리"]
    assert names("제2,3공단") == ["제2공단", "제3공단"]
    assert names("대연1동,2동,3") == ["대연1동", "대연2동", "대연3동"]   # stem carried over
    assert names("행당동,2") == ["행당동", "2"]                          # no number to replace


def test_area_placeholders_mean_whole_district():
    for raw in ("없음", "해당없음", "전체"):
        assert clean_areas(raw) == ([], [], True), raw


def test_schedule_chunk_text():
    row = defaultdict(str, {"시도명": "서울특별시", "시군구명": "종로구", "관리번호": "1"})
    chunk = schedule_chunk(row)
    assert chunk["text"].splitlines()[:2] == ["[서울특별시 종로구] 쓰레기 배출 안내", "대상 지역: 전체"]
    row["관리구역명"] = "1권역"
    assert schedule_chunk(row)["text"].startswith("[서울특별시 종로구 1권역] ")
    assert "stale" not in chunk["metadata"]            # would tie the corpus hash to the build date


def test_district_rows_same_names_as_lookup():
    table = default_table()
    ids = lambda *args: {r.row_id for r in table.district_rows(*args)}
    assert ids("성동구") == ids("seongdong-gu") == ids("성동") == ids("서울특별시 성동구")
    assert ids("성동구") == {r.row_id for r in table.lookup("성동구").rows}
    assert len({table.by_id[i].province for i in ids("중구")}) == 5
    assert {table.by_id[i].province for i in ids("중구", "부산")} == {"부산광역시"}
    assert not ids("강동구")


def vector_search(mode, table):
    """The search logic with a stub in place of Qdrant, which returns rows of two districts."""
    calls = []
    top = [r for r in table.rows if r.district == "마포구"][:1] + table.lookup("성동구").rows

    def search(text, k, where=None):
        calls.append((text, k, where))
        keep = [r for r in top if not where or r.district in where["district"]]
        return [cand(r.row_id, i, row_id=r.row_id) for i, r in enumerate(keep, 1)][:k]

    engine = ScheduleVectorSearch.__new__(ScheduleVectorSearch)
    engine.table, engine.mode, engine.k_retrieve = table, mode, 20
    engine.dense = SimpleNamespace(search=search)
    return engine, calls


def test_vector_variants_choose_rows():
    table = default_table()
    wanted = {r.row_id for r in table.lookup("성동구").rows}

    engine, calls = vector_search("vector", table)
    result = engine.search("언제 버려요", "seongdong-gu", dong="행당1동")
    assert calls[0][0] == "성동구 행당1동 언제 버려요"           # canonical name in the query text
    assert calls[0][2] is None
    assert result.rows[0].district == "마포구"                 # no filter: the wrong district stays

    engine, calls = vector_search("postfilter", table)
    result = engine.search("언제 버려요", "성동구")
    assert calls[0][1] == 20 and {r.row_id for r in result.rows} == wanted

    engine, calls = vector_search("prefilter", table)
    result = engine.search("언제 버려요", "성동구")
    assert calls[0][2] == {"province": ["서울특별시"], "district": ["성동구"]}
    assert {r.row_id for r in result.rows} == wanted

    for mode in ("postfilter", "prefilter"):
        engine, calls = vector_search(mode, table)
        result = engine.search("언제 버려요", "강동구")           # no such rows, so nothing to show
        assert result.status == "NO_DATA" and not result.rows


def test_schedule_summary_counts():
    table = default_table()
    first_seen = {}
    for row in table.rows:                             # two districts, one food schedule
        rule = row.rules["food"]
        twin = first_seen.setdefault((tuple(rule.days), rule.start, rule.end), row)
        if twin.district != row.district:
            one, same_days = twin.row_id, row.row_id
            break

    def trace(cid, status, shown):
        return {"case_id": cid, "answer": {"status": status, "schedule": {
            "zones": [{"row_id": i} for i in shown]}}}
    cases = [{"case_id": "a", "waste_type": "food", "expected_behavior": "answer",
              "expected_schedule": {"row_ids": [one]}},
             {"case_id": "b", "waste_type": "food", "expected_behavior": "abstain",
              "expected_schedule": {"row_ids": []}}]
    good = schedule_summary([trace("a", "ANSWER", [one]),
                             trace("b", "INSUFFICIENT_CONTEXT", [])], cases, table)
    assert good == {"cases": 2, "behaviour_ok": 2, "wrong_place": 0, "answerable": 1, "empty": 0,
                    "row_found": 1, "top_row": 1, "only_correct_rows": 1, "day_time_match": 1}
    # Another district's row with the same days: the day/time still matches, the place does not.
    lucky = schedule_summary([trace("a", "ANSWER", [same_days]),
                              trace("b", "ANSWER", [one])], cases, table)
    assert (lucky["day_time_match"], lucky["row_found"], lucky["wrong_place"]) == (1, 0, 2)
    # Rows of a refused answer are not shown to the user.
    refused = schedule_summary([trace("a", "INSUFFICIENT_CONTEXT", [one])], cases[:1], table)
    assert (refused["empty"], refused["row_found"]) == (1, 0)


def test_schedule_area_match():
    table = default_table()
    for dong in ("상계6동", "상계7동", "상계6.7동", "상계6·7동"):      # same zone, any spelling
        result = table.lookup("노원구", dong=dong)
        assert (result.status, result.matched_on, len(result.rows)) == ("OK", "area", 1), dong
        assert "상계6동" in result.rows[0].area_names
    for district, dong in (("사상구", "주례2동"), ("영도구", "청학2동"),
                           ("부산진구", "양정1동"), ("수성구", "수성2가동")):
        assert table.lookup(district, dong=dong).matched_on == "area", dong
    # An exact name wins over names that only share the base (상계1동, 상계2동, ...).
    assert len(table.lookup("노원구", dong="상계1동").rows) == 1
    assert len(table.lookup("노원구", dong="상계동").rows) > 1


def test_gate_many_rows_in_one_area():
    """Only MAX_ZONES rows reach the answer, so the gate must not answer for the rest."""
    table = default_table()

    def gate(district, dong, waste):
        return decide("schedule", [], table.lookup(district, None, dong, waste), district, dong, 0.15)

    one_name = gate("고흥군", "도덕면", "food")          # 287 collection points, Mon-Fri
    assert (one_name.status, one_name.schedule, one_name.schedule_varies) == (
        "INSUFFICIENT_CONTEXT", "abstain", True)
    names = gate("양평군", "오빈리", "general")          # 오빈1리, 오빈2리, 오빈3리
    assert names.status == "CLARIFY" and names.clarify["options"] == ["오빈1리", "오빈2리", "오빈3리"]
    assert gate("정선군", "정선읍", "food").schedule == "answer"      # same days in every row
    # Whether the rows differ depends on the waste type asked about.
    assert gate("고창군", "고창읍", "general").schedule == "answer"
    assert gate("고창군", "고창읍", "food").schedule == "abstain"


class StubLLM:
    model_id = "stub"

    def __init__(self, text):
        self.text, self.calls = text, []

    def generate(self, **kwargs):
        self.calls.append(kwargs)
        return SimpleNamespace(text=self.text, model_id=self.model_id, done_reason="stop")


def test_schedule_text_all_days_and_zones():
    table = default_table()
    rows = table.lookup("성동구", waste_type="food").rows        # two zones, different days
    numbers = {r.row_id: i for i, r in enumerate(rows, 1)}
    for lang, text in TEXT.items():
        lines = write_when(rows, "food", lang, None, numbers)
        assert len(lines) == 3, lang                             # a heading, then each zone
        for row, line in zip(rows, lines[1:]):
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
    ok = lambda text, lang="en", source="규격봉투 사용": usable_translation(source, text, lang)
    assert ok("use a pay-as-you-throw bag (규격봉투)")           # Korean in parentheses is asked for
    assert ok("使用计量收费袋", "zh")
    assert ok("положите в платный мешок", "ru")
    assert not ok("use规格式垃圾袋后投放")                        # the model drifted into Chinese
    assert not ok("выбросьте по指定的日期", "ru")
    assert not ok("규격봉투 사용")                                # returned untranslated
    assert not ok("Выposal после удаления", "ru")
    assert not ok("after 7 pm", source="저녁 6시 이후 배출")       # a number changed
    assert ok("after 6 pm", source="저녁 6시 이후 배출")


def test_failed_translation_tries_english_then_korean():
    class Queue(StubLLM):
        def generate(self, **kwargs):
            self.calls.append(kwargs)
            return SimpleNamespace(text=self.text.pop(0), model_id="stub", done_reason="stop")

    method = "규격봉투에 넣어 지정된 요일에 배출"
    llm = Queue([json.dumps({"text": "выбросьте по指定的日期"}), json.dumps({"text": "use the bag"})])
    assert ScheduleWriter(llm).translate([method], "ru")[0] == ["use the bag"]
    assert "into Russian" in llm.calls[0]["prompt"] and "into English" in llm.calls[1]["prompt"]
    llm = Queue(['{"text": "по指定的日期"}', '{"text": "use规格式"}'])
    lines, record = ScheduleWriter(llm).translate([method], "ru")
    assert lines == [method] and record["kept_korean"] == [method]


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


def test_item_only_question():
    route = Route(valid=True, item="pizza box")
    asked = item_only_question("Where does a pizza box go, and when is food waste day?", route)
    assert asked.startswith("How do I throw away pizza box?") and "food waste day" not in asked
    assert "food waste day" in item_only_question("When is food waste day?", Route(valid=True))


def test_day_named_in_question_beats_router():
    assert day_asked("화요일에 음식물쓰레기 버려도 되나요?", "wed") == "tue"
    assert day_asked("Can I put it out on Sunday?", "sat") == "sun"
    assert day_asked("Can I put it out tonight?", "tonight") == "tonight"
    assert day_asked("월요일이나 수요일에 버려도 되나요?", "mon") == "mon"       # two days: the router's


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


def test_answer_schedule_fields():
    """The flat §4.8 fields the website reads; values come from the rows, never the LLM."""
    table = default_table()
    one = table.lookup("성동구", dong="행당동", waste_type="food").rows
    fields = schedule_fields(one, ["food"])
    assert fields["days"] == "Mon, Wed, Fri" and fields["time"] and fields["place"]
    assert fields["data_date"] == one[0].data_date and fields["office_phone"] == one[0].phone
    several = table.lookup("노원구").rows                              # one entry per zone
    assert len(several) > 1
    many = schedule_fields(several, ["food"])
    assert all(r.zone in many["days"] for r in several if r.rules["food"].days)
    assert schedule_fields([], ["food"])["days"] is None


def test_router_invariants():
    route = Route(valid=True, intent="schedule", item="chicken bones", item_ko="닭骨头",
                  ko_query="닭 뼈", district="성동구", lang="ko")
    checks = check_invariants("Where do chicken bones go?", route)
    assert route.intent == "both"                         # item named -> both
    assert checks["district_in_question"] is False and route.district == ""
    assert checks["item_ko_korean"] is False and checks["rewrite_usable"] is False
    assert route.lang == "en"                             # Latin script, not Korean
    assert is_korean("투명 PET병", strict=True)


def test_config_contract():
    assert DEFAULT.replace(rerank=False).rerank is False
    assert BASELINE.router is False and BASELINE.query_mode == "original"
    try:
        PipelineConfig(retrieval="magic")
    except ValueError:
        pass
    else:
        raise AssertionError("invalid retrieval accepted")


def test_handoff_sentence():
    s = korean_sentence("우산", None, "성동구", "행당동", asks_schedule=False)
    assert s == "안녕하세요. 우산을 어떻게 버려야 하는지 알고 싶습니다. 저는 성동구 행당동에 살고 있습니다."


if __name__ == "__main__":
    tests = [(name, fn) for name, fn in sorted(globals().items()) if name.startswith("test_")]
    failed = 0
    for name, fn in tests:
        try:
            fn()
            print(f"ok    {name}")
        except Exception as exc:                       # noqa: BLE001
            failed += 1
            print(f"FAIL  {name}: {exc!r}")
    print(f"\n{len(tests) - failed}/{len(tests)} passed")
    raise SystemExit(1 if failed else 0)
