# PPT Visual Replicator Skill Design

- Date: 2026-07-11
- Status: approved for implementation
- Skill name: `ppt-visual-replicator`

## Goal

Build one independent Codex Skill that takes a target-content PPTX and one or more reference-style PPTX files, redraws every target slide through image-to-image generation, then reconstructs the generated slide images into an object-level editable PPTX.

The Skill changes visual treatment only. Content rewriting, slide re-architecture, evidence interpretation, and copy optimization belong to the separate content-rewrite Skill.

## Inputs and outputs

Required inputs:

- One target-content `.pptx`.
- One or more reference-style `.pptx` files.

Optional inputs:

- Target slide range.
- Explicit target-to-reference slide overrides.
- Output run directory.

Required outputs:

- Source ledger with slide text, critical numeric tokens, native-object counts, canvas size, and file hashes.
- Rendered target and reference pages.
- Visual plan mapping every target page to one primary reference page.
- One prompt and one provenance record per generated page.
- Generated page images.
- `editppt` reconstruction run.
- Final editable `.pptx` and validation report.

## Workflow

1. Inspect inputs without modifying them and reject Office lock files.
2. Extract the target deck into a source ledger. This ledger, not OCR or generated pixels, is the content truth source.
3. Render target and reference decks to page images.
4. Classify pages into a small generic family set: cover, table of contents, section, table, chart/figure, content, conclusion, and ending.
5. Map each target page to one primary reference page with the same family and the closest content signature. Allow explicit overrides.
6. Build a page-local image-edit prompt and command using the target page as the edit target and the selected reference page as the style reference.
7. Call `editppt image edit` serially. Preserve every input, reference, prompt, output, and hash in the run directory.
8. Reject pages with missing images, invalid dimensions, or incomplete provenance. Re-run only failed pages.
9. Pass the generated images to the installed `image-to-editable-ppt` / `editppt` workflow. Do not copy or fork that implementation.
10. Validate the reconstructed deck against the target source ledger. Slide count, critical numeric tokens, required visible text, and editable-object structure must pass.
11. Render the final PPTX and inspect every slide at full size before delivery.

## Architecture

The Skill is an orchestration layer with four deterministic helpers:

- `pptx_inspect.py`: read-only OOXML inspection using the Python standard library.
- `prepare_visual_run.py`: establish the run directory, source/reference ledgers, and renderer commands.
- `build_visual_plan.py`: classify pages and create deterministic target/reference mappings.
- `build_image_jobs.py`: create prompts, provenance records, and optional serial `editppt image edit` execution.
- `validate_visual_run.py`: check generated assets, source parity, final PPTX structure, and reconstruction reports.

The Skill delegates raster rendering to LibreOffice/Poppler-compatible tools and editable reconstruction to the installed `editppt` runtime.

## Run directory contract

```text
runs/<run-id>/
├── run.json
├── source-ledger.json
├── reference-ledger.json
├── visual-plan.json
├── targets/
├── references/
├── prompts/
├── generated/
├── image-jobs.json
├── reconstruction/
└── validation.json
```

All paths stored in manifests are relative to the run directory when possible. Original PPTX files remain read-only.

## Content protection

- Preserve slide order and count unless the user explicitly limits the slide range.
- Do not add, delete, summarize, or reinterpret visible content.
- Do not use OCR or generated image text as the final truth source.
- Preserve numeric tokens, percentages, sample sizes, dates, doses, HR/CI/P values, citations, and footers.
- Treat image generation as visual drafting. Reconcile reconstructed text against the source ledger.
- Fail a page when required source text cannot be matched reliably.

## Reference matching

Use only generic page families and content signatures. Do not embed Style1, Style2, medical, or customer-specific rules in code.

Default signature fields:

- Page family.
- Text character count.
- Picture count.
- Table count.
- Chart/graphic-frame count.
- Relative slide position.

Prefer one primary reference slide per target slide. Use multiple visual references only when the user explicitly requests it.

## Image generation contract

Each page job must record:

- Target slide image and SHA-256.
- Reference slide image and SHA-256.
- Prompt file and SHA-256.
- Output path and SHA-256 after generation.
- Model, size, quality, status, and error.

The prompt must instruct the image backend to preserve target content, chart meaning, composition responsibilities, and canvas ratio while transferring typography, palette, spacing, decorative language, and visual hierarchy from the reference.

## Reconstruction boundary

Use the installed `image-to-editable-ppt` Skill and `editppt` CLI as an external dependency:

- `editppt prepare` creates the reconstruction run.
- Multi-page reconstruction follows the page-worker dispatch, record, and finalize contract.
- Text, titles, tables, and simple shapes must be editable.
- Complex charts, paper screenshots, and scientific illustrations may remain independent images.
- A full-slide image with editable text overlaid is not an acceptable fallback.

## Validation

The MVP passes when:

- The Skill folder passes `quick_validate.py`.
- Unit tests cover OOXML inspection, page classification, mapping, image-job creation, and final validation.
- A four-page fixture covers cover, content, table/chart, and conclusion/ending families.
- Image jobs can be generated from a clean run without network calls.
- The existing completed 13-page reconstruction run passes the new structural validator.
- The final validator detects missing generated pages, missing critical numeric tokens, slide-count mismatch, and image-only PPT output.

## Non-goals

- No content rewriting.
- No web UI or desktop app.
- No new image model integration outside `editppt image`.
- No fork of `image-to-editable-ppt`.
- No inclusion of customer decks or multi-gigabyte historical outputs in the Skill package.
- No full 47-page paid image regeneration during MVP implementation; existing 47-page and 13-page artifacts are regression evidence.

