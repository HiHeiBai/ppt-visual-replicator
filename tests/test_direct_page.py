import json
import subprocess
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
    def test_prepares_direct_generation_without_rendering_the_target_slide(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            target = write_fixture_pptx(root / "target.pptx")
            source_image = root / "source-content.png"
            source_image.write_bytes(b"source-page-image")
            reference_image = root / "reference-style.png"
            reference_image.write_bytes(b"reference-page-image")

            manifest = prepare_direct_page(
                target,
                target_slide=2,
                source_image=source_image,
                reference_image=reference_image,
                reference_slide=3,
                run_dir=root / "run",
            )

            self.assertEqual(manifest["target_slide"], 2)
            self.assertEqual(manifest["style_mode"], "reference_set")
            self.assertEqual(manifest["reference_slide"], 3)
            self.assertEqual(manifest["reference_slides"], [3])
            self.assertEqual(manifest["source_image"], "source-content.png")
            self.assertEqual(manifest["reference_image"], "reference-style.png")
            self.assertEqual(manifest["reference_images"], ["reference-style.png"])
            self.assertEqual(manifest["source_ledger"], "source-ledger.json")
            self.assertEqual(manifest["content_spec"], "content-spec.json")
            self.assertFalse((root / "run" / "visual-plan.json").exists())
            self.assertFalse((root / "run" / "target.png").exists())
            self.assertEqual(
                (root / "run" / "source-content.png").read_bytes(),
                source_image.read_bytes(),
            )
            self.assertEqual(
                (root / "run" / "reference-style.png").read_bytes(),
                reference_image.read_bytes(),
            )
            source_ledger = (root / "run" / "source-ledger.json").read_text(encoding="utf-8")
            self.assertIn('"slide_number": 2', source_ledger)
            prompt = (root / "run" / "direct-image-prompt.txt").read_text(encoding="utf-8")
            self.assertIn("visual-style authority", prompt)
            self.assertIn("do not map one-to-one", prompt)
            self.assertIn("研究背景", prompt)

    def test_prepares_generation_without_a_reference_or_style_brief(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            target = write_fixture_pptx(root / "target.pptx")
            source_image = root / "source-content.png"
            source_image.write_bytes(b"source-page-image")

            manifest = prepare_direct_page(
                target,
                target_slide=2,
                source_image=source_image,
                run_dir=root / "run",
            )

            self.assertEqual(manifest["style_mode"], "default")
            self.assertEqual(manifest["reference_images"], [])
            self.assertEqual(manifest["inputs"]["references"], [])
            self.assertFalse((root / "run" / "reference-style.png").exists())
            prompt = (root / "run" / "direct-image-prompt.txt").read_text(encoding="utf-8")
            self.assertIn("No style-reference image was supplied", prompt)
            self.assertIn("Do not refuse or stop", prompt)

    def test_cli_runs_without_reference_arguments(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            target = write_fixture_pptx(root / "target.pptx")
            source_image = root / "source-content.png"
            source_image.write_bytes(b"source-page-image")

            result = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPTS / "prepare_direct_page.py"),
                    "--target",
                    str(target),
                    "--target-slide",
                    "2",
                    "--source-image",
                    str(source_image),
                    "--run-dir",
                    str(root / "run"),
                ],
                check=True,
                text=True,
                capture_output=True,
            )

            manifest = json.loads(result.stdout)
            self.assertEqual(manifest["style_mode"], "default")
            self.assertEqual(manifest["reference_images"], [])

    def test_prepares_generation_with_a_style_brief_only(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            target = write_fixture_pptx(root / "target.pptx")
            source_image = root / "source-content.png"
            source_image.write_bytes(b"source-page-image")

            manifest = prepare_direct_page(
                target,
                target_slide=2,
                source_image=source_image,
                style_brief="warm editorial style",
                run_dir=root / "run",
            )

            self.assertEqual(manifest["style_mode"], "brief")
            prompt = (root / "run" / "direct-image-prompt.txt").read_text(encoding="utf-8")
            self.assertIn("Explicit style brief: warm editorial style", prompt)

    def test_accepts_a_shared_reference_set_independent_of_target_page_count(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            target = write_fixture_pptx(root / "target.pptx")
            source_image = root / "source-content.png"
            source_image.write_bytes(b"source-page-image")
            references = [root / "style-a.png", root / "style-b.png"]
            for index, reference in enumerate(references):
                reference.write_bytes(f"style-{index}".encode())

            manifest = prepare_direct_page(
                target,
                target_slide=2,
                source_image=source_image,
                reference_image=references,
                reference_slide=[7, 12],
                run_dir=root / "run",
            )

            self.assertEqual(
                manifest["reference_images"],
                ["reference-style-01.png", "reference-style-02.png"],
            )
            self.assertEqual(manifest["reference_slides"], [7, 12])
            self.assertIsNone(manifest["reference_image"])
            prompt = (root / "run" / "direct-image-prompt.txt").read_text(encoding="utf-8")
            self.assertIn("shared style-reference set", prompt)
            self.assertIn("may be reused for every target page", prompt)

    def test_rejects_a_page_number_outside_the_input_deck(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            target = write_fixture_pptx(root / "target.pptx")
            source_image = root / "source-content.png"
            source_image.write_bytes(b"source-page-image")
            reference_image = root / "reference-style.png"
            reference_image.write_bytes(b"reference-page-image")

            with self.assertRaisesRegex(DirectRunError, "target slide does not exist"):
                prepare_direct_page(
                    target,
                    target_slide=99,
                    source_image=source_image,
                    reference_image=reference_image,
                    reference_slide=1,
                    run_dir=root / "run",
                )


if __name__ == "__main__":
    unittest.main()
