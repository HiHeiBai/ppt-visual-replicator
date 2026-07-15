import importlib.util
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RUNTIME = (
    ROOT
    / "skills"
    / "ppt-visual-replicator"
    / "reconstruction"
    / "cli"
    / "editppt"
    / "runtime"
    / "build_pptx_from_manifest.py"
)
SPEC = importlib.util.spec_from_file_location("build_pptx_from_manifest", RUNTIME)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(MODULE)


class RuntimeAlignmentTest(unittest.TestCase):
    def test_default_alignment_uses_valid_ooxml_values(self) -> None:
        xml = MODULE.text_box_xml(2, {"text": "Title", "left": 0, "top": 0, "width": 2, "height": 1})

        self.assertIn('algn="l"', xml)
        self.assertIn('anchor="t"', xml)
        self.assertNotIn('algn="left"', xml)
        self.assertNotIn('anchor="top"', xml)

    def test_common_alignment_names_are_normalized(self) -> None:
        xml = MODULE.text_box_xml(
            2,
            {
                "text": "12",
                "left": 0,
                "top": 0,
                "width": 1,
                "height": 1,
                "align": "center",
                "valign": "middle",
            },
        )

        self.assertIn('algn="ctr"', xml)
        self.assertIn('anchor="ctr"', xml)
        self.assertEqual(MODULE.preview_text_align("ctr"), "center")


if __name__ == "__main__":
    unittest.main()
