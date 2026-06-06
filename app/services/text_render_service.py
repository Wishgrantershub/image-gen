import os
import math
from typing import Any, Dict, List, Optional, Tuple

from PIL import Image, ImageDraw, ImageFont


class TextRenderService:
    def _load_font(self, font_size: int) -> ImageFont.ImageFont:
        font_candidates = [
            "C:/Windows/Fonts/trebuc.ttf",
            "C:/Windows/Fonts/segoeui.ttf",
            "C:/Windows/Fonts/arial.ttf",
        ]
        for font_path in font_candidates:
            if os.path.exists(font_path):
                try:
                    return ImageFont.truetype(font_path, font_size)
                except Exception:
                    continue
        return ImageFont.load_default()

    def get_page_text_box(
        self,
        template_data: Optional[Dict[str, Any]],
        page_number: int,
        image_path: str,
    ) -> Dict[str, int]:
        default_box: Dict[str, int] = {
            "x": 36,
            "y": 520,
            "w": 440,
            "h": 220,
            "font_size": 30,
            "line_spacing": 10,
            "padding": 20,
        }
        if not os.path.exists(image_path):
            return default_box

        try:
            with Image.open(image_path) as img:
                width, height = img.size
        except Exception:
            return default_box

        computed_default = {
            "x": max(20, int(width * 0.06)),
            "y": int(height * 0.68),
            "w": int(width * 0.88),
            "h": int(height * 0.28),
            "font_size": max(22, int(height * 0.04)),
            "line_spacing": max(6, int(height * 0.01)),
            "padding": max(14, int(width * 0.025)),
        }

        if not template_data:
            return computed_default

        page_layouts = template_data.get("text_layouts", {})
        page_key = str(page_number)
        page_box = page_layouts.get(page_key)
        if not isinstance(page_box, dict):
            return computed_default

        merged = dict(computed_default)
        for key in ["x", "y", "w", "h", "font_size", "line_spacing", "padding"]:
            val = page_box.get(key)
            if isinstance(val, int) and val > 0:
                merged[key] = val
        return merged

    @staticmethod
    def _wrap_text(
        draw: ImageDraw.ImageDraw,
        text: str,
        font: ImageFont.ImageFont,
        max_width: int,
    ) -> list[str]:
        words = (text or "").split()
        if not words:
            return []

        lines: list[str] = []
        current = words[0]
        for word in words[1:]:
            trial = f"{current} {word}"
            left, top, right, bottom = draw.textbbox((0, 0), trial, font=font)
            width = right - left
            if width <= max_width:
                current = trial
            else:
                lines.append(current)
                current = word
        lines.append(current)
        return lines

    def render_page_text(
        self,
        image_path: str,
        text: str,
        text_box: Dict[str, int],
    ) -> bool:
        if not text or not os.path.exists(image_path):
            return False

        try:
            with Image.open(image_path).convert("RGBA") as image:
                draw = ImageDraw.Draw(image)
                x = int(text_box.get("x", 0))
                y = int(text_box.get("y", 0))
                w = int(text_box.get("w", image.width))
                h = int(text_box.get("h", image.height // 3))
                font_size = int(text_box.get("font_size", 28))
                line_spacing = int(text_box.get("line_spacing", 8))
                padding = int(text_box.get("padding", 16))

                font = self._load_font(font_size)
                usable_width = max(30, w - 2 * padding)
                lines = self._wrap_text(draw, text, font, usable_width)
                if not lines:
                    return False

                left, top, right, bottom = draw.textbbox((0, 0), "Ag", font=font)
                line_height = (bottom - top) + line_spacing
                max_lines = max(1, (h - 2 * padding) // max(1, line_height))
                if len(lines) > max_lines:
                    lines = lines[:max_lines]
                    if lines:
                        lines[-1] = lines[-1].rstrip(" .,!?") + "..."

                panel = Image.new("RGBA", (w, h), (255, 255, 255, 170))
                image.alpha_composite(panel, (x, y))

                text_y = y + padding
                for line in lines:
                    draw.text(
                        (x + padding + 2, text_y + 2),
                        line,
                        font=font,
                        fill=(0, 0, 0, 120),
                    )
                    draw.text(
                        (x + padding, text_y), line, font=font, fill=(35, 35, 35, 255)
                    )
                    text_y += line_height

                image.convert("RGB").save(image_path)
            return True
        except Exception as e:
            print(f"Text render error: {e}")
            return False

    def _load_bold_font(
        self, font_size: int, candidates: Optional[List[str]] = None
    ) -> ImageFont.ImageFont:
        search = candidates or [
            "C:/Windows/Fonts/seguisb.ttf",
            "C:/Windows/Fonts/arialbd.ttf",
            "C:/Windows/Fonts/trebucbd.ttf",
            "C:/Windows/Fonts/segoeui.ttf",
            "C:/Windows/Fonts/comicbd.ttf",
            "C:/Windows/Fonts/comic.ttf",
            "C:/Windows/Fonts/impact.ttf",
        ]
        for fp in search:
            if os.path.exists(fp):
                try:
                    return ImageFont.truetype(fp, font_size)
                except Exception:
                    continue
        return self._load_font(font_size)

    @staticmethod
    def _wrap_lines(
        draw: ImageDraw.ImageDraw,
        text: str,
        font: ImageFont.ImageFont,
        max_width: int,
    ) -> List[str]:
        if not text:
            return []
        words = text.split()
        if not words:
            return []
        lines: List[str] = []
        current = words[0]
        for w in words[1:]:
            trial = f"{current} {w}"
            bbox = draw.textbbox((0, 0), trial, font=font)
            if (bbox[2] - bbox[0]) <= max_width:
                current = trial
            else:
                lines.append(current)
                current = w
        lines.append(current)
        return lines

    @staticmethod
    def _draw_text_with_stroke(
        draw: ImageDraw.ImageDraw,
        xy: Tuple[int, int],
        text: str,
        font: ImageFont.ImageFont,
        fill: Tuple[int, int, int, int],
        stroke_fill: Optional[Tuple[int, int, int, int]] = None,
        stroke_width: int = 0,
    ) -> None:
        """Draw text with an optional outline (stroke) under it.

        If `stroke_width` is 0, falls back to a single draw. Otherwise we render
        the text 8 times offset by ±w on x and y, then once on top with the
        real fill. This is the cross-platform way to outline text in PIL since
        it has no built-in stroke support on all builds.
        """
        x, y = xy
        if stroke_width and stroke_width > 0 and stroke_fill is not None:
            for ox in range(-stroke_width, stroke_width + 1):
                for oy in range(-stroke_width, stroke_width + 1):
                    if ox == 0 and oy == 0:
                        continue
                    if (ox * ox + oy * oy) > (stroke_width * stroke_width):
                        continue
                    draw.text((x + ox, y + oy), text, font=font, fill=stroke_fill)
        draw.text((x, y), text, font=font, fill=fill)

    @staticmethod
    def _panel_border_box(
        image_w: int,
        image_h: int,
        border_color: Tuple[int, int, int, int],
        border_width: int,
    ) -> Image.Image:
        layer = Image.new("RGBA", (image_w, image_h), (0, 0, 0, 0))
        draw = ImageDraw.Draw(layer)
        for i in range(border_width):
            draw.rectangle(
                [i, i, image_w - 1 - i, image_h - 1 - i],
                outline=border_color,
            )
        return layer

    @staticmethod
    def _pct_to_box(
        iw: int, ih: int, pct: Dict[str, float]
    ) -> Tuple[int, int, int, int]:
        """Convert a 0-100 percentage box to pixel coordinates.

        Clamps x+w and y+h to the panel bounds so a layout that asks for an
        oversized box (e.g. ``{x: 60, w: 90}``) never extends text past the
        panel border. The previous version only clamped x and y, which let
        speech and caption text get sliced off the right edge of the panel.
        """
        try:
            x_pct = max(0.0, min(100.0, float(pct.get("x", 0))))
        except (TypeError, ValueError):
            x_pct = 0.0
        try:
            y_pct = max(0.0, min(100.0, float(pct.get("y", 0))))
        except (TypeError, ValueError):
            y_pct = 0.0
        try:
            w_pct = max(2.0, min(100.0, float(pct.get("w", 30))))
        except (TypeError, ValueError):
            w_pct = 30.0
        try:
            h_pct = max(2.0, min(100.0, float(pct.get("h", 12))))
        except (TypeError, ValueError):
            h_pct = 12.0

        if x_pct + w_pct > 100.0:
            w_pct = max(2.0, 100.0 - x_pct)
        if y_pct + h_pct > 100.0:
            h_pct = max(2.0, 100.0 - y_pct)

        x = int(x_pct / 100.0 * iw)
        y = int(y_pct / 100.0 * ih)
        w = int(w_pct / 100.0 * iw)
        h = int(h_pct / 100.0 * ih)
        return (x, y, x + w, y + h)

    @staticmethod
    def _draw_caption_box(
        draw: ImageDraw.ImageDraw,
        box: Tuple[int, int, int, int],
        text: str,
        font: ImageFont.ImageFont,
        padding: int,
        style_colors: Dict[str, Tuple[int, int, int, int]],
    ) -> int:
        x1, y1, x2, y2 = box
        draw.rectangle(box, fill=style_colors["fill"], outline=style_colors["border"])
        usable_w = max(20, (x2 - x1) - 2 * padding)
        lines = TextRenderService._wrap_lines(draw, text, font, usable_w)
        if not lines:
            return y1
        bbox = draw.textbbox((0, 0), "Ag", font=font)
        line_h = (bbox[3] - bbox[1]) + 4
        max_lines = max(1, (y2 - y1 - 2 * padding) // max(1, line_h))
        lines = lines[:max_lines]
        ty = y1 + padding
        for line in lines:
            TextRenderService._draw_text_with_stroke(
                draw,
                (x1 + padding, ty),
                line,
                font,
                fill=style_colors["text"],
                stroke_fill=(255, 255, 255, 255),
                stroke_width=2,
            )
            ty += line_h
        return ty

    @staticmethod
    def _draw_caption_box_manga_slab(
        draw: ImageDraw.ImageDraw,
        panel_size: Tuple[int, int],
        text: str,
        font: ImageFont.ImageFont,
        style_colors: Dict[str, Tuple[int, int, int, int]],
    ) -> None:
        iw, ih = panel_size
        box_w = max(110, int(iw * 0.34))
        box_h = max(60, int(ih * 0.20))
        x2 = iw - 8
        y1 = 8
        x1 = x2 - box_w
        y2 = y1 + box_h
        box = (x1, y1, x2, y2)
        draw.rectangle(
            box, fill=style_colors["fill"], outline=style_colors["border"], width=2
        )
        inner = text.upper()
        usable_w = max(40, (x2 - x1) - 18)
        lines = TextRenderService._wrap_lines(draw, inner, font, usable_w)
        if not lines:
            return
        bbox = draw.textbbox((0, 0), "Ag", font=font)
        line_h = (bbox[3] - bbox[1]) + 4
        ty = y1 + 8
        for line in lines[: int((y2 - y1 - 12) // max(1, line_h))]:
            TextRenderService._draw_text_with_stroke(
                draw,
                (x1 + 9, ty),
                line,
                font,
                fill=style_colors["text"],
                stroke_fill=(255, 255, 255, 255),
                stroke_width=2,
            )
            ty += line_h

    @staticmethod
    def _draw_caption_box_pixar_rounded(
        draw: ImageDraw.ImageDraw,
        panel_size: Tuple[int, int],
        text: str,
        font: ImageFont.ImageFont,
        style_colors: Dict[str, Tuple[int, int, int, int]],
    ) -> None:
        iw, ih = panel_size
        box_w = max(180, int(iw * 0.78))
        box_h = max(56, int(ih * 0.16))
        x1 = (iw - box_w) // 2
        y1 = 8
        x2 = x1 + box_w
        y2 = y1 + box_h
        radius = min(22, box_h // 2)
        draw.rounded_rectangle(
            (x1, y1, x2, y2),
            radius=radius,
            fill=style_colors["fill"],
            outline=style_colors["border"],
            width=3,
        )
        inner = text.upper()
        usable_w = max(40, (x2 - x1) - 28)
        lines = TextRenderService._wrap_lines(draw, inner, font, usable_w)
        if not lines:
            return
        bbox = draw.textbbox((0, 0), "Ag", font=font)
        line_h = (bbox[3] - bbox[1]) + 4
        ty = y1 + 8
        for line in lines[: int((y2 - y1 - 16) // max(1, line_h))]:
            bb = draw.textbbox((0, 0), line, font=font)
            tx = x1 + ((x2 - x1) - (bb[2] - bb[0])) // 2
            TextRenderService._draw_text_with_stroke(
                draw,
                (tx, ty),
                line,
                font,
                fill=style_colors["text"],
                stroke_fill=(255, 255, 255, 255),
                stroke_width=2,
            )
            ty += line_h

    @staticmethod
    def _draw_caption_box_superhero_block(
        draw: ImageDraw.ImageDraw,
        panel_size: Tuple[int, int],
        text: str,
        font: ImageFont.ImageFont,
        style_colors: Dict[str, Tuple[int, int, int, int]],
    ) -> None:
        iw, ih = panel_size
        box_w = max(220, int(iw * 0.86))
        box_h = max(60, int(ih * 0.18))
        x1 = (iw - box_w) // 2
        y1 = 8
        x2 = x1 + box_w
        y2 = y1 + box_h
        accent = style_colors.get("accent", (255, 215, 0, 255))
        draw.rectangle(
            (x1 - 4, y1 - 4, x2 + 4, y2 + 4),
            fill=accent,
            outline=style_colors["border"],
            width=2,
        )
        draw.rectangle(
            (x1, y1, x2, y2),
            fill=style_colors["fill"],
            outline=style_colors["border"],
            width=4,
        )
        inner = text.upper()
        usable_w = max(40, (x2 - x1) - 24)
        lines = TextRenderService._wrap_lines(draw, inner, font, usable_w)
        if not lines:
            return
        bbox = draw.textbbox((0, 0), "Ag", font=font)
        line_h = (bbox[3] - bbox[1]) + 4
        ty = y1 + 10
        for line in lines[: int((y2 - y1 - 20) // max(1, line_h))]:
            bb = draw.textbbox((0, 0), line, font=font)
            tx = x1 + ((x2 - x1) - (bb[2] - bb[0])) // 2
            TextRenderService._draw_text_with_stroke(
                draw,
                (tx, ty),
                line,
                font,
                fill=style_colors["text"],
                stroke_fill=(0, 0, 0, 255),
                stroke_width=3,
            )
            ty += line_h

    @staticmethod
    def _draw_speech_bubble(
        draw: ImageDraw.ImageDraw,
        bubble_kind: str,
        anchor: Tuple[int, int],
        text: str,
        font: ImageFont.ImageFont,
        style_colors: Dict[str, Tuple[int, int, int, int]],
        panel_size: Tuple[int, int],
        tail_direction: str = "down-left",
        font_candidates: Optional[List[str]] = None,
    ) -> None:
        ax, ay = anchor
        iw, ih = panel_size
        max_bubble_w = int(iw * 0.45)
        max_bubble_h = int(ih * 0.36)

        if not text:
            return

        def _line_width(lines: List[str], font_obj: ImageFont.ImageFont) -> int:
            if not lines:
                return 0
            return max(
                draw.textbbox((0, 0), ln, font=font_obj)[2]
                - draw.textbbox((0, 0), ln, font=font_obj)[0]
                for ln in lines
            )

        def _try_load(size: int) -> Optional[ImageFont.ImageFont]:
            for fp in font_candidates or [
                "C:/Windows/Fonts/seguisb.ttf",
                "C:/Windows/Fonts/arialbd.ttf",
                "C:/Windows/Fonts/trebucbd.ttf",
                "C:/Windows/Fonts/segoeui.ttf",
                "C:/Windows/Fonts/comicbd.ttf",
                "C:/Windows/Fonts/comic.ttf",
                "C:/Windows/Fonts/impact.ttf",
            ]:
                if os.path.exists(fp):
                    try:
                        return ImageFont.truetype(fp, size)
                    except Exception:
                        continue
            return None

        usable_w = max(40, max_bubble_w - 24)
        lines = TextRenderService._wrap_lines(draw, text, font, usable_w)
        if not lines:
            return

        bbox = draw.textbbox((0, 0), "Ag", font=font)
        line_h = (bbox[3] - bbox[1]) + 4
        text_w = _line_width(lines, font)
        text_h = line_h * len(lines) + 12

        bw = max(80, min(max_bubble_w, text_w + 36))
        bh = max(50, min(max_bubble_h, text_h + 24))

        if text_w + 36 > bw and text_w > 0:
            try:
                cur_font = font
                cur_size = getattr(cur_font, "size", None)
                if not isinstance(cur_size, int):
                    cur_size = max(20, int(ih * 0.055))
                attempts = 0
                while text_w + 36 > bw and cur_size > 12 and attempts < 8:
                    cur_size -= 2
                    new_font = _try_load(cur_size)
                    if new_font is None:
                        break
                    cur_font = new_font
                    lines = TextRenderService._wrap_lines(
                        draw, text, cur_font, max(40, bw - 24)
                    )
                    bbox = draw.textbbox((0, 0), "Ag", font=cur_font)
                    line_h = (bbox[3] - bbox[1]) + 4
                    text_w = _line_width(lines, cur_font)
                    text_h = line_h * len(lines) + 12
                    bw = max(80, min(max_bubble_w, text_w + 36))
                    bh = max(50, min(max_bubble_h, text_h + 24))
                    attempts += 1
                font = cur_font
            except Exception:
                pass

        x1 = max(8, min(iw - bw - 8, ax - bw // 2))
        y1 = max(8, min(ih - bh - 8, ay - bh // 2))
        x2 = x1 + bw
        y2 = y1 + bh

        bubble_border = style_colors["border"]
        bubble_fill = style_colors["fill"]

        if bubble_kind == "shout":
            TextRenderService._draw_jagged_burst_bubble(
                draw, x1, y1, x2, y2, bubble_fill, bubble_border, style_colors
            )
        elif bubble_kind == "thought":
            draw.ellipse(
                [x1, y1, x2, y2],
                fill=bubble_fill,
                outline=bubble_border,
            )
            for i, (tcx, tcy, tr) in enumerate(
                [(x1 + 24, y2 + 6, 8), (x1 + 8, y2 + 22, 5)]
            ):
                draw.ellipse(
                    [tcx - tr, tcy - tr, tcx + tr, tcy + tr],
                    fill=bubble_fill,
                    outline=bubble_border,
                )
        else:
            TextRenderService._draw_rounded_bubble_with_tail(
                draw,
                x1,
                y1,
                x2,
                y2,
                bw,
                bh,
                bubble_fill,
                bubble_border,
                tail_direction,
            )

        ty = y1 + (bh - text_h) // 2 + 6
        text_stroke = (0, 0, 0, 255) if bubble_kind == "shout" else None
        text_stroke_w = 2 if bubble_kind == "shout" else 0
        for line in lines:
            tw = draw.textbbox((0, 0), line, font=font)
            tx = x1 + (bw - (tw[2] - tw[0])) // 2
            TextRenderService._draw_text_with_stroke(
                draw,
                (tx, ty),
                line,
                font,
                fill=style_colors["text"],
                stroke_fill=text_stroke,
                stroke_width=text_stroke_w,
            )
            ty += line_h

    @staticmethod
    def _draw_rounded_bubble_with_tail(
        draw: ImageDraw.ImageDraw,
        x1: int,
        y1: int,
        x2: int,
        y2: int,
        bw: int,
        bh: int,
        fill: Tuple[int, int, int, int],
        border: Tuple[int, int, int, int],
        tail_direction: str,
    ) -> None:
        """Draw a rounded speech bubble with a tail merged into the same shape.

        The bubble + tail are drawn as a single polygon so there's no visible
        seam where the tail meets the bubble body. We traverse the bubble in
        a clockwise order and detour out to the tail tip at the appropriate
        side, then return to the bubble edge before continuing around.
        """
        radius = 18
        cx1, cy1, cx2, cy2 = x1 + radius, y1 + radius, x2 - radius, y2 - radius

        tail_pts: List[Tuple[float, float]] = []
        if tail_direction == "down-left":
            tail_pts = [
                (x1 + bw * 0.30, y2),
                (x1 + bw * 0.20, y2 + 24),
                (x1 + bw * 0.08, y2 + 34),
                (x1 + bw * 0.12, y2),
            ]
        elif tail_direction == "down-right":
            tail_pts = [
                (x2 - bw * 0.12, y2),
                (x2 - bw * 0.08, y2 + 34),
                (x2 - bw * 0.20, y2 + 24),
                (x2 - bw * 0.30, y2),
            ]
        elif tail_direction == "up-left":
            tail_pts = [
                (x1 + bw * 0.12, y1),
                (x1 + bw * 0.08, y1 - 34),
                (x1 + bw * 0.20, y1 - 24),
                (x1 + bw * 0.30, y1),
            ]
        elif tail_direction == "up-right":
            tail_pts = [
                (x2 - bw * 0.30, y1),
                (x2 - bw * 0.20, y1 - 24),
                (x2 - bw * 0.08, y1 - 34),
                (x2 - bw * 0.12, y1),
            ]

        if tail_direction in ("down-left", "down-right"):
            pts: List[Tuple[float, float]] = [
                (cx1, y1),
                (cx2, y1),
                (x2, cy1),
                (x2, cy2),
                (cx2, y2),
            ]
            pts.extend(tail_pts)
            pts.append((cx1, y2))
            pts.append((x1, cy2))
            pts.append((x1, cy1))
        else:
            pts = [
                (cx1, y1),
            ]
            pts.extend(tail_pts)
            pts.append((x2, cy1))
            pts.append((x2, cy2))
            pts.append((cx2, y2))
            pts.append((cx1, y2))
            pts.append((x1, cy2))
            pts.append((x1, cy1))

        try:
            draw.polygon(pts, fill=fill, outline=border)
        except Exception:
            draw.rounded_rectangle(
                [x1, y1, x2, y2], radius=radius, fill=fill, outline=border
            )

    @staticmethod
    def _draw_jagged_burst_bubble(
        draw: ImageDraw.ImageDraw,
        x1: int,
        y1: int,
        x2: int,
        y2: int,
        fill: Tuple[int, int, int, int],
        border: Tuple[int, int, int, int],
        style_colors: Dict[str, Tuple[int, int, int, int]],
    ) -> None:
        """Draw a comic-book 'shout' / 'pow' burst bubble with jagged spikes."""
        cx = (x1 + x2) / 2
        cy = (y1 + y2) / 2
        bw = x2 - x1
        bh = y2 - y1
        spikes = max(18, int((bw + bh) / 16))
        pts: List[Tuple[float, float]] = []
        for i in range(spikes):
            t = i / spikes
            ang = t * 2 * math.pi
            rx = (bw / 2) * (1.05 if i % 2 == 0 else 0.78)
            ry = (bh / 2) * (1.05 if i % 2 == 0 else 0.78)
            pts.append((cx + rx * math.cos(ang), cy + ry * math.sin(ang)))
        try:
            draw.polygon(pts, fill=fill, outline=border)
        except Exception:
            draw.ellipse([x1, y1, x2, y2], fill=fill, outline=border)

    @staticmethod
    def _draw_sfx_text(
        draw: ImageDraw.ImageDraw,
        text: str,
        anchor: Tuple[int, int],
        font: ImageFont.ImageFont,
        fill: Tuple[int, int, int, int],
        panel_size: Tuple[int, int],
        angle_deg: float = -12.0,
    ) -> None:
        """Draw big bold SFX (sound effect) text with thick stroke, rotated."""
        iw, ih = panel_size
        if not text:
            return
        text = text.upper()
        try:
            from PIL import Image as _I

            txt_layer = _I.new("RGBA", (iw, ih), (0, 0, 0, 0))
            tdraw = ImageDraw.Draw(txt_layer)
            bbox = tdraw.textbbox((0, 0), text, font=font)
            tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
            tx = (iw - tw) // 2 - bbox[0]
            ty = (ih - th) // 2 - bbox[1]
            TextRenderService._draw_text_with_stroke(
                tdraw,
                (tx, ty),
                text,
                font,
                fill=fill,
                stroke_fill=(0, 0, 0, 255),
                stroke_width=4,
            )
            rotated = txt_layer.rotate(angle_deg, resample=Image.BICUBIC, expand=False)
            draw._image.alpha_composite(rotated)
        except Exception:
            pass

    def render_comic_panel(
        self,
        image_path: str,
        caption: Optional[str],
        speech: Optional[str],
        bubble_kind: str,
        bubble_quadrant: str = "top-right",
        bubble_tail: str = "down-left",
        bubble_style: str = "default",
        style_palette: Dict[str, Any] = None,
        panel_index: int = 1,
        panel_count: int = 1,
        font_candidates: Optional[List[str]] = None,
        border_width: int = 6,
        border_radius: int = 0,
        bubble_box_pct: Optional[Dict[str, float]] = None,
        caption_box_pct: Optional[Dict[str, float]] = None,
        narration_box_style: str = "default",
    ) -> bool:
        if style_palette is None:
            style_palette = {}
        if not os.path.exists(image_path):
            return False
        try:
            with Image.open(image_path).convert("RGBA") as image:
                draw = ImageDraw.Draw(image)
                iw, ih = image.size

                border_color = style_palette.get("border", "#0B0B0B")
                if isinstance(border_color, str) and border_color.startswith("#"):
                    border_rgba = (
                        int(border_color[1:3], 16),
                        int(border_color[3:5], 16),
                        int(border_color[5:7], 16),
                        255,
                    )
                else:
                    border_rgba = (11, 11, 11, 255)

                if border_radius > 0 and border_radius * 2 < min(iw, ih):
                    for i in range(border_width):
                        draw.rounded_rectangle(
                            [i, i, iw - 1 - i, ih - 1 - i],
                            radius=max(0, border_radius - i),
                            outline=border_rgba,
                        )
                else:
                    border_layer = self._panel_border_box(
                        iw, ih, border_rgba, border_width
                    )
                    image.alpha_composite(border_layer)

                caption_box_cfg = style_palette.get("caption_box", {})
                if caption:
                    cap_font_size = max(18, int(ih * 0.045))
                    font = self._load_bold_font(cap_font_size, font_candidates)
                    caption_colors = {
                        "fill": tuple(
                            caption_box_cfg.get("fill", (255, 250, 240, 235))
                        ),
                        "border": tuple(caption_box_cfg.get("border", border_rgba)),
                        "text": tuple(caption_box_cfg.get("text", (11, 11, 11, 255))),
                        "accent": tuple(
                            caption_box_cfg.get("accent", (255, 215, 0, 255))
                        ),
                    }

                    if narration_box_style == "manga_slab":
                        self._draw_caption_box_manga_slab(
                            draw, (iw, ih), caption, font, caption_colors
                        )
                    elif narration_box_style == "pixar_rounded":
                        self._draw_caption_box_pixar_rounded(
                            draw, (iw, ih), caption, font, caption_colors
                        )
                    elif narration_box_style == "superhero_block":
                        self._draw_caption_box_superhero_block(
                            draw, (iw, ih), caption, font, caption_colors
                        )
                    else:
                        if caption_box_pct:
                            box = self._pct_to_box(iw, ih, caption_box_pct)
                        else:
                            cap_h = max(60, int(ih * 0.13))
                            box = (
                                border_width,
                                border_width,
                                iw - border_width,
                                border_width + cap_h,
                            )
                        self._draw_caption_box(
                            draw,
                            box,
                            caption.upper(),
                            font,
                            padding=12,
                            style_colors=caption_colors,
                        )

                if speech:
                    bubble_colors_map = style_palette.get("bubble_colors", {})
                    bubble_cfg = bubble_colors_map.get(
                        bubble_kind, bubble_colors_map.get("speech", {})
                    )
                    bubble_fill = bubble_cfg.get("fill", (255, 255, 255, 250))
                    bubble_border = bubble_cfg.get("border", border_rgba)
                    bubble_text = bubble_cfg.get("text", (11, 11, 11, 255))

                    if bubble_box_pct:
                        bx = int(
                            max(0, min(100, bubble_box_pct.get("x", 50))) / 100.0 * iw
                        )
                        by = int(
                            max(0, min(100, bubble_box_pct.get("y", 20))) / 100.0 * ih
                        )
                        bw = int(
                            max(2, min(100, bubble_box_pct.get("w", 30))) / 100.0 * iw
                        )
                        bh = int(
                            max(2, min(100, bubble_box_pct.get("h", 20))) / 100.0 * ih
                        )
                        ax = bx + bw // 2
                        ay = by + bh // 2
                    elif bubble_quadrant == "top-right":
                        ax, ay = int(iw * 0.78), int(ih * 0.18)
                    elif bubble_quadrant == "top-left":
                        ax, ay = int(iw * 0.22), int(ih * 0.18)
                    elif bubble_quadrant == "bottom-right":
                        ax, ay = int(iw * 0.78), int(ih * 0.78)
                    else:
                        ax, ay = int(iw * 0.22), int(ih * 0.78)

                    font_size = max(20, int(ih * 0.055))
                    font = self._load_bold_font(font_size, font_candidates)
                    style_colors = {
                        "fill": tuple(bubble_fill),
                        "border": tuple(bubble_border),
                        "text": tuple(bubble_text),
                    }
                    self._draw_speech_bubble(
                        draw,
                        bubble_kind=bubble_kind,
                        anchor=(ax, ay),
                        text=speech,
                        font=font,
                        style_colors=style_colors,
                        panel_size=(iw, ih),
                        tail_direction=bubble_tail,
                        font_candidates=font_candidates,
                    )

                num_font = self._load_bold_font(
                    max(22, int(ih * 0.05)), font_candidates
                )
                num = f"{panel_index}"
                nb = draw.textbbox((0, 0), num, font=num_font)
                pad = 10
                circle_r = max(20, (nb[2] - nb[0]) // 2 + 14)
                cx = iw - border_width - circle_r - 12
                cy = ih - border_width - circle_r - 12
                draw.ellipse(
                    [cx - circle_r, cy - circle_r, cx + circle_r, cy + circle_r],
                    fill=(0, 0, 0, 220),
                    outline=(255, 255, 255, 220),
                )
                tx = cx - (nb[2] - nb[0]) // 2 - nb[0]
                ty = cy - (nb[3] - nb[1]) // 2 - nb[1]
                self._draw_text_with_stroke(
                    draw,
                    (tx, ty),
                    num,
                    num_font,
                    fill=(255, 255, 255, 255),
                    stroke_fill=(0, 0, 0, 220),
                    stroke_width=2,
                )

                image.convert("RGB").save(image_path)
            return True
        except Exception as e:
            print(f"Comic panel render error: {e}")
            return False

    def render_cover_overlays(
        self,
        image_path: str,
        title: str,
        subtitle: str,
        style_name: str,
        font_candidates: Optional[List[str]] = None,
        border_color: str = "#0B0B0B",
    ) -> bool:
        if not os.path.exists(image_path):
            return False
        try:
            with Image.open(image_path).convert("RGBA") as image:
                draw = ImageDraw.Draw(image)
                iw, ih = image.size

                if border_color.startswith("#"):
                    border_rgba = (
                        int(border_color[1:3], 16),
                        int(border_color[3:5], 16),
                        int(border_color[5:7], 16),
                        255,
                    )
                else:
                    border_rgba = (11, 11, 11, 255)

                border_w = max(8, int(iw * 0.012))
                border_layer = self._panel_border_box(iw, ih, border_rgba, border_w)
                image.alpha_composite(border_layer)

                top_h = int(ih * 0.22)
                bot_h = int(ih * 0.16)
                top_panel = Image.new("RGBA", (iw, top_h), (0, 0, 0, 170))
                bot_panel = Image.new("RGBA", (iw, bot_h), (0, 0, 0, 170))
                image.alpha_composite(top_panel, (0, 0))
                image.alpha_composite(bot_panel, (0, ih - bot_h))

                title_size = max(48, int(iw * 0.06))
                title_font = self._load_bold_font(title_size, font_candidates)
                title_text = (title or "YOUR COMIC").upper()
                lines = self._wrap_lines(draw, title_text, title_font, iw - 80)
                tb = draw.textbbox((0, 0), "Ag", font=title_font)
                line_h = (tb[3] - tb[1]) + 6
                ty = (top_h - line_h * len(lines)) // 2
                for ln in lines:
                    bb = draw.textbbox((0, 0), ln, font=title_font)
                    tx = (iw - (bb[2] - bb[0])) // 2
                    self._draw_text_with_stroke(
                        draw,
                        (tx, ty),
                        ln,
                        title_font,
                        fill=(255, 255, 255, 255),
                        stroke_fill=(0, 0, 0, 255),
                        stroke_width=3,
                    )
                    ty += line_h

                sub_size = max(24, int(iw * 0.028))
                sub_font = self._load_bold_font(sub_size, font_candidates)
                sub_text = (
                    f"{style_name} EDITION  -  {subtitle}".upper()
                    if subtitle
                    else f"{style_name} EDITION"
                )
                sub_lines = self._wrap_lines(draw, sub_text, sub_font, iw - 80)
                sb = draw.textbbox((0, 0), "Ag", font=sub_font)
                sub_line_h = (sb[3] - sb[1]) + 4
                sy = ih - bot_h + (bot_h - sub_line_h * len(sub_lines)) // 2
                for ln in sub_lines:
                    bb = draw.textbbox((0, 0), ln, font=sub_font)
                    tx = (iw - (bb[2] - bb[0])) // 2
                    self._draw_text_with_stroke(
                        draw,
                        (tx, sy),
                        ln,
                        sub_font,
                        fill=(255, 215, 0, 255),
                        stroke_fill=(0, 0, 0, 255),
                        stroke_width=2,
                    )
                    sy += sub_line_h

                image.convert("RGB").save(image_path)
            return True
        except Exception as e:
            print(f"Cover overlay error: {e}")
            return False


text_render_service = TextRenderService()
