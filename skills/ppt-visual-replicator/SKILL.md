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
- A style-contract JSON file when a named design system, exact palette, or fixed cross-page tone is required. It locks palette roles, typography character, recurring decoration, and reference-content boundaries for the entire deck.
- Strict native-text protection for financial, medical, legal, scientific, or number-dense decks where every native text run and critical token must remain exact.
- A speed profile: `balanced` (default), `fast`, or `strict`.
- An explicit full-page-imagegen requirement. When supplied, every unique target page is redrawn as one complete imagegen slide; do not replace this with per-region generation or direct rebuild.

Read `references/content-protection.md` before generation and `references/acceptance.md` before delivery. For a deck run, read `references/speed-profiles.md`. Before reconstruction, read the three files in `reconstruction/references/`. Read `references/chrome-normalization.md` only when the user asks to unify recurring page markers, tags, titles, or footers.

## Workflow

### Hard delivery gate — never skip reconstruction

Whole-slide `imagegen` creates a visual source for reconstruction. It is **not** an editable PPTX delivery and must never be exported as a screenshot-only final deck.

- Do not call a deck final, hand it to the user, or run final-render QA until every target page has been rebuilt, validated, and recorded through `editppt`, then assembled with `editppt run finalize`.
- A PPTX containing one full-slide raster per page plus no native editable text/structure is a failed intermediate preview, even when it looks visually correct.
- Missing PaddleOCR credentials never authorizes this shortcut. Ask once whether the user wants to configure OCR; if they decline or do not respond, continue using built-in geometry hints plus the original native text ledger. If exact reconstruction cannot be completed, report the run as incomplete rather than exporting the generated images as a final PPTX.
- Use `scripts/validate_editable_delivery.py` as a mandatory hard gate. It rejects an unreviewed full-page imagegen run, unfinished `editppt` runs, a PPTX that did not come from `reconstruction/final`, missing editable source text, and image-only final slides.
- Presentation screenshot export helpers are permitted only for an explicitly requested preview. They are forbidden for this skill's final delivery.

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

Add `--style-brief`, repeated `--reference-image`, or repeated `--reference-slide` only when supplied by the user. Every image reference also requires `--reference-user-supplied`; generated pages, previews, prior-run outputs, and any derivative of them are forbidden as imagegen references.

When the requested design has a fixed named system or exact cross-page colors, add `--style-contract "style-contract.json"`. This contract is copied into the run and embedded in every page prompt; a reference slide is never enough to guarantee consistent tones by itself.

Use `--resume` to reuse a matching existing run and completed generated pages. The command must reject resume when the target, references, style contract/brief, DPI, text mode, or speed profile changed.

Add `--strict-text-protection` only when the user requests exact native-text protection or the content is high risk. Default to visual OCR for ordinary training, tutorial, marketing, and image-heavy decks.

When the user explicitly requires whole-page imagegen for all pages, add `--full-page-imagegen`. It overrides the speed profile's page routing while keeping that profile's reconstruction rules.

For one selected page:

```bash
python3 scripts/prepare_direct_page.py \
  --target "target.pptx" --target-slide 34 \
  --run-dir "output/direct-page-034"
```

Use `--source-image source-page-034.png` only as an advanced override when a clean page PNG already exists.

Preparation must:

- Inspect slide count, slide size, and important object counts. Capture native text and critical tokens opportunistically as supplemental backup; do not make that extraction a blocking manual step in default mode.
- Render the target PPTX directly to per-page PNGs through a native PPTX renderer when available (on macOS, use Quick Look by extracting each selected slide into a temporary one-slide PPTX). Do not route through LibreOffice/PDF when a direct renderer is available. Use the LibreOffice-to-PDF route only as a recorded fallback.
- Validate PNG readability, page count, and aspect ratio before generation.
- Write `source-content.png`, `source-ledger.json`, `content-spec.json`, and `direct-image-prompt.txt` for every target page.
- Write `generation-plan.json`, detect exact duplicate source PNGs by SHA-256, and create `shared-assets/index.json` for every deck.

In default `visual-ocr` mode, treat the rendered PNG plus OCR/vision as content and layout authority; use automatically extracted native text only as supplemental backup when the renderer blurs or omits glyphs. In `strict-native` mode, treat the PPTX ledger as exact text and number authority. Rendering the target PPTX is allowed only to create the generation input; never use a full-slide source screenshot plus editable text overlay as the final editable reconstruction.

Inspect the rendered source pages before image generation. Stop if a page is visibly corrupted or materially clipped. Record missing glyphs or renderer-fidelity warnings; in strict mode, fix the renderer or rely on complete native text protection before continuing.

Use `prepare_direct_deck.py` only as a thin deck wrapper: render once, call the same direct-page preparation route for every page, then write the deterministic speed plan. Do not switch to legacy visual planning, calibration, or image-job builder routes.

### 3. Follow the generation plan

Read `generation-plan.json` and obey each page action:

- `generate`: send `source-content.png` first, then only the immutable user-supplied `reference-style*.png` files, use `direct-image-prompt.txt`, and save one complete 16:9 `generated.png`.
- `direct-rebuild`: skip whole-slide imagegen. Rebuild from `source-content.png` with the shared deck style kit.
- `reuse`: do not generate. Reuse the declared canonical slide.

Do not use `editppt image edit` for the whole-slide redraw. Inspect `generated.png` once. Retry only the direct imagegen call when content is missing, the layout is materially wrong, or the locked visual language is not followed.

Treat the source page as the only authority for information-bearing visual objects. Shared references can supply palette, type character, spacing, borders, shadows, and decorative language only; they must never supply a chart, pie/donut, diagram, table, data panel, icon, photo, logo, or page layout. Before accepting a generated image, compare it with the source for invented information-bearing objects and reject it whenever one appears. A source slide with no chart objects must never acquire a pie/donut/bar/line chart, legend, axis, percentage diagram, or data panel during redraw.

When a style contract is present, validate each generated page against the same palette roles and page-type rules before it enters reconstruction. Do not let independent image calls select a different blue/cyan/gray family on each page; regenerate the outlier using the same locked contract.

Record that inspection before the image can enter editable reconstruction:

```bash
python3 scripts/record_generation_review.py \
  --run-dir "output/direct-deck" --slide 1 --accept \
  --source-structure-match \
  --no-invented-information-visuals \
  --no-reference-content-transfer \
  --style-contract-match \
  --review-note "Compared directly with source: no introduced chart or reference component; Style1 palette roles match."
```

Every `generate` page needs its own accepted `generation-review.json`. `scripts/stage_reconstruction_inputs.py` invokes `scripts/validate_generation_delivery.py` and rejects the whole deck if a page has no review, if the image changed after review, or if any of the four checks is missing. Never bypass this gate by calling `editppt prepare` on hand-staged images.

For a deck without supplied references, use the deck-level style contract and style brief for every page. Never feed `generated.png`, a preview, a reconstruction artifact, or any previous output back into imagegen as a style anchor. A generated page may be reviewed and reconstructed only; it is never a new generation input.

Before page reconstruction, populate `shared-assets/index.json` only from user-supplied source/design assets or accepted reconstruction extracts. Separate each recurring logo, mascot, planet, decorative mark, or repeated chrome element once. Reuse those assets during editable rebuild; they must never become a later imagegen input.

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

Then prove that the only candidate delivery is the finalized editable artifact:

```bash
python3 scripts/validate_editable_delivery.py \
  --run-dir "output/direct-deck" \
  --pptx "output/direct-deck/reconstruction/final/origin_edited.pptx"
```

This command is a hard gate. On failure, do not substitute a screenshot-style PPTX, do not call the generated PNGs a final deck, and do not continue to final-render QA.

When the user explicitly asks for uniform recurring chrome, run `scripts/normalize_global_chrome.py` after page reconstruction. Use exact source labels or an explicit per-page label map; never guess labels from slide ranges or footer numbers. Rebuild and validate every affected page before finalization.

### 5. Run final real-render QA

Render only the finalized PPTX:

```bash
python3 scripts/render_final_qa.py \
  --run-dir "output/direct-deck" \
  --pptx "output/direct-deck/reconstruction/final/origin_edited.pptx" \
  --out-dir "output/direct-deck/final-render"
```

Inspect every final slide individually when practical. At minimum inspect the first, midpoint, last, every chrome-label exception, and every page flagged during reconstruction. Confirm slide count, text centering, clipping, title/footer consistency, and absence of duplicate tags. Internal `preview.png` files are not final-render evidence.

## Delivery

Deliver only `reconstruction/final/origin_edited.pptx` after the editable-delivery gate, page validation, and final real-render QA all pass. State the target pages, style mode, shared references if any, final-render directory, and unresolved visual warnings plainly. Do not deliver a screenshot-only PPTX as a substitute.
