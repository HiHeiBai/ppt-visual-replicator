# Page Reconstructor Prompt Template

Placeholders of the form `{{NAME}}` are filled by `scripts/build-page-worker-prompt.py`.

```text
Rebuild one page for image-to-editable-ppt.

Run dir: {{RUN_DIR}}
Page id: {{PAGE_ID}}
Page dir: {{PAGE_DIR}}
Source image: {{SOURCE_IMAGE}}
Original content image: {{ORIGINAL_SOURCE_IMAGE}}
Speed profile: {{SPEED_PROFILE}}
Page route: {{PAGE_ROUTE}}
Shared asset index: {{SHARED_ASSETS_INDEX}}
Canonical duplicate page dir: {{CANONICAL_PAGE_DIR}}

You own only this Page dir. Do not edit deck_manifest.json, page_jobs.json, notes_manifest.json, final outputs, the original input, or any other page directory.

MANDATORY FIRST ACTION — read `{{SKILL_ROOT}}/references/fast-worker-contract.md` before looking at the source. It is the complete operating contract for `fast` and `balanced` pages. For `strict`, also read these three full references before making any decision:
- {{SKILL_ROOT}}/references/page-decision-tree.md
- {{SKILL_ROOT}}/references/manifest-schema.md
- {{SKILL_ROOT}}/references/cli-helper.md

For `fast` and `balanced`, consult the relevant full reference only when the compact contract says to, a page is ambiguous, or `editppt page validate` fails. Do not repeat a full reference read for ordinary pages that already fit the compact contract.

Hard rules (reminders only; the details and rationale live in the references above):
1. Follow the declared speed profile. In `strict`, every non-text foreground visual object uses the asset-sheet workflow. In `balanced` or `fast`, first reuse the deck shared asset index; a self-contained screenshot, photo, chart image, or complex illustration may use `{{SKILL_ROOT}}/scripts/extract-page-region.py` and `source_type: profile-rasterized-region`. Main text and structural objects remain native. No profile permits a complete-slide raster background with editable text over it.
2. Execute the three steps in order: (1) background recognition and repair, (2) foreground asset separation, (3) native element reconstruction. Do not consume the text hints in your page dir before the step-1/2 decisions are recorded.
3. manifest.json is the authoritative build source for page validation and final deck assembly. Build page.pptx and preview.png from manifest.json with the deterministic runtime, never with separate page-local PowerPoint code that bypasses the manifest.
4. All box_px / points_px / polygon_px values are source.png pixels. Reuse page_request.json.slide and page_request.json.content_box unchanged — do not convert the page to 16:9 or recalculate the canvas; the runtime maps source-pixel coordinates into content_box. Positioned objects without coordinates are page failures.
5. validation.json must contain a top-level boolean `passed`. Deterministic validation passing never waives an object-source rule.

Image backend: before any image generation or image editing, use the `editppt image` backend specified by `page_request.json.image_backend`. In a network-restricted runtime, request approval before required `editppt image generate/edit` calls with this reason: the user requested an `image-to-editable-ppt` conversion, and the upload is limited to task-local prompts plus required page images, masks, and references for this page. If `editppt image` is unavailable, first follow the CLI error guidance and try `codex login` or `editppt config`; if it is still unavailable, stop the current page and write `validation.json` with `"passed": false`. Do not complete the page using approximate editable structure when required foreground asset separation cannot run. When you need parameter details for the image backend, input images, clean bases, or asset sheets, read `editppt image --help` and the relevant subcommand help.

Goal: rebuild the source page as object-level editable PowerPoint. Do not invent an object-source strategy outside `page-decision-tree.md`.

Use `{{ORIGINAL_SOURCE_IMAGE}}` as text/content authority when the prepared source is a generated redraw. Set `manifest.json.speed_profile` to `{{SPEED_PROFILE}}`. Read `{{SHARED_ASSETS_INDEX}}` when it exists; copy a selected matching asset into this page directory and preserve its provenance instead of generating it again. Do not edit the shared asset directory.

If `Canonical duplicate page dir` is not `none`, this page is an exact rendered-PNG duplicate. Wait until that canonical page has `validation.json` with top-level `passed: true`, reuse its manifest and page-local assets, update `page_id`, `run_id`, `source`, and profile fields from the current `page_request.json`, then rebuild and validate in this page directory. Do not run image generation or image editing for an exact duplicate.

If the page dir already contains artifacts (manifest.json, page.pptx, validation.json, assets, ...) from a previous failed attempt, treat them as untrusted: run the full decision process yourself and re-derive every artifact. Never flip a leftover validation.json to `passed: true` or return leftover outputs without having rebuilt and re-verified them — the previous attempt failed for a reason recorded in its validation.json; read it.

Work through the page in this order:
1. Build the page inventory (Pre-Decision Checklist in page-decision-tree.md).
2. Decide the background (page-decision-tree.md section 1) and record `background_strategy`.
3. Decide foreground asset sources (section 2). Reuse matching shared assets first. In strict mode, or for non-eligible objects, run page-local image jobs serially with `editppt image generate` or `editppt image edit`; do not use a batch interface. In fast/balanced mode, extract eligible self-contained regions with `extract-page-region.py`, keeping their main placement in `box_px` and recording `profile-rasterized-region` provenance with `region_reason`. Put remaining icons/foreground objects onto one sparse asset sheet when they fit. After each selected generated output, record and process it with `editppt image import` and `editppt image process-sheet`.
4. Rebuild native text, shapes, and tables. Fill `text_boxes` from measured text hints; if this fast run used `editppt prepare --no-text-hints`, run `editppt page hints {{PAGE_DIR}}` now, immediately before text reconstruction. Render formulas with `editppt formula render-latex`.
5. Write manifest.json following the field contracts in manifest-schema.md, including `speed_profile`, `text_inventory`, `visual_inventory`, `background_strategy`, `quality_checks`, and positioned `text_boxes`/`images`/`shapes`.
6. Build the artifacts with the deterministic runtime: `editppt page build {{PAGE_DIR}}` (writes page.pptx and preview.png from manifest.json), then `editppt page contact-sheet {{PAGE_DIR}}`, then `editppt page validate {{PAGE_DIR}}` — it runs the same manifest-contract checks `editppt run record` will run, so fix every reported issue here, inside the page.

The Page dir must contain when you return:
- manifest.json
- imagegen-jobs.json
- page.pptx
- preview.png
- split_assets_contact.png
- validation.json
- page_result.json

validation.json and page_result.json must follow the exact shapes defined in manifest-schema.md: validation.json carries the top-level boolean `passed` (not only a nested or renamed field), and page_result.json carries the minimal required key set.

Before returning, run the Final Self-Check in page-decision-tree.md once: compare preview.png and split_assets_contact.png to the source, confirm `editppt page validate {{PAGE_DIR}}` passes, confirm validation.json contains top-level `passed: true`, and confirm all required outputs exist. Page-local issues are fixed inside the current page by you before returning.

On failure — when a hard rule cannot be satisfied or a required tool is unavailable — stop and return a page failure: write validation.json with `"passed": false` and the concrete failure reason (what failed, the exact error, what the parent must fix), plus page_result.json referencing whatever artifacts exist (omit keys for artifacts that were never produced). Do not fabricate the remaining artifacts and do not build an approximate page to make validation pass; the parent agent will fix the root cause and dispatch or claim a fresh page execution.

Return only:
page_manifest=`<absolute path>`
page_pptx=`<absolute path>`
preview=`<absolute path>`
contact_sheet=`<absolute path>`
validation=`<absolute path>`
page_result=`<absolute path>`
```
