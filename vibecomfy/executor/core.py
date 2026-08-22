"""Executor orchestration: classify → research → implement → reply.

Implements the full executor pipeline (SD1).  Every request flows through
classify (always calls the model backend), then optionally research and/or
implement, then always reply via the model backend.

Failures are converted through an injected host port — raw exceptions never
leak out of this module, and importing the plain executor does not eagerly
load ComfyUI provider, runtime-capture, edit, or session internals.
"""

from __future__ import annotations

import logging
import os
import re
import threading
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from types import MappingProxyType
from typing import Any, Mapping

from vibecomfy.agent.deepseek_usage import estimate_deepseek_cost_usd
from vibecomfy.executor.profiler import (
    new_profile_id,
    profiler_log,
    profiler_span,
    short_text,
)
from vibecomfy.ingest.normalize import door_get_nodes

from .agent_backend import (
    clear_reply_request_capture,
    run_classify_turn,
    run_reply_turn,
    snapshot_reply_request_capture,
)
from .agent_research_stage import (
    RESEARCH_ATTEMPT_EMPTY,
    RESEARCH_ATTEMPT_GROUNDED,
    RESEARCH_ATTEMPT_NEVER,
    RESEARCH_ATTEMPT_THIN,
    AgentResearchTrace,
    build_research_brief,
    derive_research_attempt,
    form_research_question,
    run_agent_research_stage,
)
from .evidence_pack import EvidenceLedger, EvidenceLedgerEntry, EvidencePack
from .graph_inspection import inspect_graph, render_inspect_markdown
from .stage_contracts import StageDiagnostic, StagePackage
from .tool_contracts import RESEARCH_PHASE_DEADLINE_DEFAULT_SECONDS, ToolStatus
from .prompts import build_classify_messages
from .contracts import (
    ClassifyDecision,
    ExecutorHostPorts,
    ExecutorRequest,
    ExecutorResult,
    ImplementationResult,
    Report,
    VALIDATION_FAILURE_KIND,
    _ALLOWED_ROUTES,
    coerce_model_attempts,
    resolve_orchestration_mode,
    source_policy_entries,
)
from .profiles import (
    AgentSpecShape,
    load_profile,
)
from .request_purpose import deterministic_request_purpose

LOGGER = logging.getLogger(__name__)

_DEFAULT_HOST_PORTS: ExecutorHostPorts | None = None


def _default_host_ports() -> ExecutorHostPorts:
    """Build the production ComfyUI host adapter on first use."""
    global _DEFAULT_HOST_PORTS
    if _DEFAULT_HOST_PORTS is None:
        from vibecomfy.comfy_nodes.agent.executor_adapter import (  # noqa: PLC0415
            build_executor_host_ports,
        )

        _DEFAULT_HOST_PORTS = build_executor_host_ports()
    return _DEFAULT_HOST_PORTS


# Compatibility forwarding names: existing integrations and tests patch these
# module attributes.  New non-ComfyUI hosts should inject ``host_ports=``.
def handle_agent_edit(*args: Any, **kwargs: Any) -> dict[str, Any]:
    return _default_host_ports().handle_agent_edit(*args, **kwargs)


def classify_failure(*args: Any, **kwargs: Any) -> Any:
    return _default_host_ports().classify_failure(*args, **kwargs)


def failure_envelope(*args: Any, **kwargs: Any) -> Any:
    return _default_host_ports().failure_envelope(*args, **kwargs)


def begin_deepseek_usage_capture() -> Any:
    return _default_host_ports().begin_deepseek_usage_capture()


def snapshot_deepseek_usage_capture() -> tuple[dict[str, int], bool]:
    return _default_host_ports().snapshot_deepseek_usage_capture()


def end_deepseek_usage_capture(token: Any) -> None:
    _default_host_ports().end_deepseek_usage_capture(token)


def begin_model_attempt_capture() -> Any:
    return _default_host_ports().begin_model_attempt_capture()


def snapshot_model_attempt_capture() -> tuple[dict[str, Any], ...]:
    return _default_host_ports().snapshot_model_attempt_capture()


def end_model_attempt_capture(token: Any) -> None:
    _default_host_ports().end_model_attempt_capture(token)


def _is_provider_error(exc: BaseException) -> bool:
    return _default_host_ports().is_provider_error(exc)


def _payload_hash(payload: Mapping[str, Any]) -> str:
    return _default_host_ports().payload_hash(payload)

# Interval between ``vibecomfy.executor.phase`` ``status="working"`` heartbeat
# events emitted while the implement phase is running.
_IMPLEMENT_HEARTBEAT_INTERVAL_SECONDS = 15.0
_RESEARCH_HANG_RETRY_SKIP_ENV = "VIBECOMFY_RESEARCH_HANG_RETRY_SKIP"


def _legacy_host_ports() -> ExecutorHostPorts:
    """Adapt the existing ComfyUI-owned globals to the narrow host protocol.

    This remains lazy at call time so existing tests that monkeypatch the core
    compatibility names continue to observe their patches.
    """
    ports = _default_host_ports()
    return replace(
        ports,
        handle_agent_edit=handle_agent_edit,
        payload_hash=_payload_hash,
        classify_failure=classify_failure,
        failure_envelope=failure_envelope,
        begin_deepseek_usage_capture=begin_deepseek_usage_capture,
        snapshot_deepseek_usage_capture=snapshot_deepseek_usage_capture,
        end_deepseek_usage_capture=end_deepseek_usage_capture,
        begin_model_attempt_capture=begin_model_attempt_capture,
        snapshot_model_attempt_capture=snapshot_model_attempt_capture,
        end_model_attempt_capture=end_model_attempt_capture,
    )


def _spec_fields(spec: AgentSpecShape | None) -> dict[str, Any]:
    if spec is None:
        return {}
    return {"route": spec.agent, "model": spec.model, "effort": spec.effort}


def _model_attempts_from_exception(exc: BaseException) -> tuple[dict[str, Any], ...]:
    """Return the first canonical attempt sequence found in an exception chain."""
    seen: set[int] = set()
    current: BaseException | None = exc
    while current is not None and id(current) not in seen:
        seen.add(id(current))
        attempts = coerce_model_attempts(getattr(current, "model_attempts", None))
        if attempts:
            return attempts
        worker_result = getattr(current, "worker_result", None)
        if isinstance(worker_result, Mapping):
            attempts = coerce_model_attempts(worker_result.get("model_attempts"))
            if attempts:
                return attempts
        current = current.__cause__
    return ()


def _enrich_failure_envelope(
    failure: Any,
    exc: BaseException,
) -> Any:
    """Attach only canonical model-attempt evidence to a failure envelope."""
    attempts = _model_attempts_from_exception(exc)
    if not attempts:
        return failure
    context = dict(failure.agent_failure_context or {})
    context["model_attempts"] = list(attempts)
    return replace(failure, agent_failure_context=context)


def _failure_model_attempts(failure: Any) -> tuple[dict[str, Any], ...]:
    """Read canonical attempts previously attached to a failure envelope."""
    context = getattr(failure, "agent_failure_context", None)
    if not isinstance(context, Mapping):
        return ()
    return coerce_model_attempts(context.get("model_attempts"))


# ── route-aware behavior helpers (SD2) ───────────────────────────────────────


@dataclass(frozen=True)
class RouteBehavior:
    route: str
    needs_research: bool
    needs_implement: bool
    plan_summary: str
    clears_result_graph: bool
    reply_uses_graph_inspection: bool
    can_produce_candidate: bool


_ROUTE_BEHAVIORS = MappingProxyType({
    "clarify": RouteBehavior(
        route="clarify",
        needs_research=False,
        needs_implement=False,
        plan_summary="Ask a clarifying question before proceeding.",
        clears_result_graph=False,
        reply_uses_graph_inspection=False,
        can_produce_candidate=False,
    ),
    "respond": RouteBehavior(
        route="respond",
        needs_research=False,
        needs_implement=False,
        plan_summary="Answer directly from existing context without research or editing.",
        clears_result_graph=False,
        reply_uses_graph_inspection=False,
        can_produce_candidate=False,
    ),
    "inspect": RouteBehavior(
        route="inspect",
        needs_research=False,
        needs_implement=False,
        plan_summary="Inspect the graph without editing or outside research.",
        clears_result_graph=True,
        reply_uses_graph_inspection=True,
        can_produce_candidate=False,
    ),
    "research": RouteBehavior(
        route="research",
        needs_research=True,
        needs_implement=False,
        plan_summary="Research workflows, nodes, or techniques, then answer without editing.",
        clears_result_graph=True,
        reply_uses_graph_inspection=False,
        can_produce_candidate=False,
    ),
    "requires_custom_nodes": RouteBehavior(
        route="requires_custom_nodes",
        needs_research=False,
        needs_implement=False,
        plan_summary="Report that the requested edit cannot be safely authored from the current evidence.",
        clears_result_graph=True,
        reply_uses_graph_inspection=False,
        can_produce_candidate=False,
    ),
    "revise": RouteBehavior(
        route="revise",
        needs_research=False,
        needs_implement=True,
        plan_summary="Revise the current graph without research.",
        clears_result_graph=False,
        reply_uses_graph_inspection=False,
        can_produce_candidate=True,
    ),
    "adapt": RouteBehavior(
        route="adapt",
        needs_research=True,
        needs_implement=True,
        plan_summary="Research workflow precedents, then adapt them to the current graph.",
        clears_result_graph=False,
        reply_uses_graph_inspection=False,
        can_produce_candidate=True,
    ),
    "reorganise": RouteBehavior(
        route="reorganise",
        needs_research=False,
        needs_implement=True,
        plan_summary="Reorganise the current canvas layout without changing workflow semantics.",
        clears_result_graph=False,
        reply_uses_graph_inspection=False,
        can_produce_candidate=True,
    ),
})

if set(_ROUTE_BEHAVIORS) != (_ALLOWED_ROUTES - {""}):
    raise ValueError("Route behaviors must cover every non-empty allowed route exactly once.")


def _canonical_route_for_plan(plan: ClassifyDecision) -> str:
    """Return the canonical runtime route for a classifier plan."""
    route = plan.effective_route
    if route in _ROUTE_BEHAVIORS:
        return route
    # Fallback for ambiguous or legacy payloads not captured by effective_route.
    if plan.implement and plan.research:
        return "adapt"
    if plan.implement:
        return "revise"
    if plan.research:
        return "research"
    return "respond"


def _route_behavior(plan: ClassifyDecision) -> RouteBehavior:
    """Resolve the canonical route behavior for *plan*."""
    return _ROUTE_BEHAVIORS[_canonical_route_for_plan(plan)]


def _request_purpose_plan(
    request: ExecutorRequest,
    plan: ClassifyDecision,
) -> ClassifyDecision:
    """Apply request-shape purpose floors after staged classification.

    The classifier may refine ordinary requests, but it cannot override an
    explicit ``answer_only`` capability: with a graph the turn is
    inspection-only; without one it is research-only. Threaded mode uses the
    same :func:`deterministic_request_purpose` helper without adding a
    classifier and therefore treats every no-graph turn as research.
    """
    purpose = deterministic_request_purpose(request)
    if purpose == "adapt":
        return plan
    if purpose == "inspect":
        return replace(
            plan,
            research=False,
            implement=False,
            reply=True,
            route="inspect",
            task="inspect_graph",
            intent="explain_graph",
            plan_summary=(
                "Answer-only interaction: inspect the attached graph and "
                "answer without editing."
            ),
        )
    # Staged mode already has a classifier and preserves its explicit
    # respond/clarify/research choice for ordinary no-graph requests.  Only an
    # explicit answer-only capability needs the no-edit research floor here;
    # threaded mode has no classifier and therefore uses ``research`` directly.
    if request.interaction_mode != "answer_only":
        return plan
    return replace(
        plan,
        research=True,
        implement=False,
        reply=True,
        route="research",
        task="research_nodes",
        intent="research",
        research_goal=plan.research_goal or plan.change_goal or request.query,
        plan_summary=(
            "No graph is attached: research the inquiry and answer without "
            "editing."
        ),
    )


def _should_research(plan: ClassifyDecision) -> bool:
    """Determine if the research phase should run for *plan*."""
    return _route_behavior(plan).needs_research


def _should_implement(plan: ClassifyDecision) -> bool:
    """Determine if the implement phase should run for *plan*."""
    return _route_behavior(plan).needs_implement


# ── stage lens sets (Law 4, batch 12) ────────────────────────────────────────
#
# Every stage consumes the composable renderer
# (``vibecomfy.porting.render``) with exactly the lens set it is allowed to
# see:
#   * classify → census (compact node/class census + reference map)
#   * reply (inspect / respond with a graph) → surface + diff(Δ) + topology
#     (the complete Python view, what changed, full computed topology)
#   * judge → a STRICT SUBSET of the reply's lens set, enforced at the
#     render boundary via ``ceiling=`` (the reply's set is the ceiling).
# The reply lens set is the model's graph window — nothing is truncated.

_REPLY_LENSES: tuple[str, ...] = ("surface", "diff", "topology")
_CLASSIFY_LENSES: tuple[str, ...] = ("census",)


def _render_graph_text(
    graph: dict[str, Any] | None,
    *,
    delta: Any = (),
    lenses: tuple[str, ...] = _REPLY_LENSES,
) -> str | None:
    """Render the model-facing graph text via the composable renderer.

    Batch 12 (Law 4): the reply/inspect stage consumes ``render_text(wf,
    ("surface", "diff", "topology"))`` — the complete Python-surface view,
    the accepted Δ (what changed — canonical batch only), and the COMPLETE
    computed topology (no 5-widget / 6-input / 20-edge caps).  A stage
    requests exactly the lens set it is allowed to see (the implement
    stage, which has no accepted Δ yet, requests surface+topology).  The
    graph is converted through the ingest door inside the renderer;
    ``None`` when no graph is attached.
    """
    if not graph:
        return None
    from vibecomfy.porting.render import render_text

    return render_text(graph, lenses=lenses, delta=delta)


def _render_census_text(graph: dict[str, Any] | None) -> str | None:
    """Render classify's lens: the compact node/class census (+ reference map).

    Batch 12 (Law 4): classify sees ONLY the census — node count, class
    list, and the reference map.  No widgets, no edges, no topology.
    """
    if not graph:
        return None
    from vibecomfy.porting.render import render_text

    return render_text(graph, lenses=_CLASSIFY_LENSES)


def _accepted_delta_ops(
    implementation_result: ImplementationResult | None,
) -> tuple[dict[str, Any], ...]:
    """Return the accepted Δ ops from the implement phase's durable response.

    The canonical Δ is ``accepted_batch`` (batch 10): the accepted edit
    statements that landed, each carrying its typed ``op``.  No other
    representation (``batch_turns[].delta_ops_envelope`` / ``delta_ops``,
    the top-level ``delta_ops_envelope`` / ``delta_ops``) is consulted —
    one source.  Pure structured extraction — prose is never used.
    """
    if implementation_result is None:
        return ()
    durable = implementation_result.durable_response
    if not isinstance(durable, Mapping):
        return ()
    accepted = durable.get("accepted_batch")
    # ImplementationResult freezes JSON arrays to tuples.  Accept both the
    # pre-freeze list and the durable frozen tuple; rejecting the tuple made
    # the canonical accepted delta disappear precisely at the reply boundary.
    if not isinstance(accepted, (list, tuple)):
        return ()
    ops = [
        dict(item["op"]) for item in accepted
        if isinstance(item, Mapping) and isinstance(item.get("op"), Mapping)
    ]
    return tuple(ops)


def _build_session_context(request: ExecutorRequest) -> dict[str, Any] | None:
    """Build session context for reference resolution in the classify phase.

    Loads the last ``PROMPT_MEMORY_MESSAGES`` (5) durable chat messages in
    chronological order from persisted turn artifacts.  The backend-owned
    durable session store is the **only** source of prompt history — frontend
    ``recent_messages`` are never consulted as primary state (SD1: durable ==
    canonical).

    Also loads prior clarification context, latest candidate, and blocked
    route/task from session state so downstream classify logic can resolve
    follow-up references.

    Defensively tolerates malformed historical chat artifacts (non-dict
    messages, missing ``role`` / ``text`` keys, corrupt chat.json) by
    skipping unrecoverable entries rather than raising.

    Returns ``None`` when no session context is available (no session_id,
    store unavailable, etc.).
    """
    if not request.session_id:
        return None

    context: dict[str, Any] = {}
    chat_prior_clarification = False

    # ── Durable chat messages (backend-owned, SD1) ────────────────────────
    try:
        from vibecomfy.comfy_nodes.agent import edit as agent_edit

        prompt_memory = getattr(agent_edit, "PROMPT_MEMORY_MESSAGES", 5)
        chat = agent_edit.read_session_chat(
            getattr(agent_edit, "_SESSION_ROOT"),
            request.session_id,
            max_messages=prompt_memory,
        )
        if isinstance(chat, dict):
            raw_messages = chat.get("messages")
            if isinstance(raw_messages, list):
                # Defensively filter: keep only well-formed dicts with both
                # ``role`` and ``text``.  Malformed entries are silently
                # skipped so a single corrupt turn artifact cannot poison the
                # entire prompt context.
                durable_messages: list[dict[str, Any]] = []
                for msg in raw_messages:
                    if not isinstance(msg, dict):
                        continue
                    role = msg.get("role")
                    text = msg.get("text")
                    if not isinstance(role, str) or not role.strip():
                        continue
                    if not isinstance(text, str):
                        continue
                    # Normalise: store minimal fields consumed by prompt
                    # construction and classifier reference resolution.
                    entry: dict[str, Any] = {"role": role.strip(), "text": text}
                    turn_id = msg.get("turn_id")
                    if isinstance(turn_id, str) and turn_id.strip():
                        entry["turn_id"] = turn_id.strip()
                    outcome = msg.get("outcome")
                    if isinstance(outcome, dict):
                        entry["outcome"] = outcome
                    change_details = msg.get("change_details")
                    if isinstance(change_details, dict):
                        entry["change_details"] = change_details
                    durable_messages.append(entry)

                # read_session_chat already caps at max_messages, but
                # enforce the hard cap here as a defensive second gate.
                if len(durable_messages) > prompt_memory:
                    durable_messages = durable_messages[-prompt_memory:]

                if durable_messages:
                    context["recent_messages"] = durable_messages

            latest_candidate = chat.get("latest_candidate")
            if isinstance(latest_candidate, dict):
                context["latest_candidate"] = latest_candidate

            # Extract prior clarification from the most recent agent message
            # whose outcome kind is ``clarify``.  Scan raw_messages (which may
            # include entries skipped by the durable filter above).
            latest_agent = next(
                (
                    msg for msg in reversed(raw_messages if isinstance(raw_messages, list) else [])
                    if isinstance(msg, dict)
                    and msg.get("role") == "agent"
                    and isinstance(msg.get("outcome"), dict)
                    and msg["outcome"].get("kind") == "clarify"
                ),
                None,
            )
            if latest_agent is not None:
                outcome = latest_agent.get("outcome")
                question = (
                    outcome.get("question")
                    if isinstance(outcome, dict)
                    and isinstance(outcome.get("question"), str)
                    else latest_agent.get("text")
                )
                prior: dict[str, Any] = {}
                if isinstance(question, str) and question.strip():
                    prior["clarification_question"] = question.strip()
                options = (
                    outcome.get("options")
                    if isinstance(outcome, dict)
                    and isinstance(outcome.get("options"), list)
                    else None
                )
                if options:
                    prior["clarification_options"] = [
                        str(opt) for opt in options if str(opt).strip()
                    ]
                if prior:
                    context["prior_clarification"] = prior
                    chat_prior_clarification = True

        from vibecomfy.comfy_nodes.agent.session import (
            read_state,
            session_dir_for,
        )

        state = read_state(session_dir_for(getattr(agent_edit, "_SESSION_ROOT"), request.session_id))
        if isinstance(state, dict):
            # Carry forward prior clarification context if present.  Durable
            # chat is newer/more specific than session_state, so don't let a
            # stale saved clarification overwrite the latest chat turn.
            prior_clarification = state.get("prior_clarification")
            if isinstance(prior_clarification, dict) and not chat_prior_clarification:
                context["prior_clarification"] = prior_clarification

            # Carry forward blocked route/task for continuation. Prefer the
            # intended blocked route over the public clarify route when both
            # are present.
            prior_route = state.get("blocked_route") or state.get("prior_route")
            if isinstance(prior_route, str) and prior_route.strip():
                route_text = prior_route.strip()
                context["prior_route"] = route_text
                if isinstance(state.get("blocked_route"), str) and state["blocked_route"].strip():
                    context["blocked_route"] = route_text
                prior_task = state.get("blocked_task") or state.get("prior_task")
                if isinstance(prior_task, str) and prior_task.strip():
                    task_text = prior_task.strip()
                    context["prior_task"] = task_text
                    if isinstance(state.get("blocked_task"), str) and state["blocked_task"].strip():
                        context["blocked_task"] = task_text
    except Exception:
        LOGGER.debug(
            "session_context: could not load session state for %r",
            request.session_id,
            exc_info=True,
        )

    return context if context else None


def _save_clarification_context(
    request: ExecutorRequest,
    plan: ClassifyDecision,
    *,
    blocked_route: str | None = None,
    blocked_task: str | None = None,
) -> None:
    """Persist clarification artifacts to the session for follow-up resolution.

    Best-effort: failures are logged and never propagate.
    """
    if not request.session_id:
        return

    clarification_context: dict[str, Any] = {
        "prior_clarification": {
            "clarification_question": plan.clarification_question or plan.plan_summary,
            "clarification_options": list(plan.clarification_options),
        },
        "prior_route": plan.effective_route,
        "prior_task": plan.effective_task,
    }
    if isinstance(blocked_route, str) and blocked_route.strip():
        clarification_context["blocked_route"] = blocked_route.strip()
    if isinstance(blocked_task, str) and blocked_task.strip():
        clarification_context["blocked_task"] = blocked_task.strip()

    try:
        from vibecomfy.comfy_nodes.agent.session import (
            read_state,
            session_dir_for,
            write_state_atomic,
        )

        from vibecomfy.comfy_nodes.agent import edit as agent_edit

        sdir = session_dir_for(getattr(agent_edit, "_SESSION_ROOT"), request.session_id)
        if sdir is not None:
            # Merge with existing state to preserve messages.
            existing: dict[str, Any] = read_state(sdir)
            try:
                if not isinstance(existing, dict):
                    existing = {}
            except Exception:
                existing = {}

            if isinstance(existing, dict):
                existing.update(clarification_context)
            else:
                existing = clarification_context

            write_state_atomic(sdir, existing)
            LOGGER.debug(
                "session_context: saved clarification context for %r",
                request.session_id,
            )
    except Exception:
        LOGGER.debug(
            "session_context: could not save clarification context for %r",
            request.session_id,
            exc_info=True,
        )


def _context_text_mentions_ltx_audio(session_context: dict[str, Any]) -> bool:
    texts: list[str] = []
    prior = session_context.get("prior_clarification")
    if isinstance(prior, dict):
        for key in ("clarification_question", "prior_request"):
            value = prior.get(key)
            if isinstance(value, str):
                texts.append(value)
        options = prior.get("clarification_options")
        if isinstance(options, list):
            texts.extend(str(option) for option in options)
    recent = session_context.get("recent_messages")
    if isinstance(recent, list):
        for msg in recent[-5:]:
            if isinstance(msg, dict) and isinstance(msg.get("text"), str):
                texts.append(msg["text"])
    combined = " ".join(texts).lower()
    return (
        "ltx" in combined
        and any(term in combined for term in ("audio", "voice", "lipsync", "lip sync", "runexx"))
    )


def _clarify_markdown_reply(plan: ClassifyDecision, fallback: str) -> str:
    """Return a concrete Markdown clarification question with options."""
    question = (
        plan.clarification_question
        if isinstance(plan.clarification_question, str)
        else ""
    ).strip()
    fallback_text = fallback.strip() if isinstance(fallback, str) else ""
    if not question:
        question = fallback_text or "What detail should I use before continuing?"
    if "Options:" in question:
        return question
    if not any(mark in question for mark in ("?", "Would you like to", "Could you")):
        question = f"Could you clarify: {question.rstrip(':')}"
    options = [str(opt).strip() for opt in plan.clarification_options if str(opt).strip()]
    if not options:
        options = [
            "Provide the missing detail explicitly.",
            "Ask me to inspect the current graph before editing.",
        ]
    return question.rstrip() + "\n\nOptions:\n" + "\n".join(
        f"- {option}" for option in options
    )


# ── profile resolution ───────────────────────────────────────────────────────


def _resolve_spec(
    profile_name: str | None,
    stage: str,
) -> AgentSpecShape:
    """Resolve an :class:`AgentSpecShape` for *stage* from *profile_name*.

    When *profile_name* is ``None`` the default profile (``"default"``) is
    used.  Failures produce a :class:`FailureEnvelope`-compatible exception
    that the caller converts via :func:`classify_failure`.
    """
    name = profile_name or "default"
    try:
        profile = load_profile(name)
    except FileNotFoundError:
        raise FileNotFoundError(
            f"Executor profile '{name}' not found."
        ) from None
    except Exception as exc:
        raise ValueError(
            f"Failed to load executor profile '{name}': {exc}"
        ) from exc

    spec = profile.get(stage)
    if spec is None:
        raise ValueError(
            f"Profile '{name}' is missing the '{stage}' stage."
        )
    return spec


# ── classify phase ───────────────────────────────────────────────────────────


def _classify_stage_message(message: str) -> str:
    """Classify-stage failures are not workflow-validation errors (RC7)."""
    if "edited workflow has validation errors" in (message or ""):
        return (
            "Classification failed: the classifier reply was missing required "
            "fields or was not valid JSON. The graph is unchanged."
        )
    return message


_CLASSIFY_JSON_NUDGE = (
    "Your previous reply was missing required fields or was not valid JSON. "
    "Return the exact JSON object required by the classify schema and nothing else."
)


_CLASSIFY_EDIT_ROUTING_NUDGE = (
    "This interaction expects a graph change (expect_graph_changed=true). "
    "Classify route MUST be an edit route (\"revise\", \"adapt\", "
    "or \"reorganise\"). Non-applyable routes such as \"inspect\" and "
    "\"respond\" will be rejected; choose the concrete edit route the request supports."
)


def _satisfies_expected_graph_change(plan: ClassifyDecision) -> bool:
    """True only for routes that can actually return an edited graph."""
    return plan.effective_route in {"revise", "adapt", "reorganise"}


def _classify_parse_is_retryable(exc: BaseException) -> bool:
    """True for classify malformed_json / missing_required_fields only."""
    if type(exc).__name__ in {
        "JSONDecodeError",
        "MalformedModelJSON",
        "MissingRequiredField",
    }:
        return True
    if not isinstance(exc, ValueError):
        return False
    if isinstance(getattr(exc, "worker_result", None), Mapping):
        return True
    from vibecomfy.executor.agent_backend import _downstream_failure_type

    raw = getattr(exc, "raw_response_preview", None)
    if not isinstance(raw, str):
        return False
    return _downstream_failure_type(raw) in {
        "empty_response",
        "malformed_json",
        "missing_required_fields",
        "non_json_content",
    }


def _reroute_expected_edit(
    request: ExecutorRequest,
    kwargs: dict[str, Any],
) -> ClassifyDecision:
    """Re-ask a classify turn that chose a non-applyable expected-edit route.

    RC14: when ``expect_graph_changed`` is true, ``respond`` and ``inspect``
    are both no-ops for the apply gate. Re-ask once with an edit-routing nudge;
    if the model still chooses a non-applyable route, fail loudly.
    """
    base_messages = kwargs.get("messages")
    if not isinstance(base_messages, list):
        base_messages = build_classify_messages(
            request.query,
            has_graph=request.graph is not None,
            graph_summary=_render_census_text(request.graph),
            expect_graph_changed=True,
        )
    reroute_kwargs = dict(kwargs)
    reroute_kwargs["messages"] = [
        *base_messages,
        {"role": "user", "content": _CLASSIFY_EDIT_ROUTING_NUDGE},
    ]
    plan = run_classify_turn(request.query, **reroute_kwargs)
    if not _satisfies_expected_graph_change(plan):
        raise _ExecutorPhaseError(
            stage="classify",
            failure_kind="MissingRequiredField",
            message=(
                "Classification failed: the scenario expects a graph change "
                "(expect_graph_changed=true), but classify still routed to "
                f"{plan.effective_route}. The classify route must be an "
                "applyable edit route (revise, adapt, or reorganise), so the "
                "request was rejected instead of proceeding as a no-op."
            ),
        )
    return plan


def _run_classify(
    request: ExecutorRequest,
    spec: AgentSpecShape,
    *,
    session_context: dict[str, Any] | None = None,
    expect_graph_changed: bool | None = None,
    host_ports: ExecutorHostPorts | None = None,
) -> ClassifyDecision:
    """Run the classify model turn.

    Always calls the model (SD1).  Converts provider exceptions through
    ``classify_failure`` so raw exceptions never leak.

    *expect_graph_changed* declares the interaction's edit contract (RC14).
    When True, a non-applyable plan is never returned: the first attempt is
    re-asked once, and a malformed-JSON / missing-fields retry is re-asked
    once, then rejected if the model still does not choose an edit route.
    """
    try:
        # Build enriched messages when session context carries actual data
        # for reference resolution (M3).  Otherwise, let run_classify_turn
        # build them from the default parameters.
        # Batch 12 (Law 4): classify sees ONLY the census lens — the compact
        # node/class census + reference map (derived from the IR via the
        # renderer).  No widgets, no edges, no raw-JSON sidecar.
        graph_summary = _render_census_text(request.graph)
        classify_kwargs: dict[str, Any] = {
            "route": spec.agent,
            "model": spec.model,
            "effort": spec.effort,
            "has_graph": request.graph is not None,
            "graph_summary": graph_summary,
            "expect_graph_changed": expect_graph_changed,
            # The IR-aware core owns its one bounded, route-aware repair turn.
            # Direct agent_backend callers retain that backend's own repair.
            "max_parse_attempts": 1,
        }
        # Pre-build messages whenever we have session context beyond the
        # bare query.  The census lens already carries the node reference
        # map, so no separate raw-JSON walk is needed for reference
        # resolution on first-turn or follow-up graph edits.
        if isinstance(session_context, dict) and (
            session_context.get("recent_messages")
            or session_context.get("prior_clarification")
            or session_context.get("latest_candidate")
            or session_context.get("prior_route")
        ):
            classify_kwargs["messages"] = build_classify_messages(
                request.query,
                has_graph=request.graph is not None,
                graph_summary=graph_summary,
                session_context=session_context,
                expect_graph_changed=expect_graph_changed,
            )

        try:
            plan = run_classify_turn(request.query, **classify_kwargs)
        except Exception as first_exc:
            if isinstance(first_exc, _ExecutorPhaseError) or not _classify_parse_is_retryable(
                first_exc
            ):
                raise
        else:
            if expect_graph_changed is True and not _satisfies_expected_graph_change(plan):
                # Hard rule: an expected-edit interaction never proceeds via a
                # non-applyable route (RC14). Re-ask once, then fail loudly.
                plan = _reroute_expected_edit(request, classify_kwargs)
            return plan
        retry_kwargs = dict(classify_kwargs)
        base_messages = retry_kwargs.get("messages")
        if not isinstance(base_messages, list):
            base_messages = build_classify_messages(
                request.query,
                has_graph=request.graph is not None,
                graph_summary=graph_summary,
                session_context=session_context if isinstance(session_context, dict) else None,
                expect_graph_changed=expect_graph_changed,
            )
        retry_content = _CLASSIFY_JSON_NUDGE
        if expect_graph_changed is True:
            retry_content = f"{retry_content}\n\n{_CLASSIFY_EDIT_ROUTING_NUDGE}"
        retry_kwargs["messages"] = [
            *base_messages,
            {"role": "user", "content": retry_content},
        ]
        plan = run_classify_turn(request.query, **retry_kwargs)
        if expect_graph_changed is True and not _satisfies_expected_graph_change(plan):
            # The retry corrected the JSON but chose a non-applyable route —
            # re-ask once, then reject instead of returning a no-op (RC14).
            plan = _reroute_expected_edit(request, retry_kwargs)
        return plan
    except _ExecutorPhaseError:
        raise
    except Exception as exc:
        provider_failure = (
            host_ports.is_provider_error(exc)
            if host_ports is not None
            else _is_provider_error(exc)
        )
        classify = (
            host_ports.classify_failure
            if host_ports is not None
            else classify_failure
        )
        failure = classify(
            "agent_response"
            if provider_failure or _classify_parse_is_retryable(exc)
            else "classify",
            exc,
        )
        failure = _enrich_failure_envelope(failure, exc)
        raise _ExecutorPhaseError(
            stage="classify",
            failure_kind=failure.kind.value,
            message=_classify_stage_message(failure.user_facing_message),
            failure_envelope=failure,
            model_attempts=_failure_model_attempts(failure),
        ) from exc


# ── research phase ───────────────────────────────────────────────────────────


def run_research_phase(*args: Any, **kwargs: Any) -> Any:
    """Legacy automatic research engine — REMOVED by the agent-judgment rework.

    Kept only so tests can prove the active path never calls it
    (``mock.assert_not_called()``). Any live call raises: research is
    agent-owned (C01); the prefetch is gone.
    """
    raise RuntimeError(
        "legacy automatic research engine removed (C01); research is agent-owned — "
        "use run_agent_research_stage via _run_agent_owned_research"
    )


def _run_research(*args: Any, **kwargs: Any) -> Any:
    """Legacy executor research phase — removed (C01); see ``run_research_phase``."""
    return run_research_phase(*args, **kwargs)


def _default_hivemind_client(*args: Any, **kwargs: Any) -> Any:
    """Legacy default Hivemind client — removed (C01); research is agent-owned."""
    raise RuntimeError(
        "legacy _default_hivemind_client removed (C01); hivemind access is via "
        "the agent-invoked hivemind_search/hivemind_get tools"
    )


# ── research phase ───────────────────────────────────────────────────────────

# ── implement phase ──────────────────────────────────────────────────────────


@dataclass(frozen=True)
class AgentResearchResult:
    """Active C1 output; edit agents receive only its compact ledger."""

    route: str
    trace: AgentResearchTrace
    evidence_pack: EvidencePack
    package: StagePackage | None = None
    policy_diagnostics: tuple[dict[str, Any], ...] = ()
    decision_memo: Mapping[str, Any] | None = None

    @property
    def ledger(self) -> EvidenceLedger:
        return self.evidence_pack.ledger

    @property
    def summary(self) -> str:
        return self.trace.summary

    @property
    def research_attempt(self) -> str:
        """Typed attempt (never/empty/thin/grounded) derived from the ledger.

        Batch 14: the attempt is derived in Python from the research tool
        ledger + artifacts — never from model judgment — so it is correct
        even for manually-constructed results whose trace lacks an ``attempt``
        field.
        """
        return derive_research_attempt(
            ledger=self.ledger,
            artifacts=self.evidence_pack.artifacts,
        )

    @property
    def warnings(self) -> tuple[str, ...]:
        return tuple(self.trace.warnings) + tuple(
            str(item.get("message") or "")
            for item in self.policy_diagnostics
            if item.get("message")
        )

    def to_dict(self) -> dict[str, Any]:
        # T4.1: every key in contracts.RESEARCH_EVIDENCE_SHARED_KEYS is
        # projected here exactly as the threaded ``_durable_research_evidence``
        # projects it, so the two carriers expose field-for-field parity.
        trace = self.trace
        status_counts: dict[str, int] = {}
        for entry in self.ledger.entries:
            if entry.tool_status is None:
                continue
            status_counts[entry.tool_status] = (
                status_counts.get(entry.tool_status, 0) + 1
            )
        budget = getattr(trace, "budget", None)
        payload: dict[str, Any] = {
            "mode": "agent_owned",
            "route": self.route,
            "status": trace.status,
            "verdict": trace.final_verdict,
            "research_attempt": self.research_attempt,
            "decision_turns": len(trace.iterations),
            "tool_calls_executed": trace.executed_tool_calls,
            "tool_call_statuses": dict(sorted(status_counts.items())),
            "evidence_artifacts": trace.evidence_artifact_count,
            "diagnostics": [dict(item) for item in self.policy_diagnostics],
        }
        if budget is not None:
            payload["budget"] = dict(budget)
        # Bounded citation ids (the memo refines these to its inspected ≤6
        # subset; counts may differ between modes, field presence may not).
        payload["citations"] = list(trace.citations)[:12]
        if self.decision_memo is not None:
            # Research-only exposes the bounded C5 memo, never source bodies,
            # iterations, or the full C1 artifact pack.
            payload.update(dict(self.decision_memo))
        # The compact handoff ledger is exposed on BOTH routes: research-only
        # keeps its bounded C5 memo AND now carries the same compact ledger
        # field the threaded carrier exposes (entries are tiny judgments; no
        # source bodies, iterations, or artifact packs).
        payload["ledger"] = self.ledger.to_dict()
        return payload

def _source_policy_entries(
    plan: ClassifyDecision,
) -> tuple[tuple[EvidenceLedgerEntry, ...], tuple[dict[str, Any], ...]]:
    """Make unsupported classifier source requests visible, never rewrite them.

    T4.1: the policy itself is the shared contract in
    :func:`vibecomfy.executor.contracts.source_policy_entries`; staged keeps
    this thin plan-shaped wrapper.
    """
    return source_policy_entries(plan.source_preferences)


def _research_decision_memo(
    trace: AgentResearchTrace,
    *,
    diagnostics: tuple[dict[str, Any], ...],
    attempt: str = RESEARCH_ATTEMPT_NEVER,
    artifacts: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    inspected = [
        evidence_id
        for evidence_id in trace.citations
        if str(evidence_id).startswith("hivemind_get:")
    ] or list(trace.citations)
    uncertainty_parts = [trace.uncertainty.strip()] if trace.uncertainty.strip() else []
    uncertainty_parts.extend(
        str(item.get("message") or "").strip()
        for item in diagnostics
        if str(item.get("message") or "").strip()
    )
    # Batch 14: the memo NEVER refuses because research was thin.  The memo is
    # attempt-typed: on never/empty the conclusion states the attempt's own
    # fact (no evidence tools were called / no evidence was gathered) — never
    # a fake synthesis pulled from a blank trace.summary — so the reply model
    # answers from the attached graph and its own knowledge.  "No supported
    # conclusion was produced" is gone.
    if attempt == RESEARCH_ATTEMPT_NEVER:
        conclusion = (
            "No evidence tools were called; no external evidence was gathered. "
            "Answer from the attached workflow graph and general knowledge."
        )
    elif attempt == RESEARCH_ATTEMPT_EMPTY:
        conclusion = (
            "Evidence tools were called but returned no evidence; no external "
            "evidence was gathered. Answer from the attached workflow graph "
            "and general knowledge."
        )
    else:
        conclusion = trace.summary or (
            "No external evidence was gathered by the research stage; "
            "answer from the attached workflow graph and general knowledge."
        )
    warning_lines = list(trace.warnings)
    evidence_preview = _research_evidence_preview(
        trace, artifacts=artifacts
    )
    memo = {
        "question": trace.question,
        "conclusion": conclusion,
        "citations": inspected[:6],
        "uncertainty": " ".join(uncertainty_parts),
        "research_attempt": attempt,
        "next_action": (
            "Use this conclusion for the requested next step."
            if trace.final_verdict == "enough" and attempt in {
                RESEARCH_ATTEMPT_THIN,
                RESEARCH_ATTEMPT_GROUNDED,
            }
            else (
                "Answer from the attached graph and general knowledge; "
                "no external evidence was gathered."
                if attempt in {RESEARCH_ATTEMPT_NEVER, RESEARCH_ATTEMPT_EMPTY}
                else "Refine the unresolved research question before acting on this conclusion."
            )
        ),
        "research_status": trace.status,
        "research_warnings": warning_lines,
        "tool_calls_executed": trace.executed_tool_calls,
        "evidence_artifacts": trace.evidence_artifact_count,
        "evidence_preview": evidence_preview,
    }
    # R4d: a FAILED stage (e.g. an unparseable model decision) must expose the
    # actual error so the reply stage reports the real cause — never a
    # fabricated "ran out of time" (observed: malformed decision ValueError,
    # memo without trace.error, reply inventing a timeout story).  Key is
    # failure-only so successful-memo dict equality assertions stay stable.
    if trace.status == "failed" and trace.error:
        memo["research_error"] = trace.error[:400]
    return memo


def _research_evidence_preview(
    trace: Any, *, max_chars: int = 900, artifacts: Mapping[str, Any] | None = None
) -> str:
    """Bounded preview of what the research tools actually returned.

    Includes BOTH layers of gathered evidence: (1) the compact search-hit
    conclusions from the trace, and (2) the FETCHED RECORD BODIES from the
    evidence pack when available — the same content the research agent read.
    A time-cutoff must not drop the fetched records: they are the substance
    of the research, and the reply should be able to name what was actually
    read before the deadline hit (user decision: include everything
    researched).  ``payload`` (workflow JSON) never enters the preview.

    Only produced when the stage failed to synthesize (exhausted/failed) but
    DID execute tools and record tool evidence with no citations — a
    successful no-citation synthesis is a legitimate outcome, not a timed-out
    search (Codex review P1-6).
    """
    if trace.status not in {"exhausted", "failed"}:
        return ""
    if not trace.executed_tool_calls:
        return ""
    if trace.evidence_artifact_count <= 0:
        return ""
    if trace.citations:
        return ""
    lines: list[str] = []

    # Layer 2 first (most substantive): fetched record bodies, deduped.
    seen: set[str] = set()
    for iteration in getattr(trace, "iterations", ()) or ():
        for call in getattr(iteration, "tool_calls", ()) or ():
            if not isinstance(call, dict):
                continue
            if str(call.get("tool") or "") != "hivemind_get":
                continue
            if str(call.get("status") or "") != "ok":
                continue
            for evidence_id in (call.get("evidence_ids") or ()):
                if evidence_id in seen or not artifacts:
                    continue
                seen.add(evidence_id)
                artifact = artifacts.get(evidence_id)
                if artifact is None:
                    continue
                body = artifact.body if isinstance(artifact.body, Mapping) else {"value": artifact.body}
                title = str(body.get("title") or body.get("name") or evidence_id)
                content = str(
                    body.get("body")
                    or body.get("description")
                    or body.get("content")
                    or ""
                )
                # Never payload (workflow JSON); bounded per record.
                if content:
                    lines.append(f"[fetched {evidence_id}] {title}: {content[:220]}")

    # Layer 1: search-hit conclusions (titles of what was surfaced).
    for iteration in getattr(trace, "iterations", ()) or ():
        for call in getattr(iteration, "tool_calls", ()) or ():
            if not isinstance(call, dict):
                continue
            tool = str(call.get("tool") or "")
            status = str(call.get("status") or "")
            if status != "ok" or tool != "hivemind_search":
                continue
            conclusion = str(call.get("conclusion") or "").strip()
            if not conclusion or conclusion.startswith("0 "):
                continue
            query = str(call.get("query") or "").strip()
            prefix = f"[{tool} {query}] " if query else f"[{tool}] "
            lines.append(prefix + conclusion[:220])
    preview = "\n".join(lines)
    if len(preview) > max_chars:
        preview = preview[: max(0, max_chars - 3)].rstrip() + "..."
    return preview


def _research_stage_package(
    *,
    route: str,
    trace: AgentResearchTrace,
    pack: EvidencePack,
    policy_diagnostics: tuple[dict[str, Any], ...],
    research_attempt: str = RESEARCH_ATTEMPT_NEVER,
    budget: Mapping[str, Any] | None = None,
) -> StagePackage:
    """Build the F01 research :class:`StagePackage` handed to implement.

    The typed envelope carries the evidence artifacts, the compact ledger,
    and typed diagnostics (policy warnings, trace failures) — the only
    research content the implement phase may consume.  ``StageRequest`` is
    not part of this seam: the classify decision (goal/route) is authoritative
    and the package references are explicit on the wire.  ``research_attempt``
    is the batch-14 typed attempt derived from the research tool ledger.
    """
    diagnostics: list[StageDiagnostic] = [
        StageDiagnostic(
            code=str(item.get("code") or "research_policy_warning"),
            message=str(item.get("message") or ""),
            severity="warning",
        )
        for item in policy_diagnostics
        if item.get("message")
    ]
    if trace.status == "failed":
        diagnostics.append(
            StageDiagnostic(
                code="research_stage_failed",
                message=str(trace.error or "research stage failed"),
                severity="error",
            )
        )
    elif trace.status == "exhausted":
        diagnostics.append(
            StageDiagnostic(
                code="research_stage_exhausted",
                message=(
                    "research stage stopped without an agent finish "
                    "(deadline or max-turn exhaustion); no usable synthesis"
                ),
                severity="error",
            )
        )
    has_result_artifacts = any(
        str(evidence_id) != "research_question" for evidence_id in pack.artifacts
    )
    # RC1: a single 57014 must not fail the whole package when any search
    # hit or fetched artifact already exists.  Exhausted/failed with only
    # the question marker stays UNAVAILABLE.
    status = (
        ToolStatus.OK
        if trace.status == "ok" or has_result_artifacts
        else ToolStatus.UNAVAILABLE
    )
    return StagePackage(
        stage_id="research",
        produced_at=datetime.now(timezone.utc)
        .isoformat(timespec="seconds")
        .replace("+00:00", "Z"),
        artifacts=pack.artifacts,
        diagnostics=tuple(diagnostics),
        status=status,
        next_stage_hints=("implement",) if route == "adapt" else (),
        ledger=pack.ledger,
        research_attempt=research_attempt,
        budget=dict(budget) if budget is not None else None,
    )


def _run_agent_owned_research(
    request: ExecutorRequest,
    spec: AgentSpecShape,
    *,
    plan: ClassifyDecision,
) -> AgentResearchResult:
    route = _canonical_route_for_plan(plan)
    question, _source_field = form_research_question(request=request, plan=plan)
    brief = build_research_brief(plan=plan, request=request)
    # Research-only routes get the same wall-clock budget the batch-REPL
    # research path uses (VIBECOMFY_RESEARCH_PHASE_DEADLINE, default 450s):
    # a research-only turn has no implement phase, and flash-class decision
    # turns take 30-150s each — the old 240s starved the agent mid-evidence
    # (observed: 3 iterations, 30 evidence artifacts, then the deadline
    # dropped the deciding call that would have finished the synthesis).
    # ADAPT routes share the same 450s research budget: research + implement
    # then each get ~half of the panel's 15-min absolute submit deadline
    # (900s), with implement consuming the remainder after research returns.
    # The stage coerces float(deadline_seconds) unconditionally, so we only
    # pass a value for research routes (never None); 0/negative env falls
    # back to the shared stage default (T4.2 unification: ONE canonical
    # RESEARCH_PHASE_DEADLINE_DEFAULT_SECONDS for both carriers) rather than
    # an immediate deadline.
    deadline_seconds: float | None = None
    if route in ("research", "adapt"):
        try:
            configured = float(
                os.environ.get(
                    "VIBECOMFY_RESEARCH_PHASE_DEADLINE",
                    str(int(RESEARCH_PHASE_DEADLINE_DEFAULT_SECONDS)),
                )
                or 0
            )
        except ValueError:
            configured = RESEARCH_PHASE_DEADLINE_DEFAULT_SECONDS
        if configured > 0:
            deadline_seconds = configured
    research_kwargs: dict[str, float] = {}
    if deadline_seconds is not None:
        research_kwargs["deadline_seconds"] = deadline_seconds
    try:
        trace, pack = run_agent_research_stage(
            route=route,
            question=question,
            research_brief=brief,
            spec=spec,
            **research_kwargs,
        )
    except TypeError as exc:
        # Keep injected/legacy stage doubles source-compatible while the
        # production stage receives its explicit deadline telemetry.
        if "deadline_seconds" not in str(exc):
            raise
        trace, pack = run_agent_research_stage(
            route=route,
            question=question,
            research_brief=brief,
            spec=spec,
        )
    policy_entries, diagnostics = _source_policy_entries(plan)
    if policy_entries:
        pack = EvidencePack(
            artifacts=pack.artifacts,
            ledger=EvidenceLedger(entries=pack.ledger.entries + policy_entries),
        )
    attempt = derive_research_attempt(ledger=pack.ledger, artifacts=pack.artifacts)
    memo = (
        _research_decision_memo(
            trace,
            diagnostics=diagnostics,
            attempt=attempt,
            artifacts=pack.artifacts,
        )
        if route == "research"
        else None
    )
    return AgentResearchResult(
        route=route,
        trace=trace,
        evidence_pack=pack,
        package=_research_stage_package(
            route=route,
            trace=trace,
            pack=pack,
            policy_diagnostics=diagnostics,
            research_attempt=attempt,
            budget=getattr(trace, "budget", None),
        ),
        policy_diagnostics=diagnostics,
        decision_memo=memo,
    )


def _research_package_is_usable(
    research_result: AgentResearchResult | None,
    *,
    route: str | None = None,
    has_graph: bool = False,
) -> bool:
    """Attempt-typed gate for the research→implement handoff (RC2).

    Implement proceeds when any of:

    * attempt is ``thin`` or ``grounded`` and status is ``OK`` or
      ``UNAVAILABLE`` (thin+UNAVAILABLE still has graph-local evidence)
    * route is ``adapt``, a graph is attached, and the attempt is
      ``never`` / ``empty`` or the package is ``UNAVAILABLE`` /
      exhausted-from-timeout — the attached IR is the evidence

    Architectural invention is refused later by the implement prompt and
    the RC6 apply-gate; this gate no longer skips a one-line graph-local
    edit just because Hivemind timed out.
    """
    if research_result is None:
        return False
    package = getattr(research_result, "package", None)
    if not isinstance(package, StagePackage):
        return False
    attempt = research_result.research_attempt
    status = package.status
    if attempt in {RESEARCH_ATTEMPT_THIN, RESEARCH_ATTEMPT_GROUNDED}:
        return status in {ToolStatus.OK, ToolStatus.UNAVAILABLE}
    adapt_with_graph = route == "adapt" and has_graph
    if adapt_with_graph and attempt in {
        RESEARCH_ATTEMPT_NEVER,
        RESEARCH_ATTEMPT_EMPTY,
    }:
        return True
    if adapt_with_graph and status is ToolStatus.UNAVAILABLE:
        return True
    return False


def _run_implement(
    request: ExecutorRequest,
    spec: AgentSpecShape,
    *,
    plan: ClassifyDecision,
    research_result: AgentResearchResult | None = None,
    client_id: str | None = None,
    additive: bool = False,
    host_ports: ExecutorHostPorts | None = None,
) -> ImplementationResult:
    """Run the implement phase via ``handle_agent_edit``.

    Forwards the request as ``{task, query, graph, route, model, workflow_id,
    session_id, idempotency_key}`` (SD2).
    The resolved *spec* supplies ``route`` and ``model`` so the edit engine
    uses the profile-configured provider path.
    When C1 research has run, only its compact evidence ledger is forwarded.
    Converts the result to an :class:`ImplementationResult`; failures from
    the edit engine are surfaced as :class:`_ExecutorPhaseError`.
    """
    executor_route = _canonical_route_for_plan(plan)
    # RC2: adapt still implements when research is never/empty/UNAVAILABLE
    # as long as a graph is attached — the IR is the evidence.  Architectural
    # invention is refused by the implement prompt and the RC6 apply-gate.
    if (
        executor_route == "adapt"
        and research_result is not None
        and not _research_package_is_usable(
            research_result,
            route=executor_route,
            has_graph=request.graph is not None,
        )
    ):
        return ImplementationResult(
            message=(
                "No graph edit was made: research produced no "
                "evidence-backed direction to implement "
                f"(research_attempt={research_result.research_attempt})."
            ),
        )
    if request.graph is None and executor_route != "research":
        return ImplementationResult(
            message="No graph attached; implementation skipped.",
        )
    classification = plan.to_dict()
    classification["route"] = executor_route
    effective_task = plan.effective_task
    if effective_task:
        classification["task"] = effective_task

    payload: dict[str, Any] = {
        "task": request.query,
        "query": request.query,
        "graph": request.graph if request.graph is not None else {"nodes": [], "links": []},
        "route": executor_route,
        "executor_route": executor_route,
        "provider_route": spec.agent,
        "model": spec.model,
        "effort": spec.effort,
        "executor_classification": classification,
        "additive": bool(additive),
        "max_batches": request.max_batches,
    }
    if request.pipeline_mode is not None:
        # Boundary-only orchestration marker. The agent-edit host remains the
        # sole session, graph writer, checkpoint, replay, and emit authority;
        # it uses this only to select the admitted tool phase.
        payload["pipeline_mode"] = request.pipeline_mode
    # Batch 11/12 (Law 4): the implement stage's model-facing graph text is
    # the composable renderer's surface+topology view (COMPLETE — no
    # 5-widget/6-input/20-edge caps).  The implement stage has no accepted Δ
    # yet (the batch is its output), so it requests exactly that lens set;
    # the truncated text summary is no longer the authority.
    graph_inspection = _render_graph_text(
        request.graph,
        lenses=("surface", "topology"),
    )
    if isinstance(graph_inspection, str) and graph_inspection.strip():
        payload["graph_inspection"] = graph_inspection
    research_package = getattr(research_result, "package", None)
    research_ledger = getattr(research_result, "ledger", None)
    if executor_route == "adapt":
        # C01: the implement phase receives ONLY the research package's
        # compact ledger (decisions + evidence IDs); artifact bodies stay
        # server-side.  The typed StagePackage is the seam handoff; the
        # ledger fallback covers manually-constructed results without a
        # package (the live path always builds one).
        if isinstance(research_package, StagePackage):
            payload["research_ledger"] = research_package.ledger.to_dict()
        elif isinstance(research_ledger, EvidenceLedger):
            payload["research_ledger"] = research_ledger.to_dict()
    research_brief = _research_brief_from_plan(
        plan,
        query=request.query,
        suppress_avoid=False,
    )
    if research_brief:
        payload["research_brief"] = research_brief
    if request.session_id:
        payload["session_id"] = request.session_id
    if request.workflow_id:
        payload["workflow_id"] = request.workflow_id
    if request.idempotency_key:
        payload["idempotency_key"] = request.idempotency_key
    if request.client_graph_hash:
        payload["client_graph_hash"] = request.client_graph_hash
    if request.client_structural_graph_hash:
        payload["client_structural_graph_hash"] = request.client_structural_graph_hash
    if request.client_live_canvas_token:
        payload["client_live_canvas_token"] = request.client_live_canvas_token
    if request.expected_baseline_graph_hash_present:
        payload["expected_baseline_graph_hash"] = request.expected_baseline_graph_hash
    if request.on_demand_schemas is not None:
        payload["on_demand_schemas"] = request.on_demand_schemas
    if request.pipeline_mode is not None:
        # Persist the canonical driver choice with the durable edit request so
        # browser/headless recovery continues the same conversation mode.
        payload["pipeline_mode"] = request.pipeline_mode

    ports = host_ports or _legacy_host_ports()
    try:
        result = ports.handle_agent_edit(
            payload,
            client_id=client_id,
            # Classifier/research output is server-derived and may vary across
            # retries. Bind deduplication to the stable public submit instead.
            idempotency_request_hash=ports.payload_hash(request.to_dict()),
        )
    except Exception as exc:
        failure = ports.classify_failure("implement", exc)
        raise _ExecutorPhaseError(
            stage="implement",
            failure_kind=failure.kind.value,
            message=failure.user_facing_message,
            failure_envelope=failure,
        ) from exc

    if not isinstance(result, dict):
        failure = ports.failure_envelope(
            VALIDATION_FAILURE_KIND,
            "implement",
            agent_failure_context={
                "explanation": "handle_agent_edit returned a non-dict result."
            },
        )
        raise _ExecutorPhaseError(
            stage="implement",
            failure_kind=failure.kind.value,
            message=failure.user_facing_message,
            failure_envelope=failure,
        )

    # Check if result is a failure envelope.
    if result.get("ok") is False or "failure_kind" in result:
        fk = result.get("failure_kind", result.get("kind", "ValidationError"))
        fm = result.get("message", result.get("user_facing_message", "Implementation failed."))
        failure_context = result.get("agent_failure_context")
        failure_payload: dict[str, Any] = {
            "failure_kind": fk,
            "stage": result.get("stage", "implement"),
            "message": fm,
        }
        if isinstance(failure_context, Mapping):
            for key in ("issues", "diagnostics", "validation_errors"):
                value = failure_context.get(key)
                if value is not None:
                    failure_payload[key] = value
            failure_payload["agent_failure_context"] = failure_context
        for key in ("diagnostics", "validation_errors"):
            value = result.get(key)
            if value is not None:
                failure_payload[key] = value
        make_failure = ports.failure_envelope
        failure_context_payload = {
            "explanation": fm,
            **{
                key: value
                for key, value in failure_payload.items()
                if key not in {"message", "stage", "failure_kind"}
            },
        }
        try:
            failure = make_failure(
                fk if isinstance(fk, str) else VALIDATION_FAILURE_KIND,
                "implement",
                agent_failure_context=failure_context_payload,
            )
        except ValueError:
            failure = make_failure(
                VALIDATION_FAILURE_KIND,
                "implement",
                agent_failure_context=failure_context_payload,
            )
        raise _ExecutorPhaseError(
            stage="implement",
            failure_kind=failure.kind.value,
            message=failure.user_facing_message,
            failure_envelope=failure,
        )

    # Success: extract graph and message from the durable response,
    # but preserve the full validated envelope so downstream
    # serialization can attach session_id / turn_id to applyable
    # candidates (SD2: applyable == durable).
    graph_out: dict[str, Any] | None = None
    if isinstance(result.get("graph"), dict):
        graph_out = result["graph"]
    elif isinstance(result.get("candidate"), dict):
        candidate = result["candidate"]
        if isinstance(candidate.get("graph"), dict):
            graph_out = candidate["graph"]

    message: str = ""
    if isinstance(result.get("message"), str):
        message = result["message"]

    if executor_route == "research" or _implementation_response_is_non_applied(result):
        graph_out = None

    return ImplementationResult(
        graph=graph_out,
        message=message,
        durable_response=result,
    )


def _implementation_response_typed_terminal(result: dict[str, Any]) -> str | None:
    """Return the frozen-table terminal state for a durable implement response."""
    from vibecomfy.porting.edit.checkpoint import infer_terminal_state

    return infer_terminal_state(durable=result)


def _implementation_response_is_non_applied(result: dict[str, Any]) -> bool:
    """True for every typed non-apply row. Distinct from generic no-candidate."""
    from vibecomfy.porting.edit.checkpoint import (
        TERMINAL_STATE_APPLIED,
        TERMINAL_STATE_UNDETERMINED,
    )

    state = _implementation_response_typed_terminal(result)
    if state is None:
        return False
    return state not in {TERMINAL_STATE_APPLIED, TERMINAL_STATE_UNDETERMINED}


def _implementation_response_is_terminal_no_candidate(result: dict[str, Any]) -> bool:
    """True only for intentional no-candidate (row 3), never the other table rows.

    ``authority_rejected``, ``infra_failure``, ``clarify``, and ``no_op`` stay
    distinct. Do not collapse them into generic no-candidate.
    """
    from vibecomfy.porting.edit.checkpoint import TERMINAL_STATE_NO_CANDIDATE

    terminal_state = _implementation_response_typed_terminal(result)
    if terminal_state is not None:
        return terminal_state == TERMINAL_STATE_NO_CANDIDATE

    outcome = result.get("outcome")
    outcome_kind = outcome.get("kind") if isinstance(outcome, dict) else None
    no_candidate_reason = result.get("no_candidate_reason")
    if no_candidate_reason == "authority_replay_mismatch":
        return False
    if no_candidate_reason in {
        "implementation_failed",
        "implementation_skipped",
    }:
        return False
    if outcome_kind in {"clarify", "noop"}:
        return False
    if no_candidate_reason in {
        "route_not_applyable",
        "no_graph",
        "unknown_route",
        "no_candidate",
    }:
        return result.get("graph_unchanged") is not False
    if outcome_kind == "requires_custom_nodes":
        return True
    return False


def _durable_terminal_projection(
    implementation_result: ImplementationResult | None,
    *,
    request_graph: Mapping[str, Any] | None = None,
    failure: str | None = None,
    reply: str | None = None,
    mode: str | None = None,
) -> Any:
    """Build the one closed-checkpoint projection for staged and threaded."""
    from vibecomfy.porting.edit.checkpoint import (
        TERMINAL_STATE_APPLIED,
        TERMINAL_STATE_AUTHORITY_REJECTED,
        TERMINAL_STATE_NO_CANDIDATE,
        TERMINAL_STATE_UNDETERMINED,
        LineageError,
        TerminalCloseError,
        close_terminal_checkpoint,
        infer_terminal_state,
        project_terminal_checkpoint,
        recover_terminal_checkpoint,
        _admission_from_payload,
    )

    durable = (
        implementation_result.durable_response
        if implementation_result is not None
        else None
    )
    durable_map = dict(durable) if isinstance(durable, Mapping) else {}
    if "checkpoint" in durable_map or "terminal_state" in durable_map:
        recovered = recover_terminal_checkpoint(durable_map)
        return project_terminal_checkpoint(
            recovered, reply=reply, failure=failure, mode=mode
        )
    inferred = infer_terminal_state(durable=durable_map)
    original = request_graph if isinstance(request_graph, Mapping) else {}
    graph = None
    if implementation_result is not None and isinstance(implementation_result.graph, Mapping):
        graph = implementation_result.graph
    ops = _accepted_delta_ops(implementation_result)
    replay_ok = None
    receipt = durable_map.get("authority_receipt")
    if isinstance(receipt, Mapping):
        replay_ok = bool(receipt.get("replay_ok")) and bool(receipt.get("candidate_matches"))
    if inferred == TERMINAL_STATE_APPLIED or (
        inferred is None and ops and (replay_ok is not False)
    ):
        if replay_ok is False:
            inferred = TERMINAL_STATE_AUTHORITY_REJECTED
        elif not ops:
            inferred = TERMINAL_STATE_UNDETERMINED
        else:
            inferred = TERMINAL_STATE_APPLIED
    if inferred is None:
        inferred = TERMINAL_STATE_NO_CANDIDATE if not ops else TERMINAL_STATE_APPLIED
    if inferred == TERMINAL_STATE_APPLIED and (not ops or replay_ok is False):
        inferred = (
            TERMINAL_STATE_AUTHORITY_REJECTED
            if replay_ok is False
            else TERMINAL_STATE_UNDETERMINED
        )
    rejected = None
    audit = durable_map.get("audit")
    if inferred == TERMINAL_STATE_AUTHORITY_REJECTED:
        if isinstance(audit, Mapping) and isinstance(audit.get("rejected_candidate"), Mapping):
            rejected = dict(audit.get("rejected_candidate"))
        else:
            candidate = durable_map.get("candidate")
            if isinstance(candidate, Mapping):
                rejected = dict(candidate)
    facts: dict[str, Any] = {}
    admitted = None
    if inferred == TERMINAL_STATE_APPLIED and ops:
        admitted = _admission_from_payload(durable_map)
        if admitted is None:
            facts["admission_residual"] = "t2.3_persistence_carries_real_admission"
            from vibecomfy.porting.edit.admit import AdmissionAllowed

            admitted = AdmissionAllowed()
    try:
        checkpoint = close_terminal_checkpoint(
            terminal_state=inferred,
            original_graph=original,
            graph=graph if inferred == TERMINAL_STATE_APPLIED else original,
            ops=ops if inferred == TERMINAL_STATE_APPLIED else (),
            admitted=admitted,
            replay_verified=True if inferred == TERMINAL_STATE_APPLIED else bool(replay_ok),
            rejected_candidate=rejected,
            reason=inferred,
            facts=facts or None,
            evidence_refs=tuple(durable_map.get("evidence_refs") or ()),
            lineage={
                "session_id": str(durable_map.get("session_id") or ""),
                "turn_id": str(durable_map.get("turn_id") or ""),
                "scenario_id": str(durable_map.get("scenario_id") or ""),
                "baseline_id": str(
                    durable_map.get("baseline_turn_id") or durable_map.get("baseline_id") or ""
                ),
            },
        )
    except (TerminalCloseError, LineageError, ValueError):
        checkpoint = close_terminal_checkpoint(
            terminal_state=TERMINAL_STATE_UNDETERMINED,
            original_graph=original,
            reason="close_refused",
            replay_verified=False,
        )
    return project_terminal_checkpoint(
        checkpoint, reply=reply, failure=failure, mode=mode
    )



def _projection_reply(
    projection: Any,
    *,
    fallback: str | None = None,
) -> str:
    if projection is None:
        return fallback or ""
    if isinstance(getattr(projection, "reply", None), str) and projection.reply:
        return projection.reply
    return fallback or ""



def _dedupe_nonempty(values: Any) -> tuple[str, ...]:
    """Return non-empty, de-duplicated strings in original order.

    Classifier research metadata is passed to the agent-owned research stage
    verbatim (no legacy hint rewriting); this only drops blanks and exact
    duplicates so the brief stays compact.
    """
    result: list[str] = []
    seen: set[str] = set()
    for value in values or ():
        item = str(value).strip()
        if not item:
            continue
        key = item.casefold()
        if key in seen:
            continue
        seen.add(key)
        result.append(item)
    return tuple(result)


def _research_brief_from_plan(
    plan: ClassifyDecision,
    *,
    query: str = "",
    suppress_avoid: bool = False,
) -> dict[str, Any]:
    """Return classifier-authored search direction for the research agent.

    This is intentionally directional. It tells the batch REPL what evidence to
    seek, but does not pre-answer the research question or bypass research(...).
    """
    brief: dict[str, Any] = {}
    if plan.research_goal:
        research_goal = str(plan.research_goal).strip()
        if research_goal:
            brief["research_goal"] = research_goal
    if plan.search_directions:
        search_directions = _dedupe_nonempty(plan.search_directions)
        if search_directions:
            brief["search_directions"] = list(search_directions)
    if plan.source_preferences:
        source_preferences = tuple(
            str(source).strip()
            for source in plan.source_preferences
            if str(source).strip()
        )
        if source_preferences:
            brief["source_preferences"] = list(source_preferences)
    if plan.avoid and not suppress_avoid:
        brief["avoid"] = list(plan.avoid)
    if plan.known_graph_context:
        brief["known_graph_context"] = plan.known_graph_context
    if plan.model_families:
        brief["model_families"] = list(plan.model_families)
    if plan.pattern_category:
        brief["pattern_category"] = plan.pattern_category
    if plan.change_goal:
        brief["change_goal"] = plan.change_goal
    if not brief and _canonical_route_for_plan(plan) == "research":
        query_l = query.casefold()
        if "distilled" in query_l or "faster" in query_l:
            brief = {
                "research_goal": "Find distilled or faster ways to run the current ComfyUI video workflow.",
                "search_directions": [
                    "distilled or lightning video/motion models compatible with AnimateDiff-style workflows",
                    "AnimateDiff speed settings such as context length, sampler, steps, and frame count",
                    "ComfyUI workflow examples that trade quality for faster generation",
                ],
                "source_preferences": ["workflows", "messages", "web"],
                "avoid": [
                    "generic searches for the raw sentence",
                    "stopword-only searches such as there way run",
                    "inventing community consensus that the sources do not support",
                ],
                "known_graph_context": plan.known_graph_context
                or "Attached graph may be absent; infer only broad workflow family from the request.",
            }
    return brief


# ── reply grounding (fidelity + node-id guards) ─────────────────────────────
#
# The reply is the user-facing claim about what the executor did.  Two
# v5 failures were narrative defects, not graph defects:
#   * v5-batch-3 #3 — graph_unchanged=true / no_candidate_reason="no_changes"
#     while the reply asserted "the edit landed and validation passed"
#     (false success: the claim contradicted the accepted Δ).
#   * v5-batch-4 #1 — the reply cited HyVideoEncode node ID 120 although the
#     final graph wires node 43 (node-id hallucination).
# The guards below are deterministic, post-hoc, and applied to every reply
# before it is returned: the reply's claims must be consistent with the
# accepted Δ / landed operations, and every cited node id/uid must exist in
# the graph.  They run after the model turn, so a model that ignores the
# prompt-level grounding facts still cannot emit a false-success reply.

_LANDED_EDIT_VERBS = (
    "adjusted|added|applied|bumped|changed|converted|decreased|edited|"
    "increased|lowered|modified|moved|raised|reconnected|removed|replaced|"
    "rewired|switched|updated"
)

# First-person edit claims + declarative success claims.  Only consulted when
# no edit actually landed, so over-matching is safe: when the graph is
# unchanged, any of these phrases is a false-success claim that must be
# corrected.  Negated forms ("No changes were applied", "No edit landed")
# are excluded via the ``no``/``not`` lookbehinds — those are the truthful
# statements the guard itself emits.
_LANDED_CLAIM_RE = re.compile(
    r"(?ix)"
    r"(?<!no\s)(?<!not\s)\b(?:the\s+)?edit\s+landed\b"
    r"|(?<!no\s)(?<!not\s)\b(?:the\s+)?edit\s+was\s+(?:successfully\s+)?applied\b"
    r"|(?<!no\s)(?<!not\s)\b(?:the\s+)?change\s+(?:has|was)\s+been\s+(?:successfully\s+)?applied\b"
    r"|(?<!no\s)(?<!not\s)\bchanges?\s+were\s+(?:successfully\s+)?applied\b"
    r"|\bvalidation\s+passed\b"
    rf"|\bI\s+(?:have\s+)?(?:{_LANDED_EDIT_VERBS})\b"
    rf"|\bI've\s+(?:{_LANDED_EDIT_VERBS})\b"
    r"|\bI\s+set\b(?!\s+up\b)"
    r"|\bI've\s+set\b(?!\s+up\b)"
    r"|\bI\s+(?:have\s+)?made\s+(?:the\s+|these\s+|those\s+|this\s+)?changes?\b"
)

_NO_LANDED_EDIT_CLAIM_RE = re.compile(
    r"(?ix)"
    r"\b(?:the\s+)?(?:workflow|graph)\s+(?:is|was|remains?)\s+(?:exactly\s+)?unchanged\b"
    r"|\bno\s+(?:workflow\s+)?changes?\s+(?:were|was|have\s+been)\s+(?:successfully\s+)?(?:applied|made)\b"
    r"|\bno\s+edit\s+(?:was\s+)?(?:applied|landed)\b"
    r"|\b(?:the\s+)?edit\s+(?:did\s+not|didn't|could\s+not|couldn't)\s+(?:apply|land)\b"
    r"|\bvalidation\s+(?:failed|did\s+not\s+pass)\b"
)

# Cue-anchored node id/uid mentions ("node 43", "node ID 120", "uid 742",
# "node_id 218").  Link ids are a separate namespace and are excluded via the
# fixed-width lookbehind on ``id``.
_NODE_CITE_RE = re.compile(
    r"(?ix)"
    r"\bnode\s+ids?\b\s*[#:]?\s*(\d{1,6})"
    r"|\bnode_id\b\s*[#:]?\s*(\d{1,6})"
    r"|\bnodes?\b\s*[#:]?\s*(\d{1,6})"
    r"|\buids?\b\s*[#:]?\s*(\d{1,6})"
    r"|(?<!\blink\s)\bid\b\s*[#:]?\s*(\d{1,6})"
)

# Narrow graph-census contradictions.  These deliberately require an explicit
# graph/workflow subject (or an explicit "in the graph" suffix), so phrases
# such as "empty latent" and "no negative prompt" are not intercepted.
_EMPTY_GRAPH_CLAIM_RES = (
    re.compile(
        r"(?ix)\b(?:(?:the|this|that)\s+)?(?:attached|current)?\s*"
        r"(?:provided\s+)?(?:(?:workflow\s+)?graph|workflow)\s+"
        r"(?:is|looks|appears|seems)\s+"
        r"(?:to\s+be\s+)?"
        r"(?:(?:currently|presently|entirely|completely|totally)\s+)*empty\b"
    ),
    re.compile(
        r"(?ix)\b(?:(?:the|this|that)\s+)?(?:attached|current)?\s*"
        r"(?:(?:workflow\s+)?graph|workflow)\s+(?:has|contains)\s+"
        r"(?:no|0|zero)\s+(?:nodes?|links?|edges?)\b"
    ),
    re.compile(
        r"(?ix)\b(?:there\s+(?:are|is)|there's)\s+(?:no|0|zero)\s+"
        r"(?:nodes?|links?|edges?)"
        r"(?:\s+(?:or|and)\s+(?:nodes?|links?|edges?))?\s+(?:in|on)\s+"
        r"(?:(?:the|this|that)\s+)?(?:attached|current)?\s*"
        r"(?:(?:workflow\s+)?graph|workflow)\b"
    ),
    re.compile(
        r"(?ix)\b(?:no|0|zero)\s+(?:nodes?|links?|edges?)"
        r"(?:\s+(?:or|and)\s+(?:nodes?|links?|edges?))?\s+"
        r"(?:are|is)\s+(?:present|shown|attached)\s+(?:in|on)\s+"
        r"(?:(?:the|this|that)\s+)?(?:attached|current)?\s*"
        r"(?:(?:workflow\s+)?graph|workflow)\b"
    ),
)


def _reply_claims_empty_graph(reply: str) -> bool:
    """Return true only for explicit empty/zero workflow-graph claims."""
    return any(pattern.search(reply or "") for pattern in _EMPTY_GRAPH_CLAIM_RES)


def _grounded_graph_census_reply(graph: dict[str, Any]) -> str:
    """Build a deterministic non-empty census fallback from graph evidence."""
    evidence = inspect_graph(graph)
    edge_count = len(evidence.edges)
    node_labels = ", ".join(
        f"{node.node_id}: {node.class_type}" for node in evidence.nodes
    )
    details = f" Nodes: {node_labels}." if node_labels else ""
    return (
        f"The attached workflow contains {evidence.node_count} nodes and "
        f"{edge_count} edges; it is not empty.{details} "
        "I could not safely use the model's contradictory graph description, "
        "so this reply is limited to the inspected graph census."
    )

# Identifiers that are never legitimate node cites ("120 fps" style values
# are not cue-anchored, so this set only filters prose like "step 5").  The
# guard additionally requires a surrounding cue word, so bare numbers in the
# reply are never treated as cites.


def _reply_claims_landed_edit(reply: str) -> bool:
    """Return True when *reply* asserts that a graph edit landed/applied.

    Detects first-person edit claims (``I changed ...``, ``I've updated ...``)
    and declarative success claims (``the edit landed``, ``validation
    passed``, ``the change was applied``).  Meaningful only as a guard when
    no edit actually landed: with ``landed=False`` any such phrase is a
    false-success claim.
    """
    if not reply:
        return False
    return _LANDED_CLAIM_RE.search(reply) is not None


def _no_change_reply(reason: str | None = None) -> str:
    """Deterministic truthful reply for the no-edit-landed case.

    Replaces narratives that falsely claimed an edit landed (the fidelity
    guard).  Cite-free by construction, so it also satisfies the node-id
    guard.
    """
    parts = [
        "No changes were applied to the workflow: the graph is unchanged and "
        "no edit landed."
    ]
    if reason:
        parts.append(f"The edit phase reported: {reason}.")
    parts.append(
        "If you'd like, I can explain what an edit would require, but I did "
        "not modify the workflow."
    )
    return "\n\n".join(parts)


def _accepted_delta_reply(delta_ops: tuple[dict[str, Any], ...]) -> str:
    """Truthful fallback when narration contradicts the accepted delta."""
    from vibecomfy.porting.render import render
    from vibecomfy.workflow import VibeWorkflow, WorkflowSource

    empty = VibeWorkflow(
        id="reply-grounding",
        source=WorkflowSource(id="reply-grounding"),
    )
    rendered = str(render(empty, lens="diff", delta=delta_ops))
    detail = rendered.split("\n", 1)[1] if "\n" in rendered else rendered
    return (
        "The workflow edit landed. The accepted change set is:\n\n"
        f"{detail}\n\n"
        "This summary is generated from the accepted delta, which is the "
        "authoritative record of what changed."
    )


def _implementation_landed_edit(result: ImplementationResult | None) -> bool:
    """Return True when the implement phase actually landed graph edits.

    The durable response's accepted Δ (``accepted_batch``) is the canonical
    "what landed" statement (batch 10 — one source, prose never consulted);
    a returned graph or a candidate outcome also implies a landed edit.
    Terminal no-candidate responses (``no_changes``, ``clarify``, ``noop``,
    ...) are by definition not landed.
    """
    if result is None:
        return False
    if _accepted_delta_ops(result):
        return True
    durable = result.durable_response
    if isinstance(durable, Mapping):
        if _implementation_response_is_terminal_no_candidate(dict(durable)):
            return False
        outcome = durable.get("outcome")
        if isinstance(outcome, Mapping) and outcome.get("kind") == "candidate":
            return True
    return result.graph is not None


def _no_candidate_reason(result: ImplementationResult | None) -> str | None:
    """Return the durable no-candidate reason, if any."""
    if result is None:
        return None
    durable = result.durable_response
    if not isinstance(durable, Mapping):
        return None
    reason = durable.get("no_candidate_reason")
    return str(reason) if isinstance(reason, str) and reason.strip() else None


def _collect_node_identifiers(ids: set[str], node: Any) -> None:
    """Collect a node dict's ``id`` / ``uid`` / ``properties.vibecomfy_uid``."""
    if not isinstance(node, Mapping):
        return
    for field in ("id", "uid"):
        value = node.get(field)
        if value is not None and str(value).strip():
            ids.add(str(value))
    properties = node.get("properties")
    if isinstance(properties, Mapping):
        value = properties.get("vibecomfy_uid")
        if value is not None and str(value).strip():
            ids.add(str(value))


def _graph_node_ids(graph: dict[str, Any] | None) -> frozenset[str]:
    """All node identifiers (ids + uids) that exist in the final graph.

    Understands the canonical UI JSON shape (``nodes`` list with per-node
    ``id`` / ``properties.vibecomfy_uid``) and mapping-style IR graphs
    (``nodes`` keyed by node id, with optional per-node ``id``/``uid``).
    """
    if not isinstance(graph, Mapping):
        return frozenset()
    ids: set[str] = set()
    nodes = door_get_nodes(graph)
    if isinstance(nodes, Mapping):
        for key, node in nodes.items():
            ids.add(str(key))
            _collect_node_identifiers(ids, node)
    elif isinstance(nodes, list):
        for node in nodes:
            _collect_node_identifiers(ids, node)
    return frozenset(ids)


def _collect_node_class(classes: dict[str, list[str]], node_id: str, node: Any) -> None:
    if not isinstance(node, Mapping):
        return
    class_type = node.get("class_type") or node.get("type")
    if not isinstance(class_type, str) or not class_type.strip():
        return
    key = class_type.strip().casefold()
    if node_id:
        classes.setdefault(key, []).append(node_id)


def _graph_node_classes(graph: dict[str, Any] | None) -> dict[str, tuple[str, ...]]:
    """casefolded class_type → real node ids (for class-based ID correction)."""
    if not isinstance(graph, Mapping):
        return {}
    classes: dict[str, list[str]] = {}
    nodes = door_get_nodes(graph)
    if isinstance(nodes, Mapping):
        for key, node in nodes.items():
            _collect_node_class(classes, str(key), node)
    elif isinstance(nodes, list):
        for node in nodes:
            if not isinstance(node, Mapping):
                continue
            node_id = node.get("id")
            if node_id is None:
                node_id = node.get("uid")
            _collect_node_class(classes, "" if node_id is None else str(node_id), node)
    return {name: tuple(ids) for name, ids in classes.items()}


def _ground_cited_id(
    sentence: str,
    classes: Mapping[str, tuple[str, ...]],
) -> str | None:
    """Return a real node id when *sentence* uniquely names a node class.

    ``None`` when the sentence names no class, names several nodes of one
    class, or names nothing resolvable — the caller then strips the cite.
    """
    sentence_l = sentence.casefold()
    for class_name, node_ids in classes.items():
        if len(node_ids) != 1 or len(class_name) < 4:
            continue
        if re.search(
            rf"(?<![a-z0-9]){re.escape(class_name)}(?![a-z0-9])",
            sentence_l,
        ):
            return node_ids[0]
    return None


def _strip_cited_id(matched: str) -> str:
    """Remove a hallucinated numeric cite while keeping the prose readable.

    ``node 120`` → ``node``; ``node ID 120`` → ``node``; ``ID 120`` /
    ``uid 120`` → ``""`` (a bare id cite without a number is meaningless).
    """
    lowered = matched.casefold()
    if lowered.startswith(("node id", "node ids", "node_id")):
        return "node"
    if lowered.startswith("nodes "):
        return "nodes"
    if lowered.startswith("node "):
        return "node"
    return ""


def _ground_reply_node_ids(reply: str, graph: dict[str, Any] | None) -> str:
    """Correct or strip node ids cited in *reply* that do not exist in *graph*.

    Every cue-anchored node id/uid mention (``node 43``, ``node ID 120``,
    ``uid 742``, ...) must reference a real node identifier in the final
    graph.  Hallucinated ids are replaced with the real id when the
    surrounding sentence uniquely names the node class (e.g. the reply says
    ``HyVideoEncode`` and the graph has exactly one such node); otherwise the
    bogus cite is stripped.  Real cites are left untouched.
    """
    if graph is None or not reply:
        return reply
    real = _graph_node_ids(graph)
    classes = _graph_node_classes(graph)
    spans: dict[tuple[int, int], str] = {}
    for match in _NODE_CITE_RE.finditer(reply):
        cited = next(
            (group for group in match.groups() if group is not None),
            None,
        )
        if cited is None or cited in real:
            continue
        start, end = match.span()
        s_start = reply.rfind(".", 0, start)
        s_start = 0 if s_start == -1 else s_start + 1
        s_end = reply.find(".", end)
        if s_end == -1:
            s_end = len(reply)
        sentence = reply[s_start:s_end]
        grounded = _ground_cited_id(sentence, classes)
        if grounded is not None:
            spans[(start, end)] = match.group(0).replace(cited, grounded)
        else:
            spans[(start, end)] = _strip_cited_id(match.group(0))
    if not spans:
        return reply
    out: list[str] = []
    pos = 0
    for span in sorted(spans):
        out.append(reply[pos:span[0]])
        out.append(spans[span])
        pos = span[1]
    out.append(reply[pos:])
    return "".join(out)


def _enforce_reply_grounding(
    reply: str,
    *,
    landed: bool,
    graph: dict[str, Any] | None,
    reason: str | None = None,
    delta_ops: tuple[dict[str, Any], ...] = (),
    projection: Any = None,
) -> str:
    """Narrative helper. Authority comes from the one closed-checkpoint projection.

    When ``projection`` is supplied, landed/graph/reason/delta_ops are taken
    from it. This is not a second projector.
    """
    if projection is not None:
        landed = getattr(projection, "terminal_state", None) == "applied"
        graph = getattr(projection, "graph", graph)
        reason = getattr(projection, "reason", reason)
        accepted = getattr(projection, "accepted_delta", ()) or ()
        extracted: list[dict[str, Any]] = []
        for delta in accepted:
            for op in getattr(delta, "ops", ()) or ():
                if isinstance(op, Mapping):
                    extracted.append(dict(op))
        if extracted:
            delta_ops = tuple(extracted)
        if getattr(projection, "failure", None) and landed:
            projected_reply = getattr(projection, "reply", None)
            if isinstance(projected_reply, str) and projected_reply:
                reply = projected_reply
    if not landed and _reply_claims_landed_edit(reply):
        return _no_change_reply(reason=reason)
    if landed and delta_ops and _NO_LANDED_EDIT_CLAIM_RE.search(reply or ""):
        reply = _accepted_delta_reply(delta_ops)
    if graph is not None:
        evidence = inspect_graph(graph)
        if evidence.node_count > 0 and _reply_claims_empty_graph(reply):
            return _grounded_graph_census_reply(graph)
        reply = _ground_reply_node_ids(reply, graph)
    return reply


# ── reply phase ──────────────────────────────────────────────────────────────


def _run_reply(
    request: ExecutorRequest,
    spec: AgentSpecShape,
    *,
    plan: ClassifyDecision,
    effective_graph: dict[str, Any] | None,
    research_result: AgentResearchResult | None = None,
    implementation_result: ImplementationResult | None = None,
    graph_inspection: str | None = None,
    host_ports: ExecutorHostPorts | None = None,
) -> str:
    """Run the reply model turn.

    When *graph_inspection* is provided (inspect-only route), the model
    receives detailed node-by-node graph structure and is instructed to
    describe the workflow without suggesting edits.

    Converts provider exceptions through ``classify_failure``.
    """
    implementation_message: str | None = (
        implementation_result.message if implementation_result else None
    )
    route_behavior = _route_behavior(plan)
    # Edit/research replies use the authoring surface + diff + topology.
    # Inspect-only replies use the separate named/unlabeled evidence lens so
    # positional widget_N authoring aliases cannot become semantic claims.
    delta_ops = _accepted_delta_ops(implementation_result)
    graph_summary = (
        None
        if route_behavior.reply_uses_graph_inspection
        else _render_graph_text(effective_graph, delta=delta_ops)
    )

    effective_route = _canonical_route_for_plan(plan)
    effective_task = plan.effective_task
    candidate_present = (
        route_behavior.can_produce_candidate
        and implementation_result is not None
        and implementation_result.graph is not None
    )
    research_memo = (
        dict(research_result.decision_memo)
        if research_result is not None
        and effective_route == "research"
        and research_result.decision_memo is not None
        else None
    )
    research_ledger = (
        research_result.ledger.to_dict()
        if research_result is not None and effective_route == "adapt"
        else None
    )
    research_attempt = (
        research_result.research_attempt
        if research_result is not None and effective_route in {"research", "adapt"}
        else None
    )

    try:
        landed_edit = _implementation_landed_edit(implementation_result)
        real_node_ids = _graph_node_ids(effective_graph)
        reply_kwargs: dict[str, Any] = {
            "route": spec.agent,
            "model": spec.model,
            "effort": spec.effort,
            "plan": plan,
            "research_memo": research_memo,
            "research_ledger": research_ledger,
            "research_attempt": research_attempt,
            "implementation_message": implementation_message,
            "graph_summary": graph_summary,
            "graph_inspection": graph_inspection,
            "effective_route": effective_route,
            "effective_task": effective_task,
            "candidate_present": candidate_present,
            "interaction_mode": request.interaction_mode,
            "landed_edit": landed_edit,
            "real_node_ids": tuple(sorted(real_node_ids)) if real_node_ids else None,
        }
        # Gracefully degrade if the configured reply provider does not accept
        # newer keyword arguments.
        optional_reply_kwargs = (
            "graph_summary", "graph_inspection", "research_memo", "research_ledger",
            "effective_route", "effective_task",
            "candidate_present", "interaction_mode", "research_attempt",
            "landed_edit", "real_node_ids",
        )
        while True:
            try:
                result = run_reply_turn(request.query, **reply_kwargs)
                break
            except TypeError as exc:
                message = str(exc)
                rejected_key = next(
                    (
                        key
                        for key in optional_reply_kwargs
                        if key in reply_kwargs and key in message
                    ),
                    None,
                )
                if rejected_key is None:
                    raise
                reply_kwargs.pop(rejected_key, None)
        if isinstance(result, str):
            reply = result
        elif isinstance(result, dict):
            reply = ""
            for key in ("reply", "message", "text"):
                value = result.get(key)
                if isinstance(value, str) and value.strip():
                    reply = value
                    break
            if not reply:
                make_failure = (
                    host_ports.failure_envelope
                    if host_ports is not None
                    else failure_envelope
                )
                failure = make_failure(
                    VALIDATION_FAILURE_KIND,
                    "reply",
                    agent_failure_context={
                        "explanation": "Reply phase returned a response without reply text."
                    },
                )
                raise _ExecutorPhaseError(
                    stage="reply",
                    failure_kind=failure.kind.value,
                    message=failure.user_facing_message,
                    failure_envelope=failure,
                )
        else:
            make_failure = (
                host_ports.failure_envelope
                if host_ports is not None
                else failure_envelope
            )
            failure = make_failure(
                VALIDATION_FAILURE_KIND,
                "reply",
                agent_failure_context={
                    "explanation": "Reply phase returned a response without reply text."
                },
            )
            raise _ExecutorPhaseError(
                stage="reply",
                failure_kind=failure.kind.value,
                message=failure.user_facing_message,
                failure_envelope=failure,
            )
        # Fidelity + node-id grounding consumes the one closed-checkpoint
        # projection. This is not a second projector. A projection-time
        # exception after a durable applied product is row 6: keep applied.
        try:
            projection = _durable_terminal_projection(
                implementation_result,
                request_graph=effective_graph,
                reply=reply,
                mode="staged",
            )
        except Exception:
            LOGGER.exception(
                "staged terminal projection failed after durable checkpoint; "
                "preserving applied work with grounded fallback"
            )
            try:
                projection = _durable_terminal_projection(
                    implementation_result,
                    request_graph=effective_graph,
                    failure="staged terminal projection failed",
                    reply=reply,
                    mode="staged",
                )
            except Exception:
                LOGGER.exception(
                    "staged terminal projection retry failed; using accepted-delta fallback"
                )
                if landed_edit:
                    return _accepted_delta_reply(delta_ops) if delta_ops else (
                        "The workflow edit landed. "
                        "the candidate and accepted change evidence are authoritative. "
                        "Later reply narration failed; this fallback is grounded in the "
                        "closed checkpoint, not in model prose."
                    )
                raise
        return _enforce_reply_grounding(
            reply,
            landed=landed_edit,
            graph=effective_graph,
            reason=_no_candidate_reason(implementation_result),
            delta_ops=delta_ops,
            projection=projection,
        )


    except Exception as exc:
        provider_failure = (
            host_ports.is_provider_error(exc)
            if host_ports is not None
            else _is_provider_error(exc)
        )
        classify = (
            host_ports.classify_failure
            if host_ports is not None
            else classify_failure
        )
        failure = classify("agent_response" if provider_failure else "reply", exc)
        failure = _enrich_failure_envelope(failure, exc)
        raise _ExecutorPhaseError(
            stage="reply",
            failure_kind=failure.kind.value,
            message=failure.user_facing_message,
            failure_envelope=failure,
            model_attempts=_failure_model_attempts(failure),
        ) from exc


def _run_inspect_reply(
    request: ExecutorRequest,
    spec: AgentSpecShape,
    *,
    plan: ClassifyDecision,
    host_ports: ExecutorHostPorts | None = None,
) -> str:
    """Run the shared graph-inspection reply surface for either driver."""
    evidence = inspect_graph(request.graph)
    return _run_reply(
        request,
        spec,
        plan=plan,
        effective_graph=request.graph,
        graph_inspection=render_inspect_markdown(evidence),
        host_ports=host_ports,
    )


# ── internal error wrapper ───────────────────────────────────────────────────


class _ExecutorPhaseError(Exception):
    """Internal exception that carries a pre-built :class:`FailureEnvelope`.

    Caught by :func:`run_executor` and converted to an
    :class:`ExecutorResult.failure`.
    """

    def __init__(
        self,
        *,
        stage: str,
        failure_kind: str,
        message: str,
        failure_envelope: Any = None,
        warning_details: tuple[dict[str, Any], ...] = (),
        model_attempts: tuple[dict[str, Any], ...] = (),
    ) -> None:
        super().__init__(message)
        self.stage = stage
        self.failure_kind = failure_kind
        self.failure_envelope = failure_envelope
        self.warning_details = tuple(warning_details)
        self.model_attempts = coerce_model_attempts(model_attempts)


# ── public entry point ───────────────────────────────────────────────────────


def _ws_send(event: str, payload: dict[str, Any], *, client_id: str | None = None) -> None:
    """Best-effort websocket send for executor lifecycle events."""
    try:
        from server import PromptServer  # noqa: PLC0415
    except ImportError:
        return
    try:
        if hasattr(PromptServer.instance, "send_sync") and callable(
            PromptServer.instance.send_sync
        ):
            PromptServer.instance.send_sync(event, payload, sid=client_id)
        elif hasattr(PromptServer.instance, "send_json") and callable(
            PromptServer.instance.send_json
        ):
            PromptServer.instance.send_json(event, payload, sid=client_id)
    except Exception:
        LOGGER.debug(
            "executor websocket send for event %r to client %r failed",
            event,
            client_id,
            exc_info=True,
        )


def _emit_executor_phase_event(
    request: ExecutorRequest,
    *,
    executor_id: str,
    phase: str,
    status: str,
    plan: ClassifyDecision | None = None,
    client_id: str | None = None,
) -> None:
    if not client_id:
        return
    payload = {
        "executor_id": executor_id,
        "phase": phase,
        "status": status,
        "session_id": request.session_id,
        "profile": request.profile or "default",
        "has_graph": request.graph is not None,
        "query_preview": short_text(request.query),
        "emitted_at": datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
    }
    if phase == "classify" and plan is not None:
        payload["plan_summary"] = _classification_plan_summary(plan)
        payload["intent"] = plan.intent
        payload["route"] = plan.effective_route
        payload["task"] = plan.effective_task
    _ws_send("vibecomfy.executor.phase", payload, client_id=client_id)


def _classification_plan_summary(plan: ClassifyDecision) -> str:
    summary = plan.plan_summary.strip()
    if summary:
        return summary
    return _route_behavior(plan).plan_summary


def _run_staged_executor(
    request: ExecutorRequest,
    *,
    client_id: str | None = None,
    classify_only: bool = False,
    additive: bool = False,
    host_ports: ExecutorHostPorts | None = None,
) -> ExecutorResult:
    """Execute the full classify → research → implement → reply pipeline.

    Parameters
    ----------
    request:
        The parsed executor request (query + optional graph/profile/etc.).
    classify_only:
        When True, run only the classify phase and return a diagnostic result
        without invoking research, implement, or reply model calls.  This is
        the honest dry-run seam: ``live=false`` is a product flag, but
        ``classify_only`` guarantees no subsequent phases run.
    additive:
        Headless-only caller hint that this is an additive restore (the caller
        removed a feature and now asks to re-add it).  Forwarded into the
        implement payload so the revise pipeline can relax ONLY the pre-edit
        "input graph has dangling/absent endpoints -> refuse to compound"
        precondition.  All post-edit validation and gates remain enforced.
    host_ports:
        Optional host implementation for edit, failure, hashing, and capture
        operations.  When omitted, ComfyUI's implementation is loaded lazily.

    Returns
    -------
    ExecutorResult
        Always returns a result — failures are captured in the result
        shape, never raised as raw exceptions.
    """
    clear_reply_request_capture()
    ports = host_ports or _legacy_host_ports()
    plan: ClassifyDecision | None = None
    research_result: AgentResearchResult | None = None
    implementation_result: ImplementationResult | None = None
    effective_graph: dict[str, Any] | None = request.graph
    result_graph: dict[str, Any] | None = None
    executor_id = new_profile_id("executor")
    request_fields = {
        "executor_id": executor_id,
        "profile": request.profile or "default",
        "session_id": request.session_id,
        "has_graph": request.graph is not None,
        "query_preview": short_text(request.query),
    }

    profiler_log(LOGGER, "executor.request", **request_fields)
    usage_token = ports.begin_deepseek_usage_capture()
    attempt_token = ports.begin_model_attempt_capture()

    def _build_report(
        *,
        plan: ClassifyDecision | None = None,
        research: AgentResearchResult | None = None,
        implementation: ImplementationResult | None = None,
        classification_status: str = "",
        fallback_model_attempts: tuple[dict[str, Any], ...] = (),
    ) -> Report:
        usage, cache_breakout_complete = ports.snapshot_deepseek_usage_capture()
        model_attempts = ports.snapshot_model_attempt_capture()
        if not model_attempts:
            model_attempts = coerce_model_attempts(fallback_model_attempts)
        est_cost_usd, cost_basis = estimate_deepseek_cost_usd(
            usage,
            cache_breakout_complete=cache_breakout_complete,
        )
        return Report(
            plan=plan,
            research=research,
            implementation=implementation,
            deepseek_usage=usage,
            deepseek_est_cost_usd=est_cost_usd,
            deepseek_cost_basis=cost_basis,
            classification_status=classification_status,
            model_attempts=model_attempts,
            reply_request=snapshot_reply_request_capture(),
        )

    def _finish(result: ExecutorResult) -> ExecutorResult:
        ports.end_deepseek_usage_capture(usage_token)
        ports.end_model_attempt_capture(attempt_token)
        return result

    # ── Resolve profile specs ────────────────────────────────────────────
    try:
        classify_spec = _resolve_spec(request.profile, "classify")
    except Exception as exc:
        classify = ports.classify_failure
        failure = classify("profile", exc)
        return _finish(ExecutorResult.failure(
            kind=failure.kind.value,
            stage="profile",
            message=failure.user_facing_message,
            report=_build_report(),
        ))
    profiler_log(
        LOGGER,
        "executor.profile_resolved",
        **request_fields,
        classify=_spec_fields(classify_spec),
    )

    # ── Build session context (M3) ──────────────────────────────────────
    session_context: dict[str, Any] | None = None
    if request.session_id:
        session_context = _build_session_context(request)

    # ── Phase 1: classify (always via model) ─────────────────────────────
    try:
        _emit_executor_phase_event(
            request,
            executor_id=executor_id,
            phase="classify",
            status="start",
            client_id=client_id,
        )
        with profiler_span(
            LOGGER,
            "executor.phase",
            **request_fields,
            phase="classify",
            **_spec_fields(classify_spec),
        ) as span:
            plan = _run_classify(
                request,
                classify_spec,
                session_context=session_context,
                expect_graph_changed=request.expect_graph_changed,
                host_ports=ports,
            )
            span.update(
                plan_research=plan.research,
                plan_implement=plan.implement,
                plan_reply=plan.reply,
                plan_route=plan.effective_route,
                plan_task=plan.effective_task,
            )
        _emit_executor_phase_event(
            request,
            executor_id=executor_id,
            phase="classify",
            status="progress",
            plan=plan,
            client_id=client_id,
        )
        # The typed classifier output is authoritative for ambiguity.  Code
        # records clarify context but never rewrites the selected route.
        if plan.effective_route == "clarify":
            _save_clarification_context(
                request,
                plan,
                blocked_route=None,
                blocked_task=None,
            )
    except _ExecutorPhaseError as exc:
        # The classify phase raised — the report must NOT claim a model
        # decision (respond_only) that never happened. Record
        # classification_status=failed and leave the plan None so artifacts
        # reflect reality: failed classification carries no invented
        # route/task/intent.
        report = _build_report(
            classification_status="failed",
            fallback_model_attempts=exc.model_attempts,
        )
        return _finish(ExecutorResult.failure(
            kind=exc.failure_kind,
            stage=exc.stage,
            message=str(exc),
            report=report,
        ))

    # ── Classify-only dry-run exit ─────────────────────────────────────────
    if classify_only:
        _emit_executor_phase_event(
            request,
            executor_id=executor_id,
            phase="research",
            status="skipped",
            client_id=client_id,
        )
        _emit_executor_phase_event(
            request,
            executor_id=executor_id,
            phase="implement",
            status="skipped",
            client_id=client_id,
        )
        _emit_executor_phase_event(
            request,
            executor_id=executor_id,
            phase="reply",
            status="skipped",
            client_id=client_id,
        )
        profiler_log(
            LOGGER,
            "executor.result",
            **request_fields,
            has_research=False,
            has_implementation=False,
            result_has_graph=False,
            reply_preview="",
            reason="classify_only",
        )
        report = _build_report(plan=plan)
        route = _canonical_route_for_plan(plan)
        task = plan.effective_task
        parts = [f"[dry-run] classified route: {route}"]
        if task:
            parts.append(f"task: {task}")
        if plan.plan_summary:
            parts.append(f"summary: {plan.plan_summary}")
        return _finish(ExecutorResult.success(
            report=report,
            graph=None,
            reply="\n".join(parts),
        ))

    # ── Deterministic request-purpose enforcement (RC-2/RC-3) ─────────────
    # Request-shape capabilities are shared with the classifier-free threaded
    # driver.  Classifier output still governs ordinary attached-graph turns.
    resolved_plan = _request_purpose_plan(request, plan)
    if resolved_plan != plan:
        plan = resolved_plan
        LOGGER.info(
            "executor: deterministic request purpose → route=%s task=%s implement=%s",
            plan.effective_route,
            plan.effective_task,
            plan.implement,
        )

    # ── Phase 2: research (standalone replies only) ──────────────────────
    retry_skips_research = bool(os.environ.get(_RESEARCH_HANG_RETRY_SKIP_ENV))
    if (
        _canonical_route_for_plan(plan) in {"research", "adapt"}
        and not retry_skips_research
    ):
        try:
            research_spec = _resolve_spec(request.profile, "research")
        except Exception as exc:
            classify = ports.classify_failure
            failure = classify("profile", exc)
            return _finish(ExecutorResult.failure(
                kind=failure.kind.value,
                stage="profile",
                message=failure.user_facing_message,
                report=_build_report(plan=plan),
            ))
        else:
            _emit_executor_phase_event(
                request,
                executor_id=executor_id,
                phase="research",
                status="start",
                client_id=client_id,
            )
            research_span = profiler_span(
                LOGGER,
                "executor.phase",
                **request_fields,
                phase="research",
                **_spec_fields(research_spec),
            )
            research_span.__enter__()
            try:
                research_result = _run_agent_owned_research(
                    request,
                    research_spec,
                    plan=plan,
                )
                research_span.update(
                    research_status=research_result.trace.status,
                    research_verdict=research_result.trace.final_verdict,
                    ledger_entries=len(research_result.ledger.entries),
                    executed_tool_calls=getattr(
                        research_result.trace, "executed_tool_calls", None
                    ),
                    evidence_artifacts=getattr(
                        research_result.trace, "evidence_artifact_count", None
                    ),
                    summary_preview=short_text(research_result.summary),
                )
                # A completed Python call is not necessarily successful
                # research: preserve the trace's exhausted/failed status in
                # profiler output instead of reporting a generic "ok".
                research_span.finish(status=research_result.trace.status)
            except Exception:
                research_span.finish(status="error")
                raise
    else:
        _emit_executor_phase_event(
            request,
            executor_id=executor_id,
            phase="research",
            status="skipped",
            client_id=client_id,
        )
        profiler_log(
            LOGGER,
            "executor.phase.skipped",
            **request_fields,
            phase="research",
            reason=(
                "research_hang_retry"
                if retry_skips_research
                else "plan_disabled"
            ),
        )

    # ── Phase 3: implement (optional) ────────────────────────────────────
    if _should_implement(plan):
        try:
            implement_spec = _resolve_spec(request.profile, "implement")
        except Exception as exc:
            # Profile missing implement spec → failure.
            classify = ports.classify_failure
            failure = classify("profile", exc)
            report = _build_report(plan=plan, research=research_result)
            return _finish(ExecutorResult.failure(
                kind=failure.kind.value,
                stage="profile",
                message=failure.user_facing_message,
                report=report,
            ))

        try:
            _emit_executor_phase_event(
                request,
                executor_id=executor_id,
                phase="implement",
                status="start",
                client_id=client_id,
            )
            with profiler_span(
                LOGGER,
                "executor.phase",
                **request_fields,
                phase="implement",
                **_spec_fields(implement_spec),
            ) as span:
                # Keep the panel alive during long model-backed implement turns:
                # a daemon thread re-emits phase="implement" status="working" every
                # ~15s until _run_implement returns. send_sync is thread-safe.
                heartbeat_stop = threading.Event()

                def _implement_heartbeat() -> None:
                    while not heartbeat_stop.wait(_IMPLEMENT_HEARTBEAT_INTERVAL_SECONDS):
                        _emit_executor_phase_event(
                            request,
                            executor_id=executor_id,
                            phase="implement",
                            status="working",
                            client_id=client_id,
                        )

                heartbeat_thread = threading.Thread(
                    target=_implement_heartbeat,
                    name="vibecomfy-executor-implement-heartbeat",
                    daemon=True,
                )
                try:
                    heartbeat_thread.start()
                    implementation_result = _run_implement(
                        request,
                        implement_spec,
                        plan=plan,
                        research_result=research_result,
                        client_id=client_id,
                        additive=additive,
                        host_ports=ports,
                    )
                finally:
                    heartbeat_stop.set()
                    heartbeat_thread.join(timeout=2.0)
                span.update(
                    graph_returned=implementation_result.graph is not None,
                    message_preview=short_text(implementation_result.message),
                )
        except _ExecutorPhaseError as exc:
            failure_payload: dict[str, Any] = {
                "failure_kind": exc.failure_kind,
                "stage": exc.stage,
                "message": str(exc),
            }
            diagnostics_payload: dict[str, Any] | None = None
            envelope = exc.failure_envelope
            if envelope is not None:
                context_payload = getattr(envelope, "agent_failure_context", None)
                if isinstance(context_payload, Mapping):
                    failure_payload["agent_failure_context"] = context_payload
                    diagnostics_payload = {
                        key: value
                        for key, value in context_payload.items()
                        if key in {"issues", "diagnostics", "validation_errors"}
                    }
                    failure_payload.update(diagnostics_payload)
            report = _build_report(
                plan=plan,
                research=research_result,
                implementation=ImplementationResult(
                    message=str(exc),
                    diagnostics=diagnostics_payload,
                    failure=failure_payload,
                ),
            )
            return _finish(ExecutorResult.failure(
                kind=exc.failure_kind,
                stage=exc.stage,
                message=str(exc),
                report=report,
            ))

        route_behavior = _route_behavior(plan)
        if (
            route_behavior.can_produce_candidate
            and implementation_result.graph is not None
        ):
            effective_graph = implementation_result.graph
            result_graph = implementation_result.graph
        elif (
            _implementation_result_is_terminal_no_candidate(implementation_result)
            and _canonical_route_for_plan(plan) != "research"
        ):
            report = _build_report(
                plan=plan,
                research=research_result,
                implementation=implementation_result,
            )
            # Consume the one closed-checkpoint projection; do not collapse
            # typed terminals into generic no-candidate.
            projection = _durable_terminal_projection(
                implementation_result,
                request_graph=effective_graph,
                reply=implementation_result.message,
                mode="staged",
            )
            reply_text = _enforce_reply_grounding(
                implementation_result.message,
                landed=_implementation_landed_edit(implementation_result),
                graph=effective_graph,
                reason=_no_candidate_reason(implementation_result),
                projection=projection,
            )
            profiler_log(
                LOGGER,
                "executor.result",
                **request_fields,
                has_research=research_result is not None,
                has_implementation=True,
                result_has_graph=False,
                reply_preview=short_text(reply_text),
                reason="terminal_no_candidate",
            )
            return _finish(ExecutorResult.success(
                report=report,
                graph=None,
                reply=reply_text,
            ))
    else:
        _emit_executor_phase_event(
            request,
            executor_id=executor_id,
            phase="implement",
            status="skipped",
            client_id=client_id,
        )
        profiler_log(
            LOGGER,
            "executor.phase.skipped",
            **request_fields,
            phase="implement",
            reason="plan_disabled",
        )

    # ── Phase 4: reply (always via model) ────────────────────────────────
    route_behavior = _route_behavior(plan)
    try:
        reply_spec = _resolve_spec(request.profile, "reply")
    except Exception as exc:
        classify = ports.classify_failure
        failure = classify("profile", exc)
        report = _build_report(
            plan=plan,
            research=research_result,
            implementation=implementation_result,
        )
        return _finish(ExecutorResult.failure(
            kind=failure.kind.value,
            stage="profile",
            message=failure.user_facing_message,
            report=report,
        ))
    try:
        _emit_executor_phase_event(
            request,
            executor_id=executor_id,
            phase="reply",
            status="start",
            client_id=client_id,
        )
        with profiler_span(
            LOGGER,
            "executor.phase",
            **request_fields,
            phase="reply",
            **_spec_fields(reply_spec),
        ) as span:
            reply_text = _run_reply(
                request,
                reply_spec,
                plan=plan,
                effective_graph=effective_graph,
                research_result=research_result,
                implementation_result=implementation_result,
                graph_inspection=render_inspect_markdown(inspect_graph(effective_graph))
                if route_behavior.reply_uses_graph_inspection
                else None,
                host_ports=ports,
            )
            span.update(reply_preview=short_text(reply_text))
    except _ExecutorPhaseError as exc:
        # Preserve durable candidate when reply narration fails.
        # Narration failure is presentation-only (SD1): the durable
        # edit work (candidate, gates, proofs, receipts, eligibility)
        # must not be discarded when only the reply surface fails.
        if (
            implementation_result is not None
            and implementation_result.durable_response is not None
            and result_graph is not None
        ):
            LOGGER.warning(
                "Reply narration failed after durable edit succeeded "
                "(stage=%s, kind=%s); preserving implementation with "
                "deterministic fallback narration.",
                exc.stage,
                exc.failure_kind,
            )
            report = _build_report(
                plan=plan,
                research=research_result,
                implementation=implementation_result,
                fallback_model_attempts=exc.model_attempts,
            )
            projection = _durable_terminal_projection(
                implementation_result,
                request_graph=result_graph,
                failure=str(exc),
                reply=implementation_result.message,
                mode="staged",
            )
            fallback_reply = _projection_reply(
                projection,
                fallback=(
                    implementation_result.message
                    or "Edit completed. The candidate is ready to review."
                ),
            )
            fallback_reply = _enforce_reply_grounding(
                fallback_reply,
                landed=_implementation_landed_edit(implementation_result),
                graph=result_graph,
                reason=_no_candidate_reason(implementation_result),
                delta_ops=_accepted_delta_ops(implementation_result),
                projection=projection,
            )
            return _finish(ExecutorResult.success(
                report=report,
                graph=result_graph,
                reply=fallback_reply,
            ))

        report = _build_report(
            plan=plan,
            research=research_result,
            implementation=implementation_result,
            fallback_model_attempts=exc.model_attempts,
        )
        return _finish(ExecutorResult.failure(
            kind=exc.failure_kind,
            stage=exc.stage,
            message=str(exc),
            report=report,
        ))

    # ── Guard: inspect must never return an edited graph ─────────────────
    if route_behavior.clears_result_graph:
        result_graph = None

    # ── Assemble success result ──────────────────────────────────────────
    report = _build_report(
        plan=plan,
        research=research_result,
        implementation=implementation_result,
    )
    profiler_log(
        LOGGER,
        "executor.result",
        **request_fields,
        has_research=research_result is not None,
        has_implementation=implementation_result is not None,
        result_has_graph=result_graph is not None,
        reply_preview=short_text(reply_text),
    )
    return _finish(ExecutorResult.success(
        report=report,
        graph=result_graph,
        reply=reply_text,
    ))


def _implementation_result_is_terminal_no_candidate(result: ImplementationResult) -> bool:
    durable = result.durable_response
    if durable is None:
        return False
    return _implementation_response_is_terminal_no_candidate(dict(durable))


def run_executor(
    request: ExecutorRequest,
    *,
    client_id: str | None = None,
    classify_only: bool = False,
    additive: bool = False,
    host_ports: ExecutorHostPorts | None = None,
) -> ExecutorResult:
    """Dispatch once between staged and threaded deliberation drivers.

    ``staged`` remains the default and enters the original function without
    altering its events or serialized result. ``threaded`` is imported lazily
    to keep the shared kernel free of mode branches below this seam.
    """
    ports = host_ports or _legacy_host_ports()
    try:
        mode = resolve_orchestration_mode(request)
    except Exception as exc:
        failure = ports.classify_failure("configuration", exc)
        kind = getattr(getattr(failure, "kind", None), "value", "ValidationError")
        return ExecutorResult.failure(
            kind=str(kind),
            stage="configuration",
            message=str(getattr(failure, "user_facing_message", exc)),
        )

    # Environment selection is an ingress boundary too. Materialize only the
    # non-default value so threaded sessions persist their canonical mode while
    # legacy staged requests retain byte-compatible omission.
    if request.pipeline_mode is None and mode == "threaded":
        request = replace(request, pipeline_mode=mode)

    if mode == "staged":
        return _run_staged_executor(
            request,
            client_id=client_id,
            classify_only=classify_only,
            additive=additive,
            host_ports=ports,
        )

    from .threaded import ThreadedKernel, run_threaded_executor

    kernel = ThreadedKernel(
        resolve_spec=_resolve_spec,
        run_implement=_run_implement,
        emit_phase=_emit_executor_phase_event,
        enforce_reply_grounding=_enforce_reply_grounding,
        accepted_delta_ops=_accepted_delta_ops,
        implementation_landed_edit=_implementation_landed_edit,
        no_candidate_reason=_no_candidate_reason,
        run_inspect_reply=_run_inspect_reply,
    )
    return run_threaded_executor(
        request,
        kernel=kernel,
        host_ports=ports,
        executor_id=new_profile_id("executor"),
        client_id=client_id,
        classify_only=classify_only,
        additive=additive,
    )


__all__ = ["run_executor"]
