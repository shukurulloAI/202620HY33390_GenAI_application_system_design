<!-- prompt_id: answer_v2 (few-shot contract; Lesson 1). Same rules as v1 plus three worked examples:
     a supported item answer, a schedule answer, an abstention.
     Example items (exclude from the test set or mark them): 볼펜 (ballpoint pen), 소화기 (fire extinguisher, not in the corpus).
     The schedule example uses a made-up district (예시구), so it cannot leak real data.
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
[1] (District data, 예시도 예시구, 관리번호 0000, data date 2025-03-01)
[District schedule] 예시도 예시구 - zone 1권역
Areas: 가나동, 다라동
Where: 문전수거 / 집 앞
Food waste (음식물쓰레기): days Tue, Thu, Sat; time 19:00-23:00; method: 전용용기에 담아 배출
Office: 예시구청 청소과 02-000-0000
Question: When can I put out food waste? I live in 가나동.
{"status": "ANSWER", "bin": "", "bin_en": "", "how_to_prepare": ["put it in the food waste container (전용용기)"], "answer_text": "In 가나동 (zone 1권역), put food waste (음식물쓰레기) in front of your house on Tue, Thu and Sat between 19:00 and 23:00, in the food waste container (전용용기) [1].", "citations": [1], "missing": ""}

Example 3
Evidence:
[1] (환경부 재활용품 분리배출 가이드라인 (2018) p.30)
[분리배출 품목] 스프레이, 부탄가스
구분: 금속캔 (metal cans)
배출방법: 내용물을 완전히 비운 후 구멍을 뚫어 배출
[2] (환경부 재활용품 분리배출 가이드라인 (2018) p.33)
[분리배출 품목] 헬멧
구분: 종량제봉투 (general waste (pay-as-you-throw bag))
Question: How do I throw away an old fire extinguisher?
{"status": "INSUFFICIENT_CONTEXT", "bin": "", "bin_en": "", "how_to_prepare": [], "answer_text": "The official guide I have does not cover fire extinguishers (소화기), so I cannot tell you the correct bin.", "citations": [], "missing": "no rule for fire extinguishers (소화기) in the evidence"}

Now the real question.
Evidence (official sources, numbered):
{evidence}

Question: {question}
