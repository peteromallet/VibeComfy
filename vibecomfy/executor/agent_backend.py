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
    BUDGET_FAMILY_APPLY_BATCHES,
    BUDGET_FAMILY_EDIT_CONTINUATIONS,
    BUDGET_FAMILY_REPLACEMENT_ATTEMPTS,
    BUDGET_FAMILY_REPLY_CONTINUATIONS,
    BUDGET_FAMILY_RESEARCH_CONTINUATIONS,
    BUDGET_FAMILY_ROUTE_TOOL_ALLOWLIST,
    BudgetExceeded,
    BudgetUsage,
    CONTINUATION_PARTITION_EDIT,
    CONTINUATION_PARTITION_REPLY,
    CONTINUATION_PARTITION_RESEARCH,
    MAX_EMPTY_RESEARCH_STREAK,
    MessageBudget,
    check_apply_batch,
    check_before_model_call,
    check_before_tool_call,
    check_edit_tool_allowed,
    check_replacement_attempt,
    consume_apply_batch,
    consume_output_tokens,
    consume_replacement_attempt,
    consume_tool_call,
)
from vibecomfy.executor.edit_tools import (  # noqa: E402
    EDIT_TOOL_NAMES,
    EditToolRuntime,
    edit_tool_digest,
)
from vibecomfy.executor.two_step_session import (  # noqa: E402
    DEFAULT_TWO_STEP_SESSION_ROOT,
    ERROR_UNGROUNDED_ANSWER,
    TwoStepSessionError,
    TwoStepSessionState,
    TwoStepSessionStore,
    canonical_workflow_hash,
    derive_research_attempt,
    mint_lease_token,
    project_terminal_product,
)

_HOST_ACTIONS = frozenset({"tool_call", "submit"})


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

    Accepts exactly ``tool_call`` / ``submit``.  Returns a dict with
    an ``action`` key; malformed output raises ``ValueError`` (the caller maps
    it to a typed parse failure without mutating the session).
    """
    from .prompts import _extract_json_object  # noqa: PLC0415

    payload = _extract_json_object(raw)
    action = payload.get("action")
    if action not in _HOST_ACTIONS:
        raise ValueError(
            f"unknown host action {action!r} (expected tool_call or submit)"
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
) -> tuple[BudgetUsage, str, tuple[str, ...]]:
    """Gate, invoke, and record one registered tool call.

    The allowlist/cap/wall-clock gates fire BEFORE dispatch (B02); a denial
    raises :class:`BudgetExceeded` and consumes nothing.  The result is
    projected through the registered ledger projector and recorded in the
    session transcript (evidence ledger).  A missing dispatcher is a typed
    denial, never a ``None(...)`` crash.
    """
    check_before_tool_call(
        message_budget, budget_usage, tool, web_search_enabled=web_search_enabled
    )
    budget_usage = consume_tool_call(message_budget, budget_usage, tool)
    if tool_executor is None:
        raise BudgetExceeded(
            family=BUDGET_FAMILY_ROUTE_TOOL_ALLOWLIST,
            limit=0,
            used=0,
            route=route,
            detail=f"no tool dispatcher configured; cannot invoke {tool!r}.",
        )
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
    return budget_usage, str(digest), tuple(evidence_ids)


def _fact_pack_ids(graph: Any) -> tuple[str, ...]:
    """Stable reply-lens fact IDs for *graph* (surface + topology)."""
    if not graph:
        return ()
    try:
        from vibecomfy.porting.render import render_fact_pack  # noqa: PLC0415

        refs = render_fact_pack(graph, lenses=("surface", "topology"))
        return tuple(str(ref.fact_id) for ref in refs)
    except Exception:  # noqa: BLE001 - fact pack is best-effort context
        return ()


def _finish_reason(result: dict[str, Any]) -> str | None:
    """Return the provider finish reason for the last model turn, if present.

    The worker surfaces ``finish_reason`` both as a top-level key (parse-failure
    envelopes) and inside each ``model_attempt``; either is authoritative.
    """
    value = result.get("finish_reason")
    if isinstance(value, str) and value.strip():
        return value.strip()
    for attempt in reversed(coerce_model_attempts(result.get("model_attempts"))):
        value = attempt.get("finish_reason")
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _is_truncated(result: dict[str, Any]) -> bool:
    """True when the provider cut the model off mid-generation (length cap)."""
    return _finish_reason(result) == "length"


def _plan_known_graph_context(plan: Any) -> str | None:
    """Return the plan's ``known_graph_context`` when present (RC4)."""
    if plan is None:
        return None
    value = getattr(plan, "known_graph_context", None)
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def _graceful_degradation_reply(state: Any, edit_runtime: Any, route: str) -> str:
    """Build a user-facing partial-product reply for a mid-turn budget hit.

    Never echoes the budget diagnostic (RC2): the returned prose is a concrete
    "I ran out of budget before completing X; here's what I have" summary of
    whatever partial product exists (collected research evidence, an accepted
    Δ, or a partial edit graph).
    """
    del route
    deltas = list(state.accepted_delta_ids())
    evidence = list(state.evidence_ids())
    graph = getattr(edit_runtime, "graph", None) if edit_runtime is not None else None
    if deltas or graph is not None:
        product = "a partial edit was applied"
    elif evidence:
        product = f"{len(evidence)} research result(s) were collected"
    else:
        product = "no changes were made yet"
    return (
        "I ran out of budget before completing the request; here's what I have: "
        f"{product}."
    )


def run_execute_turn(
    request: Any,
    *,
    plan: ClassifyDecision | None = None,
    route: str,
    spec: Any,
    session_store: TwoStepSessionStore | None = None,
    session_id: str,
    session_root: str = DEFAULT_TWO_STEP_SESSION_ROOT,
    graph_render: str | None = None,
    model_turn_fn: Any = None,
    tool_executor: Any = None,
    edit_session: Any = None,
    fact_pack: Any = None,
    max_continuations: int | None = None,
    web_search_enabled: bool = False,
    fresh_budget_epoch: bool = False,
    budget_epoch: str | None = None,
) -> dict[str, Any]:
    """Run ONE bounded two-step execute turn for *request*.

    Returns a plain dict (``ok``, ``reply``, ``route``, ``research_attempt``,
    ``accepted_delta_ids``, ``evidence_ids``, ``tool_call_ids``,
    ``lens_fact_ids``, ``budget``, ``graph``, ``claim_validation``,
    ``self_assessment``, ``replacement_used``, ``durable_response``, or
    ``failure``).  Every tool call is dispatched through a REAL route-gated
    ``tool_executor``; editing is NORMAL TOOL USE via the typed edit tools
    (``edit_node`` / ``add_node`` / ``remove_node`` / ``upsert_link``) gated by
    ONE per-turn :class:`EditToolRuntime` over the retained IR; the final
    ``submit`` is parsed into the authoritative :class:`TwoStepFinal` and
    fail-closed validated before the reply is persisted.
    """
    from vibecomfy.comfy_nodes.agent.provider import run_model_turn  # noqa: PLC0415
    from .prompts import build_two_step_execute_messages, parse_two_step_submit  # noqa: PLC0415
    from .contracts import grounding_violations, validate_two_step_final  # noqa: PLC0415

    if model_turn_fn is None:
        model_turn_fn = run_model_turn

    if session_store is None:
        session_store = TwoStepSessionStore(session_root=session_root)

    fingerprint = getattr(request, "idempotency_key", None) or None
    lease_token = None if fingerprint else mint_lease_token()

    # Idempotent replay: a completed fingerprint returns its stored outcome
    # instead of re-running tools/edits.
    if fingerprint:
        prior = session_store.completed_outcome(session_id, fingerprint)
        if prior is not None:
            return prior

    lease_acquired = False

    def _run(initial_state: TwoStepSessionState) -> dict[str, Any]:
        nonlocal graph_render
        state = initial_state
        message_budget = MessageBudget.for_route(route)
        budget_usage = BudgetUsage(route=route)
        turn = (len(state.messages) // 2) + 1
        state = session_store.append(session_id, "route", {"route": route}, turn=turn)
        state = session_store.append(
            session_id,
            "user_message",
            {"query": getattr(request, "query", ""), "route": route},
            turn=turn,
        )
        # Persist the current fact pack (reply-lens ids) when supplied, so the
        # final submit can cite them against the durable lens ledger.
        if fact_pack:
            ids = [str(i) for i in (fact_pack or ()) if i]
            if ids:
                session_store.append(
                    session_id, "lens_fact", {"fact_ids": ids, "route": route}, turn=turn
                )
                state = session_store.load(session_id)

        # ONE per-turn atomic edit runtime (B04): typed edit tools apply
        # copy-on-write to the retained IR (``edit_session.workflow``).  Δ ids
        # are minted from a SESSION-WIDE counter (prior accepted Δs + this
        # message's ordinal) so a later ``d1`` citation is never ambiguous.
        delta_base = len(state.accepted_delta_refs)
        edit_runtime = EditToolRuntime(
            edit_session=edit_session,
            id_factory=(lambda seq, base=delta_base: f"d{base + seq}"),
        )

        def _terminal(
            failure: BaseException | None = None,
            *,
            reply: str | None = None,
            ok: bool | None = None,
            claim_validation: dict[str, Any] | None = None,
            self_assessment: Any = None,
            durable_response: dict[str, Any] | None = None,
            soft_stop: dict[str, Any] | None = None,
        ) -> dict[str, Any]:
            """Project the ONE terminal outcome for every terminal path.

            Budget stop, parse failure, grounding failure, second-apply soft
            stop, and normal submit ALL route through this single projector so
            an accepted Δ and its replayed graph can never be dropped at a
            terminal boundary (RC-P2 P0).  No separate success-only extractor.
            """
            return project_terminal_product(
                session_store=session_store,
                session_id=session_id,
                edit_runtime=edit_runtime,
                route=route,
                reply=reply,
                failure=failure,
                claim_validation=claim_validation,
                ok=ok,
                self_assessment=self_assessment,
                durable_response=durable_response,
                soft_stop=soft_stop,
            ).to_outcome_dict()

        def _failure_outcome(failure: BaseException) -> dict[str, Any]:
            """Wrap a loop failure with a graceful reply for budget hits (RC2).

            Budget denial/exhaustion (and the continuation-cap ``stale_message``)
            must never leak the diagnostic string as the user-facing reply:
            attach a concrete partial-product reply and let the caller surface
            it.  Genuine fail-closed errors (parse / submit validation) keep
            ``reply=None`` and are reported as typed failures.  The projected
            outcome still carries any accepted Δ + replayed graph.
            """
            graceful = isinstance(failure, BudgetExceeded) or (
                isinstance(failure, TwoStepSessionError)
                and getattr(failure, "kind", None) == "stale_message"
            )
            reply = (
                _graceful_degradation_reply(state, edit_runtime, route)
                if graceful
                else None
            )
            return _terminal(failure, reply=reply, ok=False)

        continuation = 0
        grounding_retry_used = False
        # RC-P3: per-purpose continuation partitioning.  Each model turn is
        # admitted against ONE purpose's reserve (research/discovery 40,
        # edit/recovery 16, final synthesis/reply 8); research may not borrow
        # the edit/reply reserve.  ``research_closed_reason`` latches
        # reply-only mode after a successful apply or repeated no-result
        # research, so the agent transitions to a grounded reply instead of
        # restarting the same search.
        purpose_used = {"research": 0, "edit": 0, "reply": 0}
        research_closed_reason: str | None = None
        empty_research_streak = 0
        while True:
            session_budget = state.budget
            try:
                session_budget = session_budget.record_model_continuation()
            except BudgetExceeded as exc:
                return _failure_outcome(exc)
            cap = (
                max_continuations
                if max_continuations is not None
                else session_budget.max_model_continuations
            )
            if continuation >= cap:
                return _failure_outcome(
                    TwoStepSessionError(
                        "stale_message",
                        "execute continuation budget exhausted",
                        session_id=session_id,
                    )
                )

            # RC3: measure wall clock from THIS model turn, never from session
            # open — classify/research/worker queueing that precedes the first
            # model call must not consume the per-message ceiling.
            budget_usage = budget_usage.reset_wall_clock()
            check_before_model_call(message_budget, budget_usage)
            transcript = _render_compact_transcript(state)
            messages = build_two_step_execute_messages(
                getattr(request, "query", ""),
                route=route,
                plan=plan,
                graph_render=graph_render,
                known_graph_context=_plan_known_graph_context(plan),
                transcript=transcript,
                web_search_enabled=web_search_enabled,
            )
            result = model_turn_fn(
                getattr(request, "query", ""),
                messages,
                route=getattr(spec, "agent", None),
                model=getattr(spec, "model", None),
                effort=message_budget.effort,
                response_contract="json",
                remaining_output_cap=session_budget.remaining_output_tokens(),
            )
            raw = _extract_content(result)
            tokens = _completion_tokens(result, raw)

            # RC1: a provider length-cap (finish_reason=length) is NOT a
            # terminal failure — record the truncated output, count it, and
            # re-invoke the model with the accumulated transcript so it resumes
            # from where it was cut off.
            if _is_truncated(result):
                try:
                    budget_usage = consume_output_tokens(message_budget, budget_usage, tokens)
                    session_budget = session_budget.record_output_tokens(tokens)
                except BudgetExceeded as exc:
                    return _failure_outcome(exc)
                state = session_store.append(
                    session_id,
                    "model_truncated",
                    {"content": raw or ""},
                    turn=turn,
                )
                state = session_store.append(
                    session_id, "budget", {"budget": session_budget.to_dict()}, turn=turn
                )
                continuation += 1
                continue

            try:
                budget_usage = consume_output_tokens(message_budget, budget_usage, tokens)
            except BudgetExceeded as exc:
                return _failure_outcome(exc)
            try:
                session_budget = session_budget.record_output_tokens(tokens)
            except BudgetExceeded as exc:
                return _failure_outcome(exc)
            state = session_store.append(
                session_id, "budget", {"budget": session_budget.to_dict()}, turn=turn
            )

            try:
                action = _parse_host_action(raw)
            except Exception as exc:
                return _failure_outcome(exc)

            kind = action.get("action")
            if kind == "tool_call":
                tool = str(action.get("tool") or "")
                raw_args = action.get("args")
                if tool in EDIT_TOOL_NAMES:
                    # Typed edit tool (Hermes-style): gate on the route
                    # allowlist + per-message apply/replacement CAS, dispatch
                    # through the atomic edit runtime, persist the accepted Δ /
                    # rejection (transcript FIRST, then the sidecar cache), and
                    # record the STRUCTURED result (never only a prose digest)
                    # so the next continuation can cite the Δ id.
                    if purpose_used["edit"] >= CONTINUATION_PARTITION_EDIT:
                        session_store.append(
                            session_id,
                            "purpose_denied",
                            {
                                "purpose": "edit",
                                "detail": "edit/recovery continuation partition exhausted",
                                "route": route,
                            },
                            turn=turn,
                        )
                        state = session_store.load(session_id)
                        continuation += 1
                        continue
                    purpose_used["edit"] += 1
                    try:
                        check_edit_tool_allowed(route, tool)
                    except BudgetExceeded as exc:
                        return _failure_outcome(exc)
                    was_replacement = edit_runtime.replacement_used
                    try:
                        if was_replacement:
                            check_replacement_attempt(message_budget, budget_usage)
                        else:
                            check_apply_batch(message_budget, budget_usage)
                    except BudgetExceeded as exc:
                        if (
                            exc.family
                            in {BUDGET_FAMILY_APPLY_BATCHES, BUDGET_FAMILY_REPLACEMENT_ATTEMPTS}
                            and state.accepted_delta_ids()
                        ):
                            # Soft commit stop (RC-P2 P0): the first accepted Δ
                            # stands; the second edit/apply attempt is recorded
                            # as unapplied — NOT a destructive terminal error.
                            session_store.append(
                                session_id,
                                "apply_soft_stop",
                                {
                                    "family": exc.family,
                                    "tool": tool,
                                    "route": route,
                                },
                                turn=turn,
                            )
                            state = session_store.load(session_id)
                            return _terminal(
                                ok=True,
                                reply=_graceful_degradation_reply(state, edit_runtime, route),
                                claim_validation={"status": "ok", "violations": []},
                                soft_stop={"family": exc.family, "tool": tool},
                            )
                        return _failure_outcome(exc)
                    outcome = edit_runtime.dispatch(tool, raw_args)
                    call_id = f"call:{session_id}:{turn}:{tool}:{len(state.evidence_ledger) + 1}"
                    structured = outcome.structured_result(call_id, tool)
                    session_store.append(
                        session_id,
                        "tool_call",
                        {
                            "tool": tool,
                            "args": raw_args,
                            "evidence_ids": [],
                            "digest": edit_tool_digest(tool, raw_args if isinstance(raw_args, dict) else {}, outcome),
                            "result": structured,
                            "route": route,
                        },
                        turn=turn,
                    )
                    if edit_runtime.replacement_used and not was_replacement:
                        budget_usage = consume_replacement_attempt(message_budget, budget_usage)
                        try:
                            session_budget = session_budget.record_replacement_attempt()
                        except BudgetExceeded as exc:
                            return _failure_outcome(exc)
                    if outcome.ok:
                        # RC-P3: a successful apply closes research for this
                        # message — the agent enters reply-only mode (further
                        # research tool calls are denied).
                        research_closed_reason = "successful apply (reply-only mode)"
                        budget_usage = consume_apply_batch(message_budget, budget_usage)
                        try:
                            session_budget = session_budget.record_apply_batch()
                        except BudgetExceeded as exc:
                            return _failure_outcome(exc)
                        graph = outcome.graph
                        # Transcript-authoritative durability: the accepted Δ is
                        # appended BEFORE the sidecar is (re)written, so a crash
                        # between the two leaves the transcript as truth.
                        session_store.append(
                            session_id,
                            "delta_accepted",
                            {
                                "delta_ids": [outcome.delta_id] if outcome.delta_id else [],
                                "ops": list(outcome.op_dicts),
                                "workflow_hash": canonical_workflow_hash(graph),
                            },
                            turn=turn,
                        )
                        if outcome.lens_fact_ids:
                            session_store.append(
                                session_id,
                                "lens_fact",
                                {"fact_ids": list(outcome.lens_fact_ids), "route": route},
                                turn=turn,
                            )
                        if graph is not None:
                            session_store.write_workflow(session_id, graph)
                        session_store.append(
                            session_id,
                            "apply_accepted",
                            {
                                "delta_ids": [outcome.delta_id] if outcome.delta_id else [],
                                "route": route,
                            },
                            turn=turn,
                        )
                        # Same-history semantics: the next continuation's render
                        # reflects the accepted edit.
                        graph_render = edit_runtime.render_text()
                    else:
                        # Feed the rejection back so the single allowed
                        # replacement continuation sees why the edit was refused.
                        session_store.append(
                            session_id,
                            "apply_rejected",
                            {
                                "reason": str(outcome.reason or "rejected"),
                                "diagnostics": list(outcome.diagnostics or ()),
                                "replacement_allowed": bool(outcome.replacement_allowed),
                                "no_candidate": bool(outcome.no_candidate),
                                "error": outcome.error,
                                "route": route,
                            },
                            turn=turn,
                        )
                    state = session_store.append(
                        session_id, "budget", {"budget": session_budget.to_dict()}, turn=turn
                    )
                    state = session_store.load(session_id)
                else:
                    if (
                        research_closed_reason is not None
                        or purpose_used["research"] >= CONTINUATION_PARTITION_RESEARCH
                    ):
                        detail = (
                            f"research closed: {research_closed_reason}"
                            if research_closed_reason is not None
                            else "research/discovery continuation partition exhausted"
                        )
                        session_store.append(
                            session_id,
                            "purpose_denied",
                            {"purpose": "research", "detail": detail, "route": route},
                            turn=turn,
                        )
                        state = session_store.load(session_id)
                        continuation += 1
                        continue
                    purpose_used["research"] += 1
                    args = raw_args if isinstance(raw_args, dict) else {}
                    try:
                        budget_usage, _digest, _eids = _run_tool_call(
                            store=session_store,
                            session_id=session_id,
                            turn=turn,
                            route=route,
                            tool=tool,
                            args=args,
                            message_budget=message_budget,
                            budget_usage=budget_usage,
                            tool_executor=tool_executor,
                            web_search_enabled=web_search_enabled,
                        )
                        session_budget = session_budget.record_tool_call()
                    except BudgetExceeded as exc:
                        # Route-allowlist denial or call-cap breach: a typed budget
                        # failure carrying the canonical B02 ``family``.
                        return _failure_outcome(exc)
                    if _eids:
                        empty_research_streak = 0
                    else:
                        empty_research_streak += 1
                        if empty_research_streak >= MAX_EMPTY_RESEARCH_STREAK:
                            research_closed_reason = "repeated no-result research"
                    state = session_store.append(
                        session_id, "budget", {"budget": session_budget.to_dict()}, turn=turn
                    )
                    state = session_store.load(session_id)
            elif kind == "submit":
                if purpose_used["reply"] >= CONTINUATION_PARTITION_REPLY:
                    return _failure_outcome(
                        BudgetExceeded(
                            family=BUDGET_FAMILY_REPLY_CONTINUATIONS,
                            limit=CONTINUATION_PARTITION_REPLY,
                            used=purpose_used["reply"],
                            route=route,
                            detail="final synthesis/reply continuation partition exhausted",
                        )
                    )
                purpose_used["reply"] += 1
                state = session_store.load(session_id)
                final = parse_two_step_submit(action)
                grounding = grounding_violations(
                    final,
                    evidence_tools=state.evidence_tool_map(),
                    accepted_delta_ids=state.accepted_delta_ids(),
                )
                if grounding:
                    if not grounding_retry_used:
                        # P2: ONE bounded corrective continuation.  Feed the
                        # diagnostics back so the model can re-submit with
                        # proper citations; the second violation fails closed.
                        grounding_retry_used = True
                        session_store.append(
                            session_id,
                            "grounding_retry",
                            {"violations": list(grounding)},
                            turn=turn,
                        )
                        state = session_store.load(session_id)
                        continuation += 1
                        continue
                    exc = TwoStepSessionError(
                        ERROR_UNGROUNDED_ANSWER,
                        "; ".join(grounding),
                        session_id=session_id,
                    )
                    return _terminal(exc, ok=False)
                violations = validate_two_step_final(
                    final,
                    accepted_delta_ids=state.accepted_delta_ids(),
                    lens_fact_ids=state.lens_fact_ids(),
                    evidence_ids=state.evidence_ids(),
                    evidence_tools=state.evidence_tool_map(),
                )
                if violations:
                    exc = TwoStepSessionError(
                        "missing_delta_reference",
                        "; ".join(violations),
                        session_id=session_id,
                    )
                    return _terminal(exc, ok=False)
                # One-step: the model's FINAL MESSAGE text (the last assistant
                # turn's prose) IS the reply — not the structured submit
                # contract's ``reply`` field.  Fall back to that field only
                # when the final message is empty/missing.
                reply_text = (raw or "").strip() or final.reply
                session_store.append(
                    session_id,
                    "reply",
                    {"reply": reply_text, "route": route},
                    turn=turn,
                )
                state = session_store.load(session_id)
                return _terminal(
                    ok=True,
                    reply=reply_text,
                    claim_validation={"status": "ok", "violations": []},
                    self_assessment=(
                        final.self_assessment.to_dict()
                        if final.self_assessment is not None
                        else None
                    ),
                    durable_response={
                        "reply": reply_text,
                        "session_id": session_id,
                        "route": route,
                    },
                )
            continuation += 1

    try:
        state = session_store.begin_message(
            session_id,
            base_graph=getattr(request, "graph", None),
            expected_baseline_hash=getattr(request, "expected_baseline_graph_hash", None),
            message_fingerprint=fingerprint,
            lease_token=lease_token,
            fresh_budget_epoch=fresh_budget_epoch,
            budget_epoch=budget_epoch,
        )
        lease_acquired = True
    except TwoStepSessionError as exc:
        # Even a begin-message identity failure (stale/expired/concurrent)
        # projects the retained product: prior accepted Δ + replayed graph must
        # survive this terminal boundary too (RC-P2 P0).
        return project_terminal_product(
            session_store=session_store,
            session_id=session_id,
            edit_runtime=None,
            route=route,
            reply=None,
            failure=exc,
            ok=False,
        ).to_outcome_dict()

    outcome: dict[str, Any]
    try:
        outcome = _run(state)
    finally:
        if lease_acquired:
            try:
                session_store.end_message(
                    session_id,
                    message_fingerprint=fingerprint,
                    lease_token=lease_token,
                )
            except Exception:  # noqa: BLE001 - best-effort marker clear
                pass

    if fingerprint:
        try:
            session_store.record_completed(session_id, fingerprint, outcome)
        except Exception:  # noqa: BLE001 - best-effort idempotency record
            pass
    return outcome


__all__ = ["run_classify_turn", "run_reply_turn", "run_execute_turn"]
