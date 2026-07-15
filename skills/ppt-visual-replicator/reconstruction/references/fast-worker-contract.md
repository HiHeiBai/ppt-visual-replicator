# Fast / Balanced Page Contract

Use this short contract for ordinary `fast` and `balanced` reconstruction pages. It keeps the final deck editable; it does not allow a complete-slide screenshot with text layered on top.

## Before building

1. Read `page_request.json`, the original content image, the prepared source image, and the shared-asset index when present.
2. Record a concise `visual_inventory`, `background_strategy`, and the four required `quality_checks` in `manifest.json`.
3. Reuse a shared asset before creating any page-local asset. A duplicate page must reuse its canonical manifest/assets after the canonical validation passes.

## Object decisions

- Native PowerPoint objects: readable titles, body text, labels, numbers, tables, cards, axes, dividers, simple arrows, and ordinary structural shapes.
- Allowed raster regions: only a self-contained screenshot, photo, complex chart image, or complex illustration. Extract it with `extract-page-region.py`, record `source_type: profile-rasterized-region`, a positioned `box_px`, and a non-empty `region_reason`.
- Never use a whole slide, card, table, dashboard, or chart as a raster shortcut. Never hide text, use transparent/off-canvas text, or substitute icons with emoji/text symbols.
- For a complex background with foreground text, first create a clean base. Use native shapes for solid/regular backgrounds; use the image backend only for a genuinely complex, occluded background.

## Text and build

- All main readable text must be visible native text boxes. Use `text_hints.json`; if it is absent, run `editppt page hints <page-dir>` immediately before text reconstruction.
- Put every reconstructed text value in `text_inventory`; this is the editable-text validation record in visual-OCR mode.
- Keep the original source image as the authority for wording and layout, even when the prepared source is a generated redraw.
- Build and verify the page with `editppt page build`, `editppt page contact-sheet`, and `editppt page validate`.

## Required return

Return the seven required artifacts listed in the worker prompt. Fix any failed page validation locally. Read the full page decision tree, manifest schema, or CLI helper only when this contract cannot settle the object decision, a non-standard manifest field is needed, or validation reports an error.
