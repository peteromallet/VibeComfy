"""Executor orchestration: classify → research → implement → reply.

Implements the full executor pipeline (SD1).  Every request flows through
classify (always calls the model backend), then optionally research and/or
implement, then always reply via the model backend.

Failures are converted through the existing failure-envelope classification
machinery (``classify_failure`` / ``failure_envelope`` from the agent
contracts module) — raw exceptions never leak out of this module.
"""

from __future__ import annotations

import logging
import os
import threading
import time
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from types import MappingProxyType
from typing import Any, Mapping

from vibecomfy.comfy_nodes.agent.contracts import (
    FailureKind,
    classify_failure,
    failure_envelope,
)
from vibecomfy.comfy_nodes.agent.edit import handle_agent_edit
from vibecomfy.comfy_nodes.agent.provider import (
    AuthError,
    MalformedModelJSON,
    MissingRequiredField,
    ProviderError,
)
from vibecomfy.comfy_nodes.agent.runtime import (
    begin_deepseek_usage_capture,
    begin_model_attempt_capture,
    end_deepseek_usage_capture,
    end_model_attempt_capture,
    snapshot_deepseek_usage_capture,
    snapshot_model_attempt_capture,
)
from vibecomfy.agent.deepseek_usage import estimate_deepseek_cost_usd
from vibecomfy.executor.profiler import (
    new_profile_id,
    profiler_log,
    profiler_span,
    short_text,
)

from .agent_backend import run_classify_turn, run_reply_turn
from .agent_research_stage import (
    AgentResearchTrace,
    build_research_brief,
    form_research_question,
    run_agent_research_stage,
)
from .evidence_pack import EvidenceLedger, EvidenceLedgerEntry, EvidencePack
from .stage_contracts import StageDiagnostic, StagePackage
from .tool_contracts import ToolStatus
from .prompts import build_classify_messages
from .contracts import (
    ClassifyDecision,
    ExecutorRequest,
    ExecutorResult,
    ImplementationResult,
    Report,
    _ALLOWED_ROUTES,
    coerce_model_attempts,
    warning_detail_from_exception,
)
from .graph_inspection import _graph_inspection
from .profiles import (
    AgentSpecShape,
    load_profile,
)

LOGGER = logging.getLogger(__name__)

# Interval between ``vibecomfy.executor.phase`` ``status="working"`` heartbeat
# events emitted while the implement phase is running.
_IMPLEMENT_HEARTBEAT_INTERVAL_SECONDS = 15.0


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


_ANSWER_ONLY_ROUTES = frozenset(
    {"clarify", "respond", "inspect", "research", "requires_custom_nodes"}
)


def _answer_only_plan(plan: ClassifyDecision) -> ClassifyDecision:
    """Enforce ``interaction_mode="answer_only"`` on a classify decision.

    Answer-only interactions (diagnosis/advice) must never run the edit gate:
    the request/scenario explicitly declares that editing is not allowed.  This
    is deliberately NOT inferred from ``apply=false`` — that flag only says
    whether a candidate is applied, not whether editing is permitted.
    Non-edit routes keep their semantics; edit-capable routes are downgraded
    to the deterministic research + semantic reply path so the user still
    receives a grounded answer.
    """
    route = _canonical_route_for_plan(plan)
    if route in _ANSWER_ONLY_ROUTES:
        return replace(plan, implement=False)
    return replace(
        plan,
        research=True,
        implement=False,
        reply=True,
        route="research",
        task="research_nodes",
        research_goal=plan.research_goal or plan.change_goal or "",
        plan_summary=(
            "Answer-only interaction: research the inquiry and answer "
            "without editing."
        ),
    )


def _should_research(plan: ClassifyDecision) -> bool:
    """Determine if the research phase should run for *plan*."""
    return _route_behavior(plan).needs_research


def _should_implement(plan: ClassifyDecision) -> bool:
    """Determine if the implement phase should run for *plan*."""
    return _route_behavior(plan).needs_implement


# ── graph summary helpers ────────────────────────────────────────────────────


def _graph_summary(graph: dict[str, Any] | None) -> str | None:
    """Build a compact (≤ 200 char) graph summary for the classify prompt."""
    if not graph:
        return None
    if isinstance(graph.get("nodes"), list) and not graph["nodes"]:
        return "Empty graph (0 nodes)."
    nodes = list(_iter_graph_nodes(graph))
    if not nodes:
        return None
    n = len(nodes)
    # Collect a few class_type hints.
    types: list[str] = []
    for _node_id, node in nodes[:8]:
        ct = node.get("class_type") or node.get("type")
        if isinstance(ct, str) and ct.strip():
            types.append(ct.strip())
    type_list = ", ".join(types[:5]) if types else "unknown"
    suffix = f", and {n - 5} more" if n > 5 else ""
    return f"{n} node(s): {type_list}{suffix}"


def _iter_graph_nodes(graph: dict[str, Any] | None) -> list[tuple[str, dict[str, Any]]]:
    """Return graph nodes from UI-style lists or API-style id mappings."""
    if not isinstance(graph, dict):
        return []
    nodes = graph.get("nodes")
    if isinstance(nodes, list):
        result: list[tuple[str, dict[str, Any]]] = []
        for index, node in enumerate(nodes):
            if not isinstance(node, dict):
                continue
            nid = node.get("id")
            result.append((str(nid) if nid is not None else str(index), node))
        return result
    if isinstance(nodes, dict):
        result = []
        for node_id, node in nodes.items():
            if isinstance(node, dict) and (
                "class_type" in node or "type" in node or "inputs" in node
            ):
                result.append((str(node_id), node))
        return result
    result = []
    for node_id, node in graph.items():
        if isinstance(node, dict) and (
            "class_type" in node or "type" in node or "inputs" in node
        ):
            result.append((str(node_id), node))
    return result


def _build_graph_reference_map(graph: dict[str, Any] | None) -> dict[str, str]:
    """Build a compact ``{node_id: label}`` reference map from *graph*.

    Returns an empty dict when *graph* is None or has no nodes.
    Labels use ``title`` when available, falling back to ``class_type``/``type``.
    """
    ref_map: dict[str, str] = {}
    for nid_str, node in _iter_graph_nodes(graph):
        # Prefer title, then class_type/type.
        title = node.get("title")
        if isinstance(title, str) and title.strip():
            ct = node.get("class_type") or node.get("type")
            if isinstance(ct, str) and ct.strip():
                ref_map[nid_str] = f"{title.strip()} ({ct.strip()})"
            else:
                ref_map[nid_str] = title.strip()
        else:
            ct = node.get("class_type") or node.get("type")
            if isinstance(ct, str) and ct.strip():
                ref_map[nid_str] = ct.strip()
            else:
                ref_map[nid_str] = f"node {nid_str}"
    return ref_map


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


def _run_classify(
    request: ExecutorRequest,
    spec: AgentSpecShape,
    *,
    session_context: dict[str, Any] | None = None,
    graph_reference_map: dict[str, str] | None = None,
) -> ClassifyDecision:
    """Run the classify model turn.

    Always calls the model (SD1).  Converts provider exceptions through
    ``classify_failure`` so raw exceptions never leak.
    """
    try:
        # Build enriched messages when session context carries actual data
        # for reference resolution (M3).  Otherwise, let run_classify_turn
        # build them from the default parameters.
        graph_summary = _graph_summary(request.graph)
        classify_kwargs: dict[str, Any] = {
            "route": spec.agent,
            "model": spec.model,
            "effort": spec.effort,
            "has_graph": request.graph is not None,
            "graph_summary": graph_summary,
        }
        # Pre-build messages whenever we have context beyond the bare query.
        # First-turn graph edits need the node reference map just as much as
        # follow-ups do; otherwise the classifier sees "a graph is attached"
        # without the custom class names required for revise/adapt routing.
        if graph_reference_map or (
            isinstance(session_context, dict)
            and (
                session_context.get("recent_messages")
                or session_context.get("prior_clarification")
                or session_context.get("latest_candidate")
                or session_context.get("prior_route")
            )
        ):
            classify_kwargs["messages"] = build_classify_messages(
                request.query,
                has_graph=request.graph is not None,
                graph_summary=graph_summary,
                session_context=session_context,
                graph_reference_map=graph_reference_map,
            )

        return run_classify_turn(request.query, **classify_kwargs)
    except _ExecutorPhaseError:
        raise
    except (ProviderError, AuthError, MalformedModelJSON,
            MissingRequiredField, TimeoutError) as exc:
        # Map provider-level errors through the failure envelope machinery.
        failure = classify_failure("agent_response", exc)
        failure = _enrich_failure_envelope(failure, exc)
        raise _ExecutorPhaseError(
            stage="classify",
            failure_kind=failure.kind.value,
            message=failure.user_facing_message,
            failure_envelope=failure,
            model_attempts=_failure_model_attempts(failure),
        ) from exc
    except Exception as exc:
        failure = classify_failure("classify", exc)
        failure = _enrich_failure_envelope(failure, exc)
        raise _ExecutorPhaseError(
            stage="classify",
            failure_kind=failure.kind.value,
            message=failure.user_facing_message,
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


_C1_SUPPORTED_SOURCE_PREFERENCES = frozenset({"hivemind", "messages", "workflows"})


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
    def warnings(self) -> tuple[str, ...]:
        return tuple(self.trace.warnings) + tuple(
            str(item.get("message") or "")
            for item in self.policy_diagnostics
            if item.get("message")
        )

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "mode": "agent_owned",
            "route": self.route,
            "status": self.trace.status,
            "verdict": self.trace.final_verdict,
            "diagnostics": [dict(item) for item in self.policy_diagnostics],
        }
        if self.decision_memo is not None:
            # Research-only exposes the bounded C5 memo, never source bodies,
            # iterations, or the full C1 artifact pack.
            payload.update(dict(self.decision_memo))
        else:
            # Edit routes expose only the compact C1 ledger.
            payload["ledger"] = self.ledger.to_dict()
        return payload


def _source_policy_entries(
    plan: ClassifyDecision,
) -> tuple[tuple[EvidenceLedgerEntry, ...], tuple[dict[str, Any], ...]]:
    """Make unsupported classifier source requests visible, never rewrite them."""

    entries: list[EvidenceLedgerEntry] = []
    diagnostics: list[dict[str, Any]] = []
    for source in plan.source_preferences:
        source_name = str(source).strip()
        if not source_name or source_name.casefold() in _C1_SUPPORTED_SOURCE_PREFERENCES:
            continue
        message = (
            f"Requested source '{source_name}' is unavailable in the active C1 "
            "research stage; it was not silently substituted or removed."
        )
        entries.append(EvidenceLedgerEntry(
            decision="source_policy",
            conclusion=message,
            evidence_ids=(),
            uncertainty=f"No {source_name} evidence was inspected.",
        ))
        diagnostics.append({
            "code": "unsupported_research_source",
            "severity": "warning",
            "source": source_name,
            "message": message,
        })
    return tuple(entries), tuple(diagnostics)


def _research_decision_memo(
    trace: AgentResearchTrace,
    *,
    diagnostics: tuple[dict[str, Any], ...],
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
    return {
        "question": trace.question,
        "conclusion": trace.summary or "No supported conclusion was produced.",
        "citations": inspected[:6],
        "uncertainty": " ".join(uncertainty_parts),
        "next_action": (
            "Use this conclusion for the requested next step."
            if trace.final_verdict == "enough"
            else "Refine the unresolved research question before acting on this conclusion."
        ),
    }


def _research_stage_package(
    *,
    route: str,
    trace: AgentResearchTrace,
    pack: EvidencePack,
    policy_diagnostics: tuple[dict[str, Any], ...],
) -> StagePackage:
    """Build the F01 research :class:`StagePackage` handed to implement.

    The typed envelope carries the evidence artifacts, the compact ledger,
    and typed diagnostics (policy warnings, trace failures) — the only
    research content the implement phase may consume.  ``StageRequest`` is
    not part of this seam: the classify decision (goal/route) is authoritative
    and the package references are explicit on the wire.
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
    status = (
        ToolStatus.OK
        if trace.status == "ok"
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
    memo = _research_decision_memo(trace, diagnostics=diagnostics) if route == "research" else None
    return AgentResearchResult(
        route=route,
        trace=trace,
        evidence_pack=pack,
        package=_research_stage_package(
            route=route,
            trace=trace,
            pack=pack,
            policy_diagnostics=diagnostics,
        ),
        policy_diagnostics=diagnostics,
        decision_memo=memo,
    )


def _research_package_is_usable(research_result: AgentResearchResult | None) -> bool:
    """Fail-closed gate for the research→implement handoff.

    An adapt implementation may proceed only when the C1 research package is
    OK AND the research agent produced an ``enough`` synthesis.  Failed,
    exhausted (deadline / max-turn), and ``refine`` verdicts mean there is no
    usable synthesis to implement from — proceeding would act on unsupported
    conclusions.  A missing research result or a result without a typed
    ``StagePackage`` is NOT usable on the adapt route: the executor always
    supplies a typed package, so anything else is a caller bug and must not
    silently proceed.
    """
    if research_result is None:
        return False
    package = getattr(research_result, "package", None)
    if not isinstance(package, StagePackage):
        return False
    if package.status is not ToolStatus.OK:
        return False
    trace = getattr(research_result, "trace", None)
    if trace is not None and getattr(trace, "final_verdict", None) not in (None, "enough"):
        return False
    return True


def _run_implement(
    request: ExecutorRequest,
    spec: AgentSpecShape,
    *,
    plan: ClassifyDecision,
    research_result: AgentResearchResult | None = None,
    client_id: str | None = None,
    additive: bool = False,
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
    # P0-b: consume the research package status fail-closed.  An adapt
    # implementation must not run — and must not report success — when the
    # C1 research stage failed, exhausted its loop without an agent finish,
    # or concluded with a refine verdict: there is no usable synthesis to
    # implement from.
    if (
        executor_route == "adapt"
        and research_result is not None
        and not _research_package_is_usable(research_result)
    ):
        trace = research_result.trace
        failure = failure_envelope(
            FailureKind.VALIDATION_ERROR,
            "research",
            agent_failure_context={
                "explanation": (
                    "C1 research produced no usable synthesis "
                    f"(status={trace.status}, verdict={trace.final_verdict}); "
                    "implement was skipped so no edit is made from unsupported conclusions."
                )
            },
        )
        raise _ExecutorPhaseError(
            stage="research",
            failure_kind=failure.kind.value,
            message=failure.user_facing_message,
            failure_envelope=failure,
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
    graph_inspection = _graph_inspection(request.graph)
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

    try:
        from vibecomfy.comfy_nodes.agent.session import payload_hash  # noqa: PLC0415

        result = handle_agent_edit(
            payload,
            client_id=client_id,
            # Classifier/research output is server-derived and may vary across
            # retries. Bind deduplication to the stable public submit instead.
            idempotency_request_hash=payload_hash(request.to_dict()),
        )
    except Exception as exc:
        failure = classify_failure("implement", exc)
        raise _ExecutorPhaseError(
            stage="implement",
            failure_kind=failure.kind.value,
            message=failure.user_facing_message,
            failure_envelope=failure,
        ) from exc

    if not isinstance(result, dict):
        failure = failure_envelope(
            FailureKind.VALIDATION_ERROR,
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
        failure = failure_envelope(
            FailureKind(fk) if isinstance(fk, str) and fk in {k.value for k in FailureKind} else FailureKind.VALIDATION_ERROR,
            "implement",
            agent_failure_context={
                "explanation": fm,
                **{
                    key: value
                    for key, value in failure_payload.items()
                    if key not in {"message", "stage", "failure_kind"}
                },
            },
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

    if executor_route == "research" or _implementation_response_is_terminal_no_candidate(result):
        graph_out = None

    return ImplementationResult(
        graph=graph_out,
        message=message,
        durable_response=result,
    )


def _implementation_response_is_terminal_no_candidate(result: dict[str, Any]) -> bool:
    """Return true when agent-edit succeeded by declining an applyable candidate."""
    outcome = result.get("outcome")
    outcome_kind = outcome.get("kind") if isinstance(outcome, dict) else None
    apply_eligible = result.get("apply_eligible")
    if not isinstance(apply_eligible, bool):
        eligibility = result.get("apply_eligibility")
        if isinstance(eligibility, dict):
            apply_eligible = bool(
                eligibility.get("applyable")
                if "applyable" in eligibility
                else eligibility.get("apply_eligible")
            )

    no_candidate_reason = result.get("no_candidate_reason")
    if no_candidate_reason in {
        "route_not_applyable",
        "no_graph",
        "implementation_skipped",
        "implementation_failed",
        "no_changes",
        "unknown_route",
    }:
        return result.get("graph_unchanged") is not False
    if outcome_kind in {"clarify", "requires_custom_nodes"}:
        return True
    if outcome_kind == "noop":
        return result.get("graph_unchanged") is not False
    return result.get("graph_unchanged") is True and apply_eligible is not True


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
    graph_summary = _graph_summary(effective_graph)

    # For inspect-only, replace the compact graph summary with the detailed
    # inspection evidence so the reply model can describe the workflow
    # step-by-step without suggesting edits.
    effective_graph_context: str | None = graph_summary
    if graph_inspection:
        effective_graph_context = graph_inspection

    route_behavior = _route_behavior(plan)
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

    try:
        reply_kwargs: dict[str, Any] = {
            "route": spec.agent,
            "model": spec.model,
            "effort": spec.effort,
            "plan": plan,
            "research_memo": research_memo,
            "research_ledger": research_ledger,
            "implementation_message": implementation_message,
            "graph_summary": effective_graph_context,
            "effective_route": effective_route,
            "effective_task": effective_task,
            "candidate_present": candidate_present,
            "interaction_mode": request.interaction_mode,
        }
        # Gracefully degrade if the configured reply provider does not accept
        # newer keyword arguments.
        optional_reply_kwargs = (
            "graph_summary", "research_memo", "research_ledger",
            "effective_route", "effective_task",
            "candidate_present", "interaction_mode",
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
            return result
        if isinstance(result, dict):
            for key in ("reply", "message", "text"):
                value = result.get(key)
                if isinstance(value, str) and value.strip():
                    return value
        failure = failure_envelope(
            FailureKind.VALIDATION_ERROR,
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
    except (ProviderError, AuthError, MalformedModelJSON,
            MissingRequiredField, TimeoutError) as exc:
        failure = classify_failure("agent_response", exc)
        failure = _enrich_failure_envelope(failure, exc)
        raise _ExecutorPhaseError(
            stage="reply",
            failure_kind=failure.kind.value,
            message=failure.user_facing_message,
            failure_envelope=failure,
            model_attempts=_failure_model_attempts(failure),
        ) from exc
    except Exception as exc:
        failure = classify_failure("reply", exc)
        failure = _enrich_failure_envelope(failure, exc)
        raise _ExecutorPhaseError(
            stage="reply",
            failure_kind=failure.kind.value,
            message=failure.user_facing_message,
            failure_envelope=failure,
            model_attempts=_failure_model_attempts(failure),
        ) from exc


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


def run_executor(
    request: ExecutorRequest,
    *,
    client_id: str | None = None,
    classify_only: bool = False,
    additive: bool = False,
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

    Returns
    -------
    ExecutorResult
        Always returns a result — failures are captured in the result
        shape, never raised as raw exceptions.
    """
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
    usage_token = begin_deepseek_usage_capture()
    attempt_token = begin_model_attempt_capture()

    def _build_report(
        *,
        plan: ClassifyDecision | None = None,
        research: AgentResearchResult | None = None,
        implementation: ImplementationResult | None = None,
        classification_status: str = "",
        fallback_model_attempts: tuple[dict[str, Any], ...] = (),
    ) -> Report:
        usage, cache_breakout_complete = snapshot_deepseek_usage_capture()
        model_attempts = snapshot_model_attempt_capture()
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
        )

    def _finish(result: ExecutorResult) -> ExecutorResult:
        end_deepseek_usage_capture(usage_token)
        end_model_attempt_capture(attempt_token)
        return result

    # ── Resolve profile specs ────────────────────────────────────────────
    try:
        classify_spec = _resolve_spec(request.profile, "classify")
    except Exception as exc:
        failure = classify_failure("profile", exc)
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

    # ── Build session context and graph reference map (M3) ────────────────
    session_context: dict[str, Any] | None = None
    if request.session_id:
        session_context = _build_session_context(request)
    graph_reference_map = _build_graph_reference_map(request.graph)

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
                graph_reference_map=graph_reference_map,
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

    # ── Answer-only interaction enforcement (PR-B) ────────────────────────
    # interaction_mode="answer_only" is the explicit request/scenario contract
    # for diagnosis/advice turns: no graph edit may be produced, whatever the
    # classifier decided.  It is never inferred from apply=false — that flag
    # only declares whether a candidate is applied, not whether editing is
    # permitted.  Edit-capable routes are downgraded to agent-owned research
    # + semantic reply so the user still gets a grounded answer.
    if request.interaction_mode == "answer_only":
        plan = _answer_only_plan(plan)
        LOGGER.info(
            "executor: answer_only interaction → route=%s task=%s implement=%s",
            plan.effective_route,
            plan.effective_task,
            plan.implement,
        )

    # ── Phase 2: research (standalone replies only) ──────────────────────
    if _canonical_route_for_plan(plan) in {"research", "adapt"}:
        try:
            research_spec = _resolve_spec(request.profile, "research")
        except Exception as exc:
            failure = classify_failure("profile", exc)
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
            with profiler_span(
                LOGGER,
                "executor.phase",
                **request_fields,
                phase="research",
                **_spec_fields(research_spec),
            ) as span:
                research_result = _run_agent_owned_research(
                    request,
                    research_spec,
                    plan=plan,
                )
                span.update(
                    research_status=research_result.trace.status,
                    research_verdict=research_result.trace.final_verdict,
                    ledger_entries=len(research_result.ledger.entries),
                    summary_preview=short_text(research_result.summary),
                )
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
            reason="plan_disabled",
        )

    # ── Phase 3: implement (optional) ────────────────────────────────────
    if _should_implement(plan):
        try:
            implement_spec = _resolve_spec(request.profile, "implement")
        except Exception as exc:
            # Profile missing implement spec → failure.
            failure = classify_failure("profile", exc)
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
            reply_text = implementation_result.message
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
        failure = classify_failure("profile", exc)
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
                graph_inspection=_graph_inspection(effective_graph)
                if route_behavior.reply_uses_graph_inspection
                else None,
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
            fallback_reply = (
                implementation_result.message
                or "Edit completed. The candidate is ready to review."
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


__all__ = ["run_executor"]
