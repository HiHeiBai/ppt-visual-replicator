#!/usr/bin/env python3
"""Locate or install the bundled editppt runtime for this skill."""

from __future__ import annotations

import argparse
import json
import shutil
import site
import subprocess
import sys
from pathlib import Path


SKILL_ROOT = Path(__file__).resolve().parent.parent
BUNDLED_CLI = SKILL_ROOT / "reconstruction" / "cli"


def installed_command() -> Path | None:
    command = shutil.which("editppt")
    if command:
        return Path(command).resolve()
    scripts_dir = Path(site.getuserbase()) / ("Scripts" if sys.platform == "win32" else "bin")
    executable = scripts_dir / ("editppt.exe" if sys.platform == "win32" else "editppt")
    return executable if executable.is_file() else None


def installer_command() -> list[str]:
    if sys.version_info >= (3, 10):
        return [
            sys.executable,
            "-m",
            "pip",
            "install",
            "--user",
            "--upgrade",
            str(BUNDLED_CLI),
        ]
    uv = shutil.which("uv")
    if uv:
        return [uv, "tool", "install", "--force", "--editable", str(BUNDLED_CLI)]
    for executable_name in ("python3.13", "python3.12", "python3.11", "python3.10"):
        executable = shutil.which(executable_name)
        if executable:
            return [
                executable,
                "-m",
                "pip",
                "install",
                "--user",
                "--upgrade",
                str(BUNDLED_CLI),
            ]
    raise RuntimeError(
        "The bundled editppt runtime needs Python 3.10+; install uv or a compatible Python first"
    )


def install_bundled_runtime() -> Path:
    subprocess.run(installer_command(), check=True)
    command = installed_command()
    if not command:
        raise RuntimeError("Bundled editppt installation completed but the executable was not found")
    return command


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Ensure this skill's bundled editppt runtime is available.",
    )
    parser.add_argument("--force", action="store_true", help="Reinstall the bundled runtime.")
    parser.add_argument("--dry-run", action="store_true", help="Report the selected action without installing.")
    parser.add_argument("--print-path", action="store_true", help="Print only the editppt command path.")
    args = parser.parse_args()

    if not BUNDLED_CLI.is_dir():
        raise SystemExit(f"Bundled editppt runtime is missing: {BUNDLED_CLI}")
    command = installed_command()
    action = "reuse"
    if args.force or not command:
        action = "install"
        if not args.dry_run:
            command = install_bundled_runtime()
    if args.print_path:
        if command:
            print(command)
            return 0
        raise SystemExit("No editppt command is installed; rerun without --dry-run to install it")
    print(
        json.dumps(
            {
                "action": action,
                "bundled_cli": str(BUNDLED_CLI),
                "editppt": str(command) if command else None,
                "install_command": installer_command(),
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
