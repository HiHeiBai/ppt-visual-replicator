# Page Matching

## Generic page families

Classify target and reference pages as one of:

- `cover`
- `toc`
- `section`
- `table`
- `chart`
- `multi_image`
- `image_content`
- `content`
- `conclusion`
- `ending`

Do not encode customer, medical, Style1, or Style2 names in matching logic.

Use `image_content` for pages with one source image plus explanatory text, such as a paper screenshot, product image, or evidence excerpt. Do not group those pages with text-only `content` pages.

## Matching order

1. Treat the first supplied reference deck as the primary deck for the complete run.
2. Group its pages by page family.
3. Select one canonical family medoid that minimizes total table, picture, chart, and text-density differences to the other pages in that family.
4. Reuse the same canonical anchor for every target page in that family.
5. Break ties by slide number for reproducibility.

Do not select later reference decks automatically. Use them only with `--allow-fallback-decks` or an explicit override, and record the deck switch as a warning. Apply explicit overrides after validating that the referenced deck and page exist.

Stop when the primary deck has no `cover`, `table`, or `chart` anchor and fallback decks were not explicitly enabled. When it has no explicit ending page, reuse its cover anchor and record a `cover_fallback` warning. For other missing families, reuse the primary deck's `content` anchor with a warning.
