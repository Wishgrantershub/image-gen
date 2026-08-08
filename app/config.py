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
    GEMINI_IMAGE_MODEL_MULTIMODAL: str = "gemini-2.5-flash-image"
    GEMINI_IMAGE_MODEL_TXT2IMG: str = "imagen-4.0-generate-001"
    GEMINI_IMAGE_MODEL_SUBJECT_REF: str = "imagen-3.0-capability-001"
    TEMPLATE_BASE_DIR: str = "templates/base"
    TEMPLATE_MASK_DIR: str = "templates/mask"
    MAX_PAGE_RETRIES: int = 3
    QA_MAX_PHOTO_PASTE_RISK: int = 3
    QA_MIN_STYLE_MATCH: int = 8
    QA_MIN_IDENTITY_MATCH: int = 7

    COMIC_PANEL_WIDTH: int = 1024
    COMIC_PANEL_HEIGHT: int = 768
    COMIC_ASPECT: str = "4:3"
    COMIC_MAX_RETRIES: int = 2
    COMIC_DEFAULT_PANELS: int = 6
    COMIC_MAX_PANELS: int = 8

    COMIC_PANEL_MAX_ATTEMPTS: int = 3
    COMIC_PANEL_IMAGEN_FALLBACK: bool = True
    COMIC_QA_ENABLED: bool = False
    COMIC_QA_RETRY: int = 1
    COMIC_PANEL_MIN_SIZE: int = 400
    COMIC_PANEL_BATCH_SIZE: int = 1

    RAZORPAY_KEY_ID: str = ""
    RAZORPAY_KEY_SECRET: str = ""
    RAZORPAY_LIVE_MODE: bool = False
    RAZORPAY_ENABLED: bool = False

    CORS_ORIGINS: str = ""
    ENVIRONMENT: str = "development"

    PDF_STORAGE_BACKEND: str = "local"
    R2_ENABLED: bool = False
    R2_ACCOUNT_ID: str = ""
    R2_ACCESS_KEY_ID: str = ""
    R2_SECRET_ACCESS_KEY: str = ""
    R2_BUCKET: str = "comicme-pdfs"
    R2_PUBLIC_BASE_URL: str = ""
    R2_PRESIGN_EXPIRY_SECONDS: int = 3600

    # --- Neon Postgres (alternative to DATABASE_URL) ---
    # Either set DATABASE_URL directly, or set all of DB_* and we will build
    # the URL. SSL is handled via the sslmode query-string param (Neon needs
    # sslmode=require at minimum).
    DB_HOST: str = ""
    DB_PORT: int = 5432
    DB_USER: str = ""
    DB_PASSWORD: str = ""
    DB_NAME: str = "neondb"
    DB_SSLMODE: str = "require"

    # --- Cloudflare R2 (extended naming) ---
    # Preferred var names (match ourverse convention). Falls back to R2_*
    # above if these are empty.
    R2_ENDPOINT: str = ""
    R2_BUCKET_NAME: str = ""
    R2_PUBLIC_URL: str = ""

    # --- Resend (email delivery for completed comics) ---
    RESEND_API_KEY: str = ""
    RESEND_FROM_EMAIL: str = "ComicMe <onboarding@resend.dev>"
    COMIC_EMAIL_ENABLED: bool = True

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()


def _mask_url(url: str) -> str:
    """Strip the password from a database URL for safe logging."""
    if not url:
        return ""
    try:
        scheme, rest = url.split("://", 1)
    except ValueError:
        return url
    if "@" not in rest:
        return f"{scheme}://{rest}"
    creds, host = rest.rsplit("@", 1)
    if ":" in creds:
        user, _ = creds.split(":", 1)
        return f"{scheme}://{user}:***@{host}"
    return f"{scheme}://{creds}@{host}"


def neon_database_url() -> str:
    """Return the Postgres URL to use at runtime.

    Priority:
      1. If ``DATABASE_URL`` is set and is *not* a sqlite URL, use
         it as-is (lets you point at any DB by URL).
      2. Otherwise, if ``DB_HOST`` is set, build the URL from
         ``DB_HOST/DB_PORT/DB_USER/DB_PASSWORD/DB_NAME/DB_SSLMODE``
         (explicit Neon UX for Railway deploy).
      3. Fall back to local SQLite so dev keeps working.
    """
    explicit = (settings.DATABASE_URL or "").strip()
    if explicit and not explicit.startswith("sqlite"):
        return explicit
    if settings.DB_HOST:
        return (
            f"postgresql+psycopg://{settings.DB_USER}:{settings.DB_PASSWORD}"
            f"@{settings.DB_HOST}:{settings.DB_PORT}/{settings.DB_NAME}"
            f"?sslmode={settings.DB_SSLMODE}"
        )
    return "sqlite:///./diffrun.db"


# Convenience aliases for R2 (preferred names win, fall back to legacy).
R2_EFFECTIVE_BUCKET: str = (
    settings.R2_BUCKET_NAME or settings.R2_BUCKET or "comicme-pdfs"
).strip()
R2_EFFECTIVE_PUBLIC_URL: str = (
    settings.R2_PUBLIC_URL or settings.R2_PUBLIC_BASE_URL or ""
).strip()
R2_EFFECTIVE_ENDPOINT: str = (
    settings.R2_ENDPOINT
    or (
        f"https://{settings.R2_ACCOUNT_ID}.r2.cloudflarestorage.com"
        if settings.R2_ACCOUNT_ID
        else ""
    )
).strip()


BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
UPLOAD_DIR = os.path.join(BASE_DIR, "uploads")
OUTPUT_DIR = os.path.join(BASE_DIR, "output")
COMIC_OUTPUT_DIR = os.path.join(BASE_DIR, "output", "comics")
COMIC_PANEL_DIR = os.path.join(BASE_DIR, "output", "comic_panels")
COMIC_SHEET_DIR = os.path.join(BASE_DIR, "output", "comic_sheets")
MODELS_DIR = os.path.join(BASE_DIR, "models")
TEMPLATE_BASE_DIR = os.path.join(BASE_DIR, settings.TEMPLATE_BASE_DIR)
TEMPLATE_MASK_DIR = os.path.join(BASE_DIR, settings.TEMPLATE_MASK_DIR)

os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)
os.makedirs(COMIC_OUTPUT_DIR, exist_ok=True)
os.makedirs(COMIC_PANEL_DIR, exist_ok=True)
os.makedirs(COMIC_SHEET_DIR, exist_ok=True)
os.makedirs(MODELS_DIR, exist_ok=True)
os.makedirs(TEMPLATE_BASE_DIR, exist_ok=True)
os.makedirs(TEMPLATE_MASK_DIR, exist_ok=True)
