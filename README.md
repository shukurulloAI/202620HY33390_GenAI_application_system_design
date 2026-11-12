# Waste-Sorting Assistant for Foreigners in Korea (RAG)

Course project for 202620HY33390 *Design of Generative AI Application Systems*, Hanyang University.
Team (equal contribution): Anar, Naura, Shukurullo, Vitou. The design, task list and roadmap are in [PLAN.md](PLAN.md).

The assistant tells a foreigner in Korea which bin an item goes in (from the national guides) and
when and where to put waste out (from the district table), with sources, in their language.

## Quick start

```bash
# 1. Python environment (3.11 or 3.12)
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements/dev.txt
# (to reproduce the reported numbers exactly: pip install -r requirements/lock.txt)

# 2. Local LLM (https://ollama.com)
ollama serve                # or open the Ollama app
ollama pull qwen2.5:7b      # default router + generator (qwen2.5:3b = course baseline)

# 3. Build and verify the vector index. Cleaned data is already in data/processed/.
#    The first run downloads BAAI/bge-m3, and the first question BAAI/bge-reranker-v2-m3
#    (~2.3 GB each).
python -m ingest.build_index
python -m ingest.verify_index

# 4. Ask a question
python -m rag "Where do I throw away a pizza box?" --lang en
python -m rag "I live in Seongdong-gu Haengdang-dong. Can I put food waste out tonight?"
python -m rag "When can I put out food waste?" --district 성동구 --dong 행당동

# 5. Check your setup (no models or Ollama needed, a few seconds)
python -m pytest
ruff check .
```

The same checks run on every push and pull request (`.github/workflows/ci.yml`: ruff, the frozen
split, pytest with coverage), with no models or Ollama.

Add `--show-trace` to see the full trace: router output, candidates with dense/BM25/rerank ranks,
gate decision, evidence, token budget, raw LLM output, validation, timings. Every request is also
appended to `traces/<date>.jsonl`.

## Repository layout

Code folders hold code. Generated files live under `data/` or `experiments/results/`, and what each
machine rebuilds for itself (`qdrant_data/`, `traces/`) is gitignored. All paths are in `rag/paths.py`.

```
data/
  raw/            official sources, never edited: district CSV, Ministry of Environment PDFs
  manual/         written by hand and reviewed: glossary, food-waste table transcription
  interim/        PDF parser output
  processed/      built by preprocess/: the files the system reads, plus manifest.json
  reports/        data-quality report; index/ holds the index verification reports
preprocess/       raw -> processed: PDF parser, cleaning, stable IDs, lookups, manifest
ingest/           processed -> vector index: build, verify, publish
rag/              the system: router, retrieval, schedule tool, gate, generation, validation
  prompts/        versioned prompt files
eval/             evaluation: cases (frozen dev/test split), metrics, runner, LLM judge,
                  audit sheets, figures, report PDF
  cases/          dev.jsonl (70), test.jsonl (30), split_manifest.json (seed + SHA-256)
  reports/        one folder per evaluation run: traces, report.json, report.md
experiments/
  configs/        one JSON file per experiment, E1-E9
  probes/         developer regression questions (not an evaluation set)
  results/        raw output: dev/<id>/ (experiments on dev), test/robustness/ (Stage 4 probes),
                  <id>/ and probes/ (Phase 2 probes)
app/              the website (Streamlit), on rag/service.py; ui/ holds its parts
tests/            fast tests with no models or Ollama, one file per module;
                  e2e/ drives the website in Chromium (pytest tests/e2e -m e2e)
docs/             REPORT.md / REPORT.pdf (final report), WEBSITE.md, PHASE1/2_NOTES.md,
                  answer_schema.json + answer_examples.json (answer contract, recorded answers),
                  Model_and_System_Guide.pdf, COMMIT_IDS.md (old -> current commit IDs),
                  AUDIT_GUIDE.md (human audit), V3_PLAN.md (next cycle: data, new held-out set)
notebooks/        data exploration (schedule_eda/)
requirements/     base.txt (the system), app.txt (+ website), dev.txt (+ tests),
                  e2e.txt (browser tests), judge.txt (LLM judge), lock.txt (exact
                  versions of the reported results)
```

Dependencies run one way: `preprocess`, `ingest`, `eval`, `experiments` and `app` import `rag`, and
`rag` imports none of them (`tests/test_layering.py` enforces this).

**Where are the results?** The final report is [docs/REPORT.md](docs/REPORT.md) (PDF:
`docs/REPORT.pdf`). Evaluation runs are in `eval/reports/<name>/` (the final test run is
`eval/reports/test-final/`), experiments on dev in `experiments/results/dev/<id>/summary.md`.
[docs/PHASE2_NOTES.md](docs/PHASE2_NOTES.md) holds the earlier developer probe results, which are
not evaluation results. Run records written before 2026-11-09 store older commit IDs;
[docs/COMMIT_IDS.md](docs/COMMIT_IDS.md) maps them to the current ones.

**Headline.** On the 30 test cases, which were never used for tuning and were run once with the
configuration frozen at commit `f0faba6`, the system got 22 cases right with 1 false answer. The
Phase 1 baseline got 11 right with 4 false answers. In a paired test the gain in correct cases is
significant (p = 0.007); the drop in false answers is not, with 30 cases (p = 0.25, 95% CI 1–17%;
`python -m eval.compare test-final test-baseline`). On dev, with the same configuration, it got 56/70
right with 3 false answers. The cases were written by the team (with AI assistance), not by real users, and the human
audit has not been done yet; see the report's §11.

## How a question is answered

```
question
 -> router (LLM): intent, item, Korean rewrite, district/dong, waste type, day   rag/router.py
 -> item retrieval: dense (bge-m3) + BM25 (kiwi) -> RRF -> cross-encoder rerank  rag/retrieve.py
 -> schedule tool: typed lookup + date check, no LLM                             rag/schedule_tool.py
 -> gate: answer / abstain / clarify / out of scope                              rag/gate.py
 -> context under a token budget -> generator (LLM, JSON schema), items only     rag/context.py, rag/generate.py
 -> validation: allowed bins, bin supported by cited evidence, citations         rag/validate.py
 -> schedule text: days, times, places by code; method translated                rag/schedule_text.py
 -> answer dict + handoff (office phone, Korean sentence) when it cannot answer  rag/answer.py, rag/handoff.py
```

`rag/pipeline.py` runs these stages. All settings live in one `PipelineConfig` (`rag/config.py`).
`config.DEFAULT` is the full system; `config.BASELINE` is the Phase 1 system (dense only, no
router, rerank or gate, prompt v1).

```bash
python -m rag "..." --baseline                          # Phase 1 system
python -m rag "..." --set retrieval=dense --set rerank=false
python -m rag "..." --set llm_model='"exaone3.5:7.8b"'  # another Ollama model
python -m rag "..." --llm fixture                       # offline, no Ollama
```

## Using it from code

An app (the website, a chatbot, a script) should use `rag/service.py`: it creates the pipeline
once, never raises for a question (on any failure the user gets an abstention with a handoff),
and has an offline mode. Details for the website: [docs/WEBSITE.md](docs/WEBSITE.md).

```python
from rag import service
answer = service.ask("Where do I throw away a pizza box?", lang="en",
                     district="성동구", dong="행당1동")    # province=, waste_type= optional
service.save_feedback(answer["trace_id"], "up", "clear answer")
service.source_text(answer["citations"][0])   # full text for a source card
service.locations(); service.glossary(); service.languages(); service.health()
service.warm_up()     # load the pipeline and the Ollama models now (the website does this at start)
service.data_reviews()  # owner and review date per source (data/manual/stewardship.json)
# RAG_OFFLINE=1 (or service.configure(offline=True)): recorded answers, no models
```

The pipeline itself, for evaluation and experiments:

```python
from rag.pipeline import Pipeline
from rag import config
p = Pipeline()                       # full system; Pipeline(config.BASELINE) for Phase 1

p.answer("Where do PET bottles go?", lang="en", district="성동구", dong="행당동")   # website
p.run_case({"case_id": "c001", "question": "...", "lang": "en",
            "location": {"district": "성동구", "dong": "행당동"}})                 # evaluation
```

`Pipeline()` loads two models, so create one and keep it. Only one process can open `qdrant_data/`
at a time; a second process automatically reads a temporary snapshot copy (a full copy of the
folder: fine on one machine, not a way to serve many processes). Tests hand `Pipeline` a
scripted LLM and a fake retriever (`retriever=`, `schedule=`, `counter=`; `tests/helpers.py`).

**Live records.** Every request is a trace in `traces/<date>.jsonl`, failures go to
`traces/errors.jsonl`, 👍/👎 to `traces/feedback.jsonl`. They hold the users' own words, so they are
kept for `RAG_TRACE_RETENTION_DAYS` (default 30, `0` keeps all) and pruned when the pipeline starts.
`python -m eval.ops_summary [--days 7]` summarizes them: requests, status mix, latency p50/p90 per
stage, errors, feedback by answer status.

Answer dict:

| Field | Meaning |
|---|---|
| `status` | `ANSWER`, `INSUFFICIENT_CONTEXT` (abstain), `CLARIFY` (ask the user), `OUT_OF_SCOPE` |
| `lang` | Language of the answer |
| `bin`, `bin_en` | Canonical bin (`rag/bins.py`), e.g. `종량제봉투` / "general waste (pay-as-you-throw bag)" |
| `how_to_prepare`, `answer_text` | Steps and the answer in the user's language, with `[n]` citations. `answer_text` can have several lines |
| `citations` | `{n, kind: item/schedule, ref: chunk_id or 관리번호, source}` |
| `schedule` | From the tool, never the LLM: `days`, `time`, `place`, and `zones` with next dates, `day_check`, office, phone, data date, `stale` |
| `data_date`, `office_phone` | Oldest data date of the rows shown; office phone |
| `missing` | What could not be answered |
| `clarify` | `{question, options}` when `status = CLARIFY` (e.g. which 중구); up to 30 options |
| `handoff` | When it cannot answer: office, phone, a Korean sentence to show, what was checked |
| `notes` | Source-year and data-age warnings |
| `trace_id` | ID of the trace behind this answer |
| `contract_version` | `1.0`; the full schema is `docs/answer_schema.json` (`rag/contract.py`) |

Schedule tool on its own (no models needed):
```bash
python -m rag.schedule_tool 성동구 --dong 행당동 --waste-type food
```

## Data

| File | What |
|---|---|
| `data/processed/item_chunks.jsonl` | 403 item chunks (2018 guide + 2026 annex + 9 hand-transcribed food-waste table rows). IDs are UUIDv5; the old IDs (`item2018_0278`) are in `metadata.legacy_id` |
| `data/processed/schedule.csv` | Cleaned district table (UTF-8): area lists split correctly (`휘경1,2동` -> 휘경1동, 휘경2동), notes separated, stale rows flagged |
| `data/processed/dong_lookup.json` | Neighbourhood -> zones; `ambiguous` lists names found in several districts |
| `data/processed/district_aliases.json` | Romanised -> Korean (`seongdong-gu` -> 서울특별시 성동구) |
| `data/processed/locations.json` | Province -> district -> zones/areas, incl. Seoul districts with no data (website dropdowns) |
| `data/manual/glossary.json` | 36 waste terms in ko/en/zh/vi/uz/ru |
| `data/manual/food_waste_table_2018.json` | Hand transcription of guide p.17-18 (PDF tables lose their layout) |
| `data/processed/manifest.json`, `data/reports/data_quality.md` | Source hashes and dates; data-quality numbers |

```bash
python -m preprocess.parse_item_guides   # only when the PDFs or the parser change
python -m preprocess.build_all           # rebuilds data/processed/ and data/reports/
```

After changing `data/processed/item_chunks.jsonl`, rebuild the index. Its name contains the corpus
hash, so the pipeline refuses to run on a mismatch instead of mixing old and new chunks.

## Experiments

```bash
python -m experiments.run_probes                    # 22 developer probes, full system
python -m experiments.run_probes --baseline         # same probes, Phase 1 system
python -m experiments.run_probes --retrieval-only   # router + retrieval only (fast)

python -m experiments.run_experiment experiments/configs/E3_lexical_dense_hybrid.json \
       --cases eval/cases/dev.jsonl                 # one variant per config, traces per case
python -m experiments.summarize experiments/results/dev/E3        # rewrite its summary.md
python -m experiments.tau_sweep experiments/results/dev/E5/rerank-on.jsonl --cases eval/cases/dev.jsonl

python -m experiments.verify_rerank                 # batched reranker == frozen system's candidates (dev)
python -m experiments.check_contract                # every probe fits the answer contract (Ollama)
python -m experiments.make_examples                 # re-record docs/answer_examples.json (Ollama)
python -m eval.label_helper item 피자 건전지          # candidate gold chunks for a new case
python -m eval.label_helper rows 성동구 --dong 행당1동  # candidate gold rows
python -m preprocess.review_templates               # blank v3 review sheets in data/manual/drafts/
```

With `--cases eval/cases/dev.jsonl`, `run_experiment` writes
`experiments/results/dev/<id>/<variant>.jsonl` (one trace per case), a `manifest.json` (configs,
model revisions, cases SHA-256, git commit) and `summary.md` (one row per variant, plus the cases
each variant gained or lost). `--cases` defaults to `eval/cases/dev.jsonl` (the developer probes
if that file is missing; probe runs write to `experiments/results/<id>/`). It refuses a test
file without `--allow-test`. Paths inside older
manifests are the paths at the time of that run.

## Evaluation

```bash
python -m eval.run_eval --name my-run                 # full system on the dev split
python -m eval.run_eval --name my-base --config baseline
python -m eval.run_eval --name x --set gate_tau=0.3   # one field changed
python -m eval.run_eval --name my-run --rescore       # score saved traces again after a metric fix
python -m eval.compare test-final test-baseline       # paired test (McNemar) + 95% intervals, no models
python -m eval.make_cases --check                     # the frozen split is unchanged
python -m experiments.run_experiment experiments/configs/E9_item_names.json --cases eval/cases/dev.jsonl --cache
python -m experiments.robustness                      # noise / negative / counterfactual probes
python -m experiments.robustness --relabel            # label saved probe traces again (no model calls)

# LLM judge (Ragas), in its own environment, with its own Ollama model
ollama pull exaone3.5:7.8b
python3.12 -m venv .venv-judge && .venv-judge/bin/pip install -r requirements/judge.txt
python -m eval.ragas_eval prepare my-run && .venv-judge/bin/python -m eval.ragas_eval score my-run

python -m eval.audit export my-run                    # two blank sheets for human raters
python -m eval.audit agree my-run                     # after both raters filled their sheet
python -m eval.figures heatmap my-run                 # docs/figures/heatmap_my-run.png
python -m eval.figures ablation dev-baseline=Baseline dev-s3e-final=Final --out docs/figures/x.png
python -m eval.report_pdf                             # docs/REPORT.md -> docs/REPORT.pdf
```

`--cache` replays identical temperature-0 LLM requests (tuning only; latency is then not valid).

**The test split** is refused without `--allow-test`. Stage 4 ran it once, with the configuration
frozen at `f0faba6`; the results are in `eval/reports/test-final/`, `eval/reports/test-baseline/`
and `experiments/results/test/robustness/`. The commands were:

```bash
python -m eval.run_eval --name test-final --cases eval/cases/test.jsonl --allow-test
python -m eval.run_eval --name test-baseline --config baseline --cases eval/cases/test.jsonl --allow-test
python -m experiments.robustness --cases eval/cases/test.jsonl --allow-test
```

Do not run them again to tune anything: a second look at test makes the test numbers optimistic.
To check the numbers without models, score the saved traces again in a copy (`--rescore` rewrites
the report in its folder):

```bash
mkdir eval/reports/check && cp eval/reports/test-final/report.json eval/reports/check/
python -m eval.run_eval --name check --rescore   # 22/30 correct, 1 false answer, bin 11/19
```

The human audit of the test answers is still to do: the sheets are in
`eval/reports/test-final/audit/`, and [docs/AUDIT_GUIDE.md](docs/AUDIT_GUIDE.md) says how to fill
them. Changes that change answers belong to the next cycle, [docs/V3_PLAN.md](docs/V3_PLAN.md),
which needs reviewed data and a new held-out set first.

## Website

![The website: a pizza-box answer](docs/figures/website_desktop_light.png)

```bash
pip install -r requirements/app.txt
streamlit run app/streamlit_app.py                   # live: Ollama running, index built
RAG_OFFLINE=1 streamlit run app/streamlit_app.py     # recorded answers, no models
docker compose --profile offline up                  # the same demo in Docker
deploy/public_link.sh                                # a public https link to this Mac's website
```

The page has the following:
- **Languages.** It comes in the six answer languages, chosen from the link (`?lang=ru`) or the
  browser.
- **Laptop and phone.** On a laptop the question and the answer sit side by side. On a tablet or
  a phone the answer comes below the question, and the page scrolls to it.
- **Progress.** A status box names each stage while a question is answered, and says when the
  question is waiting for another one.
- **Light and dark themes.** Both meet WCAG AA contrast, and axe-core finds no accessibility
  violations in Chromium (`python -m pytest tests/e2e -m e2e`, after
  `pip install -r requirements/e2e.txt`).
- **Maintainer panel.** `RAG_ADMIN=1` adds a panel with the models, digests and data-review dates.
- **Public link.** `deploy/public_link.sh` shares the website through Tailscale Funnel when the
  Tailscale app is signed in (the same link every time), or else a Cloudflare quick tunnel
  (`brew install cloudflared`). A question already asked that day is answered at once from
  memory. At most 5 questions are answered or waiting, and each visitor can ask 20 in
  5 minutes ([docs/WEBSITE.md](docs/WEBSITE.md#a-public-link-from-this-mac)).

What the page shows for each answer field, how it is tested and how to run it in Docker:
[docs/WEBSITE.md](docs/WEBSITE.md).
