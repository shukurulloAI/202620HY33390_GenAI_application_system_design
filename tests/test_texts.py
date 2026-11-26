"""Fixed text in six languages: every language says every sentence, with the same blanks."""
from __future__ import annotations

import inspect
from typing import get_args

from rag import paths
from rag.contract import Status
from rag.handoff import message
from rag.schedule_tool import WASTE_TYPES
from rag.texts import LANGUAGES, PAGE, TEXTS, page_text, placeholders, text


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


def test_every_page_label_exists_in_every_language():
    assert set(PAGE) == set(LANGUAGES)
    for lang, table in PAGE.items():
        assert set(table) == set(PAGE["en"]), (lang, set(PAGE["en"]) ^ set(table))
        for key, template in table.items():
            assert template.strip(), (lang, key)
            assert placeholders(template) == placeholders(PAGE["en"][key]), (lang, key)
    assert page_text("zone_where", "ja", place="X") == "Where: X"


def test_the_page_has_a_label_for_every_stage_and_waste_type():
    import re

    from rag import pipeline, service
    emitted = set(re.findall(r'emit\("(\w+)"\)', inspect.getsource(pipeline.Pipeline.run)))
    assert emitted == set(pipeline.STAGES)
    assert set(service.STAGES) == {"queued", "loading", *pipeline.STAGES}
    assert set(service.OFFLINE_STAGES) <= set(service.STAGES)
    assert all(f"stage_{s}" in PAGE["en"] for s in service.STAGES)
    assert all(f"waste_{w}" in PAGE["en"] for w in WASTE_TYPES)
    assert all(f"title_{s}" in PAGE["en"] for s in get_args(Status))


def test_every_label_the_page_asks_for_exists():
    import re
    used = set()
    for path in (paths.ROOT / "app").rglob("*.py"):
        used |= set(re.findall(r'\bt\("(\w+)"', path.read_text(encoding="utf-8")))
    assert used and used <= set(PAGE["en"]), used - set(PAGE["en"])
