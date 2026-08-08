from sqlalchemy import Column, Integer, String, ForeignKey, Text
from sqlalchemy.orm import relationship
from app.database import Base


class StoryPage(Base):
    __tablename__ = "story_pages"

    id = Column(Integer, primary_key=True, index=True)
    story_id = Column(Integer, ForeignKey("stories.id"), nullable=False)
    page_number = Column(Integer, nullable=False)
    text = Column(Text, nullable=True)
    image_path = Column(String, nullable=True)
    image_prompt = Column(Text, nullable=True)
    is_preview = Column(Integer, default=0)
    gen_status = Column(String, nullable=True)
    gen_notes = Column(Text, nullable=True)

    story = relationship("Story", back_populates="pages")
