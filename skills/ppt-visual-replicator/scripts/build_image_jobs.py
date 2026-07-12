#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any


class JobError(ValueError):
    pass


IMAGE_SIZE = "2560x1440"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _prompt(page: dict[str, Any], batch: str) -> str:
    if batch == "scale":
        authority = """The first image is the target slide and is the edit target and content authority.
The second image is the approved generated calibration slide for this page family and is the layout and visual-style authority. Reuse the approved calibration slide's layout skeleton, title placement, margins, content containers, footer position, palette, decorative density, and recurring chrome. Map the target's logical content groups into that skeleton. Do not preserve the target's original visual layout. Change the calibration skeleton only when target content has a genuinely different number or type of logical groups, and keep the same deck-level geometry when adapting it.
"""
    else:
        authority = f"""The first image is target slide {page['target_slide']} and is the edit target and content authority.
The second image is locked reference slide {page['reference_slide']} and is visual-style authority only.
"""
    return f"""Redesign one complete 16:9 presentation slide.

{authority}
Preserve the target canvas ratio, content responsibilities, text regions, data relationships, chart meaning, table meaning, citations, and source-image meaning. Preserve target logos, target page numbers, confidentiality notices, document codes, and every target footer item in their original semantic role and relative slide area; restyle them if needed, but never remove or replace them. Keep every target element fully inside the canvas with safe margins and at least 3% inset from every canvas edge. Do not crop or clip labels, pills, logos, text, charts, tables, images, or footer items. Transfer the locked reference typography character, palette, spacing rhythm, visual hierarchy, decorative language, borders, and background treatment.

Do not copy reference wording, facts, logos, page numbers, confidential codes, or study data. Do not add, delete, summarize, translate, or rewrite target claims, numbers, charts, tables, citations, or images. Keep all target text legible, but treat generated text as provisional because exact source text will be restored during editable reconstruction.

Return one complete slide image only. Do not add a mockup frame, perspective, hands, devices, or surrounding UI.
"""


def build_image_jobs(
    run_dir: str | Path,
    *,
    execute: bool = False,
    force: bool = False,
    command_prefix: list[str] | None = None,
) -> dict[str, Any]:
    root = Path(run_dir).expanduser().resolve()
    plan_path = root / "visual-plan.json"
    if not plan_path.is_file():
        raise JobError(f"visual plan does not exist: {plan_path}")
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    prompts_dir = root / "prompts"
    generated_dir = root / "generated"
    prompts_dir.mkdir(exist_ok=True)
    generated_dir.mkdir(exist_ok=True)

    first_by_family: dict[str, int] = {}
    for page in plan.get("pages", []):
        family = str(page.get("target_family", "content"))
        first_by_family.setdefault(family, int(page["target_slide"]))

    jobs = []
    for page in plan.get("pages", []):
        slide_number = int(page["target_slide"])
        family = str(page.get("target_family", "content"))
        batch = "calibration" if first_by_family[family] == slide_number else "scale"
        target_rel = str(page["target_image"])
        reference_rel = str(page["reference_image"])
        target = root / target_rel
        reference = root / reference_rel
        if not target.is_file():
            raise JobError(f"target image does not exist: {target}")
        if not reference.is_file():
            raise JobError(f"reference image does not exist: {reference}")

        prompt_rel = f"prompts/page-{slide_number:03d}.txt"
        output_rel = f"generated/page-{slide_number:03d}.png"
        calibration_rel = (
            None
            if batch == "calibration"
            else f"generated/page-{first_by_family[family]:03d}.png"
        )
        prompt_path = root / prompt_rel
        output_path = root / output_rel
        if output_path.exists() and not force:
            raise JobError(f"generated page already exists: {output_path}")
        prompt_path.write_text(_prompt(page, batch), encoding="utf-8")
        command = [
            "editppt",
            "image",
            "edit",
            "--image",
            str(target),
        ]
        command.extend(
            ["--image", str(root / calibration_rel)]
            if calibration_rel
            else ["--image", str(reference)]
        )
        command.extend(
            [
                "--prompt-file",
                str(prompt_path),
                "--size",
                IMAGE_SIZE,
                "--quality",
                "high",
                "--out",
                str(output_path),
            ]
        )
        jobs.append(
            {
                "job_id": f"page-{slide_number:03d}",
                "target_slide": slide_number,
                "target_family": family,
                "batch": batch,
                "reference_slide": int(page["reference_slide"]),
                "target_image": target_rel,
                "target_sha256": _sha256(target),
                "reference_image": reference_rel,
                "reference_sha256": _sha256(reference),
                "calibration_anchor": calibration_rel,
                "calibration_anchor_sha256": None,
                "prompt_file": prompt_rel,
                "prompt_sha256": _sha256(prompt_path),
                "output": output_rel,
                "output_sha256": None,
                "model": "gpt-image-2",
                "size": IMAGE_SIZE,
                "quality": "high",
                "command": command,
                "status": "ready",
                "error": None,
            }
        )

    manifest = {
        "schema": "ppt_visual_image_jobs.v2",
        "execution_mode": "serial_calibration_then_scale",
        "executed_phases": [],
        "calibration_approval": "calibration-approved.json",
        "jobs": jobs,
    }
    _write_json(root / "image-jobs.json", manifest)
    if execute:
        return execute_image_jobs(
            root,
            phase="calibration",
            force=force,
            command_prefix=command_prefix,
        )
    return manifest


def _load_jobs(root: Path) -> dict[str, Any]:
    path = root / "image-jobs.json"
    if not path.is_file():
        raise JobError(f"image jobs do not exist: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def approve_calibration(run_dir: str | Path) -> dict[str, Any]:
    root = Path(run_dir).expanduser().resolve()
    manifest = _load_jobs(root)
    families: dict[str, Any] = {}
    for job in manifest.get("jobs", []):
        if job.get("batch") != "calibration":
            continue
        if job.get("status") != "complete" or not job.get("output_sha256"):
            raise JobError(f"calibration job is not complete: {job.get('job_id')}")
        output = root / str(job["output"])
        if not output.is_file() or _sha256(output) != job["output_sha256"]:
            raise JobError(f"calibration output hash mismatch: {job.get('job_id')}")
        families[str(job["target_family"])] = {
            "job_id": job["job_id"],
            "output": job["output"],
            "sha256": job["output_sha256"],
        }
    if not families:
        raise JobError("no completed calibration jobs are available for approval")
    approval = {
        "schema": "ppt_visual_calibration_approval.v1",
        "families": families,
    }
    _write_json(root / "calibration-approved.json", approval)
    return approval


def _validated_approval(root: Path) -> dict[str, Any]:
    path = root / "calibration-approved.json"
    if not path.is_file():
        raise JobError("calibration approval is required before scale execution")
    approval = json.loads(path.read_text(encoding="utf-8"))
    for family, item in approval.get("families", {}).items():
        output = root / str(item["output"])
        if not output.is_file() or _sha256(output) != item.get("sha256"):
            raise JobError(f"approved calibration hash changed for family: {family}")
    return approval


def execute_image_jobs(
    run_dir: str | Path,
    *,
    phase: str,
    force: bool = False,
    command_prefix: list[str] | None = None,
) -> dict[str, Any]:
    if phase not in {"calibration", "scale"}:
        raise JobError(f"unsupported image execution phase: {phase}")
    root = Path(run_dir).expanduser().resolve()
    manifest = _load_jobs(root)
    approval = _validated_approval(root) if phase == "scale" else None
    prefix = list(command_prefix or ["editppt"])

    for job in manifest.get("jobs", []):
        if job.get("batch") != phase:
            continue
        if job.get("status") == "complete" and not force:
            continue
        if phase == "scale":
            family = str(job["target_family"])
            approved = approval.get("families", {}).get(family) if approval else None
            if not approved:
                raise JobError(f"calibration approval is missing for family: {family}")
            if approved.get("output") != job.get("calibration_anchor"):
                raise JobError(f"scale job uses an unapproved calibration anchor: {job['job_id']}")
            job["calibration_anchor_sha256"] = approved["sha256"]

        output_path = root / str(job["output"])
        if output_path.exists() and not force:
            raise JobError(f"generated page already exists: {output_path}")
        command = prefix + list(job["command"])[1:]
        if force:
            command.append("--force")
        last_error: OSError | subprocess.CalledProcessError | None = None
        for attempt in range(2):
            try:
                subprocess.run(command, check=True)
                last_error = None
                break
            except (OSError, subprocess.CalledProcessError) as exc:
                last_error = exc
                if attempt == 0:
                    output_path.unlink(missing_ok=True)
                    continue
        if last_error is not None:
            job["status"] = "failed"
            job["error"] = str(last_error)
            _write_json(root / "image-jobs.json", manifest)
            raise JobError(
                f"image generation failed for slide {job['target_slide']} after retry: {last_error}"
            ) from last_error
        if not output_path.is_file():
            raise JobError(f"image backend did not create output: {output_path}")
        job["status"] = "complete"
        job["error"] = None
        job["output_sha256"] = _sha256(output_path)

    phases = list(manifest.get("executed_phases", []))
    if phase not in phases:
        phases.append(phase)
    manifest["executed_phases"] = phases
    _write_json(root / "image-jobs.json", manifest)
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description="Build and execute calibration-locked image edit jobs.")
    parser.add_argument("--run-dir", required=True)
    parser.add_argument("--execute-phase", choices=("calibration", "scale"))
    parser.add_argument("--approve-calibration", action="store_true")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    if args.approve_calibration:
        result = approve_calibration(args.run_dir)
    elif args.execute_phase:
        result = execute_image_jobs(args.run_dir, phase=args.execute_phase, force=args.force)
    else:
        result = build_image_jobs(args.run_dir, force=args.force)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
