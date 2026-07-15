# PPT Visual Replicator

[简体中文](README.zh-CN.md)

Turn an existing PowerPoint deck into a visually renewed, genuinely editable `.pptx` — without changing what the deck says.

`PPTX → clean source pages → imagegen redraw → per-page review → editable PPTX`

This is a content-preserving reconstruction skill for Codex. It uses the original slide as the sole authority for copy, data, charts, citations, logos, and page order. Optional reference images contribute style only.

## What you receive

- A fresh, coherent visual treatment across the deck.
- Native editable PowerPoint text and structural objects in the final `.pptx`.
- Screenshots, photos, charts, and intricate illustrations retained as independent image regions only when breaking them apart would not make them more useful to edit.
- A page-by-page review trail, bound to source and generated-image hashes, plus delivery gates that reject unreviewed, changed, or screenshot-only output.

The output is not a screenshot pasted into PowerPoint with text over it.

## Built to protect content

The workflow separates content from style:

| Comes from the source deck | May come from a user-supplied style reference |
| --- | --- |
| Wording, numbers, tables, charts, citations, logos, and reading order | Palette, typography character, spacing, borders, shadows, and decoration |

For medical, financial, legal, scientific, or number-dense material, strict text protection keeps the native source text and critical values as the reconstruction authority.

## Install

```bash
npx skills add Moxi-Lab/ppt-visual-replicator \
  --skill ppt-visual-replicator --global --yes
```

Or copy `skills/ppt-visual-replicator` from a clone into `~/.codex/skills/`, then start a new Codex task so the skill catalog refreshes.

## Use it

Attach or point Codex to a `.pptx`, then ask:

```text
Use $ppt-visual-replicator to recreate this deck as an editable PPTX.
Preserve every source claim, number, chart, citation, logo, and page order.
```

You may also provide:

- A single slide number instead of a full deck.
- A concise style brief.
- One or more user-supplied reference-style PNGs.
- A request for strict text protection.

Do not use a reference deck or image as a source of facts, wording, charts, logos, or layouts.

## What happens during a run

1. Render the requested slides and validate the source PNGs.
2. Redraw each required page with built-in image generation.
3. Review each generated page immediately and save a hash-bound checkpoint.
4. Run the generation gate before reconstruction.
5. Rebuild the approved pages locally as editable PowerPoint objects.
6. Validate editability, then render the final deck for visual QA.

Each page has its own state and review evidence. If a run is interrupted, continue from the recorded checkpoint; do not regenerate pages that have already passed review.

## Local requirements

- Python 3.10+
- LibreOffice (`soffice` or `libreoffice`)
- Poppler (`pdftoppm`)
- A Codex environment with built-in image generation

macOS:

```bash
brew install --cask libreoffice
brew install poppler
```

Ubuntu/Debian:

```bash
sudo apt-get install libreoffice poppler-utils
```

The bundled `editppt` runtime is installed automatically when first required and verifies that it is using this skill's own source before reuse.

## Verify a development checkout

```bash
python3 -m unittest discover -s tests -v
python3 /path/to/skill-creator/scripts/quick_validate.py skills/ppt-visual-replicator
```

## License

[MIT](LICENSE)
