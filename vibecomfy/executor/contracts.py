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

MODEL_ATTEMPT_FAILURE_TYPES = frozenset({
    "empty_response",
    "malformed_json",
    "non_json_content",
    "missing_required_fields",
    "timeout",
    "provider_failure",
})
_MODEL_ATTEMPT_OUTCOMES = frozenset({"success", "failure"})
_MODEL_ATTEMPT_UNKNOWN = "unknown"
_MODEL_ATTEMPT_PREVIEW_LIMIT = 1200
_MODEL_ATTEMPT_SECRET_ASSIGNMENT_RE = re.compile(
    r"(?i)\b(api[_-]?key|authorization|bearer[_-]?token|access[_-]?token|secret|token)"
    r"(\s*[:=]\s*)([^\s,;]+)"
)
_MODEL_ATTEMPT_BEARER_RE = re.compile(r"(?i)\bBearer\s+[^\s,;]+")
_MODEL_ATTEMPT_AUTHORIZATION_HEADER_RE = re.compile(
    r"(?im)\bauthorization\s*:\s*[^\r\n]*"
)
_MODEL_ATTEMPT_URL_RE = re.compile(r"https?://[^\s<>\"']+")
# Oracle finding 5: failure previews can embed the secret as a JSON-quoted
# value (``{"api_key": "sk-..."}``), which the unquoted assignment and
# authorization-header patterns cannot see.  Match quoted sensitive fields in
# BOTH ``"key": "value"`` and ``'key': 'value'`` styles; the value is matched
# best-effort so malformed/truncated JSON never crashes the redactor.
_MODEL_ATTEMPT_JSON_QUOTED_SECRET_RE = re.compile(
    r"""(?ix)
    (["'])                                    # key quote (double or single)
    (api[_-]?key|authorization|auth|token|access[_-]?token|refresh[_-]?token)
    \1\s*:\s*                                 # closing key quote, colon
    (["'])(?:(?!\3)[^"'\r])*(\3)?             # quoted value (may be truncated)
    """
)


def normalize_model_endpoint(value: Any) -> str:
    """Return a credential-free, query-free endpoint or ``"unknown"``.

    Model-attempt evidence intentionally records only the scheme, host, port,
    and normalized path. Userinfo, query parameters, and fragments are never
    provenance and can contain credentials, so they are discarded wholesale.
    """
    if not isinstance(value, str) or not value.strip():
        return _MODEL_ATTEMPT_UNKNOWN
    try:
        parsed = urlsplit(value.strip())
    except ValueError:
        return _MODEL_ATTEMPT_UNKNOWN
    if parsed.scheme.lower() not in {"http", "https"} or not parsed.hostname:
        return _MODEL_ATTEMPT_UNKNOWN
    host = parsed.hostname.lower()
    if ":" in host and not host.startswith("["):
        host = f"[{host}]"
    try:
        port = parsed.port
    except ValueError:
        return _MODEL_ATTEMPT_UNKNOWN
    netloc = f"{host}:{port}" if port is not None else host
    path = re.sub(r"/{2,}", "/", parsed.path or "")
    if path != "/":
        path = path.rstrip("/")
    return urlunsplit((parsed.scheme.lower(), netloc, path, "", ""))


def _redact_json_quoted_secret(match: re.Match[str]) -> str:
    """Collapse a quoted sensitive JSON field to ``"key": "<redacted>"``.

    The key's original casing and quote style are preserved so the preview
    keeps its JSON-ish shape; only the value is replaced.
    """
    key_quote = match.group(1)
    value_quote = match.group(3)
    return f"{key_quote}{match.group(2)}{key_quote}: {value_quote}<redacted>{value_quote}"


def redact_model_preview(value: Any, *, limit: int = _MODEL_ATTEMPT_PREVIEW_LIMIT) -> str | None:
    """Return a bounded failure preview with credentials and URL queries removed."""
    if not isinstance(value, str):
        return None
    redacted = _MODEL_ATTEMPT_JSON_QUOTED_SECRET_RE.sub(
        _redact_json_quoted_secret, value
    )
    redacted = _MODEL_ATTEMPT_AUTHORIZATION_HEADER_RE.sub(
        "Authorization: <redacted>", redacted
    )
    normalized = " ".join(redacted.strip().split())
    if not normalized:
        return None
    normalized = _MODEL_ATTEMPT_URL_RE.sub(
        lambda match: normalize_model_endpoint(match.group(0)), normalized
    )
    normalized = _MODEL_ATTEMPT_BEARER_RE.sub("Bearer <redacted>", normalized)
    normalized = _MODEL_ATTEMPT_SECRET_ASSIGNMENT_RE.sub(
        lambda match: f"{match.group(1)}{match.group(2)}<redacted>", normalized
    )
    if len(normalized) > limit:
        normalized = normalized[: limit - 1].rstrip() + "…"
    return normalized


def _model_attempt_text(value: Any) -> str:
    if isinstance(value, str) and value.strip():
        return value.strip()
    return _MODEL_ATTEMPT_UNKNOWN


def _model_attempt_token_usage(value: Any) -> dict[str, int | str]:
    usage = value if isinstance(value, Mapping) else {}
    normalized: dict[str, int | str] = {}
    for key in ("prompt_tokens", "completion_tokens", "total_tokens"):
        token_value = usage.get(key)
        normalized[key] = (
            max(0, int(token_value))
            if isinstance(token_value, (int, float)) and not isinstance(token_value, bool)
            else _MODEL_ATTEMPT_UNKNOWN
        )
    return normalized


@dataclass(frozen=True)
class ModelAttemptEvidence:
    """Canonical evidence for one actual model-provider call.

    The shape is shared by worker envelopes, runtime/provider results, executor
    reports, durable artifacts, and the live harness. Raw model output is never
    retained on success and is bounded/redacted on failure.
    """

    phase: str = _MODEL_ATTEMPT_UNKNOWN
    attempt: int = 1
    outcome: str = "failure"
    failure_type: str | None = None
    requested_model: str = _MODEL_ATTEMPT_UNKNOWN
    resolved_model: str = _MODEL_ATTEMPT_UNKNOWN
    adapter: str = _MODEL_ATTEMPT_UNKNOWN
    provider: str = _MODEL_ATTEMPT_UNKNOWN
    transport: str = _MODEL_ATTEMPT_UNKNOWN
    endpoint: str = _MODEL_ATTEMPT_UNKNOWN
    finish_reason: str = _MODEL_ATTEMPT_UNKNOWN
    token_usage: Mapping[str, Any] = field(default_factory=dict)
    raw_response_preview: str | None = None

    def __post_init__(self) -> None:
        outcome = self.outcome if self.outcome in _MODEL_ATTEMPT_OUTCOMES else "failure"
        failure_type = self.failure_type
        if outcome == "success":
            failure_type = None
        elif failure_type not in MODEL_ATTEMPT_FAILURE_TYPES:
            failure_type = "provider_failure"
        object.__setattr__(self, "phase", _model_attempt_text(self.phase))
        object.__setattr__(self, "attempt", max(1, int(self.attempt or 1)))
        object.__setattr__(self, "outcome", outcome)
        object.__setattr__(self, "failure_type", failure_type)
        for name in (
            "requested_model", "resolved_model", "adapter", "provider",
            "transport", "finish_reason",
        ):
            object.__setattr__(self, name, _model_attempt_text(getattr(self, name)))
        object.__setattr__(self, "endpoint", normalize_model_endpoint(self.endpoint))
        object.__setattr__(
            self,
            "token_usage",
            MappingProxyType(_model_attempt_token_usage(self.token_usage)),
        )
        preview = (
            redact_model_preview(self.raw_response_preview)
            if outcome == "failure"
            else None
        )
        object.__setattr__(self, "raw_response_preview", preview)

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "ModelAttemptEvidence":
        return cls(
            phase=value.get("phase", _MODEL_ATTEMPT_UNKNOWN),
            attempt=value.get("attempt", 1),
            outcome=value.get("outcome", "failure"),
            failure_type=value.get("failure_type"),
            requested_model=value.get("requested_model", _MODEL_ATTEMPT_UNKNOWN),
            resolved_model=value.get("resolved_model", _MODEL_ATTEMPT_UNKNOWN),
            adapter=value.get("adapter", _MODEL_ATTEMPT_UNKNOWN),
            provider=value.get("provider", _MODEL_ATTEMPT_UNKNOWN),
            transport=value.get("transport", _MODEL_ATTEMPT_UNKNOWN),
            endpoint=value.get("endpoint", _MODEL_ATTEMPT_UNKNOWN),
            finish_reason=value.get("finish_reason", _MODEL_ATTEMPT_UNKNOWN),
            token_usage=value.get("token_usage", {}),
            raw_response_preview=value.get("raw_response_preview"),
        )

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "phase": self.phase,
            "attempt": self.attempt,
            "outcome": self.outcome,
            "failure_type": self.failure_type,
            "requested_model": self.requested_model,
            "resolved_model": self.resolved_model,
            "adapter": self.adapter,
            "provider": self.provider,
            "transport": self.transport,
            "endpoint": self.endpoint,
            "finish_reason": self.finish_reason,
            "token_usage": dict(self.token_usage),
        }
        if self.outcome == "failure" and self.raw_response_preview:
            payload["raw_response_preview"] = self.raw_response_preview
        return payload


def coerce_model_attempts(value: Any) -> tuple[dict[str, Any], ...]:
    """Normalize untrusted attempt mappings into the canonical serialized shape."""
    if not isinstance(value, (list, tuple)):
        return ()
    attempts: list[dict[str, Any]] = []
    for item in value:
        if isinstance(item, ModelAttemptEvidence):
            attempts.append(item.to_dict())
        elif isinstance(item, Mapping):
            attempts.append(ModelAttemptEvidence.from_mapping(item).to_dict())
    return tuple(attempts)


_NODE_TYPE_MARKER_RE = re.compile(
    r"(?:class(?:_type|\s+type)?|node(?:\s+of)?(?:\s+type)?|of\s+type)\s*[:=]?\s*"
    r"([A-Za-z_][A-Za-z0-9_.:-]*)",
    re.IGNORECASE,
)
_NODE_TYPE_VERB_RE = re.compile(
    r"\b(?:add|insert|create|restore|replace|remove|change|edit)\s+"
    r"(?:(?:an?|the|new|another|some|one)\s+)*"
    r"([A-Za-z_][A-Za-z0-9_.:-]*)\b",
    re.IGNORECASE,
)
_NON_NODE_TYPE_TOKENS = frozenset({
    "a", "an", "the", "node", "nodes", "class", "type", "of", "to",
    "with", "for", "from", "into", "on", "in", "and", "or", "value",
    "setting", "settings", "field", "fields", "widget", "widgets", "new",
})
_UI_ONLY_ANNOTATION_CLASS_TYPES = frozenset({
    "annotation",
    "annotationnode",
    "comment",
    "commentnode",
    "markdown",
    "markdownnote",
    "markdownnotenode",
    "note",
    "notenode",
    "workflowcomment",
    "workflowmarkdown",
    "workflownote",
})


def is_ui_only_annotation_class_type(class_type: Any) -> bool:
    """Return whether a class name denotes a known no-dataflow UI annotation.

    Keep this deliberately conservative: reroutes, primitives, groups, and
    other frontend components can participate in dataflow or component
    expansion and therefore are not skipped merely because they are UI nodes.
    """
    normalized = re.sub(r"[^a-z0-9]", "", str(class_type or "").casefold())
    return normalized in _UI_ONLY_ANNOTATION_CLASS_TYPES


def parse_target_node_type(change_goal: str) -> str:
    """Extract a likely ComfyUI class-type token from a change goal.

    Classifier metadata is intentionally best-effort.  The parser only uses
    explicit node/type markers or an edit verb followed by a token, and returns
    an empty string when the sentence is too ambiguous to bind safely.
    """
    if not isinstance(change_goal, str) or not change_goal.strip():
        return ""

    candidates: list[str] = []
    marker = _NODE_TYPE_MARKER_RE.search(change_goal)
    if marker:
        candidates.append(marker.group(1))
    verb = _NODE_TYPE_VERB_RE.search(change_goal)
    if verb:
        candidates.append(verb.group(1))

    for candidate in candidates:
        token = candidate.strip(".,;()[]{}\"'")
        if token and token.casefold() not in _NON_NODE_TYPE_TOKENS:
            return token
    return ""


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
    target_node_type: str = ""
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
        target_node_type = str(self.target_node_type).strip()
        if not target_node_type:
            target_node_type = parse_target_node_type(self.change_goal)
        object.__setattr__(self, "target_node_type", target_node_type)

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
        if self.target_node_type:
            result["target_node_type"] = self.target_node_type
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
    workflow_id: str | None = None
    session_id: str | None = None
    profile: str | None = None
    idempotency_key: str | None = None
    client_graph_hash: str | None = None
    client_structural_graph_hash: str | None = None
    client_live_canvas_token: str | None = None
    expected_baseline_graph_hash: str | None = None
    expected_baseline_graph_hash_present: bool = False
    # Frontend "Author Uninstalled Node Packs" setting (default ON at the provider).
    # None = unset → provider applies its env/default. Threaded through so the
    # user-facing toggle actually controls on-demand schema resolution.
    on_demand_schemas: bool | None = None

    def __post_init__(self) -> None:
        # Preserve the distinction between an explicit null from a current
        # pristine client and omission by a legacy client.
        if self.expected_baseline_graph_hash is not None:
            object.__setattr__(self, "expected_baseline_graph_hash_present", True)

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {"query": self.query}
        if self.graph is not None:
            payload["graph"] = self.graph
        if self.workflow_id is not None:
            payload["workflow_id"] = self.workflow_id
        if self.session_id is not None:
            payload["session_id"] = self.session_id
        if self.profile is not None:
            payload["profile"] = self.profile
        if self.idempotency_key is not None:
            payload["idempotency_key"] = self.idempotency_key
        if self.client_graph_hash is not None:
            payload["client_graph_hash"] = self.client_graph_hash
        if self.client_structural_graph_hash is not None:
            payload["client_structural_graph_hash"] = self.client_structural_graph_hash
        if self.client_live_canvas_token is not None:
            payload["client_live_canvas_token"] = self.client_live_canvas_token
        if self.expected_baseline_graph_hash_present:
            payload["expected_baseline_graph_hash"] = self.expected_baseline_graph_hash
        if self.on_demand_schemas is not None:
            payload["on_demand_schemas"] = self.on_demand_schemas
        return payload

    @classmethod
    def from_payload(cls, payload: Mapping[str, Any]) -> "ExecutorRequest":
        query = payload.get("query")
        if not isinstance(query, str) or not query.strip():
            raise ValueError("ExecutorRequest requires a non-empty string `query`.")
        graph = payload.get("graph")
        if graph is not None and not isinstance(graph, dict):
            raise ValueError("ExecutorRequest `graph` must be a dict or null.")
        workflow_id = payload.get("workflow_id")
        if workflow_id is not None and not isinstance(workflow_id, str):
            raise ValueError("ExecutorRequest `workflow_id` must be a string or null.")
        graph_workflow_id = graph.get("id") if isinstance(graph, dict) else None
        if workflow_id is None and isinstance(graph_workflow_id, str):
            # Older already-loaded browser modules did not send the new
            # top-level fence. Canonicalize the identity at ingress from the
            # same serialized graph instead of failing after model execution.
            workflow_id = graph_workflow_id
        if workflow_id is not None:
            from vibecomfy.comfy_nodes.agent.projection_registry_v1 import (  # noqa: PLC0415
                ContractError,
                workflow_identity_v1,
            )

            try:
                workflow_identity_v1(workflow_id)
                if isinstance(graph_workflow_id, str):
                    workflow_identity_v1(graph_workflow_id)
            except ContractError as exc:
                raise ValueError(str(exc)) from exc
            if isinstance(graph_workflow_id, str) and graph_workflow_id != workflow_id:
                raise ValueError(
                    "ExecutorRequest `workflow_id` must match the attached graph `id`."
                )
        session_id = payload.get("session_id")
        if session_id is not None and not isinstance(session_id, str):
            raise ValueError("ExecutorRequest `session_id` must be a string or null.")
        if session_id is not None:
            from vibecomfy.comfy_nodes.agent.session import normalize_session_id  # noqa: PLC0415

            session_id = normalize_session_id(session_id)
        profile = payload.get("profile")
        if profile is not None and not isinstance(profile, str):
            raise ValueError("ExecutorRequest `profile` must be a string or null.")
        idempotency_key = payload.get("idempotency_key")
        if idempotency_key is not None and not isinstance(idempotency_key, str):
            raise ValueError("ExecutorRequest `idempotency_key` must be a string or null.")
        client_graph_hash = payload.get("client_graph_hash")
        if client_graph_hash is not None and not isinstance(client_graph_hash, str):
            raise ValueError("ExecutorRequest `client_graph_hash` must be a string or null.")
        client_structural_graph_hash = payload.get("client_structural_graph_hash")
        if client_structural_graph_hash is not None and not isinstance(
            client_structural_graph_hash, str
        ):
            raise ValueError(
                "ExecutorRequest `client_structural_graph_hash` must be a string or null."
            )
        client_live_canvas_token = payload.get("client_live_canvas_token")
        if client_live_canvas_token is not None and not isinstance(client_live_canvas_token, str):
            raise ValueError("ExecutorRequest `client_live_canvas_token` must be a string or null.")
        expected_baseline_graph_hash = payload.get("expected_baseline_graph_hash")
        expected_baseline_graph_hash_present = "expected_baseline_graph_hash" in payload
        on_demand_schemas = payload.get("on_demand_schemas")
        if not isinstance(on_demand_schemas, bool):
            on_demand_schemas = None
        if expected_baseline_graph_hash is not None and not isinstance(
            expected_baseline_graph_hash, str
        ):
            raise ValueError(
                "ExecutorRequest `expected_baseline_graph_hash` must be a string or null."
            )
        return cls(
            query=query.strip(),
            graph=graph,
            workflow_id=workflow_id,
            session_id=session_id,
            profile=profile,
            idempotency_key=idempotency_key,
            client_graph_hash=client_graph_hash,
            client_structural_graph_hash=client_structural_graph_hash,
            client_live_canvas_token=client_live_canvas_token,
            expected_baseline_graph_hash=expected_baseline_graph_hash,
            expected_baseline_graph_hash_present=expected_baseline_graph_hash_present,
            on_demand_schemas=on_demand_schemas,
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
    source_template: str = ""
    role_label: str = ""
    role_confidence: str = "low"
    widget_values: tuple[dict[str, Any], ...] = ()
    binding_envelope: Mapping[str, Any] = field(default_factory=dict)
    incident_edges: tuple[dict[str, Any], ...] = ()
    warnings: tuple[dict[str, Any], ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "node_ids", tuple(self.node_ids))
        object.__setattr__(self, "node_types", tuple(self.node_types))
        if self.role_confidence not in {"low", "medium", "high"}:
            object.__setattr__(self, "role_confidence", "low")
        object.__setattr__(self, "widget_values", tuple(
            MappingProxyType({str(k): _freeze_jsonish(v) for k, v in value.items()})
            if isinstance(value, Mapping) else value
            for value in self.widget_values
        ))
        object.__setattr__(
            self,
            "binding_envelope",
            _freeze_jsonish(self.binding_envelope)
            if isinstance(self.binding_envelope, Mapping)
            else MappingProxyType({}),
        )
        object.__setattr__(self, "incident_edges", tuple(
            MappingProxyType({str(k): _freeze_jsonish(v) for k, v in edge.items()})
            if isinstance(edge, Mapping) else edge
            for edge in self.incident_edges
        ))
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
        if self.source_template:
            payload["source_template"] = self.source_template
        if self.role_label:
            payload["role_label"] = self.role_label
            payload["role_confidence"] = self.role_confidence
        if self.widget_values:
            payload["widget_values"] = _thaw_jsonish(self.widget_values)
        if self.binding_envelope:
            payload["binding_envelope"] = _thaw_jsonish(self.binding_envelope)
        if self.incident_edges:
            payload["incident_edges"] = _thaw_jsonish(self.incident_edges)
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
    # W-02: singular focused-manifest contract — at most ONE, default None
    topology_manifest: TopologyManifest | None = None

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
        if (
            self.candidate_graph is not None
            and (
                self.structural_validation != "pass"
                or self.semantic_validation == "fail"
            )
        ):
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
        if (
            self.structural_validation == "pass"
            and self.semantic_validation != "fail"
            and self.candidate_graph is not None
        ):
            payload["candidate_graph"] = self.candidate_graph
        if self.all_slices:
            payload["all_slices"] = [s.to_dict() for s in self.all_slices]
        if self.context_note:
            payload["context_note"] = self.context_note
        if self.topology_manifest is not None:
            payload["topology_manifest"] = self.topology_manifest.to_dict()
        return payload


# ── topology manifest (W-02) ──────────────────────────────────────────────────

class ManifestOversized(ValueError):
    """Raised when a manifest exceeds its size bounds (never silently truncate)."""


@dataclass(frozen=True)
class ManifestNode:
    """A single node in the topology manifest, derived from retrieved evidence.

    Carries only structural topology — no fixture ancestry, golden node
    IDs/values, filenames, sigma strings, or raw ``candidate_graph``.
    """

    symbol: str
    canonical_class_type: str
    resolver_status: str  # "resolved" | "unresolved" | "inferred"
    evidence_ref: str      # opaque hash pointer into retrieved evidence (no path)
    confidence: float

    def __post_init__(self) -> None:
        if self.resolver_status not in ("resolved", "unresolved", "inferred"):
            object.__setattr__(self, "resolver_status", "unresolved")


@dataclass(frozen=True)
class ManifestInternalEdge:
    """An edge between two manifest-local symbols (no source/target IDs)."""

    from_symbol: str
    output_socket: str    # socket NAME or "<idx:2>" (no ids)
    to_symbol: str
    input_socket: str
    evidence_ref: str
    confidence: float


@dataclass(frozen=True)
class ManifestBoundaryAnchor:
    """ID-free boundary anchor binding a manifest symbol to the target graph.

    Selectors use role/class/socket ONLY — no ``broken_graph_node_id``,
    source ids, paths, or widget literals.
    """

    direction: str        # "inbound" | "outbound"
    symbol: str
    symbol_socket: str
    target_role: str       # e.g. "sampler", "model_provider"
    target_class_type: str # e.g. "WanVideoSampler"
    target_socket: str     # e.g. "image_embeds"
    source_anchor_ref: str # opaque evidence ref (no path)
    confidence: float

    def __post_init__(self) -> None:
        if self.direction not in ("inbound", "outbound"):
            object.__setattr__(self, "direction", "inbound")


@dataclass(frozen=True)
class ManifestInquiryCoverage:
    required_roles: tuple[str, ...]
    covered_roles: tuple[str, ...]


@dataclass(frozen=True)
class ManifestValidation:
    verdict: str          # "pass" | "fail"
    class_resolution: str
    socket_checks: str
    cut_edge_coverage: str
    anchor_binding: str
    reasons: tuple[str, ...]

    def __post_init__(self) -> None:
        if self.verdict not in ("pass", "fail"):
            object.__setattr__(self, "verdict", "fail")


@dataclass(frozen=True)
class TopologyManifest:
    """Singular focused-manifest contract — complete-or-reject, size-bounded.

    Carries ONLY structural topology derived from generic retrieval evidence.
    Never fixture ancestry, golden node IDs/values, filenames, sigma strings,
    or raw ``candidate_graph``.
    """

    manifest_id: str
    # source provenance — content hash + retrieval rank + tier ONLY (no path/filename)
    source_content_hash: str
    source_retrieval_rank: int
    source_tier: str
    nodes: tuple[ManifestNode, ...]
    internal_edges: tuple[ManifestInternalEdge, ...]
    boundary_anchors: tuple[ManifestBoundaryAnchor, ...]
    inquiry_coverage: ManifestInquiryCoverage
    validation: ManifestValidation
    evidence_hash: str    # opaque hash of the retrieved evidence (no path)
    confidence: float

    def __post_init__(self) -> None:
        object.__setattr__(self, "nodes", tuple(self.nodes))
        object.__setattr__(self, "internal_edges", tuple(self.internal_edges))
        object.__setattr__(self, "boundary_anchors", tuple(self.boundary_anchors))

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a JSON-friendly dict (ID-free, no paths)."""
        return {
            "manifest_id": self.manifest_id,
            "source_content_hash": self.source_content_hash,
            "source_retrieval_rank": self.source_retrieval_rank,
            "source_tier": self.source_tier,
            "nodes": [
                {
                    "symbol": n.symbol,
                    "canonical_class_type": n.canonical_class_type,
                    "resolver_status": n.resolver_status,
                    "evidence_ref": n.evidence_ref,
                    "confidence": n.confidence,
                }
                for n in self.nodes
            ],
            "internal_edges": [
                {
                    "from_symbol": e.from_symbol,
                    "output_socket": e.output_socket,
                    "to_symbol": e.to_symbol,
                    "input_socket": e.input_socket,
                    "evidence_ref": e.evidence_ref,
                    "confidence": e.confidence,
                }
                for e in self.internal_edges
            ],
            "boundary_anchors": [
                {
                    "direction": a.direction,
                    "symbol": a.symbol,
                    "symbol_socket": a.symbol_socket,
                    "target_role": a.target_role,
                    "target_class_type": a.target_class_type,
                    "target_socket": a.target_socket,
                    "source_anchor_ref": a.source_anchor_ref,
                    "confidence": a.confidence,
                }
                for a in self.boundary_anchors
            ],
            "inquiry_coverage": {
                "required_roles": list(self.inquiry_coverage.required_roles),
                "covered_roles": list(self.inquiry_coverage.covered_roles),
            },
            "validation": {
                "verdict": self.validation.verdict,
                "class_resolution": self.validation.class_resolution,
                "socket_checks": self.validation.socket_checks,
                "cut_edge_coverage": self.validation.cut_edge_coverage,
                "anchor_binding": self.validation.anchor_binding,
                "reasons": list(self.validation.reasons),
            },
            "evidence_hash": self.evidence_hash,
            "confidence": self.confidence,
        }


# ── Manifest size bounds ─────────────────────────────────────────────────────

_MAX_MANIFEST_NODES = 64
_MAX_MANIFEST_EDGES = 128
_MAX_MANIFEST_ANCHORS = 16


def build_topology_manifest(
    manifest_id: str,
    source_content_hash: str,
    source_retrieval_rank: int,
    source_tier: str,
    nodes: tuple[ManifestNode, ...],
    internal_edges: tuple[ManifestInternalEdge, ...],
    boundary_anchors: tuple[ManifestBoundaryAnchor, ...],
    inquiry_coverage: ManifestInquiryCoverage,
    validation: ManifestValidation,
    evidence_hash: str,
    confidence: float,
) -> TopologyManifest | None:
    """Build a :class:`TopologyManifest` with complete-or-reject invariants.

    Returns ``None`` if any required field is missing/empty.  Raises
    :class:`ManifestOversized` if size bounds are exceeded.  Never silently
    truncates.
    """
    # ── complete-or-reject: required string fields ──────────────────────
    if not manifest_id or not isinstance(manifest_id, str):
        return None
    if not source_content_hash or not isinstance(source_content_hash, str):
        return None
    if not source_tier or not isinstance(source_tier, str):
        return None
    if not evidence_hash or not isinstance(evidence_hash, str):
        return None

    # ── size bounds: reject, never truncate ─────────────────────────────
    if len(nodes) > _MAX_MANIFEST_NODES:
        raise ManifestOversized(
            f"nodes count {len(nodes)} exceeds limit {_MAX_MANIFEST_NODES}"
        )
    if len(internal_edges) > _MAX_MANIFEST_EDGES:
        raise ManifestOversized(
            f"internal_edges count {len(internal_edges)} exceeds limit {_MAX_MANIFEST_EDGES}"
        )
    if len(boundary_anchors) > _MAX_MANIFEST_ANCHORS:
        raise ManifestOversized(
            f"boundary_anchors count {len(boundary_anchors)} exceeds limit {_MAX_MANIFEST_ANCHORS}"
        )

    # ── complete-or-reject: sub-objects must be present ────────────────
    if inquiry_coverage is None:
        return None
    if validation is None:
        return None

    return TopologyManifest(
        manifest_id=manifest_id,
        source_content_hash=source_content_hash,
        source_retrieval_rank=source_retrieval_rank,
        source_tier=source_tier,
        nodes=nodes,
        internal_edges=internal_edges,
        boundary_anchors=boundary_anchors,
        inquiry_coverage=inquiry_coverage,
        validation=validation,
        evidence_hash=evidence_hash,
        confidence=confidence,
    )


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


# ── freshness / evidence-metadata vocabulary ──────────────────────────────────

# Per-tier TTL defaults (seconds) with environment override hooks.
# These are consumed by research.py and govern staleness marking;
# contracts.py defines the field vocabulary so all consumers share
# a single source of truth for serialization shapes.

_ALLOWED_FRESHNESS_STATUSES = frozenset({"fresh", "stale", "unknown"})
_ALLOWED_EVIDENCE_TIERS = frozenset({
    "local_corpus",
    "hivemind",
    "hivemind_workflow",
    "comfy-registry",
    "github",
    "git",
    "web",
    "civitai",
    "external_workflow",
    "live_runtime_schema",
    "curated",
    "ready_template",
    "source_workflow",
    "custom_node_examples",
    "object_info",
})


@dataclass(frozen=True)
class SelectedPrecedent:
    """Research-grounded workflow interpretation for edit-by-precedent.

    Unlike :class:`PrecedentPacket`, this is intentionally directive: it records
    the workflow pattern research found to be compatible enough to ground the
    later authoring/resolution step.  It is still evidence, not an applied edit.

    **Freshness / evidence metadata (SD1)**
    Every precedent now carries retrieval-time, content-hash, tier, freshness
    status, and deterministic selection reasons so downstream consumers can
    audit why a particular precedent was selected and whether its cached data
    is still current relative to the tier's TTL.
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

    # ── freshness / evidence metadata (SD1) ─────────────────────────────────
    retrieval_time: str = ""          # ISO-8601 timestamp of source retrieval
    content_hash: str = ""            # SHA-256 hex digest of source content
    query_transform_trace: str = ""   # how the query was transformed for this tier
    tier: str = ""                    # evidence tier (e.g. "web", "hivemind")
    freshness_status: str = "unknown" # "fresh" | "stale" | "unknown"
    selection_reasons: tuple[str, ...] = ()  # deterministic selection rationale

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
        # ── clamp freshness / evidence metadata ──────────────────────────
        object.__setattr__(
            self,
            "selection_reasons",
            tuple(str(v) for v in self.selection_reasons if str(v).strip()),
        )
        if self.tier not in _ALLOWED_EVIDENCE_TIERS:
            object.__setattr__(self, "tier", "")
        if self.freshness_status not in _ALLOWED_FRESHNESS_STATUSES:
            object.__setattr__(self, "freshness_status", "unknown")

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
        # ── freshness / evidence metadata ──────────────────────────────────
        if self.retrieval_time:
            payload["retrieval_time"] = self.retrieval_time
        if self.content_hash:
            payload["content_hash"] = self.content_hash
        if self.query_transform_trace:
            payload["query_transform_trace"] = self.query_transform_trace
        if self.tier:
            payload["tier"] = self.tier
        if self.freshness_status != "unknown":
            payload["freshness_status"] = self.freshness_status
        if self.selection_reasons:
            payload["selection_reasons"] = list(self.selection_reasons)
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

    plan: ClassifyDecision | None = None
    research: ResearchResult | None = None
    implementation: ImplementationResult | None = None
    deepseek_usage: dict[str, Any] = field(default_factory=dict)
    deepseek_est_cost_usd: float | None = None
    deepseek_cost_basis: str | None = None
    # Truthful classification lifecycle signal: "failed" means classify raised
    # (the plan is then None — no invented respond_only placeholder). Empty
    # string means the signal was not recorded (legacy paths).
    classification_status: str = ""
    # Canonical per-call evidence for every successful and failed model attempt
    # observed across classify, implement/batch, and reply.
    model_attempts: tuple[dict[str, Any], ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "deepseek_usage",
            MappingProxyType({
                str(k): _freeze_jsonish(v)
                for k, v in coerce_deepseek_usage(self.deepseek_usage).items()
            }),
        )
        object.__setattr__(
            self,
            "model_attempts",
            tuple(_freeze_jsonish(item) for item in coerce_model_attempts(self.model_attempts)),
        )

    @property
    def model_response(self) -> dict[str, Any] | None:
        """Compatibility view derived solely from canonical ``model_attempts``."""
        if not self.model_attempts:
            return None
        return {
            "attempts": [_thaw_jsonish(item) for item in self.model_attempts]
        }

    def to_dict(self) -> dict[str, Any]:
        inner: dict[str, Any] = {}
        if self.plan is not None:
            plan_payload = self.plan.to_dict()
            route = _public_route_for_plan(self.plan)
            plan_payload["route"] = route
            task = self.plan.effective_task
            if task:
                plan_payload["task"] = task
            inner["plan"] = plan_payload
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
        if self.classification_status:
            inner["classification_status"] = self.classification_status
        inner["model_attempts"] = [
            _thaw_jsonish(item) for item in self.model_attempts
        ]
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
        reply = result.reply or result.failure_message or ""
        warnings: list[str] = []

        if plan is None:
            # Failed classification has NO decision (G0): do not invent a
            # route/task/intent.  The classification evidence stays empty and
            # the envelope carries no disposition.
            classification: dict[str, Any] = {}
            route = ""
            disposition = ""
        else:
            route = _public_route_for_plan(plan)
            classification = {
                "route": route,
                "task": plan.effective_task,
                "intent": plan.intent,
                "plan_summary": plan.plan_summary,
            }
            if plan.route and plan.route != route:
                classification["disposition"] = plan.route
            disposition = plan.route or plan.effective_route

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
            disposition=disposition,
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
    "runtime_dependencies",
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
        payload["model_attempts"] = [
            _thaw_jsonish(item) for item in self.report.model_attempts
        ]
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
    "ManifestBoundaryAnchor",
    "ManifestInquiryCoverage",
    "ManifestInternalEdge",
    "ManifestNode",
    "ManifestOversized",
    "ManifestValidation",
    "ModelAttemptEvidence",
    "TopologyFindings",
    "TopologyManifest",
    "WorkflowSlice",
    "adaptation_plan_actionability",
    "adaptation_plan_actionability_payload",
    "build_topology_manifest",
    "coerce_model_attempts",
    "is_actionable_adaptation_plan",
    "normalize_model_endpoint",
    "redact_model_preview",
    "warning_detail_from_exception",
]
