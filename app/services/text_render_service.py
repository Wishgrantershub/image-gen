import os
from typing import Any, Dict, Optional

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


text_render_service = TextRenderService()
