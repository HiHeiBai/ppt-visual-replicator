# Image Prompt Contract

Use `editppt image edit` with two ordered image inputs:

1. Target slide image: edit target and content authority.
2. Reference slide image: visual-style authority only.

Generate the first target page in every active family as a calibration page. Review those pages before approving them. For every later page in the family, add a third ordered input:

3. Approved generated calibration page: strongest authority for the actual deck-level title position, margins, footer, palette, decorative density, and recurring chrome.

Every prompt must require:

- Preserve the target canvas ratio, content responsibilities, text regions, data relationships, chart meaning, and source-image meaning.
- Transfer the reference typography character, palette, spacing rhythm, visual hierarchy, decorative language, borders, and background treatment.
- Do not copy reference wording, facts, logos, page numbers, confidential codes, or study data.
- Do not add or remove target claims, numbers, charts, tables, citations, or images.
- Keep text legible, but treat generated text as provisional because exact text is restored during editable reconstruction.
- Return one complete slide image without mockup frames, perspective, hands, devices, or surrounding UI.

Record target, reference, prompt, output, model, size, quality, status, and SHA-256 values for every page.

Do not execute scale jobs until `calibration-approved.json` records the current output hash for every active family. If an approved calibration output changes, invalidate scale execution and require approval again.
