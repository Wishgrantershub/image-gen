# Fonts module for ComicMe
# Provides cross-platform font resolution for text rendering

import os
from typing import Optional
from PIL import ImageFont


FONT_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__), "fonts")


def resolve_font(
    font_role: str,
    size: int,
    custom_candidates: Optional[list] = None
) -> ImageFont.ImageFont:
    """Resolve a font for the given role and size.

    Args:
        font_role: 'display' (superhero), 'friendly' (pixar), 'body' (manga)
        size: font size in pixels
        custom_candidates: optional list of custom font paths to try first

    Returns:
        A loaded PIL ImageFont.ImageFont instance.
    """
    search_paths: list[str] = []

    # Load bundled fonts first
    if os.path.exists(FONT_DIR):
        if font_role == "display":
            # Superhero: Bangers
            search_paths.append(os.path.join(FONT_DIR, "Bangers-Regular.ttf"))
        elif font_role == "friendly":
            # Pixar: Fredoka or Quicksand
            search_paths.extend([
                os.path.join(FONT_DIR, "Fredoka-Regular.ttf"),
                os.path.join(FONT_DIR, "Quicksand-Regular.ttf"),
            ])
        elif font_role == "body":
            # Manga: Noto Sans (or comic-like fonts)
            search_paths.extend([
                os.path.join(FONT_DIR, "NotoSans-Regular.ttf"),
            ])
        else:
            search_paths.append(os.path.join(FONT_DIR, "NotoSans-Regular.ttf"))

    # Fall back to Windows fonts
    search_paths.extend(custom_candidates or [
        "C:/Windows/Fonts/Bangers.ttf",
        "C:/Windows/Fonts/seguisb.ttf",
        "C:/Windows/Fonts/arialbd.ttf",
        "C:/Windows/Fonts/trebucbd.ttf",
        "C:/Windows/Fonts/segoeui.ttf",
        "C:/Windows/Fonts/comicbd.ttf",
        "C:/Windows/Fonts/comic.ttf",
        "C:/Windows/Fonts/impact.ttf",
    ])

    # Try to load fonts in order
    for font_path in search_paths:
        if os.path.exists(font_path):
            try:
                return ImageFont.truetype(font_path, size)
            except Exception as e:
                print(f"[Fonts] Failed to load {font_path}: {e}")
                continue

    # Last resort: load default font
    return ImageFont.load_default()


def load_display_font(size: int, custom: Optional[list] = None) -> ImageFont.ImageFont:
    """Load a display font for superhero styles."""
    return resolve_font("display", size, custom)


def load_friendly_font(size: int, custom: Optional[list] = None) -> ImageFont.ImageFont:
    """Load a friendly font for Pixar style."""
    return resolve_font("friendly", size, custom)


def load_body_font(size: int, custom: Optional[list] = None) -> ImageFont.ImageFont:
    """Load a body font for manga style."""
    return resolve_font("body", size, custom)
