"""Cross-platform font resolver for comic rendering.

Bundled OFL/Apache-licensed fonts live in app/data/fonts/. This module
provides a single resolver that checks bundled fonts first, then falls
back to platform fonts (Windows), then to PIL's default bitmap font.
"""

from __future__ import annotations

import os
from typing import List, Optional

from PIL import ImageFont


FONTS_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "data",
    "fonts",
)

_STYLE_FONT_MAP = {
    "manga": {
        "display": ["Oswald-Bold.ttf", "Bangers.ttf"],
        "body": ["C:/Windows/Fonts/comicbd.ttf", "C:/Windows/Fonts/seguisb.ttf", "NotoSans.ttf"],
    },
    "pixar": {
        "display": ["Fredoka-Bold.ttf", "Bangers.ttf"],
        "body": ["Fredoka-Bold.ttf", "C:/Windows/Fonts/comicbd.ttf", "Quicksand-Bold.ttf", "NotoSans.ttf"],
    },
    "superhero": {
        "display": ["Bangers.ttf", "Oswald-Bold.ttf"],
        "body": ["C:/Windows/Fonts/comicbd.ttf", "C:/Windows/Fonts/trebucbd.ttf", "Fredoka-Bold.ttf", "C:/Windows/Fonts/seguisb.ttf", "NotoSans.ttf"],
    },
}

_PLATFORM_FALLBACKS = [
    "C:/Windows/Fonts/comicbd.ttf",
    "C:/Windows/Fonts/comic.ttf",
    "C:/Windows/Fonts/trebucbd.ttf",
    "C:/Windows/Fonts/seguisb.ttf",
    "C:/Windows/Fonts/arialbd.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/System/Library/Fonts/Helvetica.ttc",
]


def _bundled_path(name: str) -> Optional[str]:
    p = os.path.join(FONTS_DIR, name)
    return p if os.path.isfile(p) else None


def style_font_candidates(style_id: str, role: str = "body") -> List[str]:
    """Return ordered font file paths for a style+role, bundled first."""
    out: List[str] = []
    style_map = _STYLE_FONT_MAP.get(style_id, {})
    for name in style_map.get(role, []):
        if os.path.isabs(name) and os.path.exists(name):
            out.append(name)
        else:
            p = _bundled_path(name)
            if p:
                out.append(p)
    out.extend(_PLATFORM_FALLBACKS)
    return out


def resolve_story_fonts(
    style_id: str,
    story_text: str = "",
    role: str = "body",
) -> List[str]:
    """Dynamically determine the best fonts based on style AND the story's mood/theme.

    Body fonts for speech bubbles and narration captions MUST be clean, open,
    and 100% legible (never unreadable display fonts like Bangers).
    """
    text_lower = (story_text or "").lower()

    if role == "display":
        if any(k in text_lower for k in ["fun", "laugh", "joke", "silly", "party", "candy", "play"]):
            return [_bundled_path("Fredoka-Bold.ttf"), _bundled_path("Bangers.ttf"), "C:/Windows/Fonts/comicbd.ttf"]
        return [_bundled_path("Bangers.ttf"), _bundled_path("Oswald-Bold.ttf"), "C:/Windows/Fonts/impact.ttf"]

    # Body fonts: speech bubbles & caption boxes
    out: List[str] = []
    body_priorities = [
        "C:/Windows/Fonts/comicbd.ttf",
        _bundled_path("Fredoka-Bold.ttf"),
        "C:/Windows/Fonts/trebucbd.ttf",
        "C:/Windows/Fonts/seguisb.ttf",
        _bundled_path("Quicksand-Bold.ttf"),
        _bundled_path("NotoSans.ttf"),
    ]
    for p in body_priorities:
        if p and os.path.exists(p) and p not in out:
            out.append(p)

    for p in style_font_candidates(style_id, role):
        if p not in out:
            out.append(p)

    return out


def load_font(
    size: int,
    candidates: Optional[List[str]] = None,
) -> ImageFont.FreeTypeFont:
    """Load a TrueType font at `size`, trying candidates then platform fallbacks.

    Candidates may be full paths or bare filenames (e.g. "comicbd.ttf")
    which are resolved against bundled FONTS_DIR and C:/Windows/Fonts.
    """
    search: List[str] = []
    for c in candidates or []:
        if not c:
            continue
        if os.path.isabs(c) or "/" in c or "\\" in c:
            if os.path.exists(c):
                search.append(c)
        else:
            bundled = os.path.join(FONTS_DIR, c)
            win = os.path.join("C:/Windows/Fonts", c)
            if os.path.isfile(bundled):
                search.append(bundled)
            elif os.path.isfile(win):
                search.append(win)

    search.extend(_PLATFORM_FALLBACKS)
    noto = _bundled_path("NotoSans.ttf")
    if noto and noto not in search:
        search.append(noto)

    for fp in search:
        if fp and os.path.exists(fp):
            try:
                return ImageFont.truetype(fp, size)
            except Exception:
                continue
    return ImageFont.load_default()
