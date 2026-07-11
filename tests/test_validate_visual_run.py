import json
import hashlib
import struct
import sys
import tempfile
import unittest
import zlib
from pathlib import Path

from tests.pptx_fixture import write_fixture_pptx


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "skills" / "ppt-visual-replicator" / "scripts"
sys.path.insert(0, str(SCRIPTS))

from pptx_inspect import inspect_pptx  # noqa: E402
from validate_visual_run import validate_visual_run  # noqa: E402


def write_png(path: Path, width: int = 1600, height: int = 900) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    signature = b"\x89PNG\r\n\x1a\n"
    ihdr_data = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)

    def chunk(kind: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)

    path.write_bytes(signature + chunk(b"IHDR", ihdr_data) + chunk(b"IEND", b""))


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
    reconstruction = root / "reconstruction-validation.json"
    reconstruction.write_text(json.dumps({"passed": True, "slides": 4}), encoding="utf-8")
    final_pptx = write_fixture_pptx(root / "final.pptx")
    return run, final_pptx, reconstruction


class ValidateVisualRunTest(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
