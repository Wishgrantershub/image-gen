import io
import os
import base64
import json
from typing import Any, Dict, List, Optional

import google.generativeai as genai
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

    def prepare_face(self, image_path: str) -> Optional[Any]:
        if self.app is None:
            self.initialize()
        if self.app is None:
            return None

        import cv2
        import numpy as np

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
    def _parse_image_response(
        data: Dict[str, Any],
    ) -> tuple[Optional[Image.Image], str, str]:
        """Parse Gemini image response and return (image, reason, refusal_text).

        Reason codes:
        - "SUCCESS": valid image returned
        - "BLOCKED": prompt was blocked (no candidates)
        - "SAFETY": image or prompt safety filter triggered (IMAGE_SAFETY, IMAGE_PROHIBITED_CONTENT)
        - "TEXT_INSTEAD_OF_IMAGE": model returned text instead of image
        - "TRUNCATED": MAX_TOKENS hit, output cut off
        - "EMPTY": no candidates at all
        - "ERROR": other error
        """
        if not data:
            return None, "ERROR", ""

        prompt_feedback = data.get("promptFeedback", {})
        block_reason = prompt_feedback.get("blockReason")
        candidates = data.get("candidates", [])

        if not candidates:
            refusal = ""
            if block_reason:
                refusal = f"Prompt blocked: {block_reason}"
            return None, "EMPTY" if not block_reason else "BLOCKED", refusal

        candidate = candidates[0]
        finish_reason = candidate.get("finishReason")
        parts = candidate.get("content", {}).get("parts", [])

        refusal_text = ""

        text_parts: list[str] = []

        if block_reason:
            refusal_text = f"Prompt blocked: {block_reason}"
        elif finish_reason == "MAX_TOKENS":
            return None, "TRUNCATED", "Output truncated due to token limit"
        elif finish_reason in ("IMAGE_SAFETY", "IMAGE_PROHIBITED_CONTENT"):
            return None, "SAFETY", "Image safety filter blocked the generation"
        elif finish_reason == "STOP":
            text_parts = [p.get("text", "") for p in parts if p.get("text")]
            if text_parts and not any(
                p.get("inlineData") or p.get("inline_data") for p in parts
            ):
                refusal_text = (
                    f"Model returned text instead of image: {text_parts[0][:100]}"
                )
                return None, "TEXT_INSTEAD_OF_IMAGE", refusal_text
        elif finish_reason not in ("STOP", "STOP_AND_GENERATE"):
            refusal_text = f"Finish reason: {finish_reason}"

        image = None
        for part in parts:
            inline_data = part.get("inlineData") or part.get("inline_data")
            if inline_data and inline_data.get("data"):
                raw = base64.b64decode(inline_data["data"])
                image = Image.open(io.BytesIO(raw)).convert("RGB")
                break

        if image is None:
            return (
                None,
                "TEXT_INSTEAD_OF_IMAGE" if text_parts else "EMPTY",
                refusal_text,
            )

        return image, "SUCCESS", refusal_text

    @staticmethod
    def _is_valid_panel_image(image: Optional[Image.Image]) -> bool:
        """Validate that an image is a viable comic panel (not garbage).

        Checks: dimensions, aspect ratio, and a non-blank/non-single-color
        heuristic via pixel standard deviation. A solid-color or near-blank
        image (stdev < 8) is rejected even if it technically has inlineData.
        """
        if image is None:
            return False
        iw, ih = image.size
        if iw < 400 or ih < 400:
            return False
        if iw > 4096 or ih > 4096:
            return False
        if iw / ih < 0.3 or iw / ih > 3.5:
            return False
        if ih == 0:
            return False
        try:
            import numpy as np

            small = image.convert("L").resize((64, 64), Image.LANCZOS)
            arr = np.asarray(small, dtype=np.float32)
            stdev = float(arr.std())
            if stdev < 8.0:
                print(f"[Gemini] rejecting image: stdev={stdev:.1f} (too flat)")
                return False
        except Exception:
            pass
        return True

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

    def _imagen_predict(
        self,
        prompt: str,
        aspect_ratio: str = "4:3",
        negative_prompt: str = "",
        person_generation: str = "allow_all",
        model_name: Optional[str] = None,
        timeout: int = 120,
    ) -> Optional[Image.Image]:
        """Call an Imagen text-to-image model via the :predict endpoint.

        Imagen models (imagen-4.0-generate-001, imagen-3.0-generate-002) use
        a different endpoint and payload shape than Gemini generateContent.
        This is a pure text-to-image model — no text-vs-image ambiguity, so
        it's a reliable last-resort fallback.

        Returns a PIL Image or None.
        """
        self.initialize()
        model = model_name or settings.GEMINI_IMAGE_MODEL_TXT2IMG
        if not model or not settings.GEMINI_API_KEY:
            return None

        parameters: Dict[str, Any] = {
            "sampleCount": 1,
            "aspectRatio": aspect_ratio,
            "personGeneration": person_generation,
        }
        if negative_prompt:
            parameters["negativePrompt"] = negative_prompt

        payload: Dict[str, Any] = {
            "instances": [{"prompt": prompt}],
            "parameters": parameters,
        }

        url = (
            "https://generativelanguage.googleapis.com/v1beta/models/"
            f"{model}:predict?key={settings.GEMINI_API_KEY}"
        )
        try:
            resp = requests.post(url, json=payload, timeout=timeout)
        except requests.RequestException as e:
            print(f"[Imagen] request exception ({model}): {e}")
            return None
        if resp.status_code != 200:
            print(
                f"[Imagen] request error ({model}): "
                f"{resp.status_code} {resp.text[:300]}"
            )
            return None

        data = resp.json()
        predictions = data.get("predictions", [])
        if not predictions:
            print(f"[Imagen] no predictions in response")
            return None
        b64 = predictions[0].get("bytesBase64Encoded")
        if not b64:
            print(f"[Imagen] prediction has no bytesBase64Encoded")
            return None
        try:
            raw = base64.b64decode(b64)
            image = Image.open(io.BytesIO(raw)).convert("RGB")
            if self._is_valid_panel_image(image):
                return image
            print(f"[Imagen] image failed validity check")
            return None
        except Exception as e:
            print(f"[Imagen] image decode error: {e}")
            return None

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
        rephrase_on_failure: bool = False,
        context_words: list = None,
    ) -> tuple[Optional[Image.Image], str]:
        """Generate an image via the multimodal Gemini API.

        Uses `gemini-2.5-flash-image` (or whatever `model_name` is given) with
        `responseModalities: ["TEXT", "IMAGE"]` so the model can return images
        AND text refusals. Always prefixes prompt with "Generate an image of…"
        to avoid text-instead-of-image responses.

        Args:
            prompt: The core prompt describing the scene
            image_paths: Optional list of reference images
            aspect_ratio: Target aspect ratio for the image
            model_name: Override default multimodal model
            timeout: Request timeout in seconds
            rephrase_on_failure: If True, try rephrasing prompt on safety/block errors
            context_words: Words to potentially strip on safety blocks (e.g., age, child)

        Returns:
            Tuple of (image, reason) where reason is one of:
            - "SUCCESS": valid image returned
            - "BLOCKED": prompt was blocked (no candidates)
            - "SAFETY": image or prompt safety filter triggered
            - "TEXT_INSTEAD_OF_IMAGE": model returned text instead of image
            - "TRUNCATED": MAX_TOKENS hit, output cut off
            - "EMPTY": no candidates at all
            - "ERROR": other error
        """
        self.initialize()
        model = model_name or settings.GEMINI_IMAGE_MODEL_MULTIMODAL
        if not model:
            print("[Gemini] no multimodal image model configured")
            return None, "ERROR"
        if not settings.GEMINI_API_KEY:
            print("[Gemini] GEMINI_API_KEY missing — skipping image gen")
            return None, "ERROR"

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
                "responseModalities": ["TEXT", "IMAGE"],
                "imageConfig": {"aspectRatio": aspect_ratio},
            },
            "safetySettings": self._image_safety_settings(),
        }

        try:
            data = self._generate_content(model, payload, timeout=timeout)
        except Exception as e:
            print(f"[Gemini] multimodal image exception ({model}): {e}")
            return None, "ERROR"

        if not data:
            return None, "ERROR"

        image, reason, refusal_text = self._parse_image_response(data)
        if reason == "SUCCESS":
            if self._is_valid_panel_image(image):
                return image, "SUCCESS"
            else:
                return None, "INVALID_IMAGE"

        if reason in ("BLOCKED", "SAFETY") and rephrase_on_failure:
            image_paths_list: list[str] = image_paths if image_paths else []
            return self._retry_with_rephrased_prompt(
                model, prompt, aspect_ratio, image_paths_list, context_words
            )

        return image, reason

    def _retry_with_rephrased_prompt(
        self,
        model_name: str,
        original_prompt: str,
        aspect_ratio: str,
        image_paths: list[str],
        context_words: list[str],
    ) -> tuple[Optional[Image.Image], str]:
        """Retry with a rephrased prompt when safety/block errors occur."""
        if not context_words:
            context_words = ["age", "child", "children", "minor", "baby", "kid"]

        def strip_words(text: str) -> str:
            words_to_remove = [
                w.lower() for w in context_words if w.lower() in text.lower()
            ]
            for word in words_to_remove:
                text = text.lower().replace(word, "").replace(word.capitalize(), "")
            return text

        rephrased = strip_words(original_prompt)

        parts: list[Dict[str, Any]] = [{"text": f"Generate an image of {rephrased}"}]
        image_paths_list: list[str] = image_paths
        for path in image_paths_list:
            if path and os.path.exists(path):
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
                    print(f"[Gemini] failed to attach reference on retry: {e}")

        payload: Dict[str, Any] = {
            "contents": [{"parts": parts}],
            "generationConfig": {
                "responseModalities": ["TEXT", "IMAGE"],
                "imageConfig": {"aspectRatio": aspect_ratio},
            },
            "safetySettings": self._image_safety_settings(),
        }

        try:
            data = self._generate_content(model_name, payload, timeout=180)
        except Exception as e:
            print(f"[Gemini] rephrased prompt exception: {e}")
            return None, "ERROR"

        image, reason, _ = self._parse_image_response(data if data else {})
        if reason == "SUCCESS" and self._is_valid_panel_image(image):
            return image, "SUCCESS"

        return image, reason

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

        After the vision call (or fallback), the placement is verified with
        OpenCV face detection and image energy analysis. If the bubble
        overlaps a face or high-energy region, it is moved to the safest
        available spot.
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
                "You are laying out a comic book panel. First, identify where "
                "the main character's FACE is in the image. Then decide where "
                "the speech bubble should go so it does NOT cover the face or "
                "the primary action. The speech line is: "
                f'"{speech_text}". '
                + (f'The caption is: "{caption_text}". ' if caption_text else "")
                + "Return ONLY a JSON object with this exact shape and no other text: "
                '{"face_box": {"x": 0-100, "y": 0-100, "w": 5-60, "h": 5-50}, '
                '"bubble_box": {"x": 5-95, "y": 5-95, "w": 15-50, "h": 12-35}, '
                '"bubble_kind": "speech|thought|shout", '
                '"tail_direction": "down-left|down-right|up-left|up-right", '
                '"caption_box": {"x": 5-95, "y": 5-95, "w": 30-90, "h": 8-18, '
                '"position": "top|bottom|inside"}}. '
                "CRITICAL RULES: "
                "1. The bubble_box MUST NOT overlap the face_box. "
                "2. Place the bubble in empty space — sky, wall, or ground areas with no characters. "
                "3. Keep the bubble fully inside the panel margins. "
                "4. If the speaker is upper-left, point the tail down-left toward them. "
                "5. If the speaker is lower-right, point the tail up-left toward them. "
                "Coordinates are percentages of the image dimensions."
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
                result = dict(default)
            else:
                text = self._extract_first_text_from_json(data).strip()
                parsed = self._parse_json_text(text)
                if not isinstance(parsed, dict):
                    result = dict(default)
                else:

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
                    result = {
                        "bubble_box": bubble_box,
                        "bubble_kind": bubble_kind,
                        "tail_direction": tail,
                        "caption_box": caption_box,
                    }

            # --- Programmatic verification: face detection + energy analysis ---
            adjusted_box, adjusted_tail = self._adjust_bubble_for_safety(
                panel_image_path, result["bubble_box"], result["tail_direction"]
            )
            result["bubble_box"] = adjusted_box
            result["tail_direction"] = adjusted_tail
            return result
        except Exception as e:
            print(f"Panel layout analysis error: {e}")
            # Still try to adjust the default placement
            try:
                adjusted_box, adjusted_tail = self._adjust_bubble_for_safety(
                    panel_image_path,
                    default["bubble_box"],
                    default["tail_direction"],
                )
                default["bubble_box"] = adjusted_box
                default["tail_direction"] = adjusted_tail
            except Exception:
                pass
            return default

    @staticmethod
    def _rects_overlap(r1: tuple, r2: tuple, margin: int = 0) -> bool:
        """Check if two rectangles (x1,y1,x2,y2) overlap, with optional margin."""
        return not (
            r1[2] + margin <= r2[0]
            or r2[2] + margin <= r1[0]
            or r1[3] + margin <= r2[1]
            or r2[3] + margin <= r1[1]
        )

    def _detect_face_boxes(self, image_path: str) -> List[tuple]:
        """Detect face bounding boxes using OpenCV haarcascade.

        Returns list of (x1, y1, x2, y2) tuples in pixel coordinates.
        Works best on semi-realistic art (pixar, superhero); less reliable
        on heavily stylized manga but still worth checking.
        """
        try:
            import cv2

            img = cv2.imread(image_path)
            if img is None:
                return []
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            cascade_path = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
            cascade = cv2.CascadeClassifier(cascade_path)
            if cascade.empty():
                return []
            faces = cascade.detectMultiScale(
                gray,
                scaleFactor=1.1,
                minNeighbors=3,
                minSize=(40, 40),
            )
            return [(int(x), int(y), int(x + w), int(y + h)) for (x, y, w, h) in faces]
        except Exception:
            return []

    def _compute_energy_grid(self, image_path: str, grid: int = 4) -> List[List[float]]:
        """Compute visual energy (edge density) per grid cell.

        Lower energy = less detail = safer for bubble placement.
        Returns a grid x grid matrix of floats in [0, 1].
        """
        try:
            import cv2
            import numpy as np

            img = cv2.imread(image_path)
            if img is None:
                return [[0.5] * grid for _ in range(grid)]
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            edges = cv2.Canny(gray, 50, 150)
            h, w = edges.shape
            cell_h = max(1, h // grid)
            cell_w = max(1, w // grid)
            energy: List[List[float]] = [[0.0] * grid for _ in range(grid)]
            for r in range(grid):
                for c in range(grid):
                    y0 = r * cell_h
                    x0 = c * cell_w
                    y1 = min(h, (r + 1) * cell_h)
                    x1 = min(w, (c + 1) * cell_w)
                    region = edges[y0:y1, x0:x1]
                    if region.size > 0:
                        energy[r][c] = float(np.mean(region)) / 255.0
                    else:
                        energy[r][c] = 0.5
            return energy
        except Exception:
            return [[0.5] * grid for _ in range(grid)]

    def _adjust_bubble_for_safety(
        self,
        image_path: str,
        bubble_box: Dict[str, float],
        tail_direction: str,
    ) -> tuple:
        """Verify and adjust bubble placement to avoid faces and busy regions.

        Uses OpenCV face detection + Canny edge energy analysis. If the
        current placement overlaps a face or sits in a high-energy cell,
        moves the bubble to the safest (lowest-energy) cell that doesn't
        overlap a face. Returns (adjusted_box, adjusted_tail).
        """
        try:
            from PIL import Image as PILImage

            with PILImage.open(image_path) as img:
                img_w, img_h = img.size
        except Exception:
            return bubble_box, tail_direction

        if img_w <= 0 or img_h <= 0:
            return bubble_box, tail_direction

        # Convert bubble from percentages to pixels
        bx = bubble_box["x"] / 100.0 * img_w
        by = bubble_box["y"] / 100.0 * img_h
        bw = bubble_box["w"] / 100.0 * img_w
        bh = bubble_box["h"] / 100.0 * img_h
        bubble_px = (bx, by, bx + bw, by + bh)

        # Check face overlap
        faces = self._detect_face_boxes(image_path)
        overlaps_face = any(self._rects_overlap(bubble_px, f, margin=10) for f in faces)

        # Check energy of the cell the bubble center sits in
        grid = 4
        energy = self._compute_energy_grid(image_path, grid=grid)
        cx_pct = (bx + bw / 2) / img_w
        cy_pct = (by + bh / 2) / img_h
        cell_col = min(grid - 1, max(0, int(cx_pct * grid)))
        cell_row = min(grid - 1, max(0, int(cy_pct * grid)))
        current_energy = energy[cell_row][cell_col]

        # If no face overlap and energy is low enough, keep the placement
        ENERGY_THRESHOLD = 0.15
        if not overlaps_face and current_energy < ENERGY_THRESHOLD:
            return bubble_box, tail_direction

        # Need to relocate — find the safest cell
        # Build a list of (energy, row, col) sorted by energy ascending
        candidates = []
        for r in range(grid):
            for c in range(grid):
                # Compute pixel rect for this cell with some inset
                cell_x = c / grid * img_w
                cell_y = r / grid * img_h
                cell_w = img_w / grid
                cell_h = img_h / grid
                cell_rect = (
                    cell_x + 8,
                    cell_y + 8,
                    cell_x + cell_w - 8,
                    cell_y + cell_h - 8,
                )
                # Check if this cell overlaps any face
                cell_overlaps_face = any(
                    self._rects_overlap(cell_rect, f, margin=10) for f in faces
                )
                if cell_overlaps_face:
                    continue
                candidates.append((energy[r][c], r, c, cell_x, cell_y, cell_w, cell_h))

        if not candidates:
            # Every cell overlaps a face — pick lowest energy anyway
            all_cells = [
                (
                    energy[r][c],
                    r,
                    c,
                    c / grid * img_w,
                    r / grid * img_h,
                    img_w / grid,
                    img_h / grid,
                )
                for r in range(grid)
                for c in range(grid)
            ]
            candidates = all_cells

        candidates.sort(key=lambda t: t[0])
        best = candidates[0]
        _, best_row, best_col, cx, cy, cw, ch = best

        # Place bubble centered in the safest cell, clamped to panel
        new_bw = min(bw, cw - 16)
        new_bh = min(bh, ch - 16)
        new_bx = cx + (cw - new_bw) / 2
        new_by = cy + (ch - new_bh) / 2

        # Convert back to percentages
        new_box = {
            "x": round(max(2, new_bx) / img_w * 100, 1),
            "y": round(max(2, new_by) / img_h * 100, 1),
            "w": round(new_bw / img_w * 100, 1),
            "h": round(new_bh / img_h * 100, 1),
        }

        # Adjust tail direction to point toward the speaker (center-bottom of panel)
        # If bubble is in top half, tail points down; if in bottom half, tail points up
        bubble_center_y_pct = new_box["y"] + new_box["h"] / 2
        bubble_center_x_pct = new_box["x"] + new_box["w"] / 2
        if bubble_center_y_pct < 50:
            # Bubble is in top half — tail points down toward character
            if bubble_center_x_pct < 50:
                new_tail = "down-left"
            else:
                new_tail = "down-right"
        else:
            # Bubble is in bottom half — tail points up toward character
            if bubble_center_x_pct < 50:
                new_tail = "up-left"
            else:
                new_tail = "up-right"

        return new_box, new_tail

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
        panel_aspect: str = "4:3",
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
            f"Generate an image of a single comic panel, panel {panel_index} of {panel_count}. "
            f"Style: {style_name}. {style_suffix} "
            f"{anchor}"
            f"Scene: {panel_description}. "
            "Show one clear protagonist and a readable environment. "
            "Use dynamic composition and clean linework. "
            "Correct human anatomy: five fingers per hand, two arms, two legs, limbs attached at proper joints. "
            "When holding an object, show a natural grip with fingers wrapped around it. "
            "No extra, merged, duplicated, or floating limbs or fingers. "
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

        image, reason = self._gemini_multimodal_predict(
            prompt=instruction,
            image_paths=refs if refs else [],
            aspect_ratio=panel_aspect,
            timeout=180,
        )

        if image is not None:
            return image

        image, _ = self._retry_with_rephrased_prompt(
            model_name=settings.GEMINI_IMAGE_MODEL_MULTIMODAL,
            original_prompt=instruction,
            aspect_ratio=panel_aspect,
            image_paths=refs if refs else [],
            context_words=["age", "child", "children", "minor", "baby", "kid"],
        )
        return image

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
            f"Generate an image of a comic book cover illustration. Style: {style_name}. {style_suffix} "
            f"Title concept: {title}. "
            "Heroic full-body protagonist, dramatic pose, cinematic lighting, strong depth, full bleed. "
            "Keep generous visual breathing room at top and bottom for later typography overlays. "
            "Correct anatomy: five fingers per hand, proper limb placement, natural grip on held objects. "
            "No extra, merged, duplicated, or floating limbs or fingers. "
            "No text, letters, words, logos, watermarks, speech bubbles, or panel borders. "
            "Never paste, trace, or directly copy the source photo. "
            "No photoreal skin pores, camera noise, DSLR lighting, or raw photo artifacts."
        )

        refs: list[str] = []
        if identity_sheet_path and os.path.exists(identity_sheet_path):
            refs.append(identity_sheet_path)
        if child_photo_path and os.path.exists(child_photo_path):
            refs.append(child_photo_path)

        image, reason = self._gemini_multimodal_predict(
            prompt=instruction,
            image_paths=refs if refs else [],
            aspect_ratio="3:4",
            timeout=180,
        )

        if image is not None:
            return image

        image, _ = self._retry_with_rephrased_prompt(
            model_name=settings.GEMINI_IMAGE_MODEL_MULTIMODAL,
            original_prompt=instruction,
            aspect_ratio="3:4",
            image_paths=refs if refs else [],
            context_words=["age", "child", "children", "minor", "baby", "kid"],
        )
        return image

    def generate_comic_panel_with_imagen(
        self,
        panel_description: str,
        child_photo_path: str,
        style_suffix: str,
        style_name: str,
        panel_index: int,
        panel_count: int,
        aspect_ratio: str = "4:3",
        character_description: str = "",
    ) -> Optional[Image.Image]:
        """Fallback to Imagen (text-to-image :predict) when Gemini returns no image.

        Imagen is a pure image model — no text-vs-image ambiguity. It cannot
        take reference images (no subject-reference here), so we rely on the
        text prompt + style suffix + character description for consistency.
        """
        if not settings.COMIC_PANEL_IMAGEN_FALLBACK:
            return None
        self.initialize()
        char_anchor = ""
        if character_description:
            char_anchor = (
                f"The protagonist: {character_description}. "
                "Draw this exact character — same face, hair, build, skin tone, "
                "and outfit. Keep them consistent across all panels. "
            )
        prompt = (
            f"Single comic panel, panel {panel_index} of {panel_count}. "
            f"Style: {style_name}. {style_suffix} "
            f"{char_anchor}"
            f"Scene: {panel_description}. "
            "Show one clear protagonist and a readable environment. "
            "Dynamic composition, clean linework. "
            "Correct anatomy: five fingers per hand, proper limb placement, natural grip on held objects. "
            "No extra, merged, duplicated, or floating limbs or fingers. "
            "No text, words, letters, speech bubbles, watermarks, logos."
        )
        image = self._imagen_predict(
            prompt=prompt,
            aspect_ratio=aspect_ratio,
        )
        if image is not None:
            return image

        fallback_model = "imagen-3.0-fast-generate-001"
        if fallback_model != settings.GEMINI_IMAGE_MODEL_TXT2IMG:
            print(f"[Imagen] primary model failed, trying {fallback_model}")
            image = self._imagen_predict(
                prompt=prompt,
                aspect_ratio=aspect_ratio,
                model_name=fallback_model,
            )
        return image

    def generate_cover_image_with_imagen(
        self,
        child_photo_path: str,
        style_suffix: str,
        style_name: str,
        title: str,
    ) -> Optional[Image.Image]:
        """Fallback cover generation via Imagen :predict."""
        if not settings.COMIC_PANEL_IMAGEN_FALLBACK:
            return None
        self.initialize()
        prompt = (
            f"Comic book cover illustration. Style: {style_name}. {style_suffix} "
            f"Title concept: {title}. "
            "Heroic full-body protagonist, dramatic pose, cinematic lighting, "
            "strong depth, full bleed. "
            "Keep generous visual breathing room at top and bottom. "
            "No text, words, letters, logos, watermarks, speech bubbles."
        )
        image = self._imagen_predict(
            prompt=prompt,
            aspect_ratio="3:4",
        )
        return image


face_prep_service = FacePreparationService()
image_generation_service = GeminiImageService()
