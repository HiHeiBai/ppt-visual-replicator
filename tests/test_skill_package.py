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
        self.assertIn("Required:", text)
        self.assertIn("Target PPTX", text)
        self.assertIn("user-supplied reference PNGs", text)
        self.assertIn("Do not ask for a speed profile", text)
        self.assertIn("imagegen", text)
        self.assertIn('"$EDITPPT" prepare', text)
        self.assertIn('"$EDITPPT" run finalize', text)
        self.assertIn("Do not rewrite", text)

        for reference in (
            "references/content-protection.md",
            "references/acceptance.md",
            "references/chrome-normalization.md",
            "references/speed-profiles.md",
        ):
            self.assertTrue((SKILL / reference).is_file(), reference)

    def test_skill_uses_a_direct_selected_page_workflow(self) -> None:
        text = (SKILL / "SKILL.md").read_text(encoding="utf-8")

        self.assertIn("scripts/prepare_direct_deck.py", text)
        self.assertIn("--target-slide", text)
        self.assertIn("--reference-image", text)
        self.assertIn("--reference-user-supplied", text)
        self.assertIn("--style-brief", text)
        self.assertIn("--strict-text-protection", text)
        self.assertIn("--source-renderer quicklook", text)
        self.assertIn("--full-page-imagegen", text)
        self.assertIn("generation-plan.json", text)
        self.assertIn("scripts/stage_reconstruction_inputs.py", text)
        self.assertIn("generated.png", text)
        self.assertIn("Rebuild locally, one page at a time", text)
        self.assertNotIn('"$EDITPPT" image edit', text)
        self.assertNotIn("build_visual_plan.py", text)

    def test_skill_documents_glyph_preflight(self) -> None:
        text = (SKILL / "SKILL.md").read_text(encoding="utf-8")

        self.assertIn("missing glyphs", text)

    def test_reconstruction_defaults_to_local_sequential_work_without_prompting(self) -> None:
        text = (SKILL / "SKILL.md").read_text(encoding="utf-8")

        self.assertIn("default workflow does not require subagents", text)
        self.assertIn('run next "$RUN/reconstruction" --local --json', text)

    def test_skill_vendors_its_editable_ppt_runtime_and_worker_contract(self) -> None:
        text = (SKILL / "SKILL.md").read_text(encoding="utf-8")

        self.assertIn("scripts/ensure_editppt_runtime.py", text)
        self.assertIn("worker-prompt.md", text)
        self.assertNotIn("Use the installed `image-to-editable-ppt`", text)
        for path in (
            "scripts/ensure_editppt_runtime.py",
            "scripts/render_source_pages.py",
            "scripts/prepare_direct_deck.py",
            "scripts/stage_reconstruction_inputs.py",
            "reconstruction/scripts/build-page-worker-prompt.py",
            "reconstruction/scripts/extract-page-region.py",
            "reconstruction/prompts/page-worker.md",
            "reconstruction/references/cli-helper.md",
            "reconstruction/references/manifest-schema.md",
            "reconstruction/references/page-decision-tree.md",
            "reconstruction/cli/pyproject.toml",
            "reconstruction/cli/editppt/runtime/main.py",
            "scripts/normalize_global_chrome.py",
            "scripts/render_final_qa.py",
        ):
            self.assertTrue((SKILL / path).is_file(), path)

    def test_skill_requires_final_real_render(self) -> None:
        text = (SKILL / "SKILL.md").read_text(encoding="utf-8")
        acceptance = (SKILL / "references" / "acceptance.md").read_text(encoding="utf-8")

        self.assertIn("scripts/render_final_qa.py", text)
        self.assertIn("Render the final PPTX for visual QA", text)
        self.assertIn("final real-render", acceptance)

    def test_skill_package_has_no_runtime_cache_files(self) -> None:
        tracked = subprocess.run(
            ["git", "ls-files", "--", str(SKILL.relative_to(ROOT))],
            cwd=ROOT,
            check=True,
            text=True,
            capture_output=True,
        ).stdout.splitlines()
        forbidden = [
            path
            for path in tracked
            if path.endswith(".pyc") or "/__pycache__/" in path or path.startswith("__pycache__/")
        ]

        self.assertEqual(forbidden, [])

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

        self.assertIn("render report", text.lower())
        self.assertIn("Native text extraction is not a blocking prerequisite", text)
        self.assertIn("zero or more recorded shared style inputs", text)
        self.assertIn("generated slide", text)
        self.assertIn("editable preview", text)

    def test_openai_metadata_matches_skill(self) -> None:
        text = (SKILL / "agents" / "openai.yaml").read_text(encoding="utf-8")

        self.assertIn('display_name: "PPT Visual Replicator"', text)
        self.assertIn("$ppt-visual-replicator", text)


if __name__ == "__main__":
    unittest.main()
