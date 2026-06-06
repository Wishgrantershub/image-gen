from sqlalchemy import Column, Integer, String, Text, JSON, Boolean
from sqlalchemy.orm import relationship
from app.database import Base


class Book(Base):
    __tablename__ = "books"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    theme = Column(String, nullable=False)
    age_min = Column(Integer, default=0)
    age_max = Column(Integer, default=12)
    page_count = Column(Integer, default=24)
    cover_image = Column(String, nullable=True)
    template_data = Column(JSON, nullable=True)
    is_active = Column(Boolean, default=True)
    style_keywords = Column(String, nullable=True)
    character_base = Column(String, nullable=True)
    background_consistency = Column(Boolean, default=True)

    is_comic = Column(Boolean, default=False)
    comic_style_id = Column(String, nullable=True, index=True)
    style_suffix = Column(Text, nullable=True)
    bubble_style = Column(String, nullable=True)
    border_color = Column(String, nullable=True)
    border_width = Column(Integer, nullable=True)
    default_panel_count = Column(Integer, nullable=True)
    palette = Column(JSON, nullable=True)
    sample_premises = Column(JSON, nullable=True)

    stories = relationship("Story", back_populates="book")
