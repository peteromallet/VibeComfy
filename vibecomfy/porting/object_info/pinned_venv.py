"""Shared throwaway-venv helper for pinned comfyui installs."""

from __future__ import annotations

import subprocess
import sys
import venv
from pathlib import Path
from typing import Callable, Sequence

CommandRunner = Callable[[Sequence[str]], subprocess.CompletedProcess[str]]


def venv_python(env_dir: Path) -> Path:
    if sys.platform == "win32":
        return env_dir / "Scripts" / "python.exe"
    return env_dir / "bin" / "python"


def run_checked(command: Sequence[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        list(command),
        check=True,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


def provision_comfyui_venv(
    env_dir: Path,
    comfy_version: str,
    *,
    runner: CommandRunner | None = None,
    package_template: str = "comfyui=={version}",
) -> Path:
    if not (env_dir / "pyvenv.cfg").is_file():
        venv.EnvBuilder(with_pip=True, clear=False).create(env_dir)
    python = venv_python(env_dir)
    run = runner or run_checked
    package = package_template.format(version=comfy_version)
    run([str(python), "-m", "pip", "install", "--disable-pip-version-check", package])
    return python
