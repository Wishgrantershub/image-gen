from pydantic import BaseModel
from typing import Optional
from datetime import datetime

class ChildBase(BaseModel):
    name: str
    gender: Optional[str] = None
    age: Optional[int] = None

class ChildCreate(ChildBase):
    pass

class ChildUpdate(ChildBase):
    name: Optional[str] = None
    gender: Optional[str] = None
    age: Optional[int] = None

class ChildResponse(ChildBase):
    id: int
    user_id: int
    photo_path: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True