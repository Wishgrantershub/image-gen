from pydantic import BaseModel
from typing import Optional, List


class BookBase(BaseModel):
    title: str
    description: Optional[str] = None
    theme: str
    age_min: int = 0
    age_max: int = 12
    page_count: int = 24
    cover_image: Optional[str] = None
    style_keywords: Optional[str] = None
    character_base: Optional[str] = None
    background_consistency: bool = True


class BookResponse(BookBase):
    id: int
    is_active: bool

    class Config:
        from_attributes = True


class BookList(BaseModel):
    books: List[BookResponse]
    total: int
