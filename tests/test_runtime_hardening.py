import argparse
import json
import stat
import struct
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from tests.pptx_fixture import write_fixture_pptx


ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "skills" / "ppt-visual-replicator"
RUNTIME = SKILL / "reconstruction" / "cli" / "editppt" / "runtime"
SCRIPTS = SKILL / "scripts"
sys.path.insert(0, str(RUNTIME))
sys.path.insert(0, str(SCRIPTS))

import _input_normalization as input_normalization  # noqa: E402
import image_gen  # noqa: E402
import main as editppt_main  # noqa: E402
import render_final_qa  # noqa: E402
from _page_artifacts import process_asset_sheet  # noqa: E402
from runtime_env import write_config_file  # noqa: E402


def write_png_header(path: Path, width: int, height: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00\x00\x00\rIHDR" + struct.pack(">II", width, height))


class RuntimeHardeningTest(unittest.TestCase):
    def test_ppt_normalization_uses_the_explicit_dpi_parameter(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / "legacy.ppt"
            source.write_bytes(b"legacy-ppt")
            converted = root / "converted.pptx"
            converted.write_bytes(b"converted-pptx")
            rendered_pdf = root / "rendered.pdf"
            rendered_pdf.write_bytes(b"%PDF")
            observed_dpi: list[int] = []

            def fake_render(_pdf: Path, pages_dir: Path, dpi: int) -> list[Path]:
                observed_dpi.append(dpi)
                page = pages_dir / "page_001" / "source.png"
                page.parent.mkdir(parents=True)
                page.write_bytes(b"png")
                return [page]

            with (
                patch.object(input_normalization, "convert_ppt_to_pptx", return_value=converted),
                patch.object(input_normalization, "convert_office_to_pdf", return_value=rendered_pdf),
                patch.object(input_normalization, "collect_notes_from_pptx", return_value=[]),
                patch.object(input_normalization, "render_pdf_pages", side_effect=fake_render),
            ):
                manifest_path = input_normalization.normalize_inputs(
                    [source], job_dir=root / "job", dpi=222
                )

            self.assertEqual(observed_dpi, [222])
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            self.assertEqual(manifest["input_type"], "ppt")

    def test_config_file_is_created_owner_read_write_only(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "config.yaml"
            write_config_file(path, {"OPENAI_API_KEY": "test-key"})

            self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)
            self.assertIn("OPENAI_API_KEY", path.read_text(encoding="utf-8"))

    def test_asset_sheet_processing_rejects_empty_input_instead_of_succeeding(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            args = SimpleNamespace(
                asset_sheet_source=None,
                chroma="missing-chroma.png",
                alpha="missing-alpha.png",
                skip_chroma=False,
                skip_split=False,
            )

            with self.assertRaisesRegex(SystemExit, "No asset sheet input exists"):
                process_asset_sheet(args, root)

    def test_image_backend_refuses_to_discard_extra_images(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output = Path(temp_dir) / "only-output.png"

            with patch.object(image_gen, "_die", side_effect=RuntimeError) as die:
                with self.assertRaises(RuntimeError):
                    image_gen._decode_and_write(["aGVsbG8=", "d29ybGQ="], [output], force=False)
            self.assertIn("refusing to silently discard", str(die.call_args.args[0]))
            self.assertFalse(output.exists())

    def test_prepare_uses_json_protocol_not_stdout_line_position(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            deck_manifest = root / "deck_manifest.json"
            deck_manifest.write_text("{}", encoding="utf-8")
            calls: list[list[str]] = []

            def fake_run(command, **_kwargs):
                command = [str(value) for value in command]
                calls.append(command)
                if command[1].endswith("prepare_deck_run.py"):
                    return subprocess.CompletedProcess(
                        command,
                        0,
                        json.dumps({"deck_manifest": str(deck_manifest), "pages": 1}),
                        "warning that belongs on stderr",
                    )
                return subprocess.CompletedProcess(command, 0, "", "")

            args = argparse.Namespace(
                inputs=["source.png"],
                out_root=str(root / "out"),
                job_dir=str(root / "job"),
                dpi=180,
                max_concurrent_pages=1,
                no_text_hints=True,
            )
            with patch.object(editppt_main.subprocess, "run", side_effect=fake_run):
                result = editppt_main.cmd_prepare(args)

            self.assertEqual(result, 0)
            self.assertIn("--json", calls[0])

    def test_final_render_rejects_wrong_slide_aspect_ratio(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            target = write_fixture_pptx(root / "target.pptx")

            def fake_run(command, **_kwargs):
                if "--convert-to" in command:
                    output_dir = Path(command[command.index("--outdir") + 1])
                    (output_dir / "target.pdf").write_bytes(b"%PDF")
                else:
                    prefix = Path(command[-1])
                    write_png_header(prefix.with_name(f"{prefix.name}-1.png"), 100, 100)
                return subprocess.CompletedProcess(command, 0, "", "")

            with (
                patch.object(render_final_qa.shutil, "which", side_effect=lambda name: f"/fake/{name}"),
                patch.object(render_final_qa.subprocess, "run", side_effect=fake_run),
            ):
                with self.assertRaisesRegex(render_final_qa.FinalRenderError, "wrong aspect ratio"):
                    render_final_qa.render_final_pptx(target, root / "final-render")


if __name__ == "__main__":
    unittest.main()
