# Image Prompt Contract

Use the deprecated compatibility runner only when a historical run requires it. It uses two ordered image inputs:

1. Target slide image: edit target and content authority.
2. Immutable user-supplied reference slide image: visual-style authority only.

Use the original immutable reference again for every target page. Never feed a generated page, preview, reconstruction artifact, or prior-run output back into imagegen. A generated page is review evidence only; it is never a later style or layout input.

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

Record the user-reference provenance and SHA-256 hash for every page. Do not create calibration or scale jobs.
