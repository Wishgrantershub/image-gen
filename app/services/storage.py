"""PDF storage abstraction.

We support two backends:
  - ``local``  : write PDFs to ``output/comics/`` and serve them via the
                 ``/api/comics/{id}/pdf`` endpoint. Default in dev.
  - ``r2``     : upload PDFs to a Cloudflare R2 bucket and serve them via
                 short-lived presigned URLs. Default in prod.

The choice is controlled by ``settings.PDF_STORAGE_BACKEND`` plus the
``R2_*`` environment variables. If the backend is unavailable, the factory
falls back to local storage so the app never breaks.
"""

from __future__ import annotations

import logging
import os
from abc import ABC, abstractmethod
from typing import Optional

from app.config import (
    R2_EFFECTIVE_BUCKET,
    R2_EFFECTIVE_ENDPOINT,
    R2_EFFECTIVE_PUBLIC_URL,
    settings,
)


logger = logging.getLogger(__name__)


class PDFStorage(ABC):
    """Common interface for PDF storage backends."""

    backend_name: str = "abstract"

    @abstractmethod
    def save(self, story_id: int, pdf_path: str) -> str:
        """Persist the PDF and return a storage key (URL or relative path).

        ``pdf_path`` is the absolute local filesystem path of the file to
        upload. The returned key is what we store in ``Story.pdf_storage_key``
        so we can find the same file later via ``get_download_url``.
        """

    @abstractmethod
    def get_download_url(self, story_id: int) -> Optional[str]:
        """Return a URL the browser can use to download the PDF.

        Returns None if the file is not available (e.g. R2 upload failed
        and no local copy remains). For the local backend this is a
        relative path the FastAPI app serves.
        """

    @abstractmethod
    def exists(self, story_id: int) -> bool:
        """Check if a PDF is currently stored for the given story."""


class LocalStorage(PDFStorage):
    backend_name = "local"

    def __init__(self, base_dir: str):
        self.base_dir = base_dir
        os.makedirs(self.base_dir, exist_ok=True)

    def _path_for(self, story_id: int) -> str:
        return os.path.join(self.base_dir, f"comic_{story_id}.pdf")

    def save(self, story_id: int, pdf_path: str) -> str:
        if not os.path.exists(pdf_path):
            raise FileNotFoundError(pdf_path)
        target = self._path_for(story_id)
        with open(pdf_path, "rb") as src, open(target, "wb") as dst:
            dst.write(src.read())
        logger.info(
            "[storage] local save story=%s size=%dKB path=%s",
            story_id,
            os.path.getsize(target) // 1024,
            target,
        )
        return target

    def get_download_url(self, story_id: int) -> Optional[str]:
        if not self.exists(story_id):
            return None
        return f"/api/comics/{story_id}/pdf"

    def exists(self, story_id: int) -> bool:
        return os.path.exists(self._path_for(story_id))


class R2Storage(PDFStorage):
    """Cloudflare R2 storage using the boto3 S3-compatible API.

    R2 is preferred over AWS S3 for this use case because R2 has zero egress
    fees — the dominant cost for downloadable PDF files. boto3 talks to R2
    via the same S3 API by pointing at the bucket's ``<account>.r2.cloudflarestorage.com``
    endpoint.

    Two configuration tricks are required for R2:
      - ``addressing_style="path"`` — R2 does not support virtual-hosted
        style S3 URLs, and presigned URLs fail without this.
      - ``region_name="auto"`` — R2 is region-less.
    """

    backend_name = "r2"

    def __init__(
        self,
        account_id: str,
        access_key_id: str,
        secret_access_key: str,
        bucket: str,
        public_base_url: str = "",
        presign_expiry_seconds: int = 3600,
        endpoint_url: str = "",
    ):
        try:
            import boto3  # noqa: F401  (lazy import so local dev without boto3 still works)
            from botocore.client import Config  # noqa: F401
        except ImportError as e:
            raise RuntimeError(
                "boto3 is required for R2Storage. Install it with `pip install boto3`."
            ) from e
        self.account_id = account_id
        self.bucket = bucket
        self.public_base_url = public_base_url.rstrip("/")
        self.presign_expiry_seconds = presign_expiry_seconds
        if not endpoint_url:
            endpoint_url = f"https://{account_id}.r2.cloudflarestorage.com"
        self._endpoint = endpoint_url
        self._client = boto3.client(
            "s3",
            endpoint_url=endpoint_url,
            aws_access_key_id=access_key_id,
            aws_secret_access_key=secret_access_key,
            config=Config(
                signature_version="s3v4",
                s3={"addressing_style": "path"},
            ),
            region_name="auto",
        )

    def _public_url_for(self, key: str) -> str:
        if self.public_base_url:
            return f"{self.public_base_url}/{key}"
        # Derive from endpoint: https://<account>.r2.cloudflarestorage.com -> https://pub-<account>.r2.dev
        m = self._endpoint.split("//", 1)[-1].split(".r2.", 1)[0]
        if m:
            return f"https://pub-{m}.r2.dev/{key}"
        return f"{self._endpoint}/{self.bucket}/{key}"

    def _key_for(self, story_id: int) -> str:
        return f"comics/comic_{story_id}.pdf"

    def save(self, story_id: int, pdf_path: str) -> str:
        if not os.path.exists(pdf_path):
            raise FileNotFoundError(pdf_path)
        key = self._key_for(story_id)
        size_kb = os.path.getsize(pdf_path) // 1024
        logger.info(
            "[storage] R2 upload start story=%s key=%s size=%dKB endpoint=%s",
            story_id,
            key,
            size_kb,
            self._endpoint,
        )
        with open(pdf_path, "rb") as f:
            self._client.upload_fileobj(
                f,
                self.bucket,
                key,
                ExtraArgs={"ContentType": "application/pdf"},
            )
        logger.info(
            "[storage] R2 upload success story=%s key=%s -> %s",
            story_id,
            key,
            self._public_url_for(key),
        )
        return key

    def get_download_url(self, story_id: int) -> Optional[str]:
        key = self._key_for(story_id)
        if self.public_base_url:
            return f"{self.public_base_url}/{key}"
        try:
            return self._client.generate_presigned_url(
                "get_object",
                Params={"Bucket": self.bucket, "Key": key},
                ExpiresIn=self.presign_expiry_seconds,
            )
        except Exception as e:
            logger.warning("[storage] R2 presign failed for story %s: %s", story_id, e)
            return None

    def exists(self, story_id: int) -> bool:
        try:
            self._client.head_object(Bucket=self.bucket, Key=self._key_for(story_id))
            return True
        except Exception:
            return False


_storage: Optional[PDFStorage] = None


def get_storage() -> PDFStorage:
    """Return the active PDF storage backend, instantiating on first call."""
    global _storage
    if _storage is not None:
        return _storage

    backend = (settings.PDF_STORAGE_BACKEND or "local").strip().lower()
    if backend == "r2" or settings.R2_ENABLED:
        try:
            _storage = R2Storage(
                account_id=settings.R2_ACCOUNT_ID,
                access_key_id=settings.R2_ACCESS_KEY_ID,
                secret_access_key=settings.R2_SECRET_ACCESS_KEY,
                bucket=R2_EFFECTIVE_BUCKET,
                public_base_url=R2_EFFECTIVE_PUBLIC_URL,
                presign_expiry_seconds=settings.R2_PRESIGN_EXPIRY_SECONDS,
                endpoint_url=R2_EFFECTIVE_ENDPOINT,
            )
            logger.info(
                "[storage] R2 active bucket=%s endpoint=%s public_url=%s",
                R2_EFFECTIVE_BUCKET,
                R2_EFFECTIVE_ENDPOINT or "(auto)",
                R2_EFFECTIVE_PUBLIC_URL or "(auto)",
            )
            return _storage
        except Exception as e:
            logger.warning("[storage] R2 init failed (%s) — falling back to local", e)

    from app.config import COMIC_OUTPUT_DIR

    _storage = LocalStorage(COMIC_OUTPUT_DIR)
    logger.info("[storage] local active dir=%s", COMIC_OUTPUT_DIR)
    return _storage


def reset_storage() -> None:
    """Drop the cached storage instance. Useful in tests."""
    global _storage
    _storage = None
