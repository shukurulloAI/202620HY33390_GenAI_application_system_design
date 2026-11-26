<!-- prompt_id: answer_v0 (E1 baseline: question + evidence, no contract). Same output schema as v1/v2, so only the instructions differ. -->
=== SYSTEM ===
You are a helpful assistant.

=== USER ===
Context:
{evidence}

Question: {question}

Answer in {language}. Return JSON with the fields status, bin, bin_en, how_to_prepare, answer_text, citations, missing.
