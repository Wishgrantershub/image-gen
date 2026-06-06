# ComicMe Landing Page + 5-Step Generator Modal

## Design direction

Since you've handed me the keys: I'll go **bold halftone pop-art** — think Roy Lichtenstein meets modern SaaS. High-contrast, comic-panel aesthetics applied to a real product page (not a kitschy theme).

- **Palette**: Ink black `#0A0A0A`, paper cream `#FFF8E7`, hero red `#FF2D55`, electric yellow `#FFD60A`, panel-shadow blue `#1E3A8A` accent.
- **Type**: `Bangers` / `Bowlby One` for display ("Turn anyone into a comic book hero…"), `Inter` for body. Onomatopoeia accents ("POW", "ZAP") used sparingly.
- **Texture**: SVG halftone dots, thick 3-4px ink borders on cards, hard offset shadows (8px 8px 0 black). No soft glassmorphism.
- **Motion**: panels fade-in with slight rotation, carousel auto-scrolls, modal steps slide horizontally.

Before building I'll generate **3 rendered design directions** for you to pick from (locked palette + comic motif, varied composition/density/hierarchy), then implement the winner.

## Landing page structure

Single route `/` with these sections:

1. **Sticky nav** — logo wordmark, "How it works", "Pricing", primary CTA "Make Your Comic".
2. **Hero** — H1 "Turn anyone into a comic book hero in 60 seconds.", subhead, primary CTA, secondary "See samples". Comic panel illustration on the right.
3. **Sample comics carousel** — 3 sample comics, horizontal scroll-snap, arrow controls + dots. Each sample shows a 6-panel mini-comic thumbnail with title + style tag. Generated via image gen.
4. **How it works** — 3 steps (Upload → Style → Get your comic) with comic-panel iconography.
5. **Pricing strip** — ₹99 / ₹299 / ₹499 cards mirroring modal tier names.
6. **Footer** — minimal: copyright, socials, terms.

## 5-step modal flow

Single `<Dialog>` with internal step state (1–5), progress dots at top, Back / Next controls.

```text
Step 1  Upload Photo      drag-drop zone (react-dropzone), preview thumb, replace button
Step 2  Pick Style        3 cards: Manga | Pixar | Superhero, each with preview image, selected = thick border + check
Step 3  Premise           textarea, 200-char counter, placeholder examples, validation
Step 4  Tier              3 pricing cards (₹99 / ₹299 / ₹499) with feature lists, selected = highlighted
Step 5  Generation        animated progress bar 0→100%, 6 empty panels fill in one-by-one (staggered reveal), then success screen with PDF download button + copyable share link
```

State held in a single `useState` object; "Next" disabled until step is valid. Step 5 simulates generation client-side (no backend in this scope) using `setTimeout`/`setInterval` to stagger panel reveals — placeholder panel images. PDF download is a mock link; share link is a generated UUID-style string with copy-to-clipboard.

## Files I'll add

```text
src/routes/index.tsx                    replace placeholder with landing
src/components/SiteNav.tsx
src/components/Hero.tsx
src/components/SampleCarousel.tsx
src/components/HowItWorks.tsx
src/components/PricingStrip.tsx
src/components/SiteFooter.tsx
src/components/comic-modal/ComicModal.tsx       container + step router
src/components/comic-modal/StepUpload.tsx
src/components/comic-modal/StepStyle.tsx
src/components/comic-modal/StepPremise.tsx
src/components/comic-modal/StepTier.tsx
src/components/comic-modal/StepGenerate.tsx
src/components/comic-modal/StepDone.tsx
src/components/comic-modal/Stepper.tsx
src/styles.css                          add comic palette tokens, halftone bg, ink-border utility, hard-shadow utility, Bangers/Inter font imports
src/assets/sample-*.jpg                 3 carousel samples + 3 style previews (generated)
```

## Technical notes

- Tailwind v4 tokens added to `@theme` in `src/styles.css`: `--color-ink`, `--color-paper`, `--color-hero`, `--color-zap`, `--color-panel-blue`. Custom `@utility ink-border` and `@utility hard-shadow`.
- `react-dropzone` for upload (already common, will `bun add`).
- Shadcn `Dialog`, `Button`, `Card`, `Textarea`, `RadioGroup`, `Progress` reused with comic variant overrides.
- No backend — fully frontend prototype as requested. Generation is simulated.
- SEO: title "ComicMe — Turn anyone into a comic book hero in 60 seconds", meta description, og tags, single H1.

## Flow

1. Generate 3 design directions (pop-art comic, locked palette, varied composition) and present them.
2. You pick one.
3. I generate sample images + style preview images.
4. Build landing + modal matching the chosen direction's composition exactly.
5. QA pass for slop (no duplicate CTAs, no generic icons, composition matches direction).
