import io
import os
import base64
import json
from typing import Any, Dict, List, Optional

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
                inline_data = part.get("inlineData") or part.get("inline_data")
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
        try:
            resp = requests.post(url, json=payload, timeout=timeout)
        except requests.RequestException as e:
            print(f"Gemini request exception ({model_name}): {e}")
            return None
        if resp.status_code != 200:
            print(
                f"Gemini request error ({model_name}): "
                f"{resp.status_code} {resp.text[:250]}"
            )
            return None
        return resp.json()

    @staticmethod
    def _image_safety_settings() -> list[Dict[str, str]]:
        return [
            {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
            {
                "category": "HARM_CATEGORY_SEXUALLY_EXPLICIT",
                "threshold": "BLOCK_NONE",
            },
            {
                "category": "HARM_CATEGORY_DANGEROUS_CONTENT",
                "threshold": "BLOCK_NONE",
            },
        ]

    def _gemini_multimodal_predict(
        self,
        prompt: str,
        image_paths: Optional[List[str]] = None,
        aspect_ratio: str = "4:3",
        model_name: Optional[str] = None,
        timeout: int = 180,
    ) -> Optional[Image.Image]:
        """Generate an image via the multimodal Gemini API.

        Uses `gemini-2.5-flash-image` (or whatever `model_name` is given) with
        `responseModalities: IMAGE` so the model returns a base64 PNG. We can
        attach any number of reference images (child photo, identity sheet,
        previous panel) to give the model visual context for the scene.

        The Imagen `:predict` path we used previously returned 404 for the
        subject-reference model on the free tier and 429 on the text-to-image
        fallback, leaving panels blank. The multimodal endpoint is available on
        the free tier and naturally supports "use this face in this scene" by
        putting the reference photo into the same `parts` list as the prompt.
        """
        self.initialize()
        model = model_name or settings.GEMINI_IMAGE_MODEL_MULTIMODAL
        if not model:
            print("[Gemini] no multimodal image model configured")
            return None
        if not settings.GEMINI_API_KEY:
            print("[Gemini] GEMINI_API_KEY missing — skipping image gen")
            return None

        parts: list[Dict[str, Any]] = [{"text": prompt}]
        for path in image_paths or []:
            if not path or not os.path.exists(path):
                continue
            try:
                parts.append(
                    {
                        "inlineData": {
                            "mimeType": self._guess_mime_type(path),
                            "data": base64.b64encode(
                                self._load_image_as_bytes(path)
                            ).decode("utf-8"),
                        }
                    }
                )
            except Exception as e:
                print(f"[Gemini] failed to attach reference {path}: {e}")

        payload: Dict[str, Any] = {
            "contents": [{"parts": parts}],
            "generationConfig": {
                "responseModalities": ["IMAGE"],
                "imageConfig": {"aspectRatio": aspect_ratio},
            },
            "safetySettings": self._image_safety_settings(),
        }

        try:
            data = self._generate_content(model, payload, timeout=timeout)
        except Exception as e:
            print(f"[Gemini] multimodal image exception ({model}): {e}")
            return None
        if not data:
            return None
        return self._extract_first_image_from_json(data)

    def extract_face_description(self, photo_path: str) -> str:
        """Extract a canonical text description of the person's appearance
        for use as a hard character anchor in subsequent panel prompts."""
        self.initialize()
        if not photo_path or not os.path.exists(photo_path):
            return ""
        try:
            instruction = (
                "You are extracting a visual character description for use as a "
                "drawing reference in an illustrated comic book. Look at the person "
                "in this photo. Return ONLY a single sentence (max 30 words) that "
                "describes their distinguishing visual features: approximate age "
                "range, face shape, skin tone, hair color and style, eye color, and "
                "any other notable features. Be literal and specific. This sentence "
                "will be appended to every panel prompt to keep the character "
                "consistent. Do not mention the photo. Do not use lists."
            )
            payload = {
                "contents": [
                    {
                        "parts": [
                            {"text": instruction},
                            {
                                "inlineData": {
                                    "mimeType": self._guess_mime_type(photo_path),
                                    "data": base64.b64encode(
                                        self._load_image_as_bytes(photo_path)
                                    ).decode("utf-8"),
                                }
                            },
                        ]
                    }
                ],
                "generationConfig": {"responseModalities": ["TEXT"]},
                "safetySettings": self._image_safety_settings(),
            }
            data = self._generate_content(
                settings.GEMINI_TEXT_MODEL, payload, timeout=90
            )
            if not data:
                return ""
            text = self._extract_first_text_from_json(data).strip()
            cleaned = " ".join(text.split())
            if not cleaned:
                return ""
            if len(cleaned) > 400:
                cleaned = cleaned[:400].rsplit(" ", 1)[0]
            return cleaned
        except Exception as e:
            print(f"Face description error: {e}")
            return ""

    def analyze_panel_layout(
        self, panel_image_path: str, speech_text: str, caption_text: str = ""
    ) -> Dict[str, Any]:
        """Ask vision Gemini where to place bubbles/narration in a panel.

        Returns dict with keys: bubble_box, bubble_kind, tail_direction, caption_box.
        All box coordinates are percentages (0-100) of the panel image.
        Falls back to safe defaults if the call fails.
        """
        default: Dict[str, Any] = {
            "bubble_box": {"x": 60.0, "y": 8.0, "w": 32.0, "h": 22.0},
            "bubble_kind": "speech",
            "tail_direction": "down-left",
            "caption_box": {
                "x": 5.0,
                "y": 5.0,
                "w": 60.0,
                "h": 12.0,
                "position": "top",
            },
        }
        self.initialize()
        if (
            not panel_image_path
            or not os.path.exists(panel_image_path)
            or not speech_text
        ):
            return default
        try:
            instruction = (
                "You are laying out a comic book panel. Look at the image and "
                "decide where the speech bubble (and optional caption box) should "
                "go. The speech line is: "
                f'"{speech_text}". '
                + (f'The caption is: "{caption_text}". ' if caption_text else "")
                + "Return ONLY a JSON object with this exact shape and no other text: "
                '{"bubble_box": {"x": 5-95, "y": 5-95, "w": 15-50, "h": 12-35}, '
                '"bubble_kind": "speech|thought|shout", '
                '"tail_direction": "down-left|down-right|up-left|up-right", '
                '"caption_box": {"x": 5-95, "y": 5-95, "w": 30-90, "h": 8-18, '
                '"position": "top|bottom|inside"}}. '
                "Hard rules: do not place a bubble that covers the main "
                "character's face or primary action area; prefer empty sky / "
                "wall / ground quadrants; keep the bubble fully inside the panel; "
                "if the speaker is upper-left, point the tail down-left or "
                "down-right toward them; if the speaker is lower-right, point "
                "the tail up-left or up-right. Coordinates are percentages of "
                "the image dimensions."
            )
            payload = {
                "contents": [
                    {
                        "parts": [
                            {"text": instruction},
                            {
                                "inlineData": {
                                    "mimeType": self._guess_mime_type(panel_image_path),
                                    "data": base64.b64encode(
                                        self._load_image_as_bytes(panel_image_path)
                                    ).decode("utf-8"),
                                }
                            },
                        ]
                    }
                ],
                "generationConfig": {
                    "responseModalities": ["TEXT"],
                    "temperature": 0.2,
                },
                "safetySettings": self._image_safety_settings(),
            }
            data = self._generate_content(
                settings.GEMINI_TEXT_MODEL, payload, timeout=90
            )
            if not data:
                return default
            text = self._extract_first_text_from_json(data).strip()
            parsed = self._parse_json_text(text)
            if not isinstance(parsed, dict):
                return default

            def _clamp(v: Any, lo: float, hi: float) -> float:
                try:
                    v = float(v)
                except (TypeError, ValueError):
                    return lo
                return max(lo, min(hi, v))

            bb = parsed.get("bubble_box") or {}
            bubble_box = {
                "x": _clamp(bb.get("x", 60), 5, 95),
                "y": _clamp(bb.get("y", 8), 5, 95),
                "w": _clamp(bb.get("w", 32), 15, 50),
                "h": _clamp(bb.get("h", 22), 12, 35),
            }
            bubble_kind = str(parsed.get("bubble_kind", "speech"))
            if bubble_kind not in {"speech", "thought", "shout"}:
                bubble_kind = "speech"
            tail = str(parsed.get("tail_direction", "down-left"))
            if tail not in {"down-left", "down-right", "up-left", "up-right"}:
                tail = "down-left"
            cb = parsed.get("caption_box") or {}
            caption_box = {
                "x": _clamp(cb.get("x", 5), 5, 95),
                "y": _clamp(cb.get("y", 5), 5, 95),
                "w": _clamp(cb.get("w", 60), 30, 90),
                "h": _clamp(cb.get("h", 12), 8, 18),
                "position": str(cb.get("position", "top")),
            }
            return {
                "bubble_box": bubble_box,
                "bubble_kind": bubble_kind,
                "tail_direction": tail,
                "caption_box": caption_box,
            }
        except Exception as e:
            print(f"Panel layout analysis error: {e}")
            return default

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
            "generationConfig": {
                "responseModalities": ["IMAGE"],
                "imageConfig": {
                    "aspectRatio": "1:1",
                },
            },
            "safetySettings": self._image_safety_settings(),
        }
        data = self._generate_content(settings.GEMINI_IMAGE_MODEL_MULTIMODAL, payload)
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
                "generationConfig": {
                    "responseModalities": ["IMAGE"],
                    "imageConfig": {
                        "aspectRatio": "2:3",
                    },
                },
                "safetySettings": self._image_safety_settings(),
            }

            first_data = self._generate_content(
                settings.GEMINI_IMAGE_MODEL_MULTIMODAL, payload, timeout=180
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
                "generationConfig": {
                    "responseModalities": ["IMAGE"],
                    "imageConfig": {
                        "aspectRatio": "2:3",
                    },
                },
                "safetySettings": self._image_safety_settings(),
            }
            retry_data = self._generate_content(
                settings.GEMINI_IMAGE_MODEL_MULTIMODAL, retry_payload, timeout=180
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

    def save_comic_panel(self, image: Image.Image, filename: str) -> str:
        from app.config import COMIC_PANEL_DIR

        output_path = os.path.join(COMIC_PANEL_DIR, filename)
        image.save(output_path)
        return output_path

    def save_comic_sheet(self, image: Image.Image, filename: str) -> str:
        from app.config import COMIC_SHEET_DIR

        output_path = os.path.join(COMIC_SHEET_DIR, filename)
        image.save(output_path)
        return output_path

    def generate_comic_identity_sheet(
        self,
        child_photo_path: str,
        style_suffix: str,
        style_name: str,
    ) -> Optional[Image.Image]:
        self.initialize()
        if not os.path.exists(child_photo_path):
            return None

        instruction = (
            "Create a 2x2 character reference sheet for a comic book. "
            "Panels: front-facing smile, 3/4 view confident, side profile determined, surprised expression. "
            f"Style: {style_name}. {style_suffix} "
            "Clean white background, full upper body, expressive face, consistent outfit and hairstyle across all four panels. "
            "No text, letters, words, watermarks, logos, or speech bubbles anywhere in the image."
        )

        parts: list[Dict[str, Any]] = [
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
            "contents": [{"parts": parts}],
            "generationConfig": {
                "responseModalities": ["IMAGE"],
                "imageConfig": {
                    "aspectRatio": "1:1",
                },
            },
            "safetySettings": self._image_safety_settings(),
        }
        data = self._generate_content(
            settings.GEMINI_IMAGE_MODEL_MULTIMODAL, payload, timeout=180
        )
        if not data:
            return None
        return self._extract_first_image_from_json(data)

    def generate_comic_panel(
        self,
        panel_description: str,
        child_photo_path: str,
        identity_sheet_path: Optional[str],
        style_suffix: str,
        style_name: str,
        panel_index: int,
        panel_count: int,
        bubble_quadrant: str = "top-right",
        previous_panel_path: Optional[str] = None,
        character_description: str = "",
    ) -> Optional[Image.Image]:
        self.initialize()
        anchor = (
            f"The protagonist is: {character_description}. "
            "This exact same character must appear in every panel — do not change "
            "face, hair, build, skin tone, outfit, or approximate age. "
            if character_description
            else ""
        )
        instruction = (
            f"Single comic panel illustration, panel {panel_index} of {panel_count}. "
            f"Style: {style_name}. {style_suffix} "
            f"{anchor}"
            f"Scene: {panel_description}. "
            "Show one clear protagonist and a readable environment. "
            "Use dynamic composition and clean linework. "
            "No text, letters, words, watermarks, logos, captions, speech bubbles, panel borders, split frames, or collage effects. "
            "Never paste, trace, or directly copy the source photo. "
            "No photoreal skin pores, camera noise, DSLR lighting, or raw photo artifacts."
        )

        refs: list[str] = []
        if identity_sheet_path and os.path.exists(identity_sheet_path):
            refs.append(identity_sheet_path)
        if previous_panel_path and os.path.exists(previous_panel_path):
            refs.append(previous_panel_path)
        if child_photo_path and os.path.exists(child_photo_path):
            refs.append(child_photo_path)

        image = self._gemini_multimodal_predict(
            prompt=instruction,
            image_paths=refs,
            aspect_ratio="4:3",
            timeout=180,
        )
        if image is not None:
            return image

        retry_instruction = (
            f"Draw one finished comic scene in {style_name} style. "
            f"{anchor}"
            f"{panel_description}. "
            "Single illustration only. No text or speech bubbles. "
            "Maintain consistency with the reference face in the photo."
        )
        retry_refs = (
            [child_photo_path]
            if child_photo_path and os.path.exists(child_photo_path)
            else []
        )
        return self._gemini_multimodal_predict(
            prompt=retry_instruction,
            image_paths=retry_refs,
            aspect_ratio="4:3",
            timeout=180,
        )

    def generate_cover_image(
        self,
        child_photo_path: str,
        identity_sheet_path: Optional[str],
        style_suffix: str,
        style_name: str,
        title: str,
        subtitle: str,
    ) -> Optional[Image.Image]:
        self.initialize()
        instruction = (
            f"Comic book cover illustration. Style: {style_name}. {style_suffix} "
            f"Title concept: {title}. "
            "Heroic full-body protagonist, dramatic pose, cinematic lighting, strong depth, full bleed. "
            "Keep generous visual breathing room at top and bottom for later typography overlays. "
            "No text, letters, words, logos, watermarks, speech bubbles, or panel borders. "
            "Never paste, trace, or directly copy the source photo. "
            "No photoreal skin pores, camera noise, DSLR lighting, or raw photo artifacts."
        )

        refs: list[str] = []
        if identity_sheet_path and os.path.exists(identity_sheet_path):
            refs.append(identity_sheet_path)
        if child_photo_path and os.path.exists(child_photo_path):
            refs.append(child_photo_path)

        image = self._gemini_multimodal_predict(
            prompt=instruction,
            image_paths=refs,
            aspect_ratio="3:4",
            timeout=180,
        )
        if image is not None:
            return image

        retry_instruction = (
            f"Draw a finished hero cover in {style_name} style with dramatic action and clean composition. "
            "No text. Keep the reference face consistent."
        )
        retry_refs = (
            [child_photo_path]
            if child_photo_path and os.path.exists(child_photo_path)
            else []
        )
        return self._gemini_multimodal_predict(
            prompt=retry_instruction,
            image_paths=retry_refs,
            aspect_ratio="3:4",
            timeout=180,
        )


face_prep_service = FacePreparationService()
image_generation_service = GeminiImageService()
