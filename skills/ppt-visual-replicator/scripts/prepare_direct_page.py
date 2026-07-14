#!/usr/bin/env python3
"""Prepare content and optional shared style images for direct image generation."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import tempfile
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from pptx_inspect import InputError, inspect_pptx
from render_source_pages import SourceRenderError, render_pptx_to_pngs


class DirectRunError(ValueError):
    pass


def _write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _copy_input_image(source: str | Path, destination: Path, role: str) -> dict[str, str]:
    image = Path(source).expanduser().resolve()
    if image.suffix.lower() != ".png":
        raise DirectRunError(f"{role} image must be a PNG: {image}")
    if not image.is_file() or not image.stat().st_size:
        raise DirectRunError(f"{role} image does not exist or is empty: {image}")
    shutil.copy2(image, destination)
    return {"path": str(image), "sha256": _sha256(image)}


def _require_slide(ledger: dict[str, Any], slide_number: int, role: str) -> None:
    available = {int(slide["slide_number"]) for slide in ledger.get("slides", [])}
    if slide_number not in available:
        raise DirectRunError(f"{role} slide does not exist: {slide_number}")


def _content_spec(
    slide: dict[str, Any],
    target_slide: int,
    *,
    strict_text_protection: bool,
) -> dict[str, Any]:
    native_text = slide["texts"]
    native_tokens = slide["critical_tokens"]
    return {
        "schema": "ppt_visual_content_spec.v2",
        "target_slide": target_slide,
        "text_protection_mode": "strict-native" if strict_text_protection else "visual-ocr",
        "ocr_source": "source-content.png",
        "required_text": native_text if strict_text_protection else [],
        "critical_tokens": native_tokens if strict_text_protection else [],
        "supplemental_native_text": native_text,
        "supplemental_critical_tokens": native_tokens,
        "object_summary": {
            key: slide[key]
            for key in ("picture_count", "table_count", "chart_count", "graphic_frame_count")
        },
    }


def _as_reference_images(
    value: str | Path | Sequence[str | Path] | None,
) -> list[str | Path]:
    if value is None:
        return []
    if isinstance(value, (str, Path)):
        return [value]
    return list(value)


def _as_reference_slides(value: int | Sequence[int] | None) -> list[int]:
    if value is None:
        return []
    if isinstance(value, int):
        return [value]
    return [int(item) for item in value]


def _reference_prompt(reference_slides: list[int | None]) -> str:
    if not reference_slides:
        return """No style-reference image was supplied. Create a coherent professional presentation style appropriate to the target content. Use a restrained palette, clear title hierarchy, consistent spacing, safe margins, and presentation-ready visual structure. If an explicit style brief appears below, follow it. Do not refuse or stop because a reference image is absent."""

    labels = [
        f"image {index + 2}" + (f" (source slide {slide})" if slide is not None else "")
        for index, slide in enumerate(reference_slides)
    ]
    return f"""The additional images are a shared style-reference set: {', '.join(labels)}. They are visual-style authority only. Use their common typography character, palette, spacing rhythm, visual hierarchy, decorative language, borders, and background treatment. They are deck-level style samples that may be reused for every target page; their order and count do not map one-to-one to target pages. If the samples differ, follow their common visual language instead of copying any single layout literally."""


def _direct_prompt(
    target_slide: int,
    reference_slides: list[int | None],
    content_spec: dict[str, Any],
    style_brief: str | None,
) -> str:
    strict_mode = content_spec["text_protection_mode"] == "strict-native"
    source_text = "\n".join(
        f"- {text}" for text in content_spec["supplemental_native_text"]
    ) or "- No supplemental native text was available"
    critical_tokens = ", ".join(content_spec["supplemental_critical_tokens"]) or "none"
    style_instructions = _reference_prompt(reference_slides)
    brief = style_brief.strip() if style_brief else ""
    brief_block = f"\nExplicit style brief: {brief}\n" if brief else ""
    if strict_mode:
        text_contract = f"""Use the source image plus the native PPTX ledger. The following native text must remain present and exact:
{source_text}
Critical tokens that must remain exact: {critical_tokens}."""
    else:
        text_contract = f"""Read all visible text from the first image with OCR/vision and preserve it. Native PPTX text extraction is supplemental only and may be incomplete; do not stop when it is empty. Use this automatic backup when it clarifies blurred or missing rendered glyphs:
{source_text}
Supplemental critical tokens: {critical_tokens}."""
    return f"""Redraw one complete 16:9 presentation slide.

The first image is the clean content source for target slide {target_slide}; it is the content and layout authority.
{style_instructions}
{brief_block}

Preserve the target canvas ratio, content responsibilities, text regions, data relationships, chart meaning, table meaning, citations, and source-image meaning.

Do not copy reference wording, facts, logos, page numbers, confidential codes, or study data. Do not add, delete, summarize, translate, or rewrite target claims, numbers, charts, tables, citations, or images. Keep all target text legible, but treat generated text as provisional because source text will be restored during editable reconstruction.

{text_contract}

Return one complete slide image only. Do not add a mockup frame, perspective, hands, devices, or surrounding UI.
"""


def prepare_direct_page(
    target: str | Path,
    *,
    target_slide: int,
    run_dir: str | Path,
    source_image: str | Path | None = None,
    source_dpi: int = 192,
    strict_text_protection: bool = False,
    reference_image: str | Path | Sequence[str | Path] | None = None,
    reference_slide: int | Sequence[int] | None = None,
    style_brief: str | None = None,
) -> dict[str, Any]:
    destination = Path(run_dir).expanduser().resolve()
    if destination.exists():
        raise DirectRunError(f"run directory already exists: {destination}")
    try:
        target_ledger = inspect_pptx(target)
    except InputError as exc:
        raise DirectRunError(str(exc)) from exc
    _require_slide(target_ledger, target_slide, "target")
    target_slide_ledger = next(
        slide for slide in target_ledger["slides"] if int(slide["slide_number"]) == target_slide
    )

    rendered_source: tempfile.TemporaryDirectory[str] | None = None
    source_render_report: dict[str, Any] | None = None
    try:
        if source_image is None:
            rendered_source = tempfile.TemporaryDirectory(prefix="ppt-direct-source-")
            try:
                source_render_report = render_pptx_to_pngs(
                    target_ledger["path"],
                    Path(rendered_source.name) / "source-pages",
                    dpi=source_dpi,
                    first_slide=target_slide,
                    last_slide=target_slide,
                    ledger=target_ledger,
                )
            except SourceRenderError as exc:
                raise DirectRunError(str(exc)) from exc
            source_image = source_render_report["pages"][0]["path"]

        destination.mkdir(parents=True)
        reference_images = _as_reference_images(reference_image)
        provided_slides = _as_reference_slides(reference_slide)
        if provided_slides and len(provided_slides) != len(reference_images):
            raise DirectRunError(
                "reference slide metadata must be omitted or supplied once per reference image"
            )
        reference_slides: list[int | None] = (
            [*provided_slides] if provided_slides else [None] * len(reference_images)
        )

        source_info = _copy_input_image(source_image, destination / "source-content.png", "source")
        source_info["mode"] = "auto-rendered-pptx" if source_render_report else "supplied-png"
        if source_render_report:
            source_info["path"] = target_ledger["path"]
            source_info["source_pptx_sha256"] = target_ledger["sha256"]
            source_info["target_slide"] = target_slide
            persistent_render_report = {
                **source_render_report,
                "pages": [
                    {
                        **source_render_report["pages"][0],
                        "path": "source-content.png",
                    }
                ],
            }
            _write_json(destination / "source-render-report.json", persistent_render_report)

        reference_inputs: list[dict[str, Any]] = []
        for index, (image, slide) in enumerate(zip(reference_images, reference_slides)):
            filename = (
                "reference-style.png"
                if len(reference_images) == 1
                else f"reference-style-{index + 1:02d}.png"
            )
            info = _copy_input_image(image, destination / filename, f"reference {index + 1}")
            reference_inputs.append({"image": filename, "source_slide": slide, **info})
    except Exception:
        shutil.rmtree(destination, ignore_errors=True)
        raise
    finally:
        if rendered_source is not None:
            rendered_source.cleanup()

    content_spec = _content_spec(
        target_slide_ledger,
        target_slide,
        strict_text_protection=strict_text_protection,
    )
    clean_style_brief = style_brief.strip() if style_brief else ""
    style_mode = "reference_set" if reference_inputs else ("brief" if clean_style_brief else "default")
    reference_files = [item["image"] for item in reference_inputs]
    manifest = {
        "schema": "ppt_visual_direct_run.v2",
        "target_pptx": target_ledger["path"],
        "target_slide": target_slide,
        "style_mode": style_mode,
        "text_protection_mode": content_spec["text_protection_mode"],
        "style_brief": clean_style_brief or None,
        "reference_slide": reference_slides[0] if len(reference_slides) == 1 else None,
        "reference_slides": reference_slides,
        "source_image": "source-content.png",
        "reference_image": reference_files[0] if len(reference_files) == 1 else None,
        "reference_images": reference_files,
        "source_ledger": "source-ledger.json",
        "source_render_report": "source-render-report.json" if source_render_report else None,
        "content_spec": "content-spec.json",
        "prompt": "direct-image-prompt.txt",
        "generated_image": "generated.png",
        "reconstruction_dir": "reconstruction",
        "inputs": {"source": source_info, "references": reference_inputs},
    }
    _write_json(
        destination / "source-ledger.json",
        {
            "source_pptx": target_ledger["path"],
            "target_slide": target_slide,
            "text_protection_mode": content_spec["text_protection_mode"],
            "slide": target_slide_ledger,
        },
    )
    _write_json(destination / "content-spec.json", content_spec)
    _write_json(destination / "run.json", manifest)
    (destination / "direct-image-prompt.txt").write_text(
        _direct_prompt(target_slide, reference_slides, content_spec, clean_style_brief), encoding="utf-8"
    )
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Prepare a source image and optional shared style images for direct generation."
    )
    parser.add_argument("--target", required=True)
    parser.add_argument("--target-slide", required=True, type=int)
    parser.add_argument(
        "--source-image",
        help="Optional clean PNG override. When omitted, render the selected target slide automatically.",
    )
    parser.add_argument("--source-dpi", type=int, default=192)
    parser.add_argument(
        "--strict-text-protection",
        action="store_true",
        help="Require native PPTX text and critical tokens as exact-content authority.",
    )
    parser.add_argument("--reference-image", action="append")
    parser.add_argument("--reference-slide", action="append", type=int)
    parser.add_argument("--style-brief")
    parser.add_argument("--run-dir", required=True)
    args = parser.parse_args()
    manifest = prepare_direct_page(
        args.target,
        target_slide=args.target_slide,
        run_dir=args.run_dir,
        source_image=args.source_image,
        source_dpi=args.source_dpi,
        strict_text_protection=args.strict_text_protection,
        reference_image=args.reference_image,
        reference_slide=args.reference_slide,
        style_brief=args.style_brief,
    )
    print(json.dumps(manifest, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
