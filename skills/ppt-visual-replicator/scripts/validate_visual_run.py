#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import struct
from pathlib import Path
from typing import Any

from pptx_inspect import InputError, inspect_pptx


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _png_size(path: Path) -> tuple[int, int]:
    data = path.read_bytes()[:24]
    if len(data) < 24 or data[:8] != b"\x89PNG\r\n\x1a\n" or data[12:16] != b"IHDR":
        raise ValueError("not a valid PNG header")
    return struct.unpack(">II", data[16:24])


def _normalize(text: str) -> str:
    return "".join(text.split()).lower()


def _style_consistency_checks(
    root: Path,
    plan: dict[str, Any],
    jobs_manifest: dict[str, Any],
    errors: list[str],
    warnings: list[str],
) -> dict[str, Any]:
    evidence: dict[str, Any] = {
        "style_lock_present": False,
        "automatic_reference_deck_count": 0,
        "automatic_family_anchor_counts": {},
        "explicit_override_pages": [],
        "allowed_fallback_families": [],
        "scale_jobs": 0,
        "approved_calibration_families": 0,
        "approved_calibration_hashes_checked": 0,
    }
    style_lock = plan.get("style_lock")
    if not isinstance(style_lock, dict):
        errors.append("visual plan has no deck-level style lock")
        style_lock = {}
    else:
        evidence["style_lock_present"] = True
    primary_index = int(style_lock.get("primary_reference_index", 0))
    allow_fallback = style_lock.get("allow_fallback_decks") is True
    if style_lock.get("anchor_policy") != "one_per_family":
        errors.append("visual plan does not enforce one automatic anchor per family")

    automatic_decks: set[int] = set()
    anchors_by_family: dict[str, set[tuple[int, int]]] = {}
    override_pages: list[int] = []
    fallback_families: set[str] = set()
    for page in plan.get("pages", []):
        mode = str(page.get("match_mode", ""))
        slide = int(page.get("target_slide", 0))
        if mode == "override":
            override_pages.append(slide)
            continue
        family = str(page.get("target_family", "content"))
        reference_index = int(page.get("reference_index", 0))
        reference_slide = int(page.get("reference_slide", 0))
        automatic_decks.add(reference_index)
        anchors_by_family.setdefault(family, set()).add((reference_index, reference_slide))
        if mode == "fallback_deck":
            fallback_families.add(family)

    evidence["automatic_reference_deck_count"] = len(automatic_decks)
    evidence["automatic_family_anchor_counts"] = {
        family: len(anchors) for family, anchors in sorted(anchors_by_family.items())
    }
    evidence["explicit_override_pages"] = sorted(override_pages)
    evidence["allowed_fallback_families"] = sorted(fallback_families) if allow_fallback else []
    non_primary_decks = sorted(index for index in automatic_decks if index != primary_index)
    if non_primary_decks and not allow_fallback:
        if len(automatic_decks) > 1:
            errors.append(
                "multiple automatic reference decks violate the primary deck lock: "
                + ", ".join(str(index) for index in sorted(automatic_decks))
            )
        else:
            errors.append(f"automatic pages use non-primary reference deck: {non_primary_decks[0]}")
    elif non_primary_decks:
        warnings.append(
            "allowed fallback decks are used for page families: "
            + ", ".join(sorted(fallback_families))
        )
    if override_pages:
        warnings.append(
            "explicit reference overrides are excluded from automatic style-lock checks: "
            + ", ".join(str(slide) for slide in sorted(override_pages))
        )
    for family, anchors in sorted(anchors_by_family.items()):
        if len(anchors) > 1:
            errors.append(f"page family uses multiple automatic anchors: {family}")

    scale_jobs = [job for job in jobs_manifest.get("jobs", []) if job.get("batch") == "scale"]
    evidence["scale_jobs"] = len(scale_jobs)
    if not scale_jobs:
        return evidence
    approval_path = root / "calibration-approved.json"
    if not approval_path.is_file():
        errors.append("calibration approval is required when scale jobs exist")
        return evidence
    try:
        approval = json.loads(approval_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        errors.append(f"calibration approval is invalid: {exc}")
        return evidence
    approved_families = approval.get("families", {})
    if not isinstance(approved_families, dict):
        errors.append("calibration approval has no family records")
        return evidence
    evidence["approved_calibration_families"] = len(approved_families)
    for family, item in sorted(approved_families.items()):
        if not isinstance(item, dict):
            errors.append(f"calibration approval is invalid for family: {family}")
            continue
        output_value = item.get("output")
        expected_hash = item.get("sha256")
        output = root / str(output_value) if output_value else None
        if output is None or not output.is_file() or not expected_hash:
            errors.append(f"approved calibration output is incomplete for family: {family}")
            continue
        evidence["approved_calibration_hashes_checked"] += 1
        if _sha256(output) != expected_hash:
            errors.append(f"approved calibration hash changed for family: {family}")
    for job in scale_jobs:
        family = str(job.get("target_family", "content"))
        approved = approved_families.get(family)
        if not isinstance(approved, dict):
            errors.append(f"calibration approval is missing for scale family: {family}")
            continue
        if job.get("calibration_anchor") != approved.get("output"):
            errors.append(f"scale job uses an unapproved calibration anchor: {job.get('job_id')}")
        if job.get("calibration_anchor_sha256") != approved.get("sha256"):
            errors.append(f"scale job calibration hash does not match approval: {job.get('job_id')}")
    return evidence


def _generated_checks(root: Path, errors: list[str], warnings: list[str]) -> dict[str, Any]:
    evidence: dict[str, Any] = {
        "planned_pages": 0,
        "generated_pages": 0,
        "provenance_files_checked": 0,
    }
    try:
        plan = json.loads((root / "visual-plan.json").read_text(encoding="utf-8"))
        jobs_manifest = json.loads((root / "image-jobs.json").read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        errors.append(f"missing run manifest: {exc.filename}")
        return evidence
    evidence["planned_pages"] = int(plan.get("page_count", len(plan.get("pages", []))))
    evidence.update(_style_consistency_checks(root, plan, jobs_manifest, errors, warnings))
    jobs = {int(job.get("target_slide", 0)): job for job in jobs_manifest.get("jobs", [])}
    for page in plan.get("pages", []):
        slide = int(page["target_slide"])
        job = jobs.get(slide)
        if not job:
            errors.append(f"missing image job for target slide {slide}")
            continue
        if job.get("status") != "complete":
            errors.append(f"image job is not complete for target slide {slide}: {job.get('status')}")
        for path_key, hash_key in (
            ("target_image", "target_sha256"),
            ("reference_image", "reference_sha256"),
            ("prompt_file", "prompt_sha256"),
            ("output", "output_sha256"),
        ):
            relative = job.get(path_key)
            if not relative:
                errors.append(f"missing {path_key} provenance for target slide {slide}")
                continue
            path = root / relative
            if not path.is_file():
                label = "generated page" if path_key == "output" else path_key.replace("_", " ")
                errors.append(f"missing {label} for target slide {slide}: {path}")
                continue
            expected_hash = job.get(hash_key)
            if not expected_hash:
                errors.append(f"missing {hash_key} provenance for target slide {slide}")
            elif _sha256(path) != expected_hash:
                errors.append(f"{path_key} hash mismatch for target slide {slide}")
            evidence["provenance_files_checked"] += 1
            if path_key == "output":
                try:
                    width, height = _png_size(path)
                    if width <= 0 or height <= 0:
                        raise ValueError("zero image dimension")
                    if abs((width / height) - (16 / 9)) > 0.02:
                        warnings.append(f"generated page aspect ratio differs from 16:9 on slide {slide}: {width}x{height}")
                    evidence["generated_pages"] += 1
                except ValueError as exc:
                    errors.append(f"invalid generated page for target slide {slide}: {exc}")
    return evidence


def _final_checks(
    root: Path,
    final_pptx: Path | None,
    reconstruction_validation: Path | None,
    errors: list[str],
    warnings: list[str],
) -> dict[str, int]:
    evidence = {
        "slides": 0,
        "critical_tokens_checked": 0,
        "critical_tokens_missing": 0,
        "required_text_blocks_checked": 0,
        "required_text_blocks_missing": 0,
        "image_only_slides": 0,
    }
    if final_pptx is None:
        errors.append("final PPTX path is required for final validation")
        return evidence
    if reconstruction_validation is None or not reconstruction_validation.is_file():
        errors.append("reconstruction validation JSON is required")
    else:
        payload = json.loads(reconstruction_validation.read_text(encoding="utf-8"))
        if payload.get("passed") is not True:
            errors.append("reconstruction validation did not pass")

    source_path = root / "source-ledger.json"
    if not source_path.is_file():
        errors.append(f"source ledger is missing: {source_path}")
        return evidence
    source = json.loads(source_path.read_text(encoding="utf-8"))
    try:
        final = inspect_pptx(final_pptx)
    except InputError as exc:
        errors.append(f"final PPTX is invalid: {exc}")
        return evidence
    evidence["slides"] = int(final["slide_count"])
    if final["slide_count"] != source.get("slide_count"):
        errors.append(
            f"final slide count mismatch: expected {source.get('slide_count')}, found {final['slide_count']}"
        )

    for source_slide, final_slide in zip(source.get("slides", []), final.get("slides", [])):
        slide_number = int(source_slide["slide_number"])
        source_tokens = set(source_slide.get("critical_tokens", []))
        final_tokens = set(final_slide.get("critical_tokens", []))
        missing_tokens = sorted(source_tokens - final_tokens)
        evidence["critical_tokens_checked"] += len(source_tokens)
        evidence["critical_tokens_missing"] += len(missing_tokens)
        if missing_tokens:
            errors.append(f"missing critical tokens on slide {slide_number}: {', '.join(missing_tokens)}")

        final_text = _normalize(" ".join(final_slide.get("texts", [])))
        missing_blocks = [
            text
            for text in source_slide.get("texts", [])
            if _normalize(text) and _normalize(text) not in final_text
        ]
        evidence["required_text_blocks_checked"] += len(source_slide.get("texts", []))
        evidence["required_text_blocks_missing"] += len(missing_blocks)
        if missing_blocks:
            errors.append(f"missing required source text on slide {slide_number}: {missing_blocks[:3]}")

        if (
            int(final_slide.get("picture_count", 0)) == 1
            and int(final_slide.get("text_chars", 0)) == 0
            and int(final_slide.get("table_count", 0)) == 0
            and int(final_slide.get("chart_count", 0)) == 0
        ):
            evidence["image_only_slides"] += 1
            errors.append(f"image-only final slide is not editable: slide {slide_number}")
    return evidence


def validate_visual_run(
    run_dir: str | Path,
    *,
    stage: str,
    final_pptx: str | Path | None = None,
    reconstruction_validation: str | Path | None = None,
) -> dict[str, Any]:
    if stage not in {"generated", "final"}:
        raise ValueError(f"unsupported validation stage: {stage}")
    root = Path(run_dir).expanduser().resolve()
    errors: list[str] = []
    warnings: list[str] = []
    evidence: dict[str, Any] = _generated_checks(root, errors, warnings)
    if stage == "final":
        evidence.update(
            _final_checks(
                root,
                Path(final_pptx).expanduser().resolve() if final_pptx else None,
                Path(reconstruction_validation).expanduser().resolve() if reconstruction_validation else None,
                errors,
                warnings,
            )
        )
    result = {
        "schema": "ppt_visual_validation.v1",
        "stage": stage,
        "passed": not errors,
        "errors": errors,
        "warnings": warnings,
        "evidence": evidence,
    }
    root.mkdir(parents=True, exist_ok=True)
    (root / "validation.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return result


def validate_recorded_editppt_run(run_dir: str | Path) -> dict[str, Any]:
    root = Path(run_dir).expanduser().resolve()
    errors: list[str] = []
    warnings: list[str] = []
    evidence = {
        "slides": 0,
        "page_jobs": 0,
        "page_validations_passed": 0,
        "editable_text_shapes": 0,
        "shape_count": 0,
    }
    try:
        state = json.loads((root / "run_state.json").read_text(encoding="utf-8"))
        page_jobs = json.loads((root / "page_jobs.json").read_text(encoding="utf-8"))
        final_validation = json.loads((root / "final" / "validation.json").read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        errors.append(f"recorded editppt run is missing required state: {exc.filename}")
        return {"passed": False, "errors": errors, "warnings": warnings, "evidence": evidence}

    if state.get("status") != "complete":
        errors.append(f"recorded editppt run is not complete: {state.get('status')}")
    if final_validation.get("passed") is not True:
        errors.append("recorded editppt final validation did not pass")
    pages = page_jobs.get("pages", [])
    evidence["page_jobs"] = len(pages)
    for page in pages:
        page_id = page.get("page_id", "unknown")
        validation_path = root / "pages" / page_id / "validation.json"
        manifest_path = root / "pages" / page_id / "manifest.json"
        if not validation_path.is_file() or not manifest_path.is_file():
            errors.append(f"recorded page artifacts are missing: {page_id}")
            continue
        page_validation = json.loads(validation_path.read_text(encoding="utf-8"))
        if page_validation.get("passed") is not True:
            errors.append(f"recorded page validation did not pass: {page_id}")
            continue
        evidence["page_validations_passed"] += 1
        evidence["editable_text_shapes"] += int(page_validation.get("editable_text_shapes", 0))
        evidence["shape_count"] += int(page_validation.get("shape_count", 0))

    final_pptx_value = final_validation.get("pptx")
    final_pptx = Path(final_pptx_value) if final_pptx_value else None
    if final_pptx is None or not final_pptx.is_file():
        errors.append(f"recorded final PPTX is missing: {final_pptx_value}")
    else:
        try:
            final = inspect_pptx(final_pptx)
            evidence["slides"] = int(final["slide_count"])
        except InputError as exc:
            errors.append(f"recorded final PPTX is invalid: {exc}")

    expected = int(final_validation.get("expected_pages", len(pages)))
    if evidence["slides"] and evidence["slides"] != expected:
        errors.append(f"recorded final slide count mismatch: expected {expected}, found {evidence['slides']}")
    if evidence["page_validations_passed"] != len(pages):
        errors.append(
            f"recorded page validation count mismatch: expected {len(pages)}, found {evidence['page_validations_passed']}"
        )
    return {
        "schema": "ppt_visual_recorded_editppt_validation.v1",
        "passed": not errors,
        "errors": errors,
        "warnings": warnings,
        "evidence": evidence,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate generated pages and editable PPT reconstruction.")
    parser.add_argument("--run-dir", required=True)
    parser.add_argument("--stage", choices=("generated", "final"), required=True)
    parser.add_argument("--final-pptx")
    parser.add_argument("--reconstruction-validation")
    args = parser.parse_args()
    result = validate_visual_run(
        args.run_dir,
        stage=args.stage,
        final_pptx=args.final_pptx,
        reconstruction_validation=args.reconstruction_validation,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
