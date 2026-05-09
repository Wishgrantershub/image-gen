from pydantic_settings import BaseSettings
from typing import Optional, Tuple
import os


class Settings(BaseSettings):
    GEMINI_API_KEY: str = ""
    DATABASE_URL: str = "sqlite:///./diffrun.db"
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    SD_MODEL_ID: str = "runwayml/stable-diffusion-v1-5"
    HF_TOKEN: Optional[str] = None
    SECRET_KEY: str = "diffrun-secret-key-change-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

    IMAGE_WIDTH: int = 512
    IMAGE_HEIGHT: int = 768
    NUM_INFERENCE_STEPS: int = 30
    GUIDANCE_SCALE: float = 7.5
    FACE_SCALE: float = 0.7
    STYLE_STRENGTH: float = 0.5
    USE_CPU_OFFLOAD: bool = True

    IP_ADAPTER_MODEL: str = "h94/IP-Adapter-FaceID"
    IP_ADAPTER_WEIGHT: str = "ip-adapter-faceid-plusv2_sd15.bin"
    IMAGE_ENCODER_MODEL: str = "laion/CLIP-ViT-H-14-laion2B-s32B-b79K"
    GEMINI_TEXT_MODEL: str = "gemini-2.5-flash"
    GEMINI_IMAGE_MODEL: str = "gemini-2.5-flash-image"
    TEMPLATE_BASE_DIR: str = "templates/base"
    TEMPLATE_MASK_DIR: str = "templates/mask"
    MAX_PAGE_RETRIES: int = 3
    QA_MAX_PHOTO_PASTE_RISK: int = 3
    QA_MIN_STYLE_MATCH: int = 8
    QA_MIN_IDENTITY_MATCH: int = 7

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
UPLOAD_DIR = os.path.join(BASE_DIR, "uploads")
OUTPUT_DIR = os.path.join(BASE_DIR, "output")
MODELS_DIR = os.path.join(BASE_DIR, "models")
TEMPLATE_BASE_DIR = os.path.join(BASE_DIR, settings.TEMPLATE_BASE_DIR)
TEMPLATE_MASK_DIR = os.path.join(BASE_DIR, settings.TEMPLATE_MASK_DIR)

os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)
os.makedirs(MODELS_DIR, exist_ok=True)
os.makedirs(TEMPLATE_BASE_DIR, exist_ok=True)
os.makedirs(TEMPLATE_MASK_DIR, exist_ok=True)
