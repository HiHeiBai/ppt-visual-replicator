import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "skills" / "ppt-visual-replicator"


class SkillPackageTest(unittest.TestCase):
    def test_skill_declares_visual_only_workflow_and_dependencies(self) -> None:
        text = (SKILL / "SKILL.md").read_text(encoding="utf-8")

        self.assertIn("name: ppt-visual-replicator", text)
        self.assertIn("target-content PPTX", text)
        self.assertIn("reference-style PPTX", text)
        self.assertIn("editppt image edit", text)
        self.assertIn("editppt prepare", text)
        self.assertIn("editppt run finalize", text)
        self.assertIn("Do not rewrite", text)

        for reference in (
            "references/content-protection.md",
            "references/page-matching.md",
            "references/image-prompt-contract.md",
            "references/acceptance.md",
        ):
            self.assertIn(reference, text)
            self.assertTrue((SKILL / reference).is_file(), reference)

    def test_openai_metadata_matches_skill(self) -> None:
        text = (SKILL / "agents" / "openai.yaml").read_text(encoding="utf-8")

        self.assertIn('display_name: "PPT Visual Replicator"', text)
        self.assertIn("$ppt-visual-replicator", text)


if __name__ == "__main__":
    unittest.main()
