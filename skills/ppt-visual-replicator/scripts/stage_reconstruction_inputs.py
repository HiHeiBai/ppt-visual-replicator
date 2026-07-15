#!/usr/bin/env python3
"""Materialize the mixed redraw/direct/reuse page plan for editppt preparation."""

from __future__ import annotations

import argparse
import json
import os
import shutil
from pathlib import Path
from typing import Any

from validate_generation_delivery import validate_generation_delivery


class StageInputsError(RuntimeError):
    pass


def _write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _link_or_copy(source: Path, destination: Path) -> str:
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists() or destination.is_symlink():
        destination.unlink()
    try:
        os.link(source, destination)
        return "hardlink"
    except OSError:
        shutil.copy2(source, destination)
        return "copy"


def _source_for_page(
    run_dir: Path,
    page: dict[str, Any],
    by_slide: dict[int, dict[str, Any]],
) -> tuple[Path, str, int]:
    generation = page.get("generation") or {}
    action = generation.get("action")
    slide_number = int(page["target_slide"])
    if action == "generate":
        source = run_dir / page["generated_image"]
        return source, "generated", slide_number
    if action == "direct-rebuild":
        source = run_dir / page["source_image"]
        return source, "source-content", slide_number
    if action == "reuse":
        canonical_slide = int(generation.get("canonical_slide") or 0)
        canonical = by_slide.get(canonical_slide)
        if not canonical or canonical_slide == slide_number:
            raise StageInputsError(
                f"slide {slide_number} has an invalid canonical slide: {canonical_slide}"
            )
        source, source_kind, _ = _source_for_page(run_dir, canonical, by_slide)
        return source, f"reused-{source_kind}", canonical_slide
    raise StageInputsError(f"slide {slide_number} has an unknown generation action: {action}")


def stage_reconstruction_inputs(
    run_dir: str | Path,
    *,
    out_dir: str | Path | None = None,
) -> dict[str, Any]:
    root = Path(run_dir).expanduser().resolve()
    manifest_path = root / "deck-run.json"
    if not manifest_path.is_file():
        raise StageInputsError(f"deck-run.json does not exist: {manifest_path}")
    generation_gate = validate_generation_delivery(root)
    if generation_gate.get("passed") is not True:
        details = "; ".join(generation_gate.get("errors", []))
        raise StageInputsError(
            "refusing reconstruction staging before full-page imagegen review passes: " + details
        )
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    pages = manifest.get("pages") or []
    if not pages:
        raise StageInputsError("deck-run.json has no pages")
    destination = (
        Path(out_dir).expanduser().resolve() if out_dir else root / "reconstruction-inputs"
    )
    destination.mkdir(parents=True, exist_ok=True)
    by_slide = {int(page["target_slide"]): page for page in pages}
    staged = []
    expected_names = set()

    for page in pages:
        slide_number = int(page["target_slide"])
        source, source_kind, canonical_slide = _source_for_page(root, page, by_slide)
        if not source.is_file() or not source.stat().st_size:
            raise StageInputsError(
                f"slide {slide_number} is not ready; required image is missing: {source}"
            )
        output = destination / f"slide-{slide_number:03d}.png"
        expected_names.add(output.name)
        materialization = _link_or_copy(source, output)
        staged.append(
            {
                "target_slide": slide_number,
                "input": str(output.relative_to(root)) if output.is_relative_to(root) else str(output),
                "source": str(source.relative_to(root)) if source.is_relative_to(root) else str(source),
                "source_kind": source_kind,
                "canonical_slide": canonical_slide,
                "materialization": materialization,
            }
        )

    for stale in destination.glob("slide-*.png"):
        if stale.name not in expected_names:
            stale.unlink()

    report = {
        "schema": "ppt_visual_reconstruction_inputs.v1",
        "speed_profile": manifest.get("speed_profile", "strict"),
        "page_count": len(staged),
        "output_dir": str(destination),
        "pages": staged,
        "editppt_glob": str(destination / "slide-*.png"),
    }
    _write_json(destination / "reconstruction-inputs.json", report)
    return report


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Stage the page images selected by a PPT visual generation plan."
    )
    parser.add_argument("--run-dir", required=True)
    parser.add_argument("--out-dir")
    args = parser.parse_args()
    report = stage_reconstruction_inputs(args.run_dir, out_dir=args.out_dir)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
