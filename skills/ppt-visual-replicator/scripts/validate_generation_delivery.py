#!/usr/bin/env python3
"""Hard gate for full-page imagegen inputs before editable reconstruction.

The generated image is an intermediate visual reference.  It may enter the
editable-PPT workflow only after a reviewer explicitly confirms that the
source structure survived, no reference content leaked in, and the deck-level
style contract was followed.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


REQUIRED_CHECKS = (
    "source_structure_match",
    "no_invented_information_visuals",
    "no_reference_content_transfer",
    "style_contract_match",
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def validate_generation_delivery(run_dir: str | Path) -> dict[str, Any]:
    root = Path(run_dir).expanduser().resolve()
    errors: list[str] = []
    evidence: dict[str, Any] = {"run_dir": str(root), "pages": []}
    manifest_path = root / "deck-run.json"
    plan_path = root / "generation-plan.json"
    if not manifest_path.is_file() or not plan_path.is_file():
        errors.append("direct run is missing deck-run.json or generation-plan.json")
        result = {"schema": "ppt_visual_generation_delivery_gate.v1", "passed": False, "errors": errors, "evidence": evidence}
        _write_json(root / "generation-delivery-validation.json", result)
        return result

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    plan_by_slide = {int(page["target_slide"]): page for page in plan.get("pages", [])}
    for page in manifest.get("pages", []):
        slide = int(page["target_slide"])
        generation = (plan_by_slide.get(slide) or {}).get("generation") or {}
        action = generation.get("action")
        page_evidence: dict[str, Any] = {"target_slide": slide, "action": action}
        evidence["pages"].append(page_evidence)
        if action != "generate":
            page_evidence["review_required"] = False
            continue

        source = root / str(page.get("source_image") or "")
        image = root / str(page.get("generated_image") or "")
        review = root / str(page.get("run_dir") or "") / "generation-review.json"
        page_evidence.update({"source_image": str(source), "generated_image": str(image), "review": str(review), "review_required": True})
        if not source.is_file() or not source.stat().st_size:
            errors.append(f"slide {slide} has no source image for review: {source}")
            continue
        if not image.is_file() or not image.stat().st_size:
            errors.append(f"slide {slide} has no generated.png to review: {image}")
            continue
        if not review.is_file():
            errors.append(f"slide {slide} has no accepted generation review: {review}")
            continue
        try:
            record = json.loads(review.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            errors.append(f"slide {slide} generation review is not valid JSON: {review}")
            continue
        page_evidence["record"] = record
        if record.get("accepted") is not True:
            errors.append(f"slide {slide} generation review is not accepted")
        if int(record.get("target_slide") or 0) != slide:
            errors.append(f"slide {slide} generation review points to another slide")
        if record.get("generated_image_sha256") != _sha256(image):
            errors.append(f"slide {slide} generated image changed after its review")
        if record.get("source_image_sha256") != _sha256(source):
            errors.append(f"slide {slide} source image changed after its review")
        checks = record.get("checks") or {}
        failed = [name for name in REQUIRED_CHECKS if checks.get(name) is not True]
        if failed:
            errors.append(f"slide {slide} generation review has failed or missing checks: {', '.join(failed)}")
        if not str(record.get("review_note") or "").strip():
            errors.append(f"slide {slide} generation review needs a concrete review_note")

    result = {
        "schema": "ppt_visual_generation_delivery_gate.v1",
        "passed": not errors,
        "errors": errors,
        "evidence": evidence,
    }
    _write_json(root / "generation-delivery-validation.json", result)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Reject unreviewed or structurally drifted full-page imagegen outputs before reconstruction."
    )
    parser.add_argument("--run-dir", required=True)
    args = parser.parse_args()
    result = validate_generation_delivery(args.run_dir)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
