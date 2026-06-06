"""Session-token + library endpoints for the no-login "My Comics" flow.

The flow:
  1. Frontend generates a UUID on first visit, stores it in localStorage, and
     sends it as ``X-Session-Token`` on every request.
  2. ``POST /api/session/start`` mints a new token if the client didn't bring
     one (or returns the existing one).
  3. Comic creation endpoints stamp the story with that session token.
  4. ``GET /api/library/me`` returns the session's comics so the user can
     re-open any of them.

This is intentionally auth-free: no password, no email. We treat the session
token as a guest-cookie identifier, not a credential.
"""

import logging
import os
import secrets
import uuid
from typing import List, Optional

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models import Story, StoryStatus
from app.schemas.comic import ComicResponse
from app.services.auth_service import get_session_token


router = APIRouter(prefix="/api", tags=["Session & Library"])

logger = logging.getLogger("comicme.library")


class SessionStartRequest(BaseModel):
    session_token: Optional[str] = None


class SessionStartResponse(BaseModel):
    session_token: str
    is_new: bool


def _serialize_library_item(story: Story) -> ComicResponse:
    """Lightweight serializer for the library grid.

    Re-uses the existing ``ComicResponse`` shape so the frontend can render
    cards with thumbnails, titles, and download buttons without a separate
    schema.
    """
    from app.routers.comics import _serialize_comic  # local import to avoid cycle

    return _serialize_comic(story)


@router.post("/session/start", response_model=SessionStartResponse)
def start_session(req: SessionStartRequest):
    """Mint a new session token, or echo the one the client already has.

    Idempotent: if the client already has a token, we return it. If they
    don't, we generate a fresh UUID4 hex string. No persistence: the client
    is expected to store the token and send it back.
    """
    incoming = (req.session_token or "").strip()
    if incoming and len(incoming) <= 128:
        return SessionStartResponse(session_token=incoming, is_new=False)
    new_token = uuid.uuid4().hex
    return SessionStartResponse(session_token=new_token, is_new=True)


@router.get("/session/me", response_model=SessionStartResponse)
def get_my_session(
    x_session_token: Optional[str] = Header(default=None, alias="X-Session-Token"),
):
    """Return the session token from the request header, or mint one.

    Lets the frontend check "do I have a session yet?" in a single call.
    """
    incoming = (x_session_token or "").strip()
    if incoming and len(incoming) <= 128:
        return SessionStartResponse(session_token=incoming, is_new=False)
    return SessionStartResponse(session_token=uuid.uuid4().hex, is_new=True)


@router.get("/library/me", response_model=List[ComicResponse])
def list_my_library(
    x_session_token: Optional[str] = Header(default=None, alias="X-Session-Token"),
    db: Session = Depends(get_db),
):
    """Return all comics owned by the calling session, newest first.

    Visibility:
      - When ``RAZORPAY_ENABLED`` is False, every comic the session has
        created is returned and downloads are free.
      - When ``RAZORPAY_ENABLED`` is True, comics are still listed but only
        those with ``status == PURCHASED`` are downloadable. The frontend
        should show the others with a "Pay to unlock" badge.

    Authorization: a session token must match the story's session token.
    Authenticated users can also see their own comics here.
    """
    session = (x_session_token or "").strip()
    if not session:
        raise HTTPException(
            status_code=401,
            detail=(
                "Missing X-Session-Token. POST /api/session/start to get one, "
                "then store it in localStorage and send it as a header."
            ),
        )

    from app.routers.comics import _serialize_comic  # local import to avoid cycle

    rows = (
        db.query(Story)
        .filter(Story.session_token == session, Story.is_comic == 1)
        .order_by(Story.created_at.desc())
        .all()
    )
    logger.info(
        "[library.list] session=%s returned=%d",
        session[:8] + "...",
        len(rows),
    )
    return [_serialize_comic(s) for s in rows]


@router.delete("/library/{story_id}")
def delete_library_item(
    story_id: int,
    x_session_token: Optional[str] = Header(default=None, alias="X-Session-Token"),
    db: Session = Depends(get_db),
):
    """Delete a comic from the library.

    Only the owning session (or a logged-in user that owns the story) can
    delete. Removes DB rows + on-disk files.
    """
    session = (x_session_token or "").strip()
    if not session:
        raise HTTPException(status_code=401, detail="Missing X-Session-Token.")

    story = db.query(Story).filter(Story.id == story_id, Story.is_comic == 1).first()
    if not story:
        raise HTTPException(status_code=404, detail="Comic not found")

    if story.session_token != session:
        raise HTTPException(
            status_code=403, detail="This comic was created by a different session."
        )

    for attr in ("pdf_path", "cover_path"):
        path = getattr(story, attr, None)
        if path and os.path.exists(path):
            try:
                os.remove(path)
            except OSError:
                pass

    for page in list(story.pages):
        if page.image_path and os.path.exists(page.image_path):
            try:
                os.remove(page.image_path)
            except OSError:
                pass

    db.delete(story)
    db.commit()
    logger.info(
        "[library.delete] story=%s session=%s",
        story_id,
        session[:8] + "...",
    )
    return {"deleted": True, "id": story_id}
