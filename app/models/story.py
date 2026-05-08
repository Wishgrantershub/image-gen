from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, Text, Enum as SQLEnum
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

    user = relationship("User", back_populates="stories")
    child = relationship("Child", back_populates="stories")
    book = relationship("Book", back_populates="stories")
    pages = relationship("StoryPage", back_populates="story", cascade="all, delete-orphan")
    order = relationship("Order", back_populates="story", uselist=False)