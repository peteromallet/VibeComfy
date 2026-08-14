"""Executor model-call wrappers over the VibeComfy provider/runtime seam.

These functions bridge the executor's prompt-building + response-parsing
machinery (``prompts.py``) with the provider seam (``provider.run_model_turn``)
so that classify and reply model turns route through the same
provider/runtime/worker stack as the agent-edit loop — preserving subprocess
isolation and never importing Arnold agent backends in the ComfyUI process.

Every function accepts ``route`` and ``model`` kwargs and passes them through
to the provider, ensuring the resolved profile specs reach the worker.
"""

from __future__ import annotations

import logging
import json
from typing import Any

from vibecomfy.executor.profiler import new_profile_id, profiler_span, short_text

from .prompts import (
    build_classify_messages,
    build_reply_messages,
    parse_classify_response,
    parse_reply_response,
)
from .contracts import (
    ClassifyDecision,
    ModelAttemptEvidence,
    coerce_model_attempts,
    redact_model_preview,
)

LOGGER = logging.getLogger(__name__)


def _extract_content(result: dict[str, Any]) -> str:
    """Extract the raw model output text from a provider result."""
    content = result.get("content")
    if isinstance(content, str) and content.strip():
        return content
    # Fall back to the json payload's raw text if content is missing.
    json_payload = result.get("json")
    if isinstance(json_payload, dict):
        # Re-serialise the parsed JSON so parsers get text.
        import json

        return json.dumps(json_payload)
    raise ValueError(
        "Model turn result did not contain text content. "
        f"Got keys: {sorted(result.keys())}"
    )


def _preview_raw(text: str | None, *, limit: int = 1200) -> str | None:
    """Bounded, whitespace-normalized preview of raw model output."""
    return redact_model_preview(text, limit=limit)


def _attach_model_turn_evidence(
    exc: BaseException,
    result: dict[str, Any] | None,
    *,
    model: str,
    phase: str,
    raw: str | None,
) -> None:
    """Attach additive parse evidence to a classify/reply exception in place.

    The provider result dict carries the worker's deepseek_usage plus the
    resolved model/phase/endpoint; attaching it (and the raw content preview)
    lets the executor's failure envelope persist tokens + raw preview + context
    without re-resolving provider internals.
    """
    try:
        if result is not None and getattr(exc, "worker_result", None) is None:
            exc.worker_result = dict(result)  # type: ignore[attr-defined]
        if result is not None and getattr(exc, "model_attempts", None) is None:
            exc.model_attempts = list(coerce_model_attempts(result.get("model_attempts")))  # type: ignore[attr-defined]
        if raw is not None and getattr(exc, "raw_response_preview", None) is None:
            exc.raw_response_preview = _preview_raw(raw)  # type: ignore[attr-defined]
        for name, value in (("model", model), ("phase", phase)):
            if getattr(exc, name, None) is None:
                setattr(exc, name, value)
        if getattr(exc, "requested_model", None) is None:
            exc.requested_model = model  # type: ignore[attr-defined]
    except Exception:  # noqa: BLE001 - evidence attachment is best-effort
        pass


def _downstream_failure_type(raw: str | None) -> str:
    if not isinstance(raw, str) or not raw.strip():
        return "empty_response"
    stripped = raw.strip()
    if stripped.startswith("```"):
        stripped = stripped.removeprefix("```json").removeprefix("```")
        stripped = stripped.rsplit("```", 1)[0].strip()
    try:
        parsed = json.loads(stripped)
    except (json.JSONDecodeError, TypeError):
        return "malformed_json" if "{" in stripped else "non_json_content"
    return "missing_required_fields" if isinstance(parsed, dict) else "non_json_content"


def _record_result_attempts(result: dict[str, Any]) -> None:
    from vibecomfy.comfy_nodes.agent.runtime import record_model_attempts

    record_model_attempts(result.get("model_attempts"))


def _mark_last_attempt_failed(
    result: dict[str, Any], *, raw: str | None, failure_type: str
) -> None:
    attempts = list(coerce_model_attempts(result.get("model_attempts")))
    if not attempts:
        return
    latest = dict(attempts[-1])
    latest.update({
        "outcome": "failure",
        "failure_type": failure_type,
        "raw_response_preview": raw,
    })
    revised = ModelAttemptEvidence.from_mapping(latest).to_dict()
    attempts[-1] = revised
    result["model_attempts"] = attempts
    from vibecomfy.comfy_nodes.agent.runtime import replace_last_model_attempt

    replace_last_model_attempt(revised)


def run_classify_turn(
    query: str,
    *,
    route: str,
    model: str,
    effort: str | None = None,
    has_graph: bool = False,
    graph_summary: str | None = None,
    messages: list[dict[str, str]] | None = None,
) -> ClassifyDecision:
    """Run a single classify model turn through the provider seam.

    Builds classify-specific messages via :func:`build_classify_messages`,
    dispatches through :func:`run_model_turn` with ``response_contract="json"``,
    and parses the result with :func:`parse_classify_response`.

    When *messages* is provided, it is used directly instead of building
    messages from *query* / *has_graph* / *graph_summary*.  This allows
    callers to pre-enrich messages with session context and graph reference
    maps without changing the classify route signature.

    Parameters
    ----------
    query:
        The user's natural-language request.
    route:
        Provider route name (resolved from the profile's ``agent`` field).
    model:
        Model identifier (resolved from the profile's ``model`` field).
    has_graph:
        Whether a ComfyUI canvas graph is attached to the request.
    graph_summary:
        Optional compact summary of the attached graph (≤ 200 chars).
    messages:
        Optional pre-built messages list.  When provided, skips the default
        message building and uses this list directly.
    """
    if messages is None:
        messages = build_classify_messages(
            query,
            has_graph=has_graph,
            graph_summary=graph_summary,
        )
    model_turn_id = new_profile_id("model")
    with profiler_span(
        LOGGER,
        "executor.model_turn",
        model_turn_id=model_turn_id,
        backend_phase="classify",
        route=route,
        model=model,
        response_contract="json",
        has_graph=has_graph,
        graph_summary=graph_summary,
        query_preview=short_text(query),
    ) as span:
        from vibecomfy.comfy_nodes.agent.provider import run_model_turn

        result = run_model_turn(
            query,
            messages,
            route=route,
            model=model,
            effort=effort,
            response_contract="json",
            profiling_context={"backend_phase": "classify"},
        )
        raw: str | None = None
        try:
            raw = _extract_content(result)
            decision = parse_classify_response(raw)
        except Exception as exc:  # noqa: BLE001 - attach evidence, then re-raise
            _mark_last_attempt_failed(
                result,
                raw=raw,
                failure_type=_downstream_failure_type(raw),
            )
            _attach_model_turn_evidence(
                exc,
                result,
                model=model,
                phase="classify",
                raw=raw,
            )
            raise
        _record_result_attempts(result)
        span.update(
            content_length=len(raw),
            plan_research=decision.research,
            plan_implement=decision.implement,
            plan_reply=decision.reply,
        )
        return decision


def run_reply_turn(
    query: str,
    *,
    route: str,
    model: str,
    effort: str | None = None,
    plan: ClassifyDecision | None = None,
    research_summary: str | None = None,
    research_sources: tuple[dict[str, Any], ...] | None = None,
    research_warnings: tuple[str, ...] | None = None,
    research_precedent_slices: tuple[dict[str, Any], ...] | None = None,
    implementation_message: str | None = None,
    graph_summary: str | None = None,
    graph_inspection: str | None = None,
    adaptation_plan: dict[str, Any] | None = None,
    effective_route: str | None = None,
    effective_task: str | None = None,
    candidate_present: bool = False,
    interaction_mode: str | None = None,
) -> str:
    """Run a single reply model turn through the provider seam.

    Builds reply-specific messages via :func:`build_reply_messages`,
    dispatches through :func:`run_model_turn` with
    ``response_contract="text"`` (the reply phase accepts plain prose; a
    ``{"reply": ...}`` JSON object is still parsed for backward
    compatibility), and parses the result with
    :func:`parse_reply_response`.

    Parameters
    ----------
    query:
        The user's natural-language request.
    route:
        Provider route name (resolved from the profile's ``agent`` field).
    model:
        Model identifier (resolved from the profile's ``model`` field).
    plan:
        The classify decision (provides context for the reply).
    research_summary:
        Optional research findings summary.
    research_sources:
        Optional deduplicated research sources for reply context.
    implementation_message:
        Optional implementation result message.
    graph_summary:
        Optional compact summary of the attached graph.
    graph_inspection:
        Optional detailed node-by-node graph inspection for inspect-only
        replies.  When provided, the model should describe the graph
        structure without suggesting edits.
    adaptation_plan:
        Optional serialized adaptation plan for route="adapt" replies.
    effective_route:
        The canonical route driving the reply phase.
    effective_task:
        The canonical task driving the reply phase.
    candidate_present:
        Whether a graph edit candidate was produced.
    """
    messages = build_reply_messages(
        query,
        plan=plan,
        research_summary=research_summary,
        research_sources=research_sources,
        research_warnings=research_warnings,
        research_precedent_slices=research_precedent_slices,
        implementation_message=implementation_message,
        graph_summary=graph_summary,
        graph_inspection=graph_inspection,
        adaptation_plan=adaptation_plan,
        effective_route=effective_route,
        effective_task=effective_task,
        candidate_present=candidate_present,
        interaction_mode=interaction_mode,
    )
    model_turn_id = new_profile_id("model")
    with profiler_span(
        LOGGER,
        "executor.model_turn",
        model_turn_id=model_turn_id,
        backend_phase="reply",
        route=route,
        model=model,
        response_contract="text",
        query_preview=short_text(query),
    ) as span:
        from vibecomfy.comfy_nodes.agent.provider import run_model_turn

        result = run_model_turn(
            query,
            messages,
            route=route,
            model=model,
            effort=effort,
            response_contract="text",
            profiling_context={"backend_phase": "reply"},
        )
        raw: str | None = None
        try:
            raw = _extract_content(result)
            reply = parse_reply_response(raw)
        except Exception as exc:  # noqa: BLE001 - attach evidence, then re-raise
            _mark_last_attempt_failed(
                result,
                raw=raw,
                failure_type=_downstream_failure_type(raw),
            )
            _attach_model_turn_evidence(
                exc,
                result,
                model=model,
                phase="reply",
                raw=raw,
            )
            raise
        _record_result_attempts(result)
        span.update(content_length=len(raw), reply_preview=short_text(reply))
        return reply


__all__ = ["run_classify_turn", "run_reply_turn"]
