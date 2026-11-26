# Phase 2 notes: full system on clean data (2026-11-04/06)

These are developer observations from the probe set (`experiments/probes/probes.jsonl`, 22 questions, 13 with gold chunks). They are **not** evaluation results. The official numbers will come from Anar's dev/test set. The probes are few and hand-picked, and they were also used to tune the system (τ, validation rules), so they cannot show that it generalises.

## Setup

| Part | Setting |
|---|---|
| Corpus | `data/processed/item_chunks.jsonl`, 403 chunks (item 293, faq 36, guide 20, rule 42, note 3, table 9), UUIDv5 IDs |
| Index | Qdrant local, `items_bge-m3_5617a9f6_c7d19676` (E2 also `items_bge-small-en_5c38ec7c_c7d19676`); both verified PASS |
| Schedule | `data/processed/schedule.csv` (10,187 rows, cleaned) through the typed tool, no LLM. E4's vector variants use `schedule_bge-m3_5617a9f6_7386a17d` (verified PASS) |
| Router | `qwen2.5:7b`, `router_v1`, JSON schema + invariant checks |
| Retrieval | Dense (bge-m3) + BM25 (kiwi) -> RRF (k = 60) -> top 20 -> `bge-reranker-v2-m3` @ `953dc6f6`, best score of original and rewrite -> top 5 |
| Gate | Rerank score ≥ τ = 0.15 (provisional); schedule OK / CLARIFY / NO_DATA; an area with more than 4 rows on different days asks or hands off (§10); out of scope refused |
| Generator | `qwen2.5:7b`, `answer_v2` (few-shot), JSON schema, temperature 0, seed 7; item answers only |
| Schedule text | Written by code (`rag/schedule_text.py`); the LLM only translates the method line, `schedule_method_v1` (§10) |
| Validation | `enforce`: a failed check turns the answer into an abstention |
| Baseline | Phase 1 system: dense only, no router, rerank or gate, `answer_v1`, no validation (`config.BASELINE`) |
| Hardware | Apple M3 Pro, 36 GB |

Code state, all with `git_dirty` false (current commit IDs; the run files store the IDs from before 2026-11-09, see [COMMIT_IDS.md](COMMIT_IDS.md)):
- **`e8bc797`:** E2, E3, E5 and the τ sweep (§3, §4). The retrieval code and item corpus have not changed since.
- **`09179b4`:** E4 and the full-system probes, v2 and v3.
- **`369c4e8`:** the baseline (same code as `3f51463`). `09179b4` only changes schedule text, which the baseline writes with the LLM, so it was not re-run.

Against `e8bc797`, full-system answers changed only on p11 and p14 (now written by code) and p16 (§2). Baseline answers did not change. The first runs used an uncommitted tree, and the re-run reproduced their retrieval numbers, τ and gate counts exactly. The old-vs-clean table in §1, the rerank-query paragraph in §3 and all of §8 are older runs, and they say so.

## 1. Data fixes (Phase 0 tasks, done before these runs; still to be reviewed)

Phase 2 first ran on the raw data, which was the wrong order. Comparing the same config (v2, τ = 0.045, enforce) on old and clean data shows the cost:

| | Old data (`probes_full-qwen7b`) | Clean data (`probes_default-clean`) |
|---|---|---|
| Keyword pass | 18/22 | 21/22 |
| p03 chicken bones (KO) | ❌ food waste | ✅ 종량제봉투 |
| p05 egg shells | abstains | ✅ 종량제봉투 |
| p16 chicken bones (ZH) | ❌ food waste | ✅ 종량제봉투 |

Food-waste rules are in tables on guide p.17–18, and PDF extraction lost the layout. No retrieval or prompt change could fix this; the model was reading scrambled text. It took a hand transcription.

| Problem | Fix | Numbers |
|---|---|---|
| Tables on p.17–18 lost their layout | 9 hand-transcribed `table` chunks with page provenance; added search words are labelled | 9 chunks; needs a check against the PDF |
| IDs depended on parse order | UUIDv5 of source, chunker, span and text digest; old ID kept as `legacy_id` | Repeat builds give identical IDs |
| Number lists in area names (`휘경1,2동`, `상계6.7동`, `청학1·2동`, `수성1,2.3,4가동`) | `clean_areas` expands them with any separator and moves notes out | No unexpanded lists or stemless names left in 10,187 rows |
| Exact area name lost to the base-name match | The exact name now wins; the official `상계6·7동` spelling also resolves | 상계6동: 3 wrong zones -> 1 |
| Same names in several places | Province kept; ambiguous names ask | 7 district names, 228 of 6,070 area names |
| Romanised place names | `district_aliases.json` | 1,723 aliases |
| Bad district names | 남양주 -> 남양주시, 동두천 -> 동두천시, 없음 -> 세종시 | 15 rows |
| Placeholder areas (`없음`, `해당없음`) read as a place | Now mean the whole district | 486 rows; `없음` is gone from the neighbourhood list |
| Old data | Flagged and shown to the user | 6,234 rows (61%) older than 1 year on 2026-11-06; median age 843 days |
| Seoul 도봉구, 강동구 missing | Explicit "no data" | Still no schedules for them |

The `.`/`·`/`ㆍ` number lists were found late, by comparing against the fix in `notebooks/schedule_eda/` (`90ca8b9`, 2026-11-03), which handles them. Before that fix, 주례2동, 청학2동, 양정1동 and 수성2가동 were "not found" and returned every zone in the district. No probe covered them, so the probe scores could not have shown it.

Full numbers: `data/reports/data_quality.md`.

## 2. Probe results: full system vs Phase 1 baseline (manual review)

| Probe | Baseline | Full system (v2) |
|---|---|---|
| p01 pizza box | ❌ bin 종이, text says general waste bag | ✅ paper |
| p02 chicken bones (EN) | ✅ | ⚠️ right bin, invented "emptied, punctured" (§5) |
| p03 chicken bones (KO) | ✅ | ✅ |
| p04 chicken bones (UZ) | ⚠️ right bin, broken Uzbek | ❌ abstains (§7); safe, but no help |
| p05 egg shells | ✅ | ✅ |
| p06 batteries | ⚠️ right place, no bin | ✅ |
| p07 mattress | ✅ | ✅ |
| p08 clear PET | ❌ bin 플라스틱 (2018 rule; 2026 is separate) | ✅ 투명페트병 |
| p09 expired medicine | ✅ | ✅ |
| p10 scrap a car (out of scope) | ❌ answers | ✅ refused |
| p11 food-waste days | ❌ right days, says 종량제봉투 | ✅ |
| p12 Gangdong-gu (no data) | ✅ abstains | ✅ abstains |
| p13 styrofoam | ⚠️ "appropriate recycling bin" | ❌ abstains: model said 종량제봉투, evidence says 발포합성수지 (§6) |
| p14 Seongdong, tonight | ❌ "yes", no time or date check | ✅ tool date check, 20:00–24:00 |
| p15 pizza box, negation | ✅ | ⚠️ right bin, invented "puncture the cardboard" (§5) |
| p16 chicken bones (ZH) | ✅ | ⚠️ right bin, invented "poke holes in the bag" (§5) |
| p17 visa | ✅ abstains | ✅ refused |
| p18 recycling, no location | ❌ abstains, does not ask | ✅ asks |
| p19 중구 (5 districts) | ❌ answers for an unknown 중구 | ✅ asks which one |
| p20 batteries (RU) | ❌ "throw away with the phone" | ✅ 전용함; the Russian is awkward |
| p21 nail polish (not in sources) | ❌ invents a rule | ✅ abstains |
| p22 dead hamster (not in sources) | ✅ abstains | ✅ abstains |
| **Correct / partial / wrong** | **10 / 3 / 9** | **17 / 3 / 2** |
| Keyword checker | 16/22 | 20/22 |
| Median latency | 10.7 s | 19.0 s |

- **The two ❌ of the full system are abstentions, not wrong bins.** It showed no wrong bin on any probe. The baseline showed several.
- **The keyword checker misled us again.** It gave the baseline 16/22 where review found 10. It also gave the previous full-system run 21/22 while p13 displayed a bin (플라스틱) that contradicted its own text (종량제봉투). Fixing that lowered the score to 20/22, and the system got better. This is the Lesson 6 point about auditing automatic evaluators.
- **p16 got worse through my own fix.** The router calls it a "both" question, so it now gets the item-only wording that stops invented schedules (§10). Nothing else in its input changed, but that wording was enough to bring the §5 leak into the answer. The bin is still right. It is the only probe on that path.
- **Latency nearly doubled.** Median per stage: generator 13.6 s, router 6.8 s, reranker 3.4 s, retrieval 0.1 s. The router and reranker are the added cost. Schedule-only answers skip the generator and took 3–10 s (p11 5.9 s, p14 9.7 s).
- p14 depends on the run date. Tonight was Friday 2026-11-06 in the re-run and Wednesday 2026-11-04 in the first run. Both are collection days and both answers were right, but on a Tuesday the correct answer is no.

## 3. Retrieval experiments (probes only; Recall@5 and MRR over the 13 gold probes)

**E2, embedding model** (dense, no rerank)

| Variant | Recall@5 | MRR |
|---|---|---|
| bge-small-en, original question | 0.000 | 0.013 |
| bge-small-en, Korean rewrite | 0.231 | 0.118 |
| **bge-m3, original question** | **1.000** | **0.846** |

An English-only embedding cannot search Korean text, and a Korean rewrite does not rescue it. This was the clearest result of the phase.

**E3, lexical vs dense vs hybrid** (bge-m3, original + rewrite, no rerank)

| Variant | Recall@5 | MRR |
|---|---|---|
| **Dense** | **1.000** | **0.885** |
| BM25 (kiwi morphemes) | 0.462 | 0.398 |
| BM25 (character bigrams) | 0.615 | 0.496 |
| Hybrid RRF | 0.923 | 0.703 |

**On these probes hybrid is worse than dense alone.** The plan expected the opposite. Most probes are not in Korean, so BM25 only has the rewrite to work with, and RRF gives its weak lists the same weight as dense. That explanation is likely but not proven. Bigrams beat kiwi morphemes, which may reflect the broken spacing in the 2026 text. Anar's Korean-exact-term cases are where BM25 should help, so this needs a dev-set answer.

**E5, reranker, 2×2** (bge-m3)

| Retrieval | Rerank | Recall@5 | MRR | Mean time to retrieval |
|---|---|---|---|---|
| Hybrid | off | 0.923 | 0.703 | 3.8 s |
| Hybrid | on | 1.000 | 0.846 | 5.6 s |
| Dense | off | 1.000 | 0.885 | 3.5 s |
| Dense | on | 1.000 | 0.885 | 5.5 s |

Reranking repairs hybrid but adds nothing to dense order on these probes: dense keeps 0.885, and only p15 and p20 swap ranks. The two rerank rows differ by one probe (p13: rank 1 vs 2), so 0.885 vs 0.846 is no evidence that either is better. The reranker's clearer value here is the gate: dense gives no calibrated score to threshold, and the gate scores are almost the same under both (§4).

**Decision: keep hybrid + rerank as the default for now.** It is not the best row, so this needs justifying. Every probe with gold is a simple item question, mostly not in Korean, which is the case where dense is strongest. BM25 should matter for exact Korean terms, and the probes barely test that. If dev shows no gain, drop BM25: dense + rerank is simpler and just as fast.

**Rerank query.** Reranking only against the rewrite let one mistranslation sink a correct chunk: "mattress" became 고기저귀 and 매트리스 fell to rank 19 (MRR 0.799, 12/13, old data). Scoring both queries and keeping the best fixed it (0.846, 13/13, against 0.821 for original only). It is the default.

## 4. Gate threshold (provisional)

`tau_sweep.py` on the hybrid + rerank traces, 15 probes with item retrieval:

```
p22=0.001-  p04=0.006+  p21=0.039-  p07=0.264+  p15=0.580+ ...  (+ should answer, - should abstain)
```

- τ = 0.15 is the middle of the gap between 0.039 and 0.264. Any value in that gap gives the same counts: TP 12, FP 0, FN 1 (p04), TN 2.
- **Only 2 negatives**, so "FP rate 0" means very little. The real choice needs dev.
- p04 sits below p21, so no τ separates the classes perfectly. That is a language problem, not a threshold problem (§7).
- The sweep's first tie-break picked 0.58, which also refuses p07 and gains nothing. It now takes the lowest FP, then the lowest FN, then the middle of the tied interval.

## 5. Prompt: few-shot leakage (v2 vs v3)

p02 said chicken bones should be "emptied, punctured" and p15 said to "puncture the cardboard". No evidence chunk for p02 mentions emptying or puncturing, and none for p15 mentions puncturing. The only source is `answer_v2`'s abstention example, which showed a spray-can chunk with "내용물을 완전히 비운 후 구멍을 뚫어 배출". That example text was not a real chunk either: `item2018_0131` only points to the 금속캔 method. **The example meant to teach "do not guess" became content for unrelated answers.**

`answer_v3` replaces that evidence with two real, step-free chunks (고무장갑, 보온병) and adds a rule on `how_to_prepare`. Result on all 22 probes:

| | v2 | v3 |
|---|---|---|
| Keyword pass | 20/22 | 18/22 |
| p02, p15 invented steps | yes | **gone** |
| p06 batteries | ✅ 전용함 | ❌ model said 종량제봉투; validation now abstains (§6) |
| p14 Seongdong, tonight | ✅ | ✅ since `3f51463`: schedule text no longer comes from this prompt. At `e8bc797` v3 said "general waste bag (종량제봉투)" here |
| p20 batteries (RU) | ✅ 전용함 | ❌ 금속캔 (not caught) |

**Decision: v2 stays the default for now.** v2's errors are unsupported extra steps. v3's are worse: a wrong bin for batteries, which is a fire risk (p20 still reaches the user; p06 is now stopped). This choice now only affects item answers. But v3 changed two things at once, and with 22 probes a two-probe swing may be chance: small prompt edits changed which chunks qwen cites. E1 on dev should compare both, ideally with the two v3 changes separated. The leak in v2 is still a known defect, so "v2 is better" is not the conclusion here.

## 6. Validation changes

p13 and v3's p06 found two holes in the bin checks:

| Case | What happened | New rule |
|---|---|---|
| p13 | Empty bin filled from evidence (플라스틱) while the text said 종량제봉투; the user would see both | Bin field must match the bins named in the text. An empty bin is filled from the text first |
| p13 | 2026 table files styrofoam under 합성 수지류, so the evidence looked like 플라스틱 | The sub-item decides: 스티로폼 -> 발포합성수지 |
| v3 p06 | Bin 종량제봉투 "supported" because the word appears on a cited guide page, in an unrelated sentence | If cited chunks state bins, the bin must be one of them. Text matching is only the fallback when they state none |
| "Both" question, no schedule data (§10) | Generator copied days from a few-shot example | `schedule_invented`: days or clock times with no schedule rows fail validation |

With these, p13 abstains. That counts as a failed probe, and it is the right outcome: the model contradicted its evidence and the system refused to show it. 39 deterministic tests pass (`python -m pytest`).

**What validation still cannot catch:**
- v3's p20: the model cited a 금속캔 rule for batteries. The bin matches the cited chunk; the citation is wrong. This needs a check that the cited chunk is about the asked item.
- `how_to_prepare` and step text are not checked at all, so the §5 leak passes.
- A translated method line is checked for numbers and script, not meaning (§10), so s14's "regular-sized bag" passes. Days, times and places are safe because code writes them.
- Bins are read from parentheses in `answer_text`, so a Korean answer with no parentheses gets no text check.

## 7. Router findings

| Probe | Rewrite | Used? | Effect |
|---|---|---|---|
| p04 (UZ) | 닭骨头汤 닭 뼈물기 분리배출 방법 | No, mixed script | Abstains, see below |
| p05 | 계란 скор대 음식물쓰레기로 분리배출 가능嘛？ | No, mixed script | Fine; original question works |
| p07 | 고기저귀 처리 방법 ("meat diaper") | **Yes** | Rescued by rerank max; lowest positive score (0.264) |
| p13 | 배달 용 스테로폼 상자 분리배출 방법 (misspelt) | Yes | Fine |
| p20 (RU) | 바attery(번역 필요) 오래된 배터리 분리배출 방법 | **Yes** | Fine, but this should not have passed |
| p21 | 네일 pol리스 병 ... | **Yes** | Fine |

- **Garbled rewrites are the safe kind.** The script check rejects p04 and p05. A **fluent wrong rewrite (p07) passes every invariant**, because nothing compares its meaning with the question. Only the reranker's second query saved it.
- **`is_korean` is too lenient.** p20 literally contains "(번역 필요)" ("translation needed") and p21 mixes Latin letters. Both were used.
- **p04 is the most useful failure.** Retrieval is right (gold at rank 1), yet its rerank score is only 0.006, so the gate abstains. The reranker orders the chunks correctly, but its absolute score for the Uzbek question is far below what English or Korean get. So on this probe the gate penalises the language, not the evidence. One probe proves little, but if dev shows the same pattern it is a fairness gap for a target language. A safe abstention is acceptable for now, not a solution.

Possible fixes, none tried: a glossary lookup before the router (needs Uzbek item words; `glossary.json` has none for bones today), a stronger translation model, or a gate that accepts high dense agreement when the rewrite failed.

## 8. EXAONE 3.5 7.8B (not adopted)

Run on **old data and index** (`dac8d09c`), so the chicken-bone failures below mix model and data effects. It was not repeated on clean data.

| | qwen2.5:7b both | EXAONE router + qwen generator | EXAONE both |
|---|---|---|---|
| Keyword pass | 18/22 | 19/22 | 17/22 |
| Hit@5 | 13/13 | 12/13 | 12/13 |
| MRR | 0.846 | 0.723 | 0.723 |
| Median latency | 17.9 s | 16.2 s | 23.5 s |

The deciding failure does not depend on the data. EXAONE rewrote the Uzbek chicken-bone question as 유리병 분리배출 방법 ("glass bottle disposal"): fluent Korean, wrong item, so it passes every check. With EXAONE generating too, the user was told to put chicken bones in the glass bottle bin. qwen's Uzbek rewrite was garbage, and that made it detectable. The keyword score favoured the EXAONE router by one probe, but it lost retrieval quality. This is not a general verdict on EXAONE; a re-run on clean data would be fair if time allows.

## 9. Failures still open (Lesson 6: earliest failed stage)

| Failure | Stage | Next step |
|---|---|---|
| Uzbek (and likely other low-resource languages) abstains despite correct retrieval | Router / gate | §7 fixes; measure per language on dev |
| Fluent wrong rewrite passes all checks | Router | Back-translation or item-in-evidence check; test on dev |
| `is_korean` accepts mixed text | Router | Stricter ratio; reject "번역" markers |
| Model contradicts its evidence (p13) | Generation | Caught, not fixed; a stronger model or E1 |
| Few-shot leakage / invented steps | Generation, validation | E1 v2 vs v3; check `how_to_prepare` against cited chunks |
| Wrong citation with a matching bin (v3 p20) | Validation | Check the cited chunk's item against the question |
| Method text can be mistranslated, and only script is checked (s14; §10 table) | Translation | Native review of a table of the most common strings |
| Vietnamese, Russian and Uzbek readers get the "How" line in English | Translation | Same table, then remove them from `METHOD_LANGUAGE` |
| `clarify.question` is English only (s21, s26) | Gate | Write it in code, per language |
| Hybrid not better than dense | Retrieval | E3/E5 on dev, with Korean exact-term cases; drop BM25 if there is no gain |
| Only 2 negatives for τ | Gate | E5 on dev |
| Latency about 19 s | System | Measure per stage; try a smaller router model |

Fixed since the first E4 run: text dropping days or zones, the gate answering from 4 rows, invented schedules and the wrong router day (§10).

Not run yet: E1, E6, E7 and E8. E4 has run on probes only (§10). All wait for Anar's dev set or for planned work.

## 10. E4: how to retrieve schedules (27 schedule probes)

`experiments/probes/probes_schedule.jsonl` holds 27 hand-written probes in 6 languages. 20 should answer (10 with a neighbourhood, 6 with only a district, 3 with the place only in the question, 1 in a place with many collection points on the same days), 4 should ask, and 3 should abstain (강동구 and 도봉구 have no data; 고흥군 도덕면 differs by collection point). Gold rows come from a scan of the table, checked against the raw area text, not from the lookup. Every variant gets the location in its query text and shows at most 4 rows. s25–s27 were added after the gate defect below was found, so they are regression checks, not blind tests.

Run at `09179b4`, `git_dirty` false.

| Variant | Expected behaviour (/27) | Cases showing a wrong place (/27) | Right row shown (/20) | Top row right (/20) | Only right rows (/20) | Top row day/time right (/20) | Median time (s) |
|---|---|---|---|---|---|---|---|
| **Structured lookup** | **27** | **0** | **20** | **20** | **20** | **20** | **6.8** |
| Vector, no filter | 20 | 18 | 19 | 16 | 2 | 18 | 8.1 |
| Postfilter (top 20) | 22 | 2 | 20 | 18 | 11 | 20 | 7.5 |
| Prefilter | 22 | 2 | 20 | 18 | 9 | 20 | 7.5 |

Time is the median over the 20 answerable cases, which all four variants answered.

- **Vector alone is unsafe.** It answered all 27, including both no-data districts. A 강동구 resident got collection days from 울산 북구, 부산 강서구 and 서울 강북구. For 성동구 without a neighbourhood, all four rows came from 성북구.
- **Day/time match cannot separate the filters from the lookup.** All three score 20/20, although both filters put the wrong row first on s05 and s09: the zones happen to share a schedule. This is the near-duplicate finding (#6). Top row and wrong place are the columns that separate them.
- **The filters' five misses are not retrieval misses.** On s17, s21, s22, s25 and s26 they have no rule to ask back or hand off. s21 and s22 show a 중구 and a 고성군 the user never chose, which is why each filter has 2 wrong-place cases. With the lookup's rules they would pass, and the gap left would be row order inside a district.
- **No candidate starvation here, but that is weak evidence.** s27 reaches 정선군 (2,203 rows) and both filters found a right row, but every 정선읍 row has the same days. Postfilter's 11 against prefilter's 9 on "only right rows" comes from finding fewer rows, not from being better.
- **"Only right rows" is harsh on purpose.** The vector variants always take 4 rows, even for a one-zone place. Taking 1 would match the top-row column, but would break multi-zone districts (s15, s16).

**Decision: keep the structured lookup.** It needs no index, and its search takes 1 ms against about 80–130 ms. Prefilter is the only alternative worth keeping, and only with the lookup's ask-back rules, which is what the plan's "prefilter + structured lookup" means.

**How far to trust 20/20: not far.** The probes are hand-picked, s02–s06 come from parser bugs I had just fixed, and s25–s27 were written for the defect they test. An earlier version of this table also scored 19/19 while reading the answers found real errors. Those two defects are below, and both are now fixed.

### Defects these scores did not show

**1. Right row, wrong text.** The columns above stop at the rows. Reading each answer against its row:

| | First run (19 answers) | Now (20 answers) |
|---|---|---|
| Correct | 12 | 19 |
| Partial | 4 | 1 |
| Wrong | 3 | 0 |

In the first run s11 and s18 said "general waste bag" for food waste, s15 gave one of 성동구's two zones, s02 and s16 dropped Sunday, s19 dropped Wednesday, and s07 named no days at all. `schedule_days_ok` passed all 19.

Fix: `rag/schedule_text.py` writes the days, times, places and zones in code, in the user's language. The generator now sees item evidence only. The LLM's one job is to translate the free-text `method` field, with its own prompt (`schedule_method_v1`) that has no worked examples, so nothing can leak as in §5. Schedule-only answers skip the generator, so the median fell from 16.1 s to 6.8 s.

The one partial is s14: "regular-sized bag" for 규격봉투, which loses the fact that it is a pay-as-you-throw bag.

**2. The gate answered from 4 of many rows.** In rural districts a row is one collection point, not one zone. 고흥군 도덕면 has 287 points across Monday to Friday; the 4 rows shown all said Monday, and 223 of the 287 have another day. When an area has more than `MAX_ZONES` rows and their days differ, the gate now behaves as follows:

| Area | Behaviour | Example | Names affected |
|---|---|---|---|
| Several names under a base name | Asks which one | 오빈리 → 오빈1리, 오빈2리, 오빈3리 (s26) | 39 |
| One name | Abstains and gives the office phone | 도덕면, 287 points (s25) | 89 |
| Same days in every row | Still answers | 정선읍 (s27) | 100 |

Handing off rather than asking is deliberate: the alternative is a question with 287 options.

**Two older bugs found while testing the fix, neither shown by any score:**
- A "both" question with no schedule data got days copied from a few-shot example. The generator is now told to answer about the item only, and a new `schedule_invented` check fails any answer that states days or clock times with no schedule rows.
- The router turned 화요일 (Tuesday) into Wednesday. A day named in the question now comes from code. The trial also turned 수요일 into Thursday, so a method text that names days is never sent to the LLM (28 of 811 strings, 73 of 40,748 fields) and stays in Korean.

### Method translation

The first version only rejected a line that lost a number or contained the wrong script. Reading the E4 answers found that this was not enough: two of the three Vietnamese lines in E4 were romanised Korean (`acjeoekkeul keutjian jeogjeo geuda hamyeon ...`), and s04 showed one to the user. A check that a line contains the language's own letters catches this, but a Vietnamese line with accents can still be nonsense.

So I read the 50 most common method texts that name no days, in four languages. They cover 88.6% of the 40,748 method fields. This is my reading, **not a native check**:

| Language | Failed the checks | Passed, but wrong | Examples | Decision |
|---|---|---|---|---|
| English | 1/50 | 5/49 | 고흥 as "Gogung"; 계근 (weighing) as "compacting" | Used |
| Chinese | 4/50 | 5/46 | 마대 (sack) as 桶; a county name | Used; needs review |
| Vietnamese | 2/50 | 6/48 | "under 5 tons" as "over 5 tons"; nonsense lines; "sluts" in two lines; a made-up county | **Sent to English** |
| Russian | 13/50 | 8/37 | плотный (thick) for платный (paid) bag; "sort by item" as "re-use not required" | **Sent to English** |
| Uzbek | not measured here | | '일반주택' as 'Oliy xonalar' in the earlier trial | **Sent to English** |

The English and Chinese error rates look close to Vietnamese, but the errors are not the same kind: mostly misspelt names against reversed facts and nonsense. This was a judgement call. `METHOD_LANGUAGE` in `rag/schedule_text.py` reverses it in one line.

A line that fails stays in Korean after trying English. **The cost:** a Vietnamese, Russian or Uzbek reader gets the days, times and labels in their language but the "How" line in English. The better fix is a table of reviewed translations: 50 strings would cover about 89% of fields, but it needs native speakers. This only covers schedule text. Item answers in these languages are still written by qwen, and §2's p20 and §7 show its limits there.

### Still open

- **`clarify.question` is in English only.** A Korean user sees English on s21 and s26, and other languages will too. The options are in Korean.
- **Places stay in Korean** (`집앞`, `대문앞`), exactly as the source has them.
- **Item failure in a mixed answer.** A statement that the item part failed appears only in `missing`, so the website has to show it.
- **`no_collection_days` is no longer in `answer_text`.** It is still in `zones[].no_collection`.
- **The source can contradict itself.** s10's row lists Sunday and not Friday, but its method says clear PET goes out on Friday (금). The answer shows both, as the data does.
- Day-name and label tables for zh, vi, uz and ru were written during development and need a native check, like the glossary.

**For the website:** `answer_text` now has several lines, so the page must keep line breaks. `handoff`, `office_phone` and `clarify.options` (up to 30) all need a place on the page.

**For Anar:** the plan samples the `schedule` slice from CSV rows, which will reach the rural districts. 정선군 and 고흥군 alone are about a third of the table, so decide whether to sample by row or by district. Both are worth reporting.

## Raw results

Probe runs are in `experiments/results/probes/` and experiments in `experiments/results/<id>/`. Paths and commands recorded inside these files are as they were at the time of the run; the repository was restructured afterwards (PLAN.md §9).

- Full system at `09179b4`: `probes_fixed-default_20261106-233850.json` (v2), `probes_fixed-v3_20261106-234447.json` (v3)
- Baseline at `369c4e8`: `probes_final-baseline_20261106-221155.json`
- Before the translation change, at `369c4e8`: `probes_final-default_20261106-220752.json`, `probes_final-v3_20261106-221809.json`
- At `e8bc797`: `probes_committed-default_20261106-142243.json`, `probes_committed-v3_20261106-143252.json`, `probes_committed-baseline_20261106-142636.json`
- First runs, uncommitted tree: `probes_default-final_20261104-232118.json`, `probes_default-v3_20261104-233910.json`, `probes_default-clean_20261104-203516.json` (before the last validation changes), `probes_baseline-clean_20261104-203908.json`
- Old data, for comparison: `probes_full-qwen7b_*.json`, `probes_router-exaone_*.json`, `probes_all-exaone_*.json`, `probes_rq-*.json`
- Experiments: `E2/`, `E3/`, `E5/` at `e8bc797`, `E4/` at `09179b4` (traces per case + `manifest.json`)
