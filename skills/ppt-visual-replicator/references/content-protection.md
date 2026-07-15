# Content Protection

## Truth source

Use one declared text-protection mode for the complete run:

- `visual-ocr` (default): treat the original rendered source PNG plus OCR/vision as content truth. Use automatically extracted native PPTX text only as supplemental backup.
- `strict-native`: treat the target PPTX source ledger as exact text and critical-number authority. Use generated pixels and OCR only as visual aids.

## Source rendering boundary

- Render the target PPTX into page PNGs when the user supplies only the PPTX.
- Use rendered pages as imagegen content/layout inputs, direct-rebuild content authority, and visual comparison evidence.
- Validate rendered page count, aspect ratio, PNG readability, missing glyphs, and material clipping before generation.
- Do not use a rendered full-slide screenshot as the final editable page background with native text layered over it.
- In `fast` or `balanced`, a self-contained screenshot, photo, chart image, or complex illustration may remain a positioned profile-rasterized region; this exception never applies to the complete slide or main editable text.
- In strict mode, when the renderer and native PPTX disagree, preserve exact native PPTX text and critical numbers from the ledger and report visible renderer drift.

## Required preservation

- Preserve slide order and slide count unless the user limits the page range.
- Preserve every visible title, body block, label, citation, logo, page number, confidentiality notice, document code, footer, and registered native object.
- Preserve numbers, percentages, sample sizes, dates, doses, HR, CI, P values, and units exactly.
- Preserve charts, tables, paper screenshots, and source images unless the user explicitly authorizes removal.
- Preserve speaker notes when the reconstruction runtime supports them.

## Prohibited changes

- Do not rewrite, summarize, translate, expand, or reinterpret content.
- Do not import wording or facts from the reference deck.
- Do not let OCR replace exact native target text.
- Do not accept a full-slide screenshot plus editable text overlay as an editable reconstruction.

When content cannot be preserved reliably, fail the page and record the reason.
