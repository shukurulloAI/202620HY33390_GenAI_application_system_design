"""
Page state and the rules behind it, as plain functions the tests can call without a browser.

Session keys (st.session_state):
    lang              page and answer language (one of service.languages())
    question_input    the question box
    area_province, area_district, area_dong    the area pickers (None = not selected)
    pending           a request waiting to be answered on this run, or None
    request, result   the last question asked and its answer
    feedback          trace_id -> rating already given
    flash             a page-label key to show once under the button (e.g. empty question)
"""
from __future__ import annotations

from collections.abc import MutableMapping

DEFAULT_PROVINCE = "서울특별시"          # most of the district data is Seoul's
DEFAULTS = {"pending": None, "request": None, "result": None, "flash": None,
            "area_district": None, "area_dong": None}


def init(session: MutableMapping, tree: dict) -> None:
    """Fill in what this session does not have yet (never overwrites a choice)."""
    for key, value in DEFAULTS.items():
        session.setdefault(key, value)
    session.setdefault("feedback", {})
    session.setdefault("area_province", DEFAULT_PROVINCE if DEFAULT_PROVINCE in tree else None)


def pick_lang(query: str | None, locale: str | None, offered) -> str:
    """The language to start in: ?lang= in the link, else the browser's language, else
    English. 'ru-RU', 'uz_Latn_UZ' and 'zh-Hans-CN' count as ru, uz and zh."""
    for candidate in (query, locale):
        code = (candidate or "").replace("_", "-").split("-")[0].lower()
        if code in offered:
            return code
    return "en"


def location_tree(locations: list[dict]) -> dict[str, list[dict]]:
    """province -> [{district, label, areas}], from service.locations()."""
    tree: dict[str, list[dict]] = {}
    for loc in locations:
        areas = sorted({a for z in loc["zones"] for a in z["areas"]})
        tree.setdefault(loc["province"], []).append(
            {"district": loc["district"], "label": f"{loc['district_en']} ({loc['district']})",
             "has_data": loc["has_data"], "areas": areas})
    return tree


def area_request(tree: dict[str, list[dict]], province: str | None, district: str | None,
                 dong: str | None) -> dict:
    """The area to send with a question. A district that is not in the province, or a
    neighbourhood that is not in the district, is dropped rather than sent: a mismatched pair
    finds no data and the user would get an abstention for a question we can answer."""
    entry = next((d for d in tree.get(province or "", []) if d["district"] == district), None)
    if entry is None:
        return {"province": None, "district": None, "dong": None}
    return {"province": province, "district": district,
            "dong": dong if dong in entry["areas"] else None}
