"""Headless VibeComfy agent dispatch service.

This module must only be imported after ``VIBECOMFY_HEADLESS=1`` is set in the
environment so that route-adjacent modules (ComfyUI/aiohttp registration) are
never pulled in by a headless caller.  The CLI and harness set the flag before
importing this module.
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any, Mapping

from vibecomfy.agent.contracts import HeadlessAgentRequest, NeedsInput

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
    needs_input: NeedsInput | None = None

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
        if self.needs_input is not None:
            payload["needs_input"] = self.needs_input.to_dict()
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
    from vibecomfy.executor.contracts import resolve_orchestration_mode  # noqa: PLC0415

    # Threaded mode has no classifier: readiness must probe the combined
    # execute spec users actually selected, not an unused staged dependency.
    # Resolve through the same request -> environment -> default precedence as
    # run_executor().  Without this, a headless caller selecting threaded mode
    # through VIBECOMFY_EXECUTOR_PIPELINE_MODE would probe the staged classifier
    # profile and could be reported ready before the actual execute profile was
    # checked.
    try:
        effective_mode = resolve_orchestration_mode(request)
    except Exception:
        # Preserve run_executor's authoritative configuration error. Readiness
        # is only a best-effort preflight and must not turn an invalid mode env
        # value into a misleading profile result here.
        effective_mode = "staged"
    readiness_stage = "execute" if effective_mode == "threaded" else "classify"
    readiness_kwargs = request.resolve_provider_readiness_kwargs(stage=readiness_stage)
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


def _typed_ambiguity_from_result(result: Any) -> NeedsInput | None:
    """Return only classifier-authored ambiguity; never inspect query phrases."""

    report = getattr(result, "report", None)
    plan = getattr(report, "plan", None)
    if plan is None:
        return None
    typed = getattr(plan, "needs_input", None)
    if isinstance(typed, NeedsInput):
        return typed
    if getattr(plan, "effective_route", "") != "clarify":
        return None
    question = str(getattr(plan, "clarification_question", "") or "").strip()
    if not question:
        return None
    decision = str(getattr(plan, "plan_summary", "") or "").strip()
    return NeedsInput(
        decision=decision or "A decision-critical input is missing.",
        question=question,
        missing_information=(decision or question,),
        options=tuple(getattr(plan, "clarification_options", ()) or ()),
    )


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


def _thaw_mapping(value: Any) -> Any:
    """Plain-dict/list copy of frozen mappingproxy/tuple evidence."""
    if isinstance(value, Mapping):
        return {str(k): _thaw_mapping(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_thaw_mapping(v) for v in value]
    return value


def run_headless(
    request: HeadlessAgentRequest,
    *,
    entrypoint: str = "headless_cli",
    scenario_id: str | None = None,
) -> HeadlessAgentResult:
    """Run one headless agent turn and synthesize artifacts.

    Live runs are gated by provider readiness.  Dry runs still require readiness
    because the classify phase calls a model.

    ``scenario_id`` is the harness-owned lineage identity (T5.1); when given it
    is bound into the executor request so the artifact lineage manifest records
    the scenario binding at the source.
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

    # T5.1 lineage: bind the harness-owned scenario identity at the source so
    # the artifact lineage manifest records it verbatim (never re-derived).
    if scenario_id:
        executor_request = replace(executor_request, scenario_id=str(scenario_id))

    if executor_request.network:
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
    else:
        # Do not probe a provider that this request is forbidden to use.
        # run_executor owns the typed fail-closed refusal returned below.
        readiness = {
            "ready": False,
            "reason": "Provider readiness skipped because `network=false`.",
        }
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
    typed_ambiguity = _typed_ambiguity_from_result(result)
    plan = getattr(getattr(result, "report", None), "plan", None)
    effective_route = getattr(plan, "effective_route", "")
    if typed_ambiguity is not None:
        if effective_route == "clarify":
            response["needs_input"] = typed_ambiguity.to_dict()
        elif typed_ambiguity.bounded_assumption:
            response["bounded_assumption"] = typed_ambiguity.bounded_assumption
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

    status = (
        "dry_run"
        if request.dry_run and result.ok
        else ("success" if result.ok else "executor_failure")
    )
    artifacts = _synthesize_artifacts(
        request=request,
        result=result,
        response=response,
        output_dir=output_dir,
        status=status,
        readiness=readiness,
        entrypoint=entrypoint,
    )

    # T5.1: persist the executor-built artifact lineage manifest as a stable
    # sidecar so the harness assessor can bind assessment evidence to it even
    # when the response envelope is large or redacted downstream.
    _report = response.get("report") if isinstance(response, Mapping) else None
    _lineage_manifest = (
        (_report or {}).get("executor", {}).get("artifact_lineage")
        if isinstance(_report, Mapping)
        else None
    )
    if isinstance(_lineage_manifest, Mapping):
        try:
            output_dir.mkdir(parents=True, exist_ok=True)
            (output_dir / "artifact_lineage.json").write_text(
                json.dumps(_thaw_mapping(_lineage_manifest), indent=2, sort_keys=True)
                + "\n",
                encoding="utf-8",
            )
        except OSError:
            LOGGER.warning("could not persist artifact_lineage.json sidecar")

    return HeadlessAgentResult(
        status=status,
        ok=result.ok,
        response=response,
        artifacts=artifacts,
        readiness=readiness,
        error=response.get("error") if not result.ok else None,
        request=request,
        needs_input=(
            typed_ambiguity
            if typed_ambiguity is not None and effective_route == "clarify"
            else None
        ),
    )


__all__ = ["HeadlessAgentResult", "run_headless", "HeadlessEnvironmentError"]
