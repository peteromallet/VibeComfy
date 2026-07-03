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
from typing import Any, Mapping

from vibecomfy.executor.profiler import new_profile_id, profiler_span, short_text

from .prompts import (
    build_classify_messages,
    build_reply_messages,
    parse_classify_response,
    parse_reply_response,
)
from .contracts import ClassifyDecision

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


def run_classify_turn(
    query: str,
    *,
    route: str,
    model: str,
    has_graph: bool = False,
    graph_summary: str | None = None,
    layout_hint: Mapping[str, Any] | None = None,
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
    layout_hint:
        Optional compact deterministic layout evidence for classify context.
    messages:
        Optional pre-built messages list.  When provided, skips the default
        message building and uses this list directly.
    """
    if messages is None:
        messages = build_classify_messages(
            query,
            has_graph=has_graph,
            graph_summary=graph_summary,
            layout_hint=layout_hint,
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
            response_contract="json",
        )
        raw = _extract_content(result)
        decision = parse_classify_response(raw)
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
) -> str:
    """Run a single reply model turn through the provider seam.

    Builds reply-specific messages via :func:`build_reply_messages`,
    dispatches through :func:`run_model_turn` with ``response_contract="json"``,
    and parses the result with :func:`parse_reply_response`.

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
    )
    model_turn_id = new_profile_id("model")
    with profiler_span(
        LOGGER,
        "executor.model_turn",
        model_turn_id=model_turn_id,
        backend_phase="reply",
        route=route,
        model=model,
        response_contract="json",
        query_preview=short_text(query),
    ) as span:
        from vibecomfy.comfy_nodes.agent.provider import run_model_turn

        result = run_model_turn(
            query,
            messages,
            route=route,
            model=model,
            response_contract="json",
        )
        raw = _extract_content(result)
        reply = parse_reply_response(raw)
        span.update(content_length=len(raw), reply_preview=short_text(reply))
        return reply


__all__ = ["run_classify_turn", "run_reply_turn"]
