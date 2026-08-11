"""Managed Comfy server process surface.

Spawn / ready-wait / timeout / error handling is owned by
:mod:`vibecomfy.runtime.session` (the sole owner per ORACLE-8 R:S7). This module
re-exports the canonical spawn and argv builder so :mod:`vibecomfy.runtime.server`
``comfy_server`` delegates without a second implementation.

``_comfyui_executable`` resolves the `comfyui` binary for :func:`_comfy_server_argv`
and is kept here as a server-process concern.
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

from .session import SessionConfig, _comfy_server_argv, _spawn_comfy_server

__all__ = ["SessionConfig", "_comfy_server_argv", "_spawn_comfy_server"]


def _comfyui_executable() -> str:
    executable = shutil.which("comfyui")
    if executable:
        return executable
    sibling = Path(sys.executable).with_name("comfyui")
    if sibling.exists():
        return str(sibling)
    return "comfyui"
