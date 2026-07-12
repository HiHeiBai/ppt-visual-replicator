import sys
import tempfile
import unittest
from pathlib import Path

from tests.pptx_fixture import write_fixture_pptx


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "skills" / "ppt-visual-replicator" / "scripts"
sys.path.insert(0, str(SCRIPTS))

from prepare_direct_page import DirectRunError, prepare_direct_page  # noqa: E402


class DirectPageTest(unittest.TestCase):
    def test_prepares_one_explicit_target_and_reference_page_without_a_plan(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            target = write_fixture_pptx(root / "target.pptx")
            reference = write_fixture_pptx(root / "reference.pptx")

            manifest = prepare_direct_page(
                target,
                reference,
                target_slide=2,
                reference_slide=3,
                run_dir=root / "run",
                skip_render=True,
            )

            self.assertEqual(manifest["target_slide"], 2)
            self.assertEqual(manifest["reference_slide"], 3)
            self.assertEqual(manifest["target_image"], "target.png")
            self.assertEqual(manifest["reference_image"], "reference.png")
            self.assertEqual(manifest["source_ledger"], "source-ledger.json")
            self.assertFalse((root / "run" / "visual-plan.json").exists())
            source_ledger = (root / "run" / "source-ledger.json").read_text(encoding="utf-8")
            self.assertIn('"slide_number": 2', source_ledger)
            prompt = (root / "run" / "image-edit-prompt.txt").read_text(encoding="utf-8")
            self.assertIn("first image is the target slide", prompt)
            self.assertIn("second image is the reference style", prompt)

    def test_rejects_a_page_number_outside_the_input_deck(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            target = write_fixture_pptx(root / "target.pptx")
            reference = write_fixture_pptx(root / "reference.pptx")

            with self.assertRaisesRegex(DirectRunError, "target slide does not exist"):
                prepare_direct_page(
                    target,
                    reference,
                    target_slide=99,
                    reference_slide=1,
                    run_dir=root / "run",
                    skip_render=True,
                )


if __name__ == "__main__":
    unittest.main()
