"""
Schedule answers written by code (PLAN.md §4.8; Lesson 1: use a tool for facts).

Days, times and places come straight from the tool's rows, and the LLM never sees them, so
it cannot drop or change them. E4 showed why: with the right row, the generator's text still
dropped days or zones on 5 of 19 probes (docs/PHASE2_NOTES.md §10).

The LLM does one job here: translating the free-text `method` field, which has 599 distinct
values. It is not trusted with facts: a method that names days is never sent (it turned
수요일 into Thursday), and a translation is dropped if a number changed or another script
leaked in. A dropped translation is retried in English, and failing that the Korean text is
shown, since correct but hard to read beats fluent and wrong. Korean users need no LLM.

Day names and labels are drafts for zh, vi, uz and ru, like the glossary, and need the same
native-speaker check.
"""
from __future__ import annotations

import json
import re
from functools import lru_cache

from rag import config, paths
from rag.generate import LANGUAGE_NAMES, load_prompt
from rag.schedule_tool import DayRef, ScheduleRow, WasteRule, waste_types

PROMPT = "schedule_method_v1"
METHOD_SCHEMA = {"type": "object", "properties": {"text": {"type": "string"}},
                 "required": ["text"]}
# Glossary term -> spellings in the method text. Only the terms a method uses are sent.
TERMS = {"음식물 종량제봉투": ("음식물종량제", "음식물규격봉투", "음식물쓰레기종량제"),
         "규격봉투": ("규격봉투", "종량제봉투", "종량제"),
         "음식물 전용용기": ("전용용기",),
         "전용봉투": ("전용봉투",),
         "납부필증": ("납부필증",)}
# qwen2.5:7b's Uzbek, Vietnamese and Russian change the meaning in ways no check here can see,
# so their method text goes to English. Vietnamese made "under 5 tons" into "over 5 tons" and
# put English profanity in a line; Russian wrote 'thick' for 'paid' bag, and 13 of the 50 most
# common lines failed outright (PHASE2_NOTES §10). Days, times and labels stay in the user's
# language, from the tables below. Drop an entry here once a native speaker has checked it.
METHOD_LANGUAGE = {"uz": "en", "vi": "en", "ru": "en"}
_DAY = "월화수목금토일"
_NAMES_DAYS = re.compile(rf"[{_DAY}]요일|(?<![가-힣])[{_DAY}](?=\s*(?:[,·ㆍ/~+\-]|저녁|오전|오후|$))"
                         rf"|(?<=[,·ㆍ/~+\-])\s*[{_DAY}](?![가-힣])")
WASTE_TERMS = {"general": "일반쓰레기", "food": "음식물쓰레기", "recycling": "재활용품",
               "bulky": "대형폐기물"}
PLACE_TERMS = ("문전수거", "거점수거")

TEXT = {
    "en": {"days": ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"), "sep": ", ",
           "no_days": "no days listed", "no_time": "time not given", "where": "Where",
           "how": "How", "depends": "{waste} depends on your neighbourhood:",
           "yes": "yes", "no": "no",
           "today": "Today", "tonight": "Tonight", "tomorrow": "Tomorrow",
           "no_collection": "No collection"},
    "ko": {"days": ("월", "화", "수", "목", "금", "토", "일"), "sep": ", ",
           "no_days": "요일 정보 없음", "no_time": "시간 정보 없음", "where": "장소",
           "how": "방법", "depends": "{waste}는 지역마다 다릅니다:",
           "yes": "배출 가능", "no": "배출 불가",
           "today": "오늘", "tonight": "오늘 밤", "tomorrow": "내일",
           "no_collection": "미수거일"},
    "zh": {"days": ("周一", "周二", "周三", "周四", "周五", "周六", "周日"), "sep": "、",
           "no_days": "未列出日期", "no_time": "未提供时间", "where": "地点",
           "how": "方法", "depends": "{waste}因您所在的社区而异：",
           "yes": "可以", "no": "不可以",
           "today": "今天", "tonight": "今晚", "tomorrow": "明天",
           "no_collection": "不收运日"},
    "vi": {"days": ("Thứ Hai", "Thứ Ba", "Thứ Tư", "Thứ Năm", "Thứ Sáu", "Thứ Bảy", "Chủ Nhật"),
           "sep": ", ", "no_days": "không có ngày", "no_time": "không có giờ",
           "where": "Địa điểm", "how": "Cách làm",
           "depends": "{waste} tùy theo khu phố của bạn:",
           "yes": "được", "no": "không được",
           "today": "Hôm nay", "tonight": "Tối nay", "tomorrow": "Ngày mai",
           "no_collection": "Ngày không thu gom"},
    "uz": {"days": ("dushanba", "seshanba", "chorshanba", "payshanba", "juma", "shanba",
                    "yakshanba"),
           "sep": ", ", "no_days": "kunlar ko'rsatilmagan", "no_time": "vaqt ko'rsatilmagan",
           "where": "Joy", "how": "Usul", "depends": "{waste} mahallangizga bog'liq:",
           "yes": "mumkin", "no": "mumkin emas",
           "today": "Bugun", "tonight": "Bugun kechqurun", "tomorrow": "Ertaga",
           "no_collection": "Yig'ilmaydigan kunlar"},
    "ru": {"days": ("понедельник", "вторник", "среда", "четверг", "пятница", "суббота",
                    "воскресенье"),
           "sep": ", ", "no_days": "дни не указаны", "no_time": "время не указано",
           "where": "Где", "how": "Как", "depends": "{waste}: зависит от вашего района:",
           "yes": "можно", "no": "нельзя",
           "today": "Сегодня", "tonight": "Сегодня вечером", "tomorrow": "Завтра",
           "no_collection": "Дни без вывоза"},
}


@lru_cache(maxsize=1)
def glossary() -> dict[str, dict]:
    data = json.loads(paths.GLOSSARY.read_text(encoding="utf-8"))
    return {t["ko"]: t for t in data["terms"]}


def term(ko: str, lang: str) -> str:
    """'음식물쓰레기' -> 'Food waste (음식물쓰레기)'; Korean users get the Korean alone."""
    if lang == "ko":
        return ko
    text = glossary()[ko][lang]
    return f"{text[0].upper()}{text[1:]} ({ko})"


def _when(rule: WasteRule, lang: str) -> str:
    text = TEXT[lang]
    days = text["sep"].join(text["days"][d] for d in rule.days) or text["no_days"]
    time = f"{rule.start}-{rule.end}" if rule.start and rule.end else text["no_time"]
    return f"{days}, {time}"


def _verdict(rule: WasteRule, day: DayRef, lang: str) -> str:
    """'Tonight (Fri 2026-11-06): yes'. A weekday the user named is its own label."""
    text = TEXT[lang]
    weekday = text["days"][day.date.weekday()]
    label = text.get(day.label, weekday)
    stamp = day.date.isoformat() if label == weekday else f"{weekday} {day.date.isoformat()}"
    return f"{label} ({stamp}): {text['yes' if day.date.weekday() in rule.days else 'no']}"


def _zone_label(rows: list[ScheduleRow]) -> str:
    labels = []
    for row in rows:
        areas = ", ".join(row.area_names[:3]) + (" ..." if len(row.area_names) > 3 else "")
        labels.append(f"{row.zone} ({areas})" if row.zone and areas else row.zone or areas
                      or row.district)
    return "; ".join(dict.fromkeys(labels))


def _cite(rows: list[ScheduleRow], numbers: dict[str, int]) -> str:
    return "".join(f"[{numbers[r.row_id]}]" for r in rows)


def write_when(rows: list[ScheduleRow], waste_type: str | None, lang: str,
               day: DayRef | None, numbers: dict[str, int]) -> list[str]:
    """One line per waste type. Zones share a line when their days and times are the same,
    and get one line each when they are not, so no zone's schedule is dropped."""
    lines = []
    for t in waste_types(waste_type):
        groups: dict[tuple, list[ScheduleRow]] = {}
        for row in rows:
            rule = row.rules[t]
            if rule.days or rule.method:
                groups.setdefault((tuple(rule.days), rule.start, rule.end), []).append(row)
        waste = term(WASTE_TERMS[t], lang)
        if len(groups) == 1:
            group = next(iter(groups.values()))
            rule = group[0].rules[t]
            if day:
                lines.append(f"{waste}: {_verdict(rule, day, lang)}")
            lines.append(f"{waste}: {_when(rule, lang)} {_cite(group, numbers)}")
        elif groups:
            lines.append(TEXT[lang]["depends"].format(waste=waste))
            for group in groups.values():
                rule = group[0].rules[t]
                check = f" - {_verdict(rule, day, lang)}" if day else ""
                lines.append(f"- {_zone_label(group)}: {_when(rule, lang)}{check} "
                             f"{_cite(group, numbers)}")
    return lines


def write_where(rows: list[ScheduleRow], lang: str) -> str | None:
    kinds = list(dict.fromkeys(r.place_type for r in rows if r.place_type))
    places = list(dict.fromkeys(r.place for r in rows if r.place))
    parts = [term(k, lang) if k in PLACE_TERMS else k for k in kinds]
    if not parts and not places:
        return None
    # Several raw places are collection points, not an answer: the card lists them.
    detail = places[0] if len(places) == 1 and places[0] not in kinds else ""
    if not parts:
        parts, detail = [places[0]], ""
    return f"{TEXT[lang]['where']}: {', '.join(parts)}" + (f" - {detail}" if detail else "")


# --- No-collection days (미수거일). 229 distinct free-text values; the terms below cover 96% of
# rows. A value is translated only when every part of it is known, and the Korean is kept next
# to it; any other value is shown in Korean, as the source has it.
_NO_COLLECTION_TERMS = {
    "월": 0, "월요일": 0, "화": 1, "화요일": 1, "수": 2, "수요일": 2, "목": 3, "목요일": 3,
    "금": 4, "금요일": 4, "토": 5, "토요일": 5, "매주 토요일": 5, "매주토요일": 5, "일": 6,
    "일요일": 6, "매주 일요일": 6, "매주일요일": 6,
    "공휴일": "holidays", "법정공휴일": "holidays", "관공서 공휴일": "holidays", "휴일": "holidays",
    "국경일": "holidays", "대체공휴일": "substitute", "임시공휴일": "temporary",
    "일부 공휴일": "some_holidays", "일부공휴일": "some_holidays", "법정공휴일 중 일부": "some_holidays",
    "명절": "festive", "명절당일": "festive_day", "명절 당일": "festive_day",
    "명절다음날": "festive_next", "명절 다음날": "festive_next",
    "설": "seollal", "설날": "seollal", "설명절": "seollal", "설 명절": "seollal",
    "설날 당일": "seollal_day", "설명절당일": "seollal_day", "설명절 당일": "seollal_day",
    "추석": "chuseok", "추석날": "chuseok", "추석명절": "chuseok", "추석 명절": "chuseok",
    "추석 당일": "chuseok_day", "추석명절당일": "chuseok_day",
    "1월1일": "newyear", "1월 1일": "newyear", "신정": "newyear",
    "근로자의날": "labour", "근로자의 날": "labour", "주말": "weekend",
    "없음": "none", "연중무휴": "none",
}
NO_COLLECTION_WORDS = {
    "en": {"holidays": "public holidays", "substitute": "substitute holidays",
           "temporary": "temporary holidays", "some_holidays": "some public holidays",
           "festive": "Seollal and Chuseok holidays", "festive_day": "the day of Seollal and Chuseok",
           "festive_next": "the day after Seollal and Chuseok", "seollal": "Seollal (Lunar New Year)",
           "seollal_day": "Seollal day", "chuseok": "Chuseok", "chuseok_day": "Chuseok day",
           "newyear": "New Year's Day", "labour": "Labour Day (May 1)", "weekend": "weekends",
           "none": "none", "may_change": "may change"},
    "zh": {"holidays": "法定节假日", "substitute": "补休日", "temporary": "临时公休日",
           "some_holidays": "部分节假日", "festive": "春节和中秋节假期", "festive_day": "春节和中秋节当天",
           "festive_next": "春节和中秋节的第二天", "seollal": "春节", "seollal_day": "春节当天",
           "chuseok": "中秋节", "chuseok_day": "中秋节当天", "newyear": "元旦",
           "labour": "劳动节（5月1日）", "weekend": "周末", "none": "无", "may_change": "可能变动"},
    "vi": {"holidays": "ngày lễ", "substitute": "ngày nghỉ bù", "temporary": "ngày nghỉ lễ tạm thời",
           "some_holidays": "một số ngày lễ", "festive": "Tết Seollal và Chuseok",
           "festive_day": "ngày Tết Seollal và Chuseok", "festive_next": "ngày sau Tết Seollal và Chuseok",
           "seollal": "Tết Seollal (Tết Âm lịch)", "seollal_day": "ngày Tết Seollal",
           "chuseok": "Tết Chuseok", "chuseok_day": "ngày Chuseok", "newyear": "Tết Dương lịch",
           "labour": "Ngày Quốc tế Lao động (1/5)", "weekend": "cuối tuần", "none": "không có", "may_change": "có thể thay đổi"},
    "uz": {"holidays": "bayram kunlari", "substitute": "ko'chirilgan dam olish kunlari",
           "temporary": "vaqtinchalik dam olish kunlari", "some_holidays": "ba'zi bayram kunlari",
           "festive": "Seollal va Chuseok bayramlari", "festive_day": "Seollal va Chuseok kuni",
           "festive_next": "Seollal va Chuseokdan keyingi kun", "seollal": "Seollal (Oy yangi yili)",
           "seollal_day": "Seollal kuni", "chuseok": "Chuseok", "chuseok_day": "Chuseok kuni",
           "newyear": "Yangi yil", "labour": "Mehnat kuni (1-may)", "weekend": "dam olish kunlari",
           "none": "yo'q", "may_change": "o'zgarishi mumkin"},
    "ru": {"holidays": "праздничные дни", "substitute": "переносные выходные",
           "temporary": "временные выходные", "some_holidays": "некоторые праздники",
           "festive": "праздники Соллаль и Чхусок", "festive_day": "день Соллаль и Чхусок",
           "festive_next": "день после Соллаль и Чхусок", "seollal": "Соллаль (Лунный Новый год)",
           "seollal_day": "день Соллаль", "chuseok": "Чхусок", "chuseok_day": "день Чхусок",
           "newyear": "Новый год", "labour": "День труда (1 мая)", "weekend": "выходные",
           "none": "нет", "may_change": "может меняться"},
}
_SEPARATORS = re.compile(r"\s*(?:및|,|\+|·|/|ㆍ|、)\s*")


def no_collection_text(raw: str, lang: str) -> str:
    """'토+일' -> 'Sat, Sun (토+일)'. Korean, or anything not fully known, stays as written."""
    raw = (raw or "").strip()
    if lang == "ko" or not raw or lang not in NO_COLLECTION_WORDS:
        return raw
    value = re.sub(r"명절\s*\(\s*설\s*[,·]\s*추석\s*\)", "설+추석", raw)
    may_change = bool(re.search(r"\(\s*변동\s*가능\s*\)", value))
    value = re.sub(r"\(\s*변동\s*가능\s*\)", "", value)
    parts = [p.strip() for p in _SEPARATORS.split(value) if p.strip()]
    if not parts or any(p not in _NO_COLLECTION_TERMS for p in parts):
        return raw
    words = []
    for part in parts:
        key = _NO_COLLECTION_TERMS[part]
        words.append(TEXT[lang]["days"][key] if isinstance(key, int)
                     else NO_COLLECTION_WORDS[lang][key])
    if may_change:
        words.append(NO_COLLECTION_WORDS[lang]["may_change"])
    return f"{TEXT[lang]['sep'].join(dict.fromkeys(words))} ({raw})"


def write_no_collection(rows: list[ScheduleRow], lang: str) -> str | None:
    values = list(dict.fromkeys(no_collection_text(r.no_collection_days, lang) for r in rows
                                if r.no_collection_days))
    return f"{TEXT[lang]['no_collection']}: {'; '.join(values)}" if values else None


def method_lines(rows: list[ScheduleRow], waste_type: str | None) -> list[str]:
    return list(dict.fromkeys(r.rules[t].method for t in waste_types(waste_type) for r in rows
                              if r.rules[t].method))


def names_days(method: str) -> bool:
    return bool(_NAMES_DAYS.search(method))


# Letters only this language uses. qwen sometimes answers in romanised Korean ("acjeoekkeul
# keutjian ..."), which no check for a wrong script can see. Real Vietnamese lines scored 0.19
# or more and romanised Korean 0. This tests the script, not the meaning: "acjeo khi mọt tị
# trươn ..." has its letters and is still nonsense, which is why METHOD_LANGUAGE exists.
_OWN_LETTERS = {"vi": "[àáảãạăằắẳẵặâầấẩẫậèéẻẽẹêềếểễệìíỉĩịòóỏõọôồốổỗộơờớởỡợùúủũụưừứửữựỳýỷỹỵđ]",
                "zh": "[\u4e00-\u9fff]", "ru": "[а-яё]"}
_MIN_OWN_SHARE = 0.1


def usable_translation(source: str, text: str, lang: str) -> bool:
    """Every number kept, no other script outside the parentheses meant for Korean, and
    written in the language asked for."""
    if not text.strip():
        return False
    numbers = re.findall(r"\d+", text)
    if any(n not in numbers for n in re.findall(r"\d+", source)):
        return False
    outside = re.sub(r"\([^)]*\)", "", text)
    if lang in _OWN_LETTERS:
        own = len(re.findall(_OWN_LETTERS[lang], outside, re.IGNORECASE))
        if own < _MIN_OWN_SHARE * len(re.findall(r"[^\W\d_]", outside)):
            return False
    return not (re.search("[가-힣]", outside)
                or (lang != "zh" and re.search("[\u4e00-\u9fff]", outside))
                or (lang == "ru" and re.search("[a-zA-Z]{3,}", outside.replace("PET", ""))))


class ScheduleWriter:
    def __init__(self, llm, temperature: float = config.TEMPERATURE, seed: int = config.SEED):
        self.llm = llm
        self.temperature = temperature
        self.seed = seed

    def _translate_one(self, method: str, lang: str) -> tuple[str | None, str]:
        squeezed = method.replace(" ", "")
        terms = [ko for ko, spellings in TERMS.items() if any(s in squeezed for s in spellings)]
        block = "\n".join(f"  {ko} = {glossary()[ko][lang]}" for ko in terms)
        system, user = load_prompt(PROMPT)
        prompt = (user.replace("{language}", LANGUAGE_NAMES[lang])
                      .replace("{terms}", "- Translate these terms exactly like this:\n" + block
                               if terms else "- Translate plainly.")
                      .replace("{line}", method))
        result = self.llm.generate(system=system, prompt=prompt, json_schema=METHOD_SCHEMA,
                                   temperature=self.temperature, seed=self.seed, max_tokens=300)
        try:
            text = json.loads(result.text)["text"].strip()
        except (json.JSONDecodeError, KeyError, TypeError, AttributeError):
            return None, result.text
        return (text if usable_translation(method, text, lang) else None), result.text

    def translate(self, methods: list[str], lang: str) -> tuple[list[str], dict]:
        """Returns (lines, trace record). A line that cannot be trusted stays in Korean."""
        lang = METHOD_LANGUAGE.get(lang, lang)
        record = {"prompt": PROMPT, "language": lang, "source": methods, "kept_korean": [],
                  "raw_outputs": []}
        lines = []
        for method in methods:
            text = None
            if lang != "ko" and not names_days(method):
                for target in dict.fromkeys((lang, "en")):
                    text, raw = self._translate_one(method, target)
                    record["raw_outputs"].append(raw)
                    if text:
                        break
            if text is None and lang != "ko":
                record["kept_korean"].append(method)
            lines.append(text or method)
        return lines, record

    def write(self, rows: list[ScheduleRow], waste_type: str | None, lang: str | None,
              day: DayRef | None, first_n: int) -> tuple[dict, dict]:
        """The schedule part of an answer: (answer fields, trace record). `first_n` is the
        citation number of the first row, so it can follow the item evidence."""
        lang = lang if lang in TEXT else "en"
        numbers = {r.row_id: first_n + i for i, r in enumerate(rows)}
        lines = write_when(rows, waste_type, lang, day, numbers)
        where = write_where(rows, lang)
        if where:
            lines.append(where)
        no_collection = write_no_collection(rows, lang)
        if no_collection:
            lines.append(no_collection)
        how, record = self.translate(method_lines(rows, waste_type), lang)
        if how:
            lines.append(f"{TEXT[lang]['how']}: " + " / ".join(how))
        return {"status": "ANSWER", "bin": "", "bin_en": "", "how_to_prepare": how,
                "answer_text": "\n".join(lines), "citations": sorted(numbers.values()),
                "missing": ""}, record


def merge_schedule(answer: dict | None, written: dict) -> dict:
    """Add the code-written schedule part to the generator's item answer, if there is one."""
    if not answer:
        return dict(written)
    return {**answer,
            "answer_text": f"{answer['answer_text'].strip()}\n\n{written['answer_text']}",
            "how_to_prepare": list(answer.get("how_to_prepare", [])) + written["how_to_prepare"],
            "citations": sorted({*answer.get("citations", []), *written["citations"]})}
