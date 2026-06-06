from typing import Any, Dict, List


COMIC_STYLES: Dict[str, Dict[str, Any]] = {
    "manga": {
        "id": "manga",
        "name": "Manga",
        "tagline": "Black-and-white Japanese manga with speed lines and screentone",
        "description": "Inspired by Shonen Jump. Bold ink linework, dramatic speed lines, expressive eyes, and screentone shading. The hero stands tall in monochrome panels.",
        "emoji": "📕",
        "accent_color": "#1A1A1A",
        "preview_palette": ["#0A0A0A", "#F5F5DC", "#1A1A1A", "#8B0000", "#FFFFFF"],
        "style_suffix": (
            "Japanese manga panel, monochrome black and white, screentone halftone shading, "
            "bold ink linework, dynamic speed lines, dramatic impact lines, expressive large eyes, "
            "sharp angular features, motion blur on action, clean white gutters, "
            "professional shonen manga style, white background outside subject, "
            "do not include any text, letters, words, or speech bubbles in the image"
        ),
        "bubble_style": "manga",
        "border_color": "#0A0A0A",
        "border_width": 6,
        "panel_inner_padding": 18,
        "panel_layout": "2x3",
        "default_panel_count": 6,
        "palette": {
            "ink": "#0A0A0A",
            "paper": "#FAF7EE",
            "screentone": "#D9D6CB",
            "accent": "#B71C1C",
            "soft_white": "#FFFFFF",
        },
        "font_candidates": [
            "C:/Windows/Fonts/seguisb.ttf",
            "C:/Windows/Fonts/arialbd.ttf",
            "C:/Windows/Fonts/trebucbd.ttf",
            "C:/Windows/Fonts/segoeui.ttf",
        ],
        "caption_box": {
            "fill": (255, 255, 240, 235),
            "border": (10, 10, 10, 255),
            "text": (10, 10, 10, 255),
        },
        "bubble_colors": {
            "speech": {
                "fill": (255, 255, 255, 250),
                "border": (10, 10, 10, 255),
                "text": (10, 10, 10, 255),
            },
            "thought": {
                "fill": (245, 245, 235, 250),
                "border": (10, 10, 10, 255),
                "text": (10, 10, 10, 255),
            },
            "shout": {
                "fill": (255, 245, 235, 250),
                "border": (200, 30, 30, 255),
                "text": (60, 0, 0, 255),
            },
        },
        "sample_premises": [
            "discovers they can summon thunder by humming",
            "enters a tournament to become the strongest fighter",
            "teams up with a talking fox to find a lost village",
            "wakes up with mysterious glowing tattoos",
            "is chosen as the new guardian of an ancient forest",
        ],
    },
    "pixar": {
        "id": "pixar",
        "name": "Pixar",
        "tagline": "3D animated movie magic with soft cinematic lighting",
        "description": "Warm, expressive, and instantly lovable. Soft global illumination, big emotional eyes, and rich saturated colors. The kind of hero who would star in their own animated feature.",
        "emoji": "🎬",
        "accent_color": "#FF6B35",
        "preview_palette": ["#FF6B35", "#FFD166", "#06AED5", "#086788", "#F0F3BD"],
        "style_suffix": (
            "3D Pixar-style animated movie scene, soft cinematic lighting, "
            "expressive large eyes, rich saturated colors, subsurface skin scattering, "
            "rounded soft forms, beautiful depth of field, polished render, "
            "vibrant clean background, character illustration, "
            "do not include any text, letters, words, or speech bubbles in the image"
        ),
        "bubble_style": "pixar",
        "border_color": "#1F1B2E",
        "border_width": 5,
        "panel_inner_padding": 16,
        "panel_layout": "2x3",
        "default_panel_count": 6,
        "palette": {
            "warm": "#FF6B35",
            "gold": "#FFD166",
            "sky": "#06AED5",
            "deep": "#086788",
            "cream": "#FFF1D6",
        },
        "font_candidates": [
            "C:/Windows/Fonts/comicbd.ttf",
            "C:/Windows/Fonts/comic.ttf",
            "C:/Windows/Fonts/segoeui.ttf",
        ],
        "caption_box": {
            "fill": (255, 241, 214, 235),
            "border": (31, 27, 46, 255),
            "text": (31, 27, 46, 255),
        },
        "bubble_colors": {
            "speech": {
                "fill": (255, 255, 255, 250),
                "border": (31, 27, 46, 255),
                "text": (31, 27, 46, 255),
            },
            "thought": {
                "fill": (255, 247, 230, 250),
                "border": (255, 107, 53, 255),
                "text": (60, 30, 0, 255),
            },
            "shout": {
                "fill": (255, 220, 90, 250),
                "border": (200, 30, 30, 255),
                "text": (80, 0, 0, 255),
            },
        },
        "sample_premises": [
            "a small kid who befriends a giant cloud dragon",
            "a curious robot who wants to learn how to dream",
            "a young baker whose cupcakes grant wishes",
            "an astronaut who lands on a planet made of candy",
            "a shy musician whose guitar shoots rainbow sparks",
        ],
    },
    "superhero": {
        "id": "superhero",
        "name": "Superhero",
        "tagline": "Bold modern comic book with halftone dots and dynamic action",
        "description": "Inspired by Marvel and DC. Halftone Ben-Day dots, dramatic lighting, thick black inks, primary color splashes, and gravity-defying hero poses. Cape optional but encouraged.",
        "emoji": "⚡",
        "accent_color": "#E63946",
        "preview_palette": ["#E63946", "#1D3557", "#F1C40F", "#2ECC71", "#FFFFFF"],
        "style_suffix": (
            "modern American superhero comic book panel, bold thick black inking, "
            "halftone Ben-Day dots, dynamic action pose, dramatic lighting, "
            "vibrant primary colors, comic book cover composition, strong outlines, "
            "speed lines, energy bursts, vivid saturated palette, "
            "do not include any text, letters, words, or speech bubbles in the image"
        ),
        "bubble_style": "superhero",
        "border_color": "#0B0B0B",
        "border_width": 7,
        "panel_inner_padding": 18,
        "panel_layout": "2x3",
        "default_panel_count": 6,
        "palette": {
            "hero_red": "#E63946",
            "deep_navy": "#1D3557",
            "bolt_gold": "#F1C40F",
            "ink": "#0B0B0B",
            "paper": "#FFFAF0",
        },
        "font_candidates": [
            "C:/Windows/Fonts/impact.ttf",
            "C:/Windows/Fonts/seguisb.ttf",
            "C:/Windows/Fonts/arialbd.ttf",
        ],
        "caption_box": {
            "fill": (255, 250, 240, 235),
            "border": (11, 11, 11, 255),
            "text": (11, 11, 11, 255),
        },
        "bubble_colors": {
            "speech": {
                "fill": (255, 255, 255, 250),
                "border": (11, 11, 11, 255),
                "text": (11, 11, 11, 255),
            },
            "thought": {
                "fill": (215, 240, 255, 250),
                "border": (11, 11, 11, 255),
                "text": (20, 30, 60, 255),
            },
            "shout": {
                "fill": (255, 230, 60, 250),
                "border": (200, 30, 30, 255),
                "text": (60, 0, 0, 255),
            },
        },
        "sample_premises": [
            "gains the power of gravity and must save a falling city",
            "leads a team of misfit heroes against a cosmic villain",
            "discovers a suit that upgrades with every challenge",
            "races against time to stop a doomsday machine",
            "uncovers a hidden legacy as the city's last defender",
        ],
    },
}


TIER_CONFIG: Dict[str, Dict[str, Any]] = {
    "basic": {
        "id": "basic",
        "name": "Basic",
        "panel_count": 6,
        "panel_layout": "2x3",
        "price_inr": 99,
        "tagline": "6 panels, 1 vibe, instant PDF",
    },
    "premium": {
        "id": "premium",
        "name": "Premium",
        "panel_count": 12,
        "panel_layout": "3x4",
        "price_inr": 299,
        "tagline": "12 panels, all vibes, hero share link",
    },
    "deluxe": {
        "id": "deluxe",
        "name": "Deluxe",
        "panel_count": 24,
        "panel_layout": "4x6",
        "price_inr": 499,
        "tagline": "24 panels, printable PDF, watermark-free",
    },
}


def get_style(style_id: str) -> Dict[str, Any]:
    if style_id not in COMIC_STYLES:
        raise KeyError(f"Unknown comic style: {style_id}")
    return COMIC_STYLES[style_id]


def get_tier(tier_id: str) -> Dict[str, Any]:
    if tier_id not in TIER_CONFIG:
        raise KeyError(f"Unknown tier: {tier_id}")
    return TIER_CONFIG[tier_id]


def list_styles() -> List[Dict[str, Any]]:
    return [
        {
            "id": s["id"],
            "name": s["name"],
            "tagline": s["tagline"],
            "description": s["description"],
            "emoji": s["emoji"],
            "accent_color": s["accent_color"],
            "preview_palette": s["preview_palette"],
            "default_panel_count": s["default_panel_count"],
            "sample_premises": s["sample_premises"],
        }
        for s in COMIC_STYLES.values()
    ]


def list_tiers() -> List[Dict[str, Any]]:
    return [
        {
            "id": t["id"],
            "name": t["name"],
            "panel_count": t["panel_count"],
            "panel_layout": t["panel_layout"],
            "price_inr": t["price_inr"],
            "tagline": t["tagline"],
        }
        for t in TIER_CONFIG.values()
    ]
