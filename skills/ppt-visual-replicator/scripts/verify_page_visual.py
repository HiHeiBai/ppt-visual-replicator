#!/usr/bin/env python3
"""Render a rebuilt one-slide PPTX with Quick Look and reject visual drift."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from PIL import Image, ImageChops, ImageEnhance, ImageFilter, ImageOps, UnidentifiedImageError


class VisualGateError(RuntimeError):
    pass


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _quicklook_render(pptx: Path, out_dir: Path) -> Path:
    qlmanage = shutil.which("qlmanage")
    if not qlmanage:
        raise VisualGateError("Quick Look is required for page visual QA but qlmanage is unavailable")
    rendered_dir = out_dir / "quicklook"
    rendered_dir.mkdir(parents=True, exist_ok=True)
    result = subprocess.run(
        [qlmanage, "-t", "-s", "2560", "-o", str(rendered_dir), str(pptx)],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode:
        raise VisualGateError((result.stderr or result.stdout or "Quick Look render failed").strip())
    images = sorted(rendered_dir.glob("*.png"))
    if len(images) != 1:
        raise VisualGateError("Quick Look did not create exactly one page PNG")
    destination = out_dir / "rendered.png"
    shutil.copy2(images[0], destination)
    return destination


def _load_normalized(path: Path, size: tuple[int, int]) -> Image.Image:
    try:
        with Image.open(path) as image:
            return ImageOps.fit(image.convert("RGB"), size, method=Image.Resampling.LANCZOS)
    except (OSError, UnidentifiedImageError) as exc:
        raise VisualGateError(f"cannot read PNG: {path}") from exc


def _metrics(source: Image.Image, rendered: Image.Image) -> dict[str, float]:
    source_small = source.resize((128, 72), Image.Resampling.LANCZOS)
    rendered_small = rendered.resize((128, 72), Image.Resampling.LANCZOS)
    pixel_values = zip(source_small.get_flattened_data(), rendered_small.get_flattened_data())
    pixel_distance = sum(
        abs(left_channel - right_channel)
        for left, right in pixel_values
        for left_channel, right_channel in zip(left, right)
    ) / (128 * 72 * 3)

    source_structure = source.convert("L").resize((64, 36), Image.Resampling.LANCZOS).filter(ImageFilter.GaussianBlur(1))
    rendered_structure = rendered.convert("L").resize((64, 36), Image.Resampling.LANCZOS).filter(ImageFilter.GaussianBlur(1))
    structure_distance = sum(
        abs(left - right)
        for left, right in zip(source_structure.get_flattened_data(), rendered_structure.get_flattened_data())
    ) / (64 * 36)

    source_ink = source.convert("L").resize((320, 180), Image.Resampling.LANCZOS)
    rendered_ink = rendered.convert("L").resize((320, 180), Image.Resampling.LANCZOS)
    def projection(image: Image.Image) -> tuple[list[int], list[int], int]:
        values = list(image.get_flattened_data())
        ink = [value < 200 for value in values]
        rows = [sum(ink[top * 320 : (top + 1) * 320]) for top in range(180)]
        columns = [sum(ink[left + top * 320] for top in range(180)) for left in range(320)]
        return rows, columns, sum(ink)
    source_rows, source_columns, source_count = projection(source_ink)
    rendered_rows, rendered_columns, rendered_count = projection(rendered_ink)
    denominator = max(1, source_count + rendered_count)
    ink_projection_distance = max(
        sum(abs(left - right) for left, right in zip(source_rows, rendered_rows)) / denominator,
        sum(abs(left - right) for left, right in zip(source_columns, rendered_columns)) / denominator,
    )
    title_source = source.crop((0, 0, source.width, int(source.height * 0.32)))
    title_rendered = rendered.crop((0, 0, rendered.width, int(rendered.height * 0.32)))
    title_pixels = zip(
        title_source.resize((160, 51), Image.Resampling.LANCZOS).get_flattened_data(),
        title_rendered.resize((160, 51), Image.Resampling.LANCZOS).get_flattened_data(),
    )
    title_pixel_distance = sum(
        abs(left_channel - right_channel)
        for left, right in title_pixels
        for left_channel, right_channel in zip(left, right)
    ) / (160 * 51 * 3)
    title_source_structure = title_source.convert("L").resize((80, 26), Image.Resampling.LANCZOS).filter(ImageFilter.GaussianBlur(1))
    title_rendered_structure = title_rendered.convert("L").resize((80, 26), Image.Resampling.LANCZOS).filter(ImageFilter.GaussianBlur(1))
    title_structure_distance = sum(
        abs(left - right)
        for left, right in zip(title_source_structure.get_flattened_data(), title_rendered_structure.get_flattened_data())
    ) / (80 * 26)
    return {
        "pixel_mean_distance": round(pixel_distance, 3),
        "structure_distance": round(structure_distance, 3),
        "ink_projection_distance": round(ink_projection_distance, 4),
        "title_pixel_mean_distance": round(title_pixel_distance, 3),
        "title_structure_distance": round(title_structure_distance, 3),
    }


def verify_page_visual(
    source_path: str | Path,
    *,
    page_pptx: str | Path | None,
    rendered_image: str | Path | None,
    out_dir: str | Path,
    accept: bool,
) -> dict[str, Any]:
    source = Path(source_path).expanduser().resolve()
    output = Path(out_dir).expanduser().resolve()
    if output.exists():
        raise VisualGateError(f"visual QA output already exists: {output}")
    if not source.is_file():
        raise VisualGateError(f"source page does not exist: {source}")
    if bool(page_pptx) == bool(rendered_image):
        raise VisualGateError("provide exactly one of page_pptx or rendered_image")
    output.mkdir(parents=True)
    try:
        if page_pptx:
            page = Path(page_pptx).expanduser().resolve()
            if not page.is_file():
                raise VisualGateError(f"rebuilt page PPTX does not exist: {page}")
            rendered = _quicklook_render(page, output)
            renderer = "quicklook"
            page_sha256 = _sha256(page)
        else:
            rendered_source = Path(rendered_image).expanduser().resolve()
            if not rendered_source.is_file():
                raise VisualGateError(f"rendered page image does not exist: {rendered_source}")
            rendered = output / "rendered.png"
            shutil.copy2(rendered_source, rendered)
            renderer = "provided-image"
            page_sha256 = None
        source_image = _load_normalized(source, (1280, 720))
        rendered_image_value = _load_normalized(rendered, (1280, 720))
        source_copy = output / "source.png"
        source_image.save(source_copy)
        metrics = _metrics(source_image, rendered_image_value)
        side_by_side = Image.new("RGB", (2560, 720), "white")
        side_by_side.paste(source_image, (0, 0))
        side_by_side.paste(rendered_image_value, (1280, 0))
        side_by_side.save(output / "side-by-side.png")
        difference = ImageEnhance.Contrast(
            ImageChops.difference(source_image, rendered_image_value)
        ).enhance(4)
        difference.save(output / "difference.png")
        thresholds = {
            "pixel_mean_distance": 18.0,
            "structure_distance": 7.0,
            "ink_projection_distance": 0.28,
            "title_pixel_mean_distance": 18.0,
            "title_structure_distance": 7.0,
        }
        metric_passed = all(metrics[name] <= threshold for name, threshold in thresholds.items())
        passed = bool(accept and metric_passed)
        report = {
            "schema": "ppt_visual_page_gate.v1",
            "passed": passed,
            "manual_accept": bool(accept),
            "renderer": renderer,
            "source": str(source),
            "source_sha256": _sha256(source),
            "page_pptx": str(Path(page_pptx).expanduser().resolve()) if page_pptx else None,
            "page_pptx_sha256": page_sha256,
            "rendered": str(rendered),
            "rendered_sha256": _sha256(rendered),
            "metrics": metrics,
            "thresholds": thresholds,
            "evidence": {
                "source": "source.png",
                "rendered": "rendered.png",
                "side_by_side": "side-by-side.png",
                "difference": "difference.png",
            },
            "failure_reason": (
                None
                if passed
                else "visual metrics exceed a threshold or the reviewer did not explicitly accept the Quick Look comparison"
            ),
        }
        _write_json(output / "visual-gate.json", report)
        return report
    except Exception:
        shutil.rmtree(output, ignore_errors=True)
        raise


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Compare a rebuilt one-slide PPTX to the original page with a macOS Quick Look visual gate."
    )
    parser.add_argument("--source", required=True)
    source_group = parser.add_mutually_exclusive_group(required=True)
    source_group.add_argument("--page-pptx")
    source_group.add_argument("--rendered-image", help="Test-only image input; normal reconstruction must use --page-pptx.")
    parser.add_argument("--out-dir", required=True)
    parser.add_argument("--accept", action="store_true", help="Record that the side-by-side and difference images were inspected.")
    args = parser.parse_args()
    try:
        result = verify_page_visual(
            args.source,
            page_pptx=args.page_pptx,
            rendered_image=args.rendered_image,
            out_dir=args.out_dir,
            accept=args.accept,
        )
    except VisualGateError as exc:
        raise SystemExit(str(exc)) from exc
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
