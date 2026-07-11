# Page Matching

## Generic page families

Classify target and reference pages as one of:

- `cover`
- `toc`
- `section`
- `table`
- `chart_figure`
- `content`
- `conclusion`
- `ending`

Do not encode customer, medical, Style1, or Style2 names in matching logic.

## Matching order

1. Match the same page family.
2. Minimize the difference in table, picture, and graphic-frame counts.
3. Minimize text-character-count difference.
4. Prefer a similar relative position in the deck.
5. Break remaining ties by reference filename and slide number for reproducibility.

Use exactly one primary reference page by default. Apply explicit user overrides after validating that the referenced deck and page exist.

Stop when no same-family reference exists for `cover`, `table`, or `chart_figure`. When a reference deck has no explicit ending page, use its cover as the ending-page visual source and record a `cover_fallback` warning. For other families, record a `content` fallback as a warning rather than silently choosing an unrelated layout.
