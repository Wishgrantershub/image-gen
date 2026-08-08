from sqlalchemy import create_engine, text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from app.config import neon_database_url

_engine_url = neon_database_url()
engine = create_engine(
    _engine_url,
    pool_pre_ping=True,
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
    """Best-effort additive schema fixes for SQLite and Postgres.

    SQLAlchemy create_all only creates new tables; it does not add columns
    to existing tables. We add the columns we need idempotently. Each
    ALTER TABLE runs in its own transaction so a "column already exists"
    error on one statement does not abort the rest (Postgres aborts the
    entire transaction on any error).
    """
    is_sqlite = _engine_url.startswith("sqlite")
    datetime_type = "DATETIME" if is_sqlite else "TIMESTAMP"
    statements = [
        "ALTER TABLE stories ADD COLUMN face_description TEXT",
        "ALTER TABLE stories ADD COLUMN session_token VARCHAR",
        f"ALTER TABLE stories ADD COLUMN paid_at {datetime_type}",
        "ALTER TABLE stories ADD COLUMN pdf_storage_key VARCHAR",
        "ALTER TABLE stories ADD COLUMN pdf_storage_url VARCHAR",
        "ALTER TABLE story_pages ADD COLUMN gen_status VARCHAR",
        "ALTER TABLE story_pages ADD COLUMN gen_notes TEXT",
        "ALTER TABLE stories ADD COLUMN customer_email VARCHAR",
    ]
    for stmt in statements:
        try:
            with engine.begin() as conn:
                conn.execute(text(stmt))
        except Exception:
            pass
