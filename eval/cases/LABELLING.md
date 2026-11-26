# Labelling rubric for evaluation cases (v2)

Lesson 6: a relevance label needs an explicit unit and a rubric, and the labels come from the
data, never from the system being measured. This file is that rubric. Every v2 gold label is
checked against it by a second team member before the split is frozen.

## Unit

One chunk of `data/processed/item_chunks.jsonl`, by its legacy ID (`item2018_0285`,
`rule2026_019`, `guide2018_p12`, ...). A case lists chunks in two grades:

| Field | Grade | Meaning | Used by |
|---|---|---|---|
| `gold_legacy_ids` | required (2) | The chunk by itself tells the asker where this item goes or how to put it out | Recall@k, Hit@k, MRR, precision, nDCG |
| `supporting_legacy_ids` | supporting (1) | The chunk helps but does not answer alone | precision, nDCG |

Anything not listed is not relevant (0).

## Required: the chunk answers for this item

A chunk is **required** when a person reading only that chunk could answer the question:

- It names the item, or lists it as an example (`※ 해당품목: 가습기, 스캐너, ...`), **and**
- it states the bin or the way to put it out (`구분: 전용함`, `배출요령: ...`).

For one question there can be several required chunks, for example the 2018 dictionary
entry and the 2026 rule for the same item. Label all of them: a conflict case needs both
years, and recall is measured against both.

## Supporting: it helps, but is not enough

- A 2026 rule for the item's group that does not name the item (`소형 전기·전자제품` for a
  printer).
- The 2026 "integrated collection" rows that only say `따로 배출` / `상기 1호의 세부품목별
  배출요령에 따라 배출` (put out separately, follow the rules above).
- A guide page (`guide2018_pNN`) or FAQ that covers the item's material in general.
- A table or note that states a condition the answer needs (aluminium lining, food residue)
  without naming the item.

## Not relevant

- Same bin, different item (another plastic item for a shampoo bottle question).
- Same word, different thing (`형광등` lamps for a "fluorescent marker" question).
- A rule from the wrong scope (a business-waste rule for a household question).

## Cases that should not be answered

`no_evidence`, `out_of_scope`, `ambiguous_location` and abstaining `false_premise` cases have
no gold chunks: listing one would say the system should have answered.

## Bins

- `expected_bin`: every bin key (rag/bins.py) that is a correct value for the answer's main
  `bin` field. Several are allowed when the sources allow several.
- `expected_bins_all` (multi_item, vague_item): every bin the answer must name, one per item
  or per likely kind. Example: "a pizza box and the leftover pizza" → `["종이", "음식물"]`;
  "a bottle" → `["유리병", "플라스틱"]` (and `투명페트병` when a clear PET bottle is likely).

## Analogy cases (slice `analogy`)

For an item the guides do not list at all (not by name, not in an example list, not in a
group row such as "갑각류의 껍데기"), a case says whether a careful answer may reason from a
very similar listed item:

- `analogy: true`, expected `answer`: one or more listed items are similar in what decides
  the bin (soft fruit peel like orange and banana peel; a wooden kitchen utensil like wooden
  chopsticks), and no listed look-alike points to another bin. The **required** chunks are the
  similar items the answer should cite; the answer must say that the guides do not list the
  item itself.
- `analogy: false`, expected `abstain`: a look-alike trap. Cosine similarity finds a near
  item, but the bin depends on something it cannot see: hazard (medical, chemical, mercury),
  hardness (avocado skin, nut shells), or a material the guides never mention (silicone).

Search the corpus for the item and its synonyms before writing either kind
(`python -m eval.label_helper item <words>`): if a chunk covers it, it is not an analogy case.

## How candidates are found (pooling)

Labelling only from a keyword search missed relevant guide pages in v1 (`guide2018_p12` for
fluorescent tubes and batteries). For v2 the candidates for each case are the union of:

1. `python -m eval.label_helper item <words>`: every chunk whose name or text contains the
   item's Korean names, synonyms and material words;
2. the top 10 of several retrieval settings (dense, BM25, hybrid with rerank).

The labeller grades every candidate with this rubric. The pooled systems only propose
candidates; they never decide a label.

## Review

1. One person labels (`eval/cases/source/handwritten_v2.jsonl`).
2. A second person checks every label against this rubric and writes disagreements in the
   case's `notes`; the two agree on a final label.
3. A native speaker checks every zh, vi, uz and ru question for natural wording.
4. Only then is the split frozen (`python -m eval.make_cases --version v2`). A later label
   correction is a new version (Lesson 6), not an edit.
