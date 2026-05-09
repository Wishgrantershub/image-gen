import io
import os
import base64
import json
from typing import Any, Dict, Optional

import google.generativeai as genai
import cv2
import numpy as np
from PIL import Image
import requests

from app.config import settings, OUTPUT_DIR, TEMPLATE_BASE_DIR, TEMPLATE_MASK_DIR


class FacePreparationService:
    def __init__(self):
        self.app: Any = None

    def initialize(self):
        if self.app is not None:
            return
        from insightface.app import FaceAnalysis

        self.app = FaceAnalysis(
            name="buffalo_l",
            providers=["CUDAExecutionProvider", "CPUExecutionProvider"],
        )
        self.app.prepare(ctx_id=0, det_size=(640, 640))
        print("InsightFace initialized")

    def prepare_face(self, image_path: str) -> Optional[np.ndarray]:
        if self.app is None:
            self.initialize()
        if self.app is None:
            return None

        img = cv2.imread(image_path)
        if img is None:
            return None
        img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        faces = self.app.get(img_rgb)
        if not faces:
            return None
        return faces[0].normed_embedding


class GeminiImageService:
    def __init__(self):
        self.initialized = False

    def initialize(self):
        if self.initialized:
            return
        genai.configure(api_key=settings.GEMINI_API_KEY)
        self.initialized = True
        print("Gemini image service initialized")

    @staticmethod
    def _load_image_as_bytes(path: str) -> bytes:
        with open(path, "rb") as f:
            return f.read()

    @staticmethod
    def _guess_mime_type(path: str) -> str:
        ext = os.path.splitext(path.lower())[1]
        if ext in [".jpg", ".jpeg"]:
            return "image/jpeg"
        if ext == ".webp":
            return "image/webp"
        return "image/png"

    @staticmethod
    def _pil_to_png_bytes(image: Image.Image) -> bytes:
        bio = io.BytesIO()
        image.save(bio, format="PNG")
        return bio.getvalue()

    @staticmethod
    def _extract_first_image_from_json(data: Dict[str, Any]) -> Optional[Image.Image]:
        for candidate in data.get("candidates", []):
            parts = candidate.get("content", {}).get("parts", [])
            for part in parts:
                inline_data = part.get("inlineData")
                if inline_data and inline_data.get("data"):
                    raw = base64.b64decode(inline_data["data"])
                    return Image.open(io.BytesIO(raw)).convert("RGB")
        return None

    @staticmethod
    def _extract_first_text_from_json(data: Dict[str, Any]) -> str:
        for candidate in data.get("candidates", []):
            parts = candidate.get("content", {}).get("parts", [])
            for part in parts:
                text = part.get("text")
                if text:
                    return text
        return ""

    @staticmethod
    def _parse_json_text(raw_text: str) -> Optional[Dict[str, Any]]:
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
            start = cleaned.find("{")
            end = cleaned.rfind("}")
            if start != -1 and end != -1 and end > start:
                try:
                    return json.loads(cleaned[start : end + 1])
                except json.JSONDecodeError:
                    return None
            return None

    def _generate_content(
        self, model_name: str, payload: Dict[str, Any], timeout: int = 180
    ) -> Optional[Dict[str, Any]]:
        url = (
            "https://generativelanguage.googleapis.com/v1beta/models/"
            f"{model_name}:generateContent"
            f"?key={settings.GEMINI_API_KEY}"
        )
        resp = requests.post(url, json=payload, timeout=timeout)
        if resp.status_code != 200:
            print(
                f"Gemini request error ({model_name}): "
                f"{resp.status_code} {resp.text[:250]}"
            )
            return None
        return resp.json()

    def describe_outfit_from_identity_sheet(
        self,
        identity_sheet_path: str,
        child_name: str,
        child_age: int,
        child_gender: str,
    ) -> Optional[str]:
        self.initialize()
        if not identity_sheet_path or not os.path.exists(identity_sheet_path):
            return None

        instruction = (
            "You are extracting wardrobe details for story continuity. "
            "Read this character identity sheet and return only one short plain-text phrase "
            "describing the child's canonical outfit for all pages. "
            "Include top, bottom or dress, key colors, and any consistent accessory. "
            "Do not mention pose, camera, or expression. "
            f"Child: {child_name}, age {child_age}, gender {child_gender}."
        )
        payload = {
            "contents": [
                {
                    "parts": [
                        {"text": instruction},
                        {
                            "inlineData": {
                                "mimeType": self._guess_mime_type(identity_sheet_path),
                                "data": base64.b64encode(
                                    self._load_image_as_bytes(identity_sheet_path)
                                ).decode("utf-8"),
                            }
                        },
                    ]
                }
            ],
            "generationConfig": {"responseModalities": ["TEXT"]},
        }
        data = self._generate_content(settings.GEMINI_TEXT_MODEL, payload, timeout=120)
        if not data:
            return None
        outfit = self._extract_first_text_from_json(data).strip()
        if not outfit:
            return None
        return " ".join(outfit.split())[:220]

    def generate_identity_sheet(
        self,
        child_photo_path: str,
        style_bible: Dict[str, Any],
        book_title: str,
        style_keywords: str,
    ) -> Optional[Image.Image]:
        self.initialize()
        if not os.path.exists(child_photo_path):
            return None

        instruction = (
            "Create a 2x2 children's storybook character identity sheet from this child photo. "
            "Panels: front smile, 3/4 view neutral, side profile happy, surprised expression. "
            "Keep full illustration style and avoid photoreal skin texture. "
            "Do not paste or trace the source photo. "
            f"Book: {book_title}. "
            f"Style keywords: {style_keywords}. "
            f"Style bible: {json.dumps(style_bible, ensure_ascii=True)}"
        )

        identity_parts: list[Dict[str, Any]] = [
            {"text": instruction},
            {
                "inlineData": {
                    "mimeType": self._guess_mime_type(child_photo_path),
                    "data": base64.b64encode(
                        self._load_image_as_bytes(child_photo_path)
                    ).decode("utf-8"),
                }
            },
        ]

        payload = {
            "contents": [{"parts": identity_parts}],
            "generationConfig": {"responseModalities": ["IMAGE", "TEXT"]},
        }
        data = self._generate_content(settings.GEMINI_IMAGE_MODEL, payload)
        if not data:
            return None
        return self._extract_first_image_from_json(data)

    def generate_page_with_mask(
        self,
        page_prompt: str,
        child_photo_path: str,
        style_bible: Optional[Dict[str, Any]] = None,
        page_spec: Optional[Dict[str, Any]] = None,
        identity_sheet_path: Optional[str] = None,
        previous_page_path: Optional[str] = None,
        base_template_path: Optional[str] = None,
        mask_template_path: Optional[str] = None,
    ) -> Optional[Image.Image]:
        self.initialize()

        try:
            style_json = json.dumps(style_bible or {}, ensure_ascii=True)
            page_json = json.dumps(page_spec or {}, ensure_ascii=True)
            instruction = (
                "You are editing a children's storybook page. "
                "Output one single-panel story scene image, not a multi-panel reference sheet. "
                "Preserve composition and background from the base template. "
                "If a black/white mask is provided, edit only white regions and keep black regions unchanged. "
                "Blend the child face identity naturally into the illustrated character face while keeping illustrated style. "
                "Never paste, trace, or directly copy the source photo. "
                "No photoreal skin pores, camera noise, DSLR lighting, or raw photo artifacts. "
                "Keep style as polished children's picture book illustration. "
                f"Global style bible JSON: {style_json}. "
                f"Page continuity JSON: {page_json}. "
                f"Page context: {page_prompt}"
            )

            request_parts: list[Dict[str, Any]] = [{"text": instruction}]

            if base_template_path and os.path.exists(base_template_path):
                request_parts.append(
                    {
                        "inlineData": {
                            "mimeType": "image/png",
                            "data": base64.b64encode(
                                self._load_image_as_bytes(base_template_path)
                            ).decode("utf-8"),
                        }
                    }
                )

            if mask_template_path and os.path.exists(mask_template_path):
                request_parts.append(
                    {
                        "inlineData": {
                            "mimeType": "image/png",
                            "data": base64.b64encode(
                                self._load_image_as_bytes(mask_template_path)
                            ).decode("utf-8"),
                        }
                    }
                )

            if identity_sheet_path and os.path.exists(identity_sheet_path):
                request_parts.append(
                    {
                        "inlineData": {
                            "mimeType": self._guess_mime_type(identity_sheet_path),
                            "data": base64.b64encode(
                                self._load_image_as_bytes(identity_sheet_path)
                            ).decode("utf-8"),
                        }
                    }
                )

            if previous_page_path and os.path.exists(previous_page_path):
                request_parts.append(
                    {
                        "inlineData": {
                            "mimeType": self._guess_mime_type(previous_page_path),
                            "data": base64.b64encode(
                                self._load_image_as_bytes(previous_page_path)
                            ).decode("utf-8"),
                        }
                    }
                )

            request_parts.append(
                {
                    "inlineData": {
                        "mimeType": self._guess_mime_type(child_photo_path),
                        "data": base64.b64encode(
                            self._load_image_as_bytes(child_photo_path)
                        ).decode("utf-8"),
                    }
                }
            )

            payload = {
                "contents": [{"parts": request_parts}],
                "generationConfig": {"responseModalities": ["IMAGE", "TEXT"]},
            }

            first_data = self._generate_content(
                settings.GEMINI_IMAGE_MODEL, payload, timeout=180
            )
            if first_data:
                first_image = self._extract_first_image_from_json(first_data)
                if first_image is not None:
                    return first_image

            retry_instruction = (
                instruction
                + " Retry with stricter continuity: keep outfit, linework, colors, and character scale"
                " consistent with references; return a final polished single-panel story scene."
            )
            retry_payload = {
                "contents": [
                    {
                        "parts": [{"text": retry_instruction}] + request_parts[1:],
                    }
                ],
                "generationConfig": {"responseModalities": ["IMAGE", "TEXT"]},
            }
            retry_data = self._generate_content(
                settings.GEMINI_IMAGE_MODEL, retry_payload, timeout=180
            )
            if retry_data:
                retry_image = self._extract_first_image_from_json(retry_data)
                if retry_image is not None:
                    return retry_image
            return None
        except Exception as e:
            print(f"Gemini image generation error: {e}")
            return None

    def critique_generated_page(
        self,
        image_path: str,
        style_bible: Optional[Dict[str, Any]],
        page_spec: Optional[Dict[str, Any]],
    ) -> Dict[str, Any]:
        self.initialize()
        default_result = {
            "style_match_score": 1,
            "identity_match_score": 1,
            "photo_paste_risk": 10,
            "background_preservation": 1,
            "issues": ["qa_failed_or_unavailable"],
        }
        if not image_path or not os.path.exists(image_path):
            return default_result

        instruction = (
            "You are a strict QA critic for children's book personalization. "
            "Return only JSON with keys: "
            "style_match_score (1-10), identity_match_score (1-10), "
            "photo_paste_risk (1-10), background_preservation (1-10), issues (array of short strings). "
            f"Style bible: {json.dumps(style_bible or {}, ensure_ascii=True)}. "
            f"Page spec: {json.dumps(page_spec or {}, ensure_ascii=True)}."
        )

        payload = {
            "contents": [],
            "generationConfig": {"responseModalities": ["TEXT"]},
        }
        critique_parts: list[Dict[str, Any]] = [
            {"text": instruction},
            {
                "inlineData": {
                    "mimeType": self._guess_mime_type(image_path),
                    "data": base64.b64encode(
                        self._load_image_as_bytes(image_path)
                    ).decode("utf-8"),
                }
            },
        ]
        payload = {
            "contents": [{"parts": critique_parts}],
            "generationConfig": {"responseModalities": ["TEXT"]},
        }
        data = self._generate_content(settings.GEMINI_TEXT_MODEL, payload, timeout=120)
        if not data:
            return default_result
        parsed = self._parse_json_text(self._extract_first_text_from_json(data))
        if not parsed:
            return default_result
        return {
            "style_match_score": int(parsed.get("style_match_score", 1)),
            "identity_match_score": int(parsed.get("identity_match_score", 1)),
            "photo_paste_risk": int(parsed.get("photo_paste_risk", 10)),
            "background_preservation": int(parsed.get("background_preservation", 1)),
            "issues": parsed.get("issues", []),
        }

    def get_template_paths(
        self, book_id: int, page_number: int
    ) -> tuple[Optional[str], Optional[str]]:
        base = os.path.join(
            TEMPLATE_BASE_DIR, f"book_{book_id}", f"page_{page_number}.png"
        )
        mask = os.path.join(
            TEMPLATE_MASK_DIR, f"book_{book_id}", f"page_{page_number}.png"
        )
        base_path = base if os.path.exists(base) else None
        mask_path = mask if os.path.exists(mask) else None
        return base_path, mask_path

    def save_image(self, image: Image.Image, filename: str) -> str:
        output_path = os.path.join(OUTPUT_DIR, filename)
        image.save(output_path)
        return output_path


face_prep_service = FacePreparationService()
image_generation_service = GeminiImageService()
