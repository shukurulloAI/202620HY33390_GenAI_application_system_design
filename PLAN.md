# Project Plan: Waste-Sorting Assistant for Foreigners in Korea

Course: 202620HY33390 Design of Generative AI Application Systems (Hanyang University)
Team: Shukurullo, Vitou, Anar, Naura
Plan version: v6, 2026-11-07 (v2: team roles assigned; v3: Phase 1 baseline done; v4: Phase 2 components built; v5: preprocessing done, `preprocess/`; v6: repository restructured, road to website-ready in §10.4)

This file is the project's single plan. Each design choice is linked to the lesson that taught it, so the final report can show which course concepts we used and how we measured them.

## Team roles

| Area | Owner | Plan sections |
|---|---|---|
| Data collection | **Vitou** | §3 |
| Data preprocessing (cleaning, chunking, manifest) | **Vitou** | §3, §4.1 |
| Model implementation (RAG pipeline code) | **Shukurullo** | §4.1–§4.11, §6 (making experiment variants runnable) |
| Evaluation | **Anar** | §6 (running experiments), §7 |
| Reports | **Anar** | §11, §12 |
| Website (optional) | **Naura** | §4.12 |
| Presentation | **All** | §10, Phase 4 |

Detailed task lists per person are in §10.

> **Note on "training the model":** this is a RAG system, so we **do not train or fine-tune model weights**. We use pre-trained models (embedding model, reranker, LLM) and "training" means implementing and tuning the pipeline: indexing, retrieval, prompts and the gate threshold. Tuning uses the dev set only (§7).

---

## 1. Vision

**A multilingual assistant that tells a foreigner in South Korea which bin an item goes in and when and where to put it out in their neighbourhood. It cites official sources, shows the data date, and refers the user to the district office when it isn't sure.**

Example conversation:

> **User:** I live in Seongdong-gu, Haengdang-dong. Where do I throw a PET water bottle and when?
>
> **Assistant:** Clear PET bottles go in the **transparent PET bottle collection**, kept separate from other plastics. Empty it, remove the label, crush it and close the cap [1]. In Seongdong-gu, recycling is collected on **Sun–Thu, 18:00–24:00**, in front of your house [2].
> *Sources: [1] 2026 national separation directive, Annex 1, section 2 · [2] Seongdong-gu district data, as of 2024-xx-xx · Questions: 성동구청 청소행정과 02-xxxx-xxxx*

(The days, times and phone number above are placeholders. Real values come from the data.)

### Why it matters
- Korea's sorting rules are detailed (pay-as-you-throw bags, separate food waste, clear PET bottles) and differ by district.
- Official guides are in Korean, and schedule data is spread over 200+ district records.
- Wrong sorting can lead to bags being left uncollected or to fines, and newcomers rarely know who to ask.

---

## 2. Users, scope, non-goals, consequences (Lesson 1: responsible design)

| | |
|---|---|
| **Users** | Foreign residents and students in Korea (e.g., Hanyang international s

tudents), with limited Korean |
| **In scope** | Household waste: (a) which bin and how to prepare an item, from the national rules; (b) collection days, times and places by district/neighbourhood, from the district dataset; questions in English and Korean, plus 1–2 more languages (e.g., Chinese, Uzbek, Vietnamese) |
| **Non-goals** | Business or commercial waste; booking or paying for large-item pickup (we only point to the district); legal advice about fines; real-time truck tracking; personal data of any kind |
| **Who bears failure** | The user. A wrong bin can mean an uncollected bag or a fine; a wrong day means trash left out on the street |
| **Consequence level** | Moderate and mostly reversible, so every answer cites its source, shows the data date, abstains when evidence is missing, and gives the district office phone |
| **Data ethics** | Only public government data (data.go.kr, Ministry of Environment). No user accounts. Traces store questions without personal identifiers |

---

## 3. Data sources and current status

| Source | File | What it answers | Status |
|---|---|---|---|
| MoE Recycling Separation Guideline (2018), 36 pages | `data/raw/item_guides/moe_recycling_guideline_2018.pdf` | Which bin for ~290 items, FAQ, general guidance | ✅ Chunked |
| Separation directive, Annex 1 (기후에너지환경부훈령 제18호, effective 2026-01-01), 8 pages | `data/raw/item_guides/moe_separation_directive_annex1_2026.pdf` | Current official rules by material group (incl. clear PET bottles) | ✅ Chunked |
| National household-waste schedule data (data.go.kr), CP949, 10,187 rows, 222 districts | `data/raw/korean_waste_policies.csv` | When and where: days, times, place, method per waste type, office phone, data date | ⚠️ Chunked by Vitou, needs fixes (below) |
| Recycling item API (data.go.kr 15156866), ~770 items | not downloaded yet | More items with sorting methods | ⏳ API key needed; take a snapshot file, never call it live |

### 3.1 Item chunks (`data/interim/parsed_item_chunks.jsonl`, 394 chunks)

| doc_type | Count | ID pattern | Content |
|---|---|---|---|
| `item` | 293 | `item2018_NNNN` | One dictionary item: categories (KO + EN) + method + page |
| `faq` | 36 | `faq2018_NNN` | One Q/A pair with topic |
| `guide` | 20 | `guide2018_pNN` | One body page of the 2018 guide with section title |
| `rule` | 42 | `rule2026_NNN` | One row of the 2026 annex table (group > item > sub-item, method) |
| `note` | 3 | `note2026_NN` | Notes under the 2026 tables |

Known issues:
- **IDs depend on parse order.** This is the Lesson 3 anti-pattern. Replace them with UUIDv5 (Phase 0).
- **The 2018 and 2026 rules disagree on some items.** For example, the 2018 guide puts PET bottles under plastics, while the 2026 annex makes clear PET bottles a separate stream. This needs a conflict policy (§4.6).
- **Some 2026 text has broken spacing** that comes from the PDF itself ("판 매업자", "내용물을비우고"). It may hurt BM25; keep it in mind for E3.

### 3.2 District schedule data (`notebooks/schedule_eda/output/chunks.jsonl`, 10,187 chunks)

CSV columns used: 시도명, 시군구명, 관리구역명, 관리구역대상지역명, 배출장소(유형), the 생활쓰레기/음식물/재활용품/일시적다량폐기물 배출방법·요일·시각 columns, 미수거일, 관리부서명·전화번호, 데이터기준일자.

Problems found in profiling. Each needs a fix or a stated limitation:

| # | Problem | Impact | Fix (owner: Vitou) |
|---|---|---|---|
| 1 | `split_dongs` keeps only names ending in 동 | Neighbourhood names ending in 읍/면/리/가/로 are lost; 92% of chunks have an empty `dongs` | Keep all area names; normalise rather than filter |
| 2 | Chunk metadata has no province (시도명) | 7 district names exist in several provinces (e.g., 중구, 동구, 서구, 남구, 북구, 강서구, 고성군) | Add `province`; filter on (province, district) |
| 3 | 106 neighbourhood names map to more than one district | A query like "I live in X-dong" is ambiguous | Return all matches and ask a clarifying question |
| 4 | ~21% of rows have data dates from 2019–2020 | Schedules may be outdated | Keep `data_date`; show a warning when older than 1 year |
| 5 | Seoul has no rows for Gangdong-gu or Dobong-gu | No schedule data for those districts | Abstain explicitly ("no data for your district") |
| 6 | Rows are near-duplicates (same template text, only the district differs) | Vector search cannot tell districts apart | Use structured lookup for schedules, not embeddings (§4.5, E4) |
| 7 | Only ~1.6% of rows mention specific items | The CSV cannot answer "which bin" | Item questions use the national guides instead |

---

## 4. System architecture

```
OFFLINE (Lesson 3)
 2018 guide PDF ─┐
 2026 annex PDF ─┼─► manifest.json (doc_id, uri, sha256, parser_id, source_year, effective_date)
 [770-item API snapshot] ─┘      │
                                 ▼
                     chunks.jsonl (UUIDv5 chunk_id, text, page/section span, metadata)
                                 │
                                 ▼
                     embed (pinned model + revision, normalized, cosine)
                                 │
                                 ▼
                     Qdrant local collection  ──►  verification report (PASS / FAIL)

 district CSV ──► cleaned schedule table (schedule.parquet / sqlite) + dong_lookup.json

ONLINE
 user question (any language)
   │
   ▼
 [1] Router / rewriter (LLM, JSON)  ─ validate invariants, fallback        L01, L05
       {intent, item, item_ko, province, district, dong, waste_type, lang, ko_query}
   │
   ├── intent ∈ {item, both} ──► [2a] item retrieval                        L04, L05
   │                               dense + BM25 → fuse (RRF) → cross-encoder rerank
   │
   └── intent ∈ {schedule, both} ─► [2b] schedule lookup TOOL               L01, L05
                                   typed filter (province, district, dong) on table
   │
   ▼
 [3] Evidence gate + conflict policy                                        L05, L04, L07
       enough evidence?  2018 vs 2026 disagree → use 2026 and mention it
       ambiguous location → ask a clarifying question
       no evidence → abstain + handoff
   │
   ▼
 [4] Context builder: label evidence [1]..[n], token budget with output reserve   L02, L04
   │
   ▼
 [5] Generator (T = 0) → JSON answer contract                               L01, L02, L04
   │
   ▼
 [6] Output validation + citation check                                     L04, L06, L07
       JSON schema valid? bin ∈ allowed categories? every [n] resolves?
   │
   ▼
 UI (Streamlit): answer in the user's language, source cards, data date, glossary,
 office phone, feedback buttons. Every request writes a JSON trace.         L03, L05
```

### 4.1 Ingestion and index (Lesson 3)

**Manifest record** (one per source file):
```json
{"doc_id": "uuid5(source_uri)", "source_uri": "data://item_guides/moe_recycling_guideline_2018.pdf",
 "media_type": "application/pdf", "sha256": "...", "parser_id": "pdfplumber-item-dict-v1",
 "source_year": 2018, "effective_date": "2018-xx-xx", "publisher": "환경부", "pages": 36}
```

**Chunk record:**
```json
{"chunk_id": "uuid5(NS, doc_id|sha256|chunker_id|span|text_digest)",
 "doc_id": "...", "doc_type": "item|faq|guide|rule|note",
 "text": "...", "span": "p.28 / annex section 2 row 5",
 "item": "가격표", "categories": "종이", "source": "...", "source_year": 2018,
 "chunker_id": "item-dict-v1", "lang": "ko"}
```

Rules:
- A chunk ID is derived from the source state + chunking policy + location + text digest. It never depends on loop order, so test-set gold IDs stay valid.
- Chunking is **structure-aware**: one dictionary item, one FAQ pair, one annex row or one guide page per chunk. A token-window split is used only if a unit exceeds the embedding limit. Experiment E6 justifies this choice.
- Normalisation is minimal and versioned (Unicode NFC, whitespace inside tables). Anything lost is recorded as a parser warning.
- **Verification report** before an index is used: number of points = number of chunks; all vectors have the declared dimension; all IDs unique; repeat run gives the same IDs; every payload resolves to a manifest source; reopen check passes.
- **Incremental rebuild**:
  - If a source hash changes (e.g., a new CSV from data.go.kr), rebuild only that source's chunks.
  - Delete points from removed sources.
  - A new embedding model goes into a new collection (`waste_items_<model>_<revision>`), never mixed into the old one.

Exact vs approximate search: ~400 item chunks (plus ~770 later) is small, so Qdrant local exact search is fine. The report should say that HNSW would be needed only at a much larger scale (Lesson 3).

### 4.2 Representation contract (Lesson 2, Lesson 3)

| Field | Value (proposed) |
|---|---|
| Embedding model | `BAAI/bge-m3` (multilingual, 1024-d), revision pinned |
| Baseline model for comparison | `BAAI/bge-small-en-v1.5` (course default, English-only, 384-d) |
| Pooling / normalisation | As in the model card; `normalize_embeddings=True` |
| Metric | Cosine |
| Max input | Recorded from the model card; chunks checked against it |
| Query prefix | As in the model card (bge-small-en needs its query instruction; bge-m3 does not) |
| Collection name | `waste_items_bge-m3_<revision[:8]>` |

**Why multilingual:** the corpus is Korean, but users ask in English or other languages. The course default is English-only, which is the "domain mismatch" failure from Lesson 2. E2 measures this directly instead of assuming it.

### 4.3 Router / query rewriter (Lesson 1 prompt contract, Lesson 5 rewriting)

Input: the raw user question (+ previous turn if any). Output (JSON, validated):
```json
{"intent": "item | schedule | both | out_of_scope",
 "item": "chicken bones", "item_ko": "닭뼈",
 "province": null, "district": "성동구", "dong": "행당동",
 "waste_type": "food | general | recycling | bulky | null",
 "lang": "en", "ko_query": "닭뼈 분리배출 방법",
 "negation": false}
```

- **Invariants:** the item, location, waste type, time ("tonight", "Sunday") and negation ("is it NOT recyclable?") must survive the rewrite. A validation step checks that every entity in the original question appears in the JSON.
- **Fallbacks:**
  - Invalid JSON → retry once, then search with the original question.
  - Unknown district → ask the user.
  - `out_of_scope` → polite refusal with scope.
- **Location normalisation:** match the district and neighbourhood against `dong_lookup.json`, accepting English romanisation (Seongdong-gu → 성동구) through an alias table.
- **The original question is always kept** in the trace next to the rewrite.

### 4.4 Item retrieval (Lessons 4, 5)

1. **Dense search:** `ko_query` (and the original question) → bge-m3 → Qdrant top `k_retrieve = 20`.
2. **Lexical search (BM25):** over Korean text. Korean needs morphological tokenisation (e.g., `kiwipiepy`) or character bigrams, because particles (조사) break whitespace tokens. This is an E3 sub-variable.
3. **Fusion:** Reciprocal Rank Fusion (RRF) of the dense and BM25 lists, keeping candidate identities.
4. **Rerank:** multilingual cross-encoder (`BAAI/bge-reranker-v2-m3`) over the fused top 20.
5. **Select:** `k_final = 3–5` chunks, deduplicated by item, keeping both 2018 and 2026 chunks for the same item if present (needed by the conflict policy).
6. **Optional metadata filter:** `doc_type` (e.g., FAQ for "why" questions), `source_year`.
7. **Optional, ablation only:** HyDE (generate a hypothetical rule text and embed it). The draft is never used as evidence (Lesson 5).

### 4.5 Schedule lookup tool (Lesson 1 "use a tool", Lesson 5 filtering)

The schedule question is answered by **deterministic code**, not by the LLM or vector search:
```python
lookup_schedule(province: str | None, district: str, dong: str | None,
                waste_type: str | None) -> list[ScheduleRow]
# ScheduleRow: province, district, zone, area_names, place, method, days, start, end,
#              no_collection_days, office, phone, data_date, row_id (관리번호)
```
- **Typed filter:** exact match on (province, district), then neighbourhood membership.
- **Multiple zones per district** → return all and let the generator say "depends on your zone", or ask for the neighbourhood.
- **Ambiguous names** (duplicate district names, the 106 ambiguous neighbourhoods) → return a `CLARIFY` status with the options.
- **No match** → `NO_DATA` status (e.g., Gangdong-gu). The gate then abstains.
- **Date helper (tool):** "Can I put food waste out tonight?" → compute today's weekday in KST and compare it with the collection days. The LLM never does date arithmetic.
- **Freshness:** if `data_date` is more than 1 year old, add a warning to the answer.

### 4.6 Evidence gate and conflict policy (Lessons 4, 5, 6, 7)

| Situation | Decision |
|---|---|
| Top rerank score ≥ τ (τ chosen on **dev set only**, Lesson 6) and the item matches | Answer |
| Score < τ, or no candidates | Abstain: `INSUFFICIENT_CONTEXT` + what is missing + office phone |
| 2018 and 2026 chunks disagree for the same item | Use 2026 and state that the rule changed in 2026. Show the effective dates (Morgan Stanley case, Lesson 7) |
| Item only in the 2018 guide | Answer, labelled "based on the 2018 national guide; local rules may differ" |
| Schedule tool returns `CLARIFY` | Ask a clarifying question; do not guess |
| Schedule tool returns `NO_DATA` | Answer the item part only and abstain on the schedule part |
| A neighbourhood has more than `MAX_ZONES` rows on different days | Several names to pick from (오빈리: 오빈1리, 오빈2리): ask. One name with many collection points (도덕면): abstain on the schedule part and hand off to the office. Same days in every row: answer |
| `out_of_scope` | Explain the scope |

Threshold selection: a wrong bin answer (false positive) is costlier than an unnecessary abstention (false negative). τ is chosen on dev to minimise false positives while keeping false negatives below a set limit. The objective is declared before looking at test results.

### 4.7 Context builder and token budget (Lessons 2, 4)

```python
@dataclass(frozen=True)
class ContextBudget:
    max_context: int          # from the LLM's declared limit
    reserved_output: int      # e.g., 512
    @property
    def input_budget(self): return self.max_context - self.reserved_output
```
- Order: system instructions → glossary (only the terms that appear) → evidence [1]..[n] → question.
- Token counts are measured with the **deployed model's tokenizer**, not word counts. Korean usually costs more tokens per fact than English; we measure and report this.
- Overflow policy: drop the lowest-ranked evidence chunk first and record that in the trace. Never truncate silently.
- Most relevant evidence goes first or last, not in the middle ("Lost in the Middle", Lesson 4 reference).

### 4.8 Generator contract (Lessons 1, 2, 4)

Prompt sections: **Task**, **Context**, **Constraints**, **Output**.
- Answer only from the numbered evidence. Cite `[n]` after each material claim.
- Answer in the user's language (`lang`); keep Korean terms in parentheses (e.g., "pay-as-you-throw bag (종량제봉투)").
- If the evidence is insufficient, return `INSUFFICIENT_CONTEXT` and name what is missing.
- Few-shot examples: one supported item answer, one schedule answer, one abstention.
- Temperature 0; seed recorded.

Output JSON:
```json
{"status": "ANSWER | INSUFFICIENT_CONTEXT | CLARIFY",
 "bin": "투명페트병", "bin_en": "clear PET bottles",
 "how_to_prepare": ["empty", "remove label", "crush", "close cap"],
 "schedule": {"days": "...", "time": "...", "place": "..."},
 "answer_text": "...",
 "citations": [{"n": 1, "chunk_id": "..."}, {"n": 2, "row_id": "..."}],
 "data_date": "2024-xx-xx", "office_phone": "...", "missing": null}
```

`schedule`, `data_date` and `office_phone` are filled by `pipeline.schedule_fields` from the tool's rows, never by the LLM. The schedule part of `answer_text` is written by code too (`rag/schedule_text.py`): the generator sees item evidence only, and a small LLM call translates the free-text `method` field, which falls back to English and then to the Korean text if it fails. Uzbek, Vietnamese and Russian method text goes to English until a native speaker has checked them (`METHOD_LANGUAGE`). `schedule_text = llm` keeps the old behaviour, and the baseline uses it. With several zones or waste types each value is labelled, `data_date` is the oldest date, and `schedule` also keeps the full detail (`status`, `message`, `options`, `zones`).

### 4.9 Output validation and citation check (Lessons 4, 6, 7)

- JSON schema check; `bin` must come from the **allowed category list**: the 2018 categories (종이, 종이팩, 금속캔, 고철, 유리병, 플라스틱, 비닐, 발포합성, 의류, 가전제품, 대형, 음식물, 유해, 불연성종량제, 종량제봉투, 전용함, 전문시설) plus the 2026 groups (e.g., 투명페트병). This is the Siemens lesson: validate generated output before use.
- Every `[n]` must resolve to a chunk actually in the context.
- **Cheap support check:** the `bin` value must appear in at least one cited chunk's categories or text. If it doesn't, the answer is downgraded to abstain.
- **Invented schedule check:** an answer that states days or clock times with no schedule rows behind it is downgraded to abstain (`schedule_invented`).
- Optional LLM claim check, used in evaluation only, not at runtime.

### 4.10 Human handoff (Lesson 7, Klarna case)

When the assistant abstains, it gives:
- the district office name and phone (from the CSV);
- a short **Korean sentence the user can show or say**, e.g., "안녕하세요. ○○를 어떻게 버려야 하는지 알고 싶습니다. 저는 ○○동에 살고 있습니다.";
- what it already checked, so the user doesn't start from zero.

### 4.11 Traces (Lessons 3, 5, 6)

One JSON line per request in `traces/` (gitignored):
original question, router output, rewrite validation, candidates (ID, dense rank, BM25 rank, rerank score), selected evidence, gate decision and reason, token counts, prompt version, model IDs and revisions, raw LLM output, validation result, final answer, latency per stage, user feedback.

### 4.12 Website / UI (Naura, optional)

The website calls the pipeline through one function and only displays its result:
```python
answer(question: str, lang: str | None = None,
       district: str | None = None, dong: str | None = None) -> dict  # Answer JSON from §4.8 + trace_id
```
Streamlit is the quickest option; a custom web front end (e.g., FastAPI + HTML) is fine if Naura prefers it. If the website is not built, the demo uses the command-line interface.

- Chat box with a language selector, plus an optional district/neighbourhood dropdown (reduces ambiguity).
- Answer card: bin, how to prepare, schedule, and the "data as of" date.
- Expandable source cards showing the cited chunk text and page.
- Glossary hover for 종량제봉투, 음식물 전용봉투, 대형폐기물 스티커, and similar terms.
- 👍/👎 feedback stored in the trace.

---

## 5. Lesson-to-project mapping (for the report)

| Lesson | Concept | Where in the project | Evidence we will show |
|---|---|---|---|
| L01 | Generate vs retrieve vs tool | Rules retrieved; schedule and dates by tool; only the wording generated | Architecture diagram, trace examples |
| L01 | Prompt contract (task/context/constraints/output) | Router and generator prompts (§4.3, §4.8) | Prompt files with version IDs |
| L01 | Zero-shot vs few-shot; controlled prompt experiment | E1 | E1 table |
| L01 | Hallucination = unsupported claim; abstention | `INSUFFICIENT_CONTEXT`, gate, handoff | Abstention slice results |
| L01 | Responsible design: data, users, consequences | §2 | Report section |
| L02 | Tokenization, token counting | Korean vs English token cost; budget from the real tokenizer | Small table: tokens per chunk KO vs EN |
| L02 | Context budget with output reserve, overflow policy | `ContextBudget` (§4.7) | Overflow test case in the trace |
| L02 | Temperature, seeded trials | E7 | Agreement-rate table |
| L02 | Embeddings, cosine, representation contract, domain mismatch | §4.2, E2 | E2 table |
| L03 | Manifest, SHA-256, parser ID | §4.1 | `manifest.json` |
| L03 | Stable UUIDv5 chunk IDs, source spans | §4.1 | Repeat-run ID match = true |
| L03 | Chunk granularity as an experiment (Dense X) | E6 | E6 table |
| L03 | Qdrant local persistence, verification, incremental rebuild | §4.1 | Verification report PASS; rebuild demo with a changed CSV |
| L03 | Exact search vs HNSW | §4.1 note | Report paragraph |
| L04 | Lexical / dense / hybrid retrieval | §4.4, E3 | E3 table |
| L04 | Candidate set R vs evidence set E (`k_retrieve`, `k_final`) | §4.4 | Trace shows both |
| L04 | Citations vs grounding | §4.8, §4.9 | Citation precision/coverage |
| L04 | Freshness, conflicting sources | 2018 vs 2026 policy, `data_date` warnings | E8, conflict slice |
| L04 | LangChain / LlamaIndex roles | Implementation (LangChain for the pipeline) | Code |
| L05 | Query rewriting with invariants, validation, fallback | Router (§4.3) | Rewrite records in traces, a drift example |
| L05 | Typed metadata filter, prefilter vs postfilter, candidate starvation | Schedule tool, `doc_type` filter, E4 | E4 table |
| L05 | Cross-encoder reranking | §4.4, E5 | E5 table |
| L05 | Evidence gate, abstention | §4.6 | Gate confusion matrix |
| L05 | HyDE, Rewrite-Retrieve-Read | Optional ablation | Optional row |
| L05 | Controlled comparison, ablation, latency cost | §6 | Ablation table + latency per stage |
| L06 | Test set: cases, references, slices, dev/test split | §7 | `eval/cases/*.jsonl` |
| L06 | Recall@k, Precision@k, MRR, nDCG@k | §7.3 | Metric tables |
| L06 | Correctness, grounding, citation precision/coverage | §7.3 | Metric tables |
| L06 | Gate confusion matrix, threshold on dev only | §4.6, §7.4 | Threshold sweep plot |
| L06 | Failure heatmap by earliest failed stage, slice regression | §7.5 | Heatmap |
| L06 | Ragas, judge audit, RGB robustness probes | §7.4, §7.6 | Judge vs human agreement |
| L07 | Industry lens (Problem/Application/Pros/Cons/Improvement/Measurement) | §11 | Report section |
| L07 | Source version dates (Morgan Stanley) | Conflict policy, effective dates in answers | Conflict slice |
| L07 | Human handoff with context (Klarna) | §4.10 | Abstention examples |
| L07 | Validate generated output (Siemens) | §4.9 | Validation failure counts |
| L07 | Maintenance: owner, source revision, review date (Moderna) | Manifest + data-date warnings + rebuild | Maintenance section |

Lesson 1 listed five pillars: generate, retrieve, use tools, evaluate, operate safely. Later lessons will probably cover tools/agents and operations. Because the schedule lookup and date helper are already tools, the router can later become a tool-calling agent without a redesign.

---

## 6. Experiments (controlled comparisons, Lesson 5)

Rules for every experiment:
- Change exactly one variable.
- Keep the same dev cases, corpus revision, and other settings.
- Record config, model revisions, metrics, latency, and regressions (cases that got worse).
- Tune on **dev only**; run the final chosen configuration once on **test**.

| ID | Question | Fixed | Variable | Main metrics | Priority |
|---|---|---|---|---|---|
| E1 | Does the prompt contract help? | Retrieval = best config | baseline (question only) / zero-shot contract / few-shot contract (v2) / few-shot without the leaking example (v3) | Bin correctness, abstention accuracy, JSON validity, citation precision | Must |
| E2 | Does the embedding model matter for Korean data + multilingual questions? | Chunks, k | bge-small-en (course) / bge-m3 / bge-small-en after translating the query to Korean | Recall@5, MRR, by language | Must |
| E3 | Lexical vs dense vs hybrid? | Embedding = best of E2 | dense / BM25 (kiwi tokens) / BM25 (char bigrams) / hybrid RRF | Recall@5, MRR, nDCG@5 | Must |
| E4 | How should schedule questions be retrieved? | Same schedule cases | vector search over district chunks / postfilter (top-k then filter) / prefilter + structured lookup | Correct row found, exact day/time match, empty-result rate | Must |
| E5 | Does reranking help, and what gate threshold? | Hybrid retrieval | rerank off / on; τ sweep 0.1–0.9 on dev | MRR, nDCG, gate TP/FP/FN/TN | Must |
| E6 | Which chunk granularity? | Embedding, retrieval | structure-aware (1 item per chunk) / fixed window 500 chars, overlap 80 / whole page | Recall@5, chunk count, answer correctness | Nice |
| E7 | Is the answer stable across sampling? | Everything | T = 0 / 0.7 / 1.0, 5 seeds each, 20 cases | Bin agreement rate, abstention flips | Nice |
| E8 | Does the conflict policy matter? | Everything | no year preference / prefer 2026 | Correctness on the conflict slice | Nice |

Also record **latency and cost per stage** (rewrite, embed, retrieve, rerank, generate) for the baseline and the final system.

Raw results go to `experiments/results/E*/`, and result tables to the report.

---

## 7. Evaluation plan (Lesson 6)

### 7.1 Case schema (`eval/cases/dev.jsonl`, `eval/cases/test.jsonl`)
```json
{"case_id": "c017", "version": "v1", "split": "dev", "slice": "item_tricky",
 "lang": "en", "question": "Where do I throw chicken bones?",
 "location": null,
 "expected_behavior": "answer | abstain | clarify",
 "expected_bin": ["종량제봉투"],
 "expected_chunk_ids": ["<uuid of the matching chunk>"],
 "expected_schedule": null,
 "reference_facts": ["Chicken bones go in the general-waste bag, not food waste."],
 "notes": "Common mistake: putting bones in food waste."}
```
Acceptable alternatives are listed, e.g., two chunks that both support the answer.

### 7.2 Slices and target counts (~100 cases)

| Slice | Count | How to create | Expected behaviour |
|---|---|---|---|
| `item_direct` | 20 | Templates over sampled dictionary items ("How do I throw away {item}?") | Answer: bin + method |
| `item_tricky` | 15 | Hand-written: bones, egg shells, tea bags, batteries, lamps, medicine, pizza box, receipts, styrofoam with tape | Answer |
| `schedule` | 15 | Sampled CSV rows: "I live in {district}. When is {waste_type} collected?" | Answer: days/time/place |
| `combined` | 12 | Item + location in one question | Answer from two sources |
| `conflict` | 8 | Items where 2018 and 2026 differ (clear PET, others found in data) | Answer with the 2026 rule |
| `no_evidence` | 10 | Gangdong-gu schedule, scrapping a car, business waste, fine amounts | Abstain + handoff |
| `false_premise` | 8 | "Since batteries go in general trash, which bag?" | Correct the premise |
| `ambiguous_location` | 6 | Duplicate district names ("중구") or ambiguous neighbourhoods | Clarify |
| `real_users` | 6–10 | Real questions from international students at Hanyang | Depends |

- **Language** is an attribute, not a slice. About 40% of cases in English, 30% Korean, 30% other languages (Chinese/Uzbek/Vietnamese), paraphrased by a human or a model and **checked by a person**.
- **Split:** 70% dev / 30% test, stratified by slice, assigned before any system runs. Test cases are not read during development.
- Gold chunk IDs come from the UUIDv5 chunk IDs, so they survive rebuilds.

### 7.3 Metrics

| Stage | Metric | Unit / denominator | Evaluator |
|---|---|---|---|
| Router | Intent accuracy; item/district extraction accuracy | All cases | Deterministic |
| Retrieval (item) | Recall@k, Precision@k, MRR, nDCG@k (k = 5) | Answerable item cases; chunk units | Deterministic (chunk IDs) |
| Schedule tool | Correct row found; exact day/time match | Schedule + combined cases | Deterministic |
| Gate | TP / FP / FN / TN, accuracy, FP rate | All cases (label: evidence sufficient?) | Deterministic |
| Answer | Bin correctness; schedule correctness | Answerable cases | Deterministic (JSON fields) |
| Answer | Abstention / clarification correctness | `no_evidence` + `ambiguous_location` | Deterministic (`status` field) |
| Answer | Grounding (claims supported / all claims) | Material claims | Ragas faithfulness + human audit |
| Answer | Citation precision, citation coverage | Material claims | Human annotation on a sample; LLM judge on all |
| Answer | Answer relevance, correct output language | All cases | Ragas / simple language detection |
| System | Latency per stage, tokens per request | All cases | Trace |

Undefined cases are declared, e.g., Recall@k for abstain cases = `None`, excluded and counted.

### 7.4 Judges and audits
- **Ragas** (v0.4.x): faithfulness, context relevance and answer relevance, with a pinned judge model and recorded prompt version.
- **Human audit:** Anar and one other member (e.g., Naura) independently label ~20 answers (supported / contradicted / missing per claim). Report agreement between the judge and the humans, and between the two humans. Every disagreement is explained.
- **Gate threshold:** sweep τ on dev, choose by the declared objective (§4.6), freeze it, then run test once.

### 7.5 Failure analysis
- For each failed case, label the **earliest failed stage**: router → retrieval/selection → gate → generation → citation. Report as a heatmap (slice × stage).
- Report results **by slice and by language**. An overall gain that hides a slice regression must be called out (Lesson 6 example).
- Write 3–5 short case studies from traces (one per failure type).

### 7.6 Robustness probes (RGB-style, Lesson 6)

| Probe | Construction | Desired behaviour |
|---|---|---|
| Noise | Add irrelevant chunks to the context | Same correct answer |
| Negative rejection | Remove the answer-bearing chunk | Abstain |
| Information integration | Item + schedule from two sources | Combine both correctly |
| Counterfactual | Insert a false chunk ("batteries go in food waste") with a 2026 rule present | Follow the authoritative/newer source or flag the conflict |

### 7.7 Statistics and honesty
- With ~30 test cases, report counts next to percentages (e.g., "26/30").
- Template-generated cases are not independent, so say so.
- No claim beyond the tested setting (Lesson 5: "no benchmark overclaim").

---

## 8. Technology choices

| Role | Choice | Why / course link |
|---|---|---|
| Language | Python 3.11+ | Course labs |
| PDF parsing | pdfplumber | Already used in `preprocess/parse_item_guides.py` |
| Embeddings | `BAAI/bge-m3` (pinned revision); baseline `BAAI/bge-small-en-v1.5` | Multilingual; course baseline for comparison |
| Vector store | Qdrant local mode (`QdrantClient(path=...)`) | Lessons 3–5 |
| Lexical search | `rank_bm25` + `kiwipiepy` Korean tokenizer | Lessons 4–5 hybrid |
| Reranker | `BAAI/bge-reranker-v2-m3` (CrossEncoder) | Lesson 5 |
| Orchestration | LangChain (explicit steps) or plain Python with the same stage boundaries | Lesson 4 |
| Router + generator LLM | Ollama `qwen2.5:7b` for both (default) behind an `LLMClient` interface; `qwen2.5:3b` = course baseline; `exaone3.5:7.8b` (LG, Korean/English) tested in Phase 2 and not adopted | Lesson 1 provider boundary; see `docs/PHASE1_NOTES.md`, `PHASE2_NOTES.md` |
| Judge LLM | A stronger model than the generator, pinned | Lesson 6 |
| Evaluation | Own metrics code (chunk-ID based) + `ragas` | Lesson 6 |
| UI | Streamlit | Simple demo |
| Schedule store | pandas / SQLite from the cleaned CSV | Deterministic tool |

**Open decision:** which LLM we can run. A local 3–4B model may struggle with Korean and with strict JSON output. Test it in Phase 1 and keep the interface swappable.

---

## 9. Repository structure

Owner of each folder in brackets. Code folders hold code; generated files live under `data/` or `experiments/results/`. Every path is defined once, in `rag/paths.py`. Dependencies run one way: `preprocess`, `ingest`, `eval` and `experiments` import `rag`, and `rag` imports none of them (`tests/test_layering.py`).

```
data/                                                                   [Vitou]
  raw/                        official sources, never edited
    korean_waste_policies.csv, item_guides/*.pdf
    api_snapshot/             (later) 770-item API snapshot + fetch date
  manual/                     written by hand: glossary.json, food_waste_table_2018.json
  interim/                    parsed_item_chunks.jsonl (PDF parser output)
  processed/                  item_chunks.jsonl, schedule.csv, dong_lookup.json,
                              district_aliases.json, locations.json, manifest.json
  reports/                    data_quality.md, index/ (index verification reports)
preprocess/                   raw → processed                           [Vitou]
  parse_item_guides.py        PDF → parsed chunks
  build_items.py, build_schedule.py, build_all.py, common.py
ingest/                                                                 [Shukurullo]
  build_index.py              chunks → embeddings → Qdrant
  verify_index.py             verification report
rag/                                                                    [Shukurullo]
  paths.py, config.py         every path; every setting
  files.py                    JSONL and hash helpers
  llm_client.py               provider interface (Ollama / fixture)
  router.py                   intent + entity extraction + rewrite validation
  retrieve.py                 dense, BM25, RRF, rerank
  index_registry.py           which verified index to read
  embeddings.py, korean.py, bins.py
  schedule_tool.py            typed lookup + date helper
  schedule_text.py            schedule answers written by code
  schedule_vector.py          vector variants, E4 only
  gate.py                     sufficiency + conflict policy
  context.py                  ContextBudget + evidence packing
  generate.py                 prompt versions + JSON output
  validate.py                 schema, allowed bins, citation resolution
  handoff.py                  office phone, Korean sentence
  answer.py                   the answer dict (the contract, §4.8)
  pipeline.py                 end-to-end stages
  tracing.py                  stage timing, trace writing
  __main__.py                 command line: python -m rag "..."
  prompts/                    versioned prompt files (router_v1.md, answer_v2.md, ...)
eval/                                                                   [Anar]
  cases.py, metrics.py        built; metrics still to complete (§7.3)
  cases/dev.jsonl, test.jsonl
  make_cases.py               template generation from chunks + CSV
  run_eval.py                 run a config over a split → report JSON
  ragas_eval.py               optional judge scoring
  human_audit.csv
  reports/
experiments/
  configs/E1_*.json ... E8_*.json                                       [Shukurullo]
  probes/                     developer regression questions
  results/                    E2/ to E5/ traces, probes/ timestamped runs [Anar]
  run_experiment.py, run_probes.py, tau_sweep.py, provenance.py
tests/                        one file per module, no models or Ollama  [Shukurullo]
docs/                         PHASE1_NOTES.md, PHASE2_NOTES.md
notebooks/schedule_eda/       CSV exploration                           [Vitou]
app/                          website (optional)                        [Naura]
report/                       final report + figures                    [Anar]
slides/                       presentation                              [All]
qdrant_data/, traces/         (gitignored)
PLAN.md, README.md, pyproject.toml, requirements*.txt
```

Each person works on their own branch (`vitou`, `shukurullo`, `anar`, `naura`) and merges into `main` through pull requests.

---

## 10. Task assignments and roadmap

### 10.1 Tasks per person

#### Vitou: data collection and preprocessing
`preprocess/` (`python -m preprocess.build_all`; report in `data/reports/data_quality.md`) was built by Shukurullo on 2026-11-04 so Phase 2 could run on clean data, without having seen Vitou's fixes for `split_dongs`, `province` and row handling, pushed to branch `vitou` on 2026-11-03 (`90ca8b9`, with `notebooks/schedule_eda/README.md`). The pipeline reads `data/processed/`; comparing the two found a real bug in it (below). Vitou: please review the outputs, especially the manual table transcription and the glossary, and take over the open collection items.

Collection:
- [ ] Apply for the data.go.kr API key; save a snapshot of the ~770-item recycling API (`data/raw/api_snapshot/`, with fetch date)
- [ ] Check data.go.kr for a newer version of the district CSV; record download date and file hash
- [ ] Optional: find schedules for missing Seoul districts (Gangdong-gu, Dobong-gu) on district websites, marked as a separate source

Preprocessing (fixes from §3.2):
- [x] Keep area names ending in 읍/면/리/가/로 (`preprocess/build_schedule.py`; Vitou's own fix is in `notebooks/schedule_eda/utils.py` on branch `vitou`); expand number lists with any separator (`휘경1,2동`, `상계6.7동`, `청학1·2동`, `수성1,2.3,4가동`); move `(… 제외)` to notes. The `.`/`·`/`ㆍ` lists were found by comparing with Vitou's output
- [x] Add `province` to every schedule record; handle the 7 duplicate district names (lookup asks which province)
- [x] List the ambiguous neighbourhood names in `data/processed/dong_lookup.json` (228 of 6,070)
- [x] Keep `data_date`; flag rows older than 1 year (`오래된데이터`: 56% of rows as of 2026-11-04)
- [x] Export the cleaned schedule table `data/processed/schedule.csv` (+ `schedule_chunks.jsonl` for E4, `locations.json` for the website)
- [x] `district_aliases.json`: 1,723 romanised names → Korean (Seongdong-gu → 성동구; `jung-gu` → asks which city)
- [x] `glossary.json`: 36 terms in ko/en/zh/vi/uz/ru (zh/vi/uz/ru need a native-speaker check)
- [x] `manifest.json` for all sources and outputs (§4.1)
- [x] Item chunk IDs → UUIDv5 (`preprocess/build_items.py`; old IDs kept as `legacy_id`); `data/processed/item_chunks.jsonl` (403 chunks)
- [ ] Add API-snapshot chunks when the API key is available
- [x] Data checks: unique IDs, no empty text, flat metadata types; summary in `data/reports/data_quality.md`
- [x] **Clean table chunks for guide p.17/p.18** (9 `table` chunks, `data/manual/food_waste_table_2018.json`; fixed probes p02, p03, p05, p16). (food waste: what is NOT food waste). The PDF tables lose their layout, and the 7B model reads "bones → general-waste bag" as "food waste" (Phase 2 probes p03, p16). Write one clear chunk per row, e.g. "닭 등의 뼈다귀, 생선뼈 → 음식물류폐기물 아님, 종량제봉투로 배출". Check other table pages the same way

#### Shukurullo: model implementation (RAG pipeline)
- [x] Repo setup: `.gitignore`, `requirements.txt`, folder structure (§9)
- [x] `llm_client.py`: Ollama + fixture client; Korean and JSON tested (Phase 1 notes)
- [x] `build_index.py` + `verify_index.py`: bge-m3 collection built, verification PASS
- [x] bge-small-en collection for E2 (built, PASS; 29/394 chunks exceed its 512-token limit)
- [x] `retrieve.py`: dense retrieval (baseline)
- [x] `retrieve.py`: BM25 (kiwipiepy morphemes / character bigrams), RRF fusion, cross-encoder rerank (`bge-reranker-v2-m3`, best score over original + rewrite)
- [x] `schedule_tool.py` + date helper, over `data/processed/schedule.csv`
- [x] `router.py`: intent/entity JSON + rewrite validation (item, Korean script, location named in the question via romanisation, negation, language) + retry/fallback
- [x] `gate.py`: per-part gate (item: rerank score ≥ τ; schedule: OK / clarify / no data; out of scope). τ = 0.15 is provisional (middle of the probe gap 0.039–0.264, `experiments/tau_sweep.py`) until E5 on dev
- [x] Conflict policy: prompt rule switchable (`conflict_policy`, E8) + source-year notes in the answer
- [x] `context.py`: `ContextBudget` + evidence packing (tokenizer-based counts)
- [x] `generate.py`: zero-shot contract prompt `answer_v1` + JSON schema + citation check
- [x] Prompt versions for E1: `answer_v0` (minimal), `answer_v1` (zero-shot contract), `answer_v2` (few-shot contract; default), `answer_v3` (v2 without the example that leaked into answers; see `PHASE2_NOTES.md` §5)
- [x] `validate.py` + `bins.py`: canonical bins (also enforced by the JSON schema), bin supported by cited evidence, empty bin filled from the answer text or cited chunks (must agree with the bin the chunks state), bin field consistent with answer text, cited answer, schedule-day check; `enforce` downgrades to abstain
- [x] `handoff.py`: office + phone from the district data, Korean sentence to show, what was checked
- [x] `pipeline.py`: `answer()` for the website and `run_case()` for evaluation; trace writing
- [x] `experiments/configs/E1–E8` + `run_experiment.py` + `tau_sweep.py` (E6 chunkings still need their data)
- [x] Deterministic unit tests: `python -m pytest`
- [x] E4 vector variants: `ingest.build_index --corpus schedule`, `rag/schedule_vector.py`, `experiments/probes/probes_schedule.jsonl` (27 probes; results in `PHASE2_NOTES.md` §10; still to run on dev)
- [x] Gate: when an area has more than `MAX_ZONES` rows with different schedules, ask or hand off instead of answering from the first 4 (`PHASE2_NOTES.md` §10)
- [x] Schedule answers: write days, times and places in code, so `answer_text` cannot drop or change them (`rag/schedule_text.py`; `PHASE2_NOTES.md` §10)
- [x] Repository restructured (§9): code apart from data, one way of depending on `rag/`, `pipeline.py` split into stages, tests per module under pytest. Same output as before on all 147 recorded traces
- [ ] Re-run E1–E8 on Anar's dev set when it exists; pick τ (E5) and freeze the config
- [x] CLI demo (`python -m rag`); Phase 1 notes in `docs/PHASE1_NOTES.md`
- [x] Developer probe set (`experiments/run_probes.py`, 22 questions) for quick regression checks

#### Anar: evaluation and reports
Evaluation:
- [ ] Test set v1 (§7.1–7.2): ~100 cases, slices, language variants, dev/test split frozen **before** tuning
- [ ] Collect 6–10 real questions from international students
- [ ] `metrics.py` + `run_eval.py` (can start now with mock traces)
- [ ] Baseline numbers on dev; run E1–E8 on dev as each one becomes runnable
- [ ] `ragas_eval.py` with a pinned judge; human audit of ~20 answers with a second rater (e.g., Naura); agreement score
- [ ] Gate threshold sweep on dev (with Shukurullo)
- [ ] Final single run on test; failure heatmap; 3–5 case studies; robustness probes (§7.6)

Reports:
- [ ] Report following §12, collecting inputs from each member
- [ ] Tables and figures: data quality, ablation table, slice/language results, heatmap, gate confusion matrix
- [ ] Lesson mapping (§5) and industry lens (§11) sections

**Test-set rule (Lesson 6):** Anar keeps the test split private until the final run. Shukurullo develops and tunes only on dev.

#### Naura: website (optional)
- [ ] Choose the stack (Streamlit, or FastAPI + HTML)
- [ ] Build against a **mock** answer JSON (§4.8) first, so work doesn't wait for the pipeline
- [ ] Chat box, language selector, district/neighbourhood dropdown (from Vitou's district list)
- [ ] Answer card: bin, how to prepare, schedule, "data as of" date, office phone, Korean handoff sentence
- [ ] Expandable source cards; glossary hover; 👍/👎 feedback saved with `trace_id`
- [ ] Connect to the real `answer()` when ready; prepare the demo flow
- [ ] Optional: second rater for the human audit

#### All: presentation
- [ ] Each member presents their own part:

  | Part | Presenter |
  |---|---|
  | Problem and vision | Anar |
  | Data | Vitou |
  | System design | Shukurullo |
  | Evaluation results | Anar |
  | Demo | Naura, or Shukurullo if there is no website |

- [ ] Backup screenshots or a video of the demo in case the live demo fails
- [ ] One full rehearsal with timing

### 10.2 Handoffs between members

| From → To | What | Format | Needed for |
|---|---|---|---|
| Vitou → Shukurullo | Item chunks (UUIDv5), manifest, schedule table, dong lookup, district aliases, glossary; clean table chunks for guide p.17/18 | §4.1 chunk record; §4.5 `ScheduleRow` | Phase 1–2 |
| Vitou → Anar | Chunk IDs and schedule rows for gold labels; data-quality numbers | Same files | Phase 1 |
| Vitou → Naura | District and neighbourhood list for dropdowns | `district_aliases.json`, `dong_lookup.json` | Phase 3 |
| Shukurullo → Anar | `Pipeline(cfg).run_case(case) -> trace`; `experiments/configs/E*.json` + `run_experiment.py`; `tau_sweep.py` | Trace §4.11; `experiments/results/<id>/` | Phase 1–2 |
| Shukurullo → Naura | `answer(question, lang, district, dong) -> dict` | Answer JSON §4.8 | Phase 3 (mock earlier) |
| Anar → Shukurullo | Dev results and failure labels after each change | `eval/reports/*.json` | Each Phase 2 step |
| Anar → all | Report draft for each member to check their section | `report/` | Phase 4 |

Changing a shared format means telling the others and bumping its version (e.g., `chunk_schema: v2`).

### 10.3 Phases

No deadline is fixed in this plan. Phases are ordered by dependency, and each one ends with something runnable. Work that doesn't depend on others starts right away: Anar's test set and metrics, and Naura's mock website.

**Phase 0: Data foundation**
- [x] Collect official item guides (2018 guideline, 2026 Annex 1) (done)
- [x] Item chunk builder → 394 chunks (`preprocess/parse_item_guides.py`) (done)
- [x] CSV fixes, schedule table, lookups, glossary, manifest, UUIDv5 IDs (`preprocess/`)
- [ ] API key + 770-item snapshot (Vitou, optional)
- [x] `.gitignore`, `requirements.txt`, folders (Shukurullo)
- [ ] Case schema + first test cases (Anar)
- [x] Mock-data website skeleton (Naura; `app/` on branch `naura`, not merged yet)

**Phase 1: Baseline system + test set**
- [ ] Test set v1 frozen: dev + test (Anar)
- [x] Qdrant index + verification report (Shukurullo)
- [x] Baseline pipeline: vector-only retrieval → simple prompt → answer, CLI (Shukurullo)
- [x] Schedule tool v1 (Shukurullo)
- [x] `LLMClient` with Ollama; Korean + JSON check (Shukurullo)
- [ ] `run_eval.py` + `metrics.py`; first baseline numbers on dev (Anar)

**Phase 2: Improvements, one at a time (dev set only)**
- [x] Router + rewrite validation (Shukurullo)
- [x] Hybrid retrieval E3; embedding comparison E2 built (Shukurullo); probe runs in `PHASE2_NOTES.md`
- [ ] E2/E3 on dev; E4 vector variants (Shukurullo builds, Anar measures)
- [x] Reranker + gate + `tau_sweep.py` built (Shukurullo)
- [ ] E5 τ sweep on dev (Anar measures)
- [x] Prompt variants E1 built (Shukurullo)
- [ ] E1 on dev (Anar measures)
- [ ] Optional: E6, E7, E8, HyDE

**Phase 3: Product**
- [x] Generator JSON contract + validation + citation check (Shukurullo)
- [x] Conflict policy + data-date warnings (Shukurullo)
- [x] Handoff message: office phone + Korean sentence (Shukurullo)
- [ ] Website connected to `answer()` (Naura)
- [ ] Trace logging + feedback (Shukurullo, Naura)

**Phase 4: Final evaluation, report, presentation**
- [ ] Freeze the configuration; single run on test (Anar)
- [ ] Ragas scoring + human audit (Anar + second rater)
- [ ] Failure heatmap, case studies, robustness probes (Anar)
- [ ] Final report (Anar, with input from all)
- [ ] Slides, demo, rehearsal (All)

### 10.4 Road to website-ready

Goal: everything except the website is finished, and connecting the website is one small, known step. The stages run in this order because each needs the one before. Stage 1 comes before evaluation because it changes what users see, and nothing is measured on inputs we already know are wrong.

**Stage 1: Website-ready system.** No outside dependency.
- [x] Merge branches `vitou` and `naura` here, so `app/` and Vitou's README sit in the new layout. Move `main` forward by pull request: it still holds only the initial commit *(merged, with `anar` too; the pull request into `main` is the last step)*
- [x] `rag/contract.py`: the answer as typed models, with the JSON schema exported to `docs/answer_schema.json`. `answer()` checks its output against them, so a field cannot change without a failing test
- [x] `rag/service.py`: the one module the website imports. `ask()`, `save_feedback(trace_id, rating, comment)`, `source_text(citation)`, `locations()`, `glossary()`, `languages()`. It holds the single `Pipeline`, which takes time to load
- [x] Fixed text in all six languages. Today `clarify.question`, `handoff.contact` and `notes` are English only, and `message()` covers English and Korean only
- [x] The answer gaps in `PHASE2_NOTES.md` §10: say in `answer_text` when the item part failed, and show `no_collection_days`
- [x] Citations carry the page and text, for the source cards
- [x] Feedback saved by `trace_id` in `traces/feedback.jsonl`
- [x] `docs/answer_examples.json`: one real answer per status, replacing Naura's mock, and an offline mode so the website runs without Ollama
- [x] `docs/WEBSITE.md`: one page on what to call and what to show

Done when: a contract test passes on all 49 probes in every status, and the page's data needs are all answered by `rag/service.py`.

**Stage 2: Evaluation tools and cases.**
- [x] `eval/make_cases.py` and a schema check for cases (§7.1): about 100 cases over the slices in §7.2
- [x] Decide the `schedule` sampling: by row, by district, or both (`PHASE2_NOTES.md` §10; 정선군 and 고흥군 are about a third of the table)
- [x] Stratified 70/30 split with a fixed seed, frozen with its hash **before** any tuning
- [x] `eval/metrics.py` complete (§7.3) and `eval/run_eval.py`, writing `eval/reports/`
- [x] Baseline numbers on dev

**Stage 3: Tune on dev.** About 4 to 5 hours of unattended machine time, estimated from measured medians and about 70 dev cases.
- [x] E2, E3, E5 (rerank and τ), E1, E4, E8, E7; E6 if its chunk files are built. HyDE stays out unless a retrieval failure calls for it *(all run; E6 not run, its chunk files were not built; E9 item-name search added)*
- [x] Work through `PHASE2_NOTES.md` §9 one change at a time, each measured on dev: Uzbek abstention, fluent wrong rewrites, `is_korean`, invented steps in `how_to_prepare`, wrong citations, latency
- [x] Choose τ by the §4.6 objective, choose the prompt version, freeze the config in `rag/config.py`, and record the commit *(τ 0.15, prompt v5, router repair; frozen at `cf047ff`)*

**Stage 4: Final evaluation.**
- [x] One run on test with the frozen config *(22/30 correct, 1/30 false answers; baseline 11/30, 4/30)*
- [x] Ragas with a pinned judge; export the audit sheet of about 20 answers *(17 answers; the two raters have not filled it yet)*
- [x] Results by slice and language, failure heatmap, 3 to 5 case studies, robustness probes (§7.6)

**Stage 5: Report and slides.**
- [x] Figures and tables, the report following §12, and slides following §10.1 *(docs/REPORT.md and .pdf; slide deck)*

**Stage 6: Website (Naura).** The only stage left at this point.
- [x] Replace `get_mock_answer` in `app/streamlit_app.py` with `rag.service.ask()`
- [x] Add the page parts the mock does not have: `OUT_OF_SCOPE`, clarify options, handoff, source cards, all six languages, the full location list
- [ ] Demo flow, backup screenshots *(demo flow is in the slides; backup screenshots of the live page are a team task at rehearsal)*

**What only people can do.** These cannot be generated, and the report must not imply they were.

| Task | Who | Needed by |
|---|---|---|
| 6 to 10 real questions from international students | Team | Stage 2, or the `real_users` slice is reported as missing |
| Review of the table transcription and glossary | Vitou | Before Stage 2: gold labels depend on them |
| Native-speaker check: glossary, day and label tables, Chinese method text | Speakers of zh, vi, uz, ru | Before the report claims those languages work |
| Paraphrased cases checked by a person (§7.2) | Team | Stage 2 |
| Human audit of about 20 answers, two independent raters | Two members | Stage 4 |
| Deadline, presentation date, demo format | Team | Sets how far E6 and the optional work go |

---

## 11. Industry lens for our app (Lesson 7 format)

| Lens | Our application |
|---|---|
| **Problem** | Foreign residents can't read the Korean rules and don't know their district's schedule; mistakes lead to uncollected trash or fines |
| **Application** | RAG over official national rules + a deterministic lookup over district data, multilingual, with citations and handoff |
| **Pros** | 24/7 answers in the user's language; one place for national + local rules; sources and dates are visible |
| **Cons** | Data can be stale (2019–20 rows); district rules can differ from national guides; small LLMs can mistranslate or invent; wrong confident answers cost the user |
| **Improvement** | Prefer newer sources, show effective dates, abstain below a calibrated threshold, hand off with a Korean sentence |
| **Measurement** | Bin correctness and abstention accuracy on a frozen test set, by slice and language; faithfulness audited by humans; for a real deployment: resolved questions and repeat questions, not just chats answered |

Maintenance (Moderna lesson): each source has an owner, a revision hash and a review date in the manifest. A monthly check of the data.go.kr CSV triggers an incremental rebuild.

---

## 12. Final report outline

1. Problem, users, scope and non-goals (L01)
2. Data sources, quality analysis and limitations (§3)
3. Ingestion contract and index verification (L03)
4. Representation contract and embedding choice (L02, E2)
5. Retrieval design: router, hybrid, filter, rerank, gate (L04, L05)
6. Generation contract, citations, validation, handoff (L01, L04, L07)
7. Evaluation method: test set, slices, metrics, judges (L06)
8. Results: ablation table E1–E8, latency (L05)
9. Failure analysis: heatmap, case studies, robustness probes (L06)
10. Industry lens and maintenance (L07)
11. Limitations, risks, responsible use, future work

---

## 13. Risks and mitigations

| Risk | Mitigation |
|---|---|
| Local LLM is weak in Korean or breaks JSON | Test early (Phase 1); retry + schema validation; keep provider swappable |
| District data is stale or incomplete | Show `data_date`; warn when old; abstain for missing districts; give office phone |
| National guide differs from local practice | Label national-rule answers; point to the district office |
| 2018 guide is outdated for some items | Conflict policy (§4.6); E8; conflict slice |
| Test set built from our own chunks favours our system | Add hand-written tricky cases and real student questions; report by slice |
| Ragas judge misreads Korean evidence vs English answers | Human audit; report agreement |
| Too many experiments for the time | "Must" experiments first (E1–E5); others only if time remains |
| Chunk IDs change and break gold labels | UUIDv5 IDs (Phase 0) |
| Team members block each other | Fixed formats between members (§10.2); Anar starts with mock traces, Naura with mock answers |
| Test set leaks into tuning | Anar keeps the test split private until the final run (§10.1) |

---

## 14. Open decisions

- [ ] LLM: `qwen2.5:7b` for router and generator (Phase 1–2 probes; EXAONE 3.5 7.8B tested and not adopted, see `PHASE2_NOTES.md` §8); still open: a stronger model for low-resource languages (Uzbek), and the judge model
- [ ] Which extra languages besides English and Korean
- [ ] Whether to include the 770-item API snapshot (needs an API key)
- [ ] Project deadline, presentation date and demo format
- [ ] Website: build it or not, and which stack (Naura)
