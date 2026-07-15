#!/usr/bin/env python3
"""Hard delivery gate for direct full-slide visual replication runs.

Whole-slide image generation is a visual-input step.  It is never sufficient
evidence for an editable PPTX delivery.  This validator binds the proposed
final PPTX to the completed editppt reconstruction run and verifies that the
native source text survives in editable final-slide objects.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from pptx_inspect import InputError, inspect_pptx
from validate_generation_delivery import validate_generation_delivery
from validate_visual_run import validate_recorded_editppt_run


class EditableDeliveryError(RuntimeError):
    pass


def _write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _normalize(value: str) -> str:
    return "".join(value.split()).lower()


def validate_editable_delivery(run_dir: str | Path, pptx: str | Path) -> dict[str, Any]:
    root = Path(run_dir).expanduser().resolve()
    candidate = Path(pptx).expanduser().resolve()
    errors: list[str] = []
    evidence: dict[str, Any] = {
        "run_dir": str(root),
        "candidate_pptx": str(candidate),
        "reconstruction_run": str(root / "reconstruction"),
        "slide_count": 0,
        "slides_with_required_native_text": 0,
        "image_only_slides": 0,
        "text_validation_mode": "unknown",
    }

    deck_run = root / "deck-run.json"
    source_ledger = root / "source-ledger.json"
    reconstruction = root / "reconstruction"
    if not deck_run.is_file():
        errors.append(f"direct run is missing deck-run.json: {deck_run}")
    if not source_ledger.is_file():
        errors.append(f"direct run is missing source-ledger.json: {source_ledger}")
    if not candidate.is_file() or candidate.suffix.lower() != ".pptx":
        errors.append(f"candidate final PPTX does not exist: {candidate}")

    reconstruction_report = validate_recorded_editppt_run(reconstruction)
    evidence["reconstruction"] = reconstruction_report
    if reconstruction_report.get("passed") is not True:
        errors.extend(
            f"editable reconstruction gate failed: {message}"
            for message in reconstruction_report.get("errors", [])
        )

    generation_report = validate_generation_delivery(root)
    evidence["generation"] = generation_report
    if generation_report.get("passed") is not True:
        errors.extend(
            f"whole-page imagegen gate failed: {message}"
            for message in generation_report.get("errors", [])
        )

    final_validation_path = reconstruction / "final" / "validation.json"
    if final_validation_path.is_file():
        final_validation = json.loads(final_validation_path.read_text(encoding="utf-8"))
        expected_value = final_validation.get("pptx")
        if expected_value:
            expected = Path(expected_value).expanduser().resolve()
            evidence["recorded_final_pptx"] = str(expected)
            if candidate != expected:
                errors.append(
                    "candidate PPTX is not the editppt finalized artifact: "
                    f"expected {expected}, got {candidate}"
                )
        else:
            errors.append("editable reconstruction final validation has no PPTX path")
    else:
        errors.append(f"editable reconstruction final validation is missing: {final_validation_path}")

    if errors:
        result = {
            "schema": "ppt_visual_editable_delivery_gate.v1",
            "passed": False,
            "errors": errors,
            "evidence": evidence,
        }
        root.mkdir(parents=True, exist_ok=True)
        _write_json(root / "editable-delivery-validation.json", result)
        return result

    source = json.loads(source_ledger.read_text(encoding="utf-8"))
    direct_manifest = json.loads(deck_run.read_text(encoding="utf-8"))
    strict_native = direct_manifest.get("text_protection_mode") == "strict-native"
    evidence["text_validation_mode"] = (
        "source-ledger-exact" if strict_native else "page-manifest-and-visual-qa"
    )
    try:
        final = inspect_pptx(candidate)
    except InputError as exc:
        result = {
            "schema": "ppt_visual_editable_delivery_gate.v1",
            "passed": False,
            "errors": [f"candidate final PPTX is invalid: {exc}"],
            "evidence": evidence,
        }
        _write_json(root / "editable-delivery-validation.json", result)
        return result

    evidence["slide_count"] = int(final.get("slide_count", 0))
    source_slides = source.get("slides", [])
    final_slides = final.get("slides", [])
    if len(source_slides) != len(final_slides):
        errors.append(
            f"final slide count mismatch: expected {len(source_slides)}, found {len(final_slides)}"
        )

    for source_slide, final_slide in zip(source_slides, final_slides):
        slide_number = int(source_slide.get("slide_number", 0))
        final_text = _normalize(" ".join(final_slide.get("texts", [])))
        required = [text for text in source_slide.get("texts", []) if _normalize(text)]
        if strict_native:
            missing = [text for text in required if _normalize(text) not in final_text]
            if missing:
                errors.append(
                    f"final slide {slide_number} is missing editable source text: {missing[:3]}"
                )
            elif required:
                evidence["slides_with_required_native_text"] += 1
        elif required and not final_text:
            # Page-level validation checks the worker's visual-OCR text
            # inventory. Keep a final safety net for a page that lost all
            # editable text, without incorrectly treating hidden/stale OOXML
            # strings in the original PPTX as default-mode hard requirements.
            errors.append(f"final slide {slide_number} lost all editable text")

        if (
            int(final_slide.get("picture_count", 0)) == 1
            and int(final_slide.get("text_chars", 0)) == 0
            and int(final_slide.get("table_count", 0)) == 0
            and int(final_slide.get("chart_count", 0)) == 0
        ):
            evidence["image_only_slides"] += 1
            errors.append(
                f"final slide {slide_number} is a full-slide raster with no editable text or structure"
            )

    result = {
        "schema": "ppt_visual_editable_delivery_gate.v1",
        "passed": not errors,
        "errors": errors,
        "evidence": evidence,
    }
    _write_json(root / "editable-delivery-validation.json", result)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Reject non-editable or non-finalized PPTX files before direct-run delivery."
    )
    parser.add_argument("--run-dir", required=True)
    parser.add_argument("--pptx", required=True)
    args = parser.parse_args()
    result = validate_editable_delivery(args.run_dir, args.pptx)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
