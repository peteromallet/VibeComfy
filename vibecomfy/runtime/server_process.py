from __future__ import annotations

import asyncio
import os
import shutil
import sys
from pathlib import Path
from typing import Any

from vibecomfy.errors import RuntimeStartupError

from .client import ComfyClient
from .config import SessionConfig, _comfy_server_argv


async def _spawn_comfy_server(
    config: SessionConfig, log_path: str | Path | None = None
) -> tuple[asyncio.subprocess.Process, str, Any | None]:
    log_handle = None
    if log_path:
        Path(log_path).parent.mkdir(parents=True, exist_ok=True)
        log_handle = Path(log_path).open("ab", buffering=0)
    argv = _comfy_server_argv(config)
    process = await asyncio.create_subprocess_exec(
        *argv,
        stdout=log_handle or asyncio.subprocess.DEVNULL,
        stderr=log_handle or asyncio.subprocess.DEVNULL,
        env=os.environ.copy(),
    )
    managed_url = f"http://127.0.0.1:{config.port or 8188}"
    client = ComfyClient(managed_url)
    for _ in range(120):
        if await client.ready():
            break
        await asyncio.sleep(1)
    else:
        if process.returncode is None:
            process.kill()
            await process.wait()
        if log_handle:
            log_handle.close()
        timeout = TimeoutError("Managed Comfy server did not become ready within 120 seconds")
        raise RuntimeStartupError(
            str(timeout),
            next_action="Check the ComfyUI startup log, installed custom nodes, and selected port before retrying.",
        ) from timeout
    return process, managed_url, log_handle


def _comfyui_executable() -> str:
    executable = shutil.which("comfyui")
    if executable:
        return executable
    sibling = Path(sys.executable).with_name("comfyui")
    if sibling.exists():
        return str(sibling)
    return "comfyui"
