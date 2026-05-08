import os
import numpy as np
from typing import Optional, List
import torch
from PIL import Image
from pathlib import Path

from app.config import OUTPUT_DIR, MODELS_DIR

class FaceEmbeddingService:
    def __init__(self):
        self.model = None
        self.app = None

    def initialize(self):
        if self.model is not None:
            return
        try:
            from insightface.app import FaceAnalysis
            self.app = FaceAnalysis(name='buffalo_l', providers=['CUDAExecutionProvider', 'CPUExecutionProvider'])
            self.app.prepare(ctx_id=0, det_size=(640, 640))
            print("InsightFace initialized successfully")
        except Exception as e:
            print(f"Failed to initialize InsightFace: {e}")
            raise

    def extract_face_embedding(self, image_path: str) -> Optional[np.ndarray]:
        if self.app is None:
            self.initialize()

        try:
            img = Image.open(image_path).convert("RGB")
            img_arr = np.array(img)
            faces = self.app.get(img_arr)

            if faces:
                embedding = faces[0].embedding
                return embedding.tolist()
            return None
        except Exception as e:
            print(f"Error extracting face embedding: {e}")
            return None


class ImageGenerationService:
    def __init__(self):
        self.pipeline = None
        self.ip_adapter = None

    def initialize(self):
        if self.pipeline is not None:
            return

        try:
            from diffusers import StableDiffusionImg2ImgPipeline
            from diffusers import IPAdapterPlus

            print("Loading Stable Diffusion model... (this may take a few minutes)")

            self.pipeline = StableDiffusionImg2ImgPipeline.from_pretrained(
                "runwayml/stable-diffusion-v1-5",
                torch_dtype=torch.float16,
                safety_checker=None,
            )

            self.pipeline = self.pipeline.to("cuda")
            self.pipeline.enable_vae_tiling()

            print("Stable Diffusion initialized successfully")
        except Exception as e:
            print(f"Failed to initialize Stable Diffusion: {e}")
            raise

    def generate_image(
        self,
        prompt: str,
        face_embedding: Optional[List[float]] = None,
        init_image: Optional[Image.Image] = None,
        strength: float = 0.75,
        guidance_scale: float = 7.5,
        num_inference_steps: int = 30
    ) -> Optional[Image.Image]:
        if self.pipeline is None:
            self.initialize()

        try:
            if face_embedding and init_image is not None:
                print(f"Generating image with face embedding + img2img...")
                result = self.pipeline(
                    prompt=prompt,
                    image=init_image,
                    strength=strength,
                    guidance_scale=guidance_scale,
                    num_inference_steps=num_inference_steps,
                ).images[0]
            elif init_image is not None:
                print(f"Generating image with img2img...")
                result = self.pipeline(
                    prompt=prompt,
                    image=init_image,
                    strength=strength,
                    guidance_scale=guidance_scale,
                    num_inference_steps=num_inference_steps,
                ).images[0]
            else:
                print(f"Generating image from text only...")
                from diffusers import StableDiffusionPipeline
                text_pipeline = StableDiffusionPipeline.from_pretrained(
                    "runwayml/stable-diffusion-v1-5",
                    torch_dtype=torch.float16,
                    safety_checker=None,
                ).to("cuda")
                result = text_pipeline(
                    prompt=prompt,
                    guidance_scale=guidance_scale,
                    num_inference_steps=num_inference_steps,
                ).images[0]

            return result
        except Exception as e:
            print(f"Error generating image: {e}")
            return None

    def save_image(self, image: Image.Image, filename: str) -> str:
        output_path = os.path.join(OUTPUT_DIR, filename)
        image.save(output_path)
        return output_path


face_embedding_service = FaceEmbeddingService()
image_generation_service = ImageGenerationService()