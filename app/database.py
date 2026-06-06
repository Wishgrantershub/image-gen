from sqlalchemy import create_engine, text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from app.config import neon_database_url

_engine_url = neon_database_url()
engine = create_engine(
    _engine_url,
    connect_args={"check_same_thread": False}
    if _engine_url.startswith("sqlite")
    else {},
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    from app.models import user, child, book, story, story_page, order

    Base.metadata.create_all(bind=engine)
    _run_lightweight_migrations()


def _run_lightweight_migrations():
    """Best-effort additive schema fixes for SQLite dev DBs.

    SQLAlchemy create_all only creates new tables; it does not add columns
    to existing tables. We add the columns we need idempotently.
    """
    if not _engine_url.startswith("sqlite"):
        return
    statements = [
        "ALTER TABLE stories ADD COLUMN face_description TEXT",
        "ALTER TABLE stories ADD COLUMN session_token VARCHAR",
        "ALTER TABLE stories ADD COLUMN paid_at DATETIME",
        "ALTER TABLE stories ADD COLUMN pdf_storage_key VARCHAR",
        "ALTER TABLE stories ADD COLUMN pdf_storage_url VARCHAR",
    ]
    with engine.begin() as conn:
        for stmt in statements:
            try:
                conn.execute(text(stmt))
            except Exception:
                # Column already exists or other harmless condition
                pass
