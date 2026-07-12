#!/usr/bin/env python3
"""Prepare one target slide and one reference slide for direct image editing."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
from pathlib import Path
from typing import Any

from pptx_inspect import InputError, inspect_pptx


class DirectRunError(ValueError):
    pass


def _write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _direct_prompt(target_slide: int, reference_slide: int) -> str:
    return f"""Redraw one complete 16:9 presentation slide.

The first image is the target slide {target_slide} and is the edit target and content authority.
The second image is the reference style slide {reference_slide} and is visual-style authority only.

Preserve the target canvas ratio, content responsibilities, text regions, data relationships, chart meaning, table meaning, citations, and source-image meaning. Transfer the reference typography character, palette, spacing rhythm, visual hierarchy, decorative language, borders, and background treatment.

Do not copy reference wording, facts, logos, page numbers, confidential codes, or study data. Do not add, delete, summarize, translate, or rewrite target claims, numbers, charts, tables, citations, or images. Keep all target text legible, but treat generated text as provisional because exact source text will be restored during editable reconstruction.

Return one complete slide image only. Do not add a mockup frame, perspective, hands, devices, or surrounding UI.
"""


def _render_slide(pptx: Path, slide_number: int, output: Path) -> None:
    soffice = shutil.which("soffice") or shutil.which("libreoffice")
    pdftoppm = shutil.which("pdftoppm")
    if not soffice or not pdftoppm:
        missing = [
            name
            for name, value in (("soffice/libreoffice", soffice), ("pdftoppm", pdftoppm))
            if not value
        ]
        raise DirectRunError(f"renderer command is unavailable: {', '.join(missing)}")
    render_dir = output.parent / f".{output.stem}-render"
    render_dir.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [soffice, "--headless", "--convert-to", "pdf", "--outdir", str(render_dir), str(pptx)],
        check=True,
        capture_output=True,
        text=True,
    )
    pdfs = list(render_dir.glob("*.pdf"))
    if len(pdfs) != 1:
        raise DirectRunError(f"renderer did not create one PDF for {pptx.name}")
    prefix = render_dir / output.stem
    subprocess.run(
        [
            pdftoppm,
            "-png",
            "-r",
            "150",
            "-f",
            str(slide_number),
            "-l",
            str(slide_number),
            "-singlefile",
            str(pdfs[0]),
            str(prefix),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    rendered = prefix.with_suffix(".png")
    if not rendered.is_file() or not rendered.stat().st_size:
        raise DirectRunError(f"renderer did not create slide {slide_number} for {pptx.name}")
    output.parent.mkdir(parents=True, exist_ok=True)
    rendered.replace(output)


def _require_slide(ledger: dict[str, Any], slide_number: int, role: str) -> None:
    available = {int(slide["slide_number"]) for slide in ledger.get("slides", [])}
    if slide_number not in available:
        raise DirectRunError(f"{role} slide does not exist: {slide_number}")


def prepare_direct_page(
    target: str | Path,
    reference: str | Path,
    *,
    target_slide: int,
    reference_slide: int,
    run_dir: str | Path,
    skip_render: bool = False,
) -> dict[str, Any]:
    destination = Path(run_dir).expanduser().resolve()
    if destination.exists():
        raise DirectRunError(f"run directory already exists: {destination}")
    try:
        target_ledger = inspect_pptx(target)
        reference_ledger = inspect_pptx(reference)
    except InputError as exc:
        raise DirectRunError(str(exc)) from exc
    _require_slide(target_ledger, target_slide, "target")
    _require_slide(reference_ledger, reference_slide, "reference")
    target_slide_ledger = next(
        slide for slide in target_ledger["slides"] if int(slide["slide_number"]) == target_slide
    )

    destination.mkdir(parents=True)
    prompt = _direct_prompt(target_slide, reference_slide)
    manifest = {
        "schema": "ppt_visual_direct_run.v1",
        "target_pptx": target_ledger["path"],
        "reference_pptx": reference_ledger["path"],
        "target_slide": target_slide,
        "reference_slide": reference_slide,
        "target_image": "target.png",
        "reference_image": "reference.png",
        "source_ledger": "source-ledger.json",
        "prompt": "image-edit-prompt.txt",
        "generated_image": "generated.png",
        "reconstruction_dir": "reconstruction",
    }
    _write_json(
        destination / "source-ledger.json",
        {
            "source_pptx": target_ledger["path"],
            "target_slide": target_slide,
            "slide": target_slide_ledger,
        },
    )
    _write_json(destination / "run.json", manifest)
    (destination / "image-edit-prompt.txt").write_text(prompt, encoding="utf-8")
    if not skip_render:
        _render_slide(Path(target_ledger["path"]), target_slide, destination / "target.png")
        _render_slide(Path(reference_ledger["path"]), reference_slide, destination / "reference.png")
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description="Prepare one target and one reference page for direct visual replication.")
    parser.add_argument("--target", required=True)
    parser.add_argument("--target-slide", required=True, type=int)
    parser.add_argument("--reference", required=True)
    parser.add_argument("--reference-slide", required=True, type=int)
    parser.add_argument("--run-dir", required=True)
    parser.add_argument("--skip-render", action="store_true")
    args = parser.parse_args()
    manifest = prepare_direct_page(
        args.target,
        args.reference,
        target_slide=args.target_slide,
        reference_slide=args.reference_slide,
        run_dir=args.run_dir,
        skip_render=args.skip_render,
    )
    print(json.dumps(manifest, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
