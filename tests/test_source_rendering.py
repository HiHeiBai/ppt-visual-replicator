import json
import struct
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tests.pptx_fixture import write_fixture_pptx


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "skills" / "ppt-visual-replicator" / "scripts"
sys.path.insert(0, str(SCRIPTS))

from prepare_direct_deck import prepare_direct_deck  # noqa: E402
from prepare_direct_page import prepare_direct_page  # noqa: E402
from render_source_pages import SourceRenderError, render_pptx_to_pngs  # noqa: E402


def write_png_header(path: Path, width: int = 2560, height: int = 1440) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00\x00\x00\rIHDR" + struct.pack(">II", width, height))


def fake_render_report(pptx, out_dir, *, ledger, first_slide=None, last_slide=None, **_kwargs):
    destination = Path(out_dir)
    destination.mkdir(parents=True)
    start = first_slide or 1
    end = last_slide or int(ledger["slide_count"])
    pages = []
    for slide_number in range(start, end + 1):
        page = destination / f"slide-{slide_number:03d}.png"
        write_png_header(page)
        pages.append(
            {
                "slide_number": slide_number,
                "path": str(page),
                "width_px": 2560,
                "height_px": 1440,
                "sha256": f"sha-{slide_number}",
            }
        )
    report = {
        "schema": "ppt_visual_source_render.v1",
        "source_pptx": str(Path(pptx).resolve()),
        "source_sha256": ledger["sha256"],
        "deck_slide_count": ledger["slide_count"],
        "rendered_slide_count": len(pages),
        "first_slide": start,
        "last_slide": end,
        "dpi": 192,
        "renderer": {"office": "fake-office", "rasterizer": "fake-pdftoppm"},
        "pages": pages,
    }
    (destination / "render-report.json").write_text(json.dumps(report), encoding="utf-8")
    return report


class SourceRenderingTest(unittest.TestCase):
    def test_renders_selected_pages_once_and_validates_the_result(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            target = write_fixture_pptx(root / "target.pptx")

            def fake_runner(command, **_kwargs):
                if "-t" in command:
                    output = Path(command[command.index("-o") + 1])
                    slide_number = int(Path(command[-1]).stem.rsplit("-", 1)[-1])
                    write_png_header(output / f"slide-{slide_number:03d}.png")
                elif "--convert-to" in command:
                    out_dir = Path(command[command.index("--outdir") + 1])
                    (out_dir / "target.pdf").write_bytes(b"%PDF-1.4")
                else:
                    prefix = Path(command[-1])
                    first = int(command[command.index("-f") + 1])
                    last = int(command[command.index("-l") + 1])
                    for page_number in range(first, last + 1):
                        write_png_header(prefix.with_name(f"{prefix.name}-{page_number}.png"))
                return subprocess.CompletedProcess(command, 0, "", "")

            report = render_pptx_to_pngs(
                target,
                root / "source-pages",
                first_slide=2,
                last_slide=3,
                runner=fake_runner,
                tool_lookup=lambda name: f"/fake/{name}",
            )

            self.assertEqual(report["deck_slide_count"], 4)
            self.assertEqual(report["rendered_slide_count"], 2)
            self.assertEqual([page["slide_number"] for page in report["pages"]], [2, 3])
            self.assertTrue((root / "source-pages" / "slide-002.png").is_file())
            self.assertTrue((root / "source-pages" / "render-report.json").is_file())

    def test_reports_missing_render_dependencies(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            target = write_fixture_pptx(root / "target.pptx")

            with self.assertRaisesRegex(SourceRenderError, "dependency is unavailable"):
                render_pptx_to_pngs(
                    target,
                    root / "source-pages",
                    tool_lookup=lambda _name: None,
                )

    def test_direct_page_auto_renders_when_source_image_is_omitted(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            target = write_fixture_pptx(root / "target.pptx")

            with patch("prepare_direct_page.render_pptx_to_pngs", side_effect=fake_render_report):
                manifest = prepare_direct_page(
                    target,
                    target_slide=2,
                    run_dir=root / "run",
                )

            self.assertEqual(manifest["inputs"]["source"]["mode"], "auto-rendered-pptx")
            self.assertEqual(manifest["inputs"]["source"]["target_slide"], 2)
            self.assertEqual(manifest["text_protection_mode"], "visual-ocr")
            self.assertEqual(manifest["source_render_report"], "source-render-report.json")
            self.assertTrue((root / "run" / "source-content.png").is_file())
            self.assertTrue((root / "run" / "source-render-report.json").is_file())

    def test_direct_deck_renders_once_and_prepares_every_slide(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            target = write_fixture_pptx(root / "target.pptx")
            calls = []

            def renderer(*args, **kwargs):
                calls.append((args, kwargs))
                return fake_render_report(*args, **kwargs)

            manifest = prepare_direct_deck(
                target,
                root / "deck-run",
                renderer=renderer,
            )

            self.assertEqual(len(calls), 1)
            self.assertEqual(manifest["slide_count"], 4)
            self.assertEqual(len(manifest["pages"]), 4)
            self.assertEqual(manifest["style_mode"], "default")
            self.assertEqual(manifest["text_protection_mode"], "visual-ocr")
            for slide_number in range(1, 5):
                page_dir = root / "deck-run" / "pages" / f"slide-{slide_number:03d}"
                self.assertTrue((page_dir / "source-content.png").is_file())
                self.assertTrue((page_dir / "direct-image-prompt.txt").is_file())
                page_manifest = json.loads((page_dir / "run.json").read_text(encoding="utf-8"))
                self.assertEqual(page_manifest["inputs"]["source"]["mode"], "auto-rendered-pptx")

    def test_strict_mode_promotes_native_text_to_required_content(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            target = write_fixture_pptx(root / "target.pptx")
            source_image = root / "source.png"
            write_png_header(source_image)

            manifest = prepare_direct_page(
                target,
                target_slide=3,
                source_image=source_image,
                strict_text_protection=True,
                run_dir=root / "run",
            )

            content_spec = json.loads((root / "run" / "content-spec.json").read_text(encoding="utf-8"))
            prompt = (root / "run" / "direct-image-prompt.txt").read_text(encoding="utf-8")
            self.assertEqual(manifest["text_protection_mode"], "strict-native")
            self.assertIn("HR=0.75", content_spec["required_text"])
            self.assertIn("HR=0.75", content_spec["critical_tokens"])
            self.assertIn("must remain present and exact", prompt)


if __name__ == "__main__":
    unittest.main()
