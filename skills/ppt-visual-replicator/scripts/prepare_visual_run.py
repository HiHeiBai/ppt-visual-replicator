#!/usr/bin/env python3
"""Deprecated compatibility workflow; do not use for new direct-deck runs."""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
from pathlib import Path
from typing import Any

from pptx_inspect import InputError, inspect_pptx


class RunError(ValueError):
    pass


RENDER_TIMEOUT_SECONDS = 300


def parse_slide_selection(value: str) -> list[int]:
    selected: set[int] = set()
    for part in value.split(","):
        item = part.strip()
        if not item:
            continue
        if "-" in item:
            start_text, end_text = item.split("-", 1)
            try:
                start, end = int(start_text), int(end_text)
            except ValueError as exc:
                raise RunError(f"invalid slide range: {item}") from exc
            if start <= 0 or end < start:
                raise RunError(f"invalid slide range: {item}")
            selected.update(range(start, end + 1))
        else:
            try:
                number = int(item)
            except ValueError as exc:
                raise RunError(f"invalid slide number: {item}") from exc
            if number <= 0:
                raise RunError(f"invalid slide number: {item}")
            selected.add(number)
    if not selected:
        raise RunError("slide selection is empty")
    return sorted(selected)


def _write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _renderer_command(pptx: Path, output_dir: Path) -> dict[str, Any]:
    return {
        "input": str(pptx),
        "output_dir": str(output_dir),
        "commands": [
            ["soffice", "--headless", "--convert-to", "pdf", "--outdir", str(output_dir), str(pptx)],
            ["pdftoppm", "-png", "-r", "192", "<converted.pdf>", str(output_dir / "slide")],
        ],
    }


def _render_pptx(pptx: Path, output_dir: Path) -> None:
    soffice = shutil.which("soffice")
    pdftoppm = shutil.which("pdftoppm")
    if not soffice or not pdftoppm:
        missing = [name for name, value in (("soffice", soffice), ("pdftoppm", pdftoppm)) if not value]
        raise RunError(f"renderer command is unavailable: {', '.join(missing)}")
    output_dir.mkdir(parents=True, exist_ok=True)
    try:
        subprocess.run(
            [soffice, "--headless", "--convert-to", "pdf", "--outdir", str(output_dir), str(pptx)],
            check=True,
            capture_output=True,
            text=True,
            timeout=RENDER_TIMEOUT_SECONDS,
        )
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
        raise RunError(f"legacy PPTX-to-PDF rendering failed: {exc}") from exc
    pdf = output_dir / f"{pptx.stem}.pdf"
    if not pdf.is_file():
        raise RunError(f"renderer did not create PDF: {pdf}")
    try:
        subprocess.run(
            [pdftoppm, "-png", "-r", "192", str(pdf), str(output_dir / "slide")],
            check=True,
            capture_output=True,
            text=True,
            timeout=RENDER_TIMEOUT_SECONDS,
        )
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
        raise RunError(f"legacy PDF-to-PNG rendering failed: {exc}") from exc
    pages = sorted(
        output_dir.glob("slide-*.png"),
        key=lambda path: int(path.stem.rsplit("-", 1)[-1]),
    )
    for index, page in enumerate(pages, start=1):
        target = output_dir / f"page-{index:03d}.png"
        page.replace(target)
    pdf.unlink(missing_ok=True)


def prepare_visual_run(
    target: str | Path,
    references: list[str | Path],
    run_dir: str | Path,
    *,
    skip_render: bool = False,
    slide_numbers: list[int] | None = None,
) -> dict[str, Any]:
    if not references:
        raise RunError("at least one reference-style PPTX is required")
    destination = Path(run_dir).expanduser().resolve()
    if destination.exists():
        raise RunError(f"run directory already exists: {destination}")

    try:
        source_ledger = inspect_pptx(target)
        reference_ledgers = [inspect_pptx(path) for path in references]
    except InputError as exc:
        raise RunError(str(exc)) from exc

    source_slide_count = int(source_ledger["slide_count"])
    selected_slide_numbers = slide_numbers or list(range(1, source_slide_count + 1))
    missing_slides = sorted(set(selected_slide_numbers).difference(range(1, source_slide_count + 1)))
    if missing_slides:
        raise RunError(f"selected target slides do not exist: {missing_slides}")
    selected = set(selected_slide_numbers)
    source_ledger["source_slide_count"] = source_slide_count
    source_ledger["selected_slide_numbers"] = selected_slide_numbers
    source_ledger["slides"] = [
        slide for slide in source_ledger["slides"] if int(slide["slide_number"]) in selected
    ]
    source_ledger["slide_count"] = len(source_ledger["slides"])

    destination.mkdir(parents=True)
    for name in ("targets", "references", "prompts", "generated", "reconstruction"):
        (destination / name).mkdir()

    source_path = Path(source_ledger["path"])
    target_render_dir = destination / "targets"
    source_ledger["render_dir"] = "targets"
    renderer_commands = [_renderer_command(source_path, target_render_dir)]

    for index, ledger in enumerate(reference_ledgers, start=1):
        render_dir = destination / "references" / f"reference-{index:02d}"
        render_dir.mkdir()
        ledger["reference_index"] = index - 1
        ledger["render_dir"] = f"references/reference-{index:02d}"
        renderer_commands.append(_renderer_command(Path(ledger["path"]), render_dir))

    manifest = {
        "schema": "ppt_visual_run.v1",
        "status": "prepared",
        "run_dir": str(destination),
        "source_ledger": "source-ledger.json",
        "reference_ledger": "reference-ledger.json",
        "target_render_dir": "targets",
        "reference_render_dir": "references",
        "visual_plan": "visual-plan.json",
        "image_jobs": "image-jobs.json",
        "generated_dir": "generated",
        "reconstruction_dir": "reconstruction",
        "renderer_commands": renderer_commands,
        "rendered": not skip_render,
        "selected_slide_numbers": selected_slide_numbers,
    }
    _write_json(destination / "source-ledger.json", source_ledger)
    _write_json(destination / "reference-ledger.json", reference_ledgers)
    _write_json(destination / "run.json", manifest)

    if not skip_render:
        _render_pptx(source_path, target_render_dir)
        for ledger in reference_ledgers:
            _render_pptx(Path(ledger["path"]), destination / ledger["render_dir"])
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description="Prepare a reference-style PPT visual replication run.")
    parser.add_argument("--target", required=True)
    parser.add_argument("--reference", action="append", required=True)
    parser.add_argument("--run-dir", required=True)
    parser.add_argument("--skip-render", action="store_true")
    parser.add_argument("--slides", help="Target slides such as 1,3-5,9")
    args = parser.parse_args()
    manifest = prepare_visual_run(
        args.target,
        args.reference,
        args.run_dir,
        skip_render=args.skip_render,
        slide_numbers=parse_slide_selection(args.slides) if args.slides else None,
    )
    print(json.dumps(manifest, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
