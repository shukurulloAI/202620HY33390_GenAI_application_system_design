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
ollama serve            # or open the Ollama app
ollama pull qwen2.5:7b      # default generator (qwen2.5:3b = course baseline)

# 3. Build and verify the vector index (downloads BAAI/bge-m3 on first run, ~2.3 GB)
python -m ingest.build_index
python -m ingest.verify_index

# 4. Ask a question
python -m rag.pipeline "Where do I throw away a pizza box?" --lang en
python -m rag.pipeline "When can I put out food waste?" --district 성동구 --dong 행당동 --lang en
```

Add `--show-trace` to see the full trace: candidates, evidence, token budget, raw LLM output, checks and timings.
Every request is also appended to `traces/<date>.jsonl`.

## Repository layout

| Path | What | Owner |
|---|---|---|
| `Data/` | Raw sources: district CSV (data.go.kr), Ministry of Environment PDFs | Vitou |
| `item_guide/` | PDF → item chunks (`item_guide/output/item_chunks.jsonl`) | Vitou |
| `Vitou_EDA/` | CSV exploration and schedule chunks | Vitou |
| `preprocess/` | Final cleaned outputs used by the pipeline (when ready) | Vitou |
| `ingest/` | Build and verify the Qdrant index; reports in `ingest/reports/` | Shukurullo |
| `rag/` | Pipeline: retrieval, schedule tool, context, generation | Shukurullo |
| `eval/` | Test set, metrics, evaluation runs | Anar |
| `app/` | Website (optional) | Naura |

## Pipeline interfaces

```python
from rag.pipeline import Pipeline
p = Pipeline()                       # loads the verified index, schedule table and LLM client

p.answer("Where do PET bottles go?", lang="en", district="성동구", dong="행당동")
# -> answer dict: status, bin, bin_en, how_to_prepare, answer_text, citations, missing, schedule, trace_id

p.run_case({"case_id": "c001", "question": "...", "lang": "en",
            "location": {"district": "성동구", "dong": "행당동"}})
# -> full trace for evaluation
```

Schedule tool on its own (no models needed):
```bash
python -m rag.schedule_tool 성동구 --dong 행당동 --waste-type food
```
