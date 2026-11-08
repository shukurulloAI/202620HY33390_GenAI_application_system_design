# Waste-Sorting Assistant for Foreigners in Korea

<p class="subtitle">Final report · 202620HY33390 Design of Generative AI Application Systems, Hanyang University · Team: Shukurullo (system), Vitou (data), Anar (evaluation and report), Naura (website) · 2026-11-08</p>

> **In one paragraph.** A foreigner in Korea asks, in their own language, which bin an item goes in and when waste is collected in their neighbourhood. The assistant answers from two official sources: the national separation guides for items, and the district collection table for days and places. It cites both. When it cannot answer safely, it says so and hands off to the district office with a Korean sentence the user can show. On a frozen test split of 30 cases that the system never saw while it was tuned, it got @@TEST_CORRECT@@ cases right, with @@TEST_FALSE@@ false answers (answering when it should not, or with the wrong bin). The Phase 1 baseline scored @@TEST_BASE_CORRECT@@ correct and @@TEST_BASE_FALSE@@ false answers on the same cases. The main weaknesses are translating item names from low-resource languages into Korean, and a 7B model that sometimes contradicts its own evidence. Validation catches most of these and turns them into abstentions.

## 1. Problem, users, scope (Lesson 1)

**Users.** International students and other foreign residents who do not read Korean well, mainly in Seoul.

**Questions.** "Which bin does this item go in, and how do I prepare it?" (item questions) and "When and where can I put out food waste in 행당1동?" (schedule questions), or both at once.

**Why it matters.** Mistakes mean trash left uncollected, fines, and friction with neighbours. The official rules are in Korean PDFs and a 10,187-row spreadsheet.

**Non-goals.** Business waste, construction waste, scrapping a car, fines and prices, and anything outside household waste in Korea. These are refused (`OUT_OF_SCOPE`) or handed off.

**Cost of errors.** A confident wrong bin costs the user more than an abstention. So the system is built to abstain when its evidence is weak, and the main safety number is the **false-answer rate**.

## 2. Data sources and their quality (§3)

| Source | Used for | Size | Notes |
|---|---|---|---|
| Ministry of Environment, *Recycling Separation Guideline* (2018), 36 pages | Item bins, FAQ, general rules | 293 items, 36 FAQ, 20 guide pages | Food-waste tables on p.17–18 lost their layout in PDF extraction: 9 rows transcribed by hand |
| Separation directive, Annex 1 (effective 2026-01-01) | Current rules by material group | 42 rules, 3 notes | Some items changed since 2018 (clear PET bottles, small electronics) |
| data.go.kr household-waste collection table (CP949) | Days, times, places, method, office phone | 10,187 rows, 222 districts | 61% of rows are over a year old; Seoul 강동구 and 도봉구 have no rows; 7 district names exist in several provinces |

The data work was done before any tuning, following the lesson "do not measure on known-bad data". It included:
- stable UUIDv5 chunk IDs;
- splitting area lists such as `휘경1,2동`;
- keeping the province, so the seven duplicated district names (such as 중구) can be told apart;
- a romanised-to-Korean alias table (1,723 aliases);
- flagging stale rows.

Details: `data/reports/data_quality.md`, `docs/PHASE2_NOTES.md` §1.

## 3. Ingestion contract and index verification (Lesson 3)

The 403 item chunks (`data/processed/item_chunks.jsonl`) are embedded with **BAAI/bge-m3**, pinned by revision, into a local Qdrant collection. The collection's name includes the model revision and the corpus hash (`items_bge-m3_5617a9f6_c7d19676`). The pipeline refuses to run if the corpus hash does not match, so old and new chunks are never mixed. Each build is verified before it is published: point count, no duplicate IDs, and a test that every chunk retrieves itself (`ingest/verify_index.py`).

Schedules are **not** embedded for answering. The rows are near-duplicates that differ only in the district name, so vector search returns the wrong district (E4, §8).

## 4. Representation and embedding choice (Lesson 2, E2)

The corpus is Korean, while questions come in six languages. **E2** (dense retrieval only, the original question as the query, n = 44 dev cases with gold chunks):

| Embedding | Recall@5 | MRR |
|---|---|---|
| bge-small-en (course default, English only) | 0.068 | 0.064 |
| bge-small-en, query rewritten into Korean | 0.068 | 0.069 |
| **bge-m3 (multilingual)** | **0.568** | **0.474** |

An English-only model cannot represent Korean chunks at all, even when the query itself is Korean. bge-m3 is the only usable option.

## 5. Retrieval design (Lessons 4–5)

```
question ─► router (qwen2.5:7b, JSON): intent, item, Korean item name + query, district/dong, waste type, day
         ─► item retrieval: dense (bge-m3) + BM25 (kiwi) for the question and its Korean rewrite,
            + item-name search (router's item name vs chunk names)  ─► RRF (k = 60) ─► top 20
            ─► cross-encoder rerank (bge-reranker-v2-m3, best score over all queries) ─► top 5
         ─► schedule tool: typed lookup over the table (province, district, area), dates computed in code
         ─► gate: answer / abstain (top rerank score < τ) / ask back (ambiguous place) / out of scope
```

**Router.** The router extracts the item and a Korean rewrite. Its output is checked against the question: the item must appear in it, the rewrite must be Hangul, a negation must be kept, and a place must be one the question mentions. A rewrite that fails these checks is not used.

**Retrieval experiments on dev** (Recall@5 / MRR, n = 44):

| Experiment | Variant | Recall@5 | MRR |
|---|---|---|---|
| E3 | dense | 0.705 | 0.600 |
| E3 | BM25 (kiwi morphemes) | 0.561 | 0.433 |
| E3 | BM25 (character bigrams) | 0.585 | 0.494 |
| E3 | hybrid (RRF) | 0.773 | 0.583 |
| E5 | hybrid + rerank | 0.795 | 0.678 |
| E5 | dense + rerank | 0.818 | 0.693 |
| **E9** | **hybrid + rerank + item names** | **0.841** | **0.730** |
| E9 | dense + rerank + item names | 0.818 | 0.713 |

![Retrieval on dev](figures/retrieval.png)

- **Hybrid beats dense before reranking** (E3: three cases better, none worse). BM25 alone is weak on English and Uzbek questions.
- **The reranker adds 0.02–0.11 Recall@5.** With the reranker, dense alone is about as good as hybrid: 0.818 vs 0.795, one case apart.
- **E9, item-name search, was added in Stage 3.** It came from the dev failure analysis: 9 of the 22 failed cases had a wrong or unusable Korean rewrite, such as 퍼플라이트 for a fluorescent tube or 참외 (Korean melon) for pineapple. The router's item name is matched against each chunk's short item name, not the whole chunk. For example, "pineapple peels" then finds 파인애플껍질 and "batteries" finds 전지. Together with reranking on the item name, Recall@5 rose from 0.795 to 0.841 with no case worse. With dense instead of hybrid it was 0.818 and one case worse, so BM25 stays.
- **These differences are 1–2 cases out of 44.** They are not statistically separable, and we do not claim they are. We chose by "no case worse" plus the full-system result (§8).

**Gate threshold (E5 τ sweep).** The gate abstains when the best rerank score among the 5 evidence chunks is below τ. On dev, every τ from 0.03 to 0.65 gives zero false positives. Only 2 item cases that should be refused reach the gate (0.029 and 0.032); the Phase 2 probes add one more at 0.039. We **kept τ = 0.15**. A τ just above 0.039 would answer 3 more cases (h31 at 0.051, item14 at 0.068, h23 at 0.084), but h23 would be answered from the wrong evidence (glass-bottle chunks for a PET-bottle question). A threshold 0.01 above the highest negative seen is not trustworthy with three negatives. This is a judgement call, and it is recorded here.

**Schedule lookup (E4).** @@E4@@

## 6. Generation contract, validation and handoff (Lessons 1, 4, 7)

**Generator.** qwen2.5:7b through Ollama, with temperature 0 and seed 7. Output is constrained to a JSON schema: status, bin, how_to_prepare, answer_text with `[n]` citations, citations and missing. The context is built under a token budget (8,192-token context, 768 reserved for the answer). The generator sees **item evidence only**: days, times and places are written by code from the table, in the user's language. In Phase 2 the LLM dropped and invented days in 7 of 19 schedule answers, and writing them in code fixed that. The LLM only translates the free-text method line, with its own prompt.

**Prompt versions (E1).** Only the prompt changes between these variants; retrieval, gate and validation stay the same (dev, n = 70, router repair off):

| Prompt | What it adds | Correct | False answers | Bin | Unsupported 종량제봉투 |
|---|---|---|---|---|---|
| v0 | minimal instruction | 32 | 2 | 8/45 | 4 |
| v1 | zero-shot contract (rules + JSON schema) | 48 | 4 | 24/45 | 3 |
| v2 | + three worked examples | 51 | 4 | 27/45 | 5 |
| v3 | + "no steps from the examples" | 49 | 5 | 25/45 | 7 |
| v4 | + a rule for wrong premises; schedule example replaced | 51 | 2 | 27/45 | 8 |
| **v5** | **v4 with the example bins balanced** | **54** | **3** | **30/45** | **2** |

- **The contract does most of the work.** v0 → v1 is +16 cases. Without the contract, v0 seldom names a bin (8/45). Its 2 false answers are low only because it rarely answers.
- **The examples leak their bins.** "Unsupported 종량제봉투" counts the answers that named the general waste bag although the case does not accept it. In v4 all three examples show 종량제봉투: the pen, the cushion of the false-premise example, and both distractors of the abstention example. The model then said 종량제봉투 against its evidence in 8 cases: metal cans, bubble wrap and spoiled food among them. v5 changes only the examples: the false-premise example became a metal kettle that goes with scrap metal (고철), and one distractor became iron tools (고철). Unsupported 종량제봉투 bins fell to 2, and v5 is worse than v2 on no case and better on three (h03, h37, h73). Validation had caught most of the v4 cases, as abstentions, so the gain is mostly in correct answers, not in false answers.
- **Every example item was checked against all 100 cases** (Korean, English, Russian, Chinese, Vietnamese and Uzbek words), so no case can be answered by copying an example.
- **Caveat.** v5 is the best of six prompts on the same 70 dev cases, so its dev score is optimistic. The test split (§8) is the check.

**Validation (enforce mode).** Any failed check turns an `ANSWER` into `INSUFFICIENT_CONTEXT` with a handoff. The checks are:
- **The bin is a known category** (18 canonical bins and their aliases, `rag/bins.py`).
- **The cited chunks state that bin.** These are their 2018 categories or their 2026 rule group; for chunks that state no bin, it is a text match.
- **The bin field agrees with the bins named in the text.**
- **The answer cites at least one chunk.**
- **No invented days or times.** An answer must not state days or clock times that its sources do not contain. Stage 3 extended this from schedule answers to item-only answers, after dev item10 copied "Tue, Thu, Sat 19:00–23:00" from a few-shot example into an answer about spoiled food.

Stage 3 also fixed two gaps in the bin checks. A 2026 sub-item that is itself a bin now decides: 종이팩 under 골판지 외 종이류. And an empty bin field is filled from Korean bin names in the text, such as 폐가전제품.

**Answer contract.** Every answer fits a typed contract (`rag/contract.py`, schema in `docs/answer_schema.json`) with rules between fields. For example, `CLARIFY` needs a question, and an abstention needs a handoff. All 49 Stage 1 probes and every evaluation answer satisfied it: **0 contract problems in @@N_ANSWERS@@ answers**.

**Handoff (Lesson 7, Klarna).** An abstention gives the user:
- the district office and its phone number;
- a Korean sentence to show the staff, written by code, never by the LLM;
- what the assistant checked.

The fixed texts are written in six languages (`rag/texts.py`). The zh, vi, uz and ru drafts have not been checked by a native speaker.

## 7. Evaluation method (Lesson 6)

**Cases.** There are 100 cases in 9 slices (`eval/cases/`, schema in `eval/cases.py`):
- 65 hand-written cases (tricky items, 2018/2026 conflicts, false premises, no evidence, ambiguous places, out of scope, combined item + schedule);
- 20 item cases from templates over the item dictionary;
- 15 schedule cases from templates over the table, one per district.

Gold chunk IDs and gold schedule rows come from scans of the data (`eval/label_helper.py`), never from the system's own output.

**Split.** The split is 70 dev / 30 test, stratified by slice, with seed 20261108. Its SHA-256 hashes were frozen in `split_manifest.json` (commit `375e7d2`) **before any tuning**. Twelve cases already seen during development were forced into dev. All tuning (E1–E9, τ, the Stage 3 fixes) used dev only. The test split was run **once**, with the configuration frozen at commit `@@FREEZE_COMMIT@@` (§8). A test report lists no per-case rows, so nobody could tune on it.

| Slice | Dev | Test | Expected behaviour |
|---|---|---|---|
| item_direct | 14 | 6 | answer |
| item_tricky | 11 | 5 | answer |
| conflict (2018 vs 2026) | 6 | 2 | answer with the 2026 rule |
| false_premise | 6 | 2 | answer, correcting the premise |
| combined (item + schedule) | 8 | 4 | answer both |
| schedule | 11 | 4 | answer |
| no_evidence | 7 | 3 | abstain |
| ambiguous_location | 4 | 2 | ask back |
| out_of_scope | 3 | 2 | refuse |
| real_users | 0 | 0 | **missing**: no real student questions were collected |

Languages: dev has en 25, ko 22, uz 7, zh 6, ru 6 and vi 4. Test has en 15, ko 8, vi 3, ru 2 and zh 2, and **no Uzbek case**, so Uzbek is measured on dev only.

**Metrics** (`eval/metrics.py`; undefined values are counted, not hidden):
- **Case correct.** For answer cases: `ANSWER`, the bin in the expected set, and a gold row shown where a schedule is expected. For the others: the expected behaviour.
- **False answer.** `ANSWER` when the case should not be answered, or `ANSWER` with a bin outside the expected set. This is the costly error.
- **Item withheld.** For a combined question, the item part can be refused while the schedule is still answered, with a sentence saying the item could not be confirmed. That is not correct, but it names no wrong bin, so it is counted on its own and not as a false answer. Until Stage 3 the code counted it as a false answer, contrary to the definition above. This was fixed before the test run, and every dev report was scored again from its saved traces (`python -m eval.run_eval --name <report> --rescore`). The baseline went from 21 to 13 false answers on dev, 8 of them withheld items.
- **Retrieval:** Recall@5, MRR, nDCG@5 and P@5 on the reranked order.
- **Gate:** TP/FP/FN/TN. **Schedule:** gold row found, and only gold rows shown.
- **Citations:** whether a gold chunk is cited, and citation precision.
- **Language:** whether the answer is in the asked language's script.
- **Latency per stage.**
- **Failure stage:** for every failed case, the earliest stage that went wrong, labelled by rule from its trace.

**LLM judge.** Ragas 0.4.3 measured faithfulness and context relevance, with **exaone3.5:7.8b** (LG AI Research, digest `c7c4e3d1ca22`) as the judge. The judge comes from a different model family than the generator, so the system does not grade its own answers. It still is a 7.8B model, so its scores need a human check (§9).

**Statistics.** With 30 test cases, every rate is shown as a count ("26/30"). One case is 3.3 points, so differences of one or two cases are noise. The template cases are not independent of each other.

## 8. Results (Lesson 5)

@@RESULTS@@

## 9. Failure analysis (Lesson 6)

@@FAILURES@@

## 10. Industry lens and maintenance (Lesson 7)

| Lens | Our application |
|---|---|
| Problem | Foreign residents can't read the Korean rules and don't know their district's schedule |
| Application | RAG over the national rules plus a deterministic lookup over district data, multilingual, with citations and a handoff |
| Pros | Available 24/7 in the user's language; national and local rules in one place; sources and data dates are visible |
| Cons | Stale district data (61% of rows over a year old); national guides can differ from local practice; a 7B model mistranslates rare item names and sometimes contradicts its evidence |
| Improvement | Prefer the newer source; show data dates; abstain below a threshold; hand off with a Korean sentence; validate every bin against the cited evidence |
| Measurement | Bin correctness and false answers on a frozen test set, by slice and language; faithfulness with a judge, to be checked by people. In deployment, the 👍/👎 feedback saved by `trace_id`, and repeat questions |

**Maintenance.** Every source has a hash and a date in `data/processed/manifest.json`. A change to the chunks changes the corpus hash, which forces a rebuild of the index: the pipeline will not run on a mismatch. The district table should be refreshed from data.go.kr every month, with stale rows flagged to the user in the meantime.

## 11. Limitations, risks, responsible use, future work

**What was not done (and must not be read into the numbers).**
- **No real users.** The `real_users` slice is empty: no real questions from international students were collected.
- **The cases were written by the system's developer** (with AI assistance), not by an independent person. The paraphrases in zh, vi, uz and ru were not checked by native speakers. A developer who also wrote the system tends to write questions the system can parse. So the test score is an optimistic estimate, even though the test split was never used for tuning.
- **No human audit yet.** The plan asks two people to label about 20 answers independently. The blank sheets are exported (`eval/reports/test-final/audit/`) and `python -m eval.audit agree` computes the agreement once they are filled. Until then, the judge's faithfulness scores are unchecked.
- **No native-speaker check** of the glossary, the day and label tables, or the fixed texts in zh, vi, uz and ru.

**Known weaknesses.**
- **Low-resource languages.** The 7B router mistranslates or garbles Uzbek and Russian item names: `기름occo散布的纸张` for frying oil, `투명 플라스틱 수저` (spoons) for PET bottles. The Uzbek answers it writes are often not fluent. The test split has no Uzbek case, so Uzbek is measured on dev only: see §8.
- **The model contradicts its own evidence.** Examples: pineapple peel into food waste, a thermometer into general waste although a 2026 rule says small electronics. Validation catches this when the bin it names is not the bin the cited chunk states. It cannot catch a wrong bin that a cited chunk supports, or wrong preparation steps.
- **Stale and incomplete district data.** 61% of the rows are over a year old (shown to the user), and 강동구 and 도봉구 have no rows.
- **Latency.** About @@LATENCY@@ s per question on an Apple M3 Pro with local models: the router about 7 s, the reranker about 3 s, the generator about 13 s. Too slow for a chat feel, but acceptable for a lookup.
- **Small test set.** With 30 test cases, one case is 3.3 points.

**Responsible use.** The page:
- says that the answers come from official guides that can differ from building or district practice;
- shows each source and its data date;
- marks old data;
- never shows a bin when it abstains.

Feedback is stored with a trace ID and an optional comment, and no personal data is asked for. The location is a district and neighbourhood, never a street address.

**Future work, in order of expected value:**
1. A reviewed table of Korean item names in the user languages, to replace LLM translation of item names. This needs native speakers.
2. A stronger or specialised model for Uzbek and Russian routing.
3. A check that a cited chunk is about the asked item, not just a chunk that states the bin.
4. Real-user questions as a new evaluation slice.
5. Caching the router and reranker for frequent items, to cut latency.
