"""The website's colours meet WCAG 2.2 AA contrast in light and dark mode, and its CSS uses
no Streamlit internals (the rendered page is also scanned with axe-core: tests/e2e/)."""
from __future__ import annotations

import re
import tomllib

import pytest

from rag import paths

CONFIG = paths.ROOT / ".streamlit" / "config.toml"
STYLE = paths.ROOT / "app" / "ui" / "style.css"
TEXT, LARGE_OR_UI = 4.5, 3.0          # AA: normal text; large text and interface parts
CAPTION_ALPHA = 0.6                   # captions and help text are body text at 60 % opacity


def channels(hex_colour: str) -> list[int]:
    h = hex_colour.lstrip("#")
    return [int(h[i:i + 2], 16) for i in (0, 2, 4)]


def luminance(hex_colour: str) -> float:
    def linear(c: int) -> float:
        c = c / 255
        return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4
    r, g, b = (linear(c) for c in channels(hex_colour))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast(a: str, b: str) -> float:
    high, low = sorted((luminance(a), luminance(b)), reverse=True)
    return (high + 0.05) / (low + 0.05)


def blend(fg: str, bg: str, alpha: float) -> str:
    return "#" + "".join(f"{round(alpha * f + (1 - alpha) * b):02x}"
                         for f, b in zip(channels(fg), channels(bg), strict=True))


def test_contrast_helpers_match_known_values():
    assert contrast("#000000", "#ffffff") == pytest.approx(21.0)
    assert contrast("#767676", "#ffffff") == pytest.approx(4.54, abs=0.01)   # the AA grey


@pytest.mark.parametrize("mode", ["light", "dark"])
def test_theme_colours_meet_aa(mode):
    theme = tomllib.loads(CONFIG.read_text(encoding="utf-8"))["theme"][mode]
    text, bg, bg2 = theme["textColor"], theme["backgroundColor"], theme["secondaryBackgroundColor"]
    assert contrast(text, bg) >= TEXT
    assert contrast(text, bg2) >= TEXT                              # inputs, code boxes
    assert contrast(blend(text, bg, CAPTION_ALPHA), bg) >= TEXT     # captions
    assert contrast(blend(text, bg2, CAPTION_ALPHA), bg2) >= TEXT
    assert contrast(theme["linkColor"], bg) >= TEXT
    assert contrast("#ffffff", theme["primaryColor"]) >= TEXT       # primary button label
    assert contrast(theme["primaryColor"], bg) >= LARGE_OR_UI       # focus ring, accents
    assert contrast(theme["borderColor"], bg) > 1.2                 # visible card edges


def css_tokens() -> tuple[dict, dict, dict]:
    """The custom properties of style.css: colours, translucent colours, percentages."""
    css = STYLE.read_text(encoding="utf-8")
    hexes = dict(re.findall(r"--([\w-]+):\s*(#[0-9a-fA-F]{6})", css))
    translucent = {name: ("#" + "".join(f"{int(c):02x}" for c in (r, g, b)), int(a) / 100)
                   for name, r, g, b, a in re.findall(
                       r"--([\w-]+):\s*rgb\((\d+) (\d+) (\d+) / (\d+)%\)", css)}
    shares = {name: int(v) / 100 for name, v in re.findall(r"--([\w-]+):\s*(\d+)%;", css)}
    return hexes, translucent, shares


@pytest.mark.parametrize("mode", ["light", "dark"])
def test_page_colours_meet_aa_on_every_surface(mode):
    """The tiles and secondary text are translucent, so their colour depends on the theme:
    compose them as the browser does and check every text on every surface."""
    theme = tomllib.loads(CONFIG.read_text(encoding="utf-8"))["theme"][mode]
    hexes, translucent, shares = css_tokens()
    text, bg, link = theme["textColor"], theme["backgroundColor"], theme["linkColor"]
    assert hexes["accent"] == theme["primaryColor"]                 # one blue on the page
    tile = blend(translucent["tile"][0], bg, translucent["tile"][1])
    bin_card = blend(translucent["bin-tint"][0], tile, translucent["bin-tint"][1])
    for surface, colour in (("page", bg), ("tile", tile), ("bin card", bin_card)):
        assert contrast(text, colour) >= TEXT, surface
        assert contrast(blend(text, colour, CAPTION_ALPHA), colour) >= TEXT, surface
        assert contrast(blend(text, colour, shares["muted"]), colour) >= TEXT, surface
        assert contrast(link, colour) >= TEXT, surface
    eyebrow = blend(hexes["accent"], text, shares["accent-text"])  # blue text over the headline
    assert contrast(eyebrow, bg) >= TEXT


def test_css_uses_no_streamlit_internals():
    css = re.sub(r"/\*.*?\*/", "", STYLE.read_text(encoding="utf-8"), flags=re.S)
    assert "!important" not in css
    assert "data-testid" not in css and "baseweb" not in css
    assert "color-scheme" not in css          # colours follow the theme, not the system
    keys = {"st-key-page", "st-key-topbar", "st-key-examples", "st-key-workspace",
            "st-key-ask_side", "st-key-answer_side", "st-key-question_panel",
            "st-key-answer_panel", "st-key-answer_placeholder", "st-key-bin_card"}
    assert set(re.findall(r"\.(st-[\w-]+)", css)) <= keys


def test_the_bin_signs_light_ends_before_the_text():
    """No text may sit on the light: a caption on even a 20 % blue light misses 4.5:1. The
    light reaches its inset plus its blur beyond the sign; the text starts a medium gap
    (2rem) away (app/ui/components.py show_bin)."""
    css = re.sub(r"/\*.*?\*/", "", STYLE.read_text(encoding="utf-8"), flags=re.S)
    light = re.search(r"\.bin-sign::before\s*\{([^}]*)\}", css).group(1)
    reach = (int(re.search(r"inset:\s*-(\d+)px", light).group(1))
             + int(re.search(r"blur\((\d+)px\)", light).group(1)))
    font = tomllib.loads(CONFIG.read_text(encoding="utf-8"))["theme"]["baseFontSize"]
    assert reach < 2 * font                                         # 26 px < 34 px
    components = (paths.ROOT / "app" / "ui" / "components.py").read_text(encoding="utf-8")
    assert re.search(r'key="bin_card".*?gap="medium"', components, flags=re.S)
    assert "bin-tint" in css and "st-key-bin_card::before" not in css   # no light on the card


def used_icons() -> set[str]:
    sources = [*(paths.ROOT / "app").rglob("*.py"), paths.ROOT / "rag" / "texts.py"]
    return {name for path in sources
            for name in re.findall(r":material/([a-z0-9_]+):", path.read_text(encoding="utf-8"))}


def test_every_icon_is_a_material_symbol_streamlit_knows():
    """One icon set on the whole page; a name Streamlit does not know fails at runtime."""
    from streamlit.string_util import validate_material_icon
    assert len(used_icons()) > 10
    for name in used_icons():
        validate_material_icon(f":material/{name}:")              # raises for an unknown name
    from rag.texts import PAGE
    for lang, labels in PAGE.items():
        for key in ("ex1_icon", "ex2_icon", "ex3_icon"):
            assert re.fullmatch(r":material/[a-z0-9_]+:", labels[key]), (lang, key)


def test_the_app_icon_is_one_svg_drawing():
    import xml.etree.ElementTree as ET

    from app.ui import components
    favicon = ET.fromstring(components.favicon_svg())               # well-formed, no download
    assert favicon.tag.endswith("svg") and favicon.get("viewBox") == "0 0 64 64"
    inline = ET.fromstring(components.icon_svg())
    assert inline.get("aria-hidden") == "true"                     # decoration, not content
    assert components.GRADIENT == tuple(css_tokens()[0][k] for k in ("icon-from", "icon-to"))
