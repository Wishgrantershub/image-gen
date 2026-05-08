import os
from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import StoryPage

router = APIRouter(prefix="/api/images", tags=["Images"])

@router.get("/{page_id}")
def get_image(page_id: int, db: Session = Depends(get_db)):
    page = db.query(StoryPage).filter(StoryPage.id == page_id).first()
    if not page or not page.image_path:
        raise HTTPException(status_code=404, detail="Image not found")

    if not os.path.exists(page.image_path):
        raise HTTPException(status_code=404, detail="Image file not found")

    return FileResponse(page.image_path)