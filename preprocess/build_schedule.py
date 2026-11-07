"""
Cleaned district schedule table and location lookups (PLAN.md §3.2, §4.5).

Input:  data/raw/korean_waste_policies.csv (data.go.kr, CP949, 10,187 rows)
Outputs (data/processed/):
  schedule.csv          UTF-8, the original Korean columns (cleaned) + extra columns:
                         관리구역대상지역명_원문, 구역비고, 전체구역, 요일기타, 오래된데이터 (as of built_on)
  schedule_chunks.jsonl  one text chunk per row, with province in the metadata (E4 vector variants;
                         9 MB, not committed: rebuild with this script)
  dong_lookup.json       neighbourhood -> rows; names that map to more than one district
  district_aliases.json  romanised names -> Korean (Seongdong-gu -> 성동구), for typed input
  locations.json         province -> districts -> zones/areas (website dropdowns), incl. no-data districts

Fixes (PLAN.md §3.2 table):
  1  area lists are split without losing names: '휘경1,2동' -> 휘경1동 + 휘경2동, names ending in
     읍/면/리/가/로 are kept, '(… 제외)' notes move to 구역비고, '전체'/'용산구 16개동' -> 전체구역
  2  province kept on every row and chunk (7 district names exist in several provinces)
  3  ambiguous neighbourhood names listed in dong_lookup.json
  4  data age computed; rows older than 365 days flagged
  -  district names without suffix fixed ('남양주' -> '남양주시'), zone '없음'/= district -> ''

    python -m preprocess.build_schedule
"""
from __future__ import annotations

import csv
import json
import re
from collections import Counter, defaultdict
from datetime import date, datetime
from zoneinfo import ZoneInfo

from preprocess.common import SOURCES, nfc, write_json
from rag import paths
from rag.files import sha256_file, write_jsonl
from rag.korean import romanize

RAW = SOURCES["schedule_csv"]["path"]
OUT = paths.PROCESSED_DIR
STALE_AFTER_DAYS = 365
DISTRICT_FIXES = {"남양주": "남양주시", "동두천": "동두천시"}
WHOLE = re.compile(r"^(전체|전지역|전역|없음|해당없음|관내\s*전지역|.*\d+\s*개\s*(동|읍|면|리)|.*(전역|일원))$")
SEOUL_DISTRICTS = ("종로구 중구 용산구 성동구 광진구 동대문구 중랑구 성북구 강북구 도봉구 노원구 은평구 "
                   "서대문구 마포구 양천구 강서구 구로구 금천구 영등포구 동작구 관악구 서초구 강남구 "
                   "송파구 강동구").split()
PROVINCE_EN = {
    "서울": ["seoul"], "부산": ["busan"], "대구": ["daegu"], "인천": ["incheon"],
    "광주": ["gwangju"], "대전": ["daejeon"], "울산": ["ulsan"], "세종": ["sejong"],
    "경기": ["gyeonggi", "gyeonggi-do"], "강원": ["gangwon", "gangwon-do"],
    "충청북": ["chungbuk", "chungcheongbuk-do"], "충청남": ["chungnam", "chungcheongnam-do"],
    "전북": ["jeonbuk", "jeollabuk-do"], "전라남": ["jeonnam", "jeollanam-do"],
    "전남광주": ["jeonnam", "gwangju"], "경상북": ["gyeongbuk", "gyeongsangbuk-do"],
    "경상남": ["gyeongnam", "gyeongsangnam-do"], "제주": ["jeju"],
}
SUFFIX_EN = {"구": "gu", "군": "gun", "시": "si"}
PROVINCE_NAMES_EN = {n for names in PROVINCE_EN.values() for n in names}


def province_en(province: str) -> list[str]:
    for prefix, names in sorted(PROVINCE_EN.items(), key=lambda kv: -len(kv[0])):
        if province.startswith(prefix):
            return names
    return []


# Number lists use any of these, sometimes mixed: 휘경1,2동  상계6.7동  청학1·2동  수성1,2.3,4가동
NUM_SEP = r"\s*[,.·ㆍ]\s*"
NUM_LIST = re.compile(rf"([가-힣]+?)(\d+(?:{NUM_SEP}\d+)+)(가동|동|리|가|공단|단지|지구)?(?=$|[+,·ㆍ/\s])")
NUMBERED = re.compile(r"(.*?)(\d+)(가동|동|리|가)?")


def _expand(match: re.Match) -> str:
    stem, numbers, suffix = match.group(1), match.group(2), match.group(3) or ""
    return "+".join(f"{stem}{n}{suffix}" for n in re.split(NUM_SEP, numbers))


def _carry_stem(part: str, previous: str) -> str:
    """'대연1동,2동' -> the fragment '2동' takes its stem from the name before it."""
    bare, before = NUMBERED.fullmatch(part), NUMBERED.fullmatch(previous)
    if not (bare and before) or bare.group(1) or not before.group(1):
        return part
    return f"{before.group(1)}{bare.group(2)}{bare.group(3) or before.group(3) or ''}"


def clean_areas(raw: str) -> tuple[list[str], list[str], bool]:
    """Area field -> (names, notes, whole_district)."""
    text, notes = nfc(raw), []
    star = text.find("※")
    if star >= 0:                                    # '… ※ 제외 : …' -> note
        notes.append(text[star:].strip())
        text = text[:star]
    while re.search(r"\([^()]*\)", text):            # '(… 제외)' -> note
        notes += re.findall(r"\(([^()]*)\)", text)
        text = re.sub(r"\([^()]*\)", "", text)
    text = NUM_LIST.sub(_expand, text)               # one name per number
    names, whole = [], False
    for part in re.split(r"[+,·ㆍ/]", text):
        part = part.strip()
        if not part:
            continue
        if WHOLE.match(part):
            whole = True
            continue
        if names:
            part = _carry_stem(part, names[-1])
        if part not in names:
            names.append(part)
    return names, [n.strip() for n in notes if n.strip()], whole


def clean_row(r: dict, today: date) -> tuple[dict, dict]:
    row = {k: nfc(v) for k, v in r.items()}
    flags = {}
    district = DISTRICT_FIXES.get(row["시군구명"], row["시군구명"])
    if district == "없음" and row["시도명"].startswith("세종"):
        district = "세종시"                          # Sejong has no 시군구 level
    if district != row["시군구명"]:
        flags["district_fixed"] = f"{row['시군구명']} -> {district}"
    row["시군구명"] = district
    zone = row["관리구역명"]
    inner = re.fullmatch(r"(.+?)\((.+)\)", zone)
    if inner and inner.group(1) in (row["시도명"], district):   # '세종특별자치시(1권역)' -> '1권역'
        zone = inner.group(2)
    # a zone name that only repeats the place ('서울특별시 동대문구', '서울시 중구') -> ''
    province_short = re.sub(r"(특별자치시|특별자치도|특별시|광역시|통합특별시|도)$", "", row["시도명"])
    rest = zone
    for name in sorted({row["시도명"], province_short + "시", province_short, district,
                        district[:-1] if len(district) > 2 else district}, key=len, reverse=True):
        rest = rest.replace(name, "")
    row["관리구역명"] = "" if zone == "없음" or not rest.strip(" ()") else zone
    names, notes, whole = clean_areas(row["관리구역대상지역명"])
    row["관리구역대상지역명_원문"] = row["관리구역대상지역명"]
    row["관리구역대상지역명"] = "+".join(names)
    row["구역비고"] = " / ".join(notes)
    row["전체구역"] = "Y" if whole or not names else "N"
    row["요일기타"] = "Y" if any("기타" in row[c] for c in
                                ("생활쓰레기배출요일", "음식물쓰레기배출요일", "재활용품배출요일")) else "N"
    try:
        age = (today - date.fromisoformat(row["데이터기준일자"])).days
    except ValueError:
        age = None
    row["오래된데이터"] = "Y" if age is None or age > STALE_AFTER_DAYS else "N"
    flags.update(whole_district=whole, notes=bool(notes), no_phone=not row["관리부서전화번호"],
                 age_days=age)
    return row, flags


def area_base(name: str) -> str:
    """Same rule as rag.schedule_tool.area_base: '행당1동' -> '행당동'."""
    name = re.sub(r"\(.*?\)", "", name).strip()
    return re.sub(r"제?\d+가?", "", name).replace(" ", "")


def district_aliases(pairs: list[tuple[str, str]]) -> dict:
    by_key: dict[str, set] = defaultdict(set)
    for province, district in pairs:
        if district == "없음":
            continue
        suffix = SUFFIX_EN.get(district[-1], "")
        base = romanize(district[:-1] if suffix else district)
        plain = {f"{base}-{suffix}", f"{base}{suffix}"} if suffix else set()
        if base not in PROVINCE_NAMES_EN:             # bare 'gwangju' means the city, not 광주시
            plain.add(base)
        keys = set(plain)
        for p in province_en(province):               # 'seoul jung-gu' -> ['서울특별시', '중구']
            keys |= {f"{p}{k}" for k in plain | ({base} if suffix else set())}
        for k in keys:
            by_key[k].add((province, district))
    if ("세종특별자치시", "세종시") in pairs:            # the province is the city
        by_key["sejong"].add(("세종특별자치시", "세종시"))
    aliases = {}
    for key, targets in sorted(by_key.items()):
        names = {d for _, d in targets}
        if len(names) > 1:
            continue                                  # one spelling, different districts: skip
        if len(targets) == 1:
            aliases[key] = list(next(iter(targets)))  # [province, district]
        else:
            aliases[key] = next(iter(names))          # same name in several provinces -> clarify
    return aliases


def schedule_chunk(row: dict) -> dict:
    place = " ".join(p for p in (row["시도명"], row["시군구명"], row["관리구역명"]) if p)
    lines = [f"[{place}] 쓰레기 배출 안내",
             "대상 지역: " + (row["관리구역대상지역명"].replace("+", ", ") or "전체")]
    for label, prefix in (("생활쓰레기", "생활쓰레기"), ("음식물쓰레기", "음식물쓰레기"),
                          ("재활용품", "재활용품")):
        lines.append(f"{label}: {row[prefix + '배출방법']} / 요일: {row[prefix + '배출요일']} / "
                     f"시간: {row[prefix + '배출시작시각']}~{row[prefix + '배출종료시각']}")
    lines += [f"미수거일: {row['미수거일']}",
              f"문의: {row['관리부서명']} ({row['관리부서전화번호']})",
              f"데이터 기준일: {row['데이터기준일자']}"]
    # No `stale` flag here: it depends on the build date, so it would change the corpus hash
    # and invalidate the index with no change in content. The runtime computes it.
    return {"id": f"schedule_{row['관리번호']}", "text": "\n".join(lines),
            "metadata": {"doc_type": "schedule", "row_id": row["관리번호"],
                         "province": row["시도명"], "district": row["시군구명"],
                         "zone": row["관리구역명"], "areas": row["관리구역대상지역명"].replace("+", ", "),
                         "data_date": row["데이터기준일자"],
                         "source": SOURCES["schedule_csv"]["title"]}}


def build(today: date | None = None) -> dict:
    today = today or datetime.now(ZoneInfo("Asia/Seoul")).date()
    with RAW.open(encoding="cp949", newline="") as f:
        reader = csv.DictReader(f)
        raw_rows = list(reader)
        raw_columns = [c.strip() for c in reader.fieldnames]
    cleaned, flags = zip(*(clean_row(r, today) for r in raw_rows), strict=True)
    # no per-day age column: it would change the file every day (age is computed at runtime)
    columns = raw_columns + ["관리구역대상지역명_원문", "구역비고", "전체구역", "요일기타", "오래된데이터"]
    with (OUT / "schedule.csv").open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=columns)
        writer.writeheader()
        writer.writerows({c: r.get(c, "") for c in columns} for r in cleaned)
    write_jsonl(OUT / "schedule_chunks.jsonl", [schedule_chunk(r) for r in cleaned])

    # neighbourhood lookup
    lookup: dict[str, list] = defaultdict(list)
    for r in cleaned:
        for name in r["관리구역대상지역명"].split("+"):
            if not name:
                continue
            entry = {"province": r["시도명"], "district": r["시군구명"], "zone": r["관리구역명"],
                     "row_id": r["관리번호"], "area": name}
            for key in {name, area_base(name)}:
                if entry not in lookup[key]:
                    lookup[key].append(entry)
    ambiguous = {k: sorted({f"{e['province']} {e['district']}" for e in v})
                 for k, v in lookup.items()
                 if len({(e["province"], e["district"]) for e in v}) > 1}
    write_json(OUT / "dong_lookup.json", {"names": dict(sorted(lookup.items())),
                                          "ambiguous": dict(sorted(ambiguous.items()))})

    # districts, aliases, dropdown data
    pairs = sorted({(r["시도명"], r["시군구명"]) for r in cleaned})
    aliases = district_aliases(pairs)
    write_json(OUT / "district_aliases.json", aliases)
    zones = defaultdict(list)
    for r in cleaned:
        zones[(r["시도명"], r["시군구명"])].append(
            {"zone": r["관리구역명"], "row_id": r["관리번호"],
             "areas": [a for a in r["관리구역대상지역명"].split("+") if a],
             "whole_district": r["전체구역"] == "Y", "data_date": r["데이터기준일자"],
             "stale": r["오래된데이터"] == "Y"})
    locations = []
    for province, district in pairs:
        suffix = SUFFIX_EN.get(district[-1], "")
        base = romanize(district[:-1] if suffix else district)
        locations.append({"province": province, "province_en": (province_en(province) or [""])[0],
                          "district": district,
                          "district_en": (base.capitalize() + (f"-{suffix}" if suffix else "")),
                          "has_data": True, "zones": zones[(province, district)]})
    seoul = {d for p, d in pairs if p.startswith("서울")}
    for d in SEOUL_DISTRICTS:
        if d not in seoul:
            locations.append({"province": "서울특별시", "province_en": "seoul", "district": d,
                              "district_en": romanize(d[:-1]).capitalize() + "-gu",
                              "has_data": False, "zones": []})
    write_json(OUT / "locations.json", locations)

    ages = [f["age_days"] for f in flags if f["age_days"] is not None]
    dup_names = Counter(d for _, d in pairs)
    return {
        "input": paths.relative(RAW), "input_sha256": sha256_file(RAW),
        "built_on": today.isoformat(),
        "outputs": {name: sha256_file(OUT / name) for name in
                    ("schedule.csv", "schedule_chunks.jsonl", "dong_lookup.json",
                     "district_aliases.json", "locations.json")},
        "rows": len(cleaned), "province_district_pairs": len(pairs),
        "provinces": len({p for p, _ in pairs}),
        "district_names_in_several_provinces": {d: n for d, n in dup_names.items() if n > 1},
        "district_name_fixes": dict(Counter(f["district_fixed"] for f in flags if "district_fixed" in f)),
        "rows_with_district_none": sum(r["시군구명"] == "없음" for r in cleaned),
        "seoul_districts_without_data": [d for d in SEOUL_DISTRICTS if d not in seoul],
        "rows_whole_district": sum(f["whole_district"] for f in flags),
        "rows_with_area_notes": sum(f["notes"] for f in flags),
        "rows_without_area_names": sum(not r["관리구역대상지역명"] for r in cleaned),
        "rows_days_irregular": sum(r["요일기타"] == "Y" for r in cleaned),
        "rows_without_phone": sum(f["no_phone"] for f in flags),
        "rows_stale": sum(r["오래된데이터"] == "Y" for r in cleaned),
        "data_year_counts": dict(sorted(Counter(r["데이터기준일자"][:4] for r in cleaned).items())),
        "data_age_days_median": sorted(ages)[len(ages) // 2] if ages else None,
        "area_names": len(lookup), "ambiguous_area_names": len(ambiguous),
        "district_aliases": len(aliases),
        "place_types": dict(Counter(r["배출장소유형"] for r in cleaned)),
    }


if __name__ == "__main__":
    print(json.dumps(build(), ensure_ascii=False, indent=2))
