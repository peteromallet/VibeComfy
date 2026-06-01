from __future__ import annotations

import json

import pytest

from vibecomfy.comfy_nodes.agent_contracts import (
    CANVAS_APPLY_GATE_NAMES,
    DEFAULT_GATE_NAMES,
    FAILURE_SPECS,
    SCAN_CODE_FAILURE_KIND,
    FailureEnvelope,
    FailureKind,
    TurnContext,
    classify_failure,
    failure_envelope,
)
from vibecomfy.security.agent_generated_loader import (
    AgentGeneratedLoadError,
    ScanFailure,
    ScanReport,
)


def test_failure_kind_enum_matches_closed_contract_exactly() -> None:
    assert [kind.value for kind in FailureKind] == [
        "SyntaxError",
        "ASTScanFailure",
        "OversizedPayload",
        "MalformedModelJSON",
        "MissingRequiredField",
        "ProviderError",
        "AuthError",
        "TimeoutError",
        "ValidationError",
        "UnsatisfiedInputError",
        "RefusedEmit",
        "EditorAheadConflict",
        "StaleStateMismatch",
        "UnsupportedNonDAG",
        "SchemaLessQueueBlocker",
        "LowConfidenceQueueBlocker",
        "EditorOnlyNodeQueueBlocker",
        "AuditWriteWarning",
        "AuditWriteFailure",
    ]


def test_turn_context_defaults_all_named_gates_false() -> None:
    context = TurnContext(session_id="s1")

    assert tuple(context.gate_results) == DEFAULT_GATE_NAMES
    assert context.gate_snapshot() == {name: False for name in DEFAULT_GATE_NAMES}
    assert context.canvas_apply_allowed is False
    assert context.apply_allowed is False
    assert context.queue_allowed is False


def test_turn_context_preserves_protocol_identity_fields() -> None:
    context = TurnContext(
        session_id="s1",
        turn_id="0007",
        baseline_turn_id="0006",
        client_graph_hash="submit-hash",
        idempotency_key="accept:s1:0007:abc",
    )

    assert context.session_id == "s1"
    assert context.turn_id == "0007"
    assert context.baseline_turn_id == "0006"
    assert context.client_graph_hash == "submit-hash"
    assert context.idempotency_key == "accept:s1:0007:abc"
    assert context.gate_snapshot() == {name: False for name in DEFAULT_GATE_NAMES}


def test_scan_code_mapping_is_exact_and_closed() -> None:
    assert dict(SCAN_CODE_FAILURE_KIND) == {
        "syntax_error": FailureKind.SYNTAX_ERROR,
        "source_too_large": FailureKind.OVERSIZED_PAYLOAD,
        "source_type": FailureKind.VALIDATION_ERROR,
        "forbidden_node": FailureKind.AST_SCAN_FAILURE,
        "forbidden_import": FailureKind.AST_SCAN_FAILURE,
        "forbidden_name": FailureKind.AST_SCAN_FAILURE,
        "forbidden_call": FailureKind.AST_SCAN_FAILURE,
        "dunder_access": FailureKind.AST_SCAN_FAILURE,
    }


def test_classify_failure_uses_loader_scan_mappings() -> None:
    context = TurnContext(session_id="s1", turn_id="0001", baseline_turn_id="0000")
    load_error = AgentGeneratedLoadError(
        "scan failed",
        report=ScanReport(
            ok=False,
            failures=(ScanFailure(code="source_type", message="source must be str"),),
        ),
    )

    failure = classify_failure("load_python", load_error, context)

    assert failure.kind is FailureKind.VALIDATION_ERROR
    assert failure.stage == "load_python"
    assert failure.session_id == "s1"
    assert failure.turn_id == "0001"
    assert failure.baseline_turn_id == "0000"
    assert failure.canvas_apply_allowed is False
    assert failure.queue_allowed is False
    assert failure.apply_allowed is False
    assert failure.agent_failure_context["scan_code"] == "source_type"


def test_failure_envelope_shape_is_frozen_and_uses_apply_alias() -> None:
    context = TurnContext(session_id="s1", turn_id="0001")
    failure = failure_envelope(
        FailureKind.MISSING_REQUIRED_FIELD,
        "agent_response",
        context,
        agent_failure_context={"explanation": "missing python"},
    )

    payload = failure.to_dict()

    assert payload["ok"] is False
    assert payload["kind"] == "MissingRequiredField"
    assert payload["stage"] == "agent_response"
    assert payload["session_id"] == "s1"
    assert payload["turn_id"] == "0001"
    assert payload["baseline_turn_id"] is None
    assert payload["canvas_apply_allowed"] is False
    assert payload["apply_allowed"] is False
    assert payload["queue_allowed"] is False
    assert payload["graph_unchanged"] is True
    assert payload["message"] == payload["user_facing_message"]
    assert payload["agent_failure_context"] == {"explanation": "missing python"}
    assert payload["audit_ref"] is None
    assert payload["audit_error"] is None

    with pytest.raises(TypeError):
        failure.agent_failure_context["other"] = "nope"  # type: ignore[index]


# ---------------------------------------------------------------------------
# T2: Focused contract tests — classifier stability, scan-code mappings,
# failure envelope shape, gate defaults, apply_allowed == canvas_apply_allowed
# ---------------------------------------------------------------------------


# --- Gate default stability ---


def test_all_design_gates_present_and_distinct() -> None:
    """Every design-level named gate exists and is distinct."""
    assert len(DEFAULT_GATE_NAMES) == 7
    assert len(set(DEFAULT_GATE_NAMES)) == 7
    assert set(DEFAULT_GATE_NAMES) == {
        "python_load_ok",
        "ir_validate_ok",
        "ui_emit_ok",
        "ui_fidelity_ok",
        "ui_load_safe_ok",
        "queue_validate_ok",
        "state_match_ok",
    }


def test_canvas_apply_subset_is_proper_subset_of_all_gates() -> None:
    """canvas_apply_allowed checks every gate except queue_validate_ok."""
    assert set(CANVAS_APPLY_GATE_NAMES) == set(DEFAULT_GATE_NAMES) - {"queue_validate_ok"}
    assert "queue_validate_ok" not in CANVAS_APPLY_GATE_NAMES


def test_turn_context_set_gate_rejects_unknown_name() -> None:
    context = TurnContext(session_id="s1")
    with pytest.raises(KeyError, match="Unknown gate"):
        context.set_gate("nonexistent_gate", True)


def test_turn_context_apply_allowed_equals_canvas_apply_allowed() -> None:
    """Explicit check: apply_allowed IS canvas_apply_allowed for TurnContext."""
    context = TurnContext(session_id="s1")
    assert context.apply_allowed is context.canvas_apply_allowed
    assert context.apply_allowed is False

    # After setting all canvas-apply gates true, both should flip
    for name in CANVAS_APPLY_GATE_NAMES:
        context.set_gate(name, True, evidence={"test": True})
    assert context.canvas_apply_allowed is True
    assert context.apply_allowed is True
    assert context.apply_allowed is context.canvas_apply_allowed


def test_queue_allowed_requires_queue_validate_ok() -> None:
    """queue_allowed = canvas_apply_allowed AND queue_validate_ok."""
    context = TurnContext(session_id="s1")
    for name in CANVAS_APPLY_GATE_NAMES:
        context.set_gate(name, True)
    # canvas_apply_allowed is now true, but queue_validate_ok still false
    assert context.canvas_apply_allowed is True
    assert context.queue_allowed is False

    context.set_gate("queue_validate_ok", True)
    assert context.queue_allowed is True


# --- Failure envelope shape invariants ---


def test_failure_envelope_apply_allowed_equals_canvas_apply_allowed() -> None:
    """apply_allowed alias on FailureEnvelope mirrors canvas_apply_allowed."""
    fe = failure_envelope(FailureKind.VALIDATION_ERROR, "validate", None)
    assert fe.apply_allowed is fe.canvas_apply_allowed
    assert fe.apply_allowed is False


def test_failure_envelope_to_dict_excludes_null_turn_id() -> None:
    """When turn_id is None it is not serialized into the dict payload."""
    fe = failure_envelope(FailureKind.VALIDATION_ERROR, "load_python", None)
    payload = fe.to_dict()
    assert "turn_id" not in payload
    assert payload["baseline_turn_id"] is None


def test_failure_envelope_to_dict_includes_turn_id_when_present() -> None:
    ctx = TurnContext(session_id="s1", turn_id="0007", baseline_turn_id="0006")
    fe = failure_envelope(FailureKind.VALIDATION_ERROR, "load_python", ctx)
    payload = fe.to_dict()
    assert payload["turn_id"] == "0007"
    assert payload["baseline_turn_id"] == "0006"


def test_failure_envelope_always_has_ok_false() -> None:
    """Every FailureEnvelope reports ok=False."""
    for kind in FailureKind:
        fe = failure_envelope(kind, "any_stage", None)
        assert fe.ok is False
        assert fe.to_dict()["ok"] is False


def test_failure_envelope_to_dict_has_all_required_keys() -> None:
    """The serialized dict contains every consumer-facing key."""
    fe = failure_envelope(FailureKind.SYNTAX_ERROR, "load_python")
    payload = fe.to_dict()
    required_keys = {
        "ok", "kind", "stage", "session_id", "baseline_turn_id",
        "canvas_apply_allowed", "apply_allowed", "queue_allowed",
        "graph_unchanged", "retryable", "next_action",
        "message", "user_facing_message", "agent_failure_context",
        "audit_ref", "audit_error",
    }
    present = set(payload.keys())
    assert required_keys.issubset(present)


def test_failure_envelope_message_equals_user_facing_message_for_all_kinds() -> None:
    """message is an alias for user_facing_message on every FailureKind."""
    for kind in FailureKind:
        fe = failure_envelope(kind, "any_stage", None)
        assert fe.message == fe.user_facing_message
        assert fe.to_dict()["message"] == fe.to_dict()["user_facing_message"]


def test_failure_envelope_is_fully_frozen() -> None:
    """Cannot mutate any field after construction."""
    fe = failure_envelope(FailureKind.VALIDATION_ERROR, "validate")
    with pytest.raises((TypeError, AttributeError)):
        fe.kind = FailureKind.SYNTAX_ERROR  # type: ignore[misc]
    with pytest.raises((TypeError, AttributeError)):
        fe.stage = "other"  # type: ignore[misc]
    with pytest.raises((TypeError, AttributeError)):
        fe.canvas_apply_allowed = True  # type: ignore[misc]


def test_failure_specs_cover_all_kinds() -> None:
    """Every FailureKind has an entry in FAILURE_SPECS."""
    for kind in FailureKind:
        assert kind in FAILURE_SPECS, f"{kind} missing from FAILURE_SPECS"


def test_failure_specs_retryable_and_graph_unchanged_are_booleans() -> None:
    """retryable and graph_unchanged are bools for every spec."""
    for kind, spec in FAILURE_SPECS.items():
        assert isinstance(spec.retryable, bool), f"{kind}: retryable not bool"
        assert isinstance(spec.graph_unchanged, bool), f"{kind}: graph_unchanged not bool"
        assert len(spec.next_action) > 0, f"{kind}: next_action empty"
        assert len(spec.user_facing_message) > 0, f"{kind}: user_facing_message empty"


# --- Scan-code mapping stability ---


def test_scan_code_mapping_keys_are_lower_snake_case() -> None:
    """All scan-code mapping keys are lower_snake_case strings."""
    for code in SCAN_CODE_FAILURE_KIND:
        assert code == code.lower()
        assert " " not in code
        assert code.isascii()


def test_scan_code_mapping_all_targets_are_valid_enum_members() -> None:
    """Every value in SCAN_CODE_FAILURE_KIND is a genuine FailureKind member."""
    for code, kind in SCAN_CODE_FAILURE_KIND.items():
        assert isinstance(kind, FailureKind), f"{code} -> {kind!r}"
        assert kind in FailureKind, f"{code} -> {kind} not in FailureKind"


def test_scan_code_mapping_is_immutable() -> None:
    """SCAN_CODE_FAILURE_KIND cannot be mutated."""
    with pytest.raises(TypeError):
        SCAN_CODE_FAILURE_KIND["new_code"] = FailureKind.SYNTAX_ERROR  # type: ignore[index]


# --- Classifier stability ---


def test_classify_auth_401_returns_auth_error() -> None:
    """HTTP 401 response classifies as AUTH_ERROR."""

    class MockResponse:
        status_code = 401

    class MockAuthError(Exception):
        def __init__(self) -> None:
            self.response = MockResponse()

    ctx = TurnContext(session_id="s1", turn_id="t1")
    fe = classify_failure("agent_response", MockAuthError(), ctx)
    assert fe.kind is FailureKind.AUTH_ERROR
    assert fe.stage == "agent_response"
    assert fe.agent_failure_context["http_status"] == 401


def test_classify_auth_403_returns_auth_error() -> None:
    """HTTP 403 response classifies as AUTH_ERROR."""

    class MockResponse:
        status_code = 403

    class MockAuthError(Exception):
        def __init__(self) -> None:
            self.response = MockResponse()

    ctx = TurnContext(session_id="s1", turn_id="t1")
    fe = classify_failure("agent_response", MockAuthError(), ctx)
    assert fe.kind is FailureKind.AUTH_ERROR
    assert fe.agent_failure_context["http_status"] == 403


def test_classify_auth_from_mapping_http_status() -> None:
    """Mapping with http_status=401 also classifies as AUTH_ERROR."""
    ctx = TurnContext(session_id="s1")
    fe = classify_failure("agent_response", {"http_status": 401, "message": "unauthorized"}, ctx)
    assert fe.kind is FailureKind.AUTH_ERROR
    assert fe.agent_failure_context["http_status"] == 401


def test_classify_auth_from_mapping_status_code() -> None:
    """Mapping with status_code=403 also classifies as AUTH_ERROR."""
    ctx = TurnContext(session_id="s1")
    fe = classify_failure("agent_response", {"status_code": 403, "message": "forbidden"}, ctx)
    assert fe.kind is FailureKind.AUTH_ERROR
    assert fe.agent_failure_context["http_status"] == 403


def test_classify_refused_emit_by_exception_name() -> None:
    """An exception named RefusedEmit classifies as REFUSED_EMIT."""

    class RefusedEmit(Exception):
        pass

    ctx = TurnContext(session_id="s1")
    fe = classify_failure("emit_ui", RefusedEmit("protected state"), ctx)
    assert fe.kind is FailureKind.REFUSED_EMIT
    assert fe.stage == "emit_ui"


def test_classify_editor_ahead_error_by_exception_name() -> None:
    """An exception named EditorAheadError classifies as EDITOR_AHEAD_CONFLICT."""

    class EditorAheadError(Exception):
        pass

    ctx = TurnContext(session_id="s1")
    fe = classify_failure("ingest", EditorAheadError("conflict"), ctx)
    assert fe.kind is FailureKind.EDITOR_AHEAD_CONFLICT
    assert fe.stage == "ingest"


def test_classify_timeout_by_exception_type() -> None:
    """A built-in TimeoutError classifies as TIMEOUT_ERROR."""
    ctx = TurnContext(session_id="s1")
    fe = classify_failure("agent_response", TimeoutError("timed out"), ctx)
    assert fe.kind is FailureKind.TIMEOUT_ERROR


def test_classify_timeout_by_name_containing_timeout() -> None:
    """An exception with 'timeout' in its name classifies as TIMEOUT_ERROR."""

    class RequestTimeout(Exception):
        pass

    ctx = TurnContext(session_id="s1")
    fe = classify_failure("agent_response", RequestTimeout("slow"), ctx)
    assert fe.kind is FailureKind.TIMEOUT_ERROR


def test_classify_agent_response_missing_python() -> None:
    """agent_response stage with 'missing' + 'python' -> MISSING_REQUIRED_FIELD."""
    ctx = TurnContext(session_id="s1")
    fe = classify_failure("agent_response", ValueError("missing python field"), ctx)
    assert fe.kind is FailureKind.MISSING_REQUIRED_FIELD


def test_classify_agent_response_json_decode_error() -> None:
    """JSONDecodeError in agent_response -> MALFORMED_MODEL_JSON."""
    ctx = TurnContext(session_id="s1")
    exc: json.JSONDecodeError
    try:
        json.loads("{bad")
    except json.JSONDecodeError as e:
        exc = e
    fe = classify_failure("agent_response", exc, ctx)
    assert fe.kind is FailureKind.MALFORMED_MODEL_JSON


def test_classify_agent_response_value_error_malformed() -> None:
    """Generic ValueError in agent_response -> MALFORMED_MODEL_JSON."""
    ctx = TurnContext(session_id="s1")
    fe = classify_failure("agent_response", ValueError("bad value"), ctx)
    assert fe.kind is FailureKind.MALFORMED_MODEL_JSON


def test_classify_agent_response_type_error_malformed() -> None:
    """TypeError in agent_response -> MALFORMED_MODEL_JSON."""
    ctx = TurnContext(session_id="s1")
    fe = classify_failure("agent_response", TypeError("bad type"), ctx)
    assert fe.kind is FailureKind.MALFORMED_MODEL_JSON


def test_classify_agent_response_provider_error_fallback() -> None:
    """Unrecognized error in agent_response stage falls back to PROVIDER_ERROR."""
    ctx = TurnContext(session_id="s1")
    fe = classify_failure("agent_response", RuntimeError("something unexpected"), ctx)
    assert fe.kind is FailureKind.PROVIDER_ERROR


def test_classify_ingest_stale_state() -> None:
    """Ingest stage with 'stale' in message -> STALE_STATE_MISMATCH."""
    ctx = TurnContext(session_id="s1")
    fe = classify_failure("ingest", RuntimeError("stale state detected"), ctx)
    assert fe.kind is FailureKind.STALE_STATE_MISMATCH


def test_classify_ingest_non_dag() -> None:
    """Ingest stage with 'non-dag' in message -> UNSUPPORTED_NON_DAG."""
    ctx = TurnContext(session_id="s1")
    fe = classify_failure("ingest", RuntimeError("non-dag graph unsupported"), ctx)
    assert fe.kind is FailureKind.UNSUPPORTED_NON_DAG


def test_classify_ingest_unsupported() -> None:
    """Ingest stage with 'unsupported' in message -> UNSUPPORTED_NON_DAG."""
    ctx = TurnContext(session_id="s1")
    fe = classify_failure("ingest", RuntimeError("unsupported graph structure"), ctx)
    assert fe.kind is FailureKind.UNSUPPORTED_NON_DAG


def test_classify_ingest_fallback_missing_required_field() -> None:
    """Generic ingest error falls back to MISSING_REQUIRED_FIELD."""
    ctx = TurnContext(session_id="s1")
    fe = classify_failure("ingest", RuntimeError("something went wrong"), ctx)
    assert fe.kind is FailureKind.MISSING_REQUIRED_FIELD


def test_classify_validate_unsatisfied_input() -> None:
    """Validate stage with 'missing input' -> UNSATISFIED_INPUT_ERROR."""
    ctx = TurnContext(session_id="s1")
    fe = classify_failure("validate", RuntimeError("missing input 'image'"), ctx)
    assert fe.kind is FailureKind.UNSATISFIED_INPUT_ERROR


def test_classify_validate_required_input() -> None:
    """Validate stage with 'required input' -> UNSATISFIED_INPUT_ERROR."""
    ctx = TurnContext(session_id="s1")
    fe = classify_failure("validate", RuntimeError("required input absent"), ctx)
    assert fe.kind is FailureKind.UNSATISFIED_INPUT_ERROR


def test_classify_validate_generic() -> None:
    """Generic validate error -> VALIDATION_ERROR."""
    ctx = TurnContext(session_id="s1")
    fe = classify_failure("validate", RuntimeError("bad graph"), ctx)
    assert fe.kind is FailureKind.VALIDATION_ERROR


def test_classify_queue_validate_schema_less() -> None:
    """Queue validate with 'schema' -> SCHEMA_LESS_QUEUE_BLOCKER."""
    ctx = TurnContext(session_id="s1")
    fe = classify_failure("queue_validate", RuntimeError("schema missing"), ctx)
    assert fe.kind is FailureKind.SCHEMA_LESS_QUEUE_BLOCKER


def test_classify_queue_validate_editor_only() -> None:
    """Queue validate with 'editor-only' -> EDITOR_ONLY_NODE_QUEUE_BLOCKER."""
    ctx = TurnContext(session_id="s1")
    fe = classify_failure("queue_validate", RuntimeError("editor-only node present"), ctx)
    assert fe.kind is FailureKind.EDITOR_ONLY_NODE_QUEUE_BLOCKER


def test_classify_queue_validate_editor_only_space() -> None:
    """Queue validate with 'editor only' (space) -> EDITOR_ONLY_NODE_QUEUE_BLOCKER."""
    ctx = TurnContext(session_id="s1")
    fe = classify_failure("queue_validate", RuntimeError("editor only node blocks queue"), ctx)
    assert fe.kind is FailureKind.EDITOR_ONLY_NODE_QUEUE_BLOCKER


def test_classify_queue_validate_low_confidence() -> None:
    """Generic queue_validate error -> LOW_CONFIDENCE_QUEUE_BLOCKER."""
    ctx = TurnContext(session_id="s1")
    fe = classify_failure("queue_validate", RuntimeError("confidence too low"), ctx)
    assert fe.kind is FailureKind.LOW_CONFIDENCE_QUEUE_BLOCKER


def test_classify_audit_warning() -> None:
    """Audit stage with 'warning' -> AUDIT_WRITE_WARNING."""
    ctx = TurnContext(session_id="s1")
    fe = classify_failure("audit", RuntimeError("audit write warning: disk near full"), ctx)
    assert fe.kind is FailureKind.AUDIT_WRITE_WARNING


def test_classify_audit_failure() -> None:
    """Audit stage without 'warning' -> AUDIT_WRITE_FAILURE."""
    ctx = TurnContext(session_id="s1")
    fe = classify_failure("audit", RuntimeError("audit disk full"), ctx)
    assert fe.kind is FailureKind.AUDIT_WRITE_FAILURE


def test_classify_fallback_unknown_stage() -> None:
    """Completely unknown stage falls back to VALIDATION_ERROR."""
    ctx = TurnContext(session_id="s1")
    fe = classify_failure("unknown_stage", RuntimeError("something"), ctx)
    assert fe.kind is FailureKind.VALIDATION_ERROR


# --- Failure envelope from TurnContext-derived context ---


def test_failure_envelope_from_turn_context_uses_explicit_params_not_context() -> None:
    """failure_envelope canvas_apply_allowed/queue_allowed come from explicit
    parameters, NOT auto-derived from the TurnContext gate state.  The context
    only provides session/turn/baseline IDs."""
    ctx = TurnContext(session_id="s1", turn_id="t1")
    for name in CANVAS_APPLY_GATE_NAMES:
        ctx.set_gate(name, True)
    ctx.set_gate("queue_validate_ok", True)

    # Without explicit params, defaults to False (does NOT read context gates)
    fe = failure_envelope(FailureKind.AUDIT_WRITE_WARNING, "audit", ctx)
    assert fe.canvas_apply_allowed is False
    assert fe.apply_allowed is False
    assert fe.queue_allowed is False

    # With explicit params, those are used
    fe2 = failure_envelope(
        FailureKind.AUDIT_WRITE_WARNING, "audit", ctx,
        canvas_apply_allowed=True, queue_allowed=True,
    )
    assert fe2.canvas_apply_allowed is True
    assert fe2.apply_allowed is True
    assert fe2.queue_allowed is True


def test_failure_envelope_explicit_flags_override_context() -> None:
    """Explicit canvas_apply_allowed/queue_allowed params override the context."""
    ctx = TurnContext(session_id="s1")
    fe = failure_envelope(
        FailureKind.VALIDATION_ERROR,
        "validate",
        ctx,
        canvas_apply_allowed=True,
        queue_allowed=True,
    )
    assert fe.canvas_apply_allowed is True
    assert fe.queue_allowed is True


# --- failure_envelope with string-kind coercion ---


def test_failure_envelope_accepts_string_kind() -> None:
    """failure_envelope coerces a string to FailureKind."""
    fe = failure_envelope("SyntaxError", "load_python", None)
    assert fe.kind is FailureKind.SYNTAX_ERROR
    assert fe.to_dict()["kind"] == "SyntaxError"


def test_failure_envelope_invalid_string_kind_raises() -> None:
    """An unrecognised string raises ValueError from the Enum constructor."""
    with pytest.raises(ValueError):
        failure_envelope("NotAKind", "load_python", None)
