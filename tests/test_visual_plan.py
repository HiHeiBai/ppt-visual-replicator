import json
import sys
import tempfile
import unittest
from pathlib import Path

from tests.pptx_fixture import write_fixture_pptx


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "skills" / "ppt-visual-replicator" / "scripts"
sys.path.insert(0, str(SCRIPTS))

from build_visual_plan import PlanError, build_plan  # noqa: E402
from prepare_visual_run import RunError, prepare_visual_run  # noqa: E402


class VisualPlanTest(unittest.TestCase):
    def test_prepare_creates_relative_run_contract_without_overwrite(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            target = write_fixture_pptx(root / "target.pptx")
            reference = write_fixture_pptx(root / "reference.pptx")
            run_dir = root / "run"

            manifest = prepare_visual_run(target, [reference], run_dir, skip_render=True)

            self.assertEqual(manifest["source_ledger"], "source-ledger.json")
            self.assertEqual(manifest["reference_ledger"], "reference-ledger.json")
            self.assertEqual(manifest["target_render_dir"], "targets")
            self.assertEqual(manifest["reference_render_dir"], "references")
            self.assertTrue((run_dir / "source-ledger.json").is_file())
            self.assertTrue((run_dir / "reference-ledger.json").is_file())
            self.assertEqual(json.loads((run_dir / "run.json").read_text())["status"], "prepared")
            self.assertEqual(len(manifest["renderer_commands"]), 2)

            with self.assertRaisesRegex(RunError, "already exists"):
                prepare_visual_run(target, [reference], run_dir, skip_render=True)

    def test_plan_matches_same_family_and_closest_signature(self) -> None:
        source = {
            "path": "/tmp/target.pptx",
            "slide_count": 2,
            "slides": [
                {
                    "slide_number": 1,
                    "family_hint": "cover",
                    "text_chars": 20,
                    "picture_count": 0,
                    "table_count": 0,
                    "chart_count": 0,
                },
                {
                    "slide_number": 2,
                    "family_hint": "table",
                    "text_chars": 100,
                    "picture_count": 1,
                    "table_count": 1,
                    "chart_count": 0,
                },
            ],
        }
        references = [
            {
                "path": "/tmp/reference.pptx",
                "slide_count": 3,
                "slides": [
                    {
                        "slide_number": 1,
                        "family_hint": "cover",
                        "text_chars": 24,
                        "picture_count": 0,
                        "table_count": 0,
                        "chart_count": 0,
                    },
                    {
                        "slide_number": 2,
                        "family_hint": "table",
                        "text_chars": 300,
                        "picture_count": 3,
                        "table_count": 1,
                        "chart_count": 0,
                    },
                    {
                        "slide_number": 3,
                        "family_hint": "table",
                        "text_chars": 110,
                        "picture_count": 1,
                        "table_count": 1,
                        "chart_count": 0,
                    },
                ],
            }
        ]

        plan = build_plan(source, references)

        self.assertEqual(plan["pages"][0]["reference_slide"], 1)
        self.assertEqual(plan["pages"][1]["reference_slide"], 3)
        self.assertEqual(plan["pages"][1]["match_mode"], "same_family")

    def test_explicit_override_wins_after_validation(self) -> None:
        source = {
            "path": "/tmp/target.pptx",
            "slide_count": 1,
            "slides": [{"slide_number": 1, "family_hint": "cover", "text_chars": 10}],
        }
        references = [
            {
                "path": "/tmp/reference.pptx",
                "slide_count": 2,
                "slides": [
                    {"slide_number": 1, "family_hint": "cover", "text_chars": 10},
                    {"slide_number": 2, "family_hint": "content", "text_chars": 80},
                ],
            }
        ]

        plan = build_plan(source, references, overrides={"1": {"reference_index": 0, "slide": 2}})
        self.assertEqual(plan["pages"][0]["reference_slide"], 2)
        self.assertEqual(plan["pages"][0]["match_mode"], "override")

        with self.assertRaisesRegex(PlanError, "does not exist"):
            build_plan(source, references, overrides={"1": {"reference_index": 0, "slide": 99}})

    def test_ending_page_uses_cover_fallback_when_reference_has_no_ending(self) -> None:
        source = {
            "path": "/tmp/target.pptx",
            "slide_count": 1,
            "slides": [{"slide_number": 1, "family_hint": "ending", "text_chars": 9}],
        }
        references = [
            {
                "path": "/tmp/reference.pptx",
                "slide_count": 1,
                "slides": [{"slide_number": 1, "family_hint": "cover", "text_chars": 20}],
            }
        ]

        plan = build_plan(source, references)

        self.assertEqual(plan["pages"][0]["match_mode"], "cover_fallback")
        self.assertIn("cover fallback", plan["pages"][0]["warning"])


if __name__ == "__main__":
    unittest.main()
