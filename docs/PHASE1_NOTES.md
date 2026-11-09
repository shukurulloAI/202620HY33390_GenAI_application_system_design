# Phase 1 notes: baseline pipeline (2026-11-03)

These are developer observations from the probe set (`experiments/probes/probes.jsonl`, 12 questions). They are **not** evaluation results: the official numbers will come from Anar's dev/test set. The probe questions are too few and too hand-picked to support general claims.

## Setup

| Part | Setting |
|---|---|
| Corpus | `data/interim/parsed_item_chunks.jsonl`, 394 chunks (item 293, faq 36, guide 20, rule 42, note 3) |
| Embedding | `BAAI/bge-m3` @ `5617a9f6`, 1024-d, normalised, cosine |
| Index | Qdrant local, collection `items_bge-m3_5617a9f6_dac8d09c`; verification **PASS** (10/10 checks), see `data/reports/index/` |
| Retrieval | Dense only, k_retrieve = 20, k_final = 5 |
| Schedule | `rag/schedule_tool.py` on the raw CSV (10,187 rows) |
| Prompt | `answer_v1` (zero-shot contract, JSON schema enforced by Ollama) |
| Temperature / seed | 0 / 7 |
| Hardware | Apple M3 Pro, 36 GB; embeddings on MPS |

## 1. Index build (Lesson 3)
- Embedding 394 chunks took 9.8 s (model load 8.0 s, after a one-time download of ~2.3 GB).
- Chunk length: mean 98.5 tokens, max 730. No chunk exceeds the 8192-token limit.
- All checks passed: counts, unique IDs, IDs match chunks, repeat-run IDs, dimension, cosine, normalisation, payload provenance, reopen.

## 2. Token budget (Lesson 2)
- The budget is counted with the generator's own Hugging Face tokenizer before the request is sent.
- Estimated vs Ollama-measured prompt tokens: 2,298 vs 2,301 (3b) and 1,677 vs 1,681 (7b). The difference is the chat template.
- Budget: 8,192 context − 768 output reserve = 7,424 input tokens. Typical prompts use about 1.7–2.3k tokens.

## 3. Retrieval probes (dense only, bge-m3)

| Query | Top hits | Verdict |
|---|---|---|
| pizza box | 피자박스 (#1) | ✅ |
| used batteries | 충전식전지, 전지 (#1, #3) | ✅ |
| old mattress | 매트리스 (#1) | ✅ |
| fluorescent lamp | 2026 rule 조명제품 (#1), 형광등 (#2) | ✅ |
| expired medicine | FAQ 기타 (#1), 약 종류 (#2) | ✅ |
| clear PET bottle | guide p10, 2026 PET rules (#2, #3) | ✅ |
| chicken bones (EN / KO / ZH) | food-waste guide p17/p18 in top 3 | ✅ (rule is inside the guide page) |
| **chicken bones (Uzbek)** | 신발 (shoes), 신발장 … | ❌ cross-lingual retrieval fails for Uzbek |
| **styrofoam box from delivery** | 치킨박스, 피자박스 … | ❌ 스티로폼/발포합성 item not in top 5 |

So the router (§4.3) should help: translating the item to Korean before search. BM25 alone cannot fix English queries.

## 4. Generator comparison on the probe set (manual review)

| Probe | qwen2.5:3b | qwen2.5:7b |
|---|---|---|
| p01 pizza box | ❌ "general waste bag" (evidence: 종이) | ✅ paper; oily part → 종량제봉투 |
| p02 chicken bones (EN) | ❌ answers about *fish* bones | ✅ general-waste bag (+ unsupported "put in a plastic bag first") |
| p03 chicken bones (KO) | ❌ "it is food waste" (evidence: NOT food waste) | ✅ |
| p04 chicken bones (UZ) | ❌ garbled Uzbek, food-waste steps | ⚠️ correct bin, broken Uzbek |
| p05 egg shells | ✅ | ⚠️ right conclusion, wrong bin name (찌꺼기) |
| p06 batteries | ✅ | ✅ |
| p07 mattress | ✅ | ✅ |
| p08 clear PET | ✅ | ✅ |
| p09 medicine | ✅ | ✅ |
| p10 scrap a car (out of scope) | ❌ answers | ❌ answers |
| p11 food-waste days, 성동구 행당동 | ✅ Mon/Wed/Fri 20:00–24:00 | ✅ |
| p12 Gangdong-gu (no data) | ✅ abstains | ✅ abstains |
| **Correct** | **7/12** | **9/12 + 2 partial** |
| JSON valid | 12/12 | 12/12 |
| Mean / max generation time | 4.4 s / 6.0 s | 10.5 s / 19.0 s |

The keyword checker in `run_probes.py` reported 8/12 and 11/12. It counted p04 (3b) and p04/p05 (7b) as passes, which human review rejected. This is the Lesson 6 point that an automatic evaluator needs a human audit.

**Decision:** default generator changed to `qwen2.5:7b` (`rag/config.py`). `qwen2.5:3b` stays as the course baseline for comparison.

## 5. Failure types seen (Lesson 6: earliest failed stage)

| Failure | Stage | Planned fix (Phase 2–3) |
|---|---|---|
| 3b contradicts the evidence it cites (pizza box, bones) | Generation | Bigger model (done); few-shot prompt (E1); output validation against cited chunk categories (§4.9) |
| Uzbek query retrieves unrelated items | Retrieval | Router translates the item to Korean (§4.3) |
| Styrofoam not retrieved | Retrieval | Router + BM25 hybrid (E3) |
| Out-of-scope question answered (car) | Gate | Router `out_of_scope` + evidence gate (§4.6, E5) |
| `bin` field inconsistent ("", "종량제봉투 (종량제봉투)", "찌꺼기") | Generation contract | Take the bin from the cited chunk's `categories`, not from free text (§4.9) |
| Poor Uzbek output even with the right bin | Generation | Test a stronger model, or answer in English + Korean for low-resource languages (open decision) |

## Raw results
- `experiments/results/probes/probes_qwen2.5-3b_v1_*.json`
- `experiments/results/probes/probes_qwen2.5-7b_v1_*.json`
