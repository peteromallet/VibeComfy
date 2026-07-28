"""Headless VibeComfy agent dispatch service.

This module must only be imported after ``VIBECOMFY_HEADLESS=1`` is set in the
environment so that route-adjacent modules (ComfyUI/aiohttp registration) are
never pulled in by a headless caller.  The CLI and harness set the flag before
importing this module.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping

from vibecomfy.agent.contracts import HeadlessAgentRequest

LOGGER = logging.getLogger(__name__)


class HeadlessEnvironmentError(RuntimeError):
    """Raised when the headless guard flag is missing."""


@dataclass(frozen=True)
class HeadlessAgentResult:
    """Result of a headless agent run.

    ``status`` is one of:
    * ``success`` — executor returned ok.
    * ``dry_run`` — classify-only execution completed.
    * ``blocked_prerequisite`` — provider/runtime readiness was not satisfied.
    * ``validation_failure`` — the request was invalid.
    * ``executor_failure`` — the executor returned a failure envelope.
    """

    status: str
    ok: bool
    response: dict[str, Any] = field(default_factory=dict)
    artifacts: dict[str, Any] = field(default_factory=dict)
    readiness: dict[str, Any] = field(default_factory=dict)
    error: str | None = None
    request: HeadlessAgentRequest | None = None

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "status": self.status,
            "ok": self.ok,
            "response": self.response,
            "artifacts": self.artifacts,
        }
        if self.readiness:
            payload["readiness"] = self.readiness
        if self.error:
            payload["error"] = self.error
        if self.request is not None:
            payload["request"] = self.request.to_dict()
        return payload


def _ensure_headless_env() -> None:
    if os.environ.get("VIBECOMFY_HEADLESS") != "1":
        raise HeadlessEnvironmentError(
            "Headless agent surface requires VIBECOMFY_HEADLESS=1 to be set "
            "before importing this module."
        )


_ensure_headless_env()


def _check_live_readiness(request: HeadlessAgentRequest) -> dict[str, Any]:
    from vibecomfy.comfy_nodes.agent import provider  # noqa: PLC0415

    readiness_kwargs = request.resolve_provider_readiness_kwargs(stage="classify")
    route = readiness_kwargs.get("route") or "auto"
    model = readiness_kwargs.get("model")
    try:
        return provider.readiness(route=route, model=model)
    except Exception as exc:  # pragma: no cover - best-effort diagnostic
        LOGGER.warning("headless readiness check failed: %s", exc, exc_info=True)
        return {
            "ready": False,
            "route": route,
            "model": model,
            "reason": f"Readiness probe failed: {exc}",
        }


def _synthesize_artifacts(
    *,
    request: HeadlessAgentRequest,
    response: Mapping[str, Any],
    output_dir: Path,
    status: str,
    readiness: Mapping[str, Any] | None,
    entrypoint: str,
    result: Any = None,
) -> dict[str, Any]:
    from vibecomfy.agent.artifacts import synthesize_headless_artifacts  # noqa: PLC0415

    return synthesize_headless_artifacts(
        request=request.to_dict(),
        result=result,
        response=response,
        output_dir=output_dir,
        status=status,
        readiness=readiness,
        entrypoint=entrypoint,
    )


def run_headless(
    request: HeadlessAgentRequest,
    *,
    entrypoint: str = "headless_cli",
) -> HeadlessAgentResult:
    """Run one headless agent turn and synthesize artifacts.

    Live runs are gated by provider readiness.  Dry runs still require readiness
    because the classify phase calls a model.
    """
    _ensure_headless_env()

    output_dir = request.output_dir_path
    if output_dir is None:
        output_dir = Path("out") / "agentic" / "headless"

    readiness: dict[str, Any] = {}
    try:
        executor_request = request.to_executor_request()
    except Exception as exc:
        error = f"Invalid request: {exc}"
        response = {"ok": False, "error": error}
        artifacts = _synthesize_artifacts(
            request=request,
            result=None,
            response=response,
            output_dir=output_dir,
            status="validation_failure",
            readiness=readiness,
            entrypoint=entrypoint,
        )
        return HeadlessAgentResult(
            status="validation_failure",
            ok=False,
            response=response,
            artifacts=artifacts,
            readiness=readiness,
            error=error,
            request=request,
        )

    try:
        readiness = _check_live_readiness(request)
    except Exception as exc:
        LOGGER.warning("headless could not resolve profile for readiness: %s", exc, exc_info=True)
        readiness = {
            "ready": False,
            "reason": f"Could not resolve profile: {exc}",
        }

    if not readiness.get("ready"):
        error = readiness.get("reason") or "Provider is not ready."
        response = {"ok": False, "error": error}
        artifacts = _synthesize_artifacts(
            request=request,
            result=None,
            response=response,
            output_dir=output_dir,
            status="blocked_prerequisite",
            readiness=readiness,
            entrypoint=entrypoint,
        )
        return HeadlessAgentResult(
            status="blocked_prerequisite",
            ok=False,
            response=response,
            artifacts=artifacts,
            readiness=readiness,
            error=error,
            request=request,
        )

    from vibecomfy.comfy_nodes.agent.executor_durable import (  # noqa: PLC0415
        maybe_write_executor_only_durable_turn,
    )
    from vibecomfy.comfy_nodes.agent.executor_response import (  # noqa: PLC0415
        serialize_executor_result,
    )
    from vibecomfy.executor.core import run_executor  # noqa: PLC0415

    result = run_executor(
        executor_request,
        classify_only=request.dry_run,
        additive=request.additive,
    )
    response = serialize_executor_result(result)
    if not result.ok and not response.get("error"):
        response["error"] = (
            response.get("failure_message")
            or getattr(result, "failure_message", None)
            or "Executor failed."
        )

    # For non-applyable routes the executor does not delegate to handle_agent_edit,
    # so durable turn artifacts are not produced.  Reuse the HTTP-route helper to
    # allocate a lightweight session turn and write request/response/chat files.
    response = maybe_write_executor_only_durable_turn(
        response=response,
        result=result,
        payload=request.to_dict(),
        request=request,
    )

    status = "dry_run" if request.dry_run else ("success" if result.ok else "executor_failure")
    artifacts = _synthesize_artifacts(
        request=request,
        result=result,
        response=response,
        output_dir=output_dir,
        status=status,
        readiness=readiness,
        entrypoint=entrypoint,
    )

    return HeadlessAgentResult(
        status=status,
        ok=result.ok if not request.dry_run else True,
        response=response,
        artifacts=artifacts,
        readiness=readiness,
        error=response.get("error") if not result.ok and not request.dry_run else None,
        request=request,
    )


__all__ = ["HeadlessAgentResult", "run_headless", "HeadlessEnvironmentError"]
