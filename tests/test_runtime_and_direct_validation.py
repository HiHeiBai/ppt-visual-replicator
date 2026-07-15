from __future__ import annotations

import hashlib
import importlib.util
import json
import stat
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


REPO_ROOT = Path(__file__).resolve().parents[1]
SKILL_ROOT = REPO_ROOT / "skills" / "ppt-visual-replicator"
SCRIPTS = SKILL_ROOT / "scripts"
RUNTIME = SKILL_ROOT / "reconstruction" / "cli" / "editppt" / "runtime"
sys.path[:0] = [str(SCRIPTS), str(RUNTIME)]

import runtime_env  # noqa: E402
import validate_visual_run  # noqa: E402
import build_visual_plan  # noqa: E402
import prepare_direct_deck  # noqa: E402
import pptx_inspect  # noqa: E402
import main as editppt_main  # noqa: E402


def load_script(name: str):
    path = SCRIPTS / name
    spec = importlib.util.spec_from_file_location(path.stem, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class EnsureRuntimeTests(unittest.TestCase):
    def test_uv_is_preferred_over_pip(self):
        module = load_script("ensure_editppt_runtime.py")
        with patch.object(module.shutil, "which", side_effect=lambda name: "/tmp/uv" if name == "uv" else None):
            self.assertEqual(module.installer_command()[:3], ["/tmp/uv", "tool", "install"])

    def test_python_310_uses_pip_only_when_uv_is_absent(self):
        module = load_script("ensure_editppt_runtime.py")
        with patch.object(module.shutil, "which", return_value=None), patch.object(
            module.sys, "version_info", (3, 10, 0)
        ):
            command = module.installer_command()
        self.assertEqual(command[0], sys.executable)
        self.assertEqual(command[1:4], ["-m", "pip", "install"])
        self.assertIn("--editable", command)

    def test_reuses_only_a_runtime_that_proves_the_bundled_source(self):
        module = load_script("ensure_editppt_runtime.py")
        candidate = Path("/tmp/editppt")
        matching_info = {
            "schema": module.RUNTIME_INFO_SCHEMA,
            "package": module.PACKAGE_NAME,
            "source_root": str(module.BUNDLED_CLI),
        }
        with patch.object(module, "command_candidates", return_value=[candidate]), patch.object(
            module, "runtime_info", return_value=matching_info
        ):
            self.assertEqual(module.installed_command(), candidate)

        stale_info = {**matching_info, "source_root": "/tmp/another-editppt"}
        with patch.object(module, "command_candidates", return_value=[candidate]), patch.object(
            module, "runtime_info", return_value=stale_info
        ):
            self.assertIsNone(module.installed_command())

    def test_runtime_info_reports_the_bundled_cli_root(self):
        payload = editppt_main.runtime_info_payload()
        self.assertEqual(payload["schema"], "editppt.runtime-info.v1")
        self.assertEqual(payload["package"], "image-to-editable-ppt-cli")
        self.assertEqual(Path(payload["source_root"]), SKILL_ROOT / "reconstruction" / "cli")


class ConfigWriteTests(unittest.TestCase):
    def test_atomic_write_replaces_symlink_without_following_it(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            sentinel = root / "sentinel.txt"
            sentinel.write_text("unchanged", encoding="utf-8")
            config = root / "config.yaml"
            config.symlink_to(sentinel)

            runtime_env.write_config_file(config, {"OPENAI_API_KEY": "secret"})

            self.assertFalse(config.is_symlink())
            self.assertEqual(sentinel.read_text(encoding="utf-8"), "unchanged")
            self.assertIn("OPENAI_API_KEY: secret", config.read_text(encoding="utf-8"))
            self.assertEqual(stat.S_IMODE(config.stat().st_mode), 0o600)


class DirectRunValidationTests(unittest.TestCase):
    def test_generated_stage_uses_direct_run_artifacts(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            page_dir = root / "pages" / "slide-001"
            page_dir.mkdir(parents=True)
            source = page_dir / "source-content.png"
            generated = page_dir / "generated.png"
            source.write_bytes(b"source-image")
            generated.write_bytes(b"generated-image")
            digest = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
            checks = {
                "source_structure_match": True,
                "no_invented_information_visuals": True,
                "no_reference_content_transfer": True,
                "style_contract_match": True,
            }
            (page_dir / "generation-review.json").write_text(
                json.dumps(
                    {
                        "target_slide": 1,
                        "accepted": True,
                        "generated_image_sha256": digest(generated),
                        "source_image_sha256": digest(source),
                        "checks": checks,
                        "review_note": "Compared with source.",
                    }
                ),
                encoding="utf-8",
            )
            (root / "deck-run.json").write_text(
                json.dumps(
                    {
                        "pages": [
                            {
                                "target_slide": 1,
                                "run_dir": "pages/slide-001",
                                "source_image": "pages/slide-001/source-content.png",
                                "generated_image": "pages/slide-001/generated.png",
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )
            (root / "generation-plan.json").write_text(
                json.dumps({"pages": [{"target_slide": 1, "generation": {"action": "generate"}}]}),
                encoding="utf-8",
            )

            result = validate_visual_run.validate_visual_run(root, stage="generated")

            self.assertTrue(result["passed"], result)
            self.assertEqual(result["evidence"]["run_type"], "direct_deck")


class ContentInspectionTests(unittest.TestCase):
    def test_critical_tokens_preserve_ranges_units_and_medical_values(self):
        tokens = pptx_inspect.extract_critical_tokens(
            "HR=0.29; 95% CI 0.56–0.92; 65.9%; N=1,234; 3/4级; 8.2个月; 2线; 2L; HGB 8.2; HbA1c=7.1%"
        )
        for expected in (
            "HR=0.29",
            "95% CI 0.56–0.92",
            "65.9%",
            "N=1,234",
            "3/4级",
            "8.2个月",
            "2线",
            "2L",
            "HGB 8.2",
            "HbA1c=7.1%",
        ):
            self.assertIn(expected, tokens)
        self.assertNotIn("0.56", tokens)
        self.assertNotIn("0.92", tokens)

    def test_chart_and_multi_image_pages_are_distinct(self):
        self.assertEqual(pptx_inspect._slide_family(2, 5, [], 0, 0, 1), "chart")
        self.assertEqual(pptx_inspect._slide_family(2, 5, [], 2, 0, 0), "multi_image")
        chart_action, _ = prepare_direct_deck._generation_route(
            {"family_hint": "chart"}, "balanced", False
        )
        image_action, _ = prepare_direct_deck._generation_route(
            {"family_hint": "multi_image"}, "balanced", False
        )
        self.assertEqual(chart_action, "generate")
        self.assertEqual(image_action, "direct-rebuild")
        self.assertIn("chart", build_visual_plan.STRICT_FAMILIES)
        self.assertNotIn("multi_image", build_visual_plan.STRICT_FAMILIES)


if __name__ == "__main__":
    unittest.main()
