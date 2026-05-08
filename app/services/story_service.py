import os
import json
import google.genai as genai
from typing import List, Dict, Optional
from sqlalchemy.orm import Session
from PIL import Image

from app.config import settings
from app.models import Story, StoryPage, Child, Book
from app.services import ai_service

class StoryGenerationService:
    def __init__(self):
        self.client = None

    def initialize(self):
        if self.client is not None:
            return
        genai.configure(api_key=settings.GEMINI_API_KEY)
        self.client = genai
        print("Gemini API initialized")

    def generate_story_text(
        self,
        child_name: str,
        child_age: int,
        gender: str,
        book_title: str,
        theme: str,
        page_count: int = 13
    ) -> List[Dict[str, str]]:
        if self.client is None:
            self.initialize()

        gender_pronoun = "he" if gender.lower() in ["male", "boy"] else "she" if gender.lower() in ["female", "girl"] else "they"

        prompt = f"""Create a children's story about a hero named {child_name}.

Write a {page_count}-page story suitable for a {child_age} year old child.
Theme: {theme}
Book: {book_title}

For each page, provide:
1. A short text (2-3 sentences max, child-friendly language)
2. An image prompt for illustration (describe the scene, include "a child with {gender_pronoun} features" for face consistency)

Return ONLY a JSON array with {page_count} objects, each having "text" and "prompt" keys. No other text.
Example format:
[
  {{"text": "Page 1 text here", "prompt": "Image prompt here"}},
  {{"text": "Page 2 text here", "prompt": "Image prompt here"}}
]"""

        try:
            response = self.client.models.generate_content(
                model="gemini-2.0-flash",
                contents=prompt
            )

            text = response.text.strip()
            if text.startswith("```json"):
                text = text[7:]
            if text.startswith("```"):
                text = text[3:]
            if text.endswith("```"):
                text = text[:-3]

            pages = json.loads(text.strip())
            return pages
        except Exception as e:
            print(f"Error generating story text: {e}")
            return []

    def generate_preview(
        self,
        db: Session,
        story: Story,
        child: Child,
        book: Book,
        num_pages: int = 13
    ) -> bool:
        try:
            ai_service.face_embedding_service.initialize()
            ai_service.image_generation_service.initialize()

            child_name = child.name
            child_age = child.age or 6
            gender = child.gender or "neutral"

            pages_data = self.generate_story_text(
                child_name=child_name,
                child_age=child_age,
                gender=gender,
                book_title=book.title,
                theme=book.theme,
                page_count=num_pages
            )

            if not pages_data:
                return False

            face_embedding = child.face_embedding if child.face_embedding else None

            for idx, page_data in enumerate(pages_data):
                page = StoryPage(
                    story_id=story.id,
                    page_number=idx + 1,
                    text=page_data.get("text", ""),
                    image_prompt=page_data.get("prompt", ""),
                    is_preview=1 if idx < num_pages else 0
                )
                db.add(page)

            db.commit()
            db.refresh(story)

            for page in story.pages:
                if page.is_preview:
                    image = ai_service.image_generation_service.generate_image(
                        prompt=page.image_prompt,
                        face_embedding=face_embedding
                    )
                    if image:
                        filename = f"story_{story.id}_page_{page.page_number}.png"
                        image_path = ai_service.image_generation_service.save_image(image, filename)
                        page.image_path = image_path

            db.commit()
            story.status = "preview_ready"
            story.preview_generated = 1
            db.commit()

            return True
        except Exception as e:
            print(f"Error generating preview: {e}")
            db.rollback()
            return False


story_generation_service = StoryGenerationService()