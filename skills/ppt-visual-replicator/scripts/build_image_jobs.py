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


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _prompt(page: dict[str, Any]) -> str:
    return f"""Redesign one complete 16:9 presentation slide.

The first image is target slide {page['target_slide']} and is the edit target and content authority.
The second image is reference slide {page['reference_slide']} and is visual-style authority only.

Preserve the target canvas ratio, content responsibilities, text regions, data relationships, chart meaning, table meaning, citations, and source-image meaning. Transfer the reference typography character, palette, spacing rhythm, visual hierarchy, decorative language, borders, and background treatment.

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
    command_prefix = list(command_prefix or ["editppt"])
    jobs = []

    for page in plan.get("pages", []):
        slide_number = int(page["target_slide"])
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
        prompt_path = root / prompt_rel
        output_path = root / output_rel
        if output_path.exists() and not force:
            raise JobError(f"generated page already exists: {output_path}")
        prompt_path.write_text(_prompt(page), encoding="utf-8")
        command = command_prefix + [
            "image",
            "edit",
            "--image",
            str(target),
            "--image",
            str(reference),
            "--prompt-file",
            str(prompt_path),
            "--size",
            "1920x1080",
            "--quality",
            "high",
            "--out",
            str(output_path),
        ]
        if force:
            command.append("--force")
        job = {
            "job_id": f"page-{slide_number:03d}",
            "target_slide": slide_number,
            "reference_slide": int(page["reference_slide"]),
            "target_image": target_rel,
            "target_sha256": _sha256(target),
            "reference_image": reference_rel,
            "reference_sha256": _sha256(reference),
            "prompt_file": prompt_rel,
            "prompt_sha256": _sha256(prompt_path),
            "output": output_rel,
            "output_sha256": None,
            "model": "gpt-image-2",
            "size": "1920x1080",
            "quality": "high",
            "command": command,
            "status": "ready",
            "error": None,
        }
        if execute:
            try:
                subprocess.run(command, check=True)
            except (OSError, subprocess.CalledProcessError) as exc:
                job["status"] = "failed"
                job["error"] = str(exc)
                jobs.append(job)
                manifest = {"schema": "ppt_visual_image_jobs.v1", "jobs": jobs}
                (root / "image-jobs.json").write_text(
                    json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
                    encoding="utf-8",
                )
                raise JobError(f"image generation failed for slide {slide_number}: {exc}") from exc
            if not output_path.is_file():
                raise JobError(f"image backend did not create output: {output_path}")
            job["status"] = "complete"
            job["output_sha256"] = _sha256(output_path)
        jobs.append(job)

    manifest = {
        "schema": "ppt_visual_image_jobs.v1",
        "execution_mode": "serial",
        "executed": execute,
        "jobs": jobs,
    }
    (root / "image-jobs.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description="Build serial target-plus-reference image edit jobs.")
    parser.add_argument("--run-dir", required=True)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    result = build_image_jobs(args.run_dir, execute=args.execute, force=args.force)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
