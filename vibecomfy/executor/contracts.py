"""Typed data contracts for the embedded VibeComfy executor.

These are the public shapes that flow through the classify → research →
implement → reply pipeline.  Every contract is a frozen dataclass with a
canonical ``to_dict()`` serializer so the executor can produce the standard
``success_envelope`` shape without adding new top-level response fields.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import re
from types import MappingProxyType
from typing import Any, Mapping
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit


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
    "direct_edit",
    "inspect_only",
    "asset_lookup",
    "diagnose_repair",
    "subgraph_preview",
    "precedent_research",
    "clarify",
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
    "respond",
    "research_nodes",
})

_ROUTE_DESCRIPTIONS: dict[str, str] = {
    "direct_edit": "simple graph edit, no research needed.",
    "inspect_only": "inspect/explain a graph without editing.",
    "asset_lookup": "find assets, models, or nodes.",
    "diagnose_repair": "diagnose and fix a broken graph.",
    "subgraph_preview": "preview a subgraph or node group.",
    "precedent_research": "research precedent templates/techniques before editing.",
    "clarify": "ask a clarifying question or respond without editing.",
}

_TASK_DESCRIPTIONS: dict[str, str] = {
    "edit_graph": "modify the current graph.",
    "inspect_graph": "inspect or explain a graph without editing.",
    "find_assets": "find assets, models, or nodes.",
    "diagnose": "diagnose workflow problems.",
    "preview_subgraph": "preview a subgraph or node group.",
    "research_precedent": "research precedent templates or techniques.",
    "respond": "reply without graph actions.",
    "research_nodes": "research nodes or workflow techniques.",
}

if set(_ROUTE_DESCRIPTIONS) != (_ALLOWED_ROUTES - {""}):
    raise ValueError("Route descriptions must cover every non-empty allowed route exactly once.")

if set(_TASK_DESCRIPTIONS) != (_ALLOWED_TASKS - {""}):
    raise ValueError("Task descriptions must cover every non-empty allowed task exactly once.")


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

        # Clamp route to allowed values.
        if self.route not in _ALLOWED_ROUTES:
            object.__setattr__(self, "route", "")

        # Clamp task to allowed values.
        if self.task not in _ALLOWED_TASKS:
            object.__setattr__(self, "task", "")

        # Freeze tuple fields.
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

    This is intentionally conservative: it only produces a route when the
    legacy fields unambiguously map to a single route.  Ambiguous cases
    (e.g. research=True + implement=True) return ``""`` so the caller knows
    no explicit route was set.

    The mapping follows the hard gate rules in SD2:
    * direct_edit → implement without research
    * inspect_only → research/inspect without implementation
    * clarify → neither research nor implementation
    * precedent_research is NOT derived — it requires an explicit ``route``
      because legacy ``research=true, implement=true`` is ambiguous.
    """
    if implement and not research:
        # Edit with no research requirement → direct_edit.
        return "direct_edit"
    if research and not implement:
        # Research/inspect without implementation → inspect_only.
        return "inspect_only"
    if not research and not implement:
        # Neither research nor implementation → clarify.
        return "clarify"
    # research=True, implement=True → ambiguous; do not derive.
    return ""


def _derive_task(*, research: bool, implement: bool, intent: str) -> str:
    """Derive a normalized task label from legacy fields.

    Returns ``""`` when the mapping is ambiguous.
    """
    if implement and not research:
        return "edit_graph"
    if research and not implement:
        if intent == "explain_graph":
            return "inspect_graph"
        if intent == "research":
            return "research_nodes"
        return "inspect_graph"
    if not research and not implement:
        return "respond"
    # research=True, implement=True → ambiguous.
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
    entry_anchor: str | None = None
    exit_anchor: str | None = None
    python_path: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "node_ids", tuple(self.node_ids))

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "source_class_type": self.source_class_type,
            "node_ids": list(self.node_ids),
        }
        if self.entry_anchor is not None:
            payload["entry_anchor"] = self.entry_anchor
        if self.exit_anchor is not None:
            payload["exit_anchor"] = self.exit_anchor
        if self.python_path is not None:
            payload["python_path"] = self.python_path
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
        if self.structural_validation not in ("not_evaluated", "pass", "fail", "advisory"):
            object.__setattr__(self, "structural_validation", "not_evaluated")
        if self.semantic_validation not in ("not_evaluated", "pass", "fail", "advisory"):
            object.__setattr__(self, "semantic_validation", "not_evaluated")

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "selected_slice": self.selected_slice.to_dict(),
            "anchor_bindings": _thaw_jsonish(self.anchor_bindings),
            "required_new_nodes": _thaw_jsonish(self.required_new_nodes),
            "required_rewires": _thaw_jsonish(self.required_rewires),
            "edit_ops": _thaw_jsonish(self.edit_ops),
            "structural_validation": self.structural_validation,
            "semantic_validation": self.semantic_validation,
        }
        if self.candidate_graph is not None:
            payload["candidate_graph"] = self.candidate_graph
        return payload

# ── research result ──────────────────────────────────────────────────────────


@dataclass(frozen=True)
class ResearchResult:
    """Aggregated research output from local corpus + optional Hivemind.

    ``sources`` is a deduplicated, score-ordered list of source references.
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

    def __post_init__(self) -> None:
        object.__setattr__(self, "sources", tuple(self.sources))
        object.__setattr__(self, "warnings", tuple(self.warnings))
        object.__setattr__(
            self,
            "warning_details",
            tuple(
                MappingProxyType({str(k): _freeze_jsonish(v) for k, v in detail.items()})
                if isinstance(detail, Mapping) else detail
                for detail in self.warning_details
            ),
        )
        object.__setattr__(self, "precedent_slices", tuple(self.precedent_slices))
    def to_dict(self) -> dict[str, Any]:
        result = {
            "summary": self.summary,
            "sources": _thaw_jsonish(self.sources),
            "warnings": list(self.warnings),
        }
        if self.warning_details:
            result["warning_details"] = _thaw_jsonish(self.warning_details)
        if self.precedent_slices:
            result["precedent_slices"] = [s.to_dict() for s in self.precedent_slices]
        if self.adaptation_plan is not None:
            result["adaptation_plan"] = self.adaptation_plan.to_dict()
        return result


# ── implementation result ────────────────────────────────────────────────────


@dataclass(frozen=True)
class ImplementationResult:
    """Output from the implement phase (graph edit or delta).

    Exactly one of ``graph`` or ``delta`` is populated.  ``message`` is the
    agent-facing explanation (carried into the reply phase for context).
    """

    graph: dict[str, Any] | None = None
    delta: tuple[dict[str, Any], ...] = ()
    message: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "delta", tuple(self.delta))

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {"message": self.message}
        if self.graph is not None:
            payload["graph"] = self.graph
        if self.delta:
            payload["delta"] = _thaw_jsonish(self.delta)
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

    def to_dict(self) -> dict[str, Any]:
        inner: dict[str, Any] = {"plan": self.plan.to_dict()}
        if self.research is not None:
            inner["research"] = self.research.to_dict()
        if self.implementation is not None:
            inner["implementation"] = self.implementation.to_dict()
        return {"executor": inner}


# ── executor result (final envelope leaf) ────────────────────────────────────


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

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "ok": self.ok,
            "report": self.report.to_dict(),
        }
        if self.graph is not None:
            payload["graph"] = self.graph
        if self.reply is not None:
            payload["reply"] = self.reply
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
    "ClassifyDecision",
    "ExecutorRequest",
    "ExecutorResult",
    "ImplementationResult",
    "InspectionSummary",
    "PrecedentAdaptationPlan",
    "Report",
    "ResearchResult",
    "WorkflowSlice",
    "warning_detail_from_exception",
]
