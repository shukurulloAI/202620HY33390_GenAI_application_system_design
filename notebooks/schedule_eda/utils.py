import pandas as pd
import re
import os
import json
from datetime import date, datetime

def read_csv_file(file_path):
    encodings = ["utf-8-sig", "cp949", "euc-kr"]
    separators = [",", "\t"]

    for enc in encodings:
        for sep in separators:
            try:
                df = pd.read_csv(
                    file_path,
                    sep=sep,
                    dtype=str,
                    keep_default_na=False,
                    encoding=enc,
                    quoting=3 if sep == "\t" else 0,   # tab files: ignore quotes, csv files: normal quotes
                )
            except (UnicodeDecodeError, pd.errors.ParserError):
                continue

            df.columns = [c.strip() for c in df.columns]   # remove hidden spaces
            if "시군구명" in df.columns:
                print(f"Loaded with encoding={enc}, sep={repr(sep)}, {len(df)} rows")
                return df

    raise ValueError("Could not read the file. Check the separator and encoding.")

def clean(value):
    value = str(value).strip()
    if value == "":
        return "정보 없음"      # no information
    if value == "없음":
        return "해당 없음"      # the source says "none"
    return value

def fix_time(t):
    t = t.strip().replace(":", "")   # "0:00" -> "000", "2400" -> "2400"
    if t == "":
        return ""
    t = t.zfill(4)                   # "000" -> "0000", "100" -> "0100"
    return t[:2] + ":" + t[2:]       # "0000" -> "00:00"

def time_range(start, end):
    s, e = fix_time(start), fix_time(end)
    if s == "" and e == "":
        return "정보 없음"
    return s + "~" + e

def fix_days(d):
    d = d.strip()
    if d in ("", "없음"):
        return "정보 없음"
    return d.replace("+", ", ")      # "월+수+금" -> "월, 수, 금"

def split_dongs(area):
    """Split and normalize every named service area.

    The source column contains more than dong names: it also uses eup, myeon,
    ri, ga, ro, district-wide labels, and notes in parentheses. Keep those
    values instead of dropping them because they identify the policy scope.
    """
    area = str(area).strip()
    if area in ("", "없음"):
        return []

    # Expand compact forms such as "휘경1,2동" and "독산1,2,4동".
    area = re.sub(
        r"([가-힣]+)(\d(?:[.,]\d)+)(동|읍|면|리|가|로)",
        lambda match: ",".join(
            f"{match.group(1)}{number}{match.group(3)}"
            for number in re.split(r"[.,]", match.group(2))
        ),
        area,
    )
    area = area.replace("ㆍ", ",").replace("·", ",").replace("+", ",")

    # Split only on top-level separators; commas inside parentheses are notes.
    parts = []
    current = []
    depth = 0
    for character in area:
        if character == "(":
            depth += 1
        elif character == ")" and depth:
            depth -= 1
        if character == "," and depth == 0:
            value = "".join(current).strip()
            if value:
                parts.append(value)
            current = []
        else:
            current.append(character)
    value = "".join(current).strip()
    if value:
        parts.append(value)

    return [re.sub(r"\s+", " ", value) for value in parts]

def fix_zone(zone, district):
    zone = zone.strip()
    if zone in ("", "없음") or district in zone:   # "서울시 중구" just repeats the district
        return ""
    return zone                                      # keeps "1권역", "2권역"


def clean_row(row):
    province = row["시도명"].strip()
    district = row["시군구명"].strip()
    return {
        "id": "waste_" + row["관리번호"].strip(),
        "province": province,
        "district": district,
        "zone": fix_zone(row["관리구역명"], district),
        "dongs": split_dongs(row["관리구역대상지역명"]),
        "collection_place_type": clean(row["배출장소유형"]),
        "collection_place": clean(row["배출장소"]),

        "general_method": clean(row["생활쓰레기배출방법"]),
        "general_days": fix_days(row["생활쓰레기배출요일"]),
        "general_time": time_range(row["생활쓰레기배출시작시각"], row["생활쓰레기배출종료시각"]),

        "food_method": clean(row["음식물쓰레기배출방법"]),
        "food_days": fix_days(row["음식물쓰레기배출요일"]),
        "food_time": time_range(row["음식물쓰레기배출시작시각"], row["음식물쓰레기배출종료시각"]),

        "recycle_method": clean(row["재활용품배출방법"]),
        "recycle_days": fix_days(row["재활용품배출요일"]),
        "recycle_time": time_range(row["재활용품배출시작시각"], row["재활용품배출종료시각"]),

        "bulky_method": clean(row["일시적다량폐기물배출방법"]),
        "bulky_place": clean(row["일시적다량폐기물배출장소"]),

        "no_collection": fix_days(row["미수거일"]),
        "department": clean(row["관리부서명"]),
        "phone": clean(row["관리부서전화번호"]),
        "data_date": row["데이터기준일자"].strip(),
    }


def data_age_warning(data_date, as_of=None, max_age_days=365):
    """Return a warning when a policy reference date is older than the limit."""
    if not data_date:
        return "데이터 기준일 없음"
    try:
        reference = datetime.strptime(str(data_date).strip(), "%Y-%m-%d").date()
    except ValueError:
        return "데이터 기준일 확인 필요"
    current = as_of or date.today()
    if (current - reference).days > max_age_days:
        return f"오래된 데이터: {data_date} 기준"
    return ""

def make_chunk_text(r):
    title = f"{r['province']} {r['district']} {r['zone']}".strip()
    lines = [f"[{title}] 쓰레기 배출 안내"]

    if r["dongs"]:
        lines.append("대상 지역: " + ", ".join(r["dongs"]))

    lines.append(f"배출장소: {r['collection_place_type']} / {r['collection_place']}")
    lines.append(f"생활쓰레기: {r['general_method']} / 요일: {r['general_days']} / 시간: {r['general_time']}")
    lines.append(f"음식물쓰레기: {r['food_method']} / 요일: {r['food_days']} / 시간: {r['food_time']}")
    lines.append(f"재활용품: {r['recycle_method']} / 요일: {r['recycle_days']} / 시간: {r['recycle_time']}")
    lines.append(f"대형폐기물: {r['bulky_method']} / 장소: {r['bulky_place']}")
    lines.append(f"미수거일: {r['no_collection']}")
    lines.append(f"문의: {r['department']} ({r['phone']})")
    lines.append(f"데이터 기준일: {r['data_date']}")
    warning = data_age_warning(r["data_date"])
    if warning:
        lines.append(f"주의: {warning}")
    return "\n".join(lines)


def build_chunks(records):
    """Turn cleaned records into a list of chunks (id, text, metadata)."""
    chunks = []
    for r in records:
        chunks.append({
            "id": r["id"],
            "text": make_chunk_text(r),
            "metadata": {
                "province": r["province"],
                "district": r["district"],
                "zone": r["zone"],
                "dongs": ", ".join(r["dongs"]),
                "collection_place_type": r["collection_place_type"],
                "collection_place": r["collection_place"],
                "phone": r["phone"],
                "data_date": r["data_date"],
                "data_age_warning": data_age_warning(r["data_date"]),
            },
        })
    return chunks

def save_chunks(chunks, path="output/chunks.jsonl"):
    """Save chunks to a .jsonl file, one chunk per line."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        for chunk in chunks:
            f.write(json.dumps(chunk, ensure_ascii=False) + "\n")
    print(f"Saved {len(chunks)} chunks to {path}")


def save_json(data, path):
    """Save any dictionary or list as a readable JSON file."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"Saved {path}")

def build_dong_lookup(records):
    """Area name -> all matching province/district policies.

    A name can exist in multiple districts, so callers must keep every match
    and ask the user to clarify when the province or district is missing.
    """
    lookup = {}
    for r in records:
        for dong in r["dongs"]:
            lookup.setdefault(dong, []).append(
                {
                    "province": r["province"],
                    "district": r["district"],
                    "zone": r["zone"],
                    "chunk_id": r["id"],
                }
            )
    return lookup