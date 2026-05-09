# Backend Story Generation Flow (Simple English)

This document explains how the backend creates a personalized story preview (13 pages), from the first API call to final images with text.

It is based on the current code in this repo.

## Big Picture

When a user creates a story, the backend does this:

1. Validate user, child, and selected book.
2. Generate a **style bible** (global visual rules for all pages).
3. Generate an **identity sheet** from the child photo (illustrated face reference).
4. Generate a 13-page structured story package (text + image prompts + scene continuity fields).
5. For each page:
   - generate image,
   - run visual QA scoring,
   - retry if quality is low,
   - keep the best attempt.
6. Add page text using deterministic server-side text rendering.
7. Save results and mark story as `preview_ready`.

---

## Main Entry Point

### Route: `POST /api/stories/`
File: `app/routers/stories.py`

The route:

- Checks the child belongs to the current user.
- Ensures the selected book exists (and auto-seeds default books if needed).
- Requires child photo path.
- Creates a `Story` row with status `generating`.
- Calls `story_generation_service.generate_preview(...)`.
- If generation fails, status is set back to `draft` and API returns 500.

---

## Core Orchestrator

### Service: `StoryGenerationService`
File: `app/services/story_service.py`

The `generate_preview(...)` method is the main orchestrator.

### Step 1: Initialize AI services

- `ai_service.image_generation_service.initialize()`
- `ai_service.face_prep_service.initialize()`

This prepares Gemini image/text usage and face analysis service.

### Step 2: Validate child photo

If child photo path is missing or file does not exist, generation stops.

### Step 3: Build style bible (global consistency)

Method: `generate_style_bible(...)`

Uses Gemini text model to generate one strict JSON object containing things like:

- visual style
- color palette
- line/shading/lighting rules
- outfit invariants
- face rules
- negative constraints (for example: no photo paste)

If model output is bad/unparsable, backend uses a safe fallback style bible.

### Step 4: Build identity sheet (child likeness consistency)

Method called in image service:

- `generate_identity_sheet(child_photo_path, style_bible, book_title, style_keywords)`

This asks Gemini image model for a 2x2 illustrated character sheet from child photo:

- front smile
- 3/4 neutral
- side happy
- surprised

This sheet is saved to output as:

- `output/story_<story_id>_identity_sheet.png`

This is later passed as a reference input for page generation.

### Step 5: Generate structured 13-page story package

Method: `generate_story_package(...)`

Uses Gemini text model and returns an array of exactly 13 items.

Each item includes:

- `text` (2-3 short story sentences)
- `prompt` (image direction)
- `scene_id`
- `location`
- `time_of_day`
- `emotion`
- `camera_distance`
- `character_pose`

These extra fields help continuity across pages.

### Step 6: Save style metadata on story

The service saves metadata in `story.generated_text` as JSON string, including:

- `style_bible`
- `identity_sheet_path`

### Step 7: Reset existing pages and create new StoryPage rows

For regeneration, old pages are deleted and recreated from new story package.

Each row gets:

- `page_number`
- `text`
- `image_prompt`
- `is_preview = 1`

---

## Per-Page Image Generation Loop

Still inside `generate_preview(...)`, for each page:

### A. Read optional template assets

From `GeminiImageService.get_template_paths(book_id, page_number)`:

- base template: `templates/base/book_<id>/page_<n>.png`
- mask template: `templates/mask/book_<id>/page_<n>.png`

If files are missing, value is `None`.

### B. Retry loop with quality checks

Retry count is controlled by config:

- `MAX_PAGE_RETRIES` (default 3)

For each attempt:

1. Call `generate_page_with_mask(...)` with:
   - page prompt
   - child photo
   - style bible
   - page spec (scene/location/emotion/etc)
   - identity sheet path
   - optional base/mask template paths
2. Save attempt image as:
   - `output/story_<id>_page_<n>_attempt_<k>.png`
3. Run QA critic: `critique_generated_page(...)`.

### C. QA scoring fields

QA returns JSON with:

- `style_match_score` (1-10)
- `identity_match_score` (1-10)
- `photo_paste_risk` (1-10)
- `background_preservation` (1-10)
- `issues` (array of short labels)

### D. Pass/fail gate

Attempt is accepted early if all pass:

- `photo_paste_risk <= QA_MAX_PHOTO_PASTE_RISK` (default 3)
- `style_match_score >= QA_MIN_STYLE_MATCH` (default 8)
- `identity_match_score >= QA_MIN_IDENTITY_MATCH` (default 7)

If not, loop retries until max attempts.

### E. Best-attempt selection

Even if gate is not met, service still keeps best attempt by quality formula:

- `style + identity + background - photo_paste_risk`

Best attempt is renamed to final page file:

- `output/story_<id>_page_<n>.png`

---

## How One Page Is Actually Generated

### Service: `GeminiImageService`
File: `app/services/ai_service.py`

Method: `generate_page_with_mask(...)`

What it sends to Gemini image model:

- strict instruction text (preserve composition, no direct photo copy, no photoreal artifacts)
- optional base template image
- optional mask image
- identity sheet image (if available)
- child photo image
- style bible JSON + page continuity JSON inside prompt text

Model: `settings.GEMINI_IMAGE_MODEL` (default `gemini-2.5-flash-image`).

If API response has image bytes, it returns PIL image.
If it fails, service uses fallback text-to-image prompt path.

---

## Text Overlay Rendering (Book-like Output)

### Service: `TextRenderService`
File: `app/services/text_render_service.py`

After final page art is chosen, backend overlays story text on the image.

Method flow:

1. Read text box config from `book.template_data.text_layouts[page_number]`.
2. If no config, compute responsive default box from image size.
3. Wrap text to fit width.
4. Limit max lines based on text box height.
5. Draw translucent panel behind text for readability.
6. Draw text shadow + main text.
7. Save to same final image path.

This gives consistent readable text and avoids AI-generated gibberish text in images.

---

## Default Book Text Layouts

File: `app/routers/books.py`

Default seeded books now include `template_data.text_layouts` for pages 1-13.
These coordinates define where text should be rendered.

---

## Final Story Status and API Output

After all pages are processed:

- story status is set to `preview_ready`
- `preview_generated = 1`

Preview can be fetched from:

- `GET /api/stories/{story_id}/preview`

Each page in response includes:

- page number
- page text
- image URL (`/api/images/{page_id}`)

Image route:

- `GET /api/images/{page_id}` in `app/routers/images.py`

---

## Important Config You Can Tune

File: `app/config.py`

- `GEMINI_TEXT_MODEL`
- `GEMINI_IMAGE_MODEL`
- `MAX_PAGE_RETRIES`
- `QA_MAX_PHOTO_PASTE_RISK`
- `QA_MIN_STYLE_MATCH`
- `QA_MIN_IDENTITY_MATCH`
- `TEMPLATE_BASE_DIR`
- `TEMPLATE_MASK_DIR`

Changing these values affects quality, speed, and cost.

---

## Data Model Notes

- `Story.generated_text` currently stores JSON metadata string for generation context (style bible + identity sheet path).
- `StoryPage.text` stores story text shown on image and in preview response.
- `StoryPage.image_path` stores final generated image path.

---

## Failure Handling Summary

- If child photo missing: stop immediately.
- If style/story JSON parsing fails: use fallback or fail generation.
- If page generation fails in one attempt: retry.
- If all attempts fail quality gate: keep best available attempt.
- If full preview pipeline crashes: rollback and mark story as `draft`.

---

## Quick End-to-End Sequence (Short Version)

1. `POST /api/stories/`
2. Validate child/book/user.
3. Build style bible JSON.
4. Build identity sheet image.
5. Build 13-page story package JSON.
6. Create page records.
7. For each page: generate -> QA -> retry -> pick best.
8. Overlay text panel and text.
9. Mark preview ready.
10. Fetch via `GET /api/stories/{id}/preview`.
