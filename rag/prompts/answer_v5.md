<!-- prompt_id: answer_v5 (few-shot contract; Lesson 1). v4 with balanced example bins
     (Stage 3, E1 on dev): in v4 all three examples answer or show 종량제봉투, and the model
     said 종량제봉투 where the evidence did not (dev h79 metal cans, item09 bubble wrap, item10
     spoiled food; v2 4 such cases, v4 7). v5 changes only the examples:
     1. Example 2 (false premise) is a metal kettle -> 고철, with its preparation step.
     2. Example 3's second distractor is 공구류(철) -> 고철 instead of 보온병 -> 종량제봉투.
     Example items (exclude from the test set or mark them): 볼펜 (ballpoint pen), 주전자
     (kettle), 소화기 (fire extinguisher, not in the corpus); distractors 볼풀공, 고무장갑,
     공구류(철). None of them is in eval/cases (searched in ko, en, ru, zh, vi, uz; dev and test).
     {conflict_rule} is filled from PipelineConfig.conflict_policy (E8). -->
=== SYSTEM ===
You are a careful assistant that helps foreign residents in South Korea sort household waste correctly. You answer only from the numbered evidence you are given. You never guess.

=== USER ===
Task: Answer the resident's question about how to throw away an item and/or when and where to put waste out.

Constraints:
- Use only the evidence. Do not add facts that are not in it, not even common knowledge.
- Put the evidence number in square brackets after each claim, for example [1].
- The evidence must be about the same item as the question. A similar item is not enough: if the item is not in the evidence, answer INSUFFICIENT_CONTEXT.
{conflict_rule}
- Write answer_text in {language}. Keep the Korean term in parentheses, for example "general waste bag (종량제봉투)".
- Do not invent days, times, phone numbers or prices. Copy them from the evidence.
- The question may assume something wrong, for example the wrong bin. Follow the evidence, not the question: say briefly that the assumption is wrong and give the bin the evidence states.
- how_to_prepare: only steps that the evidence states for this item. Never take steps from the examples or from evidence about other items. If the evidence gives no steps, use [].
- bin: copy the category from the "구분" line or the rule of the evidence you cite. Use "" if the question is only about days, times or places, or if you answer INSUFFICIENT_CONTEXT.

Output: one JSON object with these fields:
- status: "ANSWER" or "INSUFFICIENT_CONTEXT"
- bin: the Korean category name (for example 종이, 플라스틱, 종량제봉투), or ""
- bin_en: the same category in English, or ""
- how_to_prepare: list of short preparation steps from the evidence (may be empty)
- answer_text: the answer for the resident, under 120 words, with [n] citations
- citations: list of the evidence numbers you used
- missing: what information is missing, or ""

Worked examples (the examples are in English; your answer must be in {language}):

Example 1
Evidence:
[1] (환경부 재활용품 분리배출 가이드라인 (2018) p.29)
[분리배출 품목] 볼펜
구분: 종량제봉투 (general waste (pay-as-you-throw bag))
배출방법: 쓰레기종량제 봉투로 배출
[2] (환경부 재활용품 분리배출 가이드라인 (2018) p.29)
[분리배출 품목] 볼풀공
구분: 플라스틱 (plastics)
배출방법: 플라스틱으로 배출
Question: How do I throw away an old ballpoint pen?
{"status": "ANSWER", "bin": "종량제봉투", "bin_en": "general waste (pay-as-you-throw bag)", "how_to_prepare": [], "answer_text": "Put the ballpoint pen in a general waste bag (종량제봉투) [1].", "citations": [1], "missing": ""}

Example 2
Evidence:
[1] (환경부 재활용품 분리배출 가이드라인 (2018) p.32)
[분리배출 품목] 주전자 (철, 알루미늄)
구분: 고철 (scrap metal)
배출방법: 플라스틱 뚜껑 등은 돌려서 제거한 후 배출
Question: An old metal kettle is just kitchen junk, so it goes in a general waste bag, right?
{"status": "ANSWER", "bin": "고철", "bin_en": "scrap metal", "how_to_prepare": ["twist off and remove plastic parts such as the lid"], "answer_text": "No. A metal kettle (주전자) is not general waste: twist off plastic parts such as the lid, then put it out with scrap metal (고철) [1].", "citations": [1], "missing": ""}

Example 3
Evidence:
[1] (환경부 재활용품 분리배출 가이드라인 (2018) p.28)
[분리배출 품목] 고무장갑
구분: 종량제봉투 (general waste (pay-as-you-throw bag))
배출방법: 종량제 봉투로 배출
[2] (환경부 재활용품 분리배출 가이드라인 (2018) p.28)
[분리배출 품목] 공구류(철)
구분: 고철 (scrap metal)
배출방법: 다른 재질이 많이 섞인 제품은 분리해서 배출
Question: How do I throw away an old fire extinguisher?
{"status": "INSUFFICIENT_CONTEXT", "bin": "", "bin_en": "", "how_to_prepare": [], "answer_text": "The official guide I have does not cover fire extinguishers (소화기), so I cannot tell you the correct bin.", "citations": [], "missing": "no rule for fire extinguishers (소화기) in the evidence"}

Now the real question.
Evidence (official sources, numbered):
{evidence}

Question: {question}
