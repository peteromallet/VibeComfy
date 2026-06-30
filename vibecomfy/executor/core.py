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
import re
from dataclasses import dataclass
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
    end_deepseek_usage_capture,
    snapshot_deepseek_usage_capture,
)
from vibecomfy.agent.deepseek_usage import estimate_deepseek_cost_usd
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
from .execution_plan_builder import build_execution_plan, needs_precedent_plan
from .profiles import (
    AgentSpecShape,
    load_profile,
)
from .research import _default_hivemind_client, research as run_research_phase
from .revision_evidence import collect_graph_facts

LOGGER = logging.getLogger(__name__)

_INSTALL_RESEARCH_TERMS = (
    "install",
    "installation",
    "provider pack",
    "provider-pack",
    "which pack",
    "node pack",
    "custom node pack",
    "registry",
    "local addability",
    "locally addable",
)

_INSTALL_REQUEST_TERMS = (
    "install",
    "installation",
    "which pack",
    "what pack",
    "provider pack",
    "provides",
    "registry",
    "comfyui-manager",
)


def _spec_fields(spec: AgentSpecShape | None) -> dict[str, Any]:
    if spec is None:
        return {}
    return {"route": spec.agent, "model": spec.model}


def _allows_install_or_provider_research(query: str) -> bool:
    query_l = str(query or "").casefold()
    return any(term in query_l for term in _INSTALL_REQUEST_TERMS)


def _sanitize_research_hint_text(text: str, *, query: str = "") -> str | None:
    """Keep classifier hints pointed at precedent unless install info was asked for."""

    stripped = str(text or "").strip()
    if not stripped:
        return None
    text_l = stripped.casefold()
    if (
        _allows_install_or_provider_research(query)
        or not any(term in text_l for term in _INSTALL_RESEARCH_TERMS)
    ):
        return stripped

    replacements = (
        (r"\bnode[- ]pack installation and usage\b", "workflow precedent and usage"),
        (r"\bnode[- ]pack installation\b", "workflow precedent"),
        (r"\bnode[- ]pack details\b", "workflow examples"),
        (r"\bcustom[- ]node[- ]pack\b", "workflow"),
        (r"\bprovider[- ]pack\b", "workflow"),
        (r"\blocal addability\b", "workflow authoring pattern"),
        (r"\blocally addable\b", "workflow-backed"),
        (r"\binstallation and usage\b", "workflow usage"),
        (r"\binstallation\b", "workflow precedent"),
        (r"\binstall\b", "use"),
        (r"\bregistry\b", "workflow"),
        (r"\bnode[- ]pack\b", "workflow"),
    )
    sanitized = stripped
    for pattern, replacement in replacements:
        sanitized = re.sub(pattern, replacement, sanitized, flags=re.IGNORECASE)
    sanitized = re.sub(r"\s+", " ", sanitized).strip(" ;,.")
    sanitized = re.sub(
        r"\bworkflow examples,\s*workflow examples\b",
        "workflow examples",
        sanitized,
        flags=re.IGNORECASE,
    )
    sanitized = re.sub(r"\bworkflow examples,\s+and\b", "workflow examples and", sanitized, flags=re.IGNORECASE)
    return sanitized or None


def _sanitize_search_directions(
    directions: tuple[str, ...] | list[str],
    *,
    query: str = "",
) -> tuple[str, ...]:
    result: list[str] = []
    seen: set[str] = set()
    for direction in directions:
        sanitized = _sanitize_research_hint_text(str(direction), query=query)
        if not sanitized:
            continue
        key = sanitized.casefold()
        if key in seen:
            continue
        seen.add(key)
        result.append(sanitized)
    return tuple(result)


def _sanitize_source_preferences(
    source_preferences: tuple[str, ...] | list[str],
    *,
    query: str = "",
) -> tuple[str, ...]:
    if _allows_install_or_provider_research(query):
        return tuple(str(source) for source in source_preferences if str(source).strip())
    return tuple(
        str(source)
        for source in source_preferences
        if str(source).strip() and str(source).casefold() != "registry"
    )

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
        needs_implement=True,
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


def _should_prefetch_research(plan: ClassifyDecision) -> bool:
    """Return True for routes that should prefetch research.

    Research route: runs through the agentic batch REPL, where the model can
    call research(...) iteratively and write an auditable messages.jsonl.
    Adapt route: prefetches scoped research from classifier fields,
    nested under execution_protocol_notes — does NOT inject raw query
    results into the implementation prompt.
    Revise route: never prefetches research.
    """
    route = _canonical_route_for_plan(plan)
    if route == "adapt":
        return _route_behavior(plan).needs_research
    return False


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
    # LTX/audio route safety net: classifier-proven removal only.
    # When the context mentions LTX + audio, do NOT force a research-backed
    # route (adapt) — that would introduce concrete node-family suggestions
    # through precedent lookups.  Instead, treat this as a temporary
    # process-shape fallback: the existing prior_route (typically revise)
    # provides process-shape editing without research-driven node suggestions.
    # The _context_text_mentions_ltx_audio detector remains available for
    # classifier-proven context awareness in future routing decisions.

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
    *,
    plan: ClassifyDecision | None = None,
) -> ResearchResult:
    """Run the research phase (local corpus + optional Hivemind).

    Research failures are non-fatal; they are captured as warnings in the
    :class:`ResearchResult` and never propagate as exceptions.

    When *plan* is provided and the route is ``adapt``, the query is scoped
    from classifier fields (research_goal, pattern_category, change_goal,
    model_families) instead of the raw user query, keeping implementation
    prompts free of undirected retrieval pollution.
    """
    try:
        query = request.query
        if plan is not None and _canonical_route_for_plan(plan) == "adapt":
            # Prefer focused classifier search_directions; they contain the named
            # targets (e.g. ``Hotshot``) without the verbose explanatory glue
            # that drowns out rare terms in Hivemind keyword search.
            search_directions = _sanitize_search_directions(
                plan.search_directions,
                query=request.query,
            )
            if search_directions:
                query = "; ".join(search_directions)
            else:
                # Build a scoped research query from classifier-derived fields
                # so the adapt prefetch does not inject raw-query results.
                scoped_parts: list[str] = []
                if plan.research_goal:
                    research_goal = _sanitize_research_hint_text(
                        plan.research_goal,
                        query=request.query,
                    )
                    if research_goal:
                        scoped_parts.append(f"Research goal: {research_goal}")
                if plan.pattern_category:
                    scoped_parts.append(f"Pattern category: {plan.pattern_category}")
                if plan.change_goal:
                    scoped_parts.append(f"Change goal: {plan.change_goal}")
                if plan.model_families:
                    families = ", ".join(plan.model_families)
                    scoped_parts.append(f"Model families: {families}")
                if scoped_parts:
                    query = "; ".join(scoped_parts)
        result = run_research_phase(
            query,
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
                precedent_packet=result.precedent_packet,
                precedent_sources=result.precedent_sources,
                workflow_precedent_status=result.workflow_precedent_status,
                selected_precedent=result.selected_precedent,
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


def _adapt_execution_plan_note(
    request: ExecutorRequest,
    plan: ClassifyDecision,
    research_result: ResearchResult | None,
) -> dict[str, Any] | None:
    """Return serialized M2 execution-plan context for qualifying adapt requests."""

    if research_result is None or _canonical_route_for_plan(plan) != "adapt":
        return None

    graph_facts = None
    should_plan = needs_precedent_plan(plan, task=request.query)
    if request.graph is not None:
        try:
            graph_facts = collect_graph_facts(request.graph)
        except Exception:
            LOGGER.debug("execution plan graph-fact collection failed", exc_info=True)
            graph_facts = None
        if not should_plan:
            should_plan = needs_precedent_plan(
                plan,
                task=request.query,
                graph_facts=graph_facts,
            )
    if not should_plan:
        return None

    try:
        execution_plan = build_execution_plan(
            research_result=research_result,
            classify_result=plan,
            task=request.query,
            graph_facts=graph_facts,
            graph=request.graph,
        )
    except Exception:
        LOGGER.debug("execution plan builder failed", exc_info=True)
        return None
    if execution_plan is None:
        return None

    return {
        "plan": execution_plan.to_dict(),
        "provenance": {
            "builder": "vibecomfy.executor.execution_plan_builder.build_execution_plan",
            "routing": "vibecomfy.executor.execution_plan_builder.needs_precedent_plan",
            "phase": "m2_adapt_context",
            "enforced": False,
        },
    }


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
    executor_route = _canonical_route_for_plan(plan)
    if request.graph is None and executor_route != "research":
        return ImplementationResult(
            message="No graph attached; implementation skipped.",
        )
    if executor_route == "adapt" and _adapt_research_failed_closed(research_result):
        message = (
            "I could not safely adapt this workflow because the required workflow "
            "research failed before finding any precedent evidence. The graph is unchanged."
        )
        return ImplementationResult(
            message=message,
            durable_response={
                "ok": True,
                "message": message,
                "graph_unchanged": True,
                "no_candidate_reason": "implementation_skipped",
                "apply_eligible": False,
                "apply_allowed": False,
                "canvas_apply_allowed": False,
                "apply_eligibility": {
                    "applyable": False,
                    "reason": "no_candidate",
                    "message": "No candidate is available to apply.",
                    "warnings": ["research_failed"],
                },
                "outcome": {
                    "kind": "noop",
                    "message": message,
                    "graph_unchanged": True,
                },
            },
            diagnostics={"research_failed": True},
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
        "executor_classification": classification,
    }
    graph_inspection = _graph_inspection(request.graph)
    if isinstance(graph_inspection, str) and graph_inspection.strip():
        payload["graph_inspection"] = graph_inspection
    if research_result is not None:
        if executor_route == "adapt":
            # Adapt route: nest scoped research under execution_protocol_notes,
            # include research_context_packet as discardable context, and do
            # NOT inject raw research_summary/sources into the payload.
            protocol_notes: dict[str, Any] = {}
            # Classifier-derived scoping fields (unranked, context-only).
            if plan.research_goal:
                protocol_notes["research_goal"] = plan.research_goal
            if plan.pattern_category:
                protocol_notes["pattern_category"] = plan.pattern_category
            if plan.change_goal:
                protocol_notes["change_goal"] = plan.change_goal
            if plan.model_families:
                protocol_notes["model_families"] = list(plan.model_families)
            if research_result.workflow_precedent_status:
                protocol_notes["workflow_precedent_status"] = (
                    research_result.workflow_precedent_status
                )
            if research_result.selected_precedent is not None:
                protocol_notes["selected_precedent"] = (
                    research_result.selected_precedent.to_dict()
                )
            # Research summary as contextual note (not directive).
            if research_result.summary:
                protocol_notes["research_summary"] = research_result.summary
            if research_result.precedent_sources:
                protocol_notes["research_sources"] = list(
                    research_result.precedent_sources
                )
            if research_result.warnings:
                protocol_notes["research_warnings"] = list(research_result.warnings)
            execution_plan_note = _adapt_execution_plan_note(
                request,
                plan,
                research_result,
            )
            if execution_plan_note is not None:
                protocol_notes["execution_plan"] = execution_plan_note
            if protocol_notes:
                if research_result.selected_precedent is not None:
                    protocol_notes["_discardability"] = (
                        "This research context is provided as evidence. "
                        "It is NOT authoritative guidance or a required "
                        "implementation. Discard any packet that is empty, "
                        "irrelevant, or contradicts the user's explicit request. "
                        "Use selected_precedent as the grounding workflow "
                        "interpretation unless it contradicts the user's "
                        "explicit request. Other packets remain supporting "
                        "context."
                    )
                else:
                    protocol_notes["_discardability"] = (
                        "This research context is provided as evidence only. "
                        "It is NOT authoritative guidance or a required "
                        "implementation. Discard any packet that is empty, "
                        "irrelevant, or contradicts the user's explicit request."
                    )
                payload["execution_protocol_notes"] = protocol_notes
            # Include precedent packet as discardable research context.
            if (
                research_result.workflow_precedent_status == "compatible_workflow_found"
                and research_result.precedent_packet is not None
            ):
                payload["research_context_packet"] = (
                    research_result.precedent_packet.to_dict()
                )
        else:
            # Non-adapt routes: forward full research payload as before.
            research_payload = research_result.to_dict()
            payload["research_summary"] = research_payload.get("summary", "")
            payload["research_sources"] = research_payload.get("sources", [])
            payload["executor_research"] = research_payload
            # Forward structured precedent data to the edit engine (SD2).
            # The adaptation plan is neutral context — selected_slice is
            # presentation context only, not a winner/recommendation/required
            # implementation.  All available slices are included in all_slices.
            if research_result.precedent_slices:
                payload["precedent_slices"] = [
                    s.to_dict() for s in research_result.precedent_slices
                ]
            if research_result.adaptation_plan is not None:
                payload["adaptation_plan"] = research_result.adaptation_plan.to_dict()
    suppress_research_avoid = (
        executor_route == "adapt"
        and research_result is not None
        and research_result.selected_precedent is not None
    )
    research_brief = _research_brief_from_plan(
        plan,
        query=request.query,
        suppress_avoid=suppress_research_avoid,
    )
    if research_brief:
        payload["research_brief"] = research_brief
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


def _adapt_research_failed_closed(research_result: ResearchResult | None) -> bool:
    """Adapt needs precedent evidence; total research failure must not edit."""
    if research_result is None:
        return True
    has_precedent = bool(
        research_result.precedent_packet
        or research_result.adaptation_plan
        or research_result.precedent_slices
        or research_result.precedent_sources
        or research_result.selected_precedent
    )
    if has_precedent:
        return False
    summary = str(research_result.summary or "").lower()
    warnings = " ".join(str(warning) for warning in (research_result.warnings or ())).lower()
    return "research skipped" in summary or "research phase failed" in warnings


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
        research_goal = _sanitize_research_hint_text(plan.research_goal, query=query)
        if research_goal:
            brief["research_goal"] = research_goal
    if plan.search_directions:
        search_directions = _sanitize_search_directions(plan.search_directions, query=query)
        if search_directions:
            brief["search_directions"] = list(search_directions)
    if plan.source_preferences:
        source_preferences = _sanitize_source_preferences(plan.source_preferences, query=query)
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
                    "treating Discord snippets as authoritative without workflow evidence",
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
    research_sources: tuple[dict[str, Any], ...] | None = None
    if research_result is not None:
        if effective_route == "adapt" and research_result.precedent_sources:
            research_sources = research_result.precedent_sources
        elif research_result.sources:
            research_sources = research_result.sources
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
    classify_only: bool = False,
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
    usage_token = begin_deepseek_usage_capture()

    def _build_report(
        *,
        plan: ClassifyDecision | None = None,
        research: ResearchResult | None = None,
        implementation: ImplementationResult | None = None,
    ) -> Report:
        usage, cache_breakout_complete = snapshot_deepseek_usage_capture()
        est_cost_usd, cost_basis = estimate_deepseek_cost_usd(
            usage,
            cache_breakout_complete=cache_breakout_complete,
        )
        return Report(
            plan=plan or ClassifyDecision.respond_only(),
            research=research,
            implementation=implementation,
            deepseek_usage=usage,
            deepseek_est_cost_usd=est_cost_usd,
            deepseek_cost_basis=cost_basis,
        )

    def _finish(result: ExecutorResult) -> ExecutorResult:
        end_deepseek_usage_capture(usage_token)
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
        report = _build_report(plan=ClassifyDecision.respond_only())
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

    # ── Phase 2: research (standalone replies only) ──────────────────────
    if _should_prefetch_research(plan):
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
                    research_result = _run_research(request, research_spec, plan=plan)
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
        elif _implementation_result_is_terminal_no_candidate(implementation_result):
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
        report = _build_report(
            plan=plan,
            research=research_result,
            implementation=implementation_result,
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
