"""Fixed text in six languages: every language says every sentence, with the same blanks."""
from __future__ import annotations

from rag.handoff import message
from rag.texts import LANGUAGES, TEXTS, placeholders, text


def test_every_language_has_every_sentence():
    assert set(TEXTS) == set(LANGUAGES)
    for lang, table in TEXTS.items():
        assert set(table) == set(TEXTS["en"]), (lang, set(TEXTS["en"]) ^ set(table))
        for key, template in table.items():
            assert template.strip(), (lang, key)
            assert placeholders(template) == placeholders(TEXTS["en"][key]), (lang, key)


def test_text_falls_back_to_english():
    assert text("CLARIFY", "ja") == TEXTS["en"]["CLARIFY"]
    assert text("CLARIFY", None) == TEXTS["en"]["CLARIFY"]
    assert text("contact_phone", "ko", office="성동구 청소과", phone="02-1234") == \
        "성동구 청소과(02-1234)에 문의하세요."
    assert message("NOT_A_STATUS", "en") == TEXTS["en"]["INSUFFICIENT_CONTEXT"]
    assert message("OUT_OF_SCOPE", "uz") == TEXTS["uz"]["OUT_OF_SCOPE"]
