---
name: ppt-visual-replicator
description: Use when a target-content PowerPoint must adopt a reference deck's visual style through image generation and return to an object-level editable PPTX without rewriting the content, including 复刻参考PPT风格, reference-style redesign, and image-to-editable-PowerPoint requests.
---

# PPT Visual Replicator

## Overview

Transfer visual style from a reference deck to a target-content deck through a content-locked image-first workflow, then call the installed `image-to-editable-ppt` / `editppt` runtime to rebuild editable slides.

Do not rewrite, summarize, reorder, add, or remove target content. Route content changes to a separate content-rewrite Skill.

## Required references

- Read `references/content-protection.md` before inspecting or generating pages.
- Read `references/page-matching.md` before selecting reference slides.
- Read `references/image-prompt-contract.md` before creating image-edit jobs.
- Read `references/acceptance.md` before reconstruction and delivery.

## Workflow

### 1. Preflight

Require one target-content PPTX and at least one reference-style PPTX. Reject Office lock files such as `.~*.pptx`. Preserve every input file.

Run:

```bash
editppt doctor
```

Stop if the CLI, image backend, renderer, or required conversion runtime is unavailable.

### 2. Prepare the visual run

Create a new run directory and inspect inputs:

```bash
python3 scripts/prepare_visual_run.py \
  --target "path/to/target.pptx" \
  --reference "path/to/reference.pptx" \
  --run-dir "path/to/run"
```

This writes source/reference ledgers, render directories, and `run.json`. Inspect at least one rendered target and reference page before paid generation. Stop on missing glyphs, substituted blank text, or clipped content. The source ledger is the content truth source; never replace it with OCR or generated text.

For a representative-page trial, add a selection such as `--slides "1,5,10,47"`. Rendering may still normalize the full source deck, but planning, generation, reconstruction, and validation remain limited to the selected pages.

### 3. Match target pages to reference pages

Build the page-family plan:

```bash
python3 scripts/build_visual_plan.py --run-dir "path/to/run"
```

Treat the first supplied reference as the primary reference deck. Reuse one canonical reference anchor for every target page in the same family. Do not select later reference decks automatically; enable fallback decks or add page overrides only when the user explicitly accepts the exception.

Review `visual-plan.json` before paid image generation. Stop if `style_lock` is missing, automatic pages mix reference decks, or one page family uses multiple automatic anchors.

### 4. Create and run image-edit jobs

Create prompts and provenance records without network calls:

```bash
python3 scripts/build_image_jobs.py --run-dir "path/to/run"
```

Generate only the first calibration page for each active page family:

```bash
python3 scripts/build_image_jobs.py \
  --run-dir "path/to/run" \
  --execute-phase calibration
```

Review every calibration page at full size. Approve only when its title placement, margins, footer, palette, decorative language, density, and recurring chrome can govern the rest of that family. Record the approval and immutable hashes:

```bash
python3 scripts/build_image_jobs.py \
  --run-dir "path/to/run" \
  --approve-calibration
```

This writes `calibration-approved.json`. Then generate the remaining pages:

```bash
python3 scripts/build_image_jobs.py \
  --run-dir "path/to/run" \
  --execute-phase scale
```

Calibration jobs must call `editppt image edit` with the target slide first and the locked family reference anchor second. Scale jobs must pass the target slide followed by the approved generated calibration page; do not resend the original reference page. Retry only failed pages.

### 5. Validate generated pages

Run:

```bash
python3 scripts/validate_visual_run.py --run-dir "path/to/run" --stage generated
```

Do not reconstruct while generated pages or provenance records are incomplete. Validation must reject mixed automatic reference decks, multiple automatic anchors in one family, unapproved scale jobs, and calibration images changed after approval.

### 6. Reconstruct editable slides

Use the installed `image-to-editable-ppt` Skill. Start the deterministic runtime with:

If no PaddleOCR token is configured, continue with the local `builtin-ink` text-hints backend without stopping or asking the user. This workflow-specific rule overrides the dependency Skill's optional token prompt. Treat the source ledger and generated slide as the content authority; OCR is only an optional geometry aid in this workflow.

```bash
editppt prepare "path/to/run/generated"/*.png \
  --job-dir "path/to/run/reconstruction"
editppt run next "path/to/run/reconstruction"
```

Follow the required page-worker dispatch, record, and retry rules from `image-to-editable-ppt`. Finalize only after every page is recorded:

```bash
editppt run finalize "path/to/run/reconstruction"
```

Do not copy or fork the reconstruction implementation into this Skill.

### 7. Validate and deliver

Validate the final editable deck against the original source ledger:

```bash
python3 scripts/validate_visual_run.py \
  --run-dir "path/to/run" \
  --stage final \
  --final-pptx "path/to/final.pptx" \
  --reconstruction-validation "path/to/reconstruction/final/validation.json"
```

Render and inspect every final slide at full size. Deliver only when `validation.json` has `passed: true`.

## Stop conditions

- Target or reference inputs are missing, invalid, or temporary lock files.
- Rendered target or reference pages contain missing glyphs, blank substituted text, or clipped source content.
- A target page has no credible reference-family match.
- `visual-plan.json` has no primary deck lock, contains mixed automatic reference decks, or assigns multiple automatic anchors to one page family.
- Scale jobs exist without `calibration-approved.json`, or an approved calibration hash no longer matches the generated calibration page.
- Generated pages change chart meaning, omit registered content, or contain unresolved text drift.
- Any page lacks its target, reference, prompt, output, or hash provenance.
- Reconstruction validation fails or produces an image-only deck.
- Required source text or critical numeric tokens cannot be reconciled.
