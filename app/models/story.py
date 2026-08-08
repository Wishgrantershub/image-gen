from sqlalchemy import (
    Column,
    Integer,
    String,
    ForeignKey,
    DateTime,
    Text,
    Enum as SQLEnum,
    Float,
)
from sqlalchemy.orm import relationship
from datetime import datetime
from app.database import Base
import enum


class StoryStatus(str, enum.Enum):
    DRAFT = "draft"
    GENERATING = "generating"
    PREVIEW_READY = "preview_ready"
    PURCHASED = "purchased"
    COMPLETED = "completed"


class Story(Base):
    __tablename__ = "stories"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    child_id = Column(Integer, ForeignKey("children.id"), nullable=False)
    book_id = Column(Integer, ForeignKey("books.id"), nullable=False)
    title = Column(String, nullable=True)
    status = Column(SQLEnum(StoryStatus), default=StoryStatus.DRAFT)
    generated_text = Column(Text, nullable=True)
    preview_generated = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    is_comic = Column(Integer, default=0)
    premise = Column(Text, nullable=True)
    tier = Column(String, nullable=True)
    panel_count = Column(Integer, nullable=True)
    panel_layout = Column(String, nullable=True)
    pdf_path = Column(String, nullable=True)
    cover_path = Column(String, nullable=True)
    share_token = Column(String, nullable=True, index=True)
    session_token = Column(String, nullable=True, index=True)
    progress_step = Column(String, nullable=True)
    progress_message = Column(String, nullable=True)
    progress_pct = Column(Integer, default=0)
    error_message = Column(Text, nullable=True)
    amount = Column(Float, nullable=True)
    currency = Column(String, default="INR")
    face_description = Column(Text, nullable=True)
    paid_at = Column(DateTime, nullable=True)
    pdf_storage_key = Column(String, nullable=True)
    pdf_storage_url = Column(String, nullable=True)
    customer_email = Column(String, nullable=True)

    user = relationship("User", back_populates="stories")
    child = relationship("Child", back_populates="stories")
    book = relationship("Book", back_populates="stories")
    pages = relationship(
        "StoryPage", back_populates="story", cascade="all, delete-orphan"
    )
    order = relationship("Order", back_populates="story", uselist=False)
