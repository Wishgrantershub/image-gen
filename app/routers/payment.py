import hashlib
import hmac
import logging
import os
import secrets
import time
import uuid
from datetime import datetime
from typing import Any, Dict, Optional

import requests
from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models import Order, PaymentStatus, Story, StoryStatus, User
from app.schemas.comic import (
    PaymentOrderRequest,
    PaymentOrderResponse,
    PaymentVerifyRequest,
    PaymentVerifyResponse,
)
from app.services.auth_service import (
    get_current_active_user,
    get_current_user_optional,
)
from app.services.comic_styles import TIER_CONFIG, get_tier

router = APIRouter(prefix="/api/payment", tags=["Payment"])

logger = logging.getLogger("comicme.payment")

RAZORPAY_API_BASE = "https://api.razorpay.com/v1"


def _razorpay_configured() -> bool:
    return bool(
        settings.RAZORPAY_KEY_ID
        and settings.RAZORPAY_KEY_SECRET
        and "your_key" not in settings.RAZORPAY_KEY_ID.lower()
        and "your_key" not in settings.RAZORPAY_KEY_SECRET.lower()
    )


def _razorpay_active() -> bool:
    return settings.RAZORPAY_ENABLED and _razorpay_configured()


def verify_razorpay_signature(
    razorpay_order_id: str, razorpay_payment_id: str, razorpay_signature: str
) -> bool:
    if not (razorpay_order_id and razorpay_payment_id and razorpay_signature):
        return False
    if not settings.RAZORPAY_KEY_SECRET:
        return False
    payload = f"{razorpay_order_id}|{razorpay_payment_id}".encode("utf-8")
    expected = hmac.new(
        settings.RAZORPAY_KEY_SECRET.encode("utf-8"), payload, hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(expected, razorpay_signature)


def _owns_story(
    story: Story,
    current_user: Optional[User],
    session_token: str,
) -> bool:
    """True if the caller owns the story by login OR by session token."""
    if current_user is not None and story.user_id == current_user.id:
        return True
    if session_token and story.session_token == session_token:
        return True
    return False


def _mark_story_purchased(
    db: Session,
    story: Story,
    razorpay_payment_id: str,
    razorpay_order_id: str,
    amount: float,
) -> None:
    """Flip a story to PURCHASED + create/update the Order row + push to storage.

    Idempotent: if the story is already PURCHASED, the only side effect is
    ensuring the Order row exists and the storage key is set. Safe to call
    from both the real-Razorpay verify path and the offline demo-bypass.
    """
    now = datetime.utcnow()
    was_paid = story.status == StoryStatus.PURCHASED
    story.status = StoryStatus.PURCHASED
    story.paid_at = story.paid_at or now
    if not story.amount or story.amount <= 0:
        story.amount = amount
    db.commit()

    existing = (
        db.query(Order).filter(Order.razorpay_order_id == razorpay_order_id).first()
    )
    if existing is None:
        order = Order(
            story_id=story.id,
            user_id=story.user_id,
            amount=amount,
            currency=story.currency or "INR",
            payment_status=PaymentStatus.COMPLETED,
            razorpay_order_id=razorpay_order_id,
            razorpay_payment_id=razorpay_payment_id,
        )
        db.add(order)
    else:
        existing.payment_status = PaymentStatus.COMPLETED
        existing.razorpay_payment_id = razorpay_payment_id
        if existing.story_id != story.id:
            existing.story_id = story.id
    db.commit()

    if story.pdf_path and os.path.exists(story.pdf_path):
        try:
            from app.services.storage import get_storage

            storage = get_storage()
            storage_key = storage.save(story.id, story.pdf_path)
            story.pdf_storage_key = storage_key
            if storage.backend_name != "local":
                dl = storage.get_download_url(story.id)
                if dl:
                    story.pdf_storage_url = dl
            db.commit()
            logger.info(
                "[payment] story=%s storage upload OK backend=%s key=%s",
                story.id,
                storage.backend_name,
                storage_key,
            )
        except Exception as e:
            logger.warning(
                "[payment] story=%s storage upload failed: %s",
                story.id,
                e,
            )


@router.get("/config")
def get_payment_config():
    active = _razorpay_active()
    return {
        "razorpay_configured": _razorpay_configured(),
        "razorpay_enabled": active,
        "key_id": settings.RAZORPAY_KEY_ID if active else "",
        "is_live": settings.RAZORPAY_LIVE_MODE,
        "demo_bypass_available": not active,
        "currency": "INR",
    }


def _create_razorpay_order(
    amount_paise: int, receipt: str, notes: Dict[str, Any]
) -> Dict[str, Any]:
    if not _razorpay_configured():
        raise HTTPException(
            status_code=503, detail="Razorpay is not configured on the server"
        )
    payload = {
        "amount": amount_paise,
        "currency": "INR",
        "receipt": receipt,
        "notes": notes,
        "payment_capture": 1,
    }
    resp = requests.post(
        f"{RAZORPAY_API_BASE}/orders",
        auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET),
        json=payload,
        timeout=20,
    )
    if resp.status_code not in (200, 201):
        raise HTTPException(
            status_code=502,
            detail=f"Razorpay order creation failed: {resp.status_code} {resp.text[:200]}",
        )
    return resp.json()


@router.post("/create-order", response_model=PaymentOrderResponse)
def create_order(
    req: PaymentOrderRequest,
    current_user: Optional[User] = Depends(get_current_user_optional),
    db: Session = Depends(get_db),
):
    if req.tier_id not in TIER_CONFIG:
        raise HTTPException(status_code=400, detail="Unknown tier_id")
    tier = get_tier(req.tier_id)
    amount_inr = req.amount_inr if req.amount_inr is not None else tier["price_inr"]
    if amount_inr <= 0:
        raise HTTPException(status_code=400, detail="amount_inr must be > 0")

    amount_paise = amount_inr * 100
    receipt = f"comic_{req.tier_id}_{uuid.uuid4().hex[:10]}"
    notes = {
        "tier_id": req.tier_id,
        "style_id": req.style_id or "",
        "child_id": str(req.child_id) if req.child_id else "",
        "user_id": str(current_user.id) if current_user else "guest",
        "story_id": str(req.story_id) if req.story_id else "",
    }

    if _razorpay_active():
        try:
            order = _create_razorpay_order(amount_paise, receipt, notes)
            logger.info(
                "[payment.create_order] tier=%s story=%s amount_inr=%s order=%s",
                req.tier_id,
                req.story_id,
                amount_inr,
                order["id"],
            )
            return PaymentOrderResponse(
                order_id=order["id"],
                amount_inr=amount_inr,
                currency="INR",
                tier_id=req.tier_id,
                key_id=settings.RAZORPAY_KEY_ID,
                status=order.get("status", "created"),
            )
        except HTTPException:
            raise
        except Exception as e:
            logger.error("[payment.create_order] razorpay error: %s", e)
            raise HTTPException(status_code=502, detail=f"Razorpay error: {e}")

    raise HTTPException(
        status_code=403,
        detail="Razorpay is disabled on this deployment. Use /demo-bypass.",
    )


@router.post("/verify", response_model=PaymentVerifyResponse)
def verify_payment(
    req: PaymentVerifyRequest,
    x_session_token: Optional[str] = Header(default=None, alias="X-Session-Token"),
    current_user: Optional[User] = Depends(get_current_user_optional),
    db: Session = Depends(get_db),
):
    """Verify a Razorpay payment and unlock the linked story.

    Backwards compatibility: if ``req.story_id`` is not provided, this endpoint
    just verifies the signature and returns the same shape it always did.
    When ``req.story_id`` IS provided, it also:

      1. Looks up the story.
      2. Verifies the caller owns it (by JWT login OR X-Session-Token).
      3. Flips ``status`` to ``PURCHASED`` and stamps ``paid_at``.
      4. Creates (or updates) the local ``Order`` row.
      5. Triggers a storage upload so the PDF is ready to download.

    The frontend flow is:
      ``POST /api/payment/create-order`` → Razorpay checkout →
      ``POST /api/payment/verify`` (with ``story_id``) → library refresh.
    """
    if not _razorpay_configured():
        logger.warning(
            "[payment.verify] story=%s rejected: razorpay not configured",
            req.story_id,
        )
        return PaymentVerifyResponse(
            verified=False,
            message="Razorpay is not configured on the server. Use /demo-bypass for the hackathon.",
        )
    is_valid = verify_razorpay_signature(
        req.razorpay_order_id, req.razorpay_payment_id, req.razorpay_signature
    )
    if not is_valid:
        logger.warning(
            "[payment.verify] story=%s invalid signature order=%s",
            req.story_id,
            req.razorpay_order_id,
        )
        return PaymentVerifyResponse(verified=False, message="Invalid signature")

    if req.story_id is None:
        return PaymentVerifyResponse(verified=True, message="Payment verified")

    story = db.query(Story).filter(Story.id == req.story_id).first()
    if not story:
        return PaymentVerifyResponse(
            verified=True,
            story_id=req.story_id,
            message="Payment verified, but no matching story was found.",
        )

    session_token = (x_session_token or req.session_token or "").strip()
    if not _owns_story(story, current_user, session_token):
        raise HTTPException(
            status_code=403,
            detail="This story belongs to a different user or session.",
        )

    amount = float(story.amount or 0)
    _mark_story_purchased(
        db, story, req.razorpay_payment_id, req.razorpay_order_id, amount
    )
    logger.info(
        "[payment.verify] story=%s session=%s is_paid=true order=%s",
        story.id,
        (session_token or "")[:8] + "...",
        req.razorpay_order_id,
    )
    return PaymentVerifyResponse(
        verified=True,
        story_id=story.id,
        is_paid=True,
        message=f"Payment verified. Comic {story.id} is unlocked.",
    )


@router.post("/demo-bypass")
def demo_bypass(
    req: PaymentOrderRequest,
    x_session_token: Optional[str] = Header(default=None, alias="X-Session-Token"),
    current_user: Optional[User] = Depends(get_current_user_optional),
    db: Session = Depends(get_db),
):
    """Hackathon-only bypass. Returns 403 if Razorpay is enabled on the server.

    If ``req.story_id`` is provided, this endpoint also marks that story as
    PURCHASED in the same call, mirroring the full Razorpay flow so the
    offline / hackathon demo can still showcase the paywalled library.
    """
    if req.tier_id not in TIER_CONFIG:
        raise HTTPException(status_code=400, detail="Unknown tier_id")
    tier = get_tier(req.tier_id)
    if _razorpay_active():
        raise HTTPException(
            status_code=403,
            detail="Razorpay is enabled on this server. Demo bypass is disabled.",
        )

    amount_inr = req.amount_inr or tier["price_inr"]
    razorpay_payment_id = f"pay_demo_{secrets.token_hex(8)}"
    razorpay_order_id = f"order_demo_{secrets.token_hex(8)}"
    story_id_unlocked: Optional[int] = None

    if req.story_id is not None:
        story = db.query(Story).filter(Story.id == req.story_id).first()
        if not story:
            raise HTTPException(status_code=404, detail="Story not found")
        session_token = (x_session_token or "").strip()
        if not _owns_story(story, current_user, session_token):
            raise HTTPException(
                status_code=403,
                detail="This story belongs to a different user or session.",
            )
        _mark_story_purchased(
            db, story, razorpay_payment_id, razorpay_order_id, float(amount_inr)
        )
        story_id_unlocked = story.id
        logger.info(
            "[payment.demo_bypass] story=%s tier=%s amount_inr=%s is_paid=true",
            story.id,
            req.tier_id,
            amount_inr,
        )
    else:
        logger.info(
            "[payment.demo_bypass] tier=%s amount_inr=%s (no story_id)",
            req.tier_id,
            amount_inr,
        )

    return {
        "verified": True,
        "tier_id": req.tier_id,
        "amount_inr": amount_inr,
        "razorpay_payment_id": razorpay_payment_id,
        "razorpay_order_id": razorpay_order_id,
        "razorpay_signature": hashlib.sha256(b"demo").hexdigest(),
        "key_id": "",
        "message": "Local demo bypass (Razorpay disabled on server)",
        "story_id": story_id_unlocked,
        "is_paid": story_id_unlocked is not None,
    }
