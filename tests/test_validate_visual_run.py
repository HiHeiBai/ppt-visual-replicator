import json
import hashlib
import sys
import tempfile
import unittest
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from tests.pptx_fixture import write_fixture_pptx


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "skills" / "ppt-visual-replicator" / "scripts"
sys.path.insert(0, str(SCRIPTS))

from pptx_inspect import inspect_pptx  # noqa: E402
from validate_visual_run import validate_visual_run  # noqa: E402


def write_png(path: Path, width: int = 1600, height: int = 900) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (width, height), "white").save(path)


def write_text_layout_drift_pair(source: Path, preview: Path) -> None:
    regular = ImageFont.load_default(size=28)
    bold = ImageFont.load_default(size=44)
    source_image = Image.new("RGB", (1600, 900), "white")
    preview_image = source_image.copy()
    source_draw = ImageDraw.Draw(source_image)
    preview_draw = ImageDraw.Draw(preview_image)
    for top in (210, 350, 490, 630):
        box = (100, top, 1500, top + 100)
        source_draw.rounded_rectangle(box, radius=10, fill="#F4F5F6")
        preview_draw.rounded_rectangle(box, radius=10, fill="#F4F5F6")
    title = "frontMIND: Research Background"
    source_draw.text((50, 50), title, font=bold, fill="#075B8A")
    preview_draw.text((50, 50), title, font=regular, fill="#075B8A")
    lines = (
        "Tafasitamab is a monoclonal antibody targeting CD19 on malignant B cells",
        "Lenalidomide expands and activates effector cells and enhances ADCC",
        "More than 40% of high-risk DLBCL patients cannot be cured",
        "Prior studies confirmed efficacy in relapsed or refractory DLBCL",
    )
    for top, line in zip((245, 385, 525, 665), lines):
        source_draw.text((170, top), line, font=regular, fill="#111111")
        preview_draw.text((170, top + 10), line, font=regular, fill="#111111")
    source_image.save(source)
    preview_image.save(preview)


def write_valid_run(root: Path) -> tuple[Path, Path, Path]:
    source_pptx = write_fixture_pptx(root / "source.pptx")
    source = inspect_pptx(source_pptx)
    run = root / "run"
    run.mkdir()
    (run / "source-ledger.json").write_text(json.dumps(source), encoding="utf-8")
    families = ["cover", "content", "content", "ending"]
    family_anchors = {"cover": 1, "content": 2, "ending": 4}
    pages = []
    jobs = []
    calibration_by_family = {}
    for slide, family in zip(source["slides"], families):
        number = slide["slide_number"]
        anchor = family_anchors[family]
        calibration_slide = calibration_by_family.setdefault(family, number)
        batch = "calibration" if calibration_slide == number else "scale"
        output = f"generated/page-{number:03d}.png"
        write_png(run / output)
        target = f"targets/page-{number:03d}.png"
        reference = f"references/reference-01/page-{anchor:03d}.png"
        prompt = f"prompts/page-{number:03d}.txt"
        for relative, payload in (
            (target, f"target-{number}".encode()),
            (reference, f"reference-{number}".encode()),
            (prompt, f"prompt-{number}".encode()),
        ):
            path = run / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            if not path.exists():
                path.write_bytes(payload)
        pages.append(
            {
                "target_slide": number,
                "target_family": family,
                "reference_index": 0,
                "reference_deck": "/tmp/reference.pptx",
                "reference_slide": anchor,
                "reference_image": reference,
                "match_mode": "family_anchor",
                "warning": None,
            }
        )
        jobs.append(
            {
                "job_id": f"page-{number:03d}",
                "target_slide": number,
                "target_family": family,
                "batch": batch,
                "reference_slide": anchor,
                "target_image": target,
                "target_sha256": hashlib.sha256((run / target).read_bytes()).hexdigest(),
                "reference_image": reference,
                "reference_sha256": hashlib.sha256((run / reference).read_bytes()).hexdigest(),
                "prompt_file": prompt,
                "prompt_sha256": hashlib.sha256((run / prompt).read_bytes()).hexdigest(),
                "output": output,
                "output_sha256": hashlib.sha256((run / output).read_bytes()).hexdigest(),
                "calibration_anchor": (
                    None if batch == "calibration" else f"generated/page-{calibration_slide:03d}.png"
                ),
                "calibration_anchor_sha256": (
                    None
                    if batch == "calibration"
                    else hashlib.sha256((run / f"generated/page-{calibration_slide:03d}.png").read_bytes()).hexdigest()
                ),
                "status": "complete",
            }
        )
    (run / "visual-plan.json").write_text(
        json.dumps(
            {
                "schema": "ppt_visual_plan.v1",
                "page_count": len(pages),
                "style_lock": {
                    "primary_reference_index": 0,
                    "primary_reference_deck": "/tmp/reference.pptx",
                    "allow_fallback_decks": False,
                    "anchor_policy": "one_per_family",
                },
                "pages": pages,
            }
        ),
        encoding="utf-8",
    )
    (run / "image-jobs.json").write_text(
        json.dumps({"schema": "ppt_visual_image_jobs.v1", "jobs": jobs}),
        encoding="utf-8",
    )
    approval_families = {}
    for job in jobs:
        if job["batch"] == "calibration":
            approval_families[job["target_family"]] = {
                "job_id": job["job_id"],
                "output": job["output"],
                "sha256": job["output_sha256"],
            }
    (run / "calibration-approved.json").write_text(
        json.dumps({"schema": "ppt_visual_calibration_approval.v1", "families": approval_families}),
        encoding="utf-8",
    )
    reconstruction_run = root / "reconstruction"
    reconstruction = reconstruction_run / "final" / "validation.json"
    reconstruction.parent.mkdir(parents=True)
    reconstruction.write_text(json.dumps({"passed": True, "slides": 4}), encoding="utf-8")
    reconstruction_pages = []
    for index, job in enumerate(jobs, start=1):
        page_id = f"page_{index:03d}"
        page_dir = reconstruction_run / "pages" / page_id
        page_dir.mkdir(parents=True)
        (page_dir / "preview.png").write_bytes((run / job["output"]).read_bytes())
        reconstruction_pages.append(
            {
                "page_id": page_id,
                "status": "recorded",
                "page_dir": f"pages/{page_id}",
            }
        )
    (reconstruction_run / "page_jobs.json").write_text(
        json.dumps({"pages": reconstruction_pages}),
        encoding="utf-8",
    )
    final_pptx = write_fixture_pptx(root / "final.pptx")
    return run, final_pptx, reconstruction


class ValidateVisualRunTest(unittest.TestCase):
    def test_generated_stage_rejects_reference_copy_drift(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            run, _, _ = write_valid_run(Path(temp_dir))
            target = run / "targets/page-003.png"
            reference = run / "references/reference-01/page-002.png"
            output = run / "generated/page-003.png"

            target_image = Image.new("RGB", (640, 360), "white")
            ImageDraw.Draw(target_image).rectangle((40, 80, 280, 300), fill="black")
            target_image.save(target)
            reference_image = Image.new("RGB", (640, 360), "white")
            ImageDraw.Draw(reference_image).rectangle((360, 40, 600, 320), fill="black")
            reference_image.save(reference)
            reference_image.save(output)

            jobs_path = run / "image-jobs.json"
            manifest = json.loads(jobs_path.read_text(encoding="utf-8"))
            job = next(item for item in manifest["jobs"] if item["target_slide"] == 3)
            job["target_sha256"] = hashlib.sha256(target.read_bytes()).hexdigest()
            job["reference_sha256"] = hashlib.sha256(reference.read_bytes()).hexdigest()
            job["output_sha256"] = hashlib.sha256(output.read_bytes()).hexdigest()
            jobs_path.write_text(json.dumps(manifest), encoding="utf-8")

            result = validate_visual_run(run, stage="generated")

            self.assertFalse(result["passed"])
            self.assertTrue(any("resembles the reference more than the target" in error for error in result["errors"]))

    def test_generated_stage_rejects_multiple_automatic_reference_decks(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            run, _, _ = write_valid_run(Path(temp_dir))
            plan_path = run / "visual-plan.json"
            plan = json.loads(plan_path.read_text(encoding="utf-8"))
            plan["pages"][2]["reference_index"] = 1
            plan["pages"][2]["reference_deck"] = "/tmp/secondary.pptx"
            plan_path.write_text(json.dumps(plan), encoding="utf-8")

            result = validate_visual_run(run, stage="generated")

            self.assertFalse(result["passed"])
            self.assertTrue(any("multiple automatic reference decks" in error for error in result["errors"]))

    def test_generated_stage_rejects_multiple_automatic_anchors_per_family(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            run, _, _ = write_valid_run(Path(temp_dir))
            plan_path = run / "visual-plan.json"
            plan = json.loads(plan_path.read_text(encoding="utf-8"))
            plan["pages"][2]["reference_slide"] = 3
            plan["pages"][2]["reference_image"] = "references/reference-01/page-003.png"
            plan_path.write_text(json.dumps(plan), encoding="utf-8")

            result = validate_visual_run(run, stage="generated")

            self.assertFalse(result["passed"])
            self.assertTrue(any("multiple automatic anchors" in error for error in result["errors"]))

    def test_generated_stage_rejects_scale_jobs_without_calibration_approval(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            run, _, _ = write_valid_run(Path(temp_dir))
            (run / "calibration-approved.json").unlink()

            result = validate_visual_run(run, stage="generated")

            self.assertFalse(result["passed"])
            self.assertTrue(any("calibration approval is required" in error for error in result["errors"]))

    def test_generated_stage_rejects_changed_approved_calibration_hash(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            run, _, _ = write_valid_run(Path(temp_dir))
            write_png(run / "generated/page-002.png", width=1920, height=1080)

            result = validate_visual_run(run, stage="generated")

            self.assertFalse(result["passed"])
            self.assertTrue(any("approved calibration hash changed" in error for error in result["errors"]))

    def test_generated_stage_rejects_missing_page(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            run, _, _ = write_valid_run(Path(temp_dir))
            (run / "generated/page-002.png").unlink()

            result = validate_visual_run(run, stage="generated")

            self.assertFalse(result["passed"])
            self.assertTrue(any("missing generated page" in error for error in result["errors"]))

    def test_final_stage_rejects_missing_critical_source_token(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            run, _, reconstruction = write_valid_run(root)
            final_pptx = write_fixture_pptx(
                root / "final-missing-token.pptx",
                slides=[
                    {"texts": ["Quarterly Review 2026"]},
                    {"texts": ["目录", "研究背景", "研究结果"]},
                    {"texts": ["主要结果", "数据已删除"], "pictures": 1, "table": True, "chart": True},
                    {"texts": ["THANK YOU"]},
                ],
            )

            result = validate_visual_run(
                run,
                stage="final",
                final_pptx=final_pptx,
                reconstruction_validation=reconstruction,
            )

            self.assertFalse(result["passed"])
            self.assertTrue(any("critical tokens" in error for error in result["errors"]))

    def test_final_stage_rejects_image_only_slides(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            run, _, reconstruction = write_valid_run(root)
            image_only = write_fixture_pptx(
                root / "image-only.pptx",
                slides=[{"texts": [], "pictures": 1} for _ in range(4)],
            )

            result = validate_visual_run(
                run,
                stage="final",
                final_pptx=image_only,
                reconstruction_validation=reconstruction,
            )

            self.assertFalse(result["passed"])
            self.assertTrue(any("image-only" in error for error in result["errors"]))

    def test_final_stage_accepts_editable_content_and_passed_reconstruction(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            run, final_pptx, reconstruction = write_valid_run(Path(temp_dir))

            result = validate_visual_run(
                run,
                stage="final",
                final_pptx=final_pptx,
                reconstruction_validation=reconstruction,
            )

            self.assertTrue(result["passed"], result)
            self.assertEqual(result["evidence"]["slides"], 4)
            self.assertEqual(result["evidence"]["critical_tokens_missing"], 0)
            self.assertTrue((run / "validation.json").is_file())

    def test_final_stage_rejects_editable_preview_visual_drift(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            run, final_pptx, reconstruction = write_valid_run(root)
            preview = reconstruction.parent.parent / "pages" / "page_001" / "preview.png"
            drifted = Image.new("RGB", (1600, 900), "white")
            ImageDraw.Draw(drifted).rectangle((0, 0, 800, 900), fill="black")
            drifted.save(preview)

            result = validate_visual_run(
                run,
                stage="final",
                final_pptx=final_pptx,
                reconstruction_validation=reconstruction,
            )

            self.assertFalse(result["passed"])
            self.assertTrue(any("editable preview visual drift" in error for error in result["errors"]))

    def test_final_stage_rejects_text_layout_drift_on_white_slide(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            run, final_pptx, reconstruction = write_valid_run(root)
            generated = run / "generated" / "page-003.png"
            preview = reconstruction.parent.parent / "pages" / "page_003" / "preview.png"
            write_text_layout_drift_pair(generated, preview)
            jobs_path = run / "image-jobs.json"
            jobs_payload = json.loads(jobs_path.read_text(encoding="utf-8"))
            for job in jobs_payload["jobs"]:
                if job["target_slide"] == 3:
                    job["output_sha256"] = hashlib.sha256(generated.read_bytes()).hexdigest()
            jobs_path.write_text(json.dumps(jobs_payload), encoding="utf-8")

            result = validate_visual_run(
                run,
                stage="final",
                final_pptx=final_pptx,
                reconstruction_validation=reconstruction,
            )

            self.assertFalse(result["passed"])
            self.assertTrue(any("editable preview visual drift" in error for error in result["errors"]))


if __name__ == "__main__":
    unittest.main()
