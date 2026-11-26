"""
Page state and the rules behind it, as plain functions the tests can call without a browser.

Session keys (st.session_state):
    lang              page and answer language (one of service.languages())
    question_input    the question box
    area_province, area_district, area_dong    the area pickers (None = not selected)
    pending           a request waiting to be answered on this run, or None
    request, result   the last question asked and its answer
    feedback          trace_id -> rating already given
    asked             times of this session's recent questions (the rate limit)
    visitor           this session's id, when the visitor's address is not known
    flash             (page-label key, arguments) to show once under the button
"""
from __future__ import annotations

import ipaddress
import threading
import uuid
from collections.abc import Mapping, MutableMapping

DEFAULT_PROVINCE = "서울특별시"          # most of the district data is Seoul's
# One local LLM answers one question at a time (about 20 s), so one visitor sending many
# questions makes everyone else wait. 8 in 5 minutes is more than a person asks by hand.
RATE_LIMIT = 8
RATE_WINDOW_S = 300
# On a public link, one person can open many tabs: a second limit counts per visitor (IP
# address), across tabs. Higher than per tab, since a class on one Wi-Fi shares an address.
VISITOR_LIMIT = 20
DEFAULTS = {"pending": None, "request": None, "result": None, "flash": None,
            "area_district": None, "area_dong": None}


def init(session: MutableMapping, tree: dict) -> None:
    """Fill in what this session does not have yet (never overwrites a choice)."""
    for key, value in DEFAULTS.items():
        session.setdefault(key, value)
    session.setdefault("feedback", {})
    session.setdefault("asked", [])
    session.setdefault("visitor", str(uuid.uuid4()))
    session.setdefault("area_province", DEFAULT_PROVINCE if DEFAULT_PROVINCE in tree else None)


def allow_question(asked: list[float], now: float) -> bool:
    """The per-session rate limit: forget questions older than the window, then allow this
    one (and count it) only if fewer than RATE_LIMIT remain."""
    asked[:] = [t for t in asked if now - t < RATE_WINDOW_S]
    if len(asked) >= RATE_LIMIT:
        return False
    asked.append(now)
    return True


def rate_message_args(n: int | None = None) -> dict:
    return {"n": n or RATE_LIMIT, "minutes": RATE_WINDOW_S // 60}


class VisitorLog:
    """Recent question times per visitor, shared by every session of this server process
    (the page keeps one with st.cache_resource)."""

    def __init__(self) -> None:
        self._times: dict[str, list[float]] = {}
        self._lock = threading.Lock()

    def allow(self, visitor: str, now: float) -> bool:
        with self._lock:
            for key in [k for k, times in self._times.items()        # memory stays small
                        if not times or now - times[-1] >= RATE_WINDOW_S]:
                del self._times[key]
            times = self._times.setdefault(visitor, [])
            times[:] = [t for t in times if now - t < RATE_WINDOW_S]
            if len(times) >= VISITOR_LIMIT:
                return False
            times.append(now)
            return True


def visitor_id(ip: str | None, headers: Mapping[str, str] | None, session_visitor: str) -> str:
    """Who is asking, for the per-visitor limit: the visitor's public IP address, else this
    browser session (then only the per-tab limit counts).

    Through the public link (deploy/public_link.sh: Tailscale Funnel or a Cloudflare tunnel)
    `ip` is the visitor's: Streamlit's server reads X-Forwarded-For only from this machine and
    takes the last address, the one Tailscale or Cloudflare put there, so a visitor cannot
    choose it (checked through real links: Tailscale replaces a visitor's X-Forwarded-For,
    Cloudflare adds its entry after it). Any other
    address is not one visitor: behind Docker every visitor comes from the gateway (so the
    limit would hold for everyone together), and a server on all interfaces sees this machine
    as ::ffff:127.0.0.1 (Streamlit gives None only for 127.0.0.1 and ::1). A connection from
    this machine may carry Cloudflare's CF-Connecting-IP header instead."""
    for candidate in (ip, (headers or {}).get("CF-Connecting-IP")):
        if public_ip(candidate):
            return candidate.strip()
    return session_visitor


def public_ip(text: str | None) -> bool:
    """A global internet address: not loopback, private, link-local or carrier NAT."""
    try:
        address = ipaddress.ip_address((text or "").strip())
    except ValueError:
        return False
    address = getattr(address, "ipv4_mapped", None) or address
    return address.is_global


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


def dong_prompt(district: dict | None) -> str:
    """The page label for the neighbourhood box with nothing chosen: "Choose a district
    first", "Not needed: the answer covers the whole district" (a district with data but no
    neighbourhoods), else "Not selected"."""
    if district is None:
        return "dong_pick_district"
    if district["has_data"] and not district["areas"]:
        return "dong_whole_district"
    return "not_selected"


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
