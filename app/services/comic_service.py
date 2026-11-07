import io
import json
import logging
import os
import secrets
from typing import Any, Dict, List, Optional

import google.generativeai as genai
from sqlalchemy.orm import Session

from app.config import settings, COMIC_PANEL_DIR
from app.models import Book, Story, StoryPage, StoryStatus, Child
from app.services import ai_service
from app.services.comic_styles import COMIC_STYLES, TIER_CONFIG, get_style, get_tier
from app.services.page_template import load_layout, closest_gemini_aspect
from app.services.pdf_builder import build_hero_panel_cover, build_pdf
from app.services.text_render_service import text_render_service
from app.services.font_utils import resolve_story_fonts
import concurrent.futures


import random


def _generate_cool_title(hero_name: str, style_id: str, premise: str) -> str:
    """Generate a punchy comic-book title from the hero name + style + premise."""
    name = (hero_name or "Hero").strip() or "Hero"
    name_clean = name.split()[0]
    premise_words = [w for w in (premise or "").split() if len(w) > 4][:3]
    keyword = premise_words[0].capitalize() if premise_words else "Destiny"

    templates = [
        f"{name_clean} and the {keyword} Gambit",
        f"The {keyword} of {name_clean}",
        f"{name_clean}: {keyword} Unleashed",
        f"{name_clean} Rising",
        f"The Last {keyword}",
        f"{name_clean} vs. The {keyword}",
        f"Rise of {name_clean}",
        f"{name_clean} and the {keyword} Protocol",
        f"Shadow of {name_clean}",
        f"{name_clean}: A New Dawn",
    ]
    return random.choice(templates)


logger = logging.getLogger("comicme.comic_service")


BUBBLE_QUADRANTS = ["top-right", "top-left", "bottom-right", "bottom-left"]
BUBBLE_TAILS = ["down-left", "down-right", "up-left", "up-right"]


BEAT_TYPES = ("normal", "action", "quiet", "reveal", "climax")
BEAT_PRIORITY = {
    "climax": 5,
    "reveal": 4,
    "action": 3,
    "normal": 2,
    "quiet": 1,
}
ARC_BEAT_SEQUENCE = [
    "quiet",
    "action",
    "normal",
    "reveal",
    "climax",
    "quiet",
]


def _beat_for_panel(panel_index: int) -> str:
    """Return the beat type for a given 1-based panel index.

    The arc starts at panel 1 and rolls through ARC_BEAT_SEQUENCE. Panels
    beyond len(sequence) wrap around to the start, so a 12-panel story still
    has a coherent rising-and-falling shape.
    """
    if panel_index <= 0:
        return "normal"
    return ARC_BEAT_SEQUENCE[(panel_index - 1) % len(ARC_BEAT_SEQUENCE)]


def _dominant_beat(beats: List[str]) -> str:
    """Reduce a list of panel-beats to the one that should drive the page.

    Climax always wins. If two beats have the same priority, the earlier one
    in the arc is preferred (so a page that contains both a 'reveal' and a
    'climax' uses 'climax', but a page with a 'reveal' and a 'quiet' uses
    'reveal').
    """
    if not beats:
        return "normal"
    best = "normal"
    best_pri = 0
    for b in beats:
        pri = BEAT_PRIORITY.get(b, 0)
        if pri > best_pri:
            best = b
            best_pri = pri
    return best


def _page_beats_for_chunks(panel_beats: List[str], panels_per_page: int) -> List[str]:
    """Compute the dominant beat for each page-sized chunk of panel beats."""
    out: List[str] = []
    for i in range(0, max(1, len(panel_beats)), panels_per_page):
        chunk = panel_beats[i : i + panels_per_page]
        out.append(_dominant_beat(chunk) if chunk else "normal")
    return out


def _pick_cover_hero_panel(
    panel_paths: List[str],
    panel_beats: List[str],
) -> Optional[str]:
    """Pick the best single panel to use as a cover fallback background.

    We want the highest-priority beat in the arc — climax > reveal > action
    > normal > quiet. Ties are broken by the latest panel in the arc so the
    reader sees the resolution pose, not the opening one.
    """
    if not panel_paths:
        return None
    best_idx = 0
    best_pri = -1
    for i, beat in enumerate(panel_beats or ["normal"] * len(panel_paths)):
        pri = BEAT_PRIORITY.get(beat, 0)
        if pri >= best_pri and 0 <= i < len(panel_paths):
            best_pri = pri
            best_idx = i
    if 0 <= best_idx < len(panel_paths):
        return panel_paths[best_idx]
    return panel_paths[0]


class ComicGenerationService:
    def __init__(self):
        self.client: Any = None

    def initialize(self):
        if self.client is not None:
            return
        genai.configure(api_key=settings.GEMINI_API_KEY)
        self.client = genai.GenerativeModel(settings.GEMINI_TEXT_MODEL)
        print("Comic text service initialized")

    @staticmethod
    def _parse_json_text(raw_text: str) -> Optional[Any]:
        cleaned = (raw_text or "").strip()
        if cleaned.startswith("```json"):
            cleaned = cleaned[7:]
        if cleaned.startswith("```"):
            cleaned = cleaned[3:]
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3]
        cleaned = cleaned.strip()
        if not cleaned:
            return None
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            s = cleaned.find("{")
            e = cleaned.rfind("}")
            if s != -1 and e != -1 and e > s:
                try:
                    return json.loads(cleaned[s : e + 1])
                except json.JSONDecodeError:
                    return None
            return None

    def _generate_text_json(self, prompt: str, fallback: Any) -> Any:
        if self.client is None:
            self.initialize()
        if self.client is None:
            return fallback
        try:
            response = self.client.generate_content(prompt)
            parsed = self._parse_json_text((response.text or "").strip())
            return parsed if parsed is not None else fallback
        except Exception as e:
            print(f"Comic text JSON error: {e}")
            return fallback

    def _update_progress(
        self,
        db: Session,
        story: Story,
        step: str,
        message: str,
        pct: int,
    ) -> None:
        try:
            story.progress_step = step
            story.progress_message = message
            story.progress_pct = pct
            db.commit()
            logger.info(
                '[comic_svc] story=%s step=%s pct=%s msg="%s"',
                story.id,
                step,
                pct,
                message,
            )
        except Exception as e:
            logger.warning(
                "[comic_svc] progress update failed story=%s: %s", story.id, e
            )
            db.rollback()

    def _generate_panel_script(
        self,
        name: str,
        premise: str,
        style_name: str,
        style_tagline: str,
        panel_count: int,
    ) -> List[Dict[str, Any]]:
        setup_end = max(1, int(panel_count * 0.2))
        incite_end = max(setup_end + 1, int(panel_count * 0.4))
        climax_start = max(incite_end + 1, int(panel_count * 0.7))
        resolution_start = max(climax_start + 1, int(panel_count * 0.9))

        prompt = f"""
You are writing an authentic, engaging {panel_count}-panel comic book script starring {name}.

Premise: {premise}
Style: {style_name} ({style_tagline})

Story arc (scaled to {panel_count} panels):
- Panels 1-{setup_end}: SETUP — introduce {name} in action or routine, establishing character and tone
- Panels {setup_end + 1}-{incite_end}: INCITING INCIDENT — a sudden disruption, clue, alarm, or twist
- Panels {incite_end + 1}-{climax_start - 1}: RISING ACTION — confrontation, pursuit, struggle, teamwork, or realization
- Panels {climax_start}-{resolution_start - 1}: CLIMAX — the highest peak of action, power unleashing, or decisive move
- Panels {resolution_start}-{panel_count}: RESOLUTION — victorious finish, playful punchline, signature hero pose, or closing wink

COMIC LETTERING & DIALOGUE RULES (CRITICAL):
1. REAL COMIC PACING: A real comic panel is NOT a silent screenshot with movie-trailer narration. In nearly every panel, {name} (or an adversary/companion) is actively TALKING, THINKING, or YELLING.
2. SPEECH OVER CAPTIONS: Give at least 80% of panels direct character speech or thought bubbles.
3. AUTHENTIC COMIC BANTER: Characters speak with vivid emotion, attitude, grit, or humor. Use comic expressions, questions, mid-action gasps, and punchy comebacks:
   - "Wait — did you hear that?!"
   - "Hold on tight, this is gonna get bumpy!"
   - "Not on my watch!"
   - "Aha! I knew that signal was coming from here."
   - "Did anyone get the license plate on that boulder?!"
   - "System breached... we're in."
4. CAPTIONS ARE FOR SETTING & TIME ONLY:
   - GOOD caption: "Downtown Neo-City. 02:40 AM." or "Deep beneath the vault..." or "Seconds later..."
   - BAD caption: "Until the past starts screaming." or "He felt angry." (Never use captions to replace character voice or monologue!)
   - If no location/time jump is needed in a panel, set "caption": ""
5. LENGTH & PUNCTUATION:
   - Speech: 3 to 12 words max. Punchy and readable.
   - Caption: 2 to 6 words max (or empty string).
   - Use dynamic punctuation: exclamation marks (!), em-dashes (—), question marks (?), ellipsis (...).

For each panel output EXACTLY this JSON:
{{
  "description": "1-2 vivid sentences describing the scene, character action, background, camera angle, and lighting. Third person, present tense. NO mention of text or speech bubbles. Keep physical hand/finger poses clear and simple.",
  "caption": "A concise scene-setting tag (e.g. 'Sector 7. Midnight.') OR empty string '' if not needed",
  "speech": "Punchy line of character dialogue or thought in {name}'s voice (3-12 words) OR empty string ''",
  "bubble_kind": "speech" | "thought" | "shout" | "none",
  "camera": "one of: close-up | medium | wide | extreme-wide | overhead | low-angle",
  "mood": "one of: tense | joyful | mysterious | dramatic | triumphant | sad | epic | funny"
}}

Hard rules:
- Output ONLY a JSON array of exactly {panel_count} objects, no markdown.
- At least {max(1, panel_count - 1)} panels MUST have a non-empty "speech".
- Vary the camera angle between panels (no two adjacent panels share the same camera).
- Never mention 'speech bubble', 'caption', or 'text' inside 'description'.
- The final panel must land with a memorable hero pose, funny wrap-up, or triumphant one-liner.
""".strip()

        fallback_panels: List[Dict[str, Any]] = []
        cameras = [
            "wide",
            "medium",
            "close-up",
            "low-angle",
            "overhead",
            "extreme-wide",
        ]
        moods = ["mysterious", "joyful", "tense", "dramatic", "triumphant", "epic"]
        for i in range(panel_count):
            fallback_panels.append(
                {
                    "description": (
                        f"{name} stands in a {style_name.lower()} world, looking determined. "
                        f"Panel {i + 1} of a {panel_count}-panel story."
                    ),
                    "caption": "",
                    "speech": "This is my moment!" if i == 0 else "",
                    "bubble_kind": "speech" if i == 0 else "none",
                    "camera": cameras[i % len(cameras)],
                    "mood": moods[i % len(moods)],
                }
            )

        parsed = self._generate_text_json(prompt, fallback_panels)
        if not isinstance(parsed, list):
            return fallback_panels
        out: List[Dict[str, Any]] = []
        for i in range(panel_count):
            if i < len(parsed) and isinstance(parsed[i], dict):
                merged = {**fallback_panels[i], **parsed[i]}
                out.append(merged)
            else:
                out.append(fallback_panels[i])

        for panel in out:
            cap = (panel.get("caption") or "").strip()
            speech = (panel.get("speech") or "").strip()
            if cap and speech and len(cap) > 15 and len(speech) > 15:
                if len(speech) >= len(cap):
                    panel["caption"] = ""
                else:
                    panel["speech"] = ""
                    if panel.get("bubble_kind") in ("speech", "thought", "shout"):
                        panel["bubble_kind"] = "none"
        return out

    def _resolve_bubble_layout(
        self, panel_index: int, panel_count: int, bubble_kind: str
    ) -> Dict[str, str]:
        if bubble_kind not in {"speech", "thought", "shout"}:
            return {"quadrant": "top-right", "tail": "down-left"}
        quadrant = BUBBLE_QUADRANTS[panel_index % 4]
        tail = BUBBLE_TAILS[panel_index % 4]
        return {"quadrant": quadrant, "tail": tail}

    def _get_narration_box_style(self, style_id: str, tier_id: str) -> str:
        try:
            layout = load_layout(style_id, tier_id)
            return layout.get("narration_box_style", "default") or "default"
        except Exception:
            return "default"

    def generate_comic(
        self,
        db: Session,
        story: Story,
        child: Child,
        book: Book,
        style_id: str,
        tier_id: str,
    ) -> bool:
        try:
            logger.info(
                '[comic_svc] story=%s START style=%s tier=%s child="%s"',
                story.id,
                style_id,
                tier_id,
                child.name,
            )
            self.initialize()
            ai_service.image_generation_service.initialize()
            ai_service.face_prep_service.initialize()

            style = get_style(style_id)
            tier = get_tier(tier_id)
            panel_count = tier["panel_count"]
            panel_layout = tier["panel_layout"]

            story.panel_count = panel_count
            story.panel_layout = panel_layout
            story.tier = tier_id
            story.status = StoryStatus.GENERATING
            story.progress_pct = 1
            story.progress_step = "init"
            story.progress_message = "Starting comic generation..."
            db.commit()

            if not child.photo_path or not os.path.exists(child.photo_path):
                story.status = StoryStatus.DRAFT
                story.error_message = "Child photo missing"
                db.commit()
                return False

            self._update_progress(db, story, "script", "Writing the script...", 8)

            script = self._generate_panel_script(
                name=child.name,
                premise=(
                    story.premise or "an everyday hero on an unexpected adventure"
                ),
                style_name=style["name"],
                style_tagline=style["tagline"],
                panel_count=panel_count,
            )
            story.generated_text = json.dumps(
                {"script": script, "style_id": style_id, "tier_id": tier_id},
                ensure_ascii=True,
            )
            db.commit()

            for existing in list(story.pages):
                db.delete(existing)
            db.commit()

            self._update_progress(
                db,
                story,
                "identity_sheet",
                f"Drawing {child.name}'s character sheet...",
                18,
            )
            identity_sheet = (
                ai_service.image_generation_service.generate_comic_identity_sheet(
                    child_photo_path=child.photo_path,
                    style_suffix=style["style_suffix"],
                    style_name=style["name"],
                )
            )
            identity_sheet_path: Optional[str] = None
            if identity_sheet is not None:
                identity_sheet_path = (
                    ai_service.image_generation_service.save_comic_sheet(
                        identity_sheet, f"comic_{story.id}_identity_sheet.png"
                    )
                )

            self._update_progress(
                db,
                story,
                "face_anchor",
                f"Locking {child.name}'s look for every panel...",
                22,
            )
            try:
                face_desc = (
                    ai_service.image_generation_service.extract_face_description(
                        child.photo_path
                    )
                )
            except Exception as e:
                print(f"[ComicService] face_description failed: {e}")
                face_desc = ""

            outfit_hints = {
                "manga": "wearing a distinctive dark high-collar combat jacket with clean white undershirt",
                "pixar": "wearing a vibrant warm-toned hoodie with rolled sleeves and comfortable denim",
                "superhero": "wearing a modern hero suit with bold chest emblem and streamlined trim",
            }
            chosen_outfit = outfit_hints.get(
                style["id"], "wearing a signature jacket with consistent colors"
            )
            if face_desc:
                full_character_anchor = (
                    f"{face_desc}. Signature outfit across all panels: {chosen_outfit}."
                )
            else:
                full_character_anchor = f"{child.name}, {chosen_outfit}."

            story.face_description = full_character_anchor
            db.commit()

            panel_paths: List[str] = []
            panel_beats: List[str] = []
            previous_panel_path: Optional[str] = None

            try:
                panel_layout_cfg = load_layout(style["id"], tier_id)
                panel_cells = panel_layout_cfg.get("panels", [])
            except Exception:
                panel_cells = []

            def _aspect_for_panel(panel_idx: int) -> str:
                if panel_idx - 1 < len(panel_cells):
                    cell = panel_cells[panel_idx - 1]
                    return closest_gemini_aspect(
                        int(cell.get("w", 0)), int(cell.get("h", 0))
                    )
                return "4:3"

            base_pct = 22
            span = 55
            per_panel = span / max(1, panel_count)

            # Resolve story-driven typography based on story genre/mood and description
            story_context_text = f"{story.title or ''} {story.premise or ''} {' '.join(p.get('description', '') for p in script)}"
            story_fonts = resolve_story_fonts(
                style_id=style["id"],
                story_text=story_context_text,
                role="body",
            )

            # Extract primitive values so concurrent worker threads NEVER touch SQLAlchemy objects or sessions
            child_photo_str = str(child.photo_path) if (child and child.photo_path) else None
            face_desc_str = str(story.face_description or "")
            story_id_int = story.id
            child_name_str = child.name if child else "Hero"

            # Worker function for parallel image generation (runs purely network/image tasks, no DB access)
            def _generate_single_panel_image(p_idx: int, p_data: dict):
                p_desc = p_data.get("description", "").strip()
                p_bubble_layout = self._resolve_bubble_layout(
                    p_idx - 1, panel_count, p_data.get("bubble_kind", "speech")
                )
                p_aspect = _aspect_for_panel(p_idx)
                p_best_path: Optional[str] = None

                for attempt in range(1, settings.COMIC_MAX_RETRIES + 1):
                    panel_img = (
                        ai_service.image_generation_service.generate_comic_panel(
                            panel_description=p_desc,
                            child_photo_path=child_photo_str,
                            identity_sheet_path=identity_sheet_path,
                            style_suffix=style["style_suffix"],
                            style_name=style["name"],
                            panel_index=p_idx,
                            panel_count=panel_count,
                            bubble_quadrant=p_bubble_layout["quadrant"],
                            previous_panel_path=None,
                            character_description=face_desc_str,
                            panel_aspect=p_aspect,
                        )
                    )
                    if panel_img is not None:
                        panel_filename = f"comic_{story_id_int}_panel_{p_idx}_attempt_{attempt}.png"
                        p_best_path = ai_service.image_generation_service.save_comic_panel(
                            panel_img, panel_filename
                        )
                        break

                if p_best_path is None:
                    print(f"[ComicService] Panel {p_idx} Nano Banana failed — trying Imagen fallback")
                    try:
                        imagen_img = ai_service.image_generation_service.generate_comic_panel_with_imagen(
                            panel_description=p_desc,
                            child_photo_path=child_photo_str,
                            style_suffix=style["style_suffix"],
                            style_name=style["name"],
                            panel_index=p_idx,
                            panel_count=panel_count,
                            aspect_ratio=p_aspect,
                            character_description=face_desc_str,
                        )
                        if imagen_img is not None:
                            p_best_path = ai_service.image_generation_service.save_comic_panel(
                                imagen_img,
                                f"comic_{story_id_int}_panel_{p_idx}_imagen.png",
                            )
                            print(f"[ComicService] Panel {p_idx} saved via Imagen fallback")
                    except Exception as e:
                        print(f"[ComicService] Imagen fallback error for panel {p_idx}: {e}")

                return p_idx, p_best_path, p_data, p_bubble_layout, p_aspect

            # Clean user-facing progress message (no technical jargon)
            self._update_progress(
                db,
                story,
                "drawing_panels",
                f"Drawing panel 1 of {panel_count}...",
                base_pct,
            )

            completed_panels = 0

            # Execute generation in parallel with 3 workers
            with concurrent.futures.ThreadPoolExecutor(max_workers=min(3, panel_count)) as executor:
                future_to_idx = {
                    executor.submit(_generate_single_panel_image, idx, p_data): idx
                    for idx, p_data in enumerate(script, start=1)
                }
                for future in concurrent.futures.as_completed(future_to_idx):
                    idx = future_to_idx[future]
                    try:
                        idx, best_panel_path, panel_data, bubble_layout, panel_aspect = future.result()
                    except Exception as exc:
                        print(f"[ComicService] Panel {idx} worker raised: {exc}")
                        best_panel_path = None
                        panel_data = script[idx - 1]
                        bubble_layout = self._resolve_bubble_layout(
                            idx - 1, panel_count, panel_data.get("bubble_kind", "speech")
                        )
                        panel_aspect = _aspect_for_panel(idx)

                    if best_panel_path is None:
                        from PIL import Image as PILImage, ImageDraw as PILDraw
                        ph = PILImage.new(
                            "RGB",
                            (settings.COMIC_PANEL_WIDTH, settings.COMIC_PANEL_HEIGHT),
                            (210, 210, 210),
                        )
                        pd = PILDraw.Draw(ph)
                        pd.rectangle(
                            [6, 6, settings.COMIC_PANEL_WIDTH - 7, settings.COMIC_PANEL_HEIGHT - 7],
                            outline=(0, 0, 0),
                            width=6,
                        )
                        placeholder_filename = f"comic_{story_id_int}_panel_{idx}_placeholder.png"
                        placeholder_path = os.path.join(COMIC_PANEL_DIR, placeholder_filename)
                        ph.save(placeholder_path)
                        best_panel_path = placeholder_path

                    final_panel_filename = f"comic_{story_id_int}_panel_{idx}.png"
                    final_panel_path = os.path.join(
                        os.path.dirname(best_panel_path), final_panel_filename
                    )
                    if best_panel_path != final_panel_path:
                        if os.path.exists(final_panel_path):
                            try:
                                os.remove(final_panel_path)
                            except OSError:
                                pass
                        os.replace(best_panel_path, final_panel_path)

                    speech_text = panel_data.get("speech", "") or ""
                    caption_text = panel_data.get("caption", "") or ""
                    bubble_layout_decision: Dict[str, Any] = {
                        "bubble_box": None,
                        "caption_box": None,
                        "bubble_kind": panel_data.get("bubble_kind", "speech"),
                        "tail_direction": bubble_layout["tail"],
                    }
                    if speech_text or caption_text:
                        try:
                            layout_decision = (
                                ai_service.image_generation_service.analyze_panel_layout(
                                    panel_image_path=final_panel_path,
                                    speech_text=speech_text,
                                    caption_text=caption_text,
                                )
                            )
                            bubble_layout_decision.update(layout_decision)
                        except Exception as e:
                            print(
                                f"[ComicService] panel layout analysis failed for {final_panel_path}: {e}"
                            )

                    resolved_kind = bubble_layout_decision.get(
                        "bubble_kind"
                    ) or panel_data.get("bubble_kind", "speech")
                    resolved_tail = (
                        bubble_layout_decision.get("tail_direction")
                        or bubble_layout["tail"]
                    )
                    narration_style = self._get_narration_box_style(style["id"], tier_id)
                    try:
                        layout_cfg = load_layout(style["id"], tier_id)
                        border_radius = int(layout_cfg.get("panel_border_radius", 0))
                        show_badge = bool(layout_cfg.get("show_panel_number_badge", True))
                    except Exception:
                        border_radius = 0
                        show_badge = True

                    try:
                        text_render_service.render_comic_panel(
                            image_path=final_panel_path,
                            caption=caption_text,
                            speech=speech_text,
                            bubble_kind=resolved_kind,
                            bubble_quadrant=bubble_layout["quadrant"],
                            bubble_tail=resolved_tail,
                            bubble_style=style["bubble_style"],
                            style_palette={
                                "border": style["border_color"],
                                "caption_box": style["caption_box"],
                                "bubble_colors": style["bubble_colors"],
                            },
                            panel_index=idx,
                            panel_count=panel_count,
                            font_candidates=story_fonts,
                            border_width=style.get("border_width", 6),
                            border_radius=border_radius,
                            bubble_box_pct=bubble_layout_decision.get("bubble_box"),
                            caption_box_pct=bubble_layout_decision.get("caption_box"),
                            narration_box_style=narration_style,
                            show_panel_number_badge=show_badge,
                        )
                    except Exception as e:
                        print(f"[ComicService] render_comic_panel error for panel {idx}: {e}")

                    # Immediately insert StoryPage into DB so modal can stream panel preview live
                    description = panel_data.get("description", "").strip()
                    page = StoryPage(
                        story_id=story.id,
                        page_number=idx,
                        text=(
                            f"[CAPTION] {caption_text}\n"
                            f"[SPEECH] {speech_text}"
                        ),
                        image_prompt=description,
                        image_path=final_panel_path,
                        is_preview=1,
                        gen_status="ok",
                        gen_notes=panel_aspect,
                    )
                    db.add(page)
                    db.commit()

                    completed_panels += 1
                    pct = int(base_pct + (completed_panels / panel_count) * (span * 0.75))
                    self._update_progress(
                        db,
                        story,
                        f"panel_{completed_panels}",
                        f"Drawing panel {min(panel_count, completed_panels + 1)} of {panel_count}...",
                        pct,
                    )

            # Collect all ordered panels for cover and PDF generation
            ordered_pages = (
                db.query(StoryPage)
                .filter(StoryPage.story_id == story.id)
                .order_by(StoryPage.page_number.asc())
                .all()
            )
            panel_paths = [p.image_path for p in ordered_pages if p.image_path and os.path.exists(p.image_path)]
            previous_panel_path = panel_paths[-1] if panel_paths else None
            panel_beats = [_beat_for_panel(p.page_number) for p in ordered_pages]

            self._update_progress(db, story, "cover", "Painting the cover...", 82)
            cover_image = ai_service.image_generation_service.generate_cover_image(
                child_photo_path=child.photo_path,
                identity_sheet_path=identity_sheet_path,
                style_suffix=style["style_suffix"],
                style_name=style["name"],
                title=story.title or f"{child.name}'s Adventure",
                subtitle=f"A {style['name']} tale",
            )
            cover_path: Optional[str] = None
            cover_hero_panel: Optional[str] = None
            cover_kind: str = "ai"
            if cover_image is not None:
                cover_path = ai_service.image_generation_service.save_comic_panel(
                    cover_image, f"comic_{story.id}_cover.png"
                )
                story.cover_path = cover_path
                db.commit()
            else:
                cover_hero_panel = _pick_cover_hero_panel(panel_paths, panel_beats)
                cover_kind = "hero_panel" if cover_hero_panel else "typography"
                if cover_hero_panel:
                    cover_path = ai_service.image_generation_service.save_comic_panel(
                        build_hero_panel_cover(
                            cover_hero_panel,
                            paper_hex="#FAF7EE",
                            border_hex=style["border_color"],
                        ),
                        f"comic_{story.id}_cover.png",
                    )
                    story.cover_path = cover_path
                    db.commit()

            if cover_path is not None:
                text_render_service.render_cover_overlays(
                    image_path=cover_path,
                    title=story.title or f"{child.name}'s Adventure",
                    subtitle=f"starring {child.name}",
                    style_name=style["name"],
                    font_candidates=style.get("font_candidates"),
                    border_color=style["border_color"],
                    style_id=style["id"],
                )
            if cover_path is None:
                story.cover_path = None
                db.commit()
                print(
                    f"[ComicService] Cover generation failed for story {story.id} "
                    f"({cover_kind}); PDF will use typography cover."
                )

            self._update_progress(db, story, "pdf", "Binding the PDF...", 92)
            share_url = f"https://comicme.app/c/{story.share_token or story.id}"
            try:
                page_layout_cfg = load_layout(style["id"], tier_id)
                panels_per_page = len(page_layout_cfg.get("panels", [])) or panel_count
            except Exception:
                panels_per_page = panel_count or 6
            page_beats = _page_beats_for_chunks(panel_beats, panels_per_page)
            pdf_path = build_pdf(
                panel_paths=panel_paths,
                cover_path=cover_path,
                title=story.title or f"{child.name}'s Adventure",
                style_name=style["name"],
                share_url=share_url,
                layout=panel_layout,
                paper_hex="#FAF7EE",
                border_hex=style["border_color"],
                font_candidates=style.get("font_candidates"),
                output_filename=f"comic_{story.id}.pdf",
                style_id=style["id"],
                tier_id=tier_id,
                page_beats=page_beats,
            )
            if not os.path.exists(pdf_path) or os.path.getsize(pdf_path) == 0:
                raise RuntimeError(
                    f"PDF build produced empty file for story {story.id}"
                )
            story.pdf_path = pdf_path
            if story.paid_at is not None or not settings.RAZORPAY_ENABLED:
                story.status = StoryStatus.PURCHASED
            else:
                story.status = StoryStatus.PREVIEW_READY
            story.preview_generated = 1
            story.progress_pct = 100
            story.progress_step = "done"
            story.progress_message = "Your comic is ready!"
            db.commit()

            try:
                from app.services.storage import get_storage

                storage = get_storage()
                logger.info(
                    "[comic_svc] story=%s PDF built at %s — uploading via %s backend",
                    story.id,
                    pdf_path,
                    storage.backend_name,
                )
                storage_key = storage.save(story.id, pdf_path)
                story.pdf_storage_key = storage_key
                if storage.backend_name != "local":
                    dl = storage.get_download_url(story.id)
                    if dl:
                        story.pdf_storage_url = dl
                db.commit()
                logger.info(
                    "[comic_svc] story=%s DONE backend=%s storage_key=%s",
                    story.id,
                    storage.backend_name,
                    storage_key,
                )
            except Exception as e:
                logger.warning(
                    "[comic_svc] story=%s PDF storage upload failed: %s",
                    story.id,
                    e,
                )

            try:
                from app.services.email_service import send_comic_email

                recipient = story.customer_email or (
                    child.user.email if child and child.user else None
                )
                is_dummy = (
                    not recipient
                    or "@" not in recipient
                    or recipient.endswith(".local")
                    or recipient.endswith("@comicme.local")
                    or recipient.startswith("guest+")
                    or "@example.com" in recipient
                )
                if not is_dummy:
                    share_link = (
                        f"https://comicme.app/c/{story.share_token or story.id}"
                    )
                    sent = send_comic_email(
                        to_email=recipient,
                        hero_name=child.name if child else "Hero",
                        title=story.title or "Your Comic",
                        style_name=style["name"],
                        share_url=share_link,
                        pdf_path=pdf_path,
                    )
                    if sent:
                        logger.info(
                            "[comic_svc] story=%s email sent to %s",
                            story.id,
                            recipient,
                        )
                    else:
                        logger.warning(
                            "[comic_svc] story=%s email delivery failed to %s",
                            story.id,
                            recipient,
                        )
                else:
                    logger.info(
                        "[comic_svc] story=%s email skipped (guest/placeholder: %s)",
                        story.id,
                        recipient,
                    )
            except Exception as e:
                logger.warning(
                    "[comic_svc] story=%s email send failed: %s", story.id, e
                )
            return True
        except Exception as e:
            logger.error(
                "[comic_svc] story=%s FAILED: %s",
                getattr(story, "id", "?"),
                e,
                exc_info=True,
            )
            try:
                story.status = StoryStatus.DRAFT
                story.error_message = str(e)
                story.progress_step = "error"
                story.progress_message = f"Error: {e}"
                db.commit()
            except Exception:
                db.rollback()
            return False

    def build_sample_comic(
        self,
        db: Session,
        sample_id: str,
        child_photo_path: str,
        child_name: str,
        premise: str,
        style_id: str,
        tier_id: str,
    ) -> Optional[str]:
        """Generate a sample comic on the fly, used for the landing page gallery."""
        try:
            self.initialize()
            ai_service.image_generation_service.initialize()
            style = get_style(style_id)
            tier = get_tier(tier_id)
            panel_count = tier["panel_count"]
            panel_layout = tier["panel_layout"]

            script = self._generate_panel_script(
                name=child_name,
                premise=premise,
                style_name=style["name"],
                style_tagline=style["tagline"],
                panel_count=panel_count,
            )

            identity_sheet = (
                ai_service.image_generation_service.generate_comic_identity_sheet(
                    child_photo_path=child_photo_path,
                    style_suffix=style["style_suffix"],
                    style_name=style["name"],
                )
            )
            identity_sheet_path: Optional[str] = None
            if identity_sheet is not None:
                identity_sheet_path = (
                    ai_service.image_generation_service.save_comic_sheet(
                        identity_sheet, f"sample_{sample_id}_identity_sheet.png"
                    )
                )

            try:
                sample_face_desc = (
                    ai_service.image_generation_service.extract_face_description(
                        child_photo_path
                    )
                )
            except Exception as e:
                print(f"[ComicService.sample] face_description failed: {e}")
                sample_face_desc = ""

            panel_paths: List[str] = []
            panel_beats: List[str] = []
            previous_panel_path: Optional[str] = None
            for idx, panel_data in enumerate(script, start=1):
                bubble_layout = self._resolve_bubble_layout(
                    idx - 1, panel_count, panel_data.get("bubble_kind", "speech")
                )
                panel_img = ai_service.image_generation_service.generate_comic_panel(
                    panel_description=panel_data.get("description", ""),
                    child_photo_path=child_photo_path,
                    identity_sheet_path=identity_sheet_path,
                    style_suffix=style["style_suffix"],
                    style_name=style["name"],
                    panel_index=idx,
                    panel_count=panel_count,
                    bubble_quadrant=bubble_layout["quadrant"],
                    previous_panel_path=previous_panel_path,
                    character_description=sample_face_desc or "",
                )
                if panel_img is None:
                    return None
                panel_path = ai_service.image_generation_service.save_comic_panel(
                    panel_img, f"sample_{sample_id}_panel_{idx}.png"
                )
                speech_text = panel_data.get("speech", "") or ""
                caption_text = panel_data.get("caption", "") or ""
                bubble_decision: Dict[str, Any] = {
                    "bubble_box": None,
                    "caption_box": None,
                    "bubble_kind": panel_data.get("bubble_kind", "speech"),
                    "tail_direction": bubble_layout["tail"],
                }
                if speech_text:
                    try:
                        bubble_decision.update(
                            ai_service.image_generation_service.analyze_panel_layout(
                                panel_path, speech_text, caption_text
                            )
                        )
                    except Exception as e:
                        print(
                            f"[ComicService.sample] panel layout analysis failed: {e}"
                        )
                resolved_kind = bubble_decision.get("bubble_kind") or panel_data.get(
                    "bubble_kind", "speech"
                )
                resolved_tail = (
                    bubble_decision.get("tail_direction") or bubble_layout["tail"]
                )
                narration_style = self._get_narration_box_style(style["id"], tier_id)
                try:
                    sample_layout_cfg = load_layout(style["id"], tier_id)
                    sample_border_radius = int(
                        sample_layout_cfg.get("panel_border_radius", 0)
                    )
                except Exception:
                    sample_border_radius = 0

                text_render_service.render_comic_panel(
                    image_path=panel_path,
                    caption=caption_text,
                    speech=speech_text,
                    bubble_kind=resolved_kind,
                    bubble_quadrant=bubble_layout["quadrant"],
                    bubble_tail=resolved_tail,
                    bubble_style=style["bubble_style"],
                    style_palette={
                        "border": style["border_color"],
                        "caption_box": style["caption_box"],
                        "bubble_colors": style["bubble_colors"],
                    },
                    panel_index=idx,
                    panel_count=panel_count,
                    font_candidates=style.get("font_candidates"),
                    border_width=style.get("border_width", 6),
                    border_radius=sample_border_radius,
                    bubble_box_pct=bubble_decision.get("bubble_box"),
                    caption_box_pct=bubble_decision.get("caption_box"),
                    narration_box_style=narration_style,
                )
                panel_paths.append(panel_path)
                previous_panel_path = panel_path
                panel_beats.append(_beat_for_panel(idx))

            cover_path: Optional[str] = None
            cover_image = ai_service.image_generation_service.generate_cover_image(
                child_photo_path=child_photo_path,
                identity_sheet_path=identity_sheet_path,
                style_suffix=style["style_suffix"],
                style_name=style["name"],
                title=f"{child_name}'s Adventure",
                subtitle=f"starring {child_name}",
            )
            if cover_image is not None:
                cover_path = ai_service.image_generation_service.save_comic_panel(
                    cover_image, f"sample_{sample_id}_cover.png"
                )
            else:
                hero_panel = _pick_cover_hero_panel(panel_paths, panel_beats)
                if hero_panel:
                    cover_path = ai_service.image_generation_service.save_comic_panel(
                        build_hero_panel_cover(
                            hero_panel,
                            paper_hex="#FAF7EE",
                            border_hex=style["border_color"],
                        ),
                        f"sample_{sample_id}_cover.png",
                    )

            if cover_path is not None:
                text_render_service.render_cover_overlays(
                    image_path=cover_path,
                    title=f"{child_name}'s Adventure",
                    subtitle=f"starring {child_name}",
                    style_name=style["name"],
                    font_candidates=style.get("font_candidates"),
                    border_color=style["border_color"],
                    style_id=style["id"],
                )

            try:
                sample_page_cfg = load_layout(style["id"], tier_id)
                sample_panels_per_page = (
                    len(sample_page_cfg.get("panels", [])) or panel_count
                )
            except Exception:
                sample_panels_per_page = panel_count or 6
            sample_page_beats = _page_beats_for_chunks(
                panel_beats, sample_panels_per_page
            )
            pdf_path = build_pdf(
                panel_paths=panel_paths,
                cover_path=cover_path,
                title=f"{child_name}'s Adventure",
                style_name=style["name"],
                share_url=f"https://comicme.app/c/{sample_id}",
                layout=panel_layout,
                paper_hex="#FAF7EE",
                border_hex=style["border_color"],
                font_candidates=style.get("font_candidates"),
                output_filename=f"sample_{sample_id}.pdf",
                style_id=style["id"],
                tier_id=tier_id,
                page_beats=sample_page_beats,
            )
            return pdf_path
        except Exception as e:
            print(f"Sample comic error: {e}")
            return None


comic_generation_service = ComicGenerationService()


def make_share_token() -> str:
    return secrets.token_urlsafe(8)
