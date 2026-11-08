"""
Build the evaluation set (PLAN.md §7.1-7.2) and freeze its dev/test split.

    python -m eval.make_cases            # writes eval/cases/{dev,test}.jsonl + split_manifest.json
    python -m eval.make_cases --check    # rebuild in memory, fail if the files differ

Sources:
    eval/cases/source/handwritten.jsonl  65 cases written by hand: tricky items, 2018/2026
                                         conflicts, false premises, no evidence, ambiguous
                                         places, out of scope, item + schedule combined
    eval/cases/source/item_names.json    names in six languages for the sampled items below
    templates (this file)                20 dictionary items, 2 per bin (seeded), and 15
                                         schedule questions, one per district (seeded)

Gold labels come from the data, never from the system: chunk IDs are the legacy IDs written
in the sources, resolved to UUIDs here; schedule rows come from a table scan
(eval/label_helper.py). Every case is checked by eval.cases.validate_case.

Split: 70/30 per slice with a fixed seed, made once, before any tuning, and recorded with
the SHA-256 of both files. Cases about an item or place already used in development (the
probes, the website examples) are `seen_in_development` and always go to dev, so the test
split holds only unseen items. The test file is not read during development
(experiments/run_experiment.py refuses it without --allow-test).

Schedule questions are sampled by district, not by row: 정선군 and 고흥군 alone hold about a
third of the rows, and the slice should measure the districts, not two of them
(docs/PHASE2_NOTES.md §10).
"""
from __future__ import annotations

import argparse
import json
import random
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime

from eval.cases import validate_case
from eval.label_helper import schedule_rows
from eval.provenance import git_commit
from rag import paths
from rag.bins import evidence_bins
from rag.files import read_jsonl, sha256_file
from rag.schedule_tool import default_table

VERSION = "v1"
SEED = 20261108
TEST_SHARE = 0.3
SOURCE_DIR = paths.ROOT / "eval" / "cases" / "source"
HANDWRITTEN = SOURCE_DIR / "handwritten.jsonl"
ITEM_NAMES = SOURCE_DIR / "item_names.json"
CASES_DIR = paths.ROOT / "eval" / "cases"
TEST_CASES = CASES_DIR / "test.jsonl"
MANIFEST = CASES_DIR / "split_manifest.json"

# Items already used in development (probes, few-shot prompts, website examples) or in the
# handwritten cases: never sampled as template items.
USED_ITEM_WORDS = ("피자 닭 뼈 계란 전지 매트 페트 약 스티로폼 매니큐어 볼펜 소화기 볼풀공 고무장갑 "
                   "보온병 스프레이 영수증 티백 형광등 유리 커피 생선 파인애플 기름 아이스팩 물티슈 "
                   "치킨 라이터 핫팩 조개 머그컵 복숭아 우유팩 종이팩 우산 의류 전동칫솔 체온계 "
                   "장난감 후라이팬 바나나 나무젓가락 책 샴푸 비닐봉지 신문지 캔").split()
# Districts used in development or in the handwritten cases, and names found in several
# provinces (those are the ambiguous_location slice).
USED_DISTRICTS = {"성동구", "중구", "강동구", "도봉구", "광진구", "동대문구", "은평구", "양천구",
                  "강남구", "동작구", "노원구", "성북구", "수성구", "춘천시", "서초구", "송파구",
                  "고성군", "동구", "남구", "서구", "강서구", "북구"}
N_ITEMS, N_SCHEDULE = 20, 15
# Languages of the 35 template cases, so the whole set is ~40% en, ~30% ko, ~30% others.
TEMPLATE_LANGS = ["en"] * 15 + ["ko"] * 16 + ["uz"] * 3 + ["vi"] * 1

ITEM_TEMPLATES = {
    "en": ["How do I throw away {item}?", "Where does {item} go?"],
    "ko": ["{item} 어떻게 버려요?", "{item} 버리는 방법 알려주세요."],
    "zh": ["{item}应该怎么扔？", "{item}扔到哪里？"],
    "vi": ["Tôi nên vứt {item} ở đâu?", "{item} bỏ vào thùng nào?"],
    "uz": ["{item} qanday tashlanadi?", "{item} qaysi idishga tashlanadi?"],
    "ru": ["{item} — куда выбрасывать?", "{item} — в какой контейнер?"],
}
WASTE_WORDS = {
    "en": {"general": "general waste", "food": "food waste", "recycling": "recycling"},
    "ko": {"general": "일반쓰레기", "food": "음식물쓰레기", "recycling": "재활용품"},
    "zh": {"general": "普通垃圾", "food": "厨余垃圾", "recycling": "可回收物"},
    "vi": {"general": "rác thông thường", "food": "rác thực phẩm", "recycling": "rác tái chế"},
    "uz": {"general": "Maishiy chiqindilar", "food": "Oziq-ovqat chiqindilari",
           "recycling": "Qayta ishlanadigan chiqindilar"},
    "ru": {"general": "обычный мусор", "food": "пищевые отходы", "recycling": "вторсырьё"},
}
SCHEDULE_TEMPLATES = {
    "en": ["When can I put out {waste}?", "What days is {waste} collected?"],
    "ko": ["{waste} 언제 내놓아요?", "{waste} 배출 요일이 언제예요?"],
    "zh": ["{waste}什么时候可以扔？", "{waste}哪天收？"],
    "vi": ["Khi nào tôi có thể đổ {waste}?", "{waste} được thu gom vào ngày nào?"],
    "uz": ["{waste} qachon chiqariladi?", "{waste} qaysi kunlari olib ketiladi?"],
    "ru": ["Когда можно выносить {waste}?", "В какие дни вывозят {waste}?"],
}
_AREA = re.compile(r"^[가-힣0-9]{1,8}(동|읍|면|리|가)$")


def _chunks_by_legacy() -> dict[str, dict]:
    return {c["metadata"]["legacy_id"]: c for c in read_jsonl(paths.ITEM_CHUNKS)}


def sample_items(chunks: dict[str, dict]) -> list[str]:
    """2 items per bin from the 2018 dictionary (one bin each, not used in development),
    then one more from each of the two largest bins: 20 legacy IDs."""
    rng = random.Random(SEED)
    pool = defaultdict(list)
    for legacy, chunk in sorted(chunks.items()):
        meta = chunk["metadata"]
        bins = evidence_bins(meta)
        if (meta["doc_type"] != "item" or len(bins) != 1 or bins & {"재질별분리", "전문시설"}
                or any(word in meta["item"] for word in USED_ITEM_WORDS)):
            continue
        pool[next(iter(bins))].append(legacy)
    picked = []
    for bin_key in sorted(pool):
        items = sorted(pool[bin_key])
        rng.shuffle(items)
        picked += items[:2]
    for bin_key in sorted(pool, key=lambda b: -len(pool[b]))[:2]:
        items = sorted(pool[bin_key])
        random.Random(f"fill-{bin_key}").shuffle(items)
        picked.append(next(i for i in items if i not in picked))
    return picked[:N_ITEMS]


def item_cases(chunks: dict[str, dict], langs: list[str], rng: random.Random) -> list[dict]:
    names = json.loads(ITEM_NAMES.read_text(encoding="utf-8"))
    out = []
    for n, (legacy, lang) in enumerate(zip(sample_items(chunks), langs, strict=True), 1):
        meta = chunks[legacy]["metadata"]
        extra = names["extra"].get(legacy, {})
        bins = sorted(evidence_bins(meta) | set(extra.get("also_bins", [])))
        name = names["names"][legacy][lang]
        question = rng.choice(ITEM_TEMPLATES[lang]).format(item=name)
        out.append({"case_id": f"item{n:02d}", "slice": "item_direct", "lang": lang,
                    "question": question[0].upper() + question[1:], "location": None,
                    "expected_behavior": "answer", "expected_bin": bins,
                    "gold_legacy_ids": [legacy, *extra.get("also_gold", [])],
                    "reference_facts": [f"{meta['item']}: {chunks[legacy]['text'].splitlines()[2]}"],
                    "notes": extra.get("note", ""), "seen_in_development": False,
                    "source": "template"})
    return out


def schedule_cases(langs: list[str], rng: random.Random) -> list[dict]:
    """One question per district, sampled uniformly over districts with data. The place is
    a neighbourhood that only one row lists, so the gold row is not a matter of opinion."""
    table = default_table()
    districts = sorted({(r.province, r.district) for r in table.rows
                        if r.district not in USED_DISTRICTS})
    rng.shuffle(districts)
    out = []
    for province, district in districts:
        if len(out) == N_SCHEDULE:
            break
        rows = [r for r in table.rows if (r.province, r.district) == (province, district)]
        rng.shuffle(rows)
        for row in rows:
            areas = [a for a in row.area_names if _AREA.match(a)
                     and [r.row_id for r in schedule_rows(district, province, a)] == [row.row_id]]
            types = [t for t in ("general", "food", "recycling") if row.rules[t].days]
            if not areas or not types:
                continue
            lang, dong, waste = langs[len(out)], rng.choice(sorted(areas)), rng.choice(types)
            question = rng.choice(SCHEDULE_TEMPLATES[lang]).format(waste=WASTE_WORDS[lang][waste])
            rule = row.rules[waste]
            out.append({"case_id": f"sched{len(out) + 1:02d}", "slice": "schedule",
                        "lang": lang, "question": question[0].upper() + question[1:],
                        "location": {"province": province, "district": district, "dong": dong},
                        "waste_type": waste, "expected_behavior": "answer", "expected_bin": [],
                        "gold_legacy_ids": [],
                        "expected_schedule": {"row_ids": [row.row_id]},
                        "reference_facts": [f"{waste} in {province} {district} {dong}: "
                                            f"{rule.days_en()} {rule.start or ''}-{rule.end or ''}"],
                        "notes": "", "seen_in_development": False, "source": "template"})
            break
    return out


def finish(case: dict, chunks: dict[str, dict]) -> dict:
    """Source record -> case schema (§7.1): legacy IDs to UUIDs, schedule gold by table scan."""
    case = dict(case)
    legacy = case.pop("gold_legacy_ids")
    unknown = [i for i in legacy if i not in chunks]
    if unknown:
        raise ValueError(f"{case['case_id']}: unknown chunks {unknown}")
    case["expected_chunk_ids"] = [chunks[i]["id"] for i in legacy]
    case["gold_legacy_ids"] = legacy
    place = case.pop("schedule_place", None)
    if place:
        rows = schedule_rows(place["district"], place.get("province"), place.get("dong"))
        if not rows:
            raise ValueError(f"{case['case_id']}: no rows for {place}")
        case["expected_schedule"] = {"row_ids": [r.row_id for r in rows], "place": place}
    case.setdefault("expected_schedule", None)
    case.setdefault("waste_type", None)
    case.setdefault("source", "handwritten")
    case["version"] = VERSION
    return case


def split(cases: list[dict], rng: random.Random) -> None:
    """Sets case['split']: per slice, 30% of the unseen cases (by count of the whole slice)
    to test, the rest to dev."""
    by_slice = defaultdict(list)
    for case in cases:
        by_slice[case["slice"]].append(case)
    for slice_name in sorted(by_slice):
        group = by_slice[slice_name]
        unseen = sorted((c for c in group if not c["seen_in_development"]),
                        key=lambda c: c["case_id"])
        rng.shuffle(unseen)
        test_ids = {c["case_id"] for c in unseen[:round(TEST_SHARE * len(group))]}
        for case in group:
            case["split"] = "test" if case["case_id"] in test_ids else "dev"


def build() -> list[dict]:
    """Each random step has its own stream, so changing one step never moves another."""
    chunks = _chunks_by_legacy()
    langs = list(TEMPLATE_LANGS)
    random.Random(f"{SEED}-langs").shuffle(langs)
    cases = read_jsonl(HANDWRITTEN)
    cases += item_cases(chunks, langs[:N_ITEMS], random.Random(f"{SEED}-item-templates"))
    cases += schedule_cases(langs[N_ITEMS:], random.Random(f"{SEED}-schedule"))
    cases = [finish(c, chunks) for c in cases]
    split(cases, random.Random(f"{SEED}-split"))
    ids = [c["case_id"] for c in cases]
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate case_id")
    for case in cases:
        validate_case(case)
    return cases


def _dump(cases: list[dict]) -> str:
    return "".join(json.dumps(c, ensure_ascii=False) + "\n" for c in cases)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--check", action="store_true",
                        help="fail if the files on disk differ from a fresh build")
    args = parser.parse_args()
    cases = build()
    dev = [c for c in cases if c["split"] == "dev"]
    test = [c for c in cases if c["split"] == "test"]
    if args.check:
        same = (paths.DEV_CASES.read_text(encoding="utf-8") == _dump(dev)
                and TEST_CASES.read_text(encoding="utf-8") == _dump(test))
        print("cases are up to date" if same else "cases differ from a fresh build")
        sys.exit(0 if same else 1)
    if MANIFEST.exists() and json.loads(MANIFEST.read_text(encoding="utf-8")).get("frozen"):
        raise SystemExit(f"{paths.relative(MANIFEST)} is frozen; the split is not rebuilt "
                         "after tuning has started. Make a new version instead.")
    CASES_DIR.mkdir(parents=True, exist_ok=True)
    paths.DEV_CASES.write_text(_dump(dev), encoding="utf-8")
    TEST_CASES.write_text(_dump(test), encoding="utf-8")

    def counts(key):
        return {s: dict(Counter(c[key] for c in cases if c["split"] == s)) for s in ("dev", "test")}

    MANIFEST.write_text(json.dumps({
        "version": VERSION, "seed": SEED, "test_share": TEST_SHARE,
        "created": datetime.now().isoformat(timespec="seconds"), "git_commit": git_commit(),
        "frozen": True,
        "frozen_note": "Split made before any tuning. Do not rebuild; a new set is a new version.",
        "n": {"all": len(cases), "dev": len(dev), "test": len(test)},
        "by_slice": counts("slice"), "by_lang": counts("lang"),
        "seen_in_development": sum(c["seen_in_development"] for c in cases),
        "sha256": {"dev": sha256_file(paths.DEV_CASES), "test": sha256_file(TEST_CASES),
                   "handwritten": sha256_file(HANDWRITTEN), "item_names": sha256_file(ITEM_NAMES),
                   "item_chunks": sha256_file(paths.ITEM_CHUNKS),
                   "schedule": sha256_file(paths.SCHEDULE_CSV)},
        "missing": {"real_users": "No real questions from international students were collected "
                                  "(PLAN.md §7.2). The slice is reported as missing."},
        "authorship": "All cases were written by the system developer with AI assistance, not "
                      "by an independent person; translations were not checked by native "
                      "speakers. See the report's limitations.",
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"{len(cases)} cases: dev {len(dev)}, test {len(test)} -> {paths.relative(CASES_DIR)}/")


if __name__ == "__main__":
    main()
