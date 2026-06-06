from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import logging
import os

from app.config import (
    OUTPUT_DIR,
    COMIC_OUTPUT_DIR,
    COMIC_PANEL_DIR,
    COMIC_SHEET_DIR,
    R2_EFFECTIVE_BUCKET,
    R2_EFFECTIVE_ENDPOINT,
    R2_EFFECTIVE_PUBLIC_URL,
    _mask_url,
    neon_database_url,
    settings,
)
from app.database import init_db
from app.routers import auth, children, books, stories, images
from app.routers import comics, library, payment

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-7s %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("comicme")

app = FastAPI(
    title="ComicMe API",
    description="Personalized AI Comic Generator - Turn anyone into a comic book hero in 60 seconds.",
    version="2.0.0",
)


def _cors_origins() -> list[str]:
    raw = (settings.CORS_ORIGINS or "").strip()
    if not raw:
        return ["*"] if settings.ENVIRONMENT != "production" else []
    return [o.strip() for o in raw.split(",") if o.strip()]


_cors = _cors_origins()
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(children.router)
app.include_router(books.router)
app.include_router(stories.router)
app.include_router(images.router)
app.include_router(comics.router)
app.include_router(payment.router)
app.include_router(library.router)


@app.on_event("startup")
def on_startup():
    init_db()
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    os.makedirs(COMIC_OUTPUT_DIR, exist_ok=True)
    os.makedirs(COMIC_PANEL_DIR, exist_ok=True)
    os.makedirs(COMIC_SHEET_DIR, exist_ok=True)
    logger.info(
        "startup complete | env=%s db=%s r2=%s razorpay=%s cors_origins=%d",
        settings.ENVIRONMENT,
        _mask_url(neon_database_url()),
        (R2_EFFECTIVE_ENDPOINT or "(none)")
        + (f" bucket={R2_EFFECTIVE_BUCKET}" if R2_EFFECTIVE_ENDPOINT else ""),
        "enabled" if settings.RAZORPAY_ENABLED else "disabled",
        len(_cors),
    )


@app.get("/")
def root():
    return {
        "message": "ComicMe API",
        "tagline": "Turn anyone into a comic book hero in 60 seconds.",
        "status": "running",
        "endpoints": {
            "auth": "/api/auth",
            "children": "/api/children",
            "comics": "/api/comics",
            "styles": "/api/comics/styles",
            "samples": "/api/comics/samples",
            "payment": "/api/payment",
            "docs": "/docs",
        },
    }


@app.get("/health")
def health_check():
    return {"status": "healthy"}


@app.get("/healthz")
def healthz():
    return {"status": "ok"}


if __name__ == "__main__":
    import uvicorn
    from app.config import settings

    uvicorn.run(
        "app.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=True,
    )
