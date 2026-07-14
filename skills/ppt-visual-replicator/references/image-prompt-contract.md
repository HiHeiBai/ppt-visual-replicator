# Image Prompt Contract

For calibration jobs, use `editppt image edit` with two ordered image inputs:

1. Target slide image: edit target and content authority.
2. Reference slide image: visual-style authority only.

Generate the first target page in every active family as a calibration page. Review those pages before approving them. For every later page in the family, use two ordered inputs:

1. Target slide image: edit target and content authority.
2. Approved generated calibration page: layout and visual-style authority for the layout skeleton, title position, margins, content containers, footer, palette, decorative density, and recurring chrome.

For scale jobs, map the target's logical content groups into the calibration layout skeleton. Do not preserve the target's original visual layout. Change the skeleton only when the target has a genuinely different number or type of logical groups, and preserve the same deck-level geometry when adapting it.

Do not send the original reference page again during scale generation. It already influenced the approved calibration page and can cause reference wording, charts, or study facts to leak into later target pages.

Every prompt must require:

- Preserve the target canvas ratio, content responsibilities, text regions, data relationships, chart meaning, and source-image meaning.
- Preserve target logos, page numbers, confidentiality notices, document codes, and every target footer item in the same semantic role and relative slide area. Restyle them when needed, but never remove or replace them.
- Keep every target element fully inside the canvas with safe margins and at least 3% inset from every canvas edge. Do not crop or clip labels, pills, logos, text, charts, tables, images, or footer items.
- Transfer the reference typography character, palette, spacing rhythm, visual hierarchy, decorative language, borders, and background treatment.
- Do not copy reference wording, facts, logos, page numbers, confidential codes, or study data.
- Reference-only brand marks (logos, wordmarks, sponsors, organization names, signatures, and watermarks) are forbidden output unless the identical mark existed in the target image; never fill an empty target area with reference branding or text.
- Do not add or remove target claims, numbers, charts, tables, citations, or images.
- Keep text legible, but treat generated text as provisional because exact text is restored during editable reconstruction.
- Return one complete slide image without mockup frames, perspective, hands, devices, or surrounding UI.

Record target, reference, prompt, output, model, size, quality, status, and SHA-256 values for every page.

For a one-page family, generate that page directly with the target and the locked reference; no calibration approval is required. Do not execute scale jobs until `calibration-approved.json` records the current output hash for every multi-page family. If an approved calibration output changes, invalidate scale execution and require approval again.
