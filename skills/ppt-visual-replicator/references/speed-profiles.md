# Speed Profiles

Use one profile for the complete deck. Record it in `deck-run.json`, every page `run.json`, and every reconstruction `manifest.json`.

## Balanced (default)

- Run whole-slide `imagegen` for covers and visually composed concept/figure pages.
- Skip whole-slide `imagegen` for screenshot-led tutorial pages and ordinary image-content pages. Rebuild those pages from `source-content.png` with shared deck chrome.
- Keep main titles, body text, numbers, cards, tables, arrows, and structural shapes native and editable.
- Preserve a self-contained software screenshot, photo, or complex illustration as one positioned image object when separating its internal objects adds no useful editability.
- Extract only the required region with `reconstruction/scripts/extract-page-region.py`; record provenance as `profile-rasterized-region` with a non-empty `region_reason`.
- Never use the complete source slide as a background with editable text over it.

## Fast

- Run whole-slide `imagegen` only for the cover or one representative style seed unless the user selects more pages.
- Rebuild remaining pages directly with the shared style kit.
- Apply the same native-text and no-full-slide-background rules as balanced mode.
- Prefer preserving screenshots, photos, charts, and complex illustrations as positioned image regions.
- For a multi-page deck with `--source-renderer auto`, use the one-pass LibreOffice/PDF source render. If it fails, record the failure and fall back to the direct Quick Look renderer. Inspect the first, midpoint, and last rendered source page before generation.
- Prepare reconstruction with `--max-concurrent-pages 3 --no-text-hints`; create each page's text hints immediately before its native-text stage. Dispatch workers in batches of at most three.

## Strict

- Run whole-slide `imagegen` for every unique page.
- Follow the full per-page asset-sheet separation contract in `reconstruction/references/page-decision-tree.md`.
- Do not use `profile-rasterized-region`.

## Exact Duplicate Pages

- Compare rendered `source-content.png` files by SHA-256 before generation.
- Generate and reconstruct the first matching page only.
- Reuse the canonical generated image and page assets for later exact duplicates. Update page ids and validate each duplicated page before recording it.
- Do not treat perceptually similar pages as exact duplicates.

## Shared Deck Assets

- Create `shared-assets/index.json` before page workers start.
- Separate recurring logos, mascots, planets, decorative marks, and repeated chrome once from a successful representative page.
- Record each shared asset's stable id, path, source page, source hash, and provenance.
- Page workers must reuse a matching shared asset before requesting another image-edit separation.
- Keep the shared directory read-only during page reconstruction. Copy a selected shared asset into the page directory when the manifest runtime requires page-local paths.

## Resume and Cache

- Use `prepare_direct_deck.py --resume` only with the same target hash, references, style brief, DPI, text-protection mode, and speed profile.
- The source-renderer selection is also part of the resume contract.
- Treat an existing non-empty `generated.png` as complete only when the run fingerprint matches.
- Never regenerate a ready canonical page or exact duplicate.
