from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime

class StoryBase(BaseModel):
    child_id: int
    book_id: int

class StoryCreate(StoryBase):
    pass

class StoryUpdate(BaseModel):
    title: Optional[str] = None

class StoryPageResponse(BaseModel):
    id: int
    page_number: int
    text: Optional[str] = None
    image_path: Optional[str] = None
    is_preview: int

    class Config:
        from_attributes = True

class StoryResponse(StoryBase):
    id: int
    user_id: int
    title: Optional[str] = None
    status: str
    preview_generated: int
    created_at: datetime
    pages: List[StoryPageResponse] = []

    class Config:
        from_attributes = True

class StoryList(BaseModel):
    stories: List[StoryResponse]
    total: int