# Waste-Sorting Assistant for Foreigners in Korea (RAG)

Course project for 202620HY33390 *Design of Generative AI Application Systems*, Hanyang University.
Team: Shukurullo, Vitou, Anar, Naura. The full design and task list is in [PLAN.md](PLAN.md).

## Quick start

```bash
# 1. Python environment (3.11 or 3.12)
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# 2. Local LLM (https://ollama.com)
ollama serve                # or open the Ollama app
ollama pull qwen2.5:7b      # default router + generator (qwen2.5:3b = course baseline)

# 3. Preprocess the data (cleaned schedule table, UUIDv5 chunk IDs, lookups, manifest)
python -m preprocess.build_all

# 4. Build and verify the vector index (first run downloads BAAI/bge-m3, ~2.3 GB;
#    the first question downloads the reranker BAAI/bge-reranker-v2-m3, ~2.3 GB)
python -m ingest.build_index
python -m ingest.verify_index

# 5. Ask a question
python -m rag.pipeline "Where do I throw away a pizza box?" --lang en
python -m rag.pipeline "I live in Seongdong-gu Haengdang-dong. Can I put food waste out tonight?"
python -m rag.pipeline "When can I put out food waste?" --district 성동구 --dong 행당동
```

Add `--show-trace` to see the full trace (router output, candidates with dense/BM25/rerank
ranks, gate decision, evidence, token budget, raw LLM output, validation, timings).
Every request is also appended to `traces/<date>.jsonl`.

## Data

| File (`preprocess/`) | What |
|---|---|
| `item_chunks.jsonl` | 403 item chunks (2018 guide + 2026 annex + 9 hand-transcribed food-waste table rows). IDs are UUIDv5; the old IDs (`item2018_0278`) are in `metadata.legacy_id` |
| `schedule.csv` | Cleaned district table (UTF-8): area lists split correctly (`휘경1,2동` → 휘경1동, 휘경2동), notes separated, stale rows flagged |
| `dong_lookup.json` | Neighbourhood → zones; `ambiguous` lists names found in several districts |
| `district_aliases.json` | Romanised → Korean (`seongdong-gu` → 서울특별시 성동구) |
| `locations.json` | Province → district → zones/areas, incl. Seoul districts with no data (website dropdowns) |
| `glossary.json` | 32 waste terms in ko/en/zh/vi/uz/ru |
| `manifest.json`, `reports/data_quality.md` | Source hashes and dates; data-quality numbers for the report |
| `manual/food_waste_table_2018.json` | Hand transcription of guide p.17–18 (PDF tables lose their layout) |

The pipeline uses `preprocess/` files when they exist and falls back to the raw files otherwise.
After changing anything in `preprocess/`, rebuild the index (step 4).

## How a question is answered

```
question
 -> router (LLM): intent, item, Korean rewrite, district/dong, waste type, day   rag/router.py
 -> item retrieval: dense (bge-m3) + BM25 (kiwi) -> RRF -> cross-encoder rerank  rag/retrieve.py
 -> schedule tool: typed lookup + date check, no LLM                            rag/schedule_tool.py
 -> gate: answer / abstain / clarify / out of scope                              rag/gate.py
 -> context under a token budget -> generator (LLM, JSON schema)                rag/context.py, rag/generate.py
 -> validation: allowed bins, bin supported by cited evidence, citations        rag/validate.py
 -> answer + handoff (office phone, Korean sentence) when it cannot answer      rag/handoff.py
```

All settings live in one `PipelineConfig` (`rag/config.py`). `config.DEFAULT` is the full
system; `config.BASELINE` is the Phase 1 system (dense only, no router/rerank/gate, prompt v1).

```bash
python -m rag.pipeline "..." --baseline                          # Phase 1 system
python -m rag.pipeline "..." --set retrieval=dense --set rerank=false
python -m rag.pipeline "..." --set llm_model='"exaone3.5:7.8b"'  # another Ollama model
python -m rag.pipeline "..." --llm fixture                       # offline, no Ollama
```

## Interfaces for teammates

```python
from rag.pipeline import Pipeline
from rag import config
p = Pipeline()                       # full system; Pipeline(config.BASELINE) for Phase 1

p.answer("Where do PET bottles go?", lang="en", district="성동구", dong="행당동")
p.run_case({"case_id": "c001", "question": "...", "lang": "en",
            "location": {"district": "성동구", "dong": "행당동"}})   # full trace, for eval
```

Answer dict (website):

| Field | Meaning |
|---|---|
| `status` | `ANSWER`, `INSUFFICIENT_CONTEXT` (abstain), `CLARIFY` (ask the user), `OUT_OF_SCOPE` |
| `bin`, `bin_en` | Canonical bin (`rag/bins.py`), e.g. `종량제봉투` / "general waste (pay-as-you-throw bag)" |
| `how_to_prepare`, `answer_text` | Steps and the answer in the user's language, with `[n]` citations |
| `citations` | `{n, kind: item/schedule, ref: chunk_id or 관리번호, source}` |
| `schedule` | From the tool, never the LLM: zones, days, times, next dates, `day_check`, office, phone, data date, `stale` |
| `clarify` | `{question, options}` when `status = CLARIFY` (e.g. which 중구) |
| `handoff` | When it cannot answer: office + phone, a Korean sentence to show, what was checked |
| `notes` | Source-year and data-age warnings |

Schedule tool on its own (no models needed):
```bash
python -m rag.schedule_tool 성동구 --dong 행당동 --waste-type food
```

## Experiments

```bash
python -m experiments.run_probes                    # 22 developer probes, full system
python -m experiments.run_probes --baseline         # same probes, Phase 1 system
python -m experiments.run_probes --retrieval-only   # router + retrieval only (fast)

python -m experiments.run_experiment experiments/configs/E3_lexical_dense_hybrid.json \
       --cases eval/cases/dev.jsonl                 # one variant per config, traces per case
python -m experiments.tau_sweep experiments/results/E5/rerank-on.jsonl --cases eval/cases/dev.jsonl
```

`run_experiment` writes `experiments/results/<id>/<variant>.jsonl` (one trace per case) and a
`manifest.json` (configs, model revisions, cases SHA-256, git commit). It refuses a test file
without `--allow-test`. Without `eval/cases/dev.jsonl` it falls back to the probes and says so.

Only one process can open `qdrant_data/` at a time; a second process (e.g. the website
while an evaluation runs) automatically reads a temporary snapshot copy.

## Repository layout

| Path | What | Owner |
|---|---|---|
| `Data/` | Raw sources: district CSV (data.go.kr), Ministry of Environment PDFs | Vitou |
| `item_guide/` | PDF → parsed item chunks (`item_guide/output/item_chunks.jsonl`) | Vitou |
| `Vitou_EDA/` | CSV exploration and schedule chunks | Vitou |
| `preprocess/` | Cleaning, IDs, lookups, manifest, data-quality report (`python -m preprocess.build_all`) | Vitou (built by Shukurullo) |
| `tests/` | Deterministic unit tests (`python -m tests.test_deterministic`) | Shukurullo |
| `ingest/` | Build and verify the Qdrant index; reports in `ingest/reports/` | Shukurullo |
| `rag/` | Pipeline: router, retrieval, schedule tool, gate, generation, validation | Shukurullo |
| `experiments/` | Probes, experiment configs E1–E8, runner, results | Shukurullo (build), Anar (measure) |
| `eval/` | Test set, metrics, evaluation runs | Anar |
| `app/` | Website (optional) | Naura |
