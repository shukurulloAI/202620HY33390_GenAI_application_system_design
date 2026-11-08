# Connecting the website

Everything the page needs comes from one module, `rag/service.py`. Every answer it returns fits
the contract in `rag/contract.py`. The full schema, generated from that file, is
[answer_schema.json](answer_schema.json), and [answer_examples.json](answer_examples.json) has
13 real answers covering every case below.

## What to call

```python
from rag import service

answer = service.ask(question, lang="en", district="성동구", dong="행당1동")
service.save_feedback(answer["trace_id"], "up")    # or "down", with an optional comment
service.locations()   # dropdown data: [{province, district, district_en, has_data, zones: [{zone, areas}]}]
service.languages()   # {"en": "English", "ko": "한국어", "zh": "中文", "vi": ..., "uz": ..., "ru": ...}
service.glossary()    # 36 waste terms in all six languages, for hover text
service.health()      # {"offline", "ollama", "pipeline_loaded", "model"}, for a status line
```

- **`ask()` never raises for a question.** If Ollama is down or something breaks, the answer is an
  abstention with a handoff, and the error goes to `traces/errors.jsonl`. An empty question
  raises `ValueError`, so check for it in the page.
- **The first question takes about 20 s**, because two models load. After that a question takes
  15–20 s. Show a spinner.
- **Location:** pass `district` and `dong` from the dropdowns, using the Korean names in
  `locations()`. Leave them out if the user didn't choose. The router then reads the location
  from the question (`"I live in Seongdong-gu Haengdang-dong"`).
- **Districts with `has_data: false`** (도봉구, 강동구) are real districts with no data. Keep
  them in the list: the assistant says it has no data and gives the office instead.

**Offline mode:** set `RAG_OFFLINE=1` before starting the page, and `ask()` returns the recorded
examples with no Ollama and no models. An exact example question returns its own answer, and any
other question gets an example marked as such in `notes`.

## What to show, by `status`

| `status` | Show |
|---|---|
| `ANSWER` | `answer_text`, the bin card (`bin_en` with `bin`), `how_to_prepare`, the schedule card if `schedule` is set, source cards, `notes`. Also `handoff` and `clarify` if present: an answer can cover only one part of the question. |
| `CLARIFY` | `answer_text`, then `clarify.question` with `clarify.options` as buttons. When the user picks one, ask again with it filled in (see below). |
| `INSUFFICIENT_CONTEXT` | `answer_text` and the handoff card. Never show a bin. |
| `OUT_OF_SCOPE` | `answer_text` only. |

## Field by field

| Field | How to show it |
|---|---|
| `answer_text` | **Keep the line breaks.** It has several lines, and `[n]` marks cite `citations[n]`. A partial answer says in its first or last line which part failed. |
| `bin`, `bin_en` | `bin_en` big, `bin` (Korean) small: the Korean is what's printed on the bags. |
| `how_to_prepare` | A numbered list. |
| `schedule.zones[]` | One card per zone: `zone`, `areas`, `place`, then for each type in `by_type` its `days`, `start`–`end` and `next_dates`. `day_check` answers "tonight?"-style questions. Show `no_collection` and `stale`. |
| `citations[]` | Source cards: `source`, then `page` and `year` for guides or `data_date` for district rows, with `text` in an expander. `text` is the Korean evidence the model read. |
| `notes` | Small grey lines under the answer, already in the user's language. |
| `handoff` | A card: `contact` (who to call), `phone` as a `tel:` link, `korean_sentence` in large text with a copy button (it's for the office staff), and `checked` as a list. |
| `clarify.options` | Up to 30 buttons. The values are Korean place names, so show them as they are. |
| `data_date`, `office_phone` | Flat copies for a one-line summary. The same values are in the zone cards. |
| `missing` | Don't show it. It's a diagnostic for us, in English. |
| `trace_id` | Hidden. Send it with feedback. |

**Answering a clarify option.** For `kind: "province"` the option is `"서울특별시 중구"`, so call
`ask(question, province="서울특별시", district="중구")`. For `"zones"` or `"names"`, call with the
same district and `dong=option`. For `"district"`, show the district dropdown.

## Languages

Fixed text is written by code in all six languages: status messages, clarify questions, handoff
lines, notes, schedule labels and no-collection days. The item answer is written by the LLM in
the user's language. The zh, vi, uz and ru tables are drafts that still need a native speaker's
check (`rag/texts.py`, `rag/schedule_text.py`). For vi, uz and ru, the free-text "How" line of a
schedule is shown in English (`docs/PHASE2_NOTES.md` §10).

## Running

```bash
pip install -r requirements-app.txt
streamlit run app/streamlit_app.py            # full system: Ollama running, index built
RAG_OFFLINE=1 streamlit run app/streamlit_app.py   # recorded examples only
```
