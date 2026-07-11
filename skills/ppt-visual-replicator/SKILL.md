---
name: ppt-visual-replicator
description: Redraw a target-content PowerPoint in the visual style of one or more reference-style PowerPoint decks, generate page images through image-to-image editing, and reconstruct them into an object-level editable PPTX. Use when the user asks to 复刻参考PPT风格, apply a reference deck's visual style, redesign slides through image generation, or convert the resulting visual pages back into editable PowerPoint without rewriting the content.
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

This writes source/reference ledgers, render directories, and `run.json`. The source ledger is the content truth source; never replace it with OCR or generated text.

For a representative-page trial, add a selection such as `--slides "1,5,10,47"`. Rendering may still normalize the full source deck, but planning, generation, reconstruction, and validation remain limited to the selected pages.

### 3. Match target pages to reference pages

Build the generic page-family plan:

```bash
python3 scripts/build_visual_plan.py --run-dir "path/to/run"
```

Use one primary reference slide per target slide unless the user explicitly requests multiple references. Review `visual-plan.json` before paid image generation.

### 4. Create and run image-edit jobs

Create prompts and provenance records without network calls:

```bash
python3 scripts/build_image_jobs.py --run-dir "path/to/run"
```

After reviewing the commands, execute serially:

```bash
python3 scripts/build_image_jobs.py --run-dir "path/to/run" --execute
```

Every job must call `editppt image edit` with the target slide first and the selected reference slide second. Retry only failed pages.

### 5. Validate generated pages

Run:

```bash
python3 scripts/validate_visual_run.py --run-dir "path/to/run" --stage generated
```

Do not reconstruct while generated pages or provenance records are incomplete.

### 6. Reconstruct editable slides

Use the installed `image-to-editable-ppt` Skill. Start the deterministic runtime with:

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
- A target page has no credible reference-family match.
- Generated pages change chart meaning, omit registered content, or contain unresolved text drift.
- Any page lacks its target, reference, prompt, output, or hash provenance.
- Reconstruction validation fails or produces an image-only deck.
- Required source text or critical numeric tokens cannot be reconciled.
