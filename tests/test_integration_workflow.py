import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

from tests.pptx_fixture import write_fixture_pptx
from tests.test_validate_visual_run import write_png


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "skills" / "ppt-visual-replicator" / "scripts"
sys.path.insert(0, str(SCRIPTS))

from build_image_jobs import build_image_jobs  # noqa: E402
from build_visual_plan import build_plan  # noqa: E402
from prepare_visual_run import prepare_visual_run  # noqa: E402
from validate_visual_run import validate_recorded_editppt_run, validate_visual_run  # noqa: E402


class IntegrationWorkflowTest(unittest.TestCase):
    def test_four_page_prepare_plan_generate_and_validate_flow(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            target = write_fixture_pptx(root / "target.pptx")
            reference = write_fixture_pptx(root / "reference.pptx")
            run = root / "run"
            prepare_visual_run(target, [reference], run, skip_render=True)
            source = json.loads((run / "source-ledger.json").read_text(encoding="utf-8"))
            references = json.loads((run / "reference-ledger.json").read_text(encoding="utf-8"))
            for number in range(1, 5):
                write_png(run / f"targets/page-{number:03d}.png")
                write_png(run / f"references/reference-01/page-{number:03d}.png")
            plan = build_plan(source, references)
            (run / "visual-plan.json").write_text(json.dumps(plan), encoding="utf-8")

            template = root / "generated-template.png"
            write_png(template, 1920, 1080)
            fake = root / "fake_editppt.py"
            fake.write_text(
                "import pathlib, shutil, sys\n"
                "args = sys.argv[1:]\n"
                f"shutil.copyfile({str(template)!r}, args[args.index('--out') + 1])\n",
                encoding="utf-8",
            )
            build_image_jobs(run, execute=True, command_prefix=[sys.executable, str(fake)])

            result = validate_visual_run(run, stage="generated")

            self.assertTrue(result["passed"], result)
            self.assertEqual(result["evidence"]["generated_pages"], 4)
            self.assertEqual(len(json.loads((run / "image-jobs.json").read_text())["jobs"]), 4)

    @unittest.skipUnless(os.environ.get("PPT_VISUAL_HISTORICAL_RUN"), "historical run path not configured")
    def test_existing_editppt_run_remains_a_valid_regression_fixture(self) -> None:
        result = validate_recorded_editppt_run(Path(os.environ["PPT_VISUAL_HISTORICAL_RUN"]))

        self.assertTrue(result["passed"], result)
        self.assertEqual(result["evidence"]["slides"], 13)
        self.assertEqual(result["evidence"]["page_validations_passed"], 13)


if __name__ == "__main__":
    unittest.main()
