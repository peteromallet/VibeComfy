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
    research_memo: dict[str, Any] | None = None,
    research_ledger: dict[str, Any] | None = None,
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
    research_attempt: str | None = None,
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
        research_memo=research_memo,
        research_ledger=research_ledger,
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
        research_attempt=research_attempt,
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


# ── two-step bounded continuation loop (B03) ─────────────────────────────────
#
# One logical execute-session identity across messages and route changes.  The
# loop re-injects the compact accumulated transcript into EVERY continuation by
# FLATTENING it into the final user payload — ``runtime._split_messages`` keeps
# only the first system + last user message, so assistant/tool history passed
# as ordinary messages would be silently dropped.  No provider-native memory is
# used: continuity is host-owned via the durable session transcript.

from vibecomfy.executor.two_step import (  # noqa: E402
    BudgetUsage,
    MessageBudget,
    check_before_model_call,
    check_before_tool_call,
    consume_output_tokens,
    consume_tool_call,
)
from vibecomfy.executor.two_step_session import (  # noqa: E402
    TwoStepSessionError,
    TwoStepSessionState,
    TwoStepSessionStore,
    derive_research_attempt,
)

_HOST_ACTIONS = frozenset({"tool_call", "apply", "submit"})


def _completion_tokens(result: dict[str, Any], raw: str | None) -> int:
    """Best-effort completion-token count from worker evidence, else a fallback."""
    attempts = coerce_model_attempts(result.get("model_attempts"))
    for attempt in reversed(attempts):
        usage = attempt.get("token_usage")
        if isinstance(usage, dict):
            value = usage.get("completion_tokens")
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                return max(0, int(value))
    return max(0, len(raw or "") // 4)


def _parse_host_action(raw: str) -> dict[str, Any]:
    """Parse one host action JSON object from model output.

    Accepts exactly ``tool_call`` / ``apply`` / ``submit``.  Returns a dict with
    an ``action`` key; malformed output raises ``ValueError`` (the caller maps
    it to a typed parse failure without mutating the session).
    """
    from .prompts import _extract_json_object  # noqa: PLC0415

    payload = _extract_json_object(raw)
    action = payload.get("action")
    if action not in _HOST_ACTIONS:
        raise ValueError(
            f"unknown host action {action!r} (expected tool_call, apply, or submit)"
        )
    return payload


def _render_compact_transcript(state: TwoStepSessionState, *, limit: int = 2400) -> str:
    """Render the compact accumulated transcript for re-injection.

    Only the durable message log is rendered (never an in-memory dict as the
    authority); content is length-bounded so the flattened payload stays compact.
    """
    lines: list[str] = []
    for message in state.messages:
        role = str(message.get("role") or "")
        content = str(message.get("content") or "")
        if not content.strip():
            continue
        turn = message.get("turn")
        label = f"[turn {turn}]" if turn else ""
        if len(content) > 200:
            content = content[:197].rstrip() + "..."
        lines.append(f"{label}[{role}]: {content}")
    text = "\n".join(lines)
    if len(text) > limit:
        text = text[-limit:]
    return text or "(none)"


def _run_tool_call(
    *,
    store: TwoStepSessionStore,
    session_id: str,
    turn: int,
    route: str,
    tool: str,
    args: dict[str, Any],
    message_budget: MessageBudget,
    budget_usage: BudgetUsage,
    tool_executor: Any,
    web_search_enabled: bool,
) -> tuple[BudgetUsage, str]:
    """Gate, invoke, and record one registered tool call.

    The allowlist/cap/wall-clock gates fire BEFORE dispatch (B02); a denial
    raises :class:`BudgetExceeded` and consumes nothing.  The result is
    projected through the registered ledger projector and recorded in the
    session transcript (evidence ledger).
    """
    check_before_tool_call(
        message_budget, budget_usage, tool, web_search_enabled=web_search_enabled
    )
    budget_usage = consume_tool_call(message_budget, budget_usage, tool)
    result = tool_executor(tool, args)
    if result is None:
        digest = f"{tool}({sorted(args)})"
        evidence_ids: list[str] = []
    else:
        # result is expected to be (evidence_artifacts, ledger_entry, digest)
        artifacts, _entry, digest = result
        evidence_ids = list(artifacts) if isinstance(artifacts, dict) else []
    store.append(
        session_id,
        "tool_call",
        {
            "tool": tool,
            "args": args,
            "evidence_ids": evidence_ids,
            "digest": str(digest),
            "route": route,
        },
        turn=turn,
    )
    return budget_usage, str(digest)


def run_execute_turn(
    request: Any,
    *,
    plan: ClassifyDecision,
    route: str,
    spec: Any,
    session_store: TwoStepSessionStore,
    session_id: str,
    graph_render: str | None = None,
    model_turn_fn: Any = None,
    tool_executor: Any = None,
    max_continuations: int | None = None,
) -> dict[str, Any]:
    """Run ONE bounded two-step execute turn for *request*.

    Returns a plain dict (``ok``, ``reply``, ``route``, ``research_attempt``,
    ``accepted_delta_ids``, ``budget``, ``failure``).  The heavy edit state
    machine (parse/apply/gate/commit) is B04; B03 owns the bounded loop, host
    action parsing, tool execution, transcript re-injection, and session
    identity.
    """
    from vibecomfy.comfy_nodes.agent.provider import run_model_turn  # noqa: PLC0415

    if model_turn_fn is None:
        model_turn_fn = run_model_turn

    # Validate identity/staleness/concurrency BEFORE any model work.
    try:
        state = session_store.begin_message(
            session_id,
            base_graph=getattr(request, "graph", None),
            expected_baseline_hash=getattr(request, "expected_baseline_graph_hash", None),
            message_fingerprint=getattr(request, "idempotency_key", None),
        )
    except TwoStepSessionError as exc:
        return {"ok": False, "reply": None, "route": route, "failure": exc}

    message_budget = MessageBudget.for_route(route)
    budget_usage = BudgetUsage(route=route)
    turn = (len(state.messages) // 2) + 1
    state = session_store.append(session_id, "route", {"route": route}, turn=turn)
    state = session_store.append(
        session_id, "user_message", {"query": getattr(request, "query", ""), "route": route}, turn=turn
    )

    try:
        continuation = 0
        while True:
            session_budget = state.budget
            try:
                session_budget = session_budget.record_model_continuation()
            except Exception as exc:  # BudgetExceeded
                return {"ok": False, "reply": None, "route": route, "failure": exc}
            cap = max_continuations if max_continuations is not None else session_budget.max_model_continuations
            if continuation >= cap:
                return {"ok": False, "reply": None, "route": route, "failure": TwoStepSessionError(
                    "stale_message", "execute continuation budget exhausted", session_id=session_id
                )}

            check_before_model_call(message_budget, budget_usage)
            transcript = _render_compact_transcript(state)
            from .prompts import build_two_step_execute_messages  # noqa: PLC0415

            messages = build_two_step_execute_messages(
                getattr(request, "query", ""),
                route=route,
                plan=plan,
                graph_render=graph_render,
                transcript=transcript,
            )
            result = model_turn_fn(
                getattr(request, "query", ""),
                messages,
                route=getattr(spec, "agent", None),
                model=getattr(spec, "model", None),
                effort=getattr(spec, "effort", None),
                response_contract="json",
                remaining_output_cap=session_budget.remaining_output_tokens(),
            )
            raw = _extract_content(result)
            tokens = _completion_tokens(result, raw)
            budget_usage = consume_output_tokens(message_budget, budget_usage, tokens)
            session_budget = session_budget.record_output_tokens(tokens)
            state = session_store.append(
                session_id, "budget", {"budget": session_budget.to_dict()}, turn=turn
            )

            try:
                action = _parse_host_action(raw)
            except Exception as exc:
                return {"ok": False, "reply": None, "route": route, "failure": exc}

            kind = action.get("action")
            if kind == "tool_call":
                tool = str(action.get("tool") or "")
                args = action.get("args") if isinstance(action.get("args"), dict) else {}
                budget_usage, _digest = _run_tool_call(
                    store=session_store,
                    session_id=session_id,
                    turn=turn,
                    route=route,
                    tool=tool,
                    args=args,
                    message_budget=message_budget,
                    budget_usage=budget_usage,
                    tool_executor=tool_executor,
                    web_search_enabled=False,
                )
                state = session_store.load(session_id)
            elif kind == "apply":
                session_store.append(
                    session_id,
                    "apply",
                    {"python": str(action.get("python") or ""), "route": route},
                    turn=turn,
                )
                state = session_store.load(session_id)
            elif kind == "submit":
                delta_ids = action.get("delta_ids") or ()
                state = session_store.load(session_id)
                try:
                    state.validate_delta_references(delta_ids)
                except TwoStepSessionError as exc:
                    # Typed session errors (forged/unknown delta references)
                    # are a documented dict result, not a propagation: the
                    # finally block still clears the message marker.
                    return {"ok": False, "reply": None, "route": route, "failure": exc}
                reply_text = str(action.get("reply") or "")
                session_store.append(
                    session_id,
                    "reply",
                    {"reply": reply_text, "route": route},
                    turn=turn,
                )
                state = session_store.load(session_id)
                return {
                    "ok": True,
                    "reply": reply_text,
                    "route": route,
                    "research_attempt": state.research_attempt(),
                    "accepted_delta_ids": list(state.accepted_delta_ids()),
                    "budget": state.budget,
                }
            continuation += 1
    finally:
        try:
            session_store.end_message(
                session_id, message_fingerprint=getattr(request, "idempotency_key", None)
            )
        except Exception:  # noqa: BLE001 - best-effort marker clear
            pass


__all__ = ["run_classify_turn", "run_reply_turn", "run_execute_turn"]
