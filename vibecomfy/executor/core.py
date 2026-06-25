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
from dataclasses import dataclass
from datetime import datetime, timezone
from types import MappingProxyType
from typing import Any

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
from vibecomfy.executor.profiler import (
    new_profile_id,
    profiler_log,
    profiler_span,
    short_text,
)

from .agent_backend import run_classify_turn, run_reply_turn
from .prompts import build_classify_messages
from .contracts import (
    ClassifyDecision,
    ExecutorRequest,
    ExecutorResult,
    ImplementationResult,
    Report,
    ResearchResult,
    _ALLOWED_ROUTES,
    warning_detail_from_exception,
)
from .graph_inspection import _graph_inspection
from .profiles import (
    AgentSpecShape,
    load_profile,
)
from .research import _default_hivemind_client, research as run_research_phase

LOGGER = logging.getLogger(__name__)


def _spec_fields(spec: AgentSpecShape | None) -> dict[str, Any]:
    if spec is None:
        return {}
    return {"route": spec.agent, "model": spec.model}

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
        plan_summary="Report the custom node packs required before editing can continue.",
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
    nodes = graph.get("nodes")
    if isinstance(nodes, list):
        n = len(nodes)
        if n == 0:
            return "Empty graph (0 nodes)."
        # Collect a few class_type hints.
        types: list[str] = []
        for node in nodes[:8]:
            if isinstance(node, dict):
                ct = node.get("class_type") or node.get("type")
                if isinstance(ct, str) and ct.strip():
                    types.append(ct.strip())
        type_list = ", ".join(types[:5]) if types else "unknown"
        suffix = f", and {n - 5} more" if n > 5 else ""
        return f"{n} node(s): {type_list}{suffix}"
    return None


def _build_graph_reference_map(graph: dict[str, Any] | None) -> dict[str, str]:
    """Build a compact ``{node_id: label}`` reference map from *graph*.

    Returns an empty dict when *graph* is None or has no nodes.
    Labels use ``title`` when available, falling back to ``class_type``/``type``.
    """
    if not isinstance(graph, dict):
        return {}
    nodes = graph.get("nodes")
    if not isinstance(nodes, list):
        return {}
    ref_map: dict[str, str] = {}
    for node in nodes:
        if not isinstance(node, dict):
            continue
        nid = node.get("id")
        if nid is None:
            continue
        nid_str = str(nid)
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


_DELEGATED_CLARIFICATION_ANSWERS = (
    "you figure it out",
    "figure it out",
    "choose for me",
    "choose some",
    "choose some please",
    "pick some",
    "pick some please",
    "pick for me",
    "decide for me",
    "decide",
    "please decide",
    "your call",
    "use your judgement",
    "use your judgment",
    "use your best judgement",
    "use your best judgment",
    "default for now",
    "use the default",
    "whatever you think",
    "whatever seems best",
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


def _delegated_clarification_plan(
    request: ExecutorRequest,
    session_context: dict[str, Any] | None,
) -> ClassifyDecision | None:
    """Resolve "you choose" follow-ups to the pending edit route.

    A clarify turn asks the user to make a decision.  When the user explicitly
    delegates that decision back to the agent, another clarify is a loop: the
    executor should continue with the previously blocked edit route and let the
    implementation prompt make the conservative default choice.
    """
    if not isinstance(session_context, dict):
        return None
    if not isinstance(session_context.get("prior_clarification"), dict):
        return None
    query = request.query.strip().lower()
    if not query:
        return None
    if not any(phrase in query for phrase in _DELEGATED_CLARIFICATION_ANSWERS):
        return None

    prior_route = str(
        session_context.get("blocked_route")
        or session_context.get("prior_route")
        or ""
    ).strip()
    if prior_route not in {"revise", "adapt"}:
        prior_route = "revise" if request.graph is not None else "inspect"
    if prior_route == "revise" and _context_text_mentions_ltx_audio(session_context):
        prior_route = "adapt"

    return ClassifyDecision(
        research=(prior_route == "adapt"),
        implement=(prior_route in {"revise", "adapt"}),
        reply=True,
        effort="medium",
        intent="edit" if prior_route in {"revise", "adapt"} else "explain_graph",
        route=prior_route,
        task="edit_graph" if prior_route in {"revise", "adapt"} else "inspect_graph",
        plan_summary=(
            "The user delegated the pending clarification; proceed with a "
            "conservative default decision instead of asking again."
        ),
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
        classify_kwargs: dict[str, Any] = {
            "route": spec.agent,
            "model": spec.model,
            "has_graph": request.graph is not None,
            "graph_summary": _graph_summary(request.graph),
        }
        # Only pre-build messages when session_context has substantive data
        # (recent messages, prior clarification, latest candidate, or blocked route).
        if isinstance(session_context, dict) and (
            session_context.get("recent_messages")
            or session_context.get("prior_clarification")
            or session_context.get("latest_candidate")
            or session_context.get("prior_route")
        ):
            classify_kwargs["messages"] = build_classify_messages(
                request.query,
                has_graph=request.graph is not None,
                graph_summary=_graph_summary(request.graph),
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
        raise _ExecutorPhaseError(
            stage="classify",
            failure_kind=failure.kind.value,
            message=failure.user_facing_message,
            failure_envelope=failure,
        ) from exc
    except Exception as exc:
        failure = classify_failure("classify", exc)
        raise _ExecutorPhaseError(
            stage="classify",
            failure_kind=failure.kind.value,
            message=failure.user_facing_message,
            failure_envelope=failure,
        ) from exc


# ── research phase ───────────────────────────────────────────────────────────


def _run_research(
    request: ExecutorRequest,
    _spec: AgentSpecShape,
) -> ResearchResult:
    """Run the research phase (local corpus + optional Hivemind).

    Research failures are non-fatal; they are captured as warnings in the
    :class:`ResearchResult` and never propagate as exceptions.
    """
    try:
        result = run_research_phase(
            request.query,
            graph=request.graph,
            hivemind_client=_default_hivemind_client,
        )
        inspection = _graph_inspection(request.graph)
        if inspection:
            summary = f"{result.summary}\n\nGraph inspection:\n{inspection}"
            result = ResearchResult(
                summary=summary,
                sources=result.sources,
                warnings=result.warnings,
                warning_details=result.warning_details,
                precedent_slices=result.precedent_slices,
                adaptation_plan=result.adaptation_plan,
            )
        return result
    except Exception as exc:
        LOGGER.exception("executor research phase failed", exc_info=exc)
        # Research is always best-effort.  A total failure (e.g. search
        # index corruption) produces an empty result with a warning so the
        # executor can still produce a reply.
        return ResearchResult(
            summary="Research skipped due to an internal error.",
            warnings=(f"research phase failed: {type(exc).__name__}",),
            warning_details=(warning_detail_from_exception(exc),),
        )


# ── implement phase ──────────────────────────────────────────────────────────


def _run_implement(
    request: ExecutorRequest,
    spec: AgentSpecShape,
    *,
    plan: ClassifyDecision,
    research_result: ResearchResult | None = None,
    client_id: str | None = None,
) -> ImplementationResult:
    """Run the implement phase via ``handle_agent_edit``.

    Forwards the request as ``{task, query, graph, route, model, session_id}`` (SD2).
    The resolved *spec* supplies ``route`` and ``model`` so the edit engine
    uses the profile-configured provider path.
    When research has run, its summary and structured sources are forwarded so
    implementation can act on the discovered workflow/template context.
    Converts the result to an :class:`ImplementationResult`; failures from
    the edit engine are surfaced as :class:`_ExecutorPhaseError`.
    """
    if request.graph is None:
        return ImplementationResult(
            message="No graph attached; implementation skipped.",
        )

    executor_route = _canonical_route_for_plan(plan)
    classification = plan.to_dict()
    classification["route"] = executor_route
    effective_task = plan.effective_task
    if effective_task:
        classification["task"] = effective_task

    payload: dict[str, Any] = {
        "task": request.query,
        "query": request.query,
        "graph": request.graph,
        "route": executor_route,
        "executor_route": executor_route,
        "provider_route": spec.agent,
        "model": spec.model,
        "executor_classification": classification,
    }
    if research_result is not None:
        research_payload = research_result.to_dict()
        payload["research_summary"] = research_payload.get("summary", "")
        payload["research_sources"] = research_payload.get("sources", [])
        payload["executor_research"] = research_payload
        # Forward structured precedent data to the edit engine (SD2).
        if research_result.precedent_slices:
            payload["precedent_slices"] = [
                s.to_dict() for s in research_result.precedent_slices
            ]
        if research_result.adaptation_plan is not None:
            payload["adaptation_plan"] = research_result.adaptation_plan.to_dict()
    if request.session_id:
        payload["session_id"] = request.session_id

    try:
        result = handle_agent_edit(payload, client_id=client_id)
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
        failure = failure_envelope(
            FailureKind(fk) if isinstance(fk, str) and fk in {k.value for k in FailureKind} else FailureKind.VALIDATION_ERROR,
            "implement",
            agent_failure_context={"explanation": fm, "raw_result": result},
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

    return ImplementationResult(
        graph=graph_out,
        message=message,
        durable_response=result,
    )


# ── reply phase ──────────────────────────────────────────────────────────────


def _run_reply(
    request: ExecutorRequest,
    spec: AgentSpecShape,
    *,
    plan: ClassifyDecision,
    effective_graph: dict[str, Any] | None,
    research_result: ResearchResult | None = None,
    implementation_result: ImplementationResult | None = None,
    graph_inspection: str | None = None,
) -> str:
    """Run the reply model turn.

    When *graph_inspection* is provided (inspect-only route), the model
    receives detailed node-by-node graph structure and is instructed to
    describe the workflow without suggesting edits.

    Converts provider exceptions through ``classify_failure``.
    """
    research_summary: str | None = (
        research_result.summary if research_result else None
    )
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

    adaptation_plan: dict[str, Any] | None = None
    if research_result is not None and research_result.adaptation_plan is not None:
        adaptation_plan = research_result.adaptation_plan.to_dict()

    route_behavior = _route_behavior(plan)
    effective_route = _canonical_route_for_plan(plan)
    effective_task = plan.effective_task
    candidate_present = (
        route_behavior.can_produce_candidate
        and implementation_result is not None
        and implementation_result.graph is not None
    )
    research_sources: tuple[dict[str, Any], ...] | None = (
        research_result.sources if research_result and research_result.sources else None
    )
    research_warnings: tuple[str, ...] | None = (
        research_result.warnings if research_result and research_result.warnings else None
    )
    research_precedent_slices: tuple[dict[str, Any], ...] | None = None
    if research_result and research_result.precedent_slices:
        research_precedent_slices = tuple(
            s.to_dict() for s in research_result.precedent_slices
        )

    try:
        reply_kwargs: dict[str, Any] = {
            "route": spec.agent,
            "model": spec.model,
            "plan": plan,
            "research_summary": research_summary,
            "research_sources": research_sources,
            "research_warnings": research_warnings,
            "research_precedent_slices": research_precedent_slices,
            "implementation_message": implementation_message,
            "graph_summary": effective_graph_context,
            "adaptation_plan": adaptation_plan,
            "effective_route": effective_route,
            "effective_task": effective_task,
            "candidate_present": candidate_present,
        }
        # Gracefully degrade if the configured reply provider does not accept
        # newer keyword arguments.
        optional_reply_kwargs = (
            "graph_summary", "adaptation_plan",
            "research_sources", "research_warnings", "research_precedent_slices",
            "effective_route", "effective_task",
            "candidate_present",
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
        raise _ExecutorPhaseError(
            stage="reply",
            failure_kind=failure.kind.value,
            message=failure.user_facing_message,
            failure_envelope=failure,
        ) from exc
    except Exception as exc:
        failure = classify_failure("reply", exc)
        raise _ExecutorPhaseError(
            stage="reply",
            failure_kind=failure.kind.value,
            message=failure.user_facing_message,
            failure_envelope=failure,
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
    ) -> None:
        super().__init__(message)
        self.stage = stage
        self.failure_kind = failure_kind
        self.failure_envelope = failure_envelope
        self.warning_details = tuple(warning_details)


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
) -> ExecutorResult:
    """Execute the full classify → research → implement → reply pipeline.

    Parameters
    ----------
    request:
        The parsed executor request (query + optional graph/profile/etc.).

    Returns
    -------
    ExecutorResult
        Always returns a result — failures are captured in the result
        shape, never raised as raw exceptions.
    """
    plan: ClassifyDecision = ClassifyDecision.respond_only()
    research_result: ResearchResult | None = None
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

    # ── Resolve profile specs ────────────────────────────────────────────
    try:
        classify_spec = _resolve_spec(request.profile, "classify")
        reply_spec = _resolve_spec(request.profile, "reply")
    except Exception as exc:
        failure = classify_failure("profile", exc)
        return ExecutorResult.failure(
            kind=failure.kind.value,
            stage="profile",
            message=failure.user_facing_message,
            report=Report(),
        )
    profiler_log(
        LOGGER,
        "executor.profile_resolved",
        **request_fields,
        classify=_spec_fields(classify_spec),
        reply=_spec_fields(reply_spec),
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
        # ── Delegated clarification loop-break ───────────────────────────
        # When the user responds to a prior clarification with a delegation
        # phrase ("pick some please", "you decide", etc.), deterministically
        # continue with the previously blocked edit route instead of asking
        # again.  This check runs after classify so the model is still called
        # (preserving prompt context assembly), but the route is overridden
        # to avoid a clarification loop.
        delegated_plan: ClassifyDecision | None = None
        if plan.effective_route == "clarify":
            delegated_plan = _delegated_clarification_plan(
                request, session_context
            )
        if delegated_plan is not None:
            plan = delegated_plan
            LOGGER.info(
                "executor: delegated clarification follow-up → route=%s task=%s",
                plan.effective_route,
                plan.effective_task,
            )
        elif plan.effective_route == "clarify":
            intended_route = "adapt" if plan.research else None
            if plan.intent == "edit":
                intended_route = intended_route or "revise"
            _save_clarification_context(
                request,
                plan,
                blocked_route=intended_route,
                blocked_task=(
                    "edit_graph"
                    if intended_route in {"revise", "adapt"}
                    else None
                ),
            )
    except _ExecutorPhaseError as exc:
        report = Report(plan=ClassifyDecision.respond_only())
        return ExecutorResult.failure(
            kind=exc.failure_kind,
                stage=exc.stage,
                message=str(exc),
                report=report,
            )

    # ── Phase 2: research (optional) ─────────────────────────────────────
    if _should_research(plan):
        try:
            research_spec = _resolve_spec(request.profile, "research")
        except Exception:
            # Profile missing research spec is non-fatal — skip research.
            research_result = ResearchResult(
                summary="Research skipped (no research spec in profile).",
                warnings=("research profile missing",),
            )
            _emit_executor_phase_event(
                request,
                executor_id=executor_id,
                phase="research",
                status="skipped",
                client_id=client_id,
            )
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
                try:
                    research_result = _run_research(request, research_spec)
                    span.update(
                        warning_count=len(research_result.warnings or ()),
                        summary_preview=short_text(research_result.summary),
                    )
                except _ExecutorPhaseError as exc:
                    # Research failure is non-fatal; capture as empty result.
                    research_result = ResearchResult(
                        summary="Research skipped due to an error.",
                        warnings=("research phase error; continuing",),
                        warning_details=exc.warning_details
                        or (warning_detail_from_exception(exc),),
                    )
                    span.update(warning_count=len(research_result.warnings or ()))
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
            report = Report(plan=plan, research=research_result)
            return ExecutorResult.failure(
                kind=failure.kind.value,
                stage="profile",
                message=failure.user_facing_message,
                report=report,
            )

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
                implementation_result = _run_implement(
                    request,
                    implement_spec,
                    plan=plan,
                    research_result=research_result,
                    client_id=client_id,
                )
                span.update(
                    graph_returned=implementation_result.graph is not None,
                    message_preview=short_text(implementation_result.message),
                )
        except _ExecutorPhaseError as exc:
            report = Report(
                plan=plan,
                research=research_result,
                implementation=ImplementationResult(message=str(exc)),
            )
            return ExecutorResult.failure(
                kind=exc.failure_kind,
                stage=exc.stage,
                message=str(exc),
                report=report,
            )

        route_behavior = _route_behavior(plan)
        if (
            route_behavior.can_produce_candidate
            and implementation_result.graph is not None
        ):
            effective_graph = implementation_result.graph
            result_graph = implementation_result.graph
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
        report = Report(
            plan=plan,
            research=research_result,
            implementation=implementation_result,
        )
        return ExecutorResult.failure(
            kind=exc.failure_kind,
            stage=exc.stage,
            message=str(exc),
            report=report,
        )

    # ── Guard: inspect must never return an edited graph ─────────────────
    if route_behavior.clears_result_graph:
        result_graph = None

    # ── Assemble success result ──────────────────────────────────────────
    report = Report(
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
    return ExecutorResult.success(
        report=report,
        graph=result_graph,
        reply=reply_text,
    )


__all__ = ["run_executor"]
