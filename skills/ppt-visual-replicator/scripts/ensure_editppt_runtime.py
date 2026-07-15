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
from typing import Any


SKILL_ROOT = Path(__file__).resolve().parent.parent
BUNDLED_CLI = SKILL_ROOT / "reconstruction" / "cli"
RUNTIME_INFO_SCHEMA = "editppt.runtime-info.v1"
PACKAGE_NAME = "image-to-editable-ppt-cli"


def command_candidates() -> list[Path]:
    """Return every local editppt entrypoint that could be the bundled runtime."""
    candidates: list[Path] = []
    command = shutil.which("editppt")
    if command:
        candidates.append(Path(command).resolve())
    scripts_dir = Path(site.getuserbase()) / ("Scripts" if sys.platform == "win32" else "bin")
    executable = scripts_dir / ("editppt.exe" if sys.platform == "win32" else "editppt")
    if executable.is_file():
        candidates.append(executable.resolve())
    return list(dict.fromkeys(candidates))


def runtime_info(command: Path) -> dict[str, Any] | None:
    """Read the machine-readable provenance reported by one editppt executable."""
    try:
        result = subprocess.run(
            [str(command), "runtime-info", "--json"],
            check=False,
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if result.returncode != 0:
        return None
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError:
        return None
    return payload if isinstance(payload, dict) else None


def is_bundled_runtime(command: Path) -> bool:
    """Accept only an entrypoint that proves it is loading this skill's CLI source."""
    payload = runtime_info(command)
    source_root = payload.get("source_root") if payload else None
    if not isinstance(source_root, str):
        return False
    try:
        actual_source_root = Path(source_root).expanduser().resolve()
    except OSError:
        return False
    return (
        payload.get("schema") == RUNTIME_INFO_SCHEMA
        and payload.get("package") == PACKAGE_NAME
        and actual_source_root == BUNDLED_CLI.resolve()
    )


def installed_command() -> Path | None:
    for command in command_candidates():
        if is_bundled_runtime(command):
            return command
    return None


def installer_command() -> list[str]:
    uv = shutil.which("uv")
    if uv:
        return [uv, "tool", "install", "--force", "--editable", str(BUNDLED_CLI)]
    if sys.version_info >= (3, 10):
        return [
            sys.executable,
            "-m",
            "pip",
            "install",
            "--user",
            "--upgrade",
            "--editable",
            str(BUNDLED_CLI),
        ]
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
                "--editable",
                str(BUNDLED_CLI),
            ]
    raise RuntimeError(
        "The bundled editppt runtime needs Python 3.10+; install uv or a compatible Python first"
    )


def install_bundled_runtime() -> Path:
    subprocess.run(installer_command(), check=True)
    command = installed_command()
    if not command:
        raise RuntimeError(
            "Bundled editppt installation completed, but no executable proved it is loading "
            f"{BUNDLED_CLI}. Ensure the installer location is on PATH and retry."
        )
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
                "runtime_verified": bool(command),
                "install_command": installer_command(),
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
