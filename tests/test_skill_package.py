import unittest
import json
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "skills" / "ppt-visual-replicator"


class SkillPackageTest(unittest.TestCase):
    def test_skill_declares_visual_only_workflow_and_dependencies(self) -> None:
        text = (SKILL / "SKILL.md").read_text(encoding="utf-8")

        self.assertIn("name: ppt-visual-replicator", text)
        self.assertIn("Target PPTX and target slide number", text)
        self.assertIn("Reference-style PPTX", text)
        self.assertIn('"$EDITPPT" image edit', text)
        self.assertIn('"$EDITPPT" prepare', text)
        self.assertIn('"$EDITPPT" run finalize', text)
        self.assertIn("Do not rewrite", text)

        for reference in (
            "references/content-protection.md",
            "references/acceptance.md",
        ):
            self.assertIn(reference, text)
            self.assertTrue((SKILL / reference).is_file(), reference)

    def test_skill_uses_a_direct_selected_page_workflow(self) -> None:
        text = (SKILL / "SKILL.md").read_text(encoding="utf-8")

        self.assertIn("scripts/prepare_direct_page.py", text)
        self.assertIn("--target-slide", text)
        self.assertIn("--reference-slide", text)
        self.assertNotIn("build_visual_plan.py", text)
        self.assertNotIn("--execute-phase calibration", text)
        self.assertNotIn("--approve-calibration", text)

    def test_skill_documents_glyph_preflight(self) -> None:
        text = (SKILL / "SKILL.md").read_text(encoding="utf-8")

        self.assertIn("missing glyphs", text)

    def test_reconstruction_defaults_to_offline_text_hints_without_prompting(self) -> None:
        text = (SKILL / "SKILL.md").read_text(encoding="utf-8")

        self.assertIn("`builtin-ink`", text)
        self.assertIn("do not ask for an OCR token", text)

    def test_skill_vendors_its_editable_ppt_runtime_and_worker_contract(self) -> None:
        text = (SKILL / "SKILL.md").read_text(encoding="utf-8")

        self.assertIn("scripts/ensure_editppt_runtime.py", text)
        self.assertIn("reconstruction/scripts/build-page-worker-prompt.py", text)
        self.assertNotIn("Use the installed `image-to-editable-ppt`", text)
        for path in (
            "scripts/ensure_editppt_runtime.py",
            "reconstruction/scripts/build-page-worker-prompt.py",
            "reconstruction/prompts/page-worker.md",
            "reconstruction/references/cli-helper.md",
            "reconstruction/references/manifest-schema.md",
            "reconstruction/references/page-decision-tree.md",
            "reconstruction/cli/pyproject.toml",
            "reconstruction/cli/editppt/runtime/main.py",
        ):
            self.assertTrue((SKILL / path).is_file(), path)

    def test_runtime_bootstrap_uses_a_compatible_installer(self) -> None:
        result = subprocess.run(
            [
                "python3",
                str(SKILL / "scripts" / "ensure_editppt_runtime.py"),
                "--force",
                "--dry-run",
            ],
            check=True,
            text=True,
            capture_output=True,
        )
        payload = json.loads(result.stdout)
        self.assertEqual(Path(payload["install_command"][0]).name, "uv")
        self.assertEqual(payload["install_command"][1:3], ["tool", "install"])

    def test_acceptance_requires_direct_image_and_editable_ppt_consistency(self) -> None:
        text = (SKILL / "references" / "acceptance.md").read_text(encoding="utf-8")

        self.assertIn("target and reference", text)
        self.assertIn("generated slide", text)
        self.assertIn("editable preview", text)

    def test_openai_metadata_matches_skill(self) -> None:
        text = (SKILL / "agents" / "openai.yaml").read_text(encoding="utf-8")

        self.assertIn('display_name: "PPT Visual Replicator"', text)
        self.assertIn("$ppt-visual-replicator", text)


if __name__ == "__main__":
    unittest.main()
