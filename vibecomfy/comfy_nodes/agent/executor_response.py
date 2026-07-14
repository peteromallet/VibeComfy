from __future__ import annotations

from typing import Any, Mapping


def _to_serializable(result: Any) -> Any:
    """Convert an executor result to a plain JSON-compatible mapping."""
    if result is None:
        return {}
    if isinstance(result, dict):
        return result
    if hasattr(result, "to_dict") and callable(result.to_dict):
        return result.to_dict()
    return {"error": "Non-serializable result", "repr": repr(result)}


def _executor_compatibility_fields(payload: Mapping[str, Any]) -> dict[str, Any]:
    """Build presentation compatibility fields from a canonical executor envelope.

    Only presentation aliases (``message``, ``candidate_graph``,
    ``graph_unchanged``, ``clarification_required``,
    ``clarification_message``) are synthesized.  The ``outcome`` field is
    **never** derived from ``candidate`` or ``apply_eligible`` — it is
    preserved exclusively when durable response data already supplied it
    (via the merge in ``serialize_executor_result``).  Authority fields
    (``apply_eligibility``, ``eligibility``, ``apply_allowed``,
    ``canvas_apply_allowed``, ``queue_allowed``) are likewise never
    synthesized.
    """
    reply = payload.get("reply")
    message = reply if isinstance(reply, str) else ""
    route = payload.get("route") if isinstance(payload.get("route"), str) else "respond"
    candidate = payload.get("candidate") if isinstance(payload.get("candidate"), Mapping) else None
    candidate_graph = (
        candidate.get("graph")
        if isinstance(candidate, Mapping) and isinstance(candidate.get("graph"), dict)
        else None
    )

    compatibility: dict[str, Any] = {
        "message": message,
    }

    # Presentation aliases only — outcome and authority fields are never synthesized.
    if candidate_graph is not None:
        compatibility["candidate_graph"] = candidate_graph
    compatibility["graph_unchanged"] = candidate_graph is None

    if route == "clarify":
        compatibility["clarification_required"] = True
        compatibility["clarification_message"] = message
    return compatibility


_NON_APPLYABLE_FORBIDDEN_KEYS = {
    "candidate",
    "graph",
    "candidate_graph",
    "apply_eligible",
    "apply_eligibility",
    "eligibility",
    "apply_allowed",
    "canvas_apply_allowed",
    "queue_allowed",
}

# Legacy alias kept for callers and ledger traceability.
_CLARIFY_FORBIDDEN_KEYS = _NON_APPLYABLE_FORBIDDEN_KEYS


def _format_clarify_markdown(message: Any) -> str:
    text = message.strip() if isinstance(message, str) else ""
    if not text:
        text = "What detail should I use before continuing?"
    return text


def _strip_non_applyable_forbidden_fields(value: Any) -> Any:
    """Strip candidate/apply/eligibility fields from non-applyable route envelopes."""
    if isinstance(value, dict):
        stripped: dict[str, Any] = {}
        for key, item in value.items():
            if key in _NON_APPLYABLE_FORBIDDEN_KEYS or key.startswith("candidate_"):
                continue
            stripped[key] = _strip_non_applyable_forbidden_fields(item)
        return stripped
    if isinstance(value, list):
        return [_strip_non_applyable_forbidden_fields(item) for item in value]
    return value


def _sanitize_clarify_payload(payload: Mapping[str, Any]) -> dict[str, Any]:
    sanitized = dict(payload)
    outcome = sanitized.get("outcome")
    route = sanitized.get("route")
    is_clarify = (
        route == "clarify"
        or (
            isinstance(outcome, Mapping)
            and outcome.get("kind") == "clarify"
        )
    )
    if not is_clarify:
        return sanitized

    message = (
        sanitized.get("reply")
        or sanitized.get("message")
        or (outcome.get("question") if isinstance(outcome, Mapping) else "")
    )
    markdown = _format_clarify_markdown(message)
    if "reply" in sanitized:
        sanitized["reply"] = markdown
    sanitized["message"] = markdown
    sanitized["clarification_required"] = True
    sanitized["clarification_message"] = markdown
    sanitized["outcome"] = {
        "kind": "clarify",
        "question": markdown,
        "clarification": {"message": markdown},
    }
    internal_outcome = sanitized.get("internal_outcome")
    if isinstance(internal_outcome, Mapping) and internal_outcome.get("kind") == "clarify":
        sanitized["internal_outcome"] = {"kind": "clarify", "question": markdown}
    return _strip_non_applyable_forbidden_fields(sanitized)


_NON_APPLYABLE_ROUTES = frozenset({"clarify", "respond", "inspect", "research", "requires_custom_nodes"})
_NON_APPLYABLE_OUTCOMES = frozenset({"clarify", "noop", "requires_custom_nodes"})


def serialize_executor_result(result: Any) -> dict[str, Any]:
    """Serialise an executor result, preferring durable envelope fields.

    Compatibility fields are layered under durable fields so the canonical
    edit-envelope shape (``session_id``, ``turn_id``, ``outcome``,
    ``apply_eligibility``, etc.) always wins.  Non-applyable routes
    (clarify/respond/inspect/research/requires_custom_nodes) have
    candidate/apply fields stripped; clarify routes additionally receive
    clarification-specific formatting.
    """
    serialized = _to_serializable(result)
    if not isinstance(serialized, dict):
        serialized = {"ok": False, "error": "Non-dict executor result."}
    compatibility = _executor_compatibility_fields(serialized)
    merged = {**compatibility, **serialized}
    route = merged.get("route") if isinstance(merged.get("route"), str) else ""
    outcome = merged.get("outcome")
    is_clarify = (
        route == "clarify"
        or (isinstance(outcome, Mapping) and outcome.get("kind") == "clarify")
    )
    outcome_kind = outcome.get("kind") if isinstance(outcome, Mapping) else None
    if route in _NON_APPLYABLE_ROUTES or outcome_kind in _NON_APPLYABLE_OUTCOMES:
        merged = _strip_non_applyable_forbidden_fields(merged)
    if is_clarify:
        merged = _sanitize_clarify_payload(merged)
    return merged


_serialize_executor_result = serialize_executor_result
