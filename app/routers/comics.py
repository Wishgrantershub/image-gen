import os
import shutil
import time
import uuid
from datetime import datetime
from typing import List, Optional

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    Form,
    Header,
    HTTPException,
    UploadFile,
    status,
)
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

import logging

from app.config import COMIC_OUTPUT_DIR, COMIC_PANEL_DIR, COMIC_SHEET_DIR, UPLOAD_DIR
from app.database import get_db
from app.models import Book, Child, Story, StoryPage, StoryStatus, User
from app.schemas.comic import (
    ComicCreateRequest,
    ComicPanelOut,
    ComicResponse,
    ComicStatusResponse,
    ComicStylesTiersResponse,
    ComicStyleOut,
    ComicTierOut,
    SampleComicRequest,
)
from app.services.auth_service import (
    get_current_active_user,
    get_current_user_optional,
    get_session_token,
)


_optional_current_user_dep = get_current_user_optional
from app.services.comic_service import (
    comic_generation_service,
    make_share_token,
)
from app.services.comic_styles import (
    COMIC_STYLES,
    TIER_CONFIG,
    list_styles,
    list_tiers,
)
from app.services.ai_service import image_generation_service
from app.config import settings

router = APIRouter(prefix="/api/comics", tags=["Comics"])


logger = logging.getLogger("comicme.comics")


def _serialize_comic(story: Story) -> ComicResponse:
    panels: List[ComicPanelOut] = []
    for p in sorted(story.pages, key=lambda x: x.page_number):
        caption = ""
        speech = ""
        bubble_kind = "speech"
        if p.text:
            for line in p.text.split("\n"):
                if line.startswith("[CAPTION] "):
                    caption = line[len("[CAPTION] ") :]
                elif line.startswith("[SPEECH] "):
                    speech = line[len("[SPEECH] ") :]
        panels.append(
            ComicPanelOut(
                page_number=p.page_number,
                caption=caption,
                speech=speech,
                bubble_kind=bubble_kind,
                image_url=f"/api/comics/{story.id}/panels/{p.id}",
                image_path=p.image_path,
            )
        )
    status_str = (
        story.status.value if hasattr(story.status, "value") else str(story.status)
    )
    is_paid = status_str == StoryStatus.PURCHASED.value
    return ComicResponse(
        id=story.id,
        share_token=story.share_token or "",
        title=story.title or "Your Comic",
        style_id=(story.book.comic_style_id if story.book else "") or "",
        tier_id=story.tier or "premium",
        panel_count=story.panel_count or len(panels),
        panel_layout=story.panel_layout or "2x3",
        status=status_str,
        progress_step=story.progress_step,
        progress_message=story.progress_message,
        progress_pct=story.progress_pct or 0,
        error_message=story.error_message,
        cover_url=f"/api/comics/{story.id}/cover" if story.cover_path else None,
        pdf_url=f"/api/comics/{story.id}/pdf" if story.pdf_path else None,
        share_url=f"/c/{story.share_token}" if story.share_token else f"/c/{story.id}",
        panels=panels,
        is_paid=is_paid,
        payment_required=settings.RAZORPAY_ENABLED and not is_paid,
        amount_inr=float(story.amount) if story.amount else None,
    )


@router.get("/styles", response_model=ComicStylesTiersResponse)
def get_styles_and_tiers():
    return ComicStylesTiersResponse(styles=list_styles(), tiers=list_tiers())


@router.get("/samples")
def list_samples():
    samples = []
    if os.path.isdir(COMIC_OUTPUT_DIR):
        for fn in sorted(os.listdir(COMIC_OUTPUT_DIR)):
            if fn.startswith("sample_") and fn.endswith(".pdf"):
                sample_id = fn[len("sample_") : -len(".pdf")]
                pdf_url = f"/api/comics/samples/{sample_id}/pdf"
                cover_url = f"/api/comics/samples/{sample_id}/cover"
                samples.append(
                    {
                        "id": sample_id,
                        "pdf_url": pdf_url,
                        "cover_url": cover_url,
                    }
                )
    return {"samples": samples}


@router.get("/samples/{sample_id}/pdf")
def get_sample_pdf(sample_id: str):
    path = os.path.join(COMIC_OUTPUT_DIR, f"sample_{sample_id}.pdf")
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="Sample not found")
    return FileResponse(
        path, media_type="application/pdf", filename=f"comicme_sample_{sample_id}.pdf"
    )


@router.get("/samples/{sample_id}/cover")
def get_sample_cover(sample_id: str):
    path = os.path.join(COMIC_PANEL_DIR, f"sample_{sample_id}_cover.png")
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="Sample cover not found")
    return FileResponse(path, media_type="image/png")


@router.get("/samples/{sample_id}/panel/{n}")
def get_sample_panel(sample_id: str, n: int):
    path = os.path.join(COMIC_PANEL_DIR, f"sample_{sample_id}_panel_{n}.png")
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="Sample panel not found")
    return FileResponse(path, media_type="image/png")


@router.post("/samples/generate")
def generate_sample(req: SampleComicRequest, background: BackgroundTasks):
    photo_path = os.path.join(UPLOAD_DIR, req.photo) if req.photo else None
    if not photo_path or not os.path.exists(photo_path):
        raise HTTPException(
            status_code=400, detail="Sample photo not found in uploads/"
        )

    if req.style_id not in COMIC_STYLES:
        raise HTTPException(status_code=400, detail="Unknown style_id")
    if req.tier_id not in TIER_CONFIG:
        raise HTTPException(status_code=400, detail="Unknown tier_id")

    sample_id = f"{req.style_id}_{req.tier_id}_{abs(hash(req.name + req.premise or 'sample')) % 100000}"

    background.add_task(
        _run_sample_generation,
        sample_id,
        photo_path,
        req.name,
        req.premise or "",
        req.style_id,
        req.tier_id,
    )
    return {
        "sample_id": sample_id,
        "status": "queued",
        "poll_url": f"/api/comics/samples/{sample_id}/status",
    }


def _run_sample_generation(
    sample_id: str,
    photo_path: str,
    name: str,
    premise: str,
    style_id: str,
    tier_id: str,
) -> None:
    from app.database import SessionLocal

    db = SessionLocal()
    try:
        comic_generation_service.build_sample_comic(
            db=db,
            sample_id=sample_id,
            child_photo_path=photo_path,
            child_name=name,
            premise=premise,
            style_id=style_id,
            tier_id=tier_id,
        )
    finally:
        db.close()


@router.get("/samples/{sample_id}/status")
def get_sample_status(sample_id: str):
    pdf_path = os.path.join(COMIC_OUTPUT_DIR, f"sample_{sample_id}.pdf")
    if os.path.exists(pdf_path):
        return {
            "sample_id": sample_id,
            "status": "ready",
            "pdf_url": f"/api/comics/samples/{sample_id}/pdf",
            "cover_url": f"/api/comics/samples/{sample_id}/cover",
        }
    return {"sample_id": sample_id, "status": "generating"}


@router.post(
    "/create-anonymous",
    response_model=ComicResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_comic_anonymous(
    background: BackgroundTasks,
    photo: UploadFile = File(...),
    name: str = Form("Hero"),
    style_id: str = Form(...),
    tier_id: str = Form(...),
    premise: str = Form(...),
    title: Optional[str] = Form(None),
    payment_verified: bool = Form(False),
    razorpay_payment_id: Optional[str] = Form(None),
    razorpay_order_id: Optional[str] = Form(None),
    razorpay_signature: Optional[str] = Form(None),
    x_session_token: Optional[str] = Header(default=None, alias="X-Session-Token"),
    db: Session = Depends(get_db),
):
    """Single-call anonymous comic creation. Used by the landing page flow (no auth required).

    Accepts an optional ``X-Session-Token`` header; if present, the resulting
    story is tagged with that token so it appears in the session's "My Comics"
    library. If absent, the story is still created and visible via its
    ``share_token`` for the demo flow, but won't show up in the library.
    """
    if style_id not in COMIC_STYLES:
        raise HTTPException(status_code=400, detail=f"Unknown style_id: {style_id}")
    if tier_id not in TIER_CONFIG:
        raise HTTPException(status_code=400, detail=f"Unknown tier_id: {tier_id}")
    if not premise or len(premise.strip()) < 3:
        raise HTTPException(
            status_code=400, detail="Premise must be at least 3 characters"
        )

    if settings.RAZORPAY_ENABLED:
        from app.routers.payment import verify_razorpay_signature

        if not (razorpay_payment_id and razorpay_order_id and razorpay_signature):
            raise HTTPException(
                status_code=400,
                detail="Razorpay is enabled: payment_id, order_id and signature are required.",
            )
        if not verify_razorpay_signature(
            razorpay_order_id, razorpay_payment_id, razorpay_signature
        ):
            raise HTTPException(
                status_code=400, detail="Invalid Razorpay payment signature."
            )
        paid_at = datetime.utcnow()
    else:
        paid_at = datetime.utcnow()

    book = (
        db.query(Book)
        .filter(Book.comic_style_id == style_id, Book.is_comic == True)  # noqa: E712
        .first()
    )
    if not book:
        seed_styles_endpoint(db=db)
        db.refresh(db)
        book = (
            db.query(Book)
            .filter(Book.comic_style_id == style_id, Book.is_comic == True)  # noqa: E712
            .first()
        )
    if not book:
        raise HTTPException(
            status_code=500,
            detail="Comic style not seeded. Run /api/comics/seed-styles first.",
        )

    demo_email = f"guest+{uuid.uuid4().hex[:10]}@comicme.local"
    guest = db.query(User).filter(User.email == demo_email).first()
    if not guest:
        from app.services.auth_service import get_password_hash

        guest = User(
            email=demo_email,
            username=demo_email,
            full_name=name or "Guest",
            hashed_password=get_password_hash(uuid.uuid4().hex),
        )
        db.add(guest)
        db.commit()
        db.refresh(guest)

    safe_name = (name or "hero").strip().replace(" ", "_")
    safe_name = (
        "".join(c for c in safe_name if c.isalnum() or c in ("_", "-"))[:32] or "hero"
    )
    photo_ext = os.path.splitext(photo.filename or "upload.jpg")[1] or ".jpg"
    if photo_ext.lower() not in {".jpg", ".jpeg", ".png", ".webp"}:
        photo_ext = ".jpg"
    photo_filename = f"{guest.id}_{int(time.time())}_{safe_name}{photo_ext}"
    photo_path = os.path.join(UPLOAD_DIR, photo_filename)

    try:
        with open(photo_path, "wb") as out:
            shutil.copyfileobj(photo.file, out)
    finally:
        await photo.close()

    child = Child(
        user_id=guest.id,
        name=name or "Hero",
        gender=None,
        age=None,
        photo_path=photo_path,
    )
    db.add(child)
    db.commit()
    db.refresh(child)

    session_token = (x_session_token or "").strip() or None
    story = Story(
        user_id=guest.id,
        child_id=child.id,
        book_id=book.id,
        is_comic=1,
        premise=premise.strip(),
        tier=tier_id,
        title=(
            title.strip()
            if title
            else f"{name or 'Hero'}'s {COMIC_STYLES[style_id]['name']} Adventure"
        ),
        status=StoryStatus.GENERATING,
        share_token=make_share_token(),
        session_token=session_token,
        progress_pct=0,
        progress_step="queued",
        progress_message="Queued for generation",
        amount=float(TIER_CONFIG[tier_id]["price_inr"]),
        currency="INR",
        paid_at=paid_at,
    )
    db.add(story)
    db.commit()
    db.refresh(story)

    if settings.RAZORPAY_ENABLED and (
        razorpay_payment_id and razorpay_order_id and razorpay_signature
    ):
        from app.routers.payment import _mark_story_purchased

        _mark_story_purchased(
            db,
            story,
            razorpay_payment_id,
            razorpay_order_id,
            float(TIER_CONFIG[tier_id]["price_inr"]),
        )

    background.add_task(_run_comic_generation, story.id, guest.id, style_id, tier_id)

    logger.info(
        "[comics.create] story=%s tier=%s session=%s payment_verified=%s share_token=%s",
        story.id,
        tier_id,
        (session_token or "")[:8] + "...",
        bool(razorpay_payment_id and razorpay_order_id and razorpay_signature),
        story.share_token,
    )

    return _serialize_comic(story)


@router.post(
    "/create", response_model=ComicResponse, status_code=status.HTTP_201_CREATED
)
def create_comic(
    req: ComicCreateRequest,
    background: BackgroundTasks,
    x_session_token: Optional[str] = Header(default=None, alias="X-Session-Token"),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    if req.style_id not in COMIC_STYLES:
        raise HTTPException(status_code=400, detail=f"Unknown style_id: {req.style_id}")
    if req.tier_id not in TIER_CONFIG:
        raise HTTPException(status_code=400, detail=f"Unknown tier_id: {req.tier_id}")

    child = (
        db.query(Child)
        .filter(Child.id == req.child_id, Child.user_id == current_user.id)
        .first()
    )
    if not child:
        raise HTTPException(status_code=404, detail="Child not found")
    if not child.photo_path or not os.path.exists(child.photo_path):
        raise HTTPException(status_code=400, detail="Child has no uploaded photo")

    book = (
        db.query(Book)
        .filter(Book.comic_style_id == req.style_id, Book.is_comic == True)  # noqa: E712
        .first()
    )
    if not book:
        raise HTTPException(
            status_code=500,
            detail="Comic style not seeded. Run /api/comics/seed-styles first.",
        )

    if not req.premise or len(req.premise.strip()) < 3:
        raise HTTPException(
            status_code=400, detail="Premise must be at least 3 characters"
        )

    session_token = (x_session_token or "").strip() or None
    story = Story(
        user_id=current_user.id,
        child_id=child.id,
        book_id=book.id,
        is_comic=1,
        premise=req.premise.strip(),
        tier=req.tier_id,
        title=req.title.strip()
        if req.title
        else f"{child.name}'s {COMIC_STYLES[req.style_id]['name']} Adventure",
        status=StoryStatus.GENERATING,
        share_token=make_share_token(),
        session_token=session_token,
        progress_pct=0,
        progress_step="queued",
        progress_message="Queued for generation",
        amount=float(TIER_CONFIG[req.tier_id]["price_inr"]),
        currency="INR",
    )
    db.add(story)
    db.commit()
    db.refresh(story)

    background.add_task(
        _run_comic_generation,
        story.id,
        current_user.id,
        req.style_id,
        req.tier_id,
    )

    logger.info(
        "[comics.create] story=%s user=%s tier=%s session=%s",
        story.id,
        current_user.id,
        req.tier_id,
        (session_token or "")[:8] + "...",
    )

    return _serialize_comic(story)


def _run_comic_generation(
    story_id: int, user_id: int, style_id: str, tier_id: str
) -> None:
    from app.database import SessionLocal

    logger.info(
        "[comics.bg] story=%s user=%s style=%s tier=%s background task started",
        story_id,
        user_id,
        style_id,
        tier_id,
    )
    db = SessionLocal()
    try:
        story = db.query(Story).filter(Story.id == story_id).first()
        if not story:
            logger.warning("[comics.bg] story=%s not found, aborting", story_id)
            return
        child = db.query(Child).filter(Child.id == story.child_id).first()
        book = db.query(Book).filter(Book.id == story.book_id).first()
        if not child or not book:
            logger.warning(
                "[comics.bg] story=%s missing child/book, aborting",
                story_id,
            )
            return
        comic_generation_service.generate_comic(
            db=db,
            story=story,
            child=child,
            book=book,
            style_id=style_id,
            tier_id=tier_id,
        )
    finally:
        db.close()


@router.get("/mine", response_model=List[ComicResponse])
def list_my_comics(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    rows = (
        db.query(Story)
        .filter(Story.user_id == current_user.id, Story.is_comic == 1)
        .order_by(Story.created_at.desc())
        .all()
    )
    return [_serialize_comic(s) for s in rows]


def _ready_panel_numbers(story_id: int, db: Session) -> list:
    pages = db.query(StoryPage).filter(StoryPage.story_id == story_id).all()
    return sorted(
        p.page_number for p in pages if p.image_path and os.path.exists(p.image_path)
    )


def get_comic(
    comic_id: int,
    x_session_token: Optional[str] = Header(default=None, alias="X-Session-Token"),
    current_user: Optional[User] = Depends(_optional_current_user_dep),
    db: Session = Depends(get_db),
):
    story = db.query(Story).filter(Story.id == comic_id, Story.is_comic == 1).first()
    if not story:
        raise HTTPException(status_code=404, detail="Comic not found")
    session = (x_session_token or "").strip()
    owns_by_user = current_user is not None and story.user_id == current_user.id
    owns_by_session = bool(session) and story.session_token == session
    if not (owns_by_user or owns_by_session):
        raise HTTPException(
            status_code=403,
            detail="This comic was created by a different user or session.",
        )
    return _serialize_comic(story)


@router.get("/{comic_id}/status", response_model=ComicStatusResponse)
def get_comic_status(
    comic_id: int,
    x_session_token: Optional[str] = Header(default=None, alias="X-Session-Token"),
    current_user: Optional[User] = Depends(_optional_current_user_dep),
    db: Session = Depends(get_db),
):
    story = db.query(Story).filter(Story.id == comic_id, Story.is_comic == 1).first()
    if not story:
        raise HTTPException(status_code=404, detail="Comic not found")
    session = (x_session_token or "").strip()
    owns_by_user = current_user is not None and story.user_id == current_user.id
    owns_by_session = bool(session) and story.session_token == session
    if not (owns_by_user or owns_by_session):
        raise HTTPException(
            status_code=403,
            detail="This comic was created by a different user or session.",
        )
    ready = _ready_panel_numbers(story.id, db)
    logger.debug(
        "[comics.status] story=%s pct=%s step=%s panels_ready=%d/%d",
        story.id,
        story.progress_pct,
        story.progress_step,
        len(ready),
        story.panel_count or 0,
    )
    return ComicStatusResponse(
        id=story.id,
        status=story.status.value
        if hasattr(story.status, "value")
        else str(story.status),
        progress_step=story.progress_step,
        progress_message=story.progress_message,
        progress_pct=story.progress_pct or 0,
        error_message=story.error_message,
        pdf_url=f"/api/comics/{story.id}/pdf" if story.pdf_path else None,
        cover_url=f"/api/comics/{story.id}/cover" if story.cover_path else None,
        panel_count=story.panel_count or 0,
        completed_panels=len(ready),
        ready_panel_numbers=ready,
    )


@router.get("/{comic_id}/pdf")
def get_comic_pdf(
    comic_id: int,
    x_session_token: Optional[str] = Header(default=None, alias="X-Session-Token"),
    current_user: Optional[User] = Depends(_optional_current_user_dep),
    db: Session = Depends(get_db),
):
    """Stream the comic PDF, gated by session OR auth and by payment.

    Authorization:
      - Logged-in user who owns the story → allowed.
      - Session token matching ``Story.session_token`` → allowed.
      - Otherwise 403.

    Payment:
      - If ``RAZORPAY_ENABLED`` is False → always free, all PDFs downloadable.
      - If ``RAZORPAY_ENABLED`` is True → only stories with
        ``status == PURCHASED`` are downloadable; others get 402 with a
        ``payment_required`` flag and a price hint.
    """
    story = db.query(Story).filter(Story.id == comic_id, Story.is_comic == 1).first()
    if not story:
        raise HTTPException(status_code=404, detail="Comic not found")
    if not story.pdf_path or not os.path.exists(story.pdf_path):
        raise HTTPException(status_code=404, detail="PDF not ready")

    session_token = (x_session_token or "").strip()
    owns_by_user = current_user is not None and story.user_id == current_user.id
    owns_by_session = bool(session_token) and story.session_token == session_token
    if not (owns_by_user or owns_by_session):
        raise HTTPException(
            status_code=403,
            detail=(
                "This comic was created by a different user or session. "
                "Sign in or use the same browser session that created it."
            ),
        )

    if settings.RAZORPAY_ENABLED and story.status != StoryStatus.PURCHASED:
        raise HTTPException(
            status_code=402,
            detail={
                "code": "payment_required",
                "message": (
                    "This comic is in your library but not yet paid for. "
                    "Pay to download the PDF."
                ),
                "tier_id": story.tier,
                "amount_inr": float(story.amount or 0),
            },
        )

    return FileResponse(
        story.pdf_path,
        media_type="application/pdf",
        filename=f"comicme_{story.id}.pdf",
    )


@router.get("/{comic_id}/cover")
def get_comic_cover(
    comic_id: int,
    x_session_token: Optional[str] = Header(default=None, alias="X-Session-Token"),
    current_user: Optional[User] = Depends(_optional_current_user_dep),
    db: Session = Depends(get_db),
):
    story = db.query(Story).filter(Story.id == comic_id, Story.is_comic == 1).first()
    if not story or not story.cover_path or not os.path.exists(story.cover_path):
        raise HTTPException(status_code=404, detail="Cover not ready")
    session = (x_session_token or "").strip()
    owns_by_user = current_user is not None and story.user_id == current_user.id
    owns_by_session = bool(session) and story.session_token == session
    if not (owns_by_user or owns_by_session):
        raise HTTPException(
            status_code=403,
            detail="This comic was created by a different user or session.",
        )
    return FileResponse(story.cover_path, media_type="image/png")


@router.get("/{comic_id}/panels/{page_id}")
def get_comic_panel(
    comic_id: int,
    page_id: int,
    x_session_token: Optional[str] = Header(default=None, alias="X-Session-Token"),
    current_user: Optional[User] = Depends(_optional_current_user_dep),
    db: Session = Depends(get_db),
):
    from app.models import StoryPage

    story = db.query(Story).filter(Story.id == comic_id, Story.is_comic == 1).first()
    if not story:
        raise HTTPException(status_code=404, detail="Comic not found")
    session = (x_session_token or "").strip()
    owns_by_user = current_user is not None and story.user_id == current_user.id
    owns_by_session = bool(session) and story.session_token == session
    if not (owns_by_user or owns_by_session):
        raise HTTPException(
            status_code=403,
            detail="This comic was created by a different user or session.",
        )
    page = (
        db.query(StoryPage)
        .filter(StoryPage.id == page_id, StoryPage.story_id == comic_id)
        .first()
    )
    if not page or not page.image_path or not os.path.exists(page.image_path):
        raise HTTPException(status_code=404, detail="Panel not found")
    return FileResponse(page.image_path, media_type="image/png")


@router.post("/seed-styles")
def seed_styles_endpoint(db: Session = Depends(get_db)):
    from app.routers.books import seed_books

    seed_books(db)
    return {"status": "ok", "styles_seeded": list(COMIC_STYLES.keys())}


@router.get("/by-token/{share_token}/status", response_model=ComicStatusResponse)
def get_comic_status_by_token(share_token: str, db: Session = Depends(get_db)):
    story = (
        db.query(Story)
        .filter(Story.share_token == share_token, Story.is_comic == 1)
        .first()
    )
    if not story:
        raise HTTPException(status_code=404, detail="Comic not found")
    ready = _ready_panel_numbers(story.id, db)
    logger.debug(
        "[comics.status_by_token] story=%s pct=%s step=%s panels_ready=%d/%d",
        story.id,
        story.progress_pct,
        story.progress_step,
        len(ready),
        story.panel_count or 0,
    )
    return ComicStatusResponse(
        id=story.id,
        status=story.status.value
        if hasattr(story.status, "value")
        else str(story.status),
        progress_step=story.progress_step,
        progress_message=story.progress_message,
        progress_pct=story.progress_pct or 0,
        error_message=story.error_message,
        pdf_url=f"/api/comics/by-token/{share_token}/pdf" if story.pdf_path else None,
        cover_url=f"/api/comics/by-token/{share_token}/cover"
        if story.cover_path
        else None,
        panel_count=story.panel_count or 0,
        completed_panels=len(ready),
        ready_panel_numbers=ready,
    )


@router.get("/by-token/{share_token}", response_model=ComicResponse)
def get_comic_by_token(share_token: str, db: Session = Depends(get_db)):
    story = (
        db.query(Story)
        .filter(Story.share_token == share_token, Story.is_comic == 1)
        .first()
    )
    if not story:
        raise HTTPException(status_code=404, detail="Comic not found")
    return _serialize_comic(story)


@router.get("/by-token/{share_token}/pdf")
def get_comic_pdf_by_token(share_token: str, db: Session = Depends(get_db)):
    story = (
        db.query(Story)
        .filter(Story.share_token == share_token, Story.is_comic == 1)
        .first()
    )
    if not story or not story.pdf_path or not os.path.exists(story.pdf_path):
        raise HTTPException(status_code=404, detail="PDF not ready")
    return FileResponse(
        story.pdf_path,
        media_type="application/pdf",
        filename=f"comicme_{share_token}.pdf",
    )


@router.get("/by-token/{share_token}/cover")
def get_comic_cover_by_token(share_token: str, db: Session = Depends(get_db)):
    story = (
        db.query(Story)
        .filter(Story.share_token == share_token, Story.is_comic == 1)
        .first()
    )
    if not story or not story.cover_path or not os.path.exists(story.cover_path):
        raise HTTPException(status_code=404, detail="Cover not ready")
    return FileResponse(story.cover_path, media_type="image/png")


@router.get("/by-token/{share_token}/panels/{page_number}")
def get_comic_panel_by_token(
    share_token: str, page_number: int, db: Session = Depends(get_db)
):
    from app.models import StoryPage

    page = (
        db.query(StoryPage)
        .join(Story, StoryPage.story_id == Story.id)
        .filter(
            Story.share_token == share_token,
            Story.is_comic == 1,
            StoryPage.page_number == page_number,
        )
        .first()
    )
    if not page or not page.image_path or not os.path.exists(page.image_path):
        raise HTTPException(status_code=404, detail="Panel not found")
    return FileResponse(page.image_path, media_type="image/png")
