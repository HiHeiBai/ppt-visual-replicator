#!/usr/bin/env python3
"""Render only the finalized PPTX for real-application visual QA."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any


class FinalRenderError(RuntimeError):
    pass


def render_final_pptx(
    pptx: str | Path,
    out_dir: str | Path,
    *,
    dpi: int = 120,
) -> dict[str, Any]:
    source = Path(pptx).expanduser().resolve()
    destination = Path(out_dir).expanduser().resolve()
    if not source.is_file() or source.suffix.lower() != ".pptx":
        raise FinalRenderError(f"final PPTX does not exist: {source}")
    if destination.exists():
        raise FinalRenderError(f"output directory already exists: {destination}")
    soffice = shutil.which("soffice") or shutil.which("libreoffice")
    pdftoppm = shutil.which("pdftoppm")
    if not soffice or not pdftoppm:
        missing = [name for name, value in (("soffice/libreoffice", soffice), ("pdftoppm", pdftoppm)) if not value]
        raise FinalRenderError(f"final-render dependency is unavailable: {', '.join(missing)}")

    with tempfile.TemporaryDirectory(prefix="ppt-final-render-") as temp_dir:
        temp = Path(temp_dir)
        conversion = subprocess.run(
            [soffice, "--headless", "--convert-to", "pdf", "--outdir", str(temp), str(source)],
            check=False,
            capture_output=True,
            text=True,
        )
        if conversion.returncode != 0:
            raise FinalRenderError(conversion.stderr.strip() or conversion.stdout.strip() or "PPTX-to-PDF conversion failed")
        pdfs = list(temp.glob("*.pdf"))
        if len(pdfs) != 1:
            raise FinalRenderError("PPTX-to-PDF conversion did not create exactly one PDF")
        destination.mkdir(parents=True)
        raster = subprocess.run(
            [pdftoppm, "-png", "-r", str(int(dpi)), str(pdfs[0]), str(destination / "slide")],
            check=False,
            capture_output=True,
            text=True,
        )
        if raster.returncode != 0:
            raise FinalRenderError(raster.stderr.strip() or raster.stdout.strip() or "PDF rasterization failed")

    slides = sorted(destination.glob("slide-*.png"), key=lambda path: int(path.stem.split("-")[-1]))
    if not slides:
        raise FinalRenderError("final rendering created no slide images")
    report = {
        "pptx": str(source),
        "output_dir": str(destination),
        "slide_count": len(slides),
        "slides": [path.name for path in slides],
    }
    (destination / "render-report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="Render only a finalized PPTX for visual QA.")
    parser.add_argument("--pptx", required=True)
    parser.add_argument("--out-dir", required=True)
    parser.add_argument("--dpi", type=int, default=120)
    args = parser.parse_args()
    print(json.dumps(render_final_pptx(args.pptx, args.out_dir, dpi=args.dpi), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
