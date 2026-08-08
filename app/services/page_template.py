"""Full-page comic template renderer.

Composes a single comic book page from:
- a layout config (loaded from app/data/comic_layouts/{style}_{layout}.json)
- 1..6 panel images (already with bubble/caption/border baked in by text_render_service)
- header / footer / optional page number

The page background, screentone/halftone pattern, panel placement, and chrome
are all driven by the layout config so different visual styles look distinct.
"""

from __future__ import annotations

import json
import os
from typing import Any, Dict, List, Optional, Tuple

from PIL import Image, ImageDraw, ImageFont

from app.services.font_utils import load_font as _resolve_font


LAYOUTS_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "data",
    "comic_layouts",
)


def _parse_color(
    value: Any, default: Tuple[int, int, int] = (250, 247, 238)
) -> Tuple[int, int, int]:
    if not isinstance(value, str):
        return default
    v = value.strip()
    if v.startswith("#") and len(v) == 7:
        try:
            return (int(v[1:3], 16), int(v[3:5], 16), int(v[5:7], 16))
        except ValueError:
            return default
    return default


def _load_font(size: int) -> ImageFont.FreeTypeFont:
    return _resolve_font(size)


def _draw_text_with_stroke(
    draw: ImageDraw.ImageDraw,
    xy: Tuple[int, int],
    text: str,
    font: ImageFont.ImageFont,
    fill: Tuple[int, int, int] | Tuple[int, int, int, int],
    stroke_fill: Optional[Tuple[int, int, int] | Tuple[int, int, int, int]] = None,
    stroke_width: int = 0,
) -> None:
    """Render text with an outline (stroke) using native Pillow stroke."""
    if stroke_width and stroke_width > 0 and stroke_fill is not None:
        draw.text(
            xy,
            text,
            font=font,
            fill=fill,
            stroke_width=stroke_width,
            stroke_fill=stroke_fill,
        )
    else:
        draw.text(xy, text, font=font, fill=fill)


def list_available_layouts() -> List[str]:
    if not os.path.isdir(LAYOUTS_DIR):
        return []
    return sorted(f[:-5] for f in os.listdir(LAYOUTS_DIR) if f.endswith(".json"))


def load_layout(
    style_id: str,
    tier_id: str,
    beat_type: str = "normal",
) -> Dict[str, Any]:
    """Load a layout config for the given style+tier+beat.

    Tries these candidate file names in order, returning the first that exists:
        1. {style}_{tier}_{beat}.json            (most specific: style+tier+beat)
        2. {style}_2x3_{beat}.json               (tier-less style+beat)
        3. {style}_{tier}_classic.json           (style+tier classic fallback)
        4. {style}_2x3_classic.json              (style classic, no tier)
        5. {style}_2x3.json                      (raw legacy, no suffix)

    The first two candidates use the requested beat; the last three fall back
    to the safe "classic" variant. This means new beat-specific layouts can
    be shipped per style without breaking the rest of the system.
    """
    style_part = (style_id or "").strip().lower()
    tier_to_suffix = {
        "basic": "2x3",
        "premium": "3x4",
        "deluxe": "4x6",
    }
    tier_part = tier_to_suffix.get((tier_id or "").strip().lower(), "2x3")
    beat_part = (beat_type or "normal").strip().lower() or "normal"

    candidates = [
        f"{style_part}_{tier_part}_{beat_part}.json",
        f"{style_part}_2x3_{beat_part}.json",
        f"{style_part}_{tier_part}_classic.json",
        f"{style_part}_2x3_classic.json",
        f"{style_part}_2x3.json",
    ]
    seen = set()
    for name in candidates:
        if name in seen:
            continue
        seen.add(name)
        path = os.path.join(LAYOUTS_DIR, name)
        if os.path.isfile(path):
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
    raise FileNotFoundError(
        f"No layout config found for style='{style_id}' tier='{tier_id}' "
        f"beat='{beat_type}'. Tried: {candidates}"
    )


def _draw_dot_pattern(
    canvas: Image.Image,
    color: Tuple[int, int, int],
    dot_size: int,
    spacing: int,
) -> None:
    """Tile a screentone/halftone dot grid across the page background."""
    w, h = canvas.size
    radius = max(1, dot_size // 2)
    overlay = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    odraw = ImageDraw.Draw(overlay)
    for y in range(0, h, spacing):
        offset = (y // spacing) % 2 * (spacing // 2)
        for x in range(-offset, w, spacing):
            odraw.ellipse(
                [x - radius, y - radius, x + radius, y + radius],
                fill=(*color, 90),
            )
    canvas.alpha_composite(overlay)


def _resize_to_fit(img: Image.Image, target_w: int, target_h: int) -> Image.Image:
    iw, ih = img.size
    if iw <= 0 or ih <= 0 or target_w <= 0 or target_h <= 0:
        return img
    ratio = min(target_w / iw, target_h / ih)
    nw, nh = max(1, int(iw * ratio)), max(1, int(ih * ratio))
    return img.resize((nw, nh), Image.LANCZOS)


def _resize_to_cover(img: Image.Image, target_w: int, target_h: int) -> Image.Image:
    iw, ih = img.size
    if iw <= 0 or ih <= 0 or target_w <= 0 or target_h <= 0:
        return img
    ratio = max(target_w / iw, target_h / ih)
    nw, nh = max(target_w, int(iw * ratio)), max(target_h, int(ih * ratio))
    return img.resize((nw, nh), Image.LANCZOS)


_GEMINI_ASPECTS = [
    ("1:1", 1.0),
    ("3:2", 1.5),
    ("2:3", 0.667),
    ("3:4", 0.75),
    ("4:3", 1.333),
    ("4:5", 0.8),
    ("5:4", 1.25),
    ("9:16", 0.5625),
    ("16:9", 1.778),
    ("21:9", 2.333),
]


def closest_gemini_aspect(cell_w: int, cell_h: int) -> str:
    """Return the Gemini aspect ratio string closest to the cell's w/h ratio."""
    if cell_w <= 0 or cell_h <= 0:
        return "4:3"
    target = cell_w / cell_h
    best = "4:3"
    best_diff = 999.0
    for name, ratio in _GEMINI_ASPECTS:
        diff = abs(ratio - target)
        if diff < best_diff:
            best_diff = diff
            best = name
    return best


def _ratios_match(img_w: int, img_h: int, cell_w: int, cell_h: int) -> bool:
    """True if the image aspect and cell aspect are close enough to cover-crop."""
    if img_w <= 0 or img_h <= 0 or cell_w <= 0 or cell_h <= 0:
        return True
    img_r = img_w / img_h
    cell_r = cell_w / cell_h
    return abs(img_r - cell_r) / max(cell_r, 0.01) < 0.25


def _paste_panel(
    sheet: Image.Image,
    panel_path: str,
    box: Dict[str, int],
    zoom: str,
    border_color: Tuple[int, int, int],
    border_width: int,
    border_radius: int,
) -> None:
    x, y, w, h = box["x"], box["y"], box["w"], box["h"]
    if w <= 0 or h <= 0:
        return
    layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    if os.path.isfile(panel_path):
        try:
            with Image.open(panel_path) as src:
                src_rgba = src.convert("RGBA")
                effective_zoom = zoom
                if effective_zoom == "cover":
                    fitted = _resize_to_cover(src_rgba, w, h)
                    fx = (w - fitted.width) // 2
                    fy = (h - fitted.height) // 2
                    crop_x = max(0, -fx)
                    crop_y = max(0, -fy)
                    crop_w = min(fitted.width - crop_x, w)
                    crop_h = min(fitted.height - crop_y, h)
                    if crop_w > 0 and crop_h > 0:
                        layer.paste(
                            fitted.crop(
                                (crop_x, crop_y, crop_x + crop_w, crop_y + crop_h)
                            ),
                            (max(0, fx), max(0, fy)),
                        )
                else:
                    fitted = _resize_to_fit(src_rgba, w, h)
                    fx = (w - fitted.width) // 2
                    fy = (h - fitted.height) // 2
                    layer.paste(fitted, (fx, fy))
        except Exception as e:
            print(f"[page_template] panel paste error {panel_path}: {e}")
            layer.paste((210, 210, 210, 255), (0, 0, w, h))
    else:
        layer.paste((210, 210, 210, 255), (0, 0, w, h))

    if border_radius > 0 and border_radius * 2 < min(w, h):
        mask = Image.new("L", (w, h), 0)
        mdraw = ImageDraw.Draw(mask)
        mdraw.rounded_rectangle([0, 0, w - 1, h - 1], radius=border_radius, fill=255)
        bg = Image.new("RGBA", (w, h), (*border_color, 255))
        bg.putalpha(mask)
        layer = Image.alpha_composite(bg, layer)
    else:
        bdraw = ImageDraw.Draw(layer)
        for i in range(border_width):
            bdraw.rectangle(
                [i, i, w - 1 - i, h - 1 - i],
                outline=(*border_color, 255),
            )
    sheet.alpha_composite(layer, (x, y))


def _draw_header(
    sheet: Image.Image,
    header_cfg: Dict[str, Any],
    page_w: int,
    border_color: Tuple[int, int, int],
    title: str,
    subtitle: str,
) -> None:
    height = int(header_cfg.get("height", 90))
    title_size = int(header_cfg.get("title_size", 44))
    sub_size = int(header_cfg.get("subtitle_size", 18))
    title_color = _parse_color(header_cfg.get("title_color"), border_color)
    sub_color = _parse_color(header_cfg.get("subtitle_color"), border_color)

    title_font = _load_font(title_size)
    sub_font = _load_font(sub_size)
    draw = ImageDraw.Draw(sheet)

    title_text = (title or "YOUR COMIC").upper()
    has_sub = bool(subtitle) and bool(header_cfg.get("show_subtitle", True))

    def _measure(font: ImageFont.ImageFont, text: str) -> Tuple[int, int, int]:
        bb = draw.textbbox((0, 0), text, font=font)
        return bb[0], bb[1], bb[2], bb[3]

    def _draw_centered(
        text: str,
        font: ImageFont.ImageFont,
        cap_top_y: int,
        fill: Tuple[int, int, int, int],
        page_w_for_draw: int,
    ) -> int:
        bb = draw.textbbox((0, 0), text, font=font)
        text_w = bb[2] - bb[0]
        if text_w > page_w_for_draw - 20:
            return bb[3] - bb[1]
        tx = (page_w_for_draw - text_w) // 2 - bb[0]
        ty = cap_top_y - bb[1]
        _draw_text_with_stroke(
            draw,
            (tx, ty),
            text,
            font,
            fill=fill,
            stroke_fill=(0, 0, 0, 200),
            stroke_width=2,
        )
        return bb[3] - bb[1]

    if has_sub:
        title_h = (
            draw.textbbox((0, 0), title_text, font=title_font)[3]
            - draw.textbbox((0, 0), title_text, font=title_font)[1]
        )
        sub_h = (
            draw.textbbox((0, 0), subtitle.upper(), font=sub_font)[3]
            - draw.textbbox((0, 0), subtitle.upper(), font=sub_font)[1]
        )
        title_w = (
            draw.textbbox((0, 0), title_text, font=title_font)[2]
            - draw.textbbox((0, 0), title_text, font=title_font)[0]
        )
        gap = 6
        total = title_h + gap + sub_h
        scale = (height - 8) / max(1, total)
        if title_w > page_w - 20:
            w_scale = (page_w - 20) / max(1, title_w)
            scale = min(scale, w_scale)
        if scale < 1.0:
            title_size = max(12, int(title_size * scale))
            sub_size = max(10, int(sub_size * scale))
            title_font = _load_font(title_size)
            sub_font = _load_font(sub_size)
            title_h = (
                draw.textbbox((0, 0), title_text, font=title_font)[3]
                - draw.textbbox((0, 0), title_text, font=title_font)[1]
            )
            sub_h = (
                draw.textbbox((0, 0), subtitle.upper(), font=sub_font)[3]
                - draw.textbbox((0, 0), subtitle.upper(), font=sub_font)[1]
            )
            total = title_h + gap + sub_h
        top_pad = max(4, (height - total) // 2)
        title_cap_y = top_pad
        title_bot = _draw_centered(
            title_text, title_font, title_cap_y, (*title_color, 255), page_w
        )
        sub_cap_y = title_cap_y + title_bot + gap
        _draw_centered(subtitle.upper(), sub_font, sub_cap_y, (*sub_color, 255), page_w)
    else:
        title_h = (
            draw.textbbox((0, 0), title_text, font=title_font)[3]
            - draw.textbbox((0, 0), title_text, font=title_font)[1]
        )
        top_pad = max(4, (height - title_h) // 2)
        _draw_centered(title_text, title_font, top_pad, (*title_color, 255), page_w)


def _draw_footer(
    sheet: Image.Image,
    footer_cfg: Dict[str, Any],
    page_w: int,
    page_h: int,
    border_color: Tuple[int, int, int],
) -> None:
    height = int(footer_cfg.get("height", 50))
    color = _parse_color(footer_cfg.get("color"), border_color)
    size = int(footer_cfg.get("size", 14))
    text = (footer_cfg.get("text") or "MADE WITH COMICME").upper()
    font = _load_font(size)
    draw = ImageDraw.Draw(sheet)
    bb = draw.textbbox((0, 0), text, font=font)
    fx = (page_w - (bb[2] - bb[0])) // 2
    fy = page_h - height + (height - (bb[3] - bb[1])) // 2
    _draw_text_with_stroke(
        draw,
        (fx, fy),
        text,
        font,
        fill=(*color, 255),
        stroke_fill=(255, 255, 255, 220),
        stroke_width=1,
    )


def _draw_page_number(
    sheet: Image.Image,
    page_w: int,
    page_h: int,
    border_color: Tuple[int, int, int],
    current: int,
    total: int,
) -> None:
    if total <= 1 or current <= 0:
        return
    font = _load_font(18)
    text = f"{current} / {total}"
    draw = ImageDraw.Draw(sheet)
    bb = draw.textbbox((0, 0), text, font=font)
    tx = page_w - (bb[2] - bb[0]) - 24
    ty = page_h - (bb[3] - bb[1]) - 18
    _draw_text_with_stroke(
        draw,
        (tx, ty),
        text,
        font,
        fill=(*border_color, 255),
        stroke_fill=(255, 255, 255, 220),
        stroke_width=2,
    )


def build_page(
    layout: Dict[str, Any],
    panel_paths: List[str],
    title: str = "",
    subtitle: str = "",
    current_page: int = 1,
    total_pages: int = 1,
) -> Image.Image:
    """Compose a single full-page comic image.

    Args:
        layout: dict loaded from one of the layout JSONs.
        panel_paths: ordered list of panel image paths. Length should match
            len(layout["panels"]); extra are ignored, missing -> gray box.
        title / subtitle: header text.
        current_page / total_pages: if total_pages > 1, "1 / 2" style marker
            is drawn in the bottom-right.
    """
    page_w, page_h = layout.get("page_size", [1200, 1600])
    page_bg = _parse_color(layout.get("page_bg"), (250, 247, 238))
    border_color = _parse_color(layout.get("border_color"), (10, 10, 10))
    border_width = int(layout.get("border_width", 4))
    border_radius = int(layout.get("panel_border_radius", 0))

    sheet = Image.new("RGBA", (page_w, page_h), (*page_bg, 255))

    pattern = layout.get("page_bg_pattern", "solid")
    if pattern in {"screentone", "halftone"}:
        dot_color = _parse_color(layout.get("screentone_dot_color"), (200, 200, 200))
        dot_size = int(layout.get("screentone_dot_size", 2))
        spacing = int(layout.get("screentone_spacing", 8))
        _draw_dot_pattern(sheet, dot_color, dot_size, spacing)

    panels = layout.get("panels", [])
    for i, panel_cfg in enumerate(panels):
        path = panel_paths[i] if i < len(panel_paths) else None
        _paste_panel(
            sheet=sheet,
            panel_path=path or "",
            box={
                "x": int(panel_cfg["x"]),
                "y": int(panel_cfg["y"]),
                "w": int(panel_cfg["w"]),
                "h": int(panel_cfg["h"]),
            },
            zoom=panel_cfg.get("zoom", "fit"),
            border_color=border_color,
            border_width=border_width,
            border_radius=border_radius,
        )

    _draw_header(
        sheet,
        layout.get("header", {}),
        page_w,
        border_color,
        title if layout.get("show_title_on_interior", False) else "",
        subtitle if layout.get("show_title_on_interior", False) else "",
    )
    _draw_footer(
        sheet,
        layout.get("footer", {}),
        page_w,
        page_h,
        border_color,
    )

    if total_pages > 1 or layout.get("show_page_number", False):
        _draw_page_number(
            sheet, page_w, page_h, border_color, current_page, total_pages
        )

    return sheet.convert("RGB")
