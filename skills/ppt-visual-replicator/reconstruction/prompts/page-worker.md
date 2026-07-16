# Page Reconstructor Prompt Template

Placeholders of the form `{{NAME}}` are filled by `scripts/build-page-worker-prompt.py`.

```text
Rebuild one page for image-to-editable-ppt.

Run dir: {{RUN_DIR}}
Page id: {{PAGE_ID}}
Page dir: {{PAGE_DIR}}
Source image: {{SOURCE_IMAGE}}
Original content image: {{ORIGINAL_SOURCE_IMAGE}}
Native manifest seed: {{NATIVE_MANIFEST_SEED}}
Native source slide: {{NATIVE_SOURCE_SLIDE}}
Source title style sheet: {{TITLE_STYLE_SHEET}}
Explicit style contract: {{STYLE_CONTRACT}}
Page family: {{PAGE_FAMILY}}
Shared asset index: {{SHARED_ASSETS_INDEX}}

You own only this Page dir. Do not edit deck_manifest.json, page_jobs.json, notes_manifest.json, final outputs, the original input, or any other page directory.

FAST PATH — check `{{NATIVE_MANIFEST_SEED}}` first. If it exists, copy it to `manifest.json`, build a preview immediately, and use the generated PNG only to make necessary style/layout corrections. Reuse `{{NATIVE_SOURCE_SLIDE}}` and its extracted assets as the editable blueprint. Do not call `editppt image edit`, create an asset sheet, or reconstruct native text and basic geometry from pixels when the seed already contains those objects.

Read the three detailed references only when the native seed is absent, contains unsupported objects, or a build/validation error requires their contracts:
- {{SKILL_ROOT}}/references/page-decision-tree.md — the single source of truth for all object-source decisions: the three-step decision process, text-hints usage, the final self-check, and the fix-versus-warning split.
- {{SKILL_ROOT}}/references/manifest-schema.md — the field contracts for manifest.json, validation.json, page_result.json, and imagegen-jobs.json.
- {{SKILL_ROOT}}/references/cli-helper.md — editppt command syntax and examples.

Hard rules (reminders only; the details and rationale live in the references above):
1. Reuse the native manifest seed and deck shared asset index first. Only when neither contains a required non-text object may a self-contained screenshot/photo/chart/illustration use a `source-faithful-region`. Do not start an asset-sheet image call for decoration already present in the user-provided PPTX.
2. Execute the three steps in order: (1) background recognition and repair, (2) foreground asset separation, (3) native element reconstruction. Do not consume the text hints in your page dir before the step-1/2 decisions are recorded.
3. manifest.json is the authoritative build source for page validation and final deck assembly. Build page.pptx and preview.png from manifest.json with the deterministic runtime, never with separate page-local PowerPoint code that bypasses the manifest.
4. All box_px / points_px / polygon_px values are source.png pixels. Reuse page_request.json.slide and page_request.json.content_box unchanged — do not convert the page to 16:9 or recalculate the canvas; the runtime maps source-pixel coordinates into content_box. Positioned objects without coordinates are page failures.
5. validation.json must contain a top-level boolean `passed`. Deterministic validation passing never waives an object-source rule.
6. The prepared source image is the accepted `generated.png`: the generated redraw is the visual authority, while the original content image is the content authority. Do not use `editppt image generate` during reconstruction. `editppt image edit` is allowed only for source-faithful separation or removal of provisional text from the accepted generated redraw; never use it to redesign, beautify, or replace an object.

Image backend: editable reconstruction must not make another image-model call when a native seed exists. If an unsupported visual cannot be recovered from the native PPTX or shared assets, stop the page with `validation.json.passed=false` and a concrete reason instead of waiting on a second generation/edit request.

Goal: rebuild the source page as object-level editable PowerPoint. Do not invent an object-source strategy outside `page-decision-tree.md`.

Use `{{SOURCE_IMAGE}}` as the visual authority and `{{ORIGINAL_SOURCE_IMAGE}}` as text/content authority. Read `{{SHARED_ASSETS_INDEX}}` when it exists; copy a selected matching asset into this page directory and preserve its provenance instead of generating it again. Do not edit the shared asset directory.

If the page dir already contains artifacts (manifest.json, page.pptx, validation.json, assets, ...) from a previous failed attempt, treat them as untrusted: run the full decision process yourself and re-derive every artifact. Never flip a leftover validation.json to `passed: true` or return leftover outputs without having rebuilt and re-verified them — the previous attempt failed for a reason recorded in its validation.json; read it.

Work through the page in this order:
0. If `{{NATIVE_MANIFEST_SEED}}` exists, copy it to `manifest.json`, run `editppt page build {{PAGE_DIR}}`, and inspect the first preview before doing any manual inventory.
1. Build the page inventory only for objects missing from the native seed.
2. Decide the background (page-decision-tree.md section 1) and record `background_strategy`.
3. Reuse native extracted assets and shared assets. Do not create an asset sheet in the default path.
4. Rebuild native text, shapes, and tables (section 3). Fill `text_boxes` from the measured text hints per section 3.1; render formulas with `editppt formula render-latex` per section 3.2.

   Title typography is a hard style lock. Read `{{TITLE_STYLE_SHEET}}` and use the record for this source slide. If `{{STYLE_CONTRACT}}` exists and declares `title_system.{{PAGE_FAMILY}}`, that explicit user-selected title system overrides only the declared font/color/weight fields; otherwise preserve the source title font, color, size, bold/italic state, and title box placement exactly. Do not let imagegen, the default deck palette, or a fallback font choose title color or typography. Preserve a source declaration such as `微软雅黑`/`Microsoft YaHei` in the native text run; do not replace it with Noto merely for local rendering.
5. Write manifest.json following the field contracts in manifest-schema.md, including `text_inventory`, `visual_inventory`, `background_strategy`, `quality_checks`, and positioned `text_boxes`/`images`/`shapes`.
6. Build the artifacts with the deterministic runtime: `editppt page build {{PAGE_DIR}}` (writes page.pptx and preview.png from manifest.json), then `editppt page contact-sheet {{PAGE_DIR}}`. Next run the dual-reference visual gate against both the accepted generated redraw and the original content image:

   ```bash
   python3 "{{SKILL_ROOT}}/scripts/verify_page_visual.py" \
     --source "{{SOURCE_IMAGE}}" \
     --content-source "{{ORIGINAL_SOURCE_IMAGE}}" \
     --page-pptx "{{PAGE_DIR}}/page.pptx" \
     --out-dir "{{PAGE_DIR}}/visual-qa" \
     --native-seed \
     --accept-visual \
     --accept-content
   cp "{{PAGE_DIR}}/visual-qa/visual-gate.json" "{{PAGE_DIR}}/visual-gate.json"
   ```

   Inspect `visual-qa/side-by-side.png` and `visual-qa/difference.png` for generated-reference fidelity, then inspect `visual-qa/content-side-by-side.png` and `visual-qa/content-difference.png` for original-content retention before using either accept flag. A failed generated-reference metric, missing original content, changed data visual, title wrapping drift, or wrong text position is a current-page failure. Fix the manifest and rebuild; do not record the page. If retrying, use a new empty directory such as `visual-qa-retry-2`, then copy its `visual-gate.json` into `{{PAGE_DIR}}/visual-gate.json`. Only after the visual gate passes, run `editppt page validate {{PAGE_DIR}}` — it runs the same manifest-contract checks `editppt run record` will run, so fix every reported issue here, inside the page.

The Page dir must contain when you return:
- manifest.json
- imagegen-jobs.json
- page.pptx
- preview.png
- split_assets_contact.png
- validation.json
- page_result.json

validation.json and page_result.json must follow the exact shapes defined in manifest-schema.md: validation.json carries the top-level boolean `passed` (not only a nested or renamed field), and page_result.json carries the minimal required key set.

Before returning, run the Final Self-Check in page-decision-tree.md once: inspect both generated-reference and original-content comparison pairs, confirm `visual-gate.json` has `passed: true` with both checks accepted, compare preview.png and split_assets_contact.png to the source, confirm `editppt page validate {{PAGE_DIR}}` passes, confirm validation.json contains top-level `passed: true`, and confirm all required outputs exist. `editppt run record` rejects a direct-run page without a passing dual-reference gate. Page-local issues are fixed inside the current page by you before returning.

Time bound: the first `preview.png` must exist before manual refinement begins. Make at most two preview-correction iterations. If the page still cannot pass, write a concrete failed `validation.json` and return; never leave the page indefinitely in `dispatched` state.

On failure — when a hard rule cannot be satisfied or a required tool is unavailable — stop and return a page failure: write validation.json with `"passed": false` and the concrete failure reason (what failed, the exact error, what the parent must fix), plus page_result.json referencing whatever artifacts exist (omit keys for artifacts that were never produced). Do not fabricate the remaining artifacts and do not build an approximate page to make validation pass; the parent agent will fix the root cause and dispatch or claim a fresh page execution.

Return only:
page_manifest=`<absolute path>`
page_pptx=`<absolute path>`
preview=`<absolute path>`
contact_sheet=`<absolute path>`
validation=`<absolute path>`
page_result=`<absolute path>`
```
