import hashlib
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import Image, ImageDraw


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "skills" / "ppt-visual-replicator" / "scripts"
sys.path.insert(0, str(SCRIPTS))

from verify_page_visual import verify_page_visual  # noqa: E402


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_reference(path: Path, color: str, *, offset: int = 0) -> None:
    image = Image.new("RGB", (1280, 720), "white")
    draw = ImageDraw.Draw(image)
    draw.rectangle((80 + offset, 90, 1200, 180), fill=color)
    draw.rectangle((120, 240, 1160, 650), outline=color, width=8)
    image.save(path)


class PageVisualGateTest(unittest.TestCase):
    def test_records_visual_and_content_references(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            visual = root / "generated.png"
            content = root / "source-content.png"
            rendered = root / "rendered.png"
            write_reference(visual, "#005587")
            write_reference(content, "#005587")
            write_reference(rendered, "#005587")

            result = verify_page_visual(
                visual,
                content_source_path=content,
                page_pptx=None,
                rendered_image=rendered,
                out_dir=root / "qa",
                accept=False,
                accept_visual=True,
                accept_content=True,
            )

            self.assertTrue(result["passed"])
            self.assertEqual(result["schema"], "ppt_visual_page_gate.v2")
            self.assertEqual(result["source_sha256"], sha256(visual))
            self.assertEqual(result["content_source_sha256"], sha256(content))
            self.assertTrue(result["checks"]["visual_reference_match"])
            self.assertTrue(result["checks"]["original_content_reviewed"])
            self.assertTrue((root / "qa" / "content-side-by-side.png").is_file())
            self.assertTrue((root / "qa" / "content-difference.png").is_file())

    def test_rejects_dual_reference_gate_without_content_acceptance(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            visual = root / "generated.png"
            content = root / "source-content.png"
            rendered = root / "rendered.png"
            write_reference(visual, "#005587")
            write_reference(content, "#333333")
            write_reference(rendered, "#005587")

            result = verify_page_visual(
                visual,
                content_source_path=content,
                page_pptx=None,
                rendered_image=rendered,
                out_dir=root / "qa",
                accept=False,
                accept_visual=True,
                accept_content=False,
            )

            self.assertFalse(result["passed"])
            self.assertFalse(result["checks"]["original_content_reviewed"])

    def test_native_seed_uses_coarse_generated_metrics_and_exact_content_metrics(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            visual = root / "generated.png"
            content = root / "source-content.png"
            rendered = root / "rendered.png"
            write_reference(visual, "#005587")
            write_reference(content, "#333333")
            write_reference(rendered, "#005587")
            visual_metrics = {
                "pixel_mean_distance": 10.0,
                "structure_distance": 5.0,
                "ink_projection_distance": 0.9,
                "title_pixel_mean_distance": 90.0,
                "title_structure_distance": 90.0,
            }
            content_metrics = {
                "pixel_mean_distance": 2.0,
                "structure_distance": 1.0,
                "ink_projection_distance": 0.1,
                "title_pixel_mean_distance": 2.0,
                "title_structure_distance": 1.0,
            }

            with patch("verify_page_visual._metrics", side_effect=[visual_metrics, content_metrics]):
                result = verify_page_visual(
                    visual,
                    content_source_path=content,
                    page_pptx=None,
                    rendered_image=rendered,
                    out_dir=root / "qa",
                    accept=False,
                    accept_visual=True,
                    accept_content=True,
                    native_seed=True,
                )

            self.assertTrue(result["passed"])
            self.assertTrue(result["native_seed"])

    def test_native_seed_still_rejects_original_content_drift(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            visual = root / "generated.png"
            content = root / "source-content.png"
            rendered = root / "rendered.png"
            write_reference(visual, "#005587")
            write_reference(content, "#333333")
            write_reference(rendered, "#005587")
            visual_metrics = {
                "pixel_mean_distance": 10.0,
                "structure_distance": 5.0,
                "ink_projection_distance": 0.9,
                "title_pixel_mean_distance": 90.0,
                "title_structure_distance": 90.0,
            }
            content_metrics = dict(visual_metrics, pixel_mean_distance=40.0)

            with patch("verify_page_visual._metrics", side_effect=[visual_metrics, content_metrics]):
                result = verify_page_visual(
                    visual,
                    content_source_path=content,
                    page_pptx=None,
                    rendered_image=rendered,
                    out_dir=root / "qa",
                    accept=False,
                    accept_visual=True,
                    accept_content=True,
                    native_seed=True,
                )

            self.assertFalse(result["passed"])
            self.assertFalse(result["checks"]["original_content_reviewed"])


if __name__ == "__main__":
    unittest.main()
