from pydantic_settings import BaseSettings
from typing import Optional
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

    class Config:
        env_file = ".env"
        extra = "ignore"

settings = Settings()

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
UPLOAD_DIR = os.path.join(BASE_DIR, "uploads")
OUTPUT_DIR = os.path.join(BASE_DIR, "output")
MODELS_DIR = os.path.join(BASE_DIR, "models")

os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)
os.makedirs(MODELS_DIR, exist_ok=True)