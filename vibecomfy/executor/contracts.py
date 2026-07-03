"""Typed data contracts for the embedded VibeComfy executor.

These are the public shapes that flow through the classify → research →
implement → reply pipeline.  Every contract is a frozen dataclass with a
canonical ``to_dict()`` serializer so the executor can produce the standard
``success_envelope`` shape without adding new top-level response fields.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any, Mapping
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from vibecomfy.agent.deepseek_usage import coerce_deepseek_usage

LOGGER = logging.getLogger(__name__)

_WARNING_DETAIL_MAX_MESSAGE = 160
_SENSITIVE_QUERY_KEYS = frozenset({
    "api_key",
    "apikey",
    "auth",
    "authorization",
    "key",
    "password",
    "secret",
    "sig",
    "signature",
    "token",
})


def _freeze_jsonish(value: Any) -> Any:
    if isinstance(value, Mapping):
        return MappingProxyType({str(k): _freeze_jsonish(v) for k, v in value.items()})
    if isinstance(value, (list, tuple)):
        return tuple(_freeze_jsonish(v) for v in value)
    return value


def _thaw_jsonish(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(k): _thaw_jsonish(v) for k, v in value.items()}
    if isinstance(value, tuple):
        return [_thaw_jsonish(v) for v in value]
    return value


_ADAPTATION_PLAN_FOLLOWUPS: tuple[str, ...] = (
    "apply_bound_current_graph_edit_if_schema_sufficient",
    "build_execution_plan_with_required_nodes_and_rewires",
    "typed_refusal_or_clarification_if_authoring_surface_missing",
)


def _adaptation_plan_field(value: Any, key: str, default: Any = None) -> Any:
    if isinstance(value, Mapping):
        return value.get(key, default)
    return getattr(value, key, default)


def adaptation_plan_actionability(value: Any) -> tuple[str, str]:
    """Return ``("actionable", "")`` or ``("non_actionable", reason)``.

    Validation status alone is not enough. A structurally failed plan with
    concrete edit operations can still describe a current-graph direct edit,
    while a passing or unevaluated plan with no candidate graph, nodes, rewires,
    or edit ops is still only evidence.
    """

    if value is None:
        return "non_actionable", "missing_plan"
    if not isinstance(value, Mapping) and not any(
        hasattr(value, key)
        for key in (
            "candidate_graph",
            "required_new_nodes",
            "required_rewires",
            "edit_ops",
            "structural_validation",
            "semantic_validation",
        )
    ):
        return "non_actionable", "invalid_plan_shape"

    explicit = _adaptation_plan_field(value, "actionability")
    if explicit == "non_actionable":
        reason = _adaptation_plan_field(value, "non_actionable_reason") or "explicitly_non_actionable"
        return "non_actionable", str(reason)

    candidate_graph = _adaptation_plan_field(value, "candidate_graph")
    required_new_nodes = _adaptation_plan_field(value, "required_new_nodes") or ()
    required_rewires = _adaptation_plan_field(value, "required_rewires") or ()
    edit_ops = _adaptation_plan_field(value, "edit_ops") or ()
    if candidate_graph or required_new_nodes or required_rewires or edit_ops:
        return "actionable", ""

    structural = _adaptation_plan_field(value, "structural_validation")
    semantic = _adaptation_plan_field(value, "semantic_validation")
    if structural == "fail":
        return "non_actionable", "structural_validation_failed_without_concrete_edits"
    if semantic == "fail":
        return "non_actionable", "semantic_validation_failed_without_concrete_edits"
    return "non_actionable", "no_concrete_adaptation_edits"


def is_actionable_adaptation_plan(value: Any) -> bool:
    return adaptation_plan_actionability(value)[0] == "actionable"


def adaptation_plan_actionability_payload(value: Any) -> dict[str, Any]:
    actionability, reason = adaptation_plan_actionability(value)
    payload: dict[str, Any] = {"actionability": actionability}
    if actionability != "actionable":
        payload["non_actionable_reason"] = reason
        payload["allowed_followups"] = list(_ADAPTATION_PLAN_FOLLOWUPS)
    return payload


def _safe_exception_message(exc: BaseException) -> str:
    message = " ".join(str(exc).split())
    if not message:
        return ""
    message = re.sub(
        r"https?://[^\s]+",
        lambda match: _sanitize_url_for_warning(match.group(0)),
        message,
    )
    if len(message) > _WARNING_DETAIL_MAX_MESSAGE:
        return message[: _WARNING_DETAIL_MAX_MESSAGE - 3].rstrip() + "..."
    return message


def _sanitize_url_for_warning(raw_url: str) -> str:
    try:
        parsed = urlsplit(raw_url)
    except ValueError:
        return "<url>"
    query_pairs = []
    for key, value in parse_qsl(parsed.query, keep_blank_values=True):
        if key.lower() in _SENSITIVE_QUERY_KEYS:
            query_pairs.append((key, "<redacted>"))
        else:
            query_pairs.append((key, value))
    return urlunsplit((
        parsed.scheme,
        parsed.netloc,
        parsed.path,
        urlencode(query_pairs),
        "",
    ))


def warning_detail_from_exception(exc: BaseException) -> dict[str, str]:
    """Return a compact, JSON-safe exception detail for research warnings."""
    return {
        "type": type(exc).__name__,
        "message": _safe_exception_message(exc),
    }


# ── classify decision ────────────────────────────────────────────────────────

# Canonical route vocabulary (SD1).  Empty string means "no route specified —
# derive from legacy booleans".
_ALLOWED_ROUTES = frozenset({
    "",
    "clarify",
    "respond",
    "inspect",
    "research",
    "requires_custom_nodes",
    "revise",
    "adapt",
    "reorganise",
})

# Normalized task vocabulary carried alongside route.
_ALLOWED_TASKS = frozenset({
    "",
    "edit_graph",
    "inspect_graph",
    "find_assets",
    "diagnose",
    "preview_subgraph",
    "research_precedent",
    "layout_reorganise",
    "respond",
    "research_nodes",
})

_ROUTE_DESCRIPTIONS: dict[str, str] = {
    "clarify": "ask a clarifying question when load-bearing information is missing.",
    "respond": "answer directly from existing context without research or editing.",
    "inspect": "explain or analyze the current graph without outside research or editing.",
    "research": "research workflows, nodes, or techniques, then answer without editing.",
    "requires_custom_nodes": "return that the requested edit cannot be safely authored from current evidence without applying graph changes.",
    "revise": "edit the current graph using local context only.",
    "adapt": "research precedent or workflow patterns, then edit the graph.",
    "reorganise": "reorganise the current canvas layout/readability without changing workflow semantics.",
}

_PUBLIC_ROUTES = frozenset({
    *_ROUTE_DESCRIPTIONS,
    "requires_custom_nodes",
})
_APPLY_ELIGIBLE_ROUTES = frozenset({"revise", "adapt", "reorganise"})
_EVIDENCE_KEYS = frozenset({
    "classification",
    "graph_inspection",
    "research",
    "implementation",
    "warnings",
})
_NO_CANDIDATE_REASONS = frozenset({
    "route_not_applyable",
    "no_graph",
    "implementation_skipped",
    "implementation_failed",
    "no_changes",
    "unknown_route",
})

_TASK_DESCRIPTIONS: dict[str, str] = {
    "edit_graph": "modify the current graph.",
    "inspect_graph": "inspect or explain a graph without editing.",
    "find_assets": "find assets, models, or nodes.",
    "diagnose": "diagnose workflow problems.",
    "preview_subgraph": "preview a subgraph or node group.",
    "research_precedent": "research precedent templates or techniques.",
    "layout_reorganise": "reorganise canvas layout/readability without changing workflow semantics.",
    "respond": "reply without graph actions.",
    "research_nodes": "research nodes or workflow techniques.",
}

if set(_ROUTE_DESCRIPTIONS) != (_ALLOWED_ROUTES - {""}):
    raise ValueError("Route descriptions must cover every non-empty allowed route exactly once.")

if set(_TASK_DESCRIPTIONS) != (_ALLOWED_TASKS - {""}):
    raise ValueError("Task descriptions must cover every non-empty allowed task exactly once.")


def _normalize_explicit_route(
    route: str,
    *,
    research: bool,
    implement: bool,
    intent: str,
    task: str = "",
) -> str:
    """Normalize an explicit classifier route to the public route vocabulary.

    Legacy route names are accepted as input aliases only during the migration
    window. Unknown explicit routes fail closed to ``clarify`` so serialized
    output never exposes blank or legacy route values.
    """
    if not route:
        if task in {
            "layout_reorganise",
            "reorganise_comfy_workflow",
            "reorganize_comfy_workflow",
            "/reorganise_comfy_workflow",
            "/reorganize_comfy_workflow",
        }:
            return "reorganise"
        return ""

    if route == "requires_custom_nodes":
        if implement or intent == "edit" or task in {"edit_graph", "research_precedent"}:
            normalized = "adapt"
        elif research or intent == "research" or task in {"find_assets", "research_nodes"}:
            normalized = "research"
        else:
            normalized = "respond"
        LOGGER.info(
            "executor install-intent route normalized to executable route",
            extra={
                "requested_route": route,
                "normalized_route": normalized,
                "intent": intent,
                "task": task,
            },
        )
        return normalized

    if route in _ALLOWED_ROUTES:
        return route

    static_aliases = {
        "inspect_only": "inspect",
        "direct_edit": "revise",
        "diagnose_repair": "revise",
        "precedent_research": "adapt",
        "layout_reorganise": "reorganise",
        "layout_reorganize": "reorganise",
        "reorganise_workflow": "reorganise",
        "reorganize_workflow": "reorganise",
        "reorganise_comfy_workflow": "reorganise",
        "reorganize_comfy_workflow": "reorganise",
        "/reorganise_comfy_workflow": "reorganise",
        "/reorganize_comfy_workflow": "reorganise",
    }
    if route in static_aliases:
        normalized = static_aliases[route]
        LOGGER.info(
            "executor legacy route alias normalized",
            extra={"legacy_route": route, "normalized_route": normalized},
        )
        return normalized

    if route in {"asset_lookup", "subgraph_preview"}:
        if research and implement:
            normalized = "adapt"
        elif implement:
            normalized = "revise"
        elif research:
            normalized = "research"
        else:
            normalized = "clarify"
        LOGGER.info(
            "executor legacy route alias normalized",
            extra={
                "legacy_route": route,
                "normalized_route": normalized,
                "intent": intent,
                "task": task,
            },
        )
        return normalized

    LOGGER.warning(
        "executor unknown explicit route failed closed",
        extra={"requested_route": route, "normalized_route": "clarify"},
    )
    return "clarify"


def format_route_options_for_prompt() -> str:
    """Return the route options block for the classify system prompt."""
    lines = [
        '  "route": string (optional) — the precise execution route.  Choose from:\n',
    ]
    for route, description in _ROUTE_DESCRIPTIONS.items():
        lines.append(f'    "{route}" — {description}\n')
    lines.append('    Omit or use "" when the legacy booleans are sufficient.\n')
    return "".join(lines)


def format_task_options_for_prompt() -> str:
    """Return the task options block for the classify system prompt."""
    tasks = list(_TASK_DESCRIPTIONS)
    lines = [
        '  "task": string (optional) — normalized task class.  Choose from:\n',
    ]
    for idx in range(0, len(tasks), 4):
        chunk = ", ".join(f'"{task}"' for task in tasks[idx:idx + 4])
        suffix = ",\n" if idx + 4 < len(tasks) else ".\n"
        lines.append(f"    {chunk}{suffix}")
    lines.append('    Omit or use "" when the legacy booleans are sufficient.\n')
    return "".join(lines)


@dataclass(frozen=True)
class ClassifyDecision:
    """Model-driven classification result for an executor request.

    This is always produced by a model call (SD1: no heuristic shortcut).

    **Legacy fields (backward compatible)**
    ``research`` and ``implement`` are booleans that drive whether those phases
    run; ``reply`` is True when the executor should produce a user-facing
    message.  ``intent`` is the legacy coarse classification.

    **Route-aware fields (new, SD1)**
    ``route`` is the authoritative phase-routing label.  When the classifier
    model omits it (or returns an empty string), the parser derives a
    normalized route from the legacy ``research`` / ``implement`` / ``intent``
    fields so downstream executor gates can use route helpers without
    inspecting legacy booleans directly.

    ``task`` is a normalized task-class label (e.g. ``"edit_graph"``,
    ``"inspect_graph"``).  It is derived from legacy fields when absent, and
    defaults to ``""`` (unknown) when derivation is ambiguous.

    ``effort`` is a coarse hint from the model ("low" / "medium" / "high")
    that downstream phases may use to select models or token budgets.
    """

    # ── legacy boolean gates ─────────────────────────────────────────────
    research: bool = False
    implement: bool = False
    reply: bool = True
    effort: str = "low"
    plan_summary: str = ""
    intent: str = "respond"

    # ── route-aware fields (SD1) ─────────────────────────────────────────
    route: str = ""
    task: str = ""

    # ── route-aware metadata (SD1) ─────────────────────────────────────
    research_goal: str = ""
    search_directions: tuple[str, ...] = ()
    source_preferences: tuple[str, ...] = ()
    avoid: tuple[str, ...] = ()
    known_graph_context: str = ""
    model_families: tuple[str, ...] = ()
    pattern_category: str = ""
    change_goal: str = ""
    clarification_question: str = ""
    clarification_options: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.effort not in ("low", "medium", "high"):
            object.__setattr__(self, "effort", "low")

        allowed_intents = {"edit", "research", "explain_graph", "respond"}
        if self.intent not in allowed_intents:
            object.__setattr__(self, "intent", "respond")

        normalized_route = _normalize_explicit_route(
            str(self.route).strip() if isinstance(self.route, str) else "",
            research=self.research,
            implement=self.implement,
            intent=self.intent,
            task=self.task if isinstance(self.task, str) else "",
        )
        object.__setattr__(self, "route", normalized_route)

        # Enforce route/boolean consistency (SD1).  Stale booleans from the
        # classifier are canonicalized to the route's required values so
        # downstream executor gates never see contradictory combinations.
        route_booleans = {
            "clarify": (False, False),
            "respond": (False, False),
            "inspect": (False, False),
            "research": (True, False),
            "revise": (False, True),
            "adapt": (True, True),
            "reorganise": (False, True),
        }
        if self.route in route_booleans:
            expected_research, expected_implement = route_booleans[self.route]
            object.__setattr__(self, "research", expected_research)
            object.__setattr__(self, "implement", expected_implement)

        # Clamp task to allowed values.
        if self.task not in _ALLOWED_TASKS:
            object.__setattr__(self, "task", "")
        if self.route == "reorganise" and self.task != "layout_reorganise":
            object.__setattr__(self, "task", "layout_reorganise")

        # Freeze tuple fields.
        object.__setattr__(self, "search_directions", tuple(self.search_directions))
        object.__setattr__(self, "source_preferences", tuple(self.source_preferences))
        object.__setattr__(self, "avoid", tuple(self.avoid))
        object.__setattr__(self, "model_families", tuple(self.model_families))
        object.__setattr__(self, "clarification_options", tuple(self.clarification_options))

    # ── derived helpers ──────────────────────────────────────────────────

    @property
    def effective_route(self) -> str:
        """Return the normalized route, deriving from legacy fields when empty."""
        if self.route:
            return self.route
        return _derive_route(
            research=self.research,
            implement=self.implement,
            intent=self.intent,
        )

    @property
    def effective_task(self) -> str:
        """Return the normalized task, deriving from legacy fields when empty."""
        if self.task:
            return self.task
        if self.route == "reorganise":
            return "layout_reorganise"
        return _derive_task(
            research=self.research,
            implement=self.implement,
            intent=self.intent,
        )

    # ── serialization ────────────────────────────────────────────────────

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "research": self.research,
            "implement": self.implement,
            "reply": self.reply,
            "effort": self.effort,
            "plan_summary": self.plan_summary,
            "intent": self.intent,
        }
        # Only emit route/task when non-empty so legacy consumers see the
        # same shape they always have.
        if self.route:
            result["route"] = self.route
        if self.task:
            result["task"] = self.task
        # Emit metadata fields only when non-empty.
        if self.research_goal:
            result["research_goal"] = self.research_goal
        if self.search_directions:
            result["search_directions"] = list(self.search_directions)
        if self.source_preferences:
            result["source_preferences"] = list(self.source_preferences)
        if self.avoid:
            result["avoid"] = list(self.avoid)
        if self.known_graph_context:
            result["known_graph_context"] = self.known_graph_context
        if self.model_families:
            result["model_families"] = list(self.model_families)
        if self.pattern_category:
            result["pattern_category"] = self.pattern_category
        if self.change_goal:
            result["change_goal"] = self.change_goal
        if self.clarification_question:
            result["clarification_question"] = self.clarification_question
        if self.clarification_options:
            result["clarification_options"] = list(self.clarification_options)
        return result

    # ── convenience constructors ─────────────────────────────────────────

    @classmethod
    def respond_only(
        cls,
        *,
        effort: str = "low",
        plan_summary: str = "",
        route: str = "",
        task: str = "",
    ) -> "ClassifyDecision":
        """Convenience: classify as a respond-only turn (no research, no edit)."""
        return cls(
            research=False,
            implement=False,
            reply=True,
            effort=effort,
            plan_summary=plan_summary,
            intent="respond",
            route=route,
            task=task,
        )

    @classmethod
    def edit(
        cls,
        *,
        research: bool = True,
        effort: str = "medium",
        plan_summary: str = "",
        route: str = "",
        task: str = "",
    ) -> "ClassifyDecision":
        """Convenience: classify as an edit turn (with research by default)."""
        return cls(
            research=research,
            implement=True,
            reply=True,
            effort=effort,
            plan_summary=plan_summary,
            intent="edit",
            route=route,
            task=task,
        )


# ── route / task derivation (legacy compatibility) ───────────────────────────


def _derive_route(*, research: bool, implement: bool, intent: str) -> str:
    """Derive a normalized route from legacy boolean + intent fields.

    This follows the locked route vocabulary for the no-edit contract repair:
    * revise → implement without research
    * adapt → research + implement (legacy booleans are unambiguous here)
    * research → research without implementation and research intent
    * inspect → explain_graph intent without implementation
    * respond → respond intent without research or implementation
    * clarify → neither research nor implementation when intent is ambiguous
    """
    if implement and research:
        return "adapt"
    if implement and not research:
        return "revise"
    if research and not implement:
        return "research"
    if not research and not implement:
        if intent == "explain_graph":
            return "inspect"
        if intent == "respond":
            return "respond"
        return "clarify"
    return ""


def _derive_task(*, research: bool, implement: bool, intent: str) -> str:
    """Derive a normalized task label from legacy fields.

    Returns ``""`` when the mapping is ambiguous.
    """
    if implement and research:
        return "research_precedent"
    if implement and not research:
        return "edit_graph"
    if research and not implement:
        return "research_nodes"
    if not research and not implement:
        if intent == "explain_graph":
            return "inspect_graph"
        if intent == "respond":
            return "respond"
        return "respond"
    return ""


# ── request ──────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class ExecutorRequest:
    """Public input shape for ``POST /vibecomfy/agent-executor``.

    ``query`` is the only required field.  ``graph`` is the optional current
    canvas (the executor forwards it to ``handle_agent_edit`` through a
    ``{task, query, graph, session_id}`` payload when an implementation turn is
    indicated).
    """

    query: str
    graph: dict[str, Any] | None = None
    session_id: str | None = None
    profile: str | None = None
    idempotency_key: str | None = None

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {"query": self.query}
        if self.graph is not None:
            payload["graph"] = self.graph
        if self.session_id is not None:
            payload["session_id"] = self.session_id
        if self.profile is not None:
            payload["profile"] = self.profile
        if self.idempotency_key is not None:
            payload["idempotency_key"] = self.idempotency_key
        return payload

    @classmethod
    def from_payload(cls, payload: Mapping[str, Any]) -> "ExecutorRequest":
        query = payload.get("query")
        if not isinstance(query, str) or not query.strip():
            raise ValueError("ExecutorRequest requires a non-empty string `query`.")
        graph = payload.get("graph")
        if graph is not None and not isinstance(graph, dict):
            raise ValueError("ExecutorRequest `graph` must be a dict or null.")
        session_id = payload.get("session_id")
        if session_id is not None and not isinstance(session_id, str):
            raise ValueError("ExecutorRequest `session_id` must be a string or null.")
        profile = payload.get("profile")
        if profile is not None and not isinstance(profile, str):
            raise ValueError("ExecutorRequest `profile` must be a string or null.")
        idempotency_key = payload.get("idempotency_key")
        if idempotency_key is not None and not isinstance(idempotency_key, str):
            raise ValueError("ExecutorRequest `idempotency_key` must be a string or null.")
        return cls(
            query=query.strip(),
            graph=graph,
            session_id=session_id,
            profile=profile,
            idempotency_key=idempotency_key,
        )





# ── structured precedent contracts (SD2) ──────────────────────────────────────

@dataclass(frozen=True)
class InspectionSummary:
    """Minimal typed contract for a graph inspection pass.

    Produced by graph-native inspection (``_graph_inspection``) and carried
    alongside research results so downstream phases can reference concrete
    node-level findings without re-parsing the raw graph dict.
    """

    node_count: int = 0
    node_types: tuple[str, ...] = ()
    has_dangling_inputs: bool = False
    has_dangling_outputs: bool = False
    key_widget_values: tuple[dict[str, Any], ...] = ()
    summary: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "node_types", tuple(self.node_types))
        object.__setattr__(self, "key_widget_values", tuple(
            MappingProxyType({str(k): v for k, v in w.items()})
            if isinstance(w, Mapping) else w
            for w in self.key_widget_values
        ))

    def to_dict(self) -> dict[str, Any]:
        return {
            "node_count": self.node_count,
            "node_types": list(self.node_types),
            "has_dangling_inputs": self.has_dangling_inputs,
            "has_dangling_outputs": self.has_dangling_outputs,
            "key_widget_values": _thaw_jsonish(self.key_widget_values),
            "summary": self.summary,
        }


@dataclass(frozen=True)
class WorkflowSlice:
    """Identifies a selected slice of a workflow (precedent or current graph).

    Points at a specific region of a workflow — a contiguous set of nodes and
    their internal wiring — that can be adapted into the current graph.  The
    *entry_anchor* and *exit_anchor* describe where the slice connects to the
    rest of the graph; they are node ids in the source workflow that map to
    node ids in the target graph via anchor bindings.
    """

    source_class_type: str = ""
    node_ids: tuple[str, ...] = ()
    node_types: tuple[str, ...] = ()
    entry_anchor: str | None = None
    exit_anchor: str | None = None
    source_workflow_path: str | None = None
    python_path: str | None = None
    warnings: tuple[dict[str, Any], ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "node_ids", tuple(self.node_ids))
        object.__setattr__(self, "node_types", tuple(self.node_types))
        object.__setattr__(self, "warnings", tuple(
            MappingProxyType({str(k): _freeze_jsonish(v) for k, v in warning.items()})
            if isinstance(warning, Mapping) else warning
            for warning in self.warnings
        ))

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "source_class_type": self.source_class_type,
            "node_ids": list(self.node_ids),
        }
        if self.node_types:
            payload["node_types"] = list(self.node_types)
        if self.entry_anchor is not None:
            payload["entry_anchor"] = self.entry_anchor
        if self.exit_anchor is not None:
            payload["exit_anchor"] = self.exit_anchor
        if self.source_workflow_path is not None:
            payload["source_workflow_path"] = self.source_workflow_path
        if self.python_path is not None:
            payload["python_path"] = self.python_path
        if self.warnings:
            payload["warnings"] = _thaw_jsonish(self.warnings)
        return payload


@dataclass(frozen=True)
class PrecedentAdaptationPlan:
    """Structured plan for adapting a workflow precedent into the current graph.

    This is the typed handoff between precedent research and implementation
    (SD2).  It records exactly which slice was selected, how its anchors bind
    to the current graph, what new nodes/rewires are required, and the concrete
    edit operations needed to produce the candidate graph.

    *structural_validation* and *semantic_validation* capture validation notes
    (may be ``"not_evaluated"`` when validation is deferred to a later sprint).
    """

    selected_slice: WorkflowSlice = field(default_factory=WorkflowSlice)
    anchor_bindings: tuple[dict[str, str], ...] = ()
    required_new_nodes: tuple[dict[str, Any], ...] = ()
    required_rewires: tuple[dict[str, Any], ...] = ()
    edit_ops: tuple[dict[str, Any], ...] = ()
    candidate_graph: dict[str, Any] | None = None
    structural_validation: str = "not_evaluated"
    semantic_validation: str = "not_evaluated"
    warnings: tuple[dict[str, Any], ...] = ()
    # SD1 migration: all available precedent slices preserved as neutral context.
    # The first item (selected_slice) is presentation context only — it is not
    # a winner, recommendation, or required implementation.
    all_slices: tuple[WorkflowSlice, ...] = ()
    context_note: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "anchor_bindings", tuple(
            MappingProxyType({str(k): str(v) for k, v in b.items()})
            if isinstance(b, Mapping) else b
            for b in self.anchor_bindings
        ))
        object.__setattr__(self, "required_new_nodes", tuple(
            MappingProxyType({str(k): _freeze_jsonish(v) for k, v in n.items()})
            if isinstance(n, Mapping) else n
            for n in self.required_new_nodes
        ))
        object.__setattr__(self, "required_rewires", tuple(
            MappingProxyType({str(k): _freeze_jsonish(v) for k, v in r.items()})
            if isinstance(r, Mapping) else r
            for r in self.required_rewires
        ))
        object.__setattr__(self, "edit_ops", tuple(
            MappingProxyType({str(k): _freeze_jsonish(v) for k, v in op.items()})
            if isinstance(op, Mapping) else op
            for op in self.edit_ops
        ))
        object.__setattr__(self, "warnings", tuple(
            MappingProxyType({str(k): _freeze_jsonish(v) for k, v in warning.items()})
            if isinstance(warning, Mapping) else warning
            for warning in self.warnings
        ))
        object.__setattr__(self, "all_slices", tuple(self.all_slices))
        if self.structural_validation not in ("not_evaluated", "pass", "fail", "advisory"):
            object.__setattr__(self, "structural_validation", "not_evaluated")
        if self.semantic_validation not in ("not_evaluated", "pass", "fail", "advisory"):
            object.__setattr__(self, "semantic_validation", "not_evaluated")
        if self.structural_validation != "pass" and self.candidate_graph is not None:
            object.__setattr__(self, "candidate_graph", None)

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            # selected_slice is presentation context only — it is not a winner,
            # recommendation, or required implementation.  See all_slices and
            # context_note for the full neutral precedent context.
            "selected_slice": self.selected_slice.to_dict(),
            "anchor_bindings": _thaw_jsonish(self.anchor_bindings),
            "required_new_nodes": _thaw_jsonish(self.required_new_nodes),
            "required_rewires": _thaw_jsonish(self.required_rewires),
            "edit_ops": _thaw_jsonish(self.edit_ops),
            "structural_validation": self.structural_validation,
            "semantic_validation": self.semantic_validation,
        }
        payload.update(adaptation_plan_actionability_payload(self))
        if self.warnings:
            payload["warnings"] = _thaw_jsonish(self.warnings)
        if self.structural_validation == "pass" and self.candidate_graph is not None:
            payload["candidate_graph"] = self.candidate_graph
        if self.all_slices:
            payload["all_slices"] = [s.to_dict() for s in self.all_slices]
        if self.context_note:
            payload["context_note"] = self.context_note
        return payload

# ── neutral precedent packet (SD1 successor) ──────────────────────────────────


@dataclass(frozen=True)
class PrecedentOption:
    """Neutral representation of a single precedent workflow slice.

    Describes one discovered workflow slice without asserting any ranking,
    selection preference, or winner.  The packet consumer (not this type)
    decides which option to act on.

    All keys emitted by ``to_dict()`` are descriptive/contextual only —
    forbidden public-key names (``winner``, ``best``, ``selected``,
    ``score``, ``rank``, ``primary``, ``preferred``, ``chosen``, ``pick``,
    ``choice``, ``top``, ``recommended``) are never present in the
    serialized payload.
    """

    source_class_type: str = ""
    source_workflow_path: str | None = None
    node_ids: tuple[str, ...] = ()
    node_types: tuple[str, ...] = ()
    description: str = ""
    notes: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "node_ids", tuple(self.node_ids))
        object.__setattr__(self, "node_types", tuple(self.node_types))
        object.__setattr__(self, "notes", tuple(self.notes))

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "source_class_type": self.source_class_type,
            "description": self.description,
        }
        if self.source_workflow_path is not None:
            payload["source_workflow_path"] = self.source_workflow_path
        if self.node_ids:
            payload["node_ids"] = list(self.node_ids)
        if self.node_types:
            payload["node_types"] = list(self.node_types)
        if self.notes:
            payload["notes"] = list(self.notes)
        return payload


@dataclass(frozen=True)
class PrecedentPacket:
    """Neutral packet of precedent options for adaptation.

    Carries every discovered precedent option without selecting a winner.
    The ``options`` tuple is intentionally unordered and carries no score
    or ranking metadata.  This is the neutral successor to
    ``PrecedentAdaptationPlan`` — the old plan carries a single selected
    slice while the packet preserves every option for the downstream
    consumer.

    Forbidden public-key names are absent from serialized output (see
    ``PrecedentOption`` for the full list).
    """

    options: tuple[PrecedentOption, ...] = ()
    context_note: str = ""
    warnings: tuple[dict[str, Any], ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "options", tuple(self.options))
        object.__setattr__(self, "warnings", tuple(
            MappingProxyType({str(k): _freeze_jsonish(v) for k, v in w.items()})
            if isinstance(w, Mapping) else w
            for w in self.warnings
        ))

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "options": [opt.to_dict() for opt in self.options],
        }
        if self.context_note:
            payload["context_note"] = self.context_note
        if self.warnings:
            payload["warnings"] = _thaw_jsonish(self.warnings)
        return payload


@dataclass(frozen=True)
class SelectedPrecedent:
    """Research-grounded workflow interpretation for edit-by-precedent.

    Unlike :class:`PrecedentPacket`, this is intentionally directive: it records
    the workflow pattern research found to be compatible enough to ground the
    later authoring/resolution step.  It is still evidence, not an applied edit.
    """

    name: str = ""
    source: str = ""
    source_workflow_path: str | None = None
    match_reasons: tuple[str, ...] = ()
    requested_terms: tuple[str, ...] = ()
    model_families: tuple[str, ...] = ()
    implementation_ecosystems: tuple[str, ...] = ()
    models: tuple[str, ...] = ()
    minimal_spine: tuple[str, ...] = ()
    terminal_output_path: tuple[str, ...] = ()
    promotion_gates: Mapping[str, Any] = field(default_factory=dict)
    interpretation_notes: tuple[str, ...] = ()
    avoid_searches: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "match_reasons",
            tuple(str(v) for v in self.match_reasons if str(v).strip()),
        )
        object.__setattr__(
            self,
            "requested_terms",
            tuple(str(v) for v in self.requested_terms if str(v).strip()),
        )
        object.__setattr__(
            self,
            "model_families",
            tuple(str(v) for v in self.model_families if str(v).strip()),
        )
        object.__setattr__(
            self,
            "implementation_ecosystems",
            tuple(str(v) for v in self.implementation_ecosystems if str(v).strip()),
        )
        object.__setattr__(
            self,
            "models",
            tuple(str(v) for v in self.models if str(v).strip()),
        )
        object.__setattr__(
            self,
            "minimal_spine",
            tuple(str(v) for v in self.minimal_spine if str(v).strip()),
        )
        object.__setattr__(
            self,
            "terminal_output_path",
            tuple(str(v) for v in self.terminal_output_path if str(v).strip()),
        )
        object.__setattr__(self, "promotion_gates", MappingProxyType({
            str(k): _freeze_jsonish(v)
            for k, v in self.promotion_gates.items()
        }))
        object.__setattr__(
            self,
            "interpretation_notes",
            tuple(str(v) for v in self.interpretation_notes if str(v).strip()),
        )
        object.__setattr__(
            self,
            "avoid_searches",
            tuple(str(v) for v in self.avoid_searches if str(v).strip()),
        )

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "name": self.name,
            "source": self.source,
        }
        if self.source_workflow_path:
            payload["source_workflow_path"] = self.source_workflow_path
        if self.match_reasons:
            payload["match_reasons"] = list(self.match_reasons)
        if self.requested_terms:
            payload["requested_terms"] = list(self.requested_terms)
        if self.model_families:
            payload["model_families"] = list(self.model_families)
        if self.implementation_ecosystems:
            payload["implementation_ecosystems"] = list(self.implementation_ecosystems)
        if self.models:
            payload["models"] = list(self.models)
        if self.minimal_spine:
            payload["minimal_spine"] = list(self.minimal_spine)
        if self.terminal_output_path:
            payload["terminal_output_path"] = list(self.terminal_output_path)
        if self.promotion_gates:
            payload["promotion_gates"] = _thaw_jsonish(self.promotion_gates)
        if self.interpretation_notes:
            payload["interpretation_notes"] = list(self.interpretation_notes)
        if self.avoid_searches:
            payload["avoid_searches"] = list(self.avoid_searches)
        return payload


# ── revision evidence contracts (M3) ──────────────────────────────────────────


@dataclass(frozen=True)
class TopologyFindings:
    """Deterministic LiteGraph topology findings collected before repair.

    Captures structural issues in the current graph, including disconnected
    edges, missing endpoint nodes, and schema-backed missing required inputs.
    When ``schema_available`` is False, schema-dependent checks degrade
    gracefully rather than guessing.

    All fields default to safe/empty values so evidence can always be emitted,
    even when no graph is present or schema/object_info is unavailable.
    """

    missing_graph: bool = False
    dangling_links: tuple[str, ...] = ()
    absent_endpoint_nodes: tuple[str, ...] = ()
    socket_type_mismatches: tuple[dict[str, Any], ...] = ()
    unknown_class_types: tuple[str, ...] = ()
    missing_required_inputs: tuple[dict[str, Any], ...] = ()
    schema_available: bool = True
    summary: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "dangling_links", tuple(self.dangling_links))
        object.__setattr__(self, "absent_endpoint_nodes", tuple(self.absent_endpoint_nodes))
        object.__setattr__(self, "socket_type_mismatches", tuple(
            MappingProxyType({str(k): _freeze_jsonish(v) for k, v in item.items()})
            if isinstance(item, Mapping) else item
            for item in self.socket_type_mismatches
        ))
        object.__setattr__(self, "unknown_class_types", tuple(self.unknown_class_types))
        object.__setattr__(self, "missing_required_inputs", tuple(
            MappingProxyType({str(k): _freeze_jsonish(v) for k, v in item.items()})
            if isinstance(item, Mapping) else item
            for item in self.missing_required_inputs
        ))

    @property
    def has_blockers(self) -> bool:
        """True when any topology problem was found."""
        return bool(
            self.missing_graph
            or self.dangling_links
            or self.absent_endpoint_nodes
            or self.socket_type_mismatches
            or self.unknown_class_types
            or self.missing_required_inputs
        )

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "missing_graph": self.missing_graph,
            "dangling_links": list(self.dangling_links),
            "absent_endpoint_nodes": list(self.absent_endpoint_nodes),
            "socket_type_mismatches": _thaw_jsonish(self.socket_type_mismatches),
            "unknown_class_types": list(self.unknown_class_types),
            "missing_required_inputs": _thaw_jsonish(self.missing_required_inputs),
            "schema_available": self.schema_available,
            "summary": self.summary,
        }
        payload["has_blockers"] = self.has_blockers
        return payload


@dataclass(frozen=True)
class ReadinessReport:
    """Deterministic readiness / execution-honesty findings.

    Captures missing models, missing node packs, validation errors, and
    no-GPU conditions.  All fields default to empty/safe values so a
    report can be emitted regardless of schema/object_info availability.

    ``object_info_available`` distinguishes schema-backed findings from
    degraded best-effort checks.
    """

    missing_models: tuple[str, ...] = ()
    missing_node_packs: tuple[str, ...] = ()
    validation_errors: tuple[str, ...] = ()
    no_gpu_detected: bool = False
    readiness_blockers: tuple[str, ...] = ()
    object_info_available: bool = True
    summary: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "missing_models", tuple(self.missing_models))
        object.__setattr__(self, "missing_node_packs", tuple(self.missing_node_packs))
        object.__setattr__(self, "validation_errors", tuple(self.validation_errors))
        object.__setattr__(self, "readiness_blockers", tuple(self.readiness_blockers))

    @property
    def has_blockers(self) -> bool:
        """True when any readiness/runtime problem was found.

        ``missing_models`` and ``missing_node_packs`` are still recorded and
        reported (advisory) but are deliberately NOT blockers. A graph is edited
        as a spec, and the assets it references are often not installed on the
        editing machine (downloaded workflows, or a user asking the agent to
        swap in a different model/custom node). Asset availability is a runtime
        concern, not an edit-correctness concern, so it must not prevent
        producing or applying an edit candidate. ``validation_errors``,
        ``no_gpu_detected`` and explicit ``readiness_blockers`` remain blockers.
        """
        return bool(
            self.validation_errors
            or self.no_gpu_detected
            or self.readiness_blockers
        )

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "missing_models": list(self.missing_models),
            "missing_node_packs": list(self.missing_node_packs),
            "validation_errors": list(self.validation_errors),
            "no_gpu_detected": self.no_gpu_detected,
            "readiness_blockers": list(self.readiness_blockers),
            "object_info_available": self.object_info_available,
            "summary": self.summary,
        }
        payload["has_blockers"] = self.has_blockers
        return payload


@dataclass(frozen=True)
class ScopedDiff:
    """Stable scoped diff between an original graph and a candidate graph.

    Computes changed/added/removed/untouched node ids, link summaries,
    before/after hashes, and stable dot paths to changed fields.

    ``candidate_eligible`` is False when the diff is empty, too broad,
    evidence is missing, or unresolved blockers remain.
    """

    changed_nodes: tuple[str, ...] = ()
    added_nodes: tuple[str, ...] = ()
    removed_nodes: tuple[str, ...] = ()
    untouched_nodes: tuple[str, ...] = ()
    changed_links: tuple[str, ...] = ()
    added_links: tuple[dict[str, Any], ...] = ()
    removed_links: tuple[dict[str, Any], ...] = ()
    diff_paths: tuple[str, ...] = ()
    target_node_ids: tuple[str, ...] = ()
    target_matched: bool = True
    before_hash: str = ""
    after_hash: str = ""
    candidate_eligible: bool = False
    eligibility_blockers: tuple[str, ...] = ()
    summary: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "changed_nodes", tuple(self.changed_nodes))
        object.__setattr__(self, "added_nodes", tuple(self.added_nodes))
        object.__setattr__(self, "removed_nodes", tuple(self.removed_nodes))
        object.__setattr__(self, "untouched_nodes", tuple(self.untouched_nodes))
        object.__setattr__(self, "changed_links", tuple(self.changed_links))
        object.__setattr__(self, "added_links", tuple(
            MappingProxyType({str(k): _freeze_jsonish(v) for k, v in link.items()})
            if isinstance(link, Mapping) else link
            for link in self.added_links
        ))
        object.__setattr__(self, "removed_links", tuple(
            MappingProxyType({str(k): _freeze_jsonish(v) for k, v in link.items()})
            if isinstance(link, Mapping) else link
            for link in self.removed_links
        ))
        object.__setattr__(self, "diff_paths", tuple(self.diff_paths))
        object.__setattr__(self, "target_node_ids", tuple(str(node_id) for node_id in self.target_node_ids))
        object.__setattr__(self, "eligibility_blockers", tuple(self.eligibility_blockers))

    @property
    def has_diff(self) -> bool:
        """True when any concrete change was detected between graphs."""
        return bool(
            self.changed_nodes
            or self.added_nodes
            or self.removed_nodes
            or self.changed_links
            or self.added_links
            or self.removed_links
            or self.diff_paths
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "changed_nodes": list(self.changed_nodes),
            "added_nodes": list(self.added_nodes),
            "removed_nodes": list(self.removed_nodes),
            "untouched_nodes": list(self.untouched_nodes),
            "changed_links": list(self.changed_links),
            "added_links": _thaw_jsonish(self.added_links),
            "removed_links": _thaw_jsonish(self.removed_links),
            "diff_paths": list(self.diff_paths),
            "target_node_ids": list(self.target_node_ids),
            "target_matched": self.target_matched,
            "before_hash": self.before_hash,
            "after_hash": self.after_hash,
            "candidate_eligible": self.candidate_eligible,
            "eligibility_blockers": list(self.eligibility_blockers),
            "has_diff": self.has_diff,
            "summary": self.summary,
        }


@dataclass(frozen=True)
class RevisionEvidence:
    """Canonical revision evidence artifact collected before LLM repair.

    Aggregates topology findings, readiness findings, and (after repair)
    a scoped diff.  When no safe candidate is possible, ``no_candidate_reason``
    and ``candidate_eligible=False`` record the reason.

    This is the primary evidence contract for the ``revise`` route — it is
    always produced deterministically before the first model repair prompt.
    """

    topology: TopologyFindings = field(default_factory=TopologyFindings)
    readiness: ReadinessReport = field(default_factory=ReadinessReport)
    scoped_diff: ScopedDiff | None = None
    no_candidate_reason: str | None = None
    candidate_eligible: bool = False
    warnings: tuple[str | dict[str, Any], ...] = ()
    summary: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "warnings", tuple(str(w) for w in self.warnings))
        # Clamp no_candidate_reason to allowed values.
        reason = self.no_candidate_reason
        if reason is not None and reason not in _NO_CANDIDATE_REASONS:
            object.__setattr__(self, "no_candidate_reason", "no_changes")

    @property
    def safe_candidate_possible(self) -> bool:
        """True when no deterministic blockers exist and a candidate could be attempted.

        This is the pre-repair gate: topology and readiness are clean enough
        that the LLM may attempt a scoped repair.
        """
        return (
            not (
                self.topology.missing_graph
                or self.topology.dangling_links
                or self.topology.absent_endpoint_nodes
                or self.topology.missing_required_inputs
            )
            and self.topology.schema_available is not False
            and not self.readiness.has_blockers
        )

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "topology": self.topology.to_dict(),
            "readiness": self.readiness.to_dict(),
            "candidate_eligible": self.candidate_eligible,
            "warnings": list(self.warnings),
            "summary": self.summary,
            "safe_candidate_possible": self.safe_candidate_possible,
        }
        if self.scoped_diff is not None:
            payload["scoped_diff"] = self.scoped_diff.to_dict()
        if self.no_candidate_reason is not None:
            payload["no_candidate_reason"] = self.no_candidate_reason
        return payload


# ── graph facts projection (SD2) ──────────────────────────────────────────────


@dataclass(frozen=True)
class GraphFacts:
    """Compact projection of graph facts from topology and readiness collectors.

    Reuses existing ``TopologyFindings`` and ``ReadinessReport`` collectors
    rather than defining an independent collection schema.  Provides a
    flattened projection suitable for adapt-prompt construction without
    exposing full revision-evidence internals.

    All fields default to safe/empty values so facts can always be emitted.
    """

    current_output_node_types: tuple[str, ...] = ()
    terminal_output_socket_types: tuple[str, ...] = ()
    socket_type_mismatches: tuple[dict[str, Any], ...] = ()
    missing_required_inputs: tuple[dict[str, Any], ...] = ()
    unknown_class_types: tuple[str, ...] = ()
    missing_models: tuple[str, ...] = ()
    missing_node_packs: tuple[str, ...] = ()
    readiness_blockers: tuple[str, ...] = ()
    has_dangling_inputs: bool = False
    has_dangling_outputs: bool = False
    no_gpu_detected: bool = False
    summary: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "current_output_node_types",
                           tuple(self.current_output_node_types))
        object.__setattr__(self, "terminal_output_socket_types",
                           tuple(self.terminal_output_socket_types))
        object.__setattr__(self, "socket_type_mismatches", tuple(
            MappingProxyType({str(k): _freeze_jsonish(v) for k, v in item.items()})
            if isinstance(item, Mapping) else item
            for item in self.socket_type_mismatches
        ))
        object.__setattr__(self, "missing_required_inputs", tuple(
            MappingProxyType({str(k): _freeze_jsonish(v) for k, v in item.items()})
            if isinstance(item, Mapping) else item
            for item in self.missing_required_inputs
        ))
        object.__setattr__(self, "unknown_class_types",
                           tuple(self.unknown_class_types))
        object.__setattr__(self, "missing_models",
                           tuple(self.missing_models))
        object.__setattr__(self, "missing_node_packs",
                           tuple(self.missing_node_packs))
        object.__setattr__(self, "readiness_blockers",
                           tuple(self.readiness_blockers))

    @classmethod
    def from_collectors(
        cls,
        topology: TopologyFindings | None = None,
        readiness: ReadinessReport | None = None,
    ) -> "GraphFacts":
        """Project GraphFacts from existing topology and readiness collectors.

        Returns a compact projection that reuses collector outputs rather
        than collecting new independent facts.  When a collector is None
        its defaults are used.
        """
        if topology is None:
            topology = TopologyFindings()
        if readiness is None:
            readiness = ReadinessReport()
        return cls(
            socket_type_mismatches=topology.socket_type_mismatches,
            missing_required_inputs=topology.missing_required_inputs,
            unknown_class_types=topology.unknown_class_types,
            missing_models=readiness.missing_models,
            missing_node_packs=readiness.missing_node_packs,
            readiness_blockers=readiness.readiness_blockers,
            no_gpu_detected=readiness.no_gpu_detected,
        )

    @property
    def has_blockers(self) -> bool:
        """True when any graph-fact problem was found."""
        return bool(
            self.socket_type_mismatches
            or self.missing_required_inputs
            or self.unknown_class_types
            or self.missing_models
            or self.missing_node_packs
            or self.readiness_blockers
            or self.no_gpu_detected
        )

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "current_output_node_types": list(self.current_output_node_types),
            "terminal_output_socket_types": list(self.terminal_output_socket_types),
            "socket_type_mismatches": _thaw_jsonish(self.socket_type_mismatches),
            "missing_required_inputs": _thaw_jsonish(self.missing_required_inputs),
            "unknown_class_types": list(self.unknown_class_types),
            "missing_models": list(self.missing_models),
            "missing_node_packs": list(self.missing_node_packs),
            "readiness_blockers": list(self.readiness_blockers),
            "has_dangling_inputs": self.has_dangling_inputs,
            "has_dangling_outputs": self.has_dangling_outputs,
            "no_gpu_detected": self.no_gpu_detected,
            "summary": self.summary,
        }
        payload["has_blockers"] = self.has_blockers
        return payload


# ── research result ──────────────────────────────────────────────────────────


@dataclass(frozen=True)
class ResearchResult:
    """Aggregated research output from local corpus + optional Hivemind.

    ``sources`` is a bounded, score-ordered list of source references.
    ``warnings`` captures non-fatal problems (e.g. Hivemind timeout) so the
    executor can still proceed with local-only results.
    """

    summary: str = ""
    sources: tuple[dict[str, Any], ...] = ()
    warnings: tuple[str, ...] = ()
    warning_details: tuple[dict[str, Any], ...] = ()

    # ── structured precedent fields (SD2, optional) ──────────────────
    precedent_slices: tuple[WorkflowSlice, ...] = ()
    adaptation_plan: PrecedentAdaptationPlan | None = None
    # SD1: neutral precedent packet carrying all discovered options without
    # ranking or winner selection.
    precedent_packet: PrecedentPacket | None = None
    # Execute-facing source subset after precedent compatibility gates. The
    # full `sources` tuple remains the audit trail.
    precedent_sources: tuple[dict[str, Any], ...] = ()
    workflow_precedent_status: str = ""
    selected_precedent: SelectedPrecedent | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "sources", tuple(self.sources))
        object.__setattr__(self, "warnings", tuple(
            MappingProxyType({str(k): _freeze_jsonish(v) for k, v in warning.items()})
            if isinstance(warning, Mapping) else str(warning)
            for warning in self.warnings
        ))
        object.__setattr__(self, "warning_details", tuple(
            MappingProxyType({str(k): _freeze_jsonish(v) for k, v in detail.items()})
            for detail in self.warning_details
            if isinstance(detail, Mapping)
        ))
        object.__setattr__(self, "precedent_slices", tuple(self.precedent_slices))
        object.__setattr__(self, "precedent_sources", tuple(self.precedent_sources))

    def to_dict(self) -> dict[str, Any]:
        result = {
            "summary": self.summary,
            "sources": _thaw_jsonish(self.sources),
            "warnings": _thaw_jsonish(self.warnings),
        }
        if self.warning_details:
            result["warning_details"] = _thaw_jsonish(self.warning_details)
        if self.precedent_slices:
            result["precedent_slices"] = [s.to_dict() for s in self.precedent_slices]
        if self.adaptation_plan is not None:
            result["adaptation_plan"] = self.adaptation_plan.to_dict()
        if self.precedent_packet is not None:
            result["precedent_packet"] = self.precedent_packet.to_dict()
        if self.precedent_sources:
            result["precedent_sources"] = _thaw_jsonish(self.precedent_sources)
        if self.workflow_precedent_status:
            result["workflow_precedent_status"] = self.workflow_precedent_status
        if self.selected_precedent is not None:
            result["selected_precedent"] = self.selected_precedent.to_dict()
        return result


# ── implementation result ────────────────────────────────────────────────────


@dataclass(frozen=True)
class ImplementationResult:
    """Output from the implement phase (graph edit or delta).

    Exactly one of ``graph`` or ``delta`` is populated.  ``message`` is the
    agent-facing explanation (carried into the reply phase for context).

    ``durable_response`` carries the full validated response dict from
    ``handle_agent_edit`` (SD1).  It preserves ``session_id``, ``turn_id``,
    and other durable metadata so downstream serialization can attach them
    to applyable candidates (SD2).
    """

    graph: dict[str, Any] | None = None
    delta: tuple[dict[str, Any], ...] = ()
    message: str = ""
    durable_response: dict[str, Any] | None = None
    diagnostics: dict[str, Any] | None = None
    failure: dict[str, Any] | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "delta", tuple(self.delta))
        if self.durable_response is not None:
            object.__setattr__(
                self,
                "durable_response",
                MappingProxyType({
                    str(k): _freeze_jsonish(v)
                    for k, v in self.durable_response.items()
                }),
            )
        if self.diagnostics is not None:
            object.__setattr__(
                self,
                "diagnostics",
                MappingProxyType({
                    str(k): _freeze_jsonish(v)
                    for k, v in self.diagnostics.items()
                }),
            )
        if self.failure is not None:
            object.__setattr__(
                self,
                "failure",
                MappingProxyType({
                    str(k): _freeze_jsonish(v)
                    for k, v in self.failure.items()
                }),
            )

    @property
    def durable_session_id(self) -> str | None:
        """Return the session_id from the durable response, if present."""
        dr = self.durable_response
        if dr is None:
            return None
        sid = dr.get("session_id")
        return sid if isinstance(sid, str) and sid.strip() else None

    @property
    def durable_turn_id(self) -> str | None:
        """Return the turn_id from the durable response, if present."""
        dr = self.durable_response
        if dr is None:
            return None
        tid = dr.get("turn_id")
        return tid if isinstance(tid, str) and tid.strip() else None

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {"message": self.message}
        if self.graph is not None:
            payload["graph"] = self.graph
        if self.delta:
            payload["delta"] = _thaw_jsonish(self.delta)
        if self.diagnostics is not None:
            payload["diagnostics"] = _thaw_jsonish(self.diagnostics)
        if self.failure is not None:
            payload["failure"] = _thaw_jsonish(self.failure)
            diagnostics = self.failure.get("diagnostics")
            if diagnostics is not None:
                payload["diagnostics"] = _thaw_jsonish(diagnostics)
        # Durable metadata is internal; only exposed through the
        # candidate payload in AgentTurnResult, not here.
        return payload


# ── report (nested executor metadata) ────────────────────────────────────────


@dataclass(frozen=True)
class Report:
    """Executor metadata nested under ``report`` in the final envelope.

    Every phase's output is captured here so the envelope stays a stable
    ``{message, outcome, candidate, eligibility, report}`` shape without
    new top-level fields.
    """

    plan: ClassifyDecision = field(default_factory=ClassifyDecision)
    research: ResearchResult | None = None
    implementation: ImplementationResult | None = None
    deepseek_usage: dict[str, Any] = field(default_factory=dict)
    deepseek_est_cost_usd: float | None = None
    deepseek_cost_basis: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "deepseek_usage",
            MappingProxyType({
                str(k): _freeze_jsonish(v)
                for k, v in coerce_deepseek_usage(self.deepseek_usage).items()
            }),
        )

    def to_dict(self) -> dict[str, Any]:
        plan_payload = self.plan.to_dict()
        route = _public_route_for_plan(self.plan)
        plan_payload["route"] = route
        task = self.plan.effective_task
        if task:
            plan_payload["task"] = task
        inner: dict[str, Any] = {"plan": plan_payload}
        if self.research is not None:
            inner["research"] = self.research.to_dict()
        if self.implementation is not None:
            inner["implementation"] = self.implementation.to_dict()
        usage_payload = coerce_deepseek_usage(self.deepseek_usage)
        inner["deepseek_usage"] = usage_payload
        if self.deepseek_est_cost_usd is not None:
            inner["deepseek_est_cost_usd"] = float(self.deepseek_est_cost_usd)
        if isinstance(self.deepseek_cost_basis, str) and self.deepseek_cost_basis:
            inner["deepseek_cost_basis"] = self.deepseek_cost_basis
        return {"executor": inner}


# ── canonical turn envelope ──────────────────────────────────────────────────


def _public_route_for_plan(plan: ClassifyDecision) -> str:
    route = plan.effective_route
    if route in _PUBLIC_ROUTES:
        return route
    if plan.implement and plan.research:
        return "adapt"
    if plan.implement:
        return "revise"
    if plan.research:
        return "research"
    return "respond"


@dataclass(frozen=True)
class AgentEvidence:
    """Bounded evidence object for public executor turn responses."""

    classification: dict[str, Any] = field(default_factory=dict)
    graph_inspection: dict[str, Any] = field(default_factory=dict)
    research: dict[str, Any] = field(default_factory=dict)
    implementation: dict[str, Any] = field(default_factory=dict)
    warnings: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "classification", MappingProxyType({
            str(k): _freeze_jsonish(v) for k, v in self.classification.items()
        }))
        object.__setattr__(self, "graph_inspection", MappingProxyType({
            str(k): _freeze_jsonish(v) for k, v in self.graph_inspection.items()
        }))
        object.__setattr__(self, "research", MappingProxyType({
            str(k): _freeze_jsonish(v) for k, v in self.research.items()
        }))
        object.__setattr__(self, "implementation", MappingProxyType({
            str(k): _freeze_jsonish(v) for k, v in self.implementation.items()
        }))
        object.__setattr__(self, "warnings", tuple(str(w) for w in self.warnings))

    def to_dict(self) -> dict[str, Any]:
        payload = {
            "classification": _thaw_jsonish(self.classification),
            "graph_inspection": _thaw_jsonish(self.graph_inspection),
            "research": _thaw_jsonish(self.research),
            "implementation": _thaw_jsonish(self.implementation),
            "warnings": list(self.warnings),
        }
        extra_keys = set(payload) - _EVIDENCE_KEYS
        if extra_keys:
            raise ValueError(f"Unexpected evidence keys: {sorted(extra_keys)}")
        return payload


@dataclass(frozen=True)
class AgentTurnResult:
    """Canonical public response envelope for one executor turn.

    ``disposition`` is internal execution metadata. It is intentionally omitted
    from serialization so public ``route`` remains the only route vocabulary
    consumers see.
    """

    route: str
    reply: str
    evidence: AgentEvidence = field(default_factory=AgentEvidence)
    candidate: dict[str, Any] | None = None
    no_candidate_reason: str | None = None
    disposition: str = ""

    def __post_init__(self) -> None:
        route = self.route if self.route in _PUBLIC_ROUTES else "respond"
        object.__setattr__(self, "route", route)

        candidate = self.candidate
        if candidate is not None:
            object.__setattr__(self, "candidate", MappingProxyType({
                str(k): _freeze_jsonish(v) for k, v in candidate.items()
            }))
            object.__setattr__(self, "no_candidate_reason", None)
        else:
            reason = self.no_candidate_reason or "no_changes"
            if reason not in _NO_CANDIDATE_REASONS:
                reason = "no_changes"
            object.__setattr__(self, "no_candidate_reason", reason)

        object.__setattr__(self, "disposition", str(self.disposition or ""))

    @property
    def apply_eligible(self) -> bool:
        return self.route in _APPLY_ELIGIBLE_ROUTES and self.candidate is not None

    def to_dict(self) -> dict[str, Any]:
        return {
            "route": self.route,
            "reply": self.reply,
            "evidence": self.evidence.to_dict(),
            "candidate": _thaw_jsonish(self.candidate) if self.candidate is not None else None,
            "apply_eligible": self.apply_eligible,
            "no_candidate_reason": self.no_candidate_reason,
        }

    @classmethod
    def from_executor_result(cls, result: "ExecutorResult") -> "AgentTurnResult":
        plan = result.report.plan
        route = _public_route_for_plan(plan)
        reply = result.reply or result.failure_message or ""
        warnings: list[str] = []

        classification = {
            "route": route,
            "task": plan.effective_task,
            "intent": plan.intent,
            "plan_summary": plan.plan_summary,
        }
        if plan.route and plan.route != route:
            classification["disposition"] = plan.route

        graph_inspection: dict[str, Any] = {}
        if route == "inspect":
            graph_inspection["used_for_reply"] = True

        research: dict[str, Any] = {}
        if result.report.research is not None:
            research = result.report.research.to_dict()
            warnings.extend(result.report.research.warnings)

        implementation: dict[str, Any] = {}
        if result.report.implementation is not None:
            implementation = result.report.implementation.to_dict()

        if result.failure_message:
            warnings.append(result.failure_message)

        candidate: dict[str, Any] | None = None
        if route in _APPLY_ELIGIBLE_ROUTES and result.graph is not None:
            candidate = {"graph": result.graph}
            # Attach durable metadata (SD2: applyable == durable).
            impl = result.report.implementation
            if impl is not None:
                sid = impl.durable_session_id
                tid = impl.durable_turn_id
                if sid is not None:
                    candidate["session_id"] = sid
                if tid is not None:
                    candidate["turn_id"] = tid
        reason = _derive_no_candidate_reason(
            route=route,
            result=result,
            implementation=implementation,
        )
        return cls(
            route=route,
            reply=reply,
            evidence=AgentEvidence(
                classification=classification,
                graph_inspection=graph_inspection,
                research=research,
                implementation=implementation,
                warnings=tuple(warnings),
            ),
            candidate=candidate,
            no_candidate_reason=reason,
            disposition=plan.route or plan.effective_route,
        )


def _derive_no_candidate_reason(
    *,
    route: str,
    result: "ExecutorResult",
    implementation: Mapping[str, Any],
) -> str | None:
    if route not in _APPLY_ELIGIBLE_ROUTES:
        return "route_not_applyable"
    if result.graph is not None:
        return None
    if result.failure_stage == "implement":
        return "implementation_failed"
    if result.failure_kind is not None:
        return "implementation_failed"
    if result.report.implementation is None:
        return "implementation_skipped"
    if implementation and implementation.get("graph") is None:
        return "no_changes"
    return "no_graph"


# ── executor result (final envelope leaf) ────────────────────────────────────

# Keys from the durable handle_agent_edit response that the executor propagates
# to the top-level serialized envelope (SD1, SD2).  Executor-owned fields
# (graph, message, route, candidate, apply_eligible) always take priority.
_DURABLE_ENVELOPE_TOP_LEVEL_KEYS: tuple[str, ...] = (
    "session_id",
    "turn_id",
    "baseline_turn_id",
    "baseline_graph_hash",
    "submit_graph_hash",
    "submit_structural_graph_hash",
    "submitted_client_graph_hash",
    "submitted_client_structural_graph_hash",
    "candidate_graph_hash",
    "candidate_structural_graph_hash",
    "outcome",
    "apply_eligibility",
    "graph_unchanged",
    "no_candidate_reason",
    "change_details",
    "audit_ref",
    "artifacts",
    "gates",
    "debug",
    "contract_version",
)


@dataclass(frozen=True)
class ExecutorResult:
    """Final executor output.

    ``ok`` mirrors the existing success/failure convention.  ``report`` carries
    plan + phase outputs.  ``graph`` is the (optionally edited) canvas.
    ``reply`` is the user-facing prose produced by the reply phase.
    """

    ok: bool = True
    report: Report = field(default_factory=Report)
    graph: dict[str, Any] | None = None
    reply: str | None = None
    failure_kind: str | None = None
    failure_stage: str | None = None
    failure_message: str | None = None

    @property
    def turn(self) -> AgentTurnResult:
        return AgentTurnResult.from_executor_result(self)

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "ok": self.ok,
            "report": self.report.to_dict(),
        }
        usage_payload = coerce_deepseek_usage(self.report.deepseek_usage)
        payload["deepseek_usage"] = usage_payload
        if self.report.deepseek_est_cost_usd is not None:
            payload["deepseek_est_cost_usd"] = float(self.report.deepseek_est_cost_usd)
        if isinstance(self.report.deepseek_cost_basis, str) and self.report.deepseek_cost_basis:
            payload["deepseek_cost_basis"] = self.report.deepseek_cost_basis
        # Propagate durable envelope fields from the implementation
        # response (SD1, SD2) so downstream consumers see session_id,
        # turn_id, hashes, outcome, apply_eligibility, change_details,
        # audit/artifact refs, gates, debug, and contract_version at
        # the top level.  Executor-owned fields (graph, message, route,
        # candidate, apply_eligible) take priority over any collisions.
        impl = self.report.implementation
        if impl is not None and impl.durable_response is not None:
            dr = impl.durable_response
            for key in _DURABLE_ENVELOPE_TOP_LEVEL_KEYS:
                value = dr.get(key)
                if value is not None:
                    payload[key] = _thaw_jsonish(value)
        payload.update(self.turn.to_dict())
        if self.graph is not None:
            payload["graph"] = self.graph
        if self.failure_kind is not None:
            payload["failure_kind"] = self.failure_kind
        if self.failure_stage is not None:
            payload["failure_stage"] = self.failure_stage
        if self.failure_message is not None:
            payload["failure_message"] = self.failure_message
        return payload

    @classmethod
    def success(
        cls,
        *,
        report: Report | None = None,
        graph: dict[str, Any] | None = None,
        reply: str | None = None,
    ) -> "ExecutorResult":
        return cls(ok=True, report=report or Report(), graph=graph, reply=reply)

    @classmethod
    def failure(
        cls,
        *,
        kind: str,
        stage: str,
        message: str,
        report: Report | None = None,
    ) -> "ExecutorResult":
        return cls(
            ok=False,
            report=report or Report(),
            failure_kind=kind,
            failure_stage=stage,
            failure_message=message,
        )


__all__ = [
    "AgentEvidence",
    "AgentTurnResult",
    "ClassifyDecision",
    "ExecutorRequest",
    "ExecutorResult",
    "GraphFacts",
    "ImplementationResult",
    "InspectionSummary",
    "PrecedentAdaptationPlan",
    "PrecedentOption",
    "PrecedentPacket",
    "ReadinessReport",
    "Report",
    "ResearchResult",
    "RevisionEvidence",
    "ScopedDiff",
    "SelectedPrecedent",
    "TopologyFindings",
    "WorkflowSlice",
    "adaptation_plan_actionability",
    "adaptation_plan_actionability_payload",
    "is_actionable_adaptation_plan",
    "warning_detail_from_exception",
]
