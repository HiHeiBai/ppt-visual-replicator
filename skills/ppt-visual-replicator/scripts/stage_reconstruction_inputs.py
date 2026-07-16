#!/usr/bin/env python3
"""Stage reviewed generated PNGs for editppt preparation."""

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
) -> tuple[Path, str]:
    generation = page.get("generation") or {}
    action = generation.get("action")
    slide_number = int(page["target_slide"])
    if action != "generate":
        raise StageInputsError(
            f"slide {slide_number} violates the fixed pipeline; expected generation action 'generate', got: {action}"
        )
    return run_dir / page["generated_image"], "generated"


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
    staged = []
    expected_names = set()

    for page in pages:
        slide_number = int(page["target_slide"])
        source, source_kind = _source_for_page(root, page)
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
                "materialization": materialization,
            }
        )

    for stale in destination.glob("slide-*.png"):
        if stale.name not in expected_names:
            stale.unlink()

    report = {
        "schema": "ppt_visual_reconstruction_inputs.v1",
        "page_count": len(staged),
        "output_dir": str(destination),
        "pages": staged,
        "editppt_glob": str(destination / "slide-*.png"),
    }
    _write_json(destination / "reconstruction-inputs.json", report)
    return report


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Stage reviewed generated PNGs for editable reconstruction."
    )
    parser.add_argument("--run-dir", required=True)
    parser.add_argument("--out-dir")
    args = parser.parse_args()
    report = stage_reconstruction_inputs(args.run_dir, out_dir=args.out_dir)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
