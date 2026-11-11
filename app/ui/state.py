"""
Page state and the rules behind it, as plain functions the tests can call without a browser.
"""
from __future__ import annotations

NOT_SELECTED = "Not selected"


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
