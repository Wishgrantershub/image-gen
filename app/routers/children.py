import os
import shutil
from typing import List
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User, Child
from app.schemas import ChildCreate, ChildUpdate, ChildResponse
from app.services.auth_service import get_current_active_user
from app.services.ai_service import face_prep_service
from app.config import UPLOAD_DIR

router = APIRouter(prefix="/api/children", tags=["Children"])


@router.post("/", response_model=ChildResponse, status_code=status.HTTP_201_CREATED)
def create_child(
    name: str = Form(...),
    gender: str | None = Form(None),
    age: int | None = Form(None),
    photo: UploadFile = File(...),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    photo_path = None
    if photo:
        filename = f"{current_user.id}_{photo.filename}"
        photo_path = os.path.join(UPLOAD_DIR, filename)
        with open(photo_path, "wb") as buffer:
            shutil.copyfileobj(photo.file, buffer)

    embedding = None
    if photo_path:
        try:
            face_prep_service.initialize()
            result = face_prep_service.prepare_face(photo_path)
            if result:
                embedding = result[0].tolist()
        except Exception as e:
            print(f"Warning: Could not extract face embedding: {e}")

    db_child = Child(
        user_id=current_user.id,
        name=name,
        gender=gender,
        age=age,
        photo_path=photo_path,
        face_embedding=embedding,
    )
    db.add(db_child)
    db.commit()
    db.refresh(db_child)
    return db_child


@router.get("/", response_model=List[ChildResponse])
def list_children(
    current_user: User = Depends(get_current_active_user), db: Session = Depends(get_db)
):
    children = db.query(Child).filter(Child.user_id == current_user.id).all()
    return children


@router.get("/{child_id}", response_model=ChildResponse)
def get_child(
    child_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    child = (
        db.query(Child)
        .filter(Child.id == child_id, Child.user_id == current_user.id)
        .first()
    )
    if not child:
        raise HTTPException(status_code=404, detail="Child not found")
    return child


@router.put("/{child_id}", response_model=ChildResponse)
def update_child(
    child_id: int,
    child_update: ChildUpdate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    child = (
        db.query(Child)
        .filter(Child.id == child_id, Child.user_id == current_user.id)
        .first()
    )
    if not child:
        raise HTTPException(status_code=404, detail="Child not found")

    for key, value in child_update.model_dump(exclude_unset=True).items():
        setattr(child, key, value)

    db.commit()
    db.refresh(child)
    return child


@router.delete("/{child_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_child(
    child_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    child = (
        db.query(Child)
        .filter(Child.id == child_id, Child.user_id == current_user.id)
        .first()
    )
    if not child:
        raise HTTPException(status_code=404, detail="Child not found")

    if child.photo_path and os.path.exists(child.photo_path):
        os.remove(child.photo_path)

    db.delete(child)
    db.commit()
    return None
