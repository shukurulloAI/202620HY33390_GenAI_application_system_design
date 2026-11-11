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
    keys = {"st-key-topbar", "st-key-examples", "st-key-question_panel", "st-key-answer_panel",
            "st-key-bin_card"}
    assert set(re.findall(r"\.(st-[\w-]+)", css)) <= keys
