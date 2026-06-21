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
)
from .graph_inspection import (
    graph_inspection_text,
    _graph_inspection,
)
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
    "inspect": RouteBehavior(
        route="inspect",
        needs_research=False,
        needs_implement=False,
        plan_summary="Inspect the graph without editing.",
        clears_result_graph=True,
        reply_uses_graph_inspection=True,
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
    if plan.implement and plan.research:
        return "adapt"
    if plan.implement:
        return "revise"
    if plan.research:
        return "inspect"
    return "clarify"


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

    Attempts to load recent conversation history and prior clarification
    artifacts from the session store.  Returns ``None`` when no session
    context is available (no session_id, store unavailable, etc.).
    """
    if not request.session_id:
        return None

    context: dict[str, Any] = {}

    # Try to load the same chat artifacts used by direct agent-edit prompt
    # memory.  Session state stores turn bookkeeping, while chat.json carries
    # the user/agent text needed to resolve follow-up references.
    try:
        from vibecomfy.comfy_nodes.agent import edit as agent_edit

        chat = agent_edit.read_session_chat(
            getattr(agent_edit, "_SESSION_ROOT"),
            request.session_id,
            max_messages=getattr(agent_edit, "PROMPT_MEMORY_MESSAGES", 5),
        )
        if isinstance(chat, dict):
            messages = chat.get("messages")
            if isinstance(messages, list) and messages:
                context["recent_messages"] = messages[-6:]
            latest_candidate = chat.get("latest_candidate")
            if isinstance(latest_candidate, dict):
                context["latest_candidate"] = latest_candidate

            latest_agent = next(
                (
                    msg for msg in reversed(messages or [])
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

        from vibecomfy.comfy_nodes.agent.session import (
            read_state,
            session_dir_for,
        )

        state = read_state(session_dir_for(getattr(agent_edit, "_SESSION_ROOT"), request.session_id))
        if isinstance(state, dict):
            # Carry forward prior clarification context if present.
            prior_clarification = state.get("prior_clarification")
            if isinstance(prior_clarification, dict):
                context["prior_clarification"] = prior_clarification

            # Carry forward blocked route/task for continuation. Prefer the
            # intended blocked route over the public clarify route when both
            # are present.
            prior_route = state.get("blocked_route") or state.get("prior_route")
            if isinstance(prior_route, str) and prior_route.strip():
                context["prior_route"] = prior_route.strip()
                prior_task = state.get("blocked_task") or state.get("prior_task")
                if isinstance(prior_task, str) and prior_task.strip():
                    context["prior_task"] = prior_task.strip()
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


# ── preclassify blockers (M3) ────────────────────────────────────────────────


def _preclassify_blockers(
    request: ExecutorRequest,
    session_context: dict[str, Any] | None = None,
) -> ClassifyDecision | None:
    """Check for obvious unsafe or ambiguous edit-like requests before
    the classify model is called.

    When a blocker is found, returns a ``ClassifyDecision`` with
    ``route="clarify"`` and a Markdown question/options so the executor
    can short-circuit model classification.  Returns ``None`` when no
    preclassify blockers apply, allowing normal model classification to
    proceed.

    Checked conditions (any single match forces ``clarify``):
    * Missing graph on a request that looks like an edit.
    * References to nonexistent node ids in the request text.
    * Unresolved pronouns or ambiguous references (\"it\", \"that node\").
    * Missing required attachments (e.g. image/model references without
      uploaded files).
    * Conflicting constraints in the request.
    * Impossible free-tier video requests (>8K resolution or >5000 frames
      without a paid tier indicator).
    * Incompatible architecture splice requests (e.g. Flux + SDXL in the
      same pipeline without a documented bridge).

    This function is pure and deterministic — it reads only *request* and
    *session_context*, never calls a model or provider.
    """
    import re

    query = request.query.strip()
    query_lower = query.lower()
    graph = request.graph

    prior_clarification = (
        session_context.get("prior_clarification")
        if isinstance(session_context, dict)
        else None
    )
    prior_options = (
        prior_clarification.get("clarification_options")
        if isinstance(prior_clarification, dict)
        else None
    )
    if not isinstance(prior_options, list):
        prior_options = []
    option_match = re.search(r'\b(?:option|choice)\s*#?\s*(\d+)\b', query_lower)
    if option_match:
        option_index = int(option_match.group(1))
        if option_index < 1 or option_index > len(prior_options):
            return ClassifyDecision(
                research=False,
                implement=False,
                reply=True,
                route="clarify",
                task="respond",
                clarification_question=(
                    f"You referred to option {option_index}, but I do not "
                    "have a matching prior clarification option in this session. "
                    "Could you restate the option you want?"
                ),
                clarification_options=(
                    "Restate the exact edit you want.",
                    "Ask me to list the current graph nodes/options again.",
                ),
                plan_summary="Unresolved prior option reference requires clarification.",
            )

    # ── 1. Missing graph edit requests ──────────────────────────────────
    if graph is None or not isinstance(graph, dict):
        nodes = graph.get("nodes") if isinstance(graph, dict) else None
        if not isinstance(nodes, list) or not nodes:
            edit_keywords = (
                "edit the graph", "modify the graph",
                "change the graph", "fix this graph",
                "splice", "patch the graph", "repair graph",
            )
            if any(kw in query_lower for kw in edit_keywords):
                return ClassifyDecision(
                    research=False,
                    implement=False,
                    reply=True,
                    route="clarify",
                    task="respond",
                    clarification_question=(
                        "You asked me to edit your graph, but no graph is "
                        "attached. Would you like to:\n"
                    ),
                    clarification_options=(
                        "Attach a graph and re-submit your edit request.",
                        "Describe what kind of graph you want to build so I can help you construct one.",
                        "Ask a different question about ComfyUI nodes or workflows.",
                    ),
                    plan_summary="Missing graph edit request requires clarification.",
                )

    # ── 2. Nonexistent node ids ─────────────────────────────────────────
    if isinstance(graph, dict):
        nodes = graph.get("nodes")
        if isinstance(nodes, list) and nodes:
            # Collect all node ids.
            node_ids: set[str] = set()
            for n in nodes:
                if isinstance(n, dict):
                    nid = n.get("id")
                    if nid is not None:
                        node_ids.add(str(nid))

            # Check if query references a node id not in the graph.
            id_pattern = re.compile(r'\bnode\s*[#\[]?\s*(\d+)\s*\]?\b', re.IGNORECASE)
            for match in id_pattern.finditer(query):
                ref_id = match.group(1)
                if ref_id not in node_ids:
                    return ClassifyDecision(
                        research=False,
                        implement=False,
                        reply=True,
                        route="clarify",
                        task="respond",
                        clarification_question=(
                            f"You referenced node #{ref_id}, but that node "
                            f"does not exist in the current graph "
                            f"(available node ids: {', '.join(sorted(node_ids, key=int))}). "
                            f"Would you like to:\n"
                        ),
                        clarification_options=(
                            "Re-check the node id and re-submit.",
                            "Describe the node by its class type or title instead.",
                            "Ask me to list the nodes in the graph so you can pick the right one.",
                        ),
                        plan_summary=(
                            f"Nonexistent node id #{ref_id} referenced in request."
                        ),
                    )

    # ── 3. Unresolved pronouns / ambiguous references ───────────────────
    ambiguous_patterns = [
        r'\b(it|that|this)\s+(node|one)\b',
        r'\b(the)\s+(node|connection|link|wire|edge)\b',
        r'\b(change|fix|update|remove|delete)\s+(it|that|this)\b',
    ]
    # When the graph has ≤2 nodes, "the node" is unambiguous enough.
    node_count = 0
    if isinstance(graph, dict):
        nodes_check = graph.get("nodes")
        if isinstance(nodes_check, list):
            node_count = len(nodes_check)
    for pattern in ambiguous_patterns:
        if re.search(pattern, query, re.IGNORECASE) and (
            "node #" not in query_lower
            and "node id" not in query_lower
            and "the ksampler" not in query_lower
            and "the clip" not in query_lower
            and "the vae" not in query_lower
            and "the checkpoint" not in query_lower
            and "the loader" not in query_lower
            and "the encode" not in query_lower
            and "the decode" not in query_lower
            and "the save" not in query_lower
            and "the preview" not in query_lower
            and "the sampler" not in query_lower
            and not option_match
            and not (
                isinstance(session_context, dict)
                and (
                    session_context.get("latest_candidate")
                    or len(prior_options) == 1
                )
            )
            and not (node_count <= 2 and "the node" in query_lower)
        ):
            return ClassifyDecision(
                research=False,
                implement=False,
                reply=True,
                route="clarify",
                task="respond",
                clarification_question=(
                    "Your request uses an ambiguous reference (e.g. \"it\", "
                    "\"that node\") without specifying which node in the "
                    "graph you mean. Could you clarify:\n"
                ),
                clarification_options=(
                    "Specify the node by its id number (e.g. \"node #3\").",
                    "Specify the node by its class type and title (e.g. \"the KSampler labeled 'Main Pass'\").",
                    "Let me list the nodes in the graph first so you can pick one.",
                ),
                plan_summary="Ambiguous pronoun/reference in request requires clarification.",
            )

    # ── 4. Missing required attachments ─────────────────────────────────
    # Only flag when the request clearly references a user-uploaded file,
    # not a conceptual "my image/video/model" that means their use case.
    attachment_keywords = [
        "this image", "this video", "this audio", "this model",
        "the attached", "uploaded", "my file",
        "the file i uploaded", "the image i uploaded",
    ]
    if any(kw in query_lower for kw in attachment_keywords):
        # Check session_context for evidence of uploaded files.
        has_attachment = False
        if isinstance(session_context, dict):
            attachments = session_context.get("attachments")
            if isinstance(attachments, (list, tuple)) and attachments:
                has_attachment = True
            elif session_context.get("has_attachment") is True:
                has_attachment = True
        if not has_attachment:
            return ClassifyDecision(
                research=False,
                implement=False,
                reply=True,
                route="clarify",
                task="respond",
                clarification_question=(
                    "Your request references an attached file or uploaded "
                    "asset, but no attachment was found in this session. "
                    "Would you like to:\n"
                ),
                clarification_options=(
                    "Upload the file and re-submit your request.",
                    "Describe the file/model you need and I can help you find it.",
                    "Re-phrase your request without assuming an attachment.",
                ),
                plan_summary="Missing attachment referenced in request.",
            )

    # ── 5. Conflicting constraints ──────────────────────────────────────
    conflict_pairs = [
        (("remove", "keep"), ("remove all nodes but keep",)),
        (("add", "remove"), ("add and remove the same",)),
        (("8k", "480p"), ()),
        (("flux", "sdxl"), ("flux and sdxl", "flux + sdxl")),
        (("realistic", "anime"), ("realistic and anime",)),
    ]
    for (a, b), disambiguations in conflict_pairs:
        has_both = (
            a in query_lower and b in query_lower
            and not any(d in query_lower for d in disambiguations)
        )
        if has_both:
            return ClassifyDecision(
                research=False,
                implement=False,
                reply=True,
                route="clarify",
                task="respond",
                clarification_question=(
                    f"Your request contains potentially conflicting "
                    f"constraints (\"{a}\" and \"{b}\"). Could you clarify "
                    f"which one you want:\n"
                ),
                clarification_options=(
                    f"Focus on \"{a}\" — ignore \"{b}\".",
                    f"Focus on \"{b}\" — ignore \"{a}\".",
                    "Explain how these should work together and I'll try to reconcile them.",
                ),
                plan_summary=(
                    f"Conflicting constraints '{a}'/'{b}' require clarification."
                ),
            )

    # ── 6. Impossible free-tier video requests ──────────────────────────
    # Detect >8K resolution or >5000 frames without a paid tier indicator.
    resolution_match = re.search(
        r'(\d{3,5})\s*[x×]\s*(\d{3,5})', query, re.IGNORECASE
    )
    frames_match = re.search(r'(\d{4,})\s*frames?', query, re.IGNORECASE)
    resolution_too_large = False
    frames_too_many = False

    if resolution_match:
        w = int(resolution_match.group(1))
        h = int(resolution_match.group(2))
        # >8K UHD = any dimension above 7680 or total pixels > ~33M
        if w > 7680 or h > 7680 or (w * h) > 33_177_600:
            resolution_too_large = True

    if frames_match:
        n_frames = int(frames_match.group(1))
        if n_frames > 5000:
            frames_too_many = True

    if resolution_too_large or frames_too_many:
        paid_indicators = (
            "paid", "pro", "premium", "enterprise", "unlimited",
            "priority", "dedicated",
        )
        if not any(pi in query_lower for pi in paid_indicators):
            dimension_desc = (
                f"{resolution_match.group(0)}"
                if resolution_too_large
                else f"{frames_match.group(0)} frames"
            )
            return ClassifyDecision(
                research=False,
                implement=False,
                reply=True,
                route="clarify",
                task="respond",
                clarification_question=(
                    f"Your request targets {dimension_desc}, which exceeds "
                    f"free-tier limits (max 7680×4320 resolution, 5000 frames). "
                    f"Would you like to:\n"
                ),
                clarification_options=(
                    "Reduce resolution/frame count to within free-tier limits.",
                    "Confirm you have a paid/priority tier that supports this scale.",
                    "Split the work into multiple smaller requests.",
                ),
                plan_summary=(
                    "Impossible free-tier video request requires clarification."
                ),
            )

    # ── 7. Incompatible architecture splice requests ────────────────────
    architecture_pairs = [
        (("flux", "sdxl"), "Flux and SDXL"),
        (("flux", "sd1"), "Flux and SD1.x"),
        (("sdxl", "sd3"), "SDXL and SD3"),
        (("ltxv", "wan"), "LTX-Video and Wan"),
    ]
    for (arch_a, arch_b), label in architecture_pairs:
        if arch_a in query_lower and arch_b in query_lower:
            # Check for documented bridge/compatibility indicators.
            bridge_indicators = (
                "bridge", "convert", "adapter", "ipadapter",
                "controlnet", "unified", "dual",
            )
            if not any(bi in query_lower for bi in bridge_indicators):
                return ClassifyDecision(
                    research=False,
                    implement=False,
                    reply=True,
                    route="clarify",
                    task="respond",
                    clarification_question=(
                        f"Your request combines {label} architectures, which "
                        f"use incompatible latent spaces and require a "
                        f"specialized bridge or adapter. Would you like to:\n"
                    ),
                    clarification_options=(
                        f"Use only one architecture ({arch_a} or {arch_b}) for this workflow.",
                        "Confirm you intend to use a specific bridge/adapter and name it.",
                        "Let me research available {label} bridge nodes before proceeding.",
                    ),
                    plan_summary=(
                        f"Incompatible architecture splice ({label}) requires clarification."
                    ),
                )

    # No preclassify blockers detected.
    return None


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
            request.query, hivemind_client=_default_hivemind_client
        )
        inspection = _graph_inspection(request.graph)
        if inspection:
            summary = f"{result.summary}\n\nGraph inspection:\n{inspection}"
            result = ResearchResult(
                summary=summary,
                sources=result.sources,
                warnings=result.warnings,
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

    # Success: extract graph and message.
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

    return ImplementationResult(graph=graph_out, message=message)


# ── reply phase ──────────────────────────────────────────────────────────────


def _run_reply(
    request: ExecutorRequest,
    spec: AgentSpecShape,
    *,
    plan: ClassifyDecision,
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
    graph_summary = _graph_summary(request.graph)

    # For inspect-only, replace the compact graph summary with the detailed
    # inspection evidence so the reply model can describe the workflow
    # step-by-step without suggesting edits.
    effective_graph_context: str | None = graph_summary
    if graph_inspection:
        effective_graph_context = graph_inspection

    try:
        reply_kwargs: dict[str, Any] = {
            "route": spec.agent,
            "model": spec.model,
            "plan": plan,
            "research_summary": research_summary,
            "implementation_message": implementation_message,
            "graph_summary": effective_graph_context,
        }
        try:
            result = run_reply_turn(request.query, **reply_kwargs)
        except TypeError as exc:
            if "graph_summary" not in str(exc):
                raise
            reply_kwargs.pop("graph_summary", None)
            result = run_reply_turn(request.query, **reply_kwargs)
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
    ) -> None:
        super().__init__(message)
        self.stage = stage
        self.failure_kind = failure_kind
        self.failure_envelope = failure_envelope


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
    candidate_graph: dict[str, Any] | None = None
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

    # ── Phase 1: preclassify blockers (M3) ───────────────────────────────
    # Check for obvious unsafe/ambiguous requests before any model call.
    pre_blocker = _preclassify_blockers(request, session_context=session_context)
    if pre_blocker is not None:
        plan = pre_blocker
        profiler_log(
            LOGGER,
            "executor.preclassify_blocked",
            **request_fields,
            plan_route=plan.effective_route,
            plan_task=plan.effective_task,
            blocker_summary=plan.plan_summary,
        )
        _emit_executor_phase_event(
            request,
            executor_id=executor_id,
            phase="classify",
            status="blocked",
            plan=plan,
            client_id=client_id,
        )
        # ── Preserve clarification context for follow-up resolution (M3) ──
        _save_clarification_context(
            request,
            plan,
            blocked_route="revise",
            blocked_task="edit_graph",
        )
        # Skip model classification entirely — proceed directly to reply.
    else:
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
                except _ExecutorPhaseError:
                    # Research failure is non-fatal; capture as empty result.
                    research_result = ResearchResult(
                        summary="Research skipped due to an error.",
                        warnings=("research phase error; continuing",),
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
            candidate_graph = implementation_result.graph
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
                research_result=research_result,
                implementation_result=implementation_result,
                graph_inspection=_graph_inspection(request.graph)
                if route_behavior.reply_uses_graph_inspection
                else None,
            )
            if (
                plan.route == "clarify"
                or plan.clarification_question
                or plan.clarification_options
            ):
                reply_text = _clarify_markdown_reply(plan, reply_text)
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
        candidate_graph = None

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
        result_has_graph=candidate_graph is not None,
        reply_preview=short_text(reply_text),
    )
    return ExecutorResult.success(
        report=report,
        graph=candidate_graph,
        reply=reply_text,
    )


__all__ = ["run_executor"]
