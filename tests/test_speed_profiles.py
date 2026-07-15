import hashlib
import json
import importlib.util
import struct
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from PIL import Image

from tests.pptx_fixture import write_fixture_pptx


ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "skills" / "ppt-visual-replicator"
SCRIPTS = SKILL / "scripts"
RUNTIME = SKILL / "reconstruction" / "cli" / "editppt" / "runtime"
RECONSTRUCTION_SCRIPTS = SKILL / "reconstruction" / "scripts"
sys.path.insert(0, str(SCRIPTS))
sys.path.insert(0, str(RUNTIME))
sys.path.insert(0, str(RECONSTRUCTION_SCRIPTS))

from prepare_direct_deck import DirectDeckError, prepare_direct_deck  # noqa: E402
from stage_reconstruction_inputs import stage_reconstruction_inputs  # noqa: E402
from validate_pptx import foreground_asset_contract_violations  # noqa: E402

PROMPT_SPEC = importlib.util.spec_from_file_location(
    "build_page_worker_prompt", RECONSTRUCTION_SCRIPTS / "build-page-worker-prompt.py"
)
PROMPT_MODULE = importlib.util.module_from_spec(PROMPT_SPEC)
assert PROMPT_SPEC and PROMPT_SPEC.loader
PROMPT_SPEC.loader.exec_module(PROMPT_MODULE)
build_prompt = PROMPT_MODULE.build_prompt


def fake_renderer(pptx, out_dir, *, ledger, **_kwargs):
    destination = Path(out_dir)
    destination.mkdir(parents=True)
    pages = []
    for slide_number in range(1, int(ledger["slide_count"]) + 1):
        page = destination / f"slide-{slide_number:03d}.png"
        marker = 2 if slide_number == 4 else slide_number
        page.write_bytes(
            b"\x89PNG\r\n\x1a\n"
            + b"\x00\x00\x00\rIHDR"
            + struct.pack(">II", 2560, 1440)
            + f"page-{marker}".encode()
        )
        pages.append(
            {
                "slide_number": slide_number,
                "path": str(page),
                "width_px": 2560,
                "height_px": 1440,
                "sha256": f"reported-{marker}",
            }
        )
    report = {
        "schema": "ppt_visual_source_render.v1",
        "source_pptx": str(Path(pptx).resolve()),
        "source_sha256": ledger["sha256"],
        "deck_slide_count": ledger["slide_count"],
        "rendered_slide_count": len(pages),
        "first_slide": 1,
        "last_slide": ledger["slide_count"],
        "dpi": 192,
        "renderer": {"office": "fake", "rasterizer": "fake"},
        "pages": pages,
    }
    (destination / "render-report.json").write_text(json.dumps(report), encoding="utf-8")
    return report


def record_accepted_generation_review(run_dir: Path, page: dict) -> None:
    """Create the reviewer evidence required before imagegen output is staged."""
    source = run_dir / page["source_image"]
    generated = run_dir / page["generated_image"]
    review = {
        "schema": "ppt_visual_generation_review.v1",
        "target_slide": page["target_slide"],
        "accepted": True,
        "generated_image": page["generated_image"],
        "generated_image_sha256": hashlib.sha256(generated.read_bytes()).hexdigest(),
        "source_image": page["source_image"],
        "source_image_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
        "checks": {
            "source_structure_match": True,
            "no_invented_information_visuals": True,
            "no_reference_content_transfer": True,
            "style_contract_match": True,
        },
        "review_note": "Test reviewer confirmed source structure and style-only reference use.",
    }
    path = run_dir / page["run_dir"] / "generation-review.json"
    path.write_text(json.dumps(review), encoding="utf-8")


class SpeedProfileTest(unittest.TestCase):
    def make_target(self, root: Path) -> Path:
        return write_fixture_pptx(
            root / "target.pptx",
            slides=[
                {"texts": ["Cover"]},
                {"texts": ["Screenshot tutorial"], "pictures": 1},
                {"texts": ["Concept page"], "pictures": 2},
                {"texts": ["Screenshot tutorial"], "pictures": 1},
            ],
        )

    def test_balanced_routes_multi_image_pages_to_direct_rebuild_and_reuses_duplicates(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            manifest = prepare_direct_deck(
                self.make_target(root),
                root / "run",
                renderer=fake_renderer,
            )

            self.assertEqual(manifest["speed_profile"], "balanced")
            self.assertEqual(manifest["generation_summary"]["generate"], 1)
            self.assertEqual(manifest["generation_summary"]["direct-rebuild"], 2)
            self.assertEqual(manifest["generation_summary"]["reuse"], 1)
            self.assertEqual(manifest["pages"][3]["generation"]["action"], "reuse")
            self.assertEqual(manifest["pages"][3]["generation"]["canonical_slide"], 2)
            self.assertTrue((root / "run" / "generation-plan.json").is_file())
            self.assertTrue((root / "run" / "shared-assets" / "index.json").is_file())

    def test_strict_redraws_every_unique_page(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            manifest = prepare_direct_deck(
                self.make_target(root),
                root / "run",
                speed_profile="strict",
                renderer=fake_renderer,
            )

            self.assertEqual(manifest["generation_summary"]["generate"], 3)
            self.assertEqual(manifest["generation_summary"]["reuse"], 1)
            self.assertEqual(manifest["generation_summary"]["direct-rebuild"], 0)

    def test_resume_requires_the_same_contract_and_reuses_ready_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            target = self.make_target(root)
            manifest = prepare_direct_deck(target, root / "run", renderer=fake_renderer)
            for page in manifest["pages"]:
                if page["generation"]["action"] == "generate":
                    output = root / "run" / page["generated_image"]
                    output.write_bytes(b"generated")

            resumed = prepare_direct_deck(
                target,
                root / "run",
                renderer=fake_renderer,
                resume=True,
            )
            self.assertEqual(resumed["status"], "generation-ready")
            self.assertTrue(resumed["resume"]["generation_ready"])

            with self.assertRaisesRegex(DirectDeckError, "does not match"):
                prepare_direct_deck(
                    target,
                    root / "run",
                    speed_profile="strict",
                    renderer=fake_renderer,
                    resume=True,
                )

    def test_stages_generated_direct_and_reused_inputs_in_slide_order(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            manifest = prepare_direct_deck(
                self.make_target(root),
                root / "run",
                renderer=fake_renderer,
            )
            for page in manifest["pages"]:
                if page["generation"]["action"] == "generate":
                    (root / "run" / page["generated_image"]).write_bytes(
                        f"generated-{page['target_slide']}".encode()
                    )
                    record_accepted_generation_review(root / "run", page)

            report = stage_reconstruction_inputs(root / "run")
            self.assertEqual(report["page_count"], 4)
            self.assertEqual(report["pages"][0]["source_kind"], "generated")
            self.assertEqual(report["pages"][1]["source_kind"], "source-content")
            self.assertEqual(report["pages"][3]["source_kind"], "reused-source-content")
            self.assertEqual(
                (root / "run" / "reconstruction-inputs" / "slide-002.png").read_bytes(),
                (root / "run" / "reconstruction-inputs" / "slide-004.png").read_bytes(),
            )

    def test_profile_region_is_allowed_only_in_fast_or_balanced(self) -> None:
        item = {
            "id": "tutorial_screenshot",
            "description": "Self-contained software screenshot preserved as a profile region",
            "path": "assets/tutorial.png",
        }
        provenance = {
            "path": "assets/tutorial.png",
            "source": "source.png",
            "source_type": "profile-rasterized-region",
            "provenance_note": "Preserved as one self-contained software screenshot region.",
            "region_reason": "Internal UI controls do not need object-level editing.",
        }
        balanced = {
            "speed_profile": "balanced",
            "visual_inventory": [item],
            "asset_provenance": [provenance],
        }
        strict = {**balanced, "speed_profile": "strict"}

        self.assertEqual(foreground_asset_contract_violations(balanced), [])
        self.assertTrue(foreground_asset_contract_violations(strict))

    def test_page_worker_prompt_receives_speed_route_and_original_source(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            manifest = prepare_direct_deck(
                self.make_target(root),
                root / "run",
                renderer=fake_renderer,
            )
            reconstruction = root / "run" / "reconstruction"
            page_dir = reconstruction / "pages" / "page_001"
            page_dir.mkdir(parents=True)
            request = {
                "source_image": str(root / "run" / manifest["pages"][0]["source_image"])
            }
            (page_dir / "page_request.json").write_text(json.dumps(request), encoding="utf-8")
            page = {"page_id": "page_001", "page_index": 1, "page_dir": "pages/page_001"}

            prompt = build_prompt(reconstruction, page, page_dir)

            self.assertIn("Speed profile: balanced", prompt)
            self.assertIn("shared-assets/index.json", prompt)
            self.assertIn(manifest["pages"][0]["source_image"], prompt)
            self.assertNotIn("{{SPEED_PROFILE}}", prompt)

    def test_region_extractor_rejects_full_slide_and_writes_partial_png(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / "source.png"
            Image.new("RGB", (200, 100), "navy").save(source)
            script = SKILL / "reconstruction" / "scripts" / "extract-page-region.py"
            output = root / "assets" / "region.png"
            subprocess.run(
                [
                    sys.executable,
                    str(script),
                    "--image",
                    str(source),
                    "--box",
                    "20,10,100,50",
                    "--out",
                    str(output),
                ],
                check=True,
                capture_output=True,
                text=True,
            )
            with Image.open(output) as image:
                self.assertEqual(image.size, (100, 50))

            failed = subprocess.run(
                [
                    sys.executable,
                    str(script),
                    "--image",
                    str(source),
                    "--box",
                    "0,0,200,100",
                    "--out",
                    str(root / "full.png"),
                ],
                capture_output=True,
                text=True,
            )
            self.assertNotEqual(failed.returncode, 0)
            self.assertIn("full-slide extraction is forbidden", failed.stderr)


if __name__ == "__main__":
    unittest.main()
