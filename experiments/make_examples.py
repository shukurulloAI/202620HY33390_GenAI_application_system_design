"""
Record real answers for the website's offline mode and for docs (docs/answer_examples.json).

    python -m experiments.make_examples            # needs Ollama and the index (~3 min)

One question per situation the page has to show: every status, a two-part answer, a partial
answer, a clarify question with options, and every language. The answers are produced by the
full system at the current commit, not written by hand, so they show what the page will
really receive. Run it again after a contract change (rag/contract.py).
"""
from __future__ import annotations

import json
from datetime import datetime

from eval.provenance import snapshot
from rag import service
from rag.contract import CONTRACT_VERSION, check
from rag.pipeline import Pipeline

EXAMPLES = [
    ("item-en", "Where do I throw away a pizza box?", "en", None, None),
    ("schedule-en", "When can I put out food waste?", "en", "성동구", "행당1동"),
    ("both-en", "Where do PET bottles go, and when is recycling collected?", "en", "성동구",
     "행당1동"),
    ("item-ko", "닭뼈는 음식물쓰레기인가요?", "ko", None, None),
    ("item-zh", "用过的电池应该怎么扔？", "zh", None, None),
    ("schedule-vi", "Khi nào tôi có thể đổ rác thực phẩm?", "vi", "성동구", "행당1동"),
    ("item-uz", "Plastik shishalarni qayerga tashlayman?", "uz", None, None),
    ("item-ru", "Куда выбрасывать стеклянные бутылки?", "ru", None, None),
    ("partial-schedule-missing", "Where does a pizza box go, and when is paper collected?",
     "en", "강동구", None),
    ("clarify-no-district", "When can I put out recycling?", "en", None, None),
    ("clarify-province", "When is general waste collected in Jung-gu?", "en", None, None),
    ("abstain", "How do I dispose of a dead hamster?", "en", None, None),
    ("out-of-scope", "Can you recommend a good restaurant near Hanyang University?", "en",
     None, None),
]


def main() -> None:
    provenance = snapshot()
    pipeline = Pipeline(write_traces=False)
    out = []
    for name, question, lang, district, dong in EXAMPLES:
        answer = check(pipeline.answer(question, lang=lang, district=district, dong=dong))
        out.append({"name": name, "question": question, "lang": lang, "district": district,
                    "dong": dong, "answer": answer})
        print(f"{name:26} {answer['status']}")
    service.EXAMPLES_FILE.write_text(json.dumps(
        {"about": "Real answers from the full system, for the website's offline mode "
                  "(RAG_OFFLINE=1) and docs/WEBSITE.md. Regenerate with "
                  "python -m experiments.make_examples.",
         "contract_version": CONTRACT_VERSION, **provenance,
         "generated": datetime.now().isoformat(timespec="seconds"),
         "examples": out}, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"-> {service.EXAMPLES_FILE}")


if __name__ == "__main__":
    main()
