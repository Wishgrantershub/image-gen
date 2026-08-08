"""Email delivery service using the Resend Python SDK.

Mirrors the working pattern from the customersahaay reference repo:
- Uses the official `resend` SDK (not raw HTTP)
- Uses `onboarding@resend.dev` as the sender (Resend's sandbox sender)
- PDF attached as base64-encoded content

NOTE: With `onboarding@resend.dev` (unverified domain), Resend only
delivers to the email address associated with your Resend account.
For production, verify a custom domain and change RESEND_FROM_EMAIL.
"""

import base64
import logging
import os
import socket
import time
import uuid
from typing import Optional

import resend

from app.config import settings

logger = logging.getLogger("comicme.email")

_MAX_RETRIES = 3


def _get_sender() -> str:
    """Return the from address. Defaults to Resend's sandbox sender."""
    raw = (settings.RESEND_FROM_EMAIL or "").strip()
    if raw and "@" in raw:
        return raw
    return "ComicMe <onboarding@resend.dev>"


def _is_configured() -> bool:
    return bool(settings.COMIC_EMAIL_ENABLED and settings.RESEND_API_KEY)


def _is_retryable(exc: Exception) -> bool:
    """Classify whether an exception warrants a retry."""
    if isinstance(exc, (ConnectionError, ConnectionRefusedError, socket.gaierror)):
        return True
    if isinstance(exc, (OSError, TimeoutError)):
        return True
    msg = str(exc).lower()
    if any(kw in msg for kw in ("failed to resolve", "connection", "timeout", "reset")):
        return True
    if hasattr(exc, "status_code"):
        return exc.status_code in (429, 500, 502, 503, 504)
    return False


def send_comic_email(
    to_email: str,
    hero_name: str,
    title: str,
    style_name: str,
    share_url: str,
    pdf_path: Optional[str] = None,
) -> bool:
    """Send the completed comic email with optional PDF attachment.

    Retries up to _MAX_RETRIES times with exponential backoff on transient
    failures (DNS, connection, rate limit, server errors). Returns True on
    success, False on permanent failure (logged but never raises).
    """
    if not _is_configured():
        logger.info("[email] skipping — RESEND_API_KEY not set or email disabled")
        return False
    if not to_email or "@" not in to_email:
        logger.warning("[email] invalid recipient: %s", to_email)
        return False

    resend.api_key = settings.RESEND_API_KEY

    subject = f"Your {style_name} comic is ready!"
    hero_display = hero_name or "Hero"
    html = _build_html(hero_display, title, style_name, share_url)

    params: dict = {
        "from": _get_sender(),
        "to": [to_email],
        "subject": subject,
        "html": html,
    }

    if pdf_path and os.path.exists(pdf_path) and os.path.getsize(pdf_path) > 0:
        try:
            with open(pdf_path, "rb") as f:
                pdf_bytes = f.read()
            params["attachments"] = [
                {
                    "filename": f"comicme_{title.replace(' ', '_')[:40]}.pdf",
                    "content": base64.b64encode(pdf_bytes).decode(),
                }
            ]
        except Exception as e:
            logger.warning("[email] could not attach PDF: %s", e)

    last_exc: Optional[Exception] = None
    for attempt in range(_MAX_RETRIES + 1):
        try:
            idempotency_key = str(uuid.uuid4())
            email = resend.Emails.send(params, idempotency_key=idempotency_key)
            logger.info(
                "[email] sent to %s (id=%s, attempt=%d/%d)",
                to_email,
                getattr(email, "id", "?"),
                attempt + 1,
                _MAX_RETRIES + 1,
            )
            return True
        except Exception as e:
            last_exc = e
            if attempt < _MAX_RETRIES and _is_retryable(e):
                delay = 2**attempt
                logger.warning(
                    "[email] attempt %d/%d failed (%s), retrying in %ds: %s",
                    attempt + 1,
                    _MAX_RETRIES + 1,
                    type(e).__name__,
                    delay,
                    e,
                )
                time.sleep(delay)
            else:
                break

    logger.error(
        "[email] Resend send failed after %d attempts to %s: %s",
        _MAX_RETRIES + 1,
        to_email,
        last_exc,
    )
    return False


def _build_html(hero_name: str, title: str, style_name: str, share_url: str) -> str:
    return f"""\
<!DOCTYPE html>
<html>
<body style="margin:0;padding:0;background:#FAF7EE;font-family:Helvetica,Arial,sans-serif;">
  <div style="max-width:560px;margin:0 auto;padding:32px 24px;">
    <div style="text-align:center;margin-bottom:32px;">
      <h1 style="font-size:28px;color:#0F0F0F;margin:0;letter-spacing:-0.5px;">
        Your comic is ready!
      </h1>
      <p style="color:#666;font-size:15px;margin:8px 0 0;">
        {hero_name}'s {style_name} adventure has been inked.
      </p>
    </div>

    <div style="background:#0F0F0F;border-radius:12px;padding:32px 24px;text-align:center;margin-bottom:24px;">
      <p style="color:#FFD700;font-size:13px;text-transform:uppercase;letter-spacing:2px;margin:0 0 8px;font-weight:bold;">
        {style_name} Edition
      </p>
      <h2 style="color:#fff;font-size:22px;margin:0 0 16px;">
        {title}
      </h2>
      <p style="color:#aaa;font-size:14px;margin:0 0 20px;">
        Your PDF is attached to this email. You can also view it online anytime.
      </p>
      <a href="{share_url}"
         style="display:inline-block;background:#FFD700;color:#0F0F0F;font-weight:bold;
                text-decoration:none;padding:14px 32px;border-radius:8px;font-size:15px;">
        View Online
      </a>
    </div>

    <div style="border:2px solid #0F0F0F;border-radius:8px;padding:20px;margin-bottom:24px;">
      <p style="color:#0F0F0F;font-size:14px;margin:0 0 12px;font-weight:bold;">
        Save your share link:
      </p>
      <p style="color:#666;font-size:13px;margin:0;word-break:break-all;font-family:monospace;">
        {share_url}
      </p>
    </div>

    <p style="color:#999;font-size:12px;text-align:center;margin:24px 0 0;">
      Made with ComicMe - Your AI comic generator.<br/>
      This comic was created in a few minutes. Make another at comicme.app
    </p>
  </div>
</body>
</html>
"""
