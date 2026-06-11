from __future__ import annotations

import os
from typing import Any, Callable


async def _maybe_flush_for_policy(
    session: Any,
    fp: tuple[Any, ...],
    *,
    free_vram_gb: Callable[[], float] | None = None,
) -> None:
    free_vram_gb = free_vram_gb or _free_vram_gb
    warm_policy = os.environ.get("VIBECOMFY_WARM", session.config.warm_policy).strip().lower()
    if warm_policy == "never":
        await session.flush()
    elif (
        warm_policy == "auto"
        and session.last_fingerprint is not None
        and fp != session.last_fingerprint
        and free_vram_gb() < session.config.auto_flush_vram_threshold_gb
    ):
        await session.flush()


def _free_vram_gb() -> float:
    try:
        from comfy.model_management import get_free_memory
    except (ImportError, AttributeError):
        return float("inf")

    try:
        return float(get_free_memory()) / (1024**3)
    except (ImportError, AttributeError):
        return float("inf")
