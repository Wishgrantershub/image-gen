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
        "page_count": 24
    },
    {
        "title": "Space Explorer",
        "description": "Blast off on an intergalactic adventure to save the galaxy",
        "theme": "imagination",
        "age_min": 5,
        "age_max": 10,
        "page_count": 24
    },
    {
        "title": "The Friendly Dragon",
        "description": "Make a magical friend in this heartwarming tale of friendship",
        "theme": "love-friendship",
        "age_min": 3,
        "age_max": 7,
        "page_count": 24
    },
    {
        "title": "Superhero Academy",
        "description": "Train to become the hero the world needs",
        "theme": "hobbies-professions",
        "age_min": 6,
        "age_max": 12,
        "page_count": 24
    },
    {
        "title": "The Brave Scientist",
        "description": "Discover the wonders of science and solve mysteries",
        "theme": "learning-growth",
        "age_min": 5,
        "age_max": 10,
        "page_count": 24
    },
    {
        "title": "Ocean Explorer",
        "description": "Dive deep into the magical underwater world",
        "theme": "imagination",
        "age_min": 4,
        "age_max": 9,
        "page_count": 24
    }
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
    db: Session = Depends(get_db)
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