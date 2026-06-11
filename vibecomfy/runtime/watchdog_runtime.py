from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any

from .config import SessionConfig
from .watchdog import Watchdog, write_report

logger = logging.getLogger(__name__)


def _embedded_observation_url(config: SessionConfig) -> str:
    """Best-guess HTTP base for the embedded backend.

    The embedded backend may or may not expose a server. The watchdog tolerates
    either case: if the URL is unreachable we record connection_state=
    never_connected and continue with VRAM sampling (which will also fail
    silently and be reflected in the diagnosis).
    """
    port = config.port or 8188
    return f"http://127.0.0.1:{port}"


async def _start_watchdog(
    *,
    server_url: str | None,
    client_id: str,
    api_dict: dict[str, Any],
) -> Watchdog | None:
    """Build and start a Watchdog. Returns None if disabled or failed to start.

    The watchdog must NEVER raise into the run path. Any error here is logged
    and ignored. Must be called from inside a running event loop.
    """
    if os.environ.get("VIBECOMFY_WATCHDOG", "1").strip() in {"0", "false", "False", "no", "off"}:
        return None
    if not server_url:
        return None
    try:
        wd = Watchdog(server_url=server_url, client_id=client_id, api_dict=api_dict)
    except Exception:
        logger.exception("watchdog: construction failed; continuing without it")
        return None
    try:
        await wd.start()
    except Exception:
        logger.exception("watchdog: start scheduling failed; continuing without it")
        return None
    return wd


async def _finalize_watchdog(
    watchdog: Watchdog | None,
    *,
    run_dir: Path,
    reason: str,
) -> None:
    """Stop the watchdog and write its report. Errors are swallowed."""
    if watchdog is None:
        return
    try:
        await watchdog.stop(reason=reason)
        report = watchdog.dump()
        path = write_report(run_dir, report)
        # Greppable header on the orchestrator log so a single tail shows it.
        logger.info("%s path=%s", report.header_line(), path)
    except Exception:
        logger.exception("watchdog: finalize failed; ignoring")
