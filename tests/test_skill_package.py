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

    def test_skill_requires_primary_deck_lock_and_calibration_gate(self) -> None:
        text = (SKILL / "SKILL.md").read_text(encoding="utf-8")

        self.assertIn("primary reference deck", text)
        self.assertIn("--execute-phase calibration", text)
        self.assertIn("--approve-calibration", text)
        self.assertIn("--execute-phase scale", text)
        self.assertIn("calibration-approved.json", text)
        self.assertIn("--stage generated", text)
        self.assertIn("mixed automatic reference decks", text)

    def test_skill_documents_glyph_preflight(self) -> None:
        text = (SKILL / "SKILL.md").read_text(encoding="utf-8")

        self.assertIn("missing glyphs", text)

    def test_reconstruction_defaults_to_offline_text_hints_without_prompting(self) -> None:
        text = (SKILL / "SKILL.md").read_text(encoding="utf-8")

        self.assertIn("`builtin-ink`", text)
        self.assertIn("without stopping or asking the user", text)

    def test_acceptance_requires_deck_and_calibration_consistency(self) -> None:
        text = (SKILL / "references" / "acceptance.md").read_text(encoding="utf-8")

        self.assertIn("one automatic reference deck", text)
        self.assertIn("one automatic reference anchor per page family", text)
        self.assertIn("calibration-approved.json", text)
        self.assertIn("approved calibration hash", text)
        self.assertIn("reference-copy drift", text)

    def test_page_matching_separates_single_image_content(self) -> None:
        text = (SKILL / "references" / "page-matching.md").read_text(encoding="utf-8")

        self.assertIn("`image_content`", text)

    def test_scale_prompt_uses_target_and_calibration_only(self) -> None:
        text = (SKILL / "references" / "image-prompt-contract.md").read_text(encoding="utf-8")

        self.assertIn("Do not send the original reference page again", text)

    def test_openai_metadata_matches_skill(self) -> None:
        text = (SKILL / "agents" / "openai.yaml").read_text(encoding="utf-8")

        self.assertIn('display_name: "PPT Visual Replicator"', text)
        self.assertIn("$ppt-visual-replicator", text)


if __name__ == "__main__":
    unittest.main()
