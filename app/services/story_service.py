import json
import os
from typing import Any, Dict, List, Optional

import google.generativeai as genai
from sqlalchemy.orm import Session

from app.config import settings
from app.models import Book, Child, Story, StoryPage
from app.services import ai_service
from app.services.text_render_service import text_render_service


class StoryGenerationService:
    def __init__(self):
        self.client: Any = None

    def initialize(self):
        if self.client is not None:
            return
        genai.configure(api_key=settings.GEMINI_API_KEY)
        self.client = genai.GenerativeModel(settings.GEMINI_TEXT_MODEL)
        print("Gemini text service initialized")

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
            start_arr = cleaned.find("[")
            end_arr = cleaned.rfind("]")
            if start_arr != -1 and end_arr != -1 and end_arr > start_arr:
                try:
                    return json.loads(cleaned[start_arr : end_arr + 1])
                except json.JSONDecodeError:
                    pass
            start_obj = cleaned.find("{")
            end_obj = cleaned.rfind("}")
            if start_obj != -1 and end_obj != -1 and end_obj > start_obj:
                try:
                    return json.loads(cleaned[start_obj : end_obj + 1])
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
            if parsed is None:
                return fallback
            return parsed
        except Exception as e:
            print(f"Text JSON generation error: {e}")
            return fallback

    def generate_style_bible(
        self,
        child_name: str,
        child_age: int,
        gender: str,
        book_title: str,
        theme: str,
        style_keywords: str,
    ) -> Dict[str, Any]:
        prompt = f"""
Create a strict visual style bible JSON for one children's storybook.
Child name: {child_name}
Child age: {child_age}
Child gender: {gender}
Book title: {book_title}
Theme: {theme}
Style keywords: {style_keywords}

Return one JSON object only with keys:
- visual_style: short sentence
- palette: array of 5-7 color words
- line_quality: short phrase
- shading: short phrase
- lighting: short phrase
- camera_language: short phrase
- outfit_invariants: array of 3-5 short rules
- face_rules: array of 4-6 short rules
- negative_constraints: array of 6-10 short rules

Hard requirements for negative_constraints:
- no raw photo paste
- no photoreal skin pores
- no camera sensor noise
- no inconsistent character age
- no drastic style shifts

Return only JSON. No markdown.
""".strip()

        fallback = {
            "visual_style": "Polished children's picture book illustration",
            "palette": [
                "warm yellow",
                "sky blue",
                "mint green",
                "coral",
                "soft brown",
            ],
            "line_quality": "clean rounded lines",
            "shading": "soft painterly shading",
            "lighting": "gentle diffused daylight",
            "camera_language": "storybook medium shots with occasional wide establishing shots",
            "outfit_invariants": [
                "keep the hero's core outfit colors stable",
                "preserve recurring accessory if introduced",
                "avoid outfit style jumps between adjacent pages",
            ],
            "face_rules": [
                "maintain child-like proportions",
                "keep eye shape consistent",
                "keep hairstyle silhouette stable",
                "preserve nose and smile characteristics",
            ],
            "negative_constraints": [
                "no raw photo paste",
                "no photoreal skin pores",
                "no camera sensor noise",
                "no inconsistent character age",
                "no drastic style shifts",
                "no harsh cinematic color grading",
            ],
        }
        parsed = self._generate_text_json(prompt, fallback)
        return parsed if isinstance(parsed, dict) else fallback

    def generate_story_package(
        self,
        child_name: str,
        child_age: int,
        gender: str,
        book_title: str,
        theme: str,
        style_keywords: str,
        page_count: int,
        style_bible: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        prompt = f"""
Create a children's story JSON for exactly {page_count} pages.
Child name: {child_name}
Child age: {child_age}
Child gender: {gender}
Book title: {book_title}
Theme: {theme}
Style keywords: {style_keywords}
Style bible JSON: {json.dumps(style_bible, ensure_ascii=True)}

Return only a JSON array with exactly {page_count} items.
Each item must have these keys:
- text: 2-3 short sentences for children
- prompt: page image direction
- scene_id: short stable scene label
- location: short phrase
- time_of_day: one of morning/afternoon/evening/night
- emotion: short phrase
- camera_distance: one of close/medium/wide
- character_pose: short phrase

Rules:
- Keep world continuity across pages.
- Keep the same art direction throughout all pages.
- Keep child's appearance age-consistent.
- Never request photorealism or direct photo pasting.

Return only JSON array. No markdown.
""".strip()

        parsed = self._generate_text_json(prompt, [])
        if not isinstance(parsed, list):
            return []
        return parsed[:page_count]

    def generate_preview(
        self,
        db: Session,
        story: Story,
        child: Child,
        book: Book,
        num_pages: int = 13,
    ) -> bool:
        try:
            ai_service.image_generation_service.initialize()
            ai_service.face_prep_service.initialize()

            if not child.photo_path or not os.path.exists(child.photo_path):
                print("Child photo missing")
                return False

            style_keywords = (
                book.style_keywords or "children's book cartoon, soft colors"
            )

            style_bible = self.generate_style_bible(
                child_name=child.name,
                child_age=child.age or 6,
                gender=child.gender or "neutral",
                book_title=book.title,
                theme=book.theme,
                style_keywords=style_keywords,
            )

            identity_sheet = (
                ai_service.image_generation_service.generate_identity_sheet(
                    child_photo_path=child.photo_path,
                    style_bible=style_bible,
                    book_title=book.title,
                    style_keywords=style_keywords,
                )
            )
            identity_sheet_path: Optional[str] = None
            if identity_sheet is not None:
                identity_sheet_filename = f"story_{story.id}_identity_sheet.png"
                identity_sheet_path = ai_service.image_generation_service.save_image(
                    identity_sheet, identity_sheet_filename
                )

            canonical_outfit: Optional[str] = None
            if identity_sheet_path:
                canonical_outfit = ai_service.image_generation_service.describe_outfit_from_identity_sheet(
                    identity_sheet_path=identity_sheet_path,
                    child_name=child.name,
                    child_age=child.age or 6,
                    child_gender=child.gender or "neutral",
                )

            pages_data = self.generate_story_package(
                child_name=child.name,
                child_age=child.age or 6,
                gender=child.gender or "neutral",
                book_title=book.title,
                theme=book.theme,
                style_keywords=style_keywords,
                page_count=num_pages,
                style_bible=style_bible,
            )

            if not pages_data:
                return False

            story.generated_text = json.dumps(
                {
                    "style_bible": style_bible,
                    "identity_sheet_path": identity_sheet_path,
                    "canonical_outfit": canonical_outfit,
                },
                ensure_ascii=True,
            )
            db.commit()

            # reset existing pages on regeneration
            for existing in list(story.pages):
                db.delete(existing)
            db.commit()

            created_pages: List[StoryPage] = []
            for idx, page_data in enumerate(pages_data, start=1):
                page_prompt = page_data.get("prompt", "")
                if canonical_outfit:
                    page_prompt = (
                        f"{page_prompt} The child is wearing: {canonical_outfit}. "
                        "Do not change this outfit in any page."
                    )
                page = StoryPage(
                    story_id=story.id,
                    page_number=idx,
                    text=page_data.get("text", ""),
                    image_prompt=page_prompt,
                    is_preview=1,
                )
                db.add(page)
                created_pages.append(page)
            db.commit()

            previous_page_final_path: Optional[str] = None
            for page in created_pages:
                page_spec = pages_data[page.page_number - 1]
                base_path, mask_path = (
                    ai_service.image_generation_service.get_template_paths(
                        book_id=book.id,
                        page_number=page.page_number,
                    )
                )

                best_path: Optional[str] = None
                best_qa: Dict[str, Any] = {
                    "style_match_score": 0,
                    "identity_match_score": 0,
                    "photo_paste_risk": 10,
                    "background_preservation": 0,
                }

                for attempt in range(1, settings.MAX_PAGE_RETRIES + 1):
                    quality_suffix = (
                        ""
                        if attempt == 1
                        else " Keep style and identity stricter. Increase illustration stylization and avoid any real-photo look."
                    )
                    image = ai_service.image_generation_service.generate_page_with_mask(
                        page_prompt=(page.image_prompt or "") + quality_suffix,
                        child_photo_path=child.photo_path,
                        style_bible=style_bible,
                        page_spec=page_spec,
                        identity_sheet_path=identity_sheet_path,
                        previous_page_path=previous_page_final_path,
                        base_template_path=base_path,
                        mask_template_path=mask_path,
                    )

                    if image is None:
                        print(
                            f"Failed image generation for page {page.page_number} attempt {attempt}"
                        )
                        continue

                    draft_filename = f"story_{story.id}_page_{page.page_number}_attempt_{attempt}.png"
                    draft_path = ai_service.image_generation_service.save_image(
                        image, draft_filename
                    )
                    qa = ai_service.image_generation_service.critique_generated_page(
                        image_path=draft_path,
                        style_bible=style_bible,
                        page_spec=page_spec,
                    )

                    current_quality = (
                        int(qa.get("style_match_score", 0))
                        + int(qa.get("identity_match_score", 0))
                        + int(qa.get("background_preservation", 0))
                        - int(qa.get("photo_paste_risk", 10))
                    )
                    best_quality = (
                        int(best_qa.get("style_match_score", 0))
                        + int(best_qa.get("identity_match_score", 0))
                        + int(best_qa.get("background_preservation", 0))
                        - int(best_qa.get("photo_paste_risk", 10))
                    )

                    if best_path is None or current_quality > best_quality:
                        best_path = draft_path
                        best_qa = qa

                    pass_gate = (
                        int(qa.get("photo_paste_risk", 10))
                        <= settings.QA_MAX_PHOTO_PASTE_RISK
                        and int(qa.get("style_match_score", 0))
                        >= settings.QA_MIN_STYLE_MATCH
                        and int(qa.get("identity_match_score", 0))
                        >= settings.QA_MIN_IDENTITY_MATCH
                    )
                    if pass_gate:
                        break

                if best_path is None:
                    continue

                final_filename = f"story_{story.id}_page_{page.page_number}.png"
                final_path = os.path.join(os.path.dirname(best_path), final_filename)
                if best_path != final_path:
                    if os.path.exists(final_path):
                        os.remove(final_path)
                    os.replace(best_path, final_path)

                text_box = text_render_service.get_page_text_box(
                    template_data=book.template_data,
                    page_number=page.page_number,
                    image_path=final_path,
                )
                text_render_service.render_page_text(
                    image_path=final_path,
                    text=page.text or "",
                    text_box=text_box,
                )

                page.image_path = final_path
                previous_page_final_path = final_path

            story.status = "preview_ready"
            story.preview_generated = 1
            db.commit()
            return True
        except Exception as e:
            print(f"Preview generation error: {e}")
            db.rollback()
            return False


story_generation_service = StoryGenerationService()
