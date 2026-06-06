# ComicMe — Implementation Reference

A detailed walkthrough of every change that took the app from a half-empty,
hardcoded-bubble comic generator to a full-page, style-aware, character-consistent
PDF pipeline.

Project root: `C:\Users\ganga\Documents\zerzura\image-gen`
Backend: FastAPI · `app/main.py` · runs via `uvicorn app.main:app --reload --port 8000`
Image gen: Google Gemini + Imagen 4 (text-only) / `imagen-3.0-capability-001` (subject ref)

---

## Table of contents

1. [Architecture overview](#1-architecture-overview)
2. [Phase 1 — Character identity anchoring](#2-phase-1--character-identity-anchoring)
3. [Phase 2 — Full-page template](#3-phase-2--full-page-template)
4. [Phase 3 — Bonuses (real QR, page numbers, per-style narration)](#4-phase-3--bonuses)
5. [Wiring — `comic_service.py` end-to-end integration](#5-wiring--comicservicepy-end-to-end-integration)
6. [Bug fixes — Imagen payload, model selection, safety](#6-bug-fixes--imagen-payload-model-selection-safety)
7. [Config, dependencies, ops](#7-config-dependencies-ops)
8. [Known gotchas / lessons learned](#8-known-gotchas--lessons-learned)

---

## 1. Architecture overview

```
child photo  ─┐
              ├─►  IdentitySheetService  ─►  identity_sheet.png
child photo  ─┘
                                                          ┌─►  panel_1.png ... panel_24.png
                                                          │
   panel_description[i]  ──►  GeminiImageService.generate_comic_panel()
                                                          │
                                                          └─►  uses subject reference (face) + face description
                                                                  on imagen-3.0-capability-001
   panel_images  ──►  VisionGemini.analyze_panel_layout()  ─►  bubble_box%, caption_box%
                                                          ┌─►  panel with bubble + caption box
   panel_image  ──►  text_render_service.render_comic_panel()
                                                          └─►  layout-aware narration box style
   panel images[6]  ──►  page_template.build_page(layout, panels)  ──►  full_page_N.png
   full pages  ──►  pdf_builder.build_pdf(cover, pages, back, style_id, tier_id)
                                                                                  │
                                                                                  └─►  comic.pdf
```

Three models are used, each in its own slot:
| Model                                       | Used for                                              | Setting                              |
|---------------------------------------------|-------------------------------------------------------|--------------------------------------|
| `gemini-2.5-flash-image`                    | Identity sheet (multimodal)                           | `GEMINI_IMAGE_MODEL_MULTIMODAL`       |
| `gemini-2.5-flash`                          | Face description text + vision-driven bubble layout   | `GEMINI_TEXT_MODEL`                  |
| `imagen-3.0-capability-001`                | Panel + cover generation WITH subject reference       | `GEMINI_IMAGE_MODEL_SUBJECT_REF`     |
| `imagen-4.0-generate-001`                   | Fallback for panel/cover when capability model is 404 | `GEMINI_IMAGE_MODEL_TXT2IMG`         |

Tier → page count:
| Tier    | Panels | Interior pages | PDF pages (cover + interior + back) |
|---------|--------|----------------|------------------------------------|
| basic   | 6      | 1              | 3                                  |
| premium | 12     | 2              | 4                                  |
| deluxe  | 24     | 4              | 6                                  |

Panels per page is 6 (constant). Layouts are 2x3 grids (one layout per style,
reused across pages).

---

## 2. Phase 1 — Character identity anchoring

**Problem:** the same child in the photo looked like a different kid in every
panel. Imagen 4 was treating each prompt as a fresh generation with no anchor
to the original face.

**Solution:** three layers of identity anchoring.

### 2.1 `extract_face_description()` — `app/services/ai_service.py:252`

Calls `gemini-2.5-flash` (vision) on the child's photo. Asks for ONE sentence
(max 30 words) describing distinguishing visual features: age, face shape, skin
tone, hair, eye color, etc. Returns plain text. Saved to
`Story.face_description` and re-injected as a text anchor in every panel prompt.

Why a separate text anchor AND a subject reference (see 2.2)? Subject reference
keeps the face structurally similar; the text anchor keeps clothing/accessories/
expression consistent. Together they're far more reliable than either alone.

### 2.2 `_imagen_predict()` with subject reference — `app/services/ai_service.py:160`

When `subject_reference_path` is provided:
- Image bytes are base64-encoded
- Sent as `referenceImages[0]` of type `REFERENCE_TYPE_SUBJECT`
- Includes `subjectImageConfig.subjectType = "SUBJECT_TYPE_PERSON"` and
  `subjectImageConfig.subjectDescription` = the face description from 2.1
- Model used: `imagen-3.0-capability-001` (the only Imagen model that supports
  subject reference)

If the capability model returns 400/403/404 (model not enabled on the API key),
the request is **automatically retried** on `imagen-4.0-generate-001` without
the reference image and without `editMode`. The text anchor in the prompt
still gives a reasonable (if less faithful) result.

### 2.3 `Story.face_description` column — `app/database.py`

Added a `face_description TEXT` column to the `stories` table. Lightweight
migration runs on startup via `_run_lightweight_migrations()`. No Alembic
needed.

### 2.4 `generate_comic_panel()` — `app/services/ai_service.py:789`

Accepts `character_description` and `subject_reference_path`. Builds the
prompt with the anchor prepended:

```
The protagonist is: a 7yo child with brown hair, big smile, light skin tone.
This exact same character must appear in every panel — do not change face,
hair, build, skin tone, outfit, or approximate age.
```

---

## 3. Phase 2 — Full-page template

**Problem:** panels were generated as bare images and pasted side-by-side with
hardcoded bubble positions. The output looked like a wall of floating
rectangles, not a comic book.

**Solution:** a true page template that owns composition, backgrounds,
borders, and per-style aesthetics.

### 3.1 Layout JSON files — `app/data/comic_layouts/`

One file per style, reused across pages within a tier. Each is a single JSON
blob describing the page from scratch:

| File                  | Style     | BG                | Border | Notes                                            |
|-----------------------|-----------|-------------------|--------|--------------------------------------------------|
| `manga_2x3.json`      | Manga     | Screentone, cream | Black  | `narration_box_style: manga_slab`                |
| `pixar_2x3.json`      | Pixar     | Solid, warm cream | Brown  | `panel_border_radius: 24` (rounded corners)      |
| `superhero_2x3.json`  | Superhero | Halftone, golden  | Black  | `border_width: 6`, thick borders, `superhero_block` |

Each layout has the same shape:

```json
{
  "style": "manga",
  "tier": "basic",
  "page_size": [1200, 1600],
  "page_bg": "#FAF7EE",
  "page_bg_pattern": "screentone" | "halftone" | "solid",
  "screentone_dot_color": "#D4C8A8",
  "screentone_dot_size": 2,
  "screentone_spacing": 10,
  "border_color": "#0A0A0A",
  "border_width": 4,
  "panel_border_radius": 0,
  "header": {
    "height": 100,
    "title_size": 56,
    "subtitle_size": 22,
    "title_color": "#0A0A0A",
    "subtitle_color": "#5A4A3A",
    "show_subtitle": true
  },
  "footer": { "height": 60, "text": "MADE WITH COMICME - TURN ANYONE INTO A COMIC HERO", "color": "#0A0A0A", "size": 18 },
  "margin_x": 50, "margin_top": 130, "margin_bottom": 80, "gutter": 12,
  "narration_box_style": "manga_slab" | "pixar_rounded" | "superhero_block" | "default",
  "show_page_number": false,
  "panels": [
    { "x": 50,  "y": 170,  "w": 750,  "h": 440, "shape": "rect", "zoom": "cover" },
    { "x": 810, "y": 170,  "w": 340,  "h": 440, "shape": "rect", "zoom": "fit"   },
    { "x": 50,  "y": 620,  "w": 550,  "h": 420, "shape": "rect", "zoom": "fit"   },
    { "x": 610, "y": 620,  "w": 540,  "h": 420, "shape": "rect", "zoom": "fit"   },
    { "x": 50,  "y": 1050, "w": 540,  "h": 420, "shape": "rect", "zoom": "fit"   },
    { "x": 610, "y": 1050, "w": 540,  "h": 420, "shape": "rect", "zoom": "fit"   }
  ]
}
```

The 2x3 grid in manga is intentional: top row is a wide establishing shot
plus a tall narrow reaction panel; middle and bottom rows are two equal
panels each.

### 3.2 `app/services/page_template.py`

Single entry point: `build_page(layout, panel_paths, title, subtitle, current_page, total_pages)`.
Returns a `PIL.Image` of size `layout["page_size"]`.

Internally:
1. Create RGBA canvas, fill with `page_bg` color
2. If pattern is screentone/halftone, draw dots via `_draw_dot_pattern()`
3. For each panel cfg in `layout["panels"]`:
   - `_paste_panel(sheet, panel_path, box, zoom, border_color, border_width, border_radius)`
   - `zoom="cover"` crops to fill the box; `zoom="fit"` letterboxes
   - Rounded corners: build a white mask with `mdraw.rounded_rectangle(..., fill=255)`, paste the panel through that mask, then draw the colored outline directly on the masked panel. (Earlier code used `putalpha` with a dark mask which darkened the entire interior — that bug was fixed.)
4. `_draw_header(sheet, layout["header"], page_w, border_color, title, subtitle)` — centered title + subtitle, with dynamic downscaling when text would overflow.
5. `_draw_footer(sheet, layout["footer"], page_w, page_h, border_color)`
6. If `total_pages > 1 OR layout["show_page_number"]`, call `_draw_page_number(sheet, page_w, page_h, border_color, current_page, total_pages)`.
7. Convert to RGB and return.

Helper functions exposed for the smoke tests:
- `load_layout(style_id, tier_id)` — maps tier to layout suffix (`basic → 2x3, premium → 3x4, deluxe → 4x6`) and falls back to `{style}_2x3.json` if the exact tier file is missing
- `list_available_layouts()`

### 3.3 `render_comic_panel()` upgrade — `app/services/text_render_service.py`

`render_comic_panel` was extended to accept vision-decided box placement
instead of hardcoded quadrants:

```python
def render_comic_panel(
    panel_image: Image.Image,
    text: str,
    bubble_kind: str = "speech",          # speech | shout | thought | whisper
    bubble_box_pct: Optional[List[int]] = None,   # [x1, y1, x2, y2] as 0–100 percentages
    caption_box_pct: Optional[List[int]] = None, # same shape
    narration_box_style: str = "default",
    border_radius: int = 0,
) -> Image.Image
```

New helpers:
- `_pct_to_box(pct, panel_w, panel_h)` — converts percentage box to pixel box
- `_draw_caption_box_manga_slab` — vertical right strip, all caps, thin black border, used for manga
- `_draw_caption_box_pixar_rounded` — top center, large rounded corners, friendly font
- `_draw_caption_box_superhero_block` — top center, thick black border with yellow accent strip
- `render_comic_panel` itself: if `caption_box_pct` is given, draw the style-specific caption box at that position; otherwise fall back to a full-width top caption.

### 3.4 `build_pdf()` rewrite — `app/services/pdf_builder.py:373`

Old version built one big panel sheet with `build_panel_sheet` and called it
done. New version is a proper multi-page PDF builder:

1. Render cover (existing `build_cover_page`)
2. Load layout for `(style_id, tier_id)` via `page_template.load_layout()`
3. Determine `panels_per_page` from `len(layout["panels"])` (6 for 2x3)
4. Chunk `panel_paths` into N chunks of 6
5. For each chunk, call `build_page(layout, chunk, title, subtitle, current_page=i, total_pages=N)`
6. Render back cover (now with real QR — see 4.1)
7. Convert all pages to JPEG via PIL, write to `img2pdf.convert([...])`, save to `output/comics/comic_{story_id}.pdf`
8. Clean up temp JPEGs

New `build_pdf` parameters: `style_id: str = "manga"`, `tier_id: str = "basic"`.
The subtitle per interior page includes the page number when multi-page:
`"MANGA EDITION - PAGE 2 OF 4"`.

---

## 4. Phase 3 — Bonuses

### 4.1 Real scannable QR on back cover

`build_back_cover` now uses `_make_qr_code(share_url, size_px=280)` which
returns a real `PIL.Image` of a QR code (using `qrcode[pil]` with
`image_factory=qrcode.image.pil.PilImage`).

```python
import qrcode, qrcode.image.pil, qrcode.constants
qr = qrcode.QRCode(
    error_correction=qrcode.constants.ERROR_CORRECT_M,
    box_size=8, border=2,
)
qr.add_data(url)
qr.make(fit=True)
img = qr.make_image(image_factory=qrcode.image.pil.PilImage,
                    fill_color="black", back_color="white").convert("RGB")
```

`qrcode.image.pil` MUST be imported explicitly to register the factory —
otherwise `qrcode.image.pil.PilImage` raises `AttributeError`.

The back cover layout:
- Headline: "YOUR STORY, REIMAGINED." (centered, 64pt)
- Subhead: 3 lines of body text describing the product
- QR code: 280px in a 296x296 white box with 4px black border
- "SCAN TO VIEW ONLINE" label under the QR
- Share URL in micro text near the bottom
- "MADE WITH COMICME - COMICME.AI" footer

`qrcode[pil]==7.4.2` was added to `requirements.txt`.

### 4.2 Page numbers for multi-page

Logic in `build_page`:
```python
if total_pages > 1 or layout.get("show_page_number", False):
    _draw_page_number(sheet, page_w, page_h, border_color, current_page, total_pages)
```

`_draw_page_number` renders e.g. `"2 / 4"` in the bottom-right corner using
the same fonts as the header. Subtitle is set to e.g. `"MANGA EDITION - PAGE 2 OF 4"`.

Result:
- basic (1 page) → no number
- premium (2 pages) → "1 / 2", "2 / 2"
- deluxe (4 pages) → "1 / 4", "2 / 4", "3 / 4", "4 / 4"

### 4.3 Per-style narration boxes

Three caption-box renderers, selected by `layout["narration_box_style"]`:

| Style               | Look                                                                                 |
|---------------------|--------------------------------------------------------------------------------------|
| `manga_slab`        | Vertical right strip, all caps, thin black border, square corners                    |
| `pixar_rounded`     | Top center, large rounded corners (16px), soft warm fill, friendly font              |
| `superhero_block`   | Top center, thick 4px black border, yellow accent strip at the top, bold blocky font |
| `default`           | Top center, standard rounded box with black border — fallback                        |

The narration box position itself is still vision-decided per panel via
`caption_box_pct` from `analyze_panel_layout()`. The style controls only the
visual treatment of that box.

---

## 5. Wiring — `comic_service.py` end-to-end integration

Both `generate_comic()` (full user comic) and `build_sample_comic()`
(landing-page sample) were updated to chain everything together:

1. **Identity sheet** — `ai_service.generate_comic_identity_sheet(child_photo, style)` writes `story_{id}_identity_sheet.png` to `COMIC_PANEL_DIR`.

2. **Face description** — wrap in try/except:
   ```python
   face_desc = ai_service.image_generation_service.extract_face_description(child_photo)
   story.face_description = face_desc
   db.commit()
   ```
   On failure, `face_desc` defaults to `""` and the comic still proceeds (text anchor simply empty).

3. **Panel generation loop** — for each panel description:
   ```python
   panel_img = ai_service.image_generation_service.generate_comic_panel(
       panel_description=...,
       child_photo_path=child.photo_path,
       identity_sheet_path=identity_sheet_path,
       style_suffix=style["suffix"],
       style_name=style["name"],
       panel_index=i+1,
       panel_count=total,
       character_description=story.face_description or "",
   )
   ```
   The character description becomes both the text anchor in the prompt AND
   the `subjectDescription` in `subjectImageConfig`.

4. **Vision-decided bubble layout** — for each saved panel image:
   ```python
   layout_info = ai_service.image_generation_service.analyze_panel_layout(panel_path)
   bubble_box = layout_info.get("bubble_box")  # [x1, y1, x2, y2] as 0-100 %
   caption_box = layout_info.get("caption_box")
   bubble_kind = layout_info.get("bubble_kind", "speech")
   ```

5. **Render panel with bubbles** — pass vision-decided boxes to `render_comic_panel`:
   ```python
   rendered = render_comic_panel(
       panel_image=Image.open(panel_path),
       text=panel.get("dialogue", ""),
       bubble_kind=bubble_kind,
       bubble_box_pct=bubble_box,
       caption_box_pct=caption_box,
       narration_box_style=narration_style,
       border_radius=layout.get("panel_border_radius", 0),
   )
   rendered.save(panel_path, "PNG")
   ```

6. **Build PDF** — pass `style_id` and `tier_id`:
   ```python
   pdf_path = build_pdf(
       panel_paths=panel_paths,
       cover_path=cover_path,
       title=story.title or f"{child.name}'s Adventure",
       style_name=style["name"],
       share_url=f"https://comicme.app/c/{story.share_token or story.id}",
       output_filename=f"comic_{story.id}.pdf",
       style_id=style["id"],
       tier_id=tier_id,
   )
   ```

Helper `_get_narration_box_style(style_id, tier_id)` is called once per
generation to read the layout JSON and pull out the `narration_box_style`
field, so `comic_service` doesn't have to know about layout file paths.

---

## 6. Bug fixes — Imagen payload, model selection, safety

This section is the answer to "why were we still getting `IMAGE_OTHER`?" —
each of these was hit, debugged, and fixed in sequence.

### 6.1 `Reference image with type SUBJECT must have subject_image_config field` (400)

Imagen 4 requires every `REFERENCE_TYPE_SUBJECT` entry to carry a sibling
`subjectImageConfig` with `subjectType` and `subjectDescription`. Initial code
only had the type and the image — Imagen rejected it.

**Fix:** add `subjectImageConfig` and pass the face description through:

```python
ref_entry = {
    "referenceType": "REFERENCE_TYPE_SUBJECT",
    "referenceId": 0,
    "referenceImage": {"image": {"bytesBase64Encoded": ref_b64, "mimeType": mime_type}},
    "subjectImageConfig": {
        "subjectType": "SUBJECT_TYPE_PERSON",
        "subjectDescription": subject_description.strip() or "the main character",
    },
}
```

### 6.2 `No uri or raw bytes are provided in media content` (400) — THE BIG ONE

**Root cause:** `imagen-4.0-generate-001` is a TEXT-ONLY model. It does not
accept reference images. The API does not validate this upfront; instead it
returns a misleading "no bytes provided" error when it sees a `referenceImages`
array on a model that doesn't support it.

The error message ("Image editing failed") is a hint: the API treats any
request with `referenceImages` as an editing operation, and the editing code
path is only enabled on the capability model.

**Fix:** two parts:

(a) Use the correct model: `imagen-3.0-capability-001` is the only Imagen
model that supports `REFERENCE_TYPE_SUBJECT`. Added a new config setting
`GEMINI_IMAGE_MODEL_SUBJECT_REF: str = "imagen-3.0-capability-001"`. The
function now picks the model based on whether a subject reference was
provided:

```python
has_ref = bool(subject_reference_path) and bool(os.path.exists(subject_reference_path or ""))
if has_ref and subject_reference_path is not None:
    model_name = settings.GEMINI_IMAGE_MODEL_SUBJECT_REF
else:
    model_name = settings.GEMINI_IMAGE_MODEL_TXT2IMG
```

(b) Nest the image bytes inside a `image` object with a `mimeType`. Even on
the capability model, the flat `{ "bytesBase64Encoded": ... }` at the
`referenceImage` level can be rejected. The shape that works is:

```python
"referenceImage": {
    "image": {
        "bytesBase64Encoded": ref_b64,
        "mimeType": "image/png",  # or image/jpeg
    }
}
```

(c) Add `editMode: "EDIT_MODE_DEFAULT"` to `parameters` when using reference
images. The capability model expects an editing mode even for subject ref.

(d) Automatic fallback: if the capability model returns 400/403/404 (model
not enabled on the API key, or feature restricted), the function
**automatically retries on the standard generate model with the reference
image removed**. The text-only prompt with the face-description anchor still
produces a reasonable result. The fallback is logged so it's obvious what
happened.

### 6.3 `person_generation: "allow_adult"` blocks children

`allow_adult` means "generate adults, but not children." Since the entire
product is child comics, this was a guaranteed fail. Changed all 4
`_imagen_predict` callsites in `generate_comic_panel` and
`generate_cover_image` to `"allow_all"`.

Note: `allow_all` requires the API key to be allowlisted for child
generation. If your key isn't, the next failure will be a 400/403 with a
message specifically about `allow_all` — distinct from the byte-encoding
errors above.

### 6.4 `os.path.join` discards earlier path components when the second is absolute

A pre-existing bug in `pdf_builder.build_pdf`: it was building temp paths
with `os.path.join(COMIC_OUTPUT_DIR, f"_cover_{output_filename}.jpg")`. When
a caller passed an absolute `output_filename`, `os.path.join` silently
discarded `COMIC_OUTPUT_DIR` and produced a malformed path. Smoke testing
caught this when a test passed an absolute path.

**Fix:** normalize `output_filename` to a basename once at the top of the
function:

```python
safe_name = os.path.basename(output_filename) or "comic.pdf"
```

Then use `safe_name` in all temp path construction. Production callers pass
relative names so they were never affected, but it was a footgun for any
future caller.

### 6.5 Dynamic font scaling was scaling UP

`_draw_header` was originally written with `if total < height: scale = height/total`
which always scaled. Intended behavior: only downscale when the text overflows.

**Fix:**
```python
if total_height > header_height:
    scale = header_height / total_height
    if scale < 1.0:
        title_size = int(title_size * scale)
```

### 6.6 PIL text baseline gotcha

PIL's `draw.textbbox((0, 0), text, font)` returns `(x0, y0, x1, y1)` where
`y0` is the offset from the top of the cell to the **cap-top** of the text,
not to the y-coordinate where you'd start drawing. To position text so its
cap-top is at `ty`, you draw at `(tx, ty - y0)`. Initial code drew at
`(tx, ty)` and overlapped the subtitle with the title.

**Fix:** everywhere we center text vertically, draw at `(tx, ty - y0)`
where `y0` came from the bounding box.

### 6.7 Rounded border darkening the panel interior

`_paste_panel` originally created a transparency mask, painted the panel
through the mask, then drew a rounded outline — but the mask layer was
`(0, 0, 0, 0.95)` alpha, which darkens the visible art. Result: panels
with `border_radius > 0` looked 5% darker than they should.

**Fix:** build a fully opaque white mask via `mdraw.rounded_rectangle(..., fill=255)`,
paste the panel through it, then draw the colored outline directly on the
panel alpha. No more darkening.

---

## 7. Config, dependencies, ops

### 7.1 New / changed settings in `app/config.py`

```python
GEMINI_IMAGE_MODEL_TXT2IMG: str = "imagen-4.0-generate-001"
GEMINI_IMAGE_MODEL_SUBJECT_REF: str = "imagen-3.0-capability-001"  # NEW
```

Both can be overridden via environment variables.

### 7.2 `requirements.txt`

Added:
```
qrcode[pil]==7.4.2
```

The `[pil]` extra is required — it pulls in the `qrcode.image.pil` factory
that the QR code generation needs.

### 7.3 Running it

```bash
cd C:\Users\ganga\Documents\zerzura\image-gen
uvicorn app.main:app --reload --port 8000
```

The backend hot-reloads on Python file changes. Frontend is at the same
origin's `/`. Story generation endpoint is
`POST /api/comics/generate` (auth required) with payload
`{ child_id, style_id, tier_id, panel_count?, prompt? }`.

### 7.4 Database

`Story.face_description` (TEXT, nullable) is added by the lightweight
migration in `_run_lightweight_migrations()` which runs on startup. No
Alembic, no separate migration step.

### 7.5 Output files

Per story, the following files are written to `output/`:
- `comic_panels/story_{id}_identity_sheet.png` — character reference image
- `comic_panels/story_{id}_page_{i}.png` — individual panel images (pre-bubble)
- `comic_sheets/story_{id}_page_{i}.png` — debug artifacts (legacy, optional)
- `comics/comic_{id}.pdf` — final PDF deliverable

---

## 8. Known gotchas / lessons learned

1. **Imagen 4 generate models don't support reference images.** Only
   `imagen-3.0-capability-001` does. The error message
   (`No uri or raw bytes are provided in media content`) is misleading; it's
   the API's "wrong model" signal.

2. **`imagen-3.0-capability-001` may not be enabled on every API key.** The
   fallback to `imagen-4.0-generate-001` is in place. If you see a log line
   like `[Imagen] subject-ref model 'imagen-3.0-capability-001' not available
   on this key — falling back`, the comic will be generated but with weaker
   character consistency. To enable: request Imagen 3 Capability access in
   Google Cloud console, or use Vertex AI with the right project permissions.

3. **`allow_all` requires allowlisting for child generation.** If the API key
   is restricted, the call fails with a specific `allow_all`-related error.
   Different error from the byte-encoding issues; easily distinguishable.

4. **PIL font baseline.** `textbbox`'s `y0` is the offset to cap-top, not
   the y-coordinate of cap-top. When centering text, draw at `(tx,
   center_y - y0)`. Forget this and your title overlaps the subtitle.

5. **`os.path.join` absolute path trap.** `os.path.join("/a/b", "/c.pdf")`
   returns `/c.pdf`, not `/a/b/c.pdf`. Always normalize the second arg with
   `os.path.basename` if it might be absolute.

6. **`qrcode.image.pil` is not auto-imported.** You must
   `import qrcode.image.pil` explicitly to register the PIL factory. Without
   it, `qrcode.image.pil.PilImage` raises `AttributeError`.

7. **Dynamic font scaling is asymmetric.** Only downscale. Scaling up
   produces blurry text and almost never looks better. Pattern:
   `if total_h > container_h: scale = container_h / total_h; apply if scale < 1`.

8. **Local dev environment has no `cv2`.** Production has
   `opencv-python-headless`; local dev on this machine does not (disk space
   too tight). If you need to smoke-test `app.services.ai_service` without
   hitting the real ML libs, stub `cv2`, `insightface`, and
   `google.generativeai` via `sys.modules` at the top of your test script.
   See the example smoke scripts that lived in the repo during development.

9. **Tier panel counts are 6 / 12 / 24, NOT linear with tier name.** Premium
   isn't "double basic" — it's 2x, but deluxe is 4x, not 3x. Reflected in
   `comic_styles.py` and in the way the layout file suffix maps
   (`basic → 2x3, premium → 3x4, deluxe → 4x6`). For now we only ship 2x3
   layouts, but the system is ready for tier-specific layouts.

10. **Disk on the dev machine is 100% full.** A 475G drive with no free
    space. Smoke testing that writes 1200x1600 PNGs and multi-page PDFs
    fills it fast. Before running smoke tests, clean `output/story_*.png`
    and any other generated images. The `output/comics/smoke_*.pdf` files
    from previous tests are safe to delete.
