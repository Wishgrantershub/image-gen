import io
import os
from typing import Any, Dict, List, Optional, Tuple

import img2pdf
import qrcode
import qrcode.constants
import qrcode.image.pil  # noqa: F401  -- registers PilImage factory
from PIL import Image, ImageDraw, ImageFont

from app.config import COMIC_OUTPUT_DIR
from app.services.page_template import build_page, load_layout
from app.services.font_utils import load_font as _resolve_font


PANELS_PER_PAGE = 6


PAGE_SIZE_LANDSCAPE = (1600, 1200)
PAGE_SIZE_PORTRAIT = (1200, 1600)
COVER_SIZE = (1200, 1600)
BACK_COVER_SIZE = (1200, 1600)


def _parse_color(
    value: str, default: Tuple[int, int, int] = (250, 247, 238)
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


def _panel_size_for_count(count: int) -> Tuple[int, int]:
    if count <= 4:
        return 2, 2
    if count <= 6:
        return 2, 3
    if count <= 8:
        return 2, 4
    if count <= 12:
        return 3, 4
    if count <= 16:
        return 4, 4
    if count <= 20:
        return 4, 5
    return 4, 6


def _page_size_for_count(count: int) -> Tuple[int, int]:
    if count <= 8:
        return PAGE_SIZE_LANDSCAPE
    return PAGE_SIZE_PORTRAIT


def _resize_to_fit(img: Image.Image, target_w: int, target_h: int) -> Image.Image:
    iw, ih = img.size
    ratio = min(target_w / iw, target_h / ih)
    nw, nh = max(1, int(iw * ratio)), max(1, int(ih * ratio))
    return img.resize((nw, nh), Image.LANCZOS)


def _load_font(
    size: int, candidates: Optional[List[str]] = None
) -> ImageFont.FreeTypeFont:
    return _resolve_font(size, candidates)


def _wrap_lines(
    draw: ImageDraw.ImageDraw, text: str, font: ImageFont.ImageFont, max_w: int
) -> List[str]:
    if not text:
        return []
    words = text.split()
    if not words:
        return []
    lines: List[str] = []
    cur = words[0]
    for w in words[1:]:
        trial = f"{cur} {w}"
        bb = draw.textbbox((0, 0), trial, font=font)
        if (bb[2] - bb[0]) <= max_w:
            cur = trial
        else:
            lines.append(cur)
            cur = w
    lines.append(cur)
    return lines


def _draw_text_with_stroke(
    draw: ImageDraw.ImageDraw,
    xy: Tuple[int, int],
    text: str,
    font: ImageFont.ImageFont,
    fill: Tuple[int, int, int] | Tuple[int, int, int, int],
    stroke_fill: Optional[Tuple[int, int, int] | Tuple[int, int, int, int]] = None,
    stroke_width: int = 0,
) -> None:
    """Render text with native Pillow stroke."""
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


def build_panel_sheet(
    panel_paths: List[str],
    title: str,
    style_name: str,
    paper_hex: str = "#FAF7EE",
    border_hex: str = "#0A0A0A",
    layout: Optional[str] = None,
    font_candidates: Optional[List[str]] = None,
) -> Image.Image:
    n = len(panel_paths)
    cols, rows = _panel_size_for_count(n)
    if layout in {
        "1x4",
        "1x3",
        "1x2",
        "2x2",
        "2x3",
        "2x4",
        "3x4",
        "3x3",
        "4x3",
        "4x4",
        "4x5",
        "4x6",
        "5x4",
        "6x4",
    }:
        try:
            cols, rows = int(layout.split("x")[0]), int(layout.split("x")[1])
        except (ValueError, IndexError):
            pass

    paper = _parse_color(paper_hex, (250, 247, 238))
    border = _parse_color(border_hex, (10, 10, 10))

    page_w, page_h = _page_size_for_count(n)
    margin_x = 60
    margin_y = 100
    title_h = 80

    gutter_x = 18
    gutter_y = 18
    panel_w = (page_w - 2 * margin_x - (cols - 1) * gutter_x) // cols
    panel_h = (page_h - 2 * margin_y - title_h - (rows - 1) * gutter_y) // rows

    sheet = Image.new("RGB", (page_w, page_h), paper)
    draw = ImageDraw.Draw(sheet)

    title_font = _load_font(54, font_candidates)
    sub_font = _load_font(24, font_candidates)
    title_text = (title or "YOUR COMIC").upper()
    sub_text = f"{style_name} EDITION  -  {n} PANELS".upper()
    title_lines = _wrap_lines(draw, title_text, title_font, page_w - 4 * margin_x)
    y = 36
    for ln in title_lines:
        bb = draw.textbbox((0, 0), ln, font=title_font)
        tx = (page_w - (bb[2] - bb[0])) // 2
        draw.text((tx + 2, y + 2), ln, font=title_font, fill=(0, 0, 0, 60))
        draw.text((tx, y), ln, font=title_font, fill=border)
        y += (bb[3] - bb[1]) + 4
    bb = draw.textbbox((0, 0), sub_text, font=sub_font)
    sx = (page_w - (bb[2] - bb[0])) // 2
    draw.text((sx, y + 4), sub_text, font=sub_font, fill=border)

    for i, path in enumerate(panel_paths):
        r, c = divmod(i, cols)
        x = margin_x + c * (panel_w + gutter_x)
        y0 = margin_y + title_h + r * (panel_h + gutter_y)
        try:
            with Image.open(path) as img:
                img_rgb = img.convert("RGB")
                fitted = _resize_to_fit(img_rgb, panel_w, panel_h)
                fx = x + (panel_w - fitted.width) // 2
                fy = y0 + (panel_h - fitted.height) // 2
                sheet.paste(fitted, (fx, fy))
        except Exception as e:
            print(f"Panel sheet paste error for {path}: {e}")
            draw.rectangle(
                [x, y0, x + panel_w, y0 + panel_h], fill=(220, 220, 220), outline=border
            )

        draw.rectangle(
            [x, y0, x + panel_w, y0 + panel_h],
            outline=border,
            width=4,
        )

        num_font = _load_font(28, font_candidates)
        num = f"{i + 1}"
        nb = draw.textbbox((0, 0), num, font=num_font)
        pad = 6
        cr = max(18, (nb[2] - nb[0]) // 2 + 12)
        cx = x + 18 + cr
        cy = y0 + 18 + cr
        draw.ellipse(
            [cx - cr, cy - cr, cx + cr, cy + cr],
            fill=(0, 0, 0),
            outline=(255, 255, 255),
        )
        tx = cx - (nb[2] - nb[0]) // 2 - nb[0]
        ty = cy - (nb[3] - nb[1]) // 2 - nb[1]
        draw.text((tx, ty), num, font=num_font, fill=(255, 255, 255))

    footer_font = _load_font(18, font_candidates)
    footer = "MADE WITH COMICME  -  TURN ANYONE INTO A COMIC HERO"
    fb = draw.textbbox((0, 0), footer, font=footer_font)
    fx = (page_w - (fb[2] - fb[0])) // 2
    draw.text((fx, page_h - 40), footer, font=footer_font, fill=border)
    return sheet


def build_cover_page(
    cover_path: Optional[str],
    title: str,
    style_name: str,
    paper_hex: str = "#FAF7EE",
    border_hex: str = "#0A0A0A",
    font_candidates: Optional[List[str]] = None,
) -> Image.Image:
    paper = _parse_color(paper_hex, (250, 247, 238))
    border = _parse_color(border_hex, (10, 10, 10))
    w, h = COVER_SIZE

    if cover_path and os.path.exists(cover_path):
        try:
            with Image.open(cover_path) as img:
                sheet = img.convert("RGB").resize((w, h), Image.LANCZOS)
        except Exception:
            sheet = _placeholder_cover(
                w, h, paper, border, font_candidates, style_name, title
            )
    else:
        sheet = _placeholder_cover(
            w, h, paper, border, font_candidates, style_name, title
        )

    draw = ImageDraw.Draw(sheet)
    border_w = 14
    for i in range(border_w):
        draw.rectangle([i, i, w - 1 - i, h - 1 - i], outline=border)
    return sheet


def _placeholder_cover(
    w: int, h: int, paper, border, font_candidates, style_name: str, title: str
) -> Image.Image:
    sheet = Image.new("RGB", (w, h), paper)
    draw = ImageDraw.Draw(sheet)
    for y in range(0, h, 12):
        offset = (y // 12) % 2 * 6
        for x in range(-6, w, 24):
            draw.ellipse([x + offset, y, x + offset + 8, y + 8], fill=(220, 215, 200))
    title_font = _load_font(72, font_candidates)
    sub_font = _load_font(32, font_candidates)
    t = (title or "YOUR COMIC").upper()
    lines = _wrap_lines(draw, t, title_font, w - 200)
    bb = draw.textbbox((0, 0), "Ag", font=title_font)
    lh = (bb[3] - bb[1]) + 8
    total = lh * len(lines)
    y = (h - total) // 2
    for ln in lines:
        bb2 = draw.textbbox((0, 0), ln, font=title_font)
        tx = (w - (bb2[2] - bb2[0])) // 2
        draw.text((tx + 3, y + 3), ln, font=title_font, fill=(0, 0, 0, 80))
        draw.text((tx, y), ln, font=title_font, fill=border)
        y += lh
    s = f"{style_name} EDITION"
    sb = draw.textbbox((0, 0), s, font=sub_font)
    sx = (w - (sb[2] - sb[0])) // 2
    draw.text((sx, h - 120), s, font=sub_font, fill=border)
    return sheet


def build_hero_panel_cover(
    hero_panel_path: str,
    paper_hex: str = "#FAF7EE",
    border_hex: str = "#0A0A0A",
) -> Image.Image:
    """Build a cover from a hero panel, used as a fallback when AI cover fails.

    Crops the panel to the 3:4 cover aspect ratio (cover zoom) and centers it
    on a paper-colored background. A dark gradient strip is pre-baked at the
    top and bottom so the typography overlay added later by
    ``text_render_service.render_cover_overlays`` reads well. The result is
    then resized to the standard COVER_SIZE.
    """
    w, h = COVER_SIZE
    paper = _parse_color(paper_hex, (250, 247, 238))
    border = _parse_color(border_hex, (10, 10, 10))
    cover_ratio = w / h

    sheet = Image.new("RGB", (w, h), paper)
    if not hero_panel_path or not os.path.exists(hero_panel_path):
        return sheet

    try:
        with Image.open(hero_panel_path) as img:
            src = img.convert("RGB")
            iw, ih = src.size
            if iw <= 0 or ih <= 0:
                return sheet
            target_ratio = cover_ratio
            src_ratio = iw / ih
            if src_ratio > target_ratio:
                new_w = int(ih * target_ratio)
                x0 = max(0, (iw - new_w) // 2)
                cropped = src.crop((x0, 0, x0 + new_w, ih))
            else:
                new_h = int(iw / target_ratio)
                y0 = max(0, (ih - new_h) // 2)
                cropped = src.crop((0, y0, iw, y0 + new_h))
            fitted = cropped.resize((w, h), Image.LANCZOS)
            sheet.paste(fitted, (0, 0))
    except Exception as e:
        print(f"[build_hero_panel_cover] panel load error: {e}")
        return sheet

    overlay = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    odraw = ImageDraw.Draw(overlay)
    top_h = int(h * 0.22)
    bot_h = int(h * 0.16)
    for y in range(top_h):
        a = int(180 * (1.0 - y / top_h))
        odraw.line([(0, y), (w, y)], fill=(0, 0, 0, a))
    for y in range(bot_h):
        a = int(180 * (y / bot_h))
        odraw.line([(0, h - 1 - y), (w, h - 1 - y)], fill=(0, 0, 0, a))
    sheet = Image.alpha_composite(sheet.convert("RGBA"), overlay).convert("RGB")

    border_w = 14
    draw = ImageDraw.Draw(sheet)
    for i in range(border_w):
        draw.rectangle([i, i, w - 1 - i, h - 1 - i], outline=border)
    return sheet


def _make_qr_code(url: str, size_px: int = 320) -> Image.Image:
    """Generate a real scannable QR code as a PIL image (white bg, black modules)."""
    target = url or "https://comicme.example"
    qr = qrcode.QRCode(
        version=None,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=8,
        border=2,
    )
    qr.add_data(target)
    qr.make(fit=True)
    raw = qr.make_image(
        fill_color="black", back_color="white", image_factory=qrcode.image.pil.PilImage
    )
    pil_img = raw.get_image() if hasattr(raw, "get_image") else raw._img
    return pil_img.convert("RGB").resize((size_px, size_px), Image.LANCZOS)


def build_back_cover(
    share_url: str,
    style_name: str,
    paper_hex: str = "#FAF7EE",
    border_hex: str = "#0A0A0A",
    font_candidates: Optional[List[str]] = None,
) -> Image.Image:
    paper = _parse_color(paper_hex, (250, 247, 238))
    border = _parse_color(border_hex, (10, 10, 10))
    w, h = BACK_COVER_SIZE
    sheet = Image.new("RGB", (w, h), paper)
    draw = ImageDraw.Draw(sheet)

    border_w = 14
    for i in range(border_w):
        draw.rectangle([i, i, w - 1 - i, h - 1 - i], outline=border)

    headline = _load_font(64, font_candidates)
    body = _load_font(28, font_candidates)
    micro = _load_font(20, font_candidates)

    head = "THE END... OR JUST THE BEGINNING?"
    bb = draw.textbbox((0, 0), head, font=headline)
    tx = (w - (bb[2] - bb[0])) // 2
    _draw_text_with_stroke(
        draw,
        (tx, 220),
        head,
        headline,
        fill=border,
        stroke_fill=(255, 255, 255, 200),
        stroke_width=2,
    )

    sub_lines = [
        f"You just starred in a {style_name.lower()} comic.",
        "Powered by AI, drawn in minutes.",
        "Make your next adventure at comicme.app.",
    ]
    y = 360
    for ln in sub_lines:
        bb2 = draw.textbbox((0, 0), ln, font=body)
        tx = (w - (bb2[2] - bb2[0])) // 2
        _draw_text_with_stroke(
            draw,
            (tx, y),
            ln,
            body,
            fill=border,
            stroke_fill=(255, 255, 255, 180),
            stroke_width=1,
        )
        y += 48

    qr_size = 280
    qr_img = _make_qr_code(share_url, size_px=qr_size)
    qr_box = (
        w // 2 - qr_size // 2 - 8,
        h // 2 - 30,
        w // 2 + qr_size // 2 + 8,
        h // 2 - 30 + qr_size + 16,
    )
    draw.rectangle(qr_box, fill=(255, 255, 255), outline=border, width=4)
    sheet.paste(qr_img, (qr_box[0] + 8, qr_box[1] + 8))

    qr_font = _load_font(22, font_candidates)
    scan_text = "SCAN TO VIEW ONLINE"
    bb3 = draw.textbbox((0, 0), scan_text, font=qr_font)
    tx = (w - (bb3[2] - bb3[0])) // 2
    _draw_text_with_stroke(
        draw,
        (tx, qr_box[3] + 12),
        scan_text,
        qr_font,
        fill=border,
        stroke_fill=(255, 255, 255, 200),
        stroke_width=2,
    )

    url = share_url or "https://comicme.example/c/<id>"
    url_bb = draw.textbbox((0, 0), url, font=micro)
    ux = (w - (url_bb[2] - url_bb[0])) // 2
    _draw_text_with_stroke(
        draw,
        (ux, h - 220),
        url,
        micro,
        fill=border,
        stroke_fill=(255, 255, 255, 180),
        stroke_width=1,
    )

    foot = "MADE WITH COMICME  -  COMICME.AI"
    fb = draw.textbbox((0, 0), foot, font=micro)
    fx = (w - (fb[2] - fb[0])) // 2
    _draw_text_with_stroke(
        draw,
        (fx, h - 80),
        foot,
        micro,
        fill=border,
        stroke_fill=(255, 255, 255, 180),
        stroke_width=1,
    )
    return sheet


def build_pdf(
    panel_paths: List[str],
    cover_path: Optional[str],
    title: str,
    style_name: str,
    share_url: str,
    layout: str = "2x3",
    paper_hex: str = "#FAF7EE",
    border_hex: str = "#0A0A0A",
    font_candidates: Optional[List[str]] = None,
    output_filename: str = "comic.pdf",
    style_id: str = "manga",
    tier_id: str = "basic",
    page_beats: Optional[List[str]] = None,
) -> str:
    os.makedirs(COMIC_OUTPUT_DIR, exist_ok=True)
    safe_name = os.path.basename(output_filename) or "comic.pdf"

    cover_img = build_cover_page(
        cover_path, title, style_name, paper_hex, border_hex, font_candidates
    )
    back_img = build_back_cover(
        share_url, style_name, paper_hex, border_hex, font_candidates
    )

    try:
        layout_cfg = load_layout(style_id, tier_id)
    except FileNotFoundError as e:
        print(f"[build_pdf] {e} — falling back to manga_2x3_classic.json")
        layout_cfg = load_layout("manga", "basic")

    style_display = style_name or layout_cfg.get("style", "MANGA")
    panels_per_page_cfg = len(layout_cfg.get("panels", [])) or PANELS_PER_PAGE
    chunks: List[List[str]] = [
        panel_paths[i : i + panels_per_page_cfg]
        for i in range(0, len(panel_paths), panels_per_page_cfg)
    ]
    if not chunks:
        chunks = [[]]
    total_pages = max(1, len(chunks))
    show_page_numbers = (total_pages > 1) or bool(
        layout_cfg.get("show_page_number", False)
    )

    page_imgs: List[Image.Image] = []
    for i, chunk in enumerate(chunks, start=1):
        beat = page_beats or []
        beat_i = beat[i - 1] if i - 1 < len(beat) else "normal"
        try:
            page_layout_cfg = load_layout(style_id, tier_id, beat_type=beat_i)
        except FileNotFoundError:
            page_layout_cfg = layout_cfg
        page_imgs.append(
            build_page(
                layout=page_layout_cfg,
                panel_paths=chunk,
                title=title,
                subtitle=f"{style_display.upper()} EDITION - PAGE {i} OF {total_pages}"
                if show_page_numbers
                else f"{style_display.upper()} EDITION",
                current_page=i,
                total_pages=total_pages,
            )
        )

    cover_path_tmp = os.path.join(COMIC_OUTPUT_DIR, f"_cover_{safe_name}.jpg")
    page_paths_tmp: List[str] = []
    back_path_tmp = os.path.join(COMIC_OUTPUT_DIR, f"_back_{safe_name}.jpg")
    cover_img.convert("RGB").save(cover_path_tmp, "JPEG", quality=92)
    for i, pimg in enumerate(page_imgs, start=1):
        ppath = os.path.join(COMIC_OUTPUT_DIR, f"_page{i}_{safe_name}.jpg")
        pimg.convert("RGB").save(ppath, "JPEG", quality=90)
        page_paths_tmp.append(ppath)
    back_img.convert("RGB").save(back_path_tmp, "JPEG", quality=90)

    all_paths = [cover_path_tmp] + page_paths_tmp + [back_path_tmp]
    output_path = os.path.join(COMIC_OUTPUT_DIR, output_filename)

    if os.path.exists(output_path):
        try:
            os.remove(output_path)
        except OSError:
            pass

    pdf_bytes = None
    try:
        pdf_bytes = img2pdf.convert(all_paths)
    except Exception as e:
        print(f"[build_pdf] img2pdf failed ({type(e).__name__}: {e}); falling back")

    if pdf_bytes:
        with open(output_path, "wb") as f:
            f.write(pdf_bytes)
    else:
        fallback_pages: List[Image.Image] = []
        for p in all_paths:
            with Image.open(p) as im:
                fallback_pages.append(im.convert("RGB"))
        if not fallback_pages:
            raise RuntimeError(f"No pages available to build {output_filename}")
        first = fallback_pages[0]
        rest = fallback_pages[1:]
        first.save(output_path, "PDF", save_all=True, append_images=rest)

    if not os.path.exists(output_path) or os.path.getsize(output_path) == 0:
        raise RuntimeError(f"PDF build produced an empty file: {output_filename}")

    for tmp in [cover_path_tmp] + page_paths_tmp + [back_path_tmp]:
        try:
            os.remove(tmp)
        except OSError:
            pass

    return output_path
