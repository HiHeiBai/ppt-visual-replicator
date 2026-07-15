import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "skills" / "ppt-visual-replicator" / "scripts"
sys.path.insert(0, str(SCRIPTS))

from normalize_global_chrome import normalize_run  # noqa: E402


class NormalizeGlobalChromeTest(unittest.TestCase):
    def test_normalizes_chrome_idempotently_and_preserves_source_tag(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            run = root / "run"
            page = run / "pages" / "page_003"
            assets = page / "assets"
            assets.mkdir(parents=True)
            (assets / "old-page-marker.png").write_bytes(b"old")
            marker = root / "marker.png"
            marker.write_bytes(b"marker")
            manifest = {
                "source": {"width_px": 1920, "height_px": 1080},
                "text_inventory": [{"id": "brand", "text": "Oral-7000"}],
                "text_boxes": [
                    {"id": "title", "text": "研究背景", "box_px": [60, 50, 800, 60], "font_size": 24},
                    {"id": "footer-left", "text": "Footer", "box_px": [120, 1000, 500, 30], "font_size": 9},
                    {"id": "tag", "text": "Oral-7000", "box_px": [1720, 50, 160, 30]},
                    {"id": "page-number", "text": "3", "box_px": [40, 1000, 60, 40]},
                ],
                "shapes": [{"id": "tag-panel", "type": "roundRect", "box_px": [1700, 40, 180, 50]}],
                "images": [
                    {
                        "id": "page-number-badge",
                        "path": "assets/old-page-marker.png",
                        "box_px": [35, 990, 70, 70],
                    }
                ],
                "asset_provenance": [
                    {
                        "path": "assets/old-page-marker.png",
                        "source": "assets/old-page-marker.png",
                        "source_type": "user-provided",
                        "provenance_note": "old",
                    }
                ],
            }
            (page / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
            config = {
                "page_range": [3, 3],
                "font": "Microsoft YaHei",
                "title": {"size": 31},
                "footer": {"size": 11},
                "top_tag": {"fill": "#0A479E"},
                "page_marker": {"asset": str(marker)},
            }
            config_path = root / "chrome.json"
            config_path.write_text(json.dumps(config), encoding="utf-8")

            first = normalize_run(run, config_path)
            second = normalize_run(run, config_path)
            normalized = json.loads((page / "manifest.json").read_text(encoding="utf-8"))

            self.assertEqual(first["page_count"], 1)
            self.assertEqual(second["page_count"], 1)
            self.assertEqual([item["id"] for item in normalized["images"]], ["global-page-marker"])
            self.assertEqual(
                [item["id"] for item in normalized["text_boxes"] if item["id"] == "global-page-number"],
                ["global-page-number"],
            )
            self.assertEqual(
                [item["text"] for item in normalized["text_boxes"] if item["id"] == "global-top-tag-text"],
                ["Oral-7000"],
            )
            title = next(item for item in normalized["text_boxes"] if item["id"] == "title")
            footer = next(item for item in normalized["text_boxes"] if item["id"] == "footer-left")
            self.assertEqual(title["font"], "Microsoft YaHei")
            self.assertEqual(title["font_size"], 31.0)
            self.assertEqual(footer["font_size"], 11.0)
            self.assertEqual(first["warnings"], [])

    def test_scales_chrome_independently_for_four_by_three_slides(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            run = root / "run"
            page = run / "pages" / "page_001"
            page.mkdir(parents=True)
            marker = root / "marker.png"
            marker.write_bytes(b"marker")
            (page / "manifest.json").write_text(
                json.dumps(
                    {
                        "source": {"width_px": 1600, "height_px": 1200},
                        "text_boxes": [],
                        "shapes": [],
                        "images": [],
                        "asset_provenance": [],
                    }
                ),
                encoding="utf-8",
            )
            config_path = root / "chrome.json"
            config_path.write_text(
                json.dumps({"page_range": [1, 1], "page_marker": {"asset": str(marker)}}),
                encoding="utf-8",
            )

            normalize_run(run, config_path)
            normalized = json.loads((page / "manifest.json").read_text(encoding="utf-8"))
            marker_box = normalized["images"][-1]["box_px"]

            self.assertEqual(marker_box, [26.7, 1110.6, 58.3, 58.3])


if __name__ == "__main__":
    unittest.main()
