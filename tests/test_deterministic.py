"""
Tests for the deterministic parts of the pipeline (no models, no Ollama, < 2 s).

    python -m tests.test_deterministic          # plain runner
    python -m pytest tests                      # if pytest is installed
"""
from __future__ import annotations

import json
from datetime import date

from rag.bins import canonical_bin, evidence_bins
from rag.config import BASELINE, DEFAULT, PipelineConfig
from rag.context import EvidenceItem
from rag.gate import decide
from rag.generate import parse_answer
from rag.handoff import korean_sentence
from preprocess.build_schedule import clean_areas
from rag.korean import mentions_place, object_particle, romanize
from rag.retrieve import Candidate, rrf, tokenize_bigram
from rag.router import Route, check_invariants, is_korean
from rag.pipeline import schedule_fields
from rag.schedule_tool import ScheduleResult, default_table, resolve_day
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
