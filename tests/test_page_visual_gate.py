import hashlib
import sys
import tempfile
import unittest
from pathlib import Path

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
            write_reference(content, "#333333", offset=20)
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


if __name__ == "__main__":
    unittest.main()
