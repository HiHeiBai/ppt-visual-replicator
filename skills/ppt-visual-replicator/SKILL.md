---
name: ppt-visual-replicator
description: Use when one selected PowerPoint slide or a complete PPTX deck must be redrawn and returned as an editable PPTX without rewriting target content. Accepts the target PPTX as the only required input, automatically renders target slides into PNG content sources, and supports optional supplied source PNG overrides, shared style-reference PNGs, or a style brief.
---

# PPT Visual Replicator

Convert the target PPTX into clean page PNGs, selectively redraw visual pages with built-in `imagegen`, then rebuild the planned inputs as editable PowerPoint with the bundled `editppt` runtime.

Do not rewrite, summarize, reorder, add, or remove target content.

## Inputs

Require only:

- Target PPTX.

Accept optionally:

- A target slide number for a one-page run. Omit it to process the complete deck.
- A clean source-page PNG override for a one-page run. Omit it to render the target slide automatically.
- Zero, one, or a few shared reference-style PNGs. Reuse the same reference set across the deck; never match reference count to target page count.
- Source slide numbers for reference images as metadata only.
- A short style brief. When neither references nor a brief are supplied, choose a restrained professional style appropriate to the content.
- Strict native-text protection for financial, medical, legal, scientific, or number-dense decks where every native text run and critical token must remain exact.
- A speed profile: `balanced` (default), `fast`, or `strict`.

Read `references/content-protection.md` before generation and `references/acceptance.md` before delivery. For a deck run, read `references/speed-profiles.md`. Before reconstruction, read the three files in `reconstruction/references/`. Read `references/chrome-normalization.md` only when the user asks to unify recurring page markers, tags, titles, or footers.

## Workflow

### 1. Lock one deck-level style mode

- **No reference page:** follow the style brief. If absent, choose a coherent professional style and continue.
- **One reference page:** use it as shared style authority for every target page.
- **A few reference pages:** extract their common palette, typography character, spacing rhythm, hierarchy, borders, and decorative language. Do not map them to target pages by order or count.

### 2. Prepare the target PPTX

For a complete deck, provide only the PPTX:

```bash
python3 scripts/prepare_direct_deck.py \
  --target "target.pptx" \
  --run-dir "output/direct-deck" \
  --speed-profile balanced
```

Add `--style-brief`, repeated `--reference-image`, or repeated `--reference-slide` only when supplied by the user.

Use `--resume` to reuse a matching existing run and completed generated pages. The command must reject resume when the target, references, style brief, DPI, text mode, or speed profile changed.

Add `--strict-text-protection` only when the user requests exact native-text protection or the content is high risk. Default to visual OCR for ordinary training, tutorial, marketing, and image-heavy decks.

For one selected page:

```bash
python3 scripts/prepare_direct_page.py \
  --target "target.pptx" --target-slide 34 \
  --run-dir "output/direct-page-034"
```

Use `--source-image source-page-034.png` only as an advanced override when a clean page PNG already exists.

Preparation must:

- Inspect slide count, slide size, and important object counts. Capture native text and critical tokens opportunistically as supplemental backup; do not make that extraction a blocking manual step in default mode.
- Render the target PPTX once at 192 DPI for a deck, or render the selected page for a one-page run.
- Validate PNG readability, page count, and aspect ratio before generation.
- Write `source-content.png`, `source-ledger.json`, `content-spec.json`, and `direct-image-prompt.txt` for every target page.
- Write `generation-plan.json`, detect exact duplicate source PNGs by SHA-256, and create `shared-assets/index.json` for every deck.

In default `visual-ocr` mode, treat the rendered PNG plus OCR/vision as content and layout authority; use automatically extracted native text only as supplemental backup when the renderer blurs or omits glyphs. In `strict-native` mode, treat the PPTX ledger as exact text and number authority. Rendering the target PPTX is allowed only to create the generation input; never use a full-slide source screenshot plus editable text overlay as the final editable reconstruction.

Inspect the rendered source pages before image generation. Stop if a page is visibly corrupted or materially clipped. Record missing glyphs or renderer-fidelity warnings; in strict mode, fix the renderer or rely on complete native text protection before continuing.

Use `prepare_direct_deck.py` only as a thin deck wrapper: render once, call the same direct-page preparation route for every page, then write the deterministic speed plan. Do not switch to legacy visual planning, calibration, or image-job builder routes.

### 3. Follow the generation plan

Read `generation-plan.json` and obey each page action:

- `generate`: send `source-content.png` first, then shared `reference-style*.png` files, use `direct-image-prompt.txt`, and save one complete 16:9 `generated.png`.
- `direct-rebuild`: skip whole-slide imagegen. Rebuild from `source-content.png` with the shared deck style kit.
- `reuse`: do not generate. Reuse the declared canonical slide.

Do not use `editppt image edit` for the whole-slide redraw. Inspect `generated.png` once. Retry only the direct imagegen call when content is missing, the layout is materially wrong, or the locked visual language is not followed.

For a deck without supplied references, generate one representative content page first and reuse that successful generated page as a shared style anchor for later pages. Add at most one or two successful early pages when different content structures need examples. Do not pair anchors page-by-page.

Before page reconstruction, populate `shared-assets/index.json` from the successful representative pages. Separate each recurring logo, mascot, planet, decorative mark, or repeated chrome element once. Page workers must reuse an exact matching shared asset before making a page-local image request.

### 4. Rebuild editable PowerPoint

During default reconstruction, read text from the original `source-content.png` with OCR/vision rather than trusting generated text. Use `source-ledger.json` as supplemental backup only. In strict mode, read the ledger and restore every required target text and critical number exactly.

For one page:

```bash
EDITPPT="$(python3 scripts/ensure_editppt_runtime.py --print-path)"
"$EDITPPT" prepare "output/direct-page-034/generated.png" \
  --job-dir "output/direct-page-034/reconstruction"
"$EDITPPT" run next "output/direct-page-034/reconstruction"
```

For a deck, stage the mixed generated/direct/reused inputs, then prepare them together in slide-number order:

```bash
EDITPPT="$(python3 scripts/ensure_editppt_runtime.py --print-path)"
python3 scripts/stage_reconstruction_inputs.py \
  --run-dir "output/direct-deck"
"$EDITPPT" prepare output/direct-deck/reconstruction-inputs/slide-*.png \
  --job-dir "output/direct-deck/reconstruction"
"$EDITPPT" run next "output/direct-deck/reconstruction"
```

Generate page-worker prompts with `reconstruction/scripts/build-page-worker-prompt.py`; it reads the speed profile, page route, original source image, duplicate canonical page, and shared-asset index from the parent direct run. Use the original source PNG as OCR/vision authority by default; promote the ledger to exact-content authority only in strict text-protection mode. Dispatch independent page workers for a multi-page run when the environment supports them; otherwise rebuild pages sequentially under the same worker contract. Use local `builtin-ink` hints by default; do not ask for an OCR token.

In `balanced` and `fast`, keep main text and structural objects editable, but preserve self-contained screenshots, photos, chart images, and complex illustrations as positioned `profile-rasterized-region` objects when decomposition adds no useful editability. Never use a complete source slide as a raster background with editable text over it. In `strict`, retain the complete per-page separation contract.

Reconstruct an exact duplicate canonical page once. For each declared duplicate, reuse the canonical manifest and page-local assets, update page/run/source fields, rebuild, and validate without another image call.

Build, contact-sheet, validate, and record every page. Finalize the reconstruction once after all pages are recorded:

```bash
"$EDITPPT" run finalize "output/direct-deck/reconstruction"
```

When the user explicitly asks for uniform recurring chrome, run `scripts/normalize_global_chrome.py` after page reconstruction. Use exact source labels or an explicit per-page label map; never guess labels from slide ranges or footer numbers. Rebuild and validate every affected page before finalization.

### 5. Run final real-render QA

Render only the finalized PPTX:

```bash
python3 scripts/render_final_qa.py \
  --pptx "output/direct-deck/reconstruction/final/origin_edited.pptx" \
  --out-dir "output/direct-deck/final-render"
```

Inspect every final slide individually when practical. At minimum inspect the first, midpoint, last, every chrome-label exception, and every page flagged during reconstruction. Confirm slide count, text centering, clipping, title/footer consistency, and absence of duplicate tags. Internal `preview.png` files are not final-render evidence.

## Delivery

Deliver only the final editable PPTX after page validation and final real-render QA. State the target pages, style mode, shared references if any, final-render directory, and unresolved visual warnings plainly.
