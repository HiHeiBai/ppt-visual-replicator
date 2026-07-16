#!/usr/bin/env python3
"""Render only the finalized PPTX for real-application visual QA."""

from __future__ import annotations

import argparse
import json
import shutil
import struct
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from pptx_inspect import InputError, inspect_pptx
from render_source_pages import _write_single_slide_pptx
from validate_editable_delivery import validate_editable_delivery


class FinalRenderError(RuntimeError):
    pass


def _png_size(path: Path) -> tuple[int, int]:
    header = path.read_bytes()[:24]
    if (
        len(header) < 24
        or header[:8] != b"\x89PNG\r\n\x1a\n"
        or header[12:16] != b"IHDR"
    ):
        raise FinalRenderError(f"final render did not create a readable PNG: {path}")
    return struct.unpack(">II", header[16:24])


def render_final_pptx(
    pptx: str | Path,
    out_dir: str | Path,
    *,
    dpi: int = 192,
    run_dir: str | Path | None = None,
) -> dict[str, Any]:
    source = Path(pptx).expanduser().resolve()
    destination = Path(out_dir).expanduser().resolve()
    if not source.is_file() or source.suffix.lower() != ".pptx":
        raise FinalRenderError(f"final PPTX does not exist: {source}")
    try:
        source_ledger = inspect_pptx(source)
    except InputError as exc:
        raise FinalRenderError(f"final PPTX is not inspectable: {exc}") from exc
    expected_aspect = float(source_ledger["slide_size"]["aspect_ratio"])
    if run_dir is not None:
        delivery_gate = validate_editable_delivery(run_dir, source)
        if delivery_gate.get("passed") is not True:
            details = "; ".join(delivery_gate.get("errors", []))
            raise FinalRenderError(
                "refusing final-render QA before the editable-delivery gate passes: " + details
            )
    if destination.exists():
        raise FinalRenderError(f"output directory already exists: {destination}")

    qlmanage = shutil.which("qlmanage")
    renderer = "quicklook" if qlmanage else "libreoffice"
    if qlmanage:
        destination.mkdir(parents=True)
        with tempfile.TemporaryDirectory(prefix="ppt-final-render-") as temp_dir:
            temp = Path(temp_dir)
            for slide_number in range(1, int(source_ledger["slide_count"]) + 1):
                slide_pptx = temp / f"slide-{slide_number}.pptx"
                rendered_dir = temp / f"rendered-{slide_number}"
                rendered_dir.mkdir()
                _write_single_slide_pptx(source, slide_pptx, slide_number)
                result = subprocess.run(
                    [
                        qlmanage,
                        "-t",
                        "-s",
                        "2560",
                        "-o",
                        str(rendered_dir),
                        str(slide_pptx),
                    ],
                    check=False,
                    capture_output=True,
                    text=True,
                )
                if result.returncode:
                    raise FinalRenderError(
                        result.stderr.strip()
                        or result.stdout.strip()
                        or "Quick Look render failed"
                    )
                images = sorted(rendered_dir.glob("*.png"))
                if len(images) != 1:
                    raise FinalRenderError(f"Quick Look did not render slide {slide_number}")
                shutil.copy2(images[0], destination / f"slide-{slide_number}.png")
    else:
        soffice = shutil.which("soffice") or shutil.which("libreoffice")
        pdftoppm = shutil.which("pdftoppm")
        if not soffice or not pdftoppm:
            missing = [
                name
                for name, value in (
                    ("soffice/libreoffice", soffice),
                    ("pdftoppm", pdftoppm),
                )
                if not value
            ]
            raise FinalRenderError(
                f"final-render dependency is unavailable: {', '.join(missing)}"
            )
        with tempfile.TemporaryDirectory(prefix="ppt-final-render-") as temp_dir:
            temp = Path(temp_dir)
            conversion = subprocess.run(
                [
                    soffice,
                    "--headless",
                    "--convert-to",
                    "pdf",
                    "--outdir",
                    str(temp),
                    str(source),
                ],
                check=False,
                capture_output=True,
                text=True,
            )
            if conversion.returncode != 0:
                raise FinalRenderError(
                    conversion.stderr.strip()
                    or conversion.stdout.strip()
                    or "PPTX-to-PDF conversion failed"
                )
            pdfs = list(temp.glob("*.pdf"))
            if len(pdfs) != 1:
                raise FinalRenderError(
                    "PPTX-to-PDF conversion did not create exactly one PDF"
                )
            destination.mkdir(parents=True)
            raster = subprocess.run(
                [
                    pdftoppm,
                    "-png",
                    "-r",
                    str(int(dpi)),
                    str(pdfs[0]),
                    str(destination / "slide"),
                ],
                check=False,
                capture_output=True,
                text=True,
            )
            if raster.returncode != 0:
                raise FinalRenderError(
                    raster.stderr.strip()
                    or raster.stdout.strip()
                    or "PDF rasterization failed"
                )

    slides = sorted(
        destination.glob("slide-*.png"),
        key=lambda path: int(path.stem.split("-")[-1]),
    )
    if not slides:
        raise FinalRenderError("final rendering created no slide images")
    rendered_sizes: dict[str, list[int]] = {}
    for slide in slides:
        width, height = _png_size(slide)
        if height <= 0 or abs((width / height) - expected_aspect) / expected_aspect > 0.01:
            raise FinalRenderError(
                f"final slide has the wrong aspect ratio: {slide.name} is {width}x{height}, "
                f"expected {expected_aspect:.4f}"
            )
        rendered_sizes[slide.name] = [width, height]
    report = {
        "pptx": str(source),
        "output_dir": str(destination),
        "slide_count": len(slides),
        "slides": [path.name for path in slides],
        "rendered_sizes_px": rendered_sizes,
        "expected_aspect_ratio": expected_aspect,
        "dpi": int(dpi),
        "renderer": renderer,
        "editable_delivery_gate": "passed" if run_dir is not None else "not-requested",
    }
    (destination / "render-report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return report


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Render only a finalized PPTX for visual QA."
    )
    parser.add_argument("--pptx", required=True)
    parser.add_argument("--out-dir", required=True)
    parser.add_argument("--dpi", type=int, default=192)
    parser.add_argument(
        "--run-dir",
        help=(
            "Direct visual-replicator run directory. When supplied, rejects "
            "screenshot-only or unfinished reconstructions."
        ),
    )
    args = parser.parse_args()
    print(
        json.dumps(
            render_final_pptx(
                args.pptx,
                args.out_dir,
                dpi=args.dpi,
                run_dir=args.run_dir,
            ),
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
