---
name: ppt-visual-replicator
description: "Recreate one selected PowerPoint slide or a complete deck as an editable PPTX without changing its content. Preserve a fully native editable source instead of redrawing it; otherwise use the fixed pipeline: clean original-page screenshot → built-in imagegen redraw → PNG → image-to-editable-ppt."
---

# PPT Visual Replicator

Use exactly this pipeline:

```text
clean original-page screenshot → built-in imagegen direct redraw → PNG → editable PPTX
```

This is a visual recreation workflow. The generated PNG is a visual reference, never the final delivery. The final PPTX must contain native editable text and structural objects; it must not be a full-slide screenshot with a text overlay.

Do not rewrite, summarize, translate, reorder, add, or remove target content.

## Inputs

Required:

- Target PPTX.

Optional:

- One target slide number. Omit it for the whole deck.
- One or more user-supplied reference PNGs, used only for visual style.
- A short style brief.
- Strict text protection for medical, financial, legal, scientific, or number-dense slides.

Do not ask for a style-contract JSON, shared assets, or worker count unless the user explicitly asks for one. They are implementation details, not normal inputs.

## Content rules

- The original rendered page is the only authority for content, layout responsibilities, charts, tables, data, citations, logos, and page order.
- References control only palette, typography character, spacing, borders, shadows, and decoration. They never contribute facts, charts, tables, logos, photos, icons, or layouts.
- For strict text protection, use the source ledger as the exact authority for every visible text run and critical number. Otherwise use the original rendered page as the authority, with the ledger as backup.
- Generated text is provisional. Restore editable text from the original source, never from imagegen output.
- Title typography is never inferred from imagegen. Use `title-styles.json` extracted from the source, unless the user explicitly selected a style contract with a `title_system`; then use that contract's declared title font/color/weight only.
- Keep a complete screenshot, photo, chart image, or complex illustration as an independent positioned image only when decomposing it adds no useful editability. Never rasterize the complete slide.

## Default workflow

Run each stage in order. Do not jump from `generated.png` to delivery.

### 0. Preserve an already-native source

Before rendering or invoking imagegen, inspect the target. This is a preservation check, not an alternate visual style: when every slide is already natively editable and the user did not ask for a restyle, rebuilding it is prohibited because it introduces visual drift.

```bash
python3 scripts/check_native_editability.py --target "target.pptx"
```

`prepare_direct_deck.py` runs this check automatically. If its `deck-run.json` status is `native-source-preserved`, stop the redraw workflow: the exact source has been copied to `reconstruction/final/origin_edited.pptx`. Open that output with macOS Quick Look and deliver it. Do not run imagegen, stage reconstruction inputs, or finalize a second time.

Use `--force-reconstruct` only when the user explicitly asks to restyle or otherwise rebuild an already-native source. A selected single slide is preserved as a one-slide native PPTX without entering imagegen.

### 1. Prepare a clean original-page PNG

Use the deck wrapper for both a selected page and a full deck. It gives every run the same review and delivery gates.

Selected slide:

```bash
python3 scripts/prepare_direct_deck.py \
  --target "target.pptx" \
  --target-slide 34 \
  --run-dir "output/slide-034" \
  --source-renderer quicklook
```

Full deck:

```bash
python3 scripts/prepare_direct_deck.py \
  --target "target.pptx" \
  --run-dir "output/deck" \
  --source-renderer quicklook
```

For medical, financial, legal, scientific, or number-dense material, add `--strict-text-protection`.

Add `--style-brief "..."` only when the user supplied a visual direction. Add a reference image only when it is genuinely user-supplied:

```bash
  --reference-image "reference.png" \
  --reference-user-supplied
```

The command writes these per-page inputs:

- `source-content.png` — the clean content source
- `direct-image-prompt.txt` — the redraw prompt
- `source-ledger.json` — native text and critical-token backup
- `generated.png` — the required destination for the selected imagegen result
- `title-styles.json` — source title font, color, size, weight, and placement authority for native reconstruction

The deck run also writes a static `generation-plan.json`; every target page has action `generate`.

Inspect the source PNG before generating. Stop if it is clipped, has missing glyphs, or does not match the requested slide.

### 2. Redraw with built-in imagegen

For every prepared page:

1. Call the built-in `image_gen` tool. The page's `source-content.png` is the first content/layout input; append only user-supplied reference-style PNGs.
2. Use the page's `direct-image-prompt.txt` as the prompt.
3. Inspect the result against the source: no missing content, no altered numbers, no invented data visual, no reference content leaking into the target, and no mockup frame or surrounding UI.
4. Copy the selected built-in imagegen output from `$CODEX_HOME/generated_images/...` to that page's exact `generated.png` path. A run-specific `generated.png` may be replaced when retrying the same page.
5. Retry only the failed page, and only for a visible layout/content/style error.

Do not use the imagegen CLI fallback, `editppt image edit`, an imagegen preview, or a prior generated page to create or replace the page-level `generated.png`. During editable reconstruction only, the vendored page worker may use `editppt image edit` only to separate existing visual objects or remove provisional text from the accepted `generated.png`; it must not redesign, beautify, regenerate, or substitute those objects.

After a page passes visual comparison, record one concise review:

```bash
python3 scripts/record_generation_review.py \
  --run-dir "output/deck" \
  --slide 1 \
  --accept \
  --review-note "Compared with the source: content structure and all data visuals retained; no reference content transferred."
```

`--accept` is the reviewer’s explicit confirmation that structure, content firewall, and style checks all passed. Do not accept a page that fails any of them.

After recording all required page reviews, run the direct-generation gate before reconstruction:

```bash
RUN="output/deck"  # Use the same path passed to --run-dir.
python3 scripts/validate_generation_delivery.py --run-dir "$RUN"
```

Do not continue to reconstruction while this gate reports an unreviewed page, changed PNG, changed source image, or missing review check.

### 3. Rebuild locally as editable PPTX

Stage the reviewed page PNGs and prepare one reconstruction run:

```bash
RUN="output/deck"
EDITPPT="$(python3 scripts/ensure_editppt_runtime.py --print-path)"

python3 scripts/stage_reconstruction_inputs.py --run-dir "$RUN"
"$EDITPPT" prepare "$RUN"/reconstruction-inputs/slide-*.png \
  --job-dir "$RUN/reconstruction" \
  --output-name origin_edited.pptx \
  --max-concurrent-pages 1

# For editable PPTX sources, seed native text, shapes, coordinates, and images.
# This is the default fast path and makes no additional image-model call.
python3 scripts/seed_native_reconstruction.py \
  --run-dir "$RUN" \
  --reconstruction-dir "$RUN/reconstruction"
```

Rebuild locally, one page at a time. The default workflow does not require subagents.

```bash
"$EDITPPT" run next "$RUN/reconstruction" --local --json
```

This command creates the selected page’s `worker-prompt.md` and prints the exact `prompt_file` and dispatch command. When `native-manifest-seed.json` exists, build it immediately and refine only the differences visible against the accepted `generated.png`; do not rebuild the page from pixels and do not call `editppt image edit`. The original `source-content.png` and source ledger remain the content authority.

Before `editppt page validate` or `run record`, render the rebuilt one-page PPTX with macOS Quick Look and run the required dual-reference visual gate. Compare the render to the accepted `generated.png` for palette, composition, chrome, cards, spacing, and decoration; compare it separately to the original `source-content.png` for content responsibilities, text regions, data visuals, citations, and page identity. Inspect both side-by-side and difference pairs, then accept only a passing `visual-gate.json`. The gate binds both reference hashes and the current page PPTX hash; either missing comparison is a hard failure.

Claim and record the page with the same `agent-id`:

```bash
"$EDITPPT" run dispatch "$RUN/reconstruction" \
  --page page_001 --agent-id main \
  --prompt-file "$RUN/reconstruction/pages/page_001/worker-prompt.md" \
  --local

# Complete the page instructions in worker-prompt.md, then:
"$EDITPPT" run record "$RUN/reconstruction" --page page_001 --agent-id main
```

Repeat `run next --local` → local rebuild → dual-reference Quick Look gate → `run record` for each remaining page. Do not dispatch a page before its prompt exists, and do not mark a failed visual or structural validation as recorded.

Fail fast: require a first `preview.png` before manual refinement, allow at most two correction iterations, and return a concrete failed `validation.json` instead of leaving a page indefinitely in `dispatched`. A stalled page is a failed run, not a reason to wait for hours.

### 4. Finalize and prove editability

Only after every page is recorded:

```bash
"$EDITPPT" run finalize "$RUN/reconstruction"

python3 scripts/validate_editable_delivery.py \
  --run-dir "$RUN" \
  --pptx "$RUN/reconstruction/final/origin_edited.pptx"
```

The editable-delivery gate must pass. A screenshot-only PPTX, an unfinished reconstruction run, or a final deck without editable source text is not an acceptable substitute.

### 5. Render the final PPTX for visual QA

```bash
python3 scripts/render_final_qa.py \
  --run-dir "$RUN" \
  --pptx "$RUN/reconstruction/final/origin_edited.pptx" \
  --out-dir "$RUN/final-render"
```

Inspect the selected slide for a one-page run. For a deck, inspect the first, midpoint, last, and every page flagged during reconstruction. Check clipping, text centering, page count/order, data retention, title/footer consistency, and accidental duplicate elements. This final check does not replace the required page-level dual-reference visual gate.

## Delivery

Deliver only:

```text
<run-dir>/reconstruction/final/origin_edited.pptx
```

State the slide range, whether strict text protection was used, supplied style references if any, final-render directory, and unresolved visual warnings. If the editable or final-render gate fails, report the run as incomplete rather than delivering generated images or a screenshot-based PPTX.
