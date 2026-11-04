"""
Schedule lookup tool (PLAN.md §4.5; Lesson 1 "use a tool", Lesson 5 typed filters).

When and where to put waste out is answered by deterministic code over the district
table, never by the LLM or by vector search (the rows are near-duplicate text).

Input table: Vitou's cleaned `preprocess/schedule.csv` (UTF-8, original Korean column
names + any extra columns) if it exists, otherwise the raw data.go.kr CSV (CP949).

Statuses:
    OK       rows found (one zone, or all zones of the district if the area is unknown)
    CLARIFY  the district name exists in several provinces -> ask the user
    NO_DATA  no rows for this district (e.g. Seoul Gangdong-gu, Dobong-gu)

Usage:
    python -m rag.schedule_tool 성동구 --dong 행당동
    python -m rag.schedule_tool 중구
"""
from __future__ import annotations

import argparse
import csv
import json
import re
from dataclasses import asdict, dataclass, field
from datetime import date, datetime, timedelta
from functools import lru_cache
from pathlib import Path
from zoneinfo import ZoneInfo

from rag import config

KST = ZoneInfo("Asia/Seoul")
STALE_AFTER_DAYS = 365
WASTE_TYPES = {                       # key -> CSV column prefix
    "general": "생활쓰레기",
    "food": "음식물쓰레기",
    "recycling": "재활용품",
    "bulky": "일시적다량폐기물",
}
WASTE_TYPE_EN = {"general": "General waste (pay-as-you-throw bag)", "food": "Food waste",
                 "recycling": "Recyclables", "bulky": "Temporary large amounts / bulky"}
DAY_KO = "월화수목금토일"              # index = date.weekday()
DAY_EN = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")


@dataclass
class WasteRule:
    method: str
    days: list[int]           # weekday numbers, Mon = 0
    days_raw: str
    start: str | None
    end: str | None

    def days_en(self) -> str:
        return ", ".join(DAY_EN[d] for d in self.days) or "not specified"


@dataclass
class ScheduleRow:
    row_id: str               # 관리번호
    province: str
    district: str
    zone: str
    area_names: list[str]
    place_type: str
    place: str
    rules: dict[str, WasteRule]
    bulky_place: str
    no_collection_days: str
    office: str
    phone: str
    data_date: str

    def data_age_days(self, today: date | None = None) -> int | None:
        try:
            return ((today or datetime.now(KST).date())
                    - date.fromisoformat(self.data_date)).days
        except ValueError:
            return None

    def is_stale(self) -> bool:
        age = self.data_age_days()
        return age is None or age > STALE_AFTER_DAYS

    def to_evidence(self, waste_type: str | None = None) -> str:
        """Text block for the generator. Days are already in English, so the model
        never has to translate or compute them."""
        types = [waste_type] if waste_type in WASTE_TYPES else list(WASTE_TYPES)
        lines = [f"[District schedule] {self.province} {self.district} - zone {self.zone}",
                 f"Areas: {', '.join(self.area_names) or 'whole district'}",
                 f"Where: {self.place_type} / {self.place}"]
        for t in types:
            rule = self.rules[t]
            if not (rule.method or rule.days):
                continue
            when = f"{rule.start}-{rule.end}" if rule.start and rule.end else "time not given"
            lines.append(f"{WASTE_TYPE_EN[t]} ({WASTE_TYPES[t]}): days {rule.days_en()}; "
                         f"time {when}; method: {rule.method or 'not given'}")
        if self.bulky_place and "bulky" in types:
            lines.append(f"Bulky waste place: {self.bulky_place}")
        lines.append(f"No collection: {self.no_collection_days or 'not given'}")
        lines.append(f"Office: {self.office} {self.phone}".strip())
        stale = " (older than 1 year - may be outdated)" if self.is_stale() else ""
        lines.append(f"Data date: {self.data_date}{stale}")
        return "\n".join(lines)

    def to_dict(self) -> dict:
        record = asdict(self)
        record["stale"] = self.is_stale()
        return record


@dataclass
class ScheduleResult:
    status: str                         # OK | CLARIFY | NO_DATA
    query: dict
    rows: list[ScheduleRow] = field(default_factory=list)
    matched_on: str | None = None       # "area" | "district"
    options: list[str] = field(default_factory=list)
    message: str = ""

    def to_trace(self) -> dict:
        return {"status": self.status, "query": self.query, "matched_on": self.matched_on,
                "row_ids": [r.row_id for r in self.rows], "options": self.options,
                "message": self.message}


# ---------------------------------------------------------------- parsing helpers

def normalize_time(value: str) -> str | None:
    value = (value or "").strip()
    if not value:
        return None
    if re.fullmatch(r"\d{4}", value):                 # "2400" -> "24:00"
        value = f"{value[:2]}:{value[2:]}"
    return value


def parse_days(value: str) -> list[int]:
    days = []
    for ch in value or "":
        if ch in DAY_KO and DAY_KO.index(ch) not in days:
            days.append(DAY_KO.index(ch))
    return sorted(days)


def split_areas(value: str) -> list[str]:
    return [a.strip() for a in re.split(r"[+,·/]", value or "") if a.strip()]


def area_base(name: str) -> str:
    """'행당1동' -> '행당동', '왕십리제2동' -> '왕십리동', '성수1가1동' -> '성수동'."""
    name = re.sub(r"\(.*?\)", "", name).strip()
    return re.sub(r"제?\d+가?", "", name).replace(" ", "")


def district_base(name: str) -> str:
    return re.sub(r"(구|시|군)$", "", name.replace(" ", ""))


def row_from_csv(r: dict) -> ScheduleRow:
    rules = {}
    for key, prefix in WASTE_TYPES.items():
        rules[key] = WasteRule(
            method=(r.get(f"{prefix}배출방법") or "").strip(),
            days=parse_days(r.get(f"{prefix}배출요일", "")),
            days_raw=(r.get(f"{prefix}배출요일") or "").strip(),
            start=normalize_time(r.get(f"{prefix}배출시작시각", "")),
            end=normalize_time(r.get(f"{prefix}배출종료시각", "")))
    return ScheduleRow(
        row_id=r["관리번호"].strip(), province=r["시도명"].strip(),
        district=r["시군구명"].strip(), zone=(r.get("관리구역명") or "").strip(),
        area_names=split_areas(r.get("관리구역대상지역명", "")),
        place_type=(r.get("배출장소유형") or "").strip(),
        place=(r.get("배출장소") or "").strip(), rules=rules,
        bulky_place=(r.get("일시적다량폐기물배출장소") or "").strip(),
        no_collection_days=(r.get("미수거일") or "").strip(),
        office=(r.get("관리부서명") or "").strip(),
        phone=(r.get("관리부서전화번호") or "").strip(),
        data_date=(r.get("데이터기준일자") or "").strip())


# ---------------------------------------------------------------- the tool

class ScheduleTable:
    def __init__(self, rows: list[ScheduleRow], source: str, aliases: dict | None = None):
        self.rows = rows
        self.source = source
        self.aliases = {k.lower().replace(" ", ""): v for k, v in (aliases or {}).items()}

    @classmethod
    def load(cls, path: Path | None = None) -> "ScheduleTable":
        path = path or next((p for p in config.SCHEDULE_PATHS if p.exists()), None)
        if path is None:
            raise FileNotFoundError("no schedule table found")
        encoding = "cp949" if path.name == "korean_waste_policies.csv" else "utf-8-sig"
        with path.open(encoding=encoding, newline="") as f:
            rows = [row_from_csv(r) for r in csv.DictReader(f)]
        aliases = {}
        if config.DISTRICT_ALIASES_PATH.exists():
            aliases = json.loads(config.DISTRICT_ALIASES_PATH.read_text(encoding="utf-8"))
        return cls(rows, str(path.relative_to(config.ROOT)), aliases)

    def _resolve_alias(self, district: str, province: str | None):
        """Alias file (Vitou): {"seongdong-gu": "성동구"} or {"...": ["서울특별시", "성동구"]}."""
        value = self.aliases.get(district.lower().replace(" ", ""))
        if isinstance(value, list) and len(value) == 2:
            return value[1], province or value[0]
        if isinstance(value, str):
            return value, province
        return district, province

    def lookup(self, district: str | None, province: str | None = None,
               dong: str | None = None, waste_type: str | None = None) -> ScheduleResult:
        query = {"district": district, "province": province, "dong": dong,
                 "waste_type": waste_type}
        if not district:
            return ScheduleResult("NO_DATA", query, message="no district given")
        district, province = self._resolve_alias(district.strip(), province)
        if " " in district and not province:          # "서울특별시 성동구"
            province, district = district.rsplit(" ", 1)

        rows = [r for r in self.rows if r.district == district]
        if not rows:                                   # "성동" -> "성동구"
            rows = [r for r in self.rows if district_base(r.district) == district_base(district)]
        if not rows:
            return ScheduleResult("NO_DATA", query,
                                  message=f"no schedule data for district '{district}'")

        if province:
            prov = province.replace(" ", "")[:2]
            in_province = [r for r in rows if r.province.startswith(prov)]
            if not in_province:
                return ScheduleResult("NO_DATA", query,
                                      message=f"no '{district}' in province '{province}'")
            rows = in_province
        provinces = sorted({r.province for r in rows})
        if len(provinces) > 1:
            return ScheduleResult(
                "CLARIFY", query, options=[f"{p} {rows[0].district}" for p in provinces],
                message=f"'{rows[0].district}' exists in {len(provinces)} provinces")

        if dong:
            target = area_base(dong)
            zone_rows = [r for r in rows
                         if any(a == dong or area_base(a) == target for a in r.area_names)]
            if zone_rows:
                message = (f"'{dong}' matches {len(zone_rows)} zones "
                           f"({', '.join(a for r in zone_rows for a in r.area_names if area_base(a) == target)}); "
                           "ask for the exact neighbourhood" if len(zone_rows) > 1 else "")
                return ScheduleResult("OK", query, zone_rows, matched_on="area",
                                      message=message)
            return ScheduleResult(
                "OK", query, rows, matched_on="district",
                message=f"area '{dong}' not found; showing all {len(rows)} zones")
        message = (f"{len(rows)} zones; the schedule depends on the neighbourhood"
                   if len(rows) > 1 else "")
        return ScheduleResult("OK", query, rows, matched_on="district", message=message)


@lru_cache(maxsize=1)
def default_table() -> ScheduleTable:
    return ScheduleTable.load()


# ---------------------------------------------------------------- date helper

def put_out_days(row: ScheduleRow, waste_type: str, start: date | None = None,
                 n_days: int = 7) -> list[str]:
    """Next dates (ISO) in the coming n_days on which this waste type can be put out.
    Holidays in `no_collection_days` are free text and are NOT applied here."""
    start = start or datetime.now(KST).date()
    rule = row.rules[waste_type]
    return [(start + timedelta(d)).isoformat() for d in range(n_days)
            if (start + timedelta(d)).weekday() in rule.days]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("district")
    parser.add_argument("--province")
    parser.add_argument("--dong")
    parser.add_argument("--waste-type", choices=sorted(WASTE_TYPES))
    args = parser.parse_args()
    table = default_table()
    result = table.lookup(args.district, args.province, args.dong, args.waste_type)
    print(json.dumps(result.to_trace(), ensure_ascii=False, indent=2))
    for row in result.rows[:5]:
        print("\n" + row.to_evidence(args.waste_type))


if __name__ == "__main__":
    main()
