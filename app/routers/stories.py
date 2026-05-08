from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User, Story, Child, Book, StoryStatus
from app.schemas import StoryCreate, StoryUpdate, StoryResponse, StoryList
from app.services.auth_service import get_current_active_user
from app.services.story_service import story_generation_service

router = APIRouter(prefix="/api/stories", tags=["Stories"])

@router.post("/", response_model=StoryResponse, status_code=status.HTTP_201_CREATED)
def create_story(
    story_data: StoryCreate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    child = db.query(Child).filter(
        Child.id == story_data.child_id,
        Child.user_id == current_user.id
    ).first()
    if not child:
        raise HTTPException(status_code=404, detail="Child not found")

    book = db.query(Book).filter(Book.id == story_data.book_id).first()
    if not book:
        raise HTTPException(status_code=404, detail="Book not found")

    if not child.face_embedding:
        raise HTTPException(
            status_code=400,
            detail="Child photo not processed. Please re-upload the photo."
        )

    story = Story(
        user_id=current_user.id,
        child_id=story_data.child_id,
        book_id=story_data.book_id,
        title=f"{child.name}'s {book.title}",
        status=StoryStatus.GENERATING
    )
    db.add(story)
    db.commit()
    db.refresh(story)

    success = story_generation_service.generate_preview(
        db=db,
        story=story,
        child=child,
        book=book,
        num_pages=13
    )

    if not success:
        story.status = StoryStatus.DRAFT
        db.commit()
        raise HTTPException(status_code=500, detail="Failed to generate story preview")

    db.refresh(story)
    return story

@router.get("/", response_model=StoryList)
def list_stories(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    stories = db.query(Story).filter(Story.user_id == current_user.id).order_by(Story.created_at.desc()).all()
    return {"stories": stories, "total": len(stories)}

@router.get("/{story_id}", response_model=StoryResponse)
def get_story(
    story_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    story = db.query(Story).filter(
        Story.id == story_id,
        Story.user_id == current_user.id
    ).first()
    if not story:
        raise HTTPException(status_code=404, detail="Story not found")
    return story

@router.get("/{story_id}/preview")
def get_preview(
    story_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    story = db.query(Story).filter(
        Story.id == story_id,
        Story.user_id == current_user.id
    ).first()
    if not story:
        raise HTTPException(status_code=404, detail="Story not found")

    preview_pages = [p for p in story.pages if p.is_preview == 1]
    return {
        "story_id": story.id,
        "title": story.title,
        "status": story.status,
        "pages": [
            {
                "page_number": p.page_number,
                "text": p.text,
                "image_url": f"/api/images/{p.id}" if p.image_path else None
            }
            for p in preview_pages
        ]
    }

@router.put("/{story_id}", response_model=StoryResponse)
def update_story(
    story_id: int,
    story_update: StoryUpdate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    story = db.query(Story).filter(
        Story.id == story_id,
        Story.user_id == current_user.id
    ).first()
    if not story:
        raise HTTPException(status_code=404, detail="Story not found")

    if story_update.title:
        story.title = story_update.title

    db.commit()
    db.refresh(story)
    return story

@router.delete("/{story_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_story(
    story_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    story = db.query(Story).filter(
        Story.id == story_id,
        Story.user_id == current_user.id
    ).first()
    if not story:
        raise HTTPException(status_code=404, detail="Story not found")

    db.delete(story)
    db.commit()
    return None