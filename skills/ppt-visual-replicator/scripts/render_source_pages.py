#!/usr/bin/env python3
"""Render target PPTX slides into validated PNG content-source pages."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import struct
import subprocess
import tempfile
from collections.abc import Callable
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET
from zipfile import ZIP_DEFLATED, ZipFile

from pptx_inspect import InputError, inspect_pptx


class SourceRenderError(RuntimeError):
    pass


P_NS = "http://schemas.openxmlformats.org/presentationml/2006/main"
NS = {"p": P_NS}


def _write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _png_size(path: Path) -> tuple[int, int]:
    header = path.read_bytes()[:24]
    if len(header) < 24 or header[:8] != b"\x89PNG\r\n\x1a\n" or header[12:16] != b"IHDR":
        raise SourceRenderError(f"renderer did not create a readable PNG: {path}")
    return struct.unpack(">II", header[16:24])


def _run(
    command: list[str],
    *,
    runner: Callable[..., subprocess.CompletedProcess[str]],
    timeout: int,
) -> None:
    try:
        runner(
            command,
            check=True,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except subprocess.CalledProcessError as exc:
        detail = (exc.stderr or exc.stdout or "").strip()
        raise SourceRenderError(detail or f"renderer command failed: {command[0]}") from exc
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise SourceRenderError(f"renderer command failed: {command[0]}: {exc}") from exc


def _write_single_slide_pptx(source: Path, destination: Path, slide_number: int) -> None:
    """Create a temporary one-slide package without rewriting slide assets.

    Quick Look produces one thumbnail per presentation. Retaining the selected
    slide relationship together with the original theme, masters, layouts and
    media lets macOS render that page directly from PPTX instead of asking
    LibreOffice to reinterpret the complete document.
    """

    with ZipFile(source) as archive:
        try:
            presentation = ET.fromstring(archive.read("ppt/presentation.xml"))
        except (KeyError, ET.ParseError) as exc:
            raise SourceRenderError("PPTX has an unreadable presentation.xml") from exc
        slide_list = presentation.find("p:sldIdLst", NS)
        if slide_list is None:
            raise SourceRenderError("PPTX has no slide relationship list")
        slide_ids = list(slide_list)
        if slide_number <= 0 or slide_number > len(slide_ids):
            raise SourceRenderError(f"slide {slide_number} is outside the presentation")
        selected = slide_ids[slide_number - 1]
        for slide_id in slide_ids:
            slide_list.remove(slide_id)
        slide_list.append(selected)

        with ZipFile(destination, "w", compression=ZIP_DEFLATED) as output:
            for item in archive.infolist():
                payload = (
                    ET.tostring(presentation, encoding="utf-8", xml_declaration=True)
                    if item.filename == "ppt/presentation.xml"
                    else archive.read(item.filename)
                )
                output.writestr(item, payload)


def _render_with_quicklook(
    source: Path,
    work: Path,
    *,
    slide_number: int,
    qlmanage: str,
    runner: Callable[..., subprocess.CompletedProcess[str]],
    timeout: int,
) -> Path:
    """Directly render one PPTX slide to PNG through the native macOS preview stack."""

    slide_pptx = work / f"source-slide-{slide_number:03d}.pptx"
    ql_output = work / f"quicklook-{slide_number:03d}"
    ql_output.mkdir()
    _write_single_slide_pptx(source, slide_pptx, slide_number)
    _run(
        [str(qlmanage), "-t", "-s", "2560", "-o", str(ql_output), str(slide_pptx)],
        runner=runner,
        timeout=timeout,
    )
    rendered = sorted(ql_output.glob("*.png"))
    if len(rendered) != 1:
        raise SourceRenderError(
            f"Quick Look did not create exactly one PNG for slide {slide_number}"
        )
    return rendered[0]


def _render_with_libreoffice(
    source: Path,
    work: Path,
    *,
    start: int,
    end: int,
    dpi: int,
    soffice: str,
    pdftoppm: str,
    runner: Callable[..., subprocess.CompletedProcess[str]],
    timeout: int,
) -> list[Path]:
    """Compatibility fallback for systems without a direct native PPTX preview."""

    office_profile = work / "office-profile"
    office_profile.mkdir()
    _run(
        [
            str(soffice),
            f"-env:UserInstallation={office_profile.resolve().as_uri()}",
            "--headless",
            "--convert-to",
            "pdf",
            "--outdir",
            str(work),
            str(source),
        ],
        runner=runner,
        timeout=timeout,
    )
    pdfs = [path for path in work.glob("*.pdf") if path.is_file() and path.stat().st_size]
    if len(pdfs) != 1:
        names = ", ".join(path.name for path in pdfs) or "none"
        raise SourceRenderError(
            f"PPTX conversion expected exactly one PDF but found {len(pdfs)}: {names}"
        )
    prefix = work / "slide"
    _run(
        [
            str(pdftoppm),
            "-png",
            "-r",
            str(dpi),
            "-f",
            str(start),
            "-l",
            str(end),
            str(pdfs[0]),
            str(prefix),
        ],
        runner=runner,
        timeout=timeout,
    )
    rendered = sorted(
        work.glob("slide-*.png"),
        key=lambda path: int(path.stem.rsplit("-", 1)[-1]),
    )
    if len(rendered) != end - start + 1:
        raise SourceRenderError(
            f"source render page count mismatch: expected {end - start + 1}, got {len(rendered)}"
        )
    return rendered


def render_pptx_to_pngs(
    pptx: str | Path,
    out_dir: str | Path,
    *,
    dpi: int = 192,
    first_slide: int | None = None,
    last_slide: int | None = None,
    ledger: dict[str, Any] | None = None,
    runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
    tool_lookup: Callable[[str], str | None] = shutil.which,
    timeout: int = 300,
    renderer: str = "auto",
) -> dict[str, Any]:
    source = Path(pptx).expanduser().resolve()
    destination = Path(out_dir).expanduser().resolve()
    if destination.exists():
        raise SourceRenderError(f"source render directory already exists: {destination}")
    if dpi <= 0:
        raise SourceRenderError("render DPI must be positive")
    try:
        source_ledger = ledger or inspect_pptx(source)
    except InputError as exc:
        raise SourceRenderError(str(exc)) from exc

    slide_count = int(source_ledger["slide_count"])
    start = first_slide or 1
    end = last_slide or slide_count
    if start <= 0 or end < start or end > slide_count:
        raise SourceRenderError(
            f"render slide range does not exist: {start}-{end}; deck has {slide_count} slides"
        )

    if renderer not in {"auto", "quicklook", "libreoffice"}:
        raise SourceRenderError("renderer must be auto, quicklook, or libreoffice")
    qlmanage = tool_lookup("qlmanage")
    soffice = tool_lookup("soffice") or tool_lookup("libreoffice")
    pdftoppm = tool_lookup("pdftoppm")
    use_quicklook = renderer == "quicklook" or (renderer == "auto" and bool(qlmanage))
    if use_quicklook and not qlmanage:
        raise SourceRenderError("direct PPTX-to-PNG rendering requires qlmanage on this machine")
    if not use_quicklook and (not soffice or not pdftoppm):
        raise SourceRenderError(
            "source render dependency is unavailable: soffice/libreoffice and pdftoppm are required"
        )

    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="ppt-source-render-", dir=destination.parent) as temp_dir:
        work = Path(temp_dir)
        if use_quicklook:
            rendered = [
                _render_with_quicklook(
                    source,
                    work,
                    slide_number=slide_number,
                    qlmanage=str(qlmanage),
                    runner=runner,
                    timeout=timeout,
                )
                for slide_number in range(start, end + 1)
            ]
            renderer_report = {
                "engine": "quicklook",
                "mode": "direct-pptx-to-png",
                "command": Path(str(qlmanage)).name,
            }
        else:
            rendered = _render_with_libreoffice(
                source,
                work,
                start=start,
                end=end,
                dpi=dpi,
                soffice=str(soffice),
                pdftoppm=str(pdftoppm),
                runner=runner,
                timeout=timeout,
            )
            renderer_report = {
                "engine": "libreoffice",
                "mode": "pptx-to-pdf-to-png-fallback",
                "office": Path(str(soffice)).name,
                "rasterizer": Path(str(pdftoppm)).name,
            }

        destination.mkdir()
        pages: list[dict[str, Any]] = []
        expected_aspect = float(source_ledger["slide_size"]["aspect_ratio"])
        try:
            for slide_number, rendered_page in zip(range(start, end + 1), rendered):
                page = destination / f"slide-{slide_number:03d}.png"
                shutil.copy2(rendered_page, page)
                width, height = _png_size(page)
                image_aspect = width / height
                if abs(image_aspect - expected_aspect) / expected_aspect > 0.01:
                    raise SourceRenderError(
                        f"rendered slide {slide_number} has the wrong aspect ratio: "
                        f"{width}x{height}"
                    )
                pages.append(
                    {
                        "slide_number": slide_number,
                        "path": str(page),
                        "width_px": width,
                        "height_px": height,
                        "sha256": _sha256(page),
                    }
                )
        except Exception:
            shutil.rmtree(destination, ignore_errors=True)
            raise

    report = {
        "schema": "ppt_visual_source_render.v1",
        "source_pptx": str(source),
        "source_sha256": source_ledger["sha256"],
        "deck_slide_count": slide_count,
        "rendered_slide_count": len(pages),
        "first_slide": start,
        "last_slide": end,
        "dpi": dpi,
        "renderer": renderer_report,
        "pages": pages,
    }
    _write_json(destination / "render-report.json", report)
    return report


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Render target PPTX slides into validated PNG content-source pages."
    )
    parser.add_argument("--target", required=True)
    parser.add_argument("--out-dir", required=True)
    parser.add_argument("--dpi", type=int, default=192)
    parser.add_argument("--first-slide", type=int)
    parser.add_argument("--last-slide", type=int)
    parser.add_argument("--renderer", choices=("auto", "quicklook", "libreoffice"), default="auto")
    args = parser.parse_args()
    report = render_pptx_to_pngs(
        args.target,
        args.out_dir,
        dpi=args.dpi,
        first_slide=args.first_slide,
        last_slide=args.last_slide,
        renderer=args.renderer,
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
