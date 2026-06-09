from __future__ import annotations

import asyncio
import shutil
import sys
from pathlib import Path
from typing import Any

from vibecomfy.errors import RuntimeStartupError

from .config import SessionConfig, _comfy_server_argv, _comfyui_command
from .config import _spawn_comfy_server as _spawn_comfy_server_impl

__all__ = ["_spawn_comfy_server", "_comfyui_executable", "_comfy_server_argv"]


async def _spawn_comfy_server(
    config: SessionConfig, log_path: str | Path | None = None
) -> tuple[asyncio.subprocess.Process, str, Any | None]:
    """Spawn a managed Comfy server for the run()/convenience path.

    Delegates to the single canonical implementation in ``config`` and
    preserves this path's historical ``RuntimeStartupError`` semantics by
    translating the canonical ``TimeoutError`` into the richer error type
    (with a next_action hint) that callers of this path expect.
    """
    try:
        return await _spawn_comfy_server_impl(config, log_path=log_path)
    except TimeoutError as timeout:
        raise RuntimeStartupError(
            str(timeout),
            next_action=(
                "Check the ComfyUI startup log, installed custom nodes, and "
                "selected port before retrying."
            ),
        ) from timeout


def _comfyui_executable() -> str:
    executable = shutil.which("comfyui")
    if executable:
        return executable
    sibling = Path(sys.executable).with_name("comfyui")
    if sibling.exists():
        return str(sibling)
    return "comfyui"
