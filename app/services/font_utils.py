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
        "display": ["Oswald-Bold.ttf", "Oswald.ttf", "Bangers.ttf"],
        "body": ["Oswald.ttf", "NotoSans.ttf"],
    },
    "pixar": {
        "display": ["Fredoka-Bold.ttf", "Fredoka.ttf", "Quicksand-Bold.ttf"],
        "body": ["Fredoka.ttf", "Quicksand.ttf", "NotoSans.ttf"],
    },
    "superhero": {
        "display": ["Bangers.ttf", "Oswald-Bold.ttf"],
        "body": ["Oswald-Bold.ttf", "Oswald.ttf", "NotoSans.ttf"],
    },
}

_PLATFORM_FALLBACKS = [
    "C:/Windows/Fonts/seguisb.ttf",
    "C:/Windows/Fonts/arialbd.ttf",
    "C:/Windows/Fonts/trebucbd.ttf",
    "C:/Windows/Fonts/segoeui.ttf",
    "C:/Windows/Fonts/comicbd.ttf",
    "C:/Windows/Fonts/comic.ttf",
    "C:/Windows/Fonts/impact.ttf",
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
        p = _bundled_path(name)
        if p:
            out.append(p)
    for name in style_map.get("display", []):
        p = _bundled_path(name)
        if p and p not in out:
            out.append(p)
    out.extend(_PLATFORM_FALLBACKS)
    return out


def load_font(
    size: int,
    candidates: Optional[List[str]] = None,
) -> ImageFont.FreeTypeFont:
    """Load a TrueType font at `size`, trying candidates then platform fallbacks.

    Candidates may be full paths or bare filenames (e.g. "Bangers.ttf")
    which are resolved against the bundled FONTS_DIR.
    """
    search: List[str] = []
    for c in candidates or []:
        if not c:
            continue
        if os.path.isabs(c) or "/" in c or "\\" in c:
            search.append(c)
        else:
            bundled = os.path.join(FONTS_DIR, c)
            if os.path.isfile(bundled):
                search.append(bundled)
    noto = _bundled_path("NotoSans.ttf")
    if noto:
        search.append(noto)
    search.extend(_PLATFORM_FALLBACKS)
    for fp in search:
        if fp and os.path.exists(fp):
            try:
                return ImageFont.truetype(fp, size)
            except Exception:
                continue
    return ImageFont.load_default()
