from __future__ import annotations

import asyncio
import signal
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncIterator

from .server_process import _spawn_comfy_server
from .session import SessionConfig


@asynccontextmanager
async def comfy_server(
    server_url: str | None = None,
    log_path: str | Path | None = None,
    config: SessionConfig | None = None,
) -> AsyncIterator[str]:
    if server_url:
        yield server_url
        return

    log_handle = None
    process: asyncio.subprocess.Process | None = None
    try:
        process, managed_url, log_handle = await _spawn_comfy_server(
            config or SessionConfig(port=8188), log_path=log_path
        )
        yield managed_url
    finally:
        if process and process.returncode is None:
            process.send_signal(signal.SIGTERM)
            try:
                await asyncio.wait_for(process.wait(), timeout=15)
            except asyncio.TimeoutError:
                process.kill()
                await process.wait()
        if log_handle:
            log_handle.close()
