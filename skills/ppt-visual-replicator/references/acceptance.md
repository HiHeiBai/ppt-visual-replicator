# Acceptance Rules

## Direct redraw

- The run declares either `visual-ocr` or `strict-native` text protection. Native text extraction is not a blocking prerequisite in default `visual-ocr` mode.
- `generation-plan.json` covers every target page exactly once and requires built-in imagegen for every page.
- Automatically rendered source pages match the requested target slide count and aspect ratio, or a supplied source-content PNG override is readable at the expected aspect ratio.
- The render report records the source PPTX, rendered slide numbers, dimensions, hashes, DPI, and renderer tools.
- Any supplied shared reference-style PNGs are readable.
- Every page has one recorded content input, zero or more recorded shared style inputs, one prompt, and one reviewed `generated.png` output.
- The generated slide retains target claims, numbers, charts, tables, citations, page markers, and document codes; it does not copy reference wording, facts, logos, or identifiers.
- With references, the generated slide visibly adopts their common palette, typography character, spacing, decorative language, and hierarchy. Without references, it follows the explicit style brief or the selected coherent default style.
- Reference images are deck-level samples. Their number is independent of the target slide count, and a single reference may be reused for the whole deck.
- The shared asset index records recurring visual assets once and page workers reuse them before requesting page-local separation.

## Editable PPT

- `editppt` page validation passes and the final PPTX opens.
- A deck run contains the same slide count and order as the requested target pages.
- Required text and critical numeric tokens from the target are present as editable objects where practical.
- In `visual-ocr` mode, editable text is recovered from the original source PNG with OCR/vision, not from generated text alone. In `strict-native` mode, every ledger-required text and critical token is validated exactly.
- For direct-redraw runs, each rebuilt `page.pptx` passes `verify_page_visual.py` against the original `source-content.png`, rendered with macOS Quick Look. The report records a reviewer acceptance, source/PPTX hashes, metrics, side-by-side image, and difference image. `run record` rejects a direct-run page without that gate.
- Title font family, color, weight, size, and placement come from `title-styles.json` unless a user-selected style contract explicitly declares a `title_system` override for that page role. A generic deck palette or imagegen output is never title authority.
- The editable preview remains visually faithful to the original source page as well as the generated visual reference; structural validation alone is not enough.
- Complex charts, paper screenshots, and scientific illustrations may remain independent image objects.
- Eligible self-contained screenshot, photo, chart-image, or complex-illustration regions may use `source-faithful-region` with a recorded reason. They never cover the complete slide behind editable text; other foreground visuals follow the asset-sheet separation contract.
- Text alignment and vertical anchoring use valid PowerPoint values; the finalized PPTX can be parsed and rendered by a real presentation renderer.

## Final real-render QA

- Render only the finalized PPTX after reconstruction; do not reintroduce source-PPT rendering before image generation.
- The real-render slide count matches the final PPTX slide count.
- Inspect the only page for a single-page run. For a deck, inspect the first, midpoint, last, every explicit chrome-label exception, and any page previously flagged.
- Page numbers are centered, top tags are not duplicated or clipped, long titles remain readable, and title/footer typography is visually consistent where the user requested it.
- An internal `preview.png` is not a substitute for final real-render evidence.

## Delivery

Return the final PPTX path, direct run directory, and final-render directory. Report warnings plainly; do not call a warning a pass.
