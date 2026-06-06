import json
from typing import List, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Book
from app.schemas import BookResponse, BookList
from app.services.comic_styles import COMIC_STYLES

router = APIRouter(prefix="/api/books", tags=["Books"])

DEFAULT_STORYBOOKS = [
    {
        "title": "The Magic Adventure",
        "description": "An exciting journey through magical lands where your child becomes the hero",
        "theme": "imagination",
        "age_min": 3,
        "age_max": 8,
        "page_count": 13,
        "style_keywords": "colorful cartoon illustration, magical fantasy, soft pastel colors, whimsical, children's book style",
        "character_base": "brave young hero in magical adventure clothes, glowing eyes, smiling face",
        "background_consistency": True,
    },
    {
        "title": "Space Explorer",
        "description": "Blast off on an intergalactic adventure to save the galaxy",
        "theme": "adventure",
        "age_min": 5,
        "age_max": 10,
        "page_count": 13,
        "style_keywords": "futuristic cartoon, space theme, bright cosmic colors, stars and planets, children's book illustration",
        "character_base": "young astronaut in space suit, helmet with visible face, adventurous pose",
        "background_consistency": True,
    },
    {
        "title": "The Friendly Dragon",
        "description": "Make a magical friend in this heartwarming tale of friendship",
        "theme": "friendship",
        "age_min": 3,
        "age_max": 7,
        "page_count": 13,
        "style_keywords": "soft pastel cartoon, warm and cozy, gentle colors, cute and friendly, children's picture book style",
        "character_base": "child as dragon friend, cute dragon features, friendly expression, colorful scales",
        "background_consistency": True,
    },
    {
        "title": "Superhero Academy",
        "description": "Train to become the hero the world needs",
        "theme": "heroism",
        "age_min": 6,
        "age_max": 12,
        "page_count": 13,
        "style_keywords": "dynamic cartoon superhero style, bold colors, comic book inspired, action poses, children's comic illustration",
        "character_base": "young superhero in colorful costume, cape, mask, confident pose",
        "background_consistency": True,
    },
    {
        "title": "The Brave Scientist",
        "description": "Discover the wonders of science and solve mysteries",
        "theme": "learning",
        "age_min": 5,
        "age_max": 10,
        "page_count": 13,
        "style_keywords": "educational cartoon, bright and cheerful, lab setting, curious and fun, children's educational illustration",
        "character_base": "young scientist in lab coat, safety goggles, curious expression, holding science tools",
        "background_consistency": True,
    },
    {
        "title": "Ocean Explorer",
        "description": "Dive deep into the magical underwater world",
        "theme": "adventure",
        "age_min": 4,
        "age_max": 9,
        "page_count": 13,
        "style_keywords": "underwater cartoon, ocean blues and greens, colorful sea creatures, magical underwater, children's storybook illustration",
        "character_base": "young diver with snorkel gear, smiling, exploring coral reef",
        "background_consistency": True,
    },
]


def _comic_style_to_book_entry(style_id: str, style: dict) -> dict:
    return {
        "title": f"{style['name']} Comic",
        "description": style["description"],
        "theme": f"comic:{style_id}",
        "age_min": 5,
        "age_max": 99,
        "page_count": style["default_panel_count"],
        "style_keywords": style["tagline"],
        "character_base": f"comic hero in {style['name']} style",
        "background_consistency": True,
        "is_comic": True,
        "comic_style_id": style_id,
        "style_suffix": style["style_suffix"],
        "bubble_style": style["bubble_style"],
        "border_color": style["border_color"],
        "border_width": style["border_width"],
        "default_panel_count": style["default_panel_count"],
        "palette": style["palette"],
        "sample_premises": style["sample_premises"],
    }


def seed_books(db: Session):
    existing = db.query(Book).first()
    if existing:
        existing_style_ids = {
            b.comic_style_id
            for b in db.query(Book).filter(Book.is_comic == True).all()  # noqa: E712
        }
        for style_id, style in COMIC_STYLES.items():
            if style_id not in existing_style_ids:
                db.add(Book(**_comic_style_to_book_entry(style_id, style)))
        db.commit()
        return

    for book_data in DEFAULT_STORYBOOKS:
        db.add(Book(**book_data))
    for style_id, style in COMIC_STYLES.items():
        db.add(Book(**_comic_style_to_book_entry(style_id, style)))
    db.commit()


@router.get("/", response_model=BookList)
def list_books(
    theme: Optional[str] = Query(None),
    age_min: Optional[int] = Query(None),
    age_max: Optional[int] = Query(None),
    is_comic: Optional[bool] = Query(None),
    db: Session = Depends(get_db),
):
    seed_books(db)

    query = db.query(Book).filter(Book.is_active == True)  # noqa: E712
    if is_comic is not None:
        query = query.filter(Book.is_comic == is_comic)
    if theme:
        query = query.filter(Book.theme == theme)
    if age_min is not None:
        query = query.filter(Book.age_max >= age_min)
    if age_max is not None:
        query = query.filter(Book.age_min <= age_max)

    books = query.all()
    return {"books": books, "total": len(books)}


@router.get("/{book_id}", response_model=BookResponse)
def get_book(book_id: int, db: Session = Depends(get_db)):
    seed_books(db)
    book = db.query(Book).filter(Book.id == book_id).first()
    if not book:
        return {"error": "Book not found"}
    return book


@router.get("/comic-styles/all")
def list_comic_styles_books(db: Session = Depends(get_db)):
    seed_books(db)
    rows = db.query(Book).filter(Book.is_comic == True).all()  # noqa: E712
    return {
        "comic_books": [
            {
                "id": b.id,
                "comic_style_id": b.comic_style_id,
                "title": b.title,
                "description": b.description,
                "default_panel_count": b.default_panel_count,
                "border_color": b.border_color,
                "sample_premises": b.sample_premises or [],
            }
            for b in rows
        ]
    }
