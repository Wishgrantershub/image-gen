from typing import List, Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Book
from app.schemas import BookResponse, BookList

router = APIRouter(prefix="/api/books", tags=["Books"])

DEFAULT_BOOKS = [
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
        "template_data": {
            "text_layouts": {
                "1": {
                    "x": 34,
                    "y": 530,
                    "w": 444,
                    "h": 210,
                    "font_size": 30,
                    "line_spacing": 9,
                    "padding": 18,
                },
                "2": {
                    "x": 34,
                    "y": 530,
                    "w": 444,
                    "h": 210,
                    "font_size": 30,
                    "line_spacing": 9,
                    "padding": 18,
                },
                "3": {
                    "x": 34,
                    "y": 530,
                    "w": 444,
                    "h": 210,
                    "font_size": 30,
                    "line_spacing": 9,
                    "padding": 18,
                },
                "4": {
                    "x": 34,
                    "y": 530,
                    "w": 444,
                    "h": 210,
                    "font_size": 30,
                    "line_spacing": 9,
                    "padding": 18,
                },
                "5": {
                    "x": 34,
                    "y": 530,
                    "w": 444,
                    "h": 210,
                    "font_size": 30,
                    "line_spacing": 9,
                    "padding": 18,
                },
                "6": {
                    "x": 34,
                    "y": 530,
                    "w": 444,
                    "h": 210,
                    "font_size": 30,
                    "line_spacing": 9,
                    "padding": 18,
                },
                "7": {
                    "x": 34,
                    "y": 530,
                    "w": 444,
                    "h": 210,
                    "font_size": 30,
                    "line_spacing": 9,
                    "padding": 18,
                },
                "8": {
                    "x": 34,
                    "y": 530,
                    "w": 444,
                    "h": 210,
                    "font_size": 30,
                    "line_spacing": 9,
                    "padding": 18,
                },
                "9": {
                    "x": 34,
                    "y": 530,
                    "w": 444,
                    "h": 210,
                    "font_size": 30,
                    "line_spacing": 9,
                    "padding": 18,
                },
                "10": {
                    "x": 34,
                    "y": 530,
                    "w": 444,
                    "h": 210,
                    "font_size": 30,
                    "line_spacing": 9,
                    "padding": 18,
                },
                "11": {
                    "x": 34,
                    "y": 530,
                    "w": 444,
                    "h": 210,
                    "font_size": 30,
                    "line_spacing": 9,
                    "padding": 18,
                },
                "12": {
                    "x": 34,
                    "y": 530,
                    "w": 444,
                    "h": 210,
                    "font_size": 30,
                    "line_spacing": 9,
                    "padding": 18,
                },
                "13": {
                    "x": 34,
                    "y": 530,
                    "w": 444,
                    "h": 210,
                    "font_size": 30,
                    "line_spacing": 9,
                    "padding": 18,
                },
            }
        },
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


def seed_books(db: Session):
    existing = db.query(Book).first()
    if not existing:
        for book_data in DEFAULT_BOOKS:
            book = Book(**book_data)
            db.add(book)
        db.commit()


@router.get("/", response_model=BookList)
def list_books(
    theme: Optional[str] = Query(None),
    age_min: Optional[int] = Query(None),
    age_max: Optional[int] = Query(None),
    db: Session = Depends(get_db),
):
    seed_books(db)

    query = db.query(Book).filter(Book.is_active == True)

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
