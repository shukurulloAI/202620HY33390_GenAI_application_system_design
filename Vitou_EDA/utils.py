import pandas as pd
import re
import os
import json

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
    # "휘경1,2동" -> "휘경1동,휘경2동"
    area = re.sub(r"([가-힣]+)(\d),(\d)동", r"\1\2동,\1\3동", area)
    area = area.replace("+", ",")
    dongs = []
    for d in area.split(","):
        d = d.strip()
        if d.endswith("동") and " " not in d:   # skip "용산구 16개동"
            dongs.append(d)
    return dongs

def fix_zone(zone, district):
    zone = zone.strip()
    if zone in ("", "없음") or district in zone:   # "서울시 중구" just repeats the district
        return ""
    return zone                                      # keeps "1권역", "2권역"


def clean_row(row):
    district = row["시군구명"].strip()
    return {
        "id": "waste_" + row["관리번호"].strip(),
        "province": row["시도명"].strip(),
        "district": district,
        "zone": fix_zone(row["관리구역명"], district),
        "dongs": split_dongs(row["관리구역대상지역명"]),

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

def make_chunk_text(r):
    title = f"{r['province']} {r['district']} {r['zone']}".strip()
    lines = [f"[{title}] 쓰레기 배출 안내"]

    if r["dongs"]:
        lines.append("대상 지역: " + ", ".join(r["dongs"]))

    lines.append(f"생활쓰레기: {r['general_method']} / 요일: {r['general_days']} / 시간: {r['general_time']}")
    lines.append(f"음식물쓰레기: {r['food_method']} / 요일: {r['food_days']} / 시간: {r['food_time']}")
    lines.append(f"재활용품: {r['recycle_method']} / 요일: {r['recycle_days']} / 시간: {r['recycle_time']}")
    lines.append(f"대형폐기물: {r['bulky_method']} / 장소: {r['bulky_place']}")
    lines.append(f"미수거일: {r['no_collection']}")
    lines.append(f"문의: {r['department']} ({r['phone']})")
    lines.append(f"데이터 기준일: {r['data_date']}")
    return "\n".join(lines)


def build_chunks(records):
    """Turn cleaned records into a list of chunks (id, text, metadata)."""
    chunks = []
    for r in records:
        chunks.append({
            "id": r["id"],
            "text": make_chunk_text(r),
            "metadata": {
                "district": r["district"],
                "zone": r["zone"],
                "dongs": ", ".join(r["dongs"]),
                "phone": r["phone"],
                "data_date": r["data_date"],
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
    """dong name -> list of {district, zone, chunk_id}."""
    lookup = {}
    for r in records:
        for dong in r["dongs"]:
            lookup.setdefault(dong, []).append(
                {"district": r["district"], "zone": r["zone"], "chunk_id": r["id"]}
            )
    return lookup