"""
Build RAG chunks from the Ministry of Environment item-sorting guides.

These chunks answer "which bin does this item go in?". The district table answers "when and
where do I put it out?".

Inputs (data/raw/item_guides/):
  moe_recycling_guideline_2018.pdf
      환경부 「재활용품 분리배출 가이드라인」 (2018, 36 pages)
  moe_separation_directive_annex1_2026.pdf
      「분리수거 등에 관한 지침」 [별표 1], 기후에너지환경부훈령 제18호 (2026-01-01)
      The current official rules. Prefer it when it disagrees with the 2018 guide.

Output: data/interim/parsed_item_chunks.jsonl
  Records of {"id", "text", "metadata"}, with parse-order IDs that build_items.py replaces.
  Metadata values are flat strings/ints so they can be used as vector-store filters.

  metadata.doc_type:
    item   one per item in the 2018 item dictionary (부록 '분리배출 품목 사전')
    faq    one per Q/A pair in the 2018 FAQ section
    guide  one per page of the 2018 guide body (food waste, hazardous waste, fines, ...)
    rule   one per row of the 2026 annex tables
    note   the 비고 (notes) under each 2026 annex section

Usage (only when the PDFs or this parser change):
  python -m preprocess.parse_item_guides
"""

import collections
import json
import re

import pdfplumber

from rag import paths

GUIDE_2018 = paths.GUIDE_2018_PDF
ANNEX_2026 = paths.ANNEX_2026_PDF
OUT_PATH = paths.PARSED_ITEM_CHUNKS

SOURCE_2018 = "환경부 재활용품 분리배출 가이드라인 (2018)"
SOURCE_2026 = "분리수거 등에 관한 지침 [별표 1] (기후에너지환경부훈령 제18호, 2026-01-01)"

# 2018 guide layout. 0-based PDF page indexes; the printed page number is index + 1.
BODY_PAGES = range(2, 27)   # sections 01-09 + the dictionary's how-to page (cover, contents skipped)
FAQ_PAGES = range(20, 25)   # 08. 분리배출 앱 FAQ
DICT_PAGES = range(27, 34)  # 부록: 분리배출 품목 사전

# Each dictionary page holds up to two tables side by side.
# x-ranges of their (item, category, method) columns, measured from the PDF.
DICT_TABLES = [
    ((64, 129), (129, 180), (180, 285)),
    ((310, 375), (375, 426), (426, 531)),
]

# Category marks (구분마크) used in the item dictionary, with an English label.
# The Korean meanings are on the dictionary's how-to page (printed p.27), which
# is also saved as its own "guide" chunk.
CATEGORY_EN = {
    "종이": "paper",
    "종이팩": "paper cartons",
    "금속캔": "metal cans",
    "고철": "scrap metal",
    "유리병": "glass bottles",
    "플라스틱": "plastics",
    "비닐": "plastic film/bags",
    "발포합성": "styrofoam",
    "의류": "clothing & textiles",
    "가전제품": "electronics & appliances",
    "대형": "large/bulky waste",
    "음식물": "food waste",
    "유해": "hazardous waste",
    "불연성종량제": "non-combustible waste",
    "종량제봉투": "general waste (pay-as-you-throw bag)",
    "전용함": "dedicated collection box",
    "전문시설": "retailer or specialised facility",
    "주의": "caution: handle safely",
    "재질별분리": "separate by material",
}

SECTION_LETTERS = set("가나다라마바사아자차카타파하")
HEADER_WORDS = {"품목", "구분", "배출방법"}
FOOTER_RE = re.compile(r"^(\d{1,2}\s*)?재활용품 분리배출(\s*\d{1,2})?$|^\d{1,2}$")
Q_RE = re.compile(r"^Q\s*[:：]\s*")
A_RE = re.compile(r"^A\s*[:：]\s*")
BULLET_RE = re.compile(r"^([-※·*]|\d+\.)")


def make_chunk(chunk_id, text, **metadata):
    return {"id": chunk_id, "text": text, "metadata": metadata}


def page_lines(page):
    """Non-empty text lines of a page, without the running footer."""
    text = page.dedupe_chars().extract_text() or ""
    lines = [ln.strip() for ln in text.splitlines()]
    return [ln for ln in lines if ln and not FOOTER_RE.match(ln)]


def region(page, bbox):
    """Characters whose centre lies inside bbox (text may overflow cell borders)."""
    x0, top, x1, bottom = bbox
    return page.filter(lambda o: o.get("object_type") == "char"
                       and x0 <= (o["x0"] + o["x1"]) / 2 <= x1
                       and top <= (o["top"] + o["bottom"]) / 2 <= bottom)


def join_wrapped(lines):
    """Re-join wrapped lines: bullets and numbered notes start a new line,
    everything else continues the previous line after a space.

    Some lines in the 2026 annex are cut mid-word (e.g. '판 매업자'), but the
    PDF does not say which, and joining every full line without a space
    breaks many more words than it fixes.
    """
    out = ""
    for t in (ln.strip() for ln in lines):
        if not t:
            continue
        if not out:
            out = t
        elif BULLET_RE.match(t):
            out += "\n" + t
        else:
            out += " " + t
    return out


# ---------------------------------------------------------------- 2018: item dictionary

def h_rules(page, x0):
    """y positions of the horizontal table rules that start at x0."""
    ys = sorted(ln["top"] for ln in page.lines
                if abs(ln["top"] - ln["bottom"]) < 1 and abs(ln["x0"] - x0) < 2)
    merged = []
    for y in ys:
        if not merged or y - merged[-1] > 2:
            merged.append(y)
    return merged


def lines_in(page, x_range, top, bottom):
    """Text lines inside one column between two rules, minus table headers."""
    cell = region(page, (x_range[0], top, x_range[1], bottom))
    lines = [ln.strip() for ln in (cell.extract_text() or "").splitlines()]
    return [ln for ln in lines
            if ln and ln.replace(" ", "") not in HEADER_WORDS and ln not in SECTION_LETTERS]


def to_categories(lines):
    """Category-mark lines -> category keys. '불연성' + '종량제' is one two-line mark."""
    out = []
    for ln in lines:
        key = ln.replace(" ", "")
        if out and {out[-1], key} == {"불연성", "종량제"}:
            out[-1] = "불연성종량제"
        else:
            out.append(key)
    return out


def parse_item_dictionary(pdf):
    items = []
    for pi in DICT_PAGES:
        page = pdf.pages[pi].dedupe_chars()
        for item_x, cat_x, method_x in DICT_TABLES:
            edges = h_rules(page, item_x[0])
            for top, bottom in zip(edges, edges[1:]):
                name = " ".join(lines_in(page, item_x, top, bottom))
                if not name:
                    continue  # header or section-letter band
                # Some items have one sub-row per category, separated by rules
                # that only span the category and method columns.
                inner = [y for y in h_rules(page, method_x[0]) if top + 2 < y < bottom - 2]
                sub_edges = [top] + inner + [bottom]
                rules = []
                for s_top, s_bottom in zip(sub_edges, sub_edges[1:]):
                    cats = to_categories(lines_in(page, cat_x, s_top, s_bottom))
                    method = " ".join(lines_in(page, method_x, s_top, s_bottom))
                    if not cats and rules:
                        rules[-1]["method"] += " " + method
                    elif cats or method:
                        rules.append({"categories": cats, "method": method})
                items.append({"item": name, "rules": rules, "page": pi + 1})
    return items


def item_chunks(items):
    chunks = []
    for n, it in enumerate(items, 1):
        cats = list(dict.fromkeys(c for r in it["rules"] for c in r["categories"]))
        labels = [f"{c} ({CATEGORY_EN[c]})" if c in CATEGORY_EN else c for c in cats]
        lines = [f"[분리배출 품목] {it['item']}", "구분: " + ", ".join(labels)]
        if len(it["rules"]) == 1:
            lines.append("배출방법: " + it["rules"][0]["method"])
        else:
            lines.append("배출방법:")
            for r in it["rules"]:
                lines.append(f"- {', '.join(r['categories']) or '공통'}: {r['method']}")
        lines.append(f"출처: {SOURCE_2018} p.{it['page']}")
        chunks.append(make_chunk(
            f"item2018_{n:04d}", "\n".join(lines),
            doc_type="item", item=it["item"], categories=", ".join(cats),
            source=SOURCE_2018, source_year=2018, page=it["page"],
        ))
    return chunks


# ---------------------------------------------------------------- 2018: FAQ and body pages

def parse_faq(pdf):
    qas, topic = [], ""
    for pi in FAQ_PAGES:
        lines = page_lines(pdf.pages[pi])
        for i, ln in enumerate(lines):
            nxt = lines[i + 1] if i + 1 < len(lines) else ""
            if ln.startswith("08."):
                continue
            if Q_RE.match(ln):
                qas.append({"topic": topic, "q": Q_RE.sub("", ln), "a": "", "page": pi + 1})
            elif A_RE.match(ln) and qas:
                qas[-1]["a"] = A_RE.sub("", ln)
            elif Q_RE.match(nxt) and len(ln) <= 12 and not ln.endswith("."):
                topic = ln.replace(" ", "")  # a short line right before a question is a topic heading
            elif qas:
                key = "a" if qas[-1]["a"] else "q"
                qas[-1][key] += "\n" + ln
    return qas


def faq_chunks(qas):
    return [
        make_chunk(
            f"faq2018_{n:03d}",
            f"[분리배출 FAQ - {qa['topic']}]\nQ: {qa['q']}\nA: {qa['a']}\n출처: {SOURCE_2018} p.{qa['page']}",
            doc_type="faq", topic=qa["topic"], source=SOURCE_2018, source_year=2018, page=qa["page"],
        )
        for n, qa in enumerate(qas, 1)
    ]


def guide_chunks(pdf):
    chunks, section = [], ""
    for pi in BODY_PAGES:
        if pi in FAQ_PAGES:
            continue
        lines = page_lines(pdf.pages[pi])
        if not lines:
            continue
        if re.match(r"^0\d\.", lines[0]):
            section = lines[0].rstrip(" /")
        if pi == 26:
            section = "부록. 분리배출 품목 사전 이용법"
        text = f"[{section}]\n" + "\n".join(lines) + f"\n출처: {SOURCE_2018} p.{pi + 1}"
        chunks.append(make_chunk(
            f"guide2018_p{pi + 1:02d}", text,
            doc_type="guide", section=section, source=SOURCE_2018, source_year=2018, page=pi + 1,
        ))
    return chunks


# ---------------------------------------------------------------- 2026: official annex

def cell_text(page, bbox):
    if bbox is None:
        return ""
    return join_wrapped(ln["text"] for ln in region(page, bbox).extract_text_lines(strip=True))


def inside(obj, bbox):
    return (bbox[0] - 1 <= obj["x0"] and obj["x1"] <= bbox[2] + 1
            and bbox[1] - 1 <= obj["top"] and obj["bottom"] <= bbox[3] + 1)


def parse_annex(pdf):
    rules, notes = [], collections.defaultdict(list)
    section, header = "", None
    for pi, page in enumerate(pdf.pages):
        tables = page.find_tables()
        first_top = min((t.bbox[1] for t in tables), default=page.height)
        outside = page.filter(lambda o: "x0" in o and not any(inside(o, t.bbox) for t in tables))
        out_lines = outside.extract_text_lines(strip=True)

        # Section titles sit above a table; 비고 notes sit below it (or fill a page alone).
        for ln in out_lines:
            if tables and ln["bottom"] <= first_top and re.match(r"^\d\.\s", ln["text"]):
                section = ln["text"]
        note_lines = [ln["text"] for ln in out_lines if not tables or ln["top"] >= first_top]
        if note_lines:
            notes[section].append(join_wrapped(note_lines))

        for table in tables:
            for row in table.rows:
                cells = [cell_text(page, c) for c in row.cells]
                if cells[-1].replace(" ", "").endswith("배출요령"):
                    header = [c.replace(" ", "") for c in cells]
                    continue
                r = dict(zip(header, cells))
                group, item, sub = r.get("구분", ""), r.get("품목", ""), r.get("세부품목", "")
                method = r.get("배출요령") or r.get("통합배출요령") or ""
                if not (group or item or sub) and rules:
                    rules[-1]["method"] += " " + method  # row continued from the previous page
                    continue
                prev = rules[-1] if rules and rules[-1]["section"] == section else None
                rules.append({
                    "section": section,
                    "group": group or (prev["group"] if prev else ""),
                    "item": item or (prev["item"] if prev else ""),
                    "sub_item": sub,
                    # an empty method means the cell is merged with the row above
                    "method": method or (prev["method"] if prev else ""),
                    "page": pi + 1,
                })
    return rules, notes


def clean_item(name):
    return re.sub(r"^[가-하]\.\s*", "", name).strip()


def clean_sub_item(sub):
    """'· 형광등\\n· LED 조명' -> '형광등, LED 조명'. Only a leading '·' is a bullet;
    the one inside '전기·전자제품' is kept."""
    parts = [ln.strip().lstrip("·").strip() for ln in sub.split("\n")]
    return ", ".join(p for p in parts if p)


def annex_chunks(rules, notes):
    chunks = []
    for n, r in enumerate(rules, 1):
        item, sub = clean_item(r["item"]), clean_sub_item(r["sub_item"])
        lines = [f"[분리배출 기준 2026] {item} > {sub}" if sub else f"[분리배출 기준 2026] {item}"]
        if r["group"]:
            lines.append(f"구분: {r['group']}")
        lines.append(f"배출요령:\n{r['method']}")
        lines.append(f"출처: {SOURCE_2026} - {r['section']}")
        chunks.append(make_chunk(
            f"rule2026_{n:03d}", "\n".join(lines),
            doc_type="rule", item=item, sub_item=sub, group=r["group"], section=r["section"],
            source=SOURCE_2026, source_year=2026, page=r["page"],
        ))
    for n, (section, parts) in enumerate(notes.items(), 1):
        text = f"[분리배출 기준 2026 비고] {section}\n" + "\n".join(parts) + f"\n출처: {SOURCE_2026}"
        chunks.append(make_chunk(
            f"note2026_{n:02d}", text,
            doc_type="note", section=section, source=SOURCE_2026, source_year=2026,
        ))
    return chunks


# ---------------------------------------------------------------- main

def report(items, qas, rules):
    unknown = sorted({c for it in items for r in it["rules"] for c in r["categories"]} - CATEGORY_EN.keys())
    if unknown:
        print("WARNING unknown category marks:", unknown)
    for it in items:
        if not it["rules"] or any(not r["method"] or not r["categories"] for r in it["rules"]):
            print(f"WARNING incomplete item p.{it['page']}: {it['item']} -> {it['rules']}")
    for qa in qas:
        if not qa["a"] or not qa["topic"]:
            print(f"WARNING incomplete FAQ p.{qa['page']}: {qa}")
    for r in rules:
        if not r["method"]:
            print(f"WARNING rule without method p.{r['page']}: {r['item']} / {r['sub_item']}")


def main():
    with pdfplumber.open(GUIDE_2018) as pdf:
        items = parse_item_dictionary(pdf)
        qas = parse_faq(pdf)
        chunks = item_chunks(items) + faq_chunks(qas) + guide_chunks(pdf)
    with pdfplumber.open(ANNEX_2026) as pdf:
        rules, notes = parse_annex(pdf)
        chunks += annex_chunks(rules, notes)

    report(items, qas, rules)
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        for c in chunks:
            f.write(json.dumps(c, ensure_ascii=False) + "\n")

    counts = collections.Counter(c["metadata"]["doc_type"] for c in chunks)
    print(f"Saved {len(chunks)} chunks to {OUT_PATH}: {dict(counts)}")


if __name__ == "__main__":
    main()
