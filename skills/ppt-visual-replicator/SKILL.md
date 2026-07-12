---
name: ppt-visual-replicator
description: Use when a specific target PowerPoint slide must be redrawn in a specific reference slide's visual style and returned as an editable PPTX, without rewriting the target content.
---

# PPT Visual Replicator

Redraw one selected target slide from one selected reference slide, then rebuild it as editable PowerPoint. This is one self-contained Skill with a bundled `editppt` runtime.

Do not rewrite, summarize, reorder, add, or remove target content.

## Inputs

Require:

- Target PPTX and target slide number.
- Reference-style PPTX and reference slide number.

Read `references/content-protection.md` before generation and `references/acceptance.md` before delivery. Before reconstruction, read the three files in `reconstruction/references/`.

## Workflow

### 1. Prepare exactly two slides

```bash
python3 scripts/prepare_direct_page.py \
  --target "target.pptx" --target-slide 34 \
  --reference "reference.pptx" --reference-slide 39 \
  --run-dir "output/direct-page-034"
```

Inspect `target.png` and `reference.png`. Stop only if either image is visibly corrupted, missing glyphs, or materially clipped. Do not build a deck-wide plan, classify page families, or create calibration jobs.

### 2. Redraw directly

```bash
EDITPPT="$(python3 scripts/ensure_editppt_runtime.py --print-path)"
"$EDITPPT" image edit \
  --image "output/direct-page-034/target.png" \
  --image "output/direct-page-034/reference.png" \
  --prompt-file "output/direct-page-034/image-edit-prompt.txt" \
  --size 2560x1440 --quality high \
  --out "output/direct-page-034/generated.png"
```

Inspect `generated.png` once. It must retain target content while adopting the reference visual language. Retry only this image-edit command when it is visibly wrong.

### 3. Rebuild editable PPT

```bash
"$EDITPPT" prepare "output/direct-page-034/generated.png" \
  --job-dir "output/direct-page-034/reconstruction"
"$EDITPPT" run next "output/direct-page-034/reconstruction"
```

The one-page run returns `rebuild_page_locally`. Generate its prompt with `reconstruction/scripts/build-page-worker-prompt.py`, claim it with `run dispatch --local`, then follow that bundled page-worker contract. Use local `builtin-ink` hints by default; do not ask for an OCR token.

Before building the editable page, read the direct run's `source-ledger.json`; it is the text and critical-number authority when generated text is imperfect.

Build, contact-sheet, and validate the page. Record it, then finalize:

```bash
"$EDITPPT" run record "output/direct-page-034/reconstruction" --page page_001 --agent-id main
"$EDITPPT" run finalize "output/direct-page-034/reconstruction"
```

## Delivery

Deliver only the final editable PPTX after its page validation passes and its preview remains visually faithful to `generated.png`. State the target/reference slides and any unresolved visual warning plainly.
