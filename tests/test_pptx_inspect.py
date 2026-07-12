import sys
import tempfile
import unittest
from pathlib import Path

from tests.pptx_fixture import write_fixture_pptx


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "skills" / "ppt-visual-replicator" / "scripts"
sys.path.insert(0, str(SCRIPTS))

from pptx_inspect import InputError, inspect_pptx  # noqa: E402


class PptxInspectTest(unittest.TestCase):
    def test_inspects_ordered_slides_and_native_content(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = write_fixture_pptx(Path(temp_dir) / "fixture.pptx")

            result = inspect_pptx(path)

        self.assertEqual(result["schema"], "ppt_visual_source.v1")
        self.assertEqual(result["slide_count"], 4)
        self.assertEqual(result["slide_size"]["width_emu"], 12192000)
        self.assertEqual(result["slide_size"]["height_emu"], 6858000)
        self.assertAlmostEqual(result["slide_size"]["aspect_ratio"], 16 / 9, places=3)
        self.assertEqual([slide["slide_number"] for slide in result["slides"]], [1, 2, 3, 4])
        self.assertEqual(result["slides"][1]["family_hint"], "toc")
        self.assertEqual(result["slides"][2]["picture_count"], 1)
        self.assertEqual(result["slides"][2]["table_count"], 1)
        self.assertEqual(result["slides"][2]["chart_count"], 1)
        self.assertEqual(result["slides"][3]["family_hint"], "ending")
        self.assertIn("71.1%", result["slides"][2]["critical_tokens"])
        self.assertEqual(len(result["sha256"]), 64)

    def test_rejects_office_lock_files(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / ".~fixture.pptx"
            path.touch()

            with self.assertRaisesRegex(InputError, "Office lock"):
                inspect_pptx(path)

    def test_classifies_spaced_chinese_toc_marker(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = write_fixture_pptx(
                Path(temp_dir) / "spaced-toc.pptx",
                slides=[
                    {"texts": ["Title"]},
                    {"texts": ["目 录", "研究背景", "研究结果"]},
                    {"texts": ["THANK YOU"]},
                ],
            )

            result = inspect_pptx(path)

        self.assertEqual(result["slides"][1]["family_hint"], "toc")

    def test_classifies_single_evidence_image_page_as_image_content(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = write_fixture_pptx(
                Path(temp_dir) / "evidence-image.pptx",
                slides=[
                    {"texts": ["Title"]},
                    {"texts": ["Study title", "2026 ASCO LBA 7000"], "pictures": 1},
                    {"texts": ["THANK YOU"]},
                ],
            )

            result = inspect_pptx(path)

        self.assertEqual(result["slides"][1]["family_hint"], "image_content")


if __name__ == "__main__":
    unittest.main()
