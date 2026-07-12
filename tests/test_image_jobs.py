import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "skills" / "ppt-visual-replicator" / "scripts"
sys.path.insert(0, str(SCRIPTS))

from build_image_jobs import (  # noqa: E402
    JobError,
    approve_calibration,
    build_image_jobs,
    execute_image_jobs,
)


def write_run(root: Path, page_count: int = 2, families=None) -> Path:
    families = families or ["content"] * page_count
    for directory in ("targets", "references/reference-01", "prompts", "generated"):
        (root / directory).mkdir(parents=True, exist_ok=True)
    pages = []
    for number in range(1, page_count + 1):
        target = root / f"targets/page-{number:03d}.png"
        reference = root / f"references/reference-01/page-{number:03d}.png"
        target.write_bytes(f"target-{number}".encode())
        reference.write_bytes(f"reference-{number}".encode())
        pages.append(
            {
                "target_slide": number,
                "target_family": families[number - 1],
                "target_image": str(target.relative_to(root)),
                "reference_index": 0,
                "reference_deck": "/tmp/reference.pptx",
                "reference_slide": number,
                "reference_image": str(reference.relative_to(root)),
                "match_mode": "same_family",
                "warning": None,
            }
        )
    (root / "visual-plan.json").write_text(
        json.dumps({"schema": "ppt_visual_plan.v1", "page_count": page_count, "pages": pages}),
        encoding="utf-8",
    )
    return root


class ImageJobsTest(unittest.TestCase):
    def test_builds_deterministic_target_then_reference_jobs(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            run_dir = write_run(Path(temp_dir) / "run")

            manifest = build_image_jobs(run_dir)

            self.assertEqual(len(manifest["jobs"]), 2)
            first = manifest["jobs"][0]
            second = manifest["jobs"][1]
            self.assertEqual(first["status"], "ready")
            self.assertEqual(first["batch"], "calibration")
            self.assertEqual(second["batch"], "scale")
            self.assertEqual(second["calibration_anchor"], first["output"])
            self.assertEqual(len(first["target_sha256"]), 64)
            self.assertEqual(len(first["reference_sha256"]), 64)
            self.assertEqual(len(first["prompt_sha256"]), 64)
            self.assertIsNone(first["output_sha256"])
            self.assertEqual(first["size"], "2560x1440")
            self.assertEqual(first["command"][first["command"].index("--size") + 1], "2560x1440")
            images = [first["command"][i + 1] for i, value in enumerate(first["command"]) if value == "--image"]
            self.assertEqual(
                images,
                [
                    str(run_dir.resolve() / first["target_image"]),
                    str(run_dir.resolve() / first["reference_image"]),
                ],
            )
            self.assertIn("Do not copy reference wording", (run_dir / first["prompt_file"]).read_text())
            self.assertTrue((run_dir / "image-jobs.json").is_file())

    def test_executes_jobs_serially_and_records_output_hashes(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            run_dir = write_run(root / "run")
            log = root / "calls.log"
            fake = root / "fake_editppt.py"
            fake.write_text(
                "import pathlib, sys\n"
                "args = sys.argv[1:]\n"
                f"pathlib.Path({str(log.resolve())!r}).open('a').write(args[args.index('--out') + 1] + '\\n')\n"
                "pathlib.Path(args[args.index('--out') + 1]).write_bytes(b'generated-image')\n",
                encoding="utf-8",
            )

            build_image_jobs(run_dir)
            execute_image_jobs(
                run_dir,
                phase="calibration",
                command_prefix=[sys.executable, str(fake)],
            )
            with self.assertRaisesRegex(JobError, "calibration approval"):
                execute_image_jobs(
                    run_dir,
                    phase="scale",
                    command_prefix=[sys.executable, str(fake)],
                )
            approval = approve_calibration(run_dir)
            self.assertEqual(set(approval["families"]), {"content"})
            manifest = execute_image_jobs(
                run_dir,
                phase="scale",
                command_prefix=[sys.executable, str(fake)],
            )

            calls = log.read_text(encoding="utf-8").splitlines()
            self.assertEqual(
                calls,
                [
                    str(run_dir.resolve() / "generated/page-001.png"),
                    str(run_dir.resolve() / "generated/page-002.png"),
                ],
            )
            self.assertTrue(all(job["status"] == "complete" for job in manifest["jobs"]))
            self.assertTrue(all(job["output_sha256"] for job in manifest["jobs"]))
            scale = next(job for job in manifest["jobs"] if job["batch"] == "scale")
            images = [scale["command"][i + 1] for i, value in enumerate(scale["command"]) if value == "--image"]
            self.assertEqual(
                images,
                [
                    str(run_dir.resolve() / scale["target_image"]),
                    str(run_dir.resolve() / "generated/page-001.png"),
                ],
            )
            scale_prompt = (run_dir / scale["prompt_file"]).read_text(encoding="utf-8")
            self.assertIn("approved calibration slide's layout skeleton", scale_prompt)
            self.assertIn("Do not preserve the target's original visual layout", scale_prompt)

    def test_first_page_of_each_family_is_a_calibration_job(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            run_dir = write_run(
                Path(temp_dir) / "run",
                page_count=4,
                families=["cover", "content", "content", "table"],
            )

            manifest = build_image_jobs(run_dir)

            batches = [(job["target_slide"], job["target_family"], job["batch"]) for job in manifest["jobs"]]
            self.assertEqual(
                batches,
                [
                    (1, "cover", "direct"),
                    (2, "content", "calibration"),
                    (3, "content", "scale"),
                    (4, "table", "direct"),
                ],
            )

    def test_single_page_family_runs_directly_without_calibration_approval(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            run_dir = write_run(root / "run", page_count=1, families=["content"])
            fake = root / "fake_editppt.py"
            fake.write_text(
                "import pathlib, sys\n"
                "args = sys.argv[1:]\n"
                "pathlib.Path(args[args.index('--out') + 1]).write_bytes(b'generated-image')\n",
                encoding="utf-8",
            )

            manifest = build_image_jobs(run_dir)
            self.assertEqual(manifest["jobs"][0]["batch"], "direct")
            completed = execute_image_jobs(
                run_dir,
                phase="calibration",
                command_prefix=[sys.executable, str(fake)],
            )

            self.assertEqual(completed["jobs"][0]["status"], "complete")
            self.assertFalse((run_dir / "calibration-approved.json").exists())

    def test_prompt_preserves_target_recurring_identifiers_and_footer(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            run_dir = write_run(Path(temp_dir) / "run", page_count=1)

            manifest = build_image_jobs(run_dir)

            prompt = (run_dir / manifest["jobs"][0]["prompt_file"]).read_text(encoding="utf-8")
            self.assertIn("target logos", prompt)
            self.assertIn("target page numbers", prompt)
            self.assertIn("confidentiality notices", prompt)
            self.assertIn("document codes", prompt)
            self.assertIn("target footer", prompt)
            self.assertIn("inside the canvas with safe margins", prompt)
            self.assertIn("at least 3% inset", prompt)
            self.assertIn("Do not crop or clip", prompt)
            self.assertIn("Reference-only brand marks", prompt)

    def test_retries_one_transient_image_backend_failure(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            run_dir = write_run(root / "run", page_count=1)
            counter = root / "counter.txt"
            fake = root / "flaky_editppt.py"
            fake.write_text(
                "import pathlib, sys\n"
                f"counter = pathlib.Path({str(counter)!r})\n"
                "attempt = int(counter.read_text()) + 1 if counter.exists() else 1\n"
                "counter.write_text(str(attempt))\n"
                "if attempt == 1: raise SystemExit(1)\n"
                "args = sys.argv[1:]\n"
                "pathlib.Path(args[args.index('--out') + 1]).write_bytes(b'generated-image')\n",
                encoding="utf-8",
            )
            build_image_jobs(run_dir)

            try:
                manifest = execute_image_jobs(
                    run_dir,
                    phase="calibration",
                    command_prefix=[sys.executable, str(fake)],
                )
            except JobError as exc:
                self.fail(f"image backend did not retry: {exc}")

            self.assertEqual(counter.read_text(), "2")
            self.assertEqual(manifest["jobs"][0]["status"], "complete")

    def test_refuses_to_overwrite_generated_pages_without_force(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            run_dir = write_run(Path(temp_dir) / "run", page_count=1)
            (run_dir / "generated/page-001.png").write_bytes(b"existing")

            with self.assertRaisesRegex(JobError, "already exists"):
                build_image_jobs(run_dir)


if __name__ == "__main__":
    unittest.main()
