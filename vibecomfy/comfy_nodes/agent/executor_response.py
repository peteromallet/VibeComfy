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
    "candidateGraph",
    "candidateTransaction",
    "acceptedBatch",
}

# Legacy alias kept for callers and ledger traceability.
_CLARIFY_FORBIDDEN_KEYS = _NON_APPLYABLE_FORBIDDEN_KEYS


def _format_clarify_markdown(message: Any) -> str:
    text = message.strip() if isinstance(message, str) else ""
    if not text:
        text = "What detail should I use before continuing?"
    return text


def _strip_non_applyable_forbidden_fields(value: Any) -> Any:
    """Strip product carriers while retaining typed terminal evidence.

    Eligibility booleans and the authority receipt are contract evidence, not
    candidate carriers.  They must survive browser/HTTP serialization so the
    client can prove that a terminal is non-applyable.
    """
    if isinstance(value, dict):
        stripped: dict[str, Any] = {}
        preserve_terminal_evidence = (
            "terminal_state" in value or "authority_receipt" in value
        )
        for key, item in value.items():
            if key == "authority_receipt":
                # Receipt hashes are authority evidence, not product aliases.
                stripped[key] = item
                continue
            if key in _NON_APPLYABLE_FORBIDDEN_KEYS or key.startswith("candidate_"):
                continue
            if key in {"apply_eligible", "apply_allowed", "canvas_apply_allowed", "queue_allowed"}:
                if preserve_terminal_evidence:
                    stripped[key] = False
                continue
            if key in {"apply_eligibility", "eligibility"}:
                if preserve_terminal_evidence:
                    stripped[key] = {"applyable": False, "reason": "terminal_not_applyable"}
                continue
            stripped[key] = item if key == "audit" else _strip_non_applyable_forbidden_fields(item)
        return stripped
    if isinstance(value, list):
        return [_strip_non_applyable_forbidden_fields(item) for item in value]
    if isinstance(value, tuple):
        return tuple(_strip_non_applyable_forbidden_fields(item) for item in value)
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
    sanitized_outcome = {
        "kind": "clarify",
        "question": markdown,
        "clarification": {"message": markdown},
    }
    if isinstance(outcome, Mapping):
        for key in ("missing_classes", "options"):
            value = outcome.get(key)
            if isinstance(value, (list, tuple)) and value:
                sanitized_outcome[key] = list(value)
    sanitized["outcome"] = sanitized_outcome
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
    # One final shared normalization pass closes combinations introduced by
    # compatibility aliases or by a custom result object's serializer.
    from vibecomfy.executor.contracts import normalize_terminal_envelope

    merged = normalize_terminal_envelope(merged)
    # Batch 10 fix: "claims ⊆ Δ" is enforced on the product path.  The reply
    # may only claim changes the accepted Δ actually landed; invalid claims
    # are stripped from the response (change_details.operations and
    # outcome.changes) and recorded as violations.
    from vibecomfy.executor.contracts import validate_reply_change_claims

    violations = validate_reply_change_claims(merged)
    if violations:
        merged["claims_violations"] = violations
        merged = _strip_invalid_change_claims(merged, violations)
    return merged


def _strip_invalid_change_claims(payload: Mapping[str, Any], violations: list[str]) -> dict[str, Any]:
    """Strip change claims that are not in the accepted Δ.

    ``change_details.operations`` / ``outcome.changes`` /
    ``internal_outcome.changes`` items whose ``(uid, field_path)`` produced a
    violation are removed so the serialized response never claims an edit the
    accepted Δ did not land.
    """
    invalid_keys: set[tuple[str, str]] = set()
    for violation in violations:
        import re

        match = re.search(r"\(([^,]+), ([^)]+)\)", violation)
        if match:
            invalid_keys.add((match.group(1).strip(), match.group(2).strip()))
    if not invalid_keys:
        return dict(payload)
    result = dict(payload)
    for key in ("change_details", "outcome", "internal_outcome"):
        section = result.get(key)
        if not isinstance(section, Mapping):
            continue
        cleaned = dict(section)
        for list_key in ("operations", "changes"):
            items = cleaned.get(list_key)
            if not isinstance(items, list):
                continue
            kept = [
                item
                for item in items
                if not (
                    isinstance(item, Mapping)
                    and (str(item.get("uid")), str(item.get("field_path"))) in invalid_keys
                )
            ]
            cleaned[list_key] = kept
        result[key] = cleaned
    return result


_serialize_executor_result = serialize_executor_result
