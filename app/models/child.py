from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, JSON
from sqlalchemy.orm import relationship
from datetime import datetime
from app.database import Base

class Child(Base):
    __tablename__ = "children"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    name = Column(String, nullable=False)
    gender = Column(String, nullable=True)
    age = Column(Integer, nullable=True)
    photo_path = Column(String, nullable=True)
    face_embedding = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = relationship("User", back_populates="children")
    stories = relationship("Story", back_populates="child", cascade="all, delete-orphan")