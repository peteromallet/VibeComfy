from __future__ import annotations

import json

import pytest

from vibecomfy.comfy_nodes.agent.contracts import (
    AGENT_EDIT_TURN_CONTRACT_VERSION,
    CANVAS_APPLY_GATE_NAMES,
    DEFAULT_GATE_NAMES,
    FAILURE_HINT_KEYS,
    DiagnosticRecord,
    FAILURE_SPECS,
    INTERNAL_TO_PUBLIC_OUTCOME,
    PUBLIC_OUTCOME_KINDS,
    PLAN_VALIDATE_GATE_NAME,
    REBASELINE_RECOVERY_FIELDS,
    SCAN_CODE_FAILURE_KIND,
    AgentError,
    ApplyCandidate,
    ApplyEligibility,
    ArtifactRef,
    FailureEnvelope,
    FailureKind,
    FieldChange as ContractFieldChange,
    ProviderStatus,
    StageResult,
    StageSnapshot,
    TURN_OUTCOME_KINDS,
    TurnContext,
    TurnIdentity,
    TurnOutcome,
    classify_failure,
    derive_apply_candidate_key,
    ensure_agent_edit_response_contract,
    derive_pending_response_key,
    failure_envelope,
    product_failure_envelope_fields,
    public_chat_rehydrate_payload,
    public_latest_candidate,
    public_response_details,
    public_session_json_payload,
    public_outcome_from_turn_outcome,
    repair_field_changes,
    success_envelope,
    turn_envelope,
)
from vibecomfy.porting.edit.types import FieldChange
from vibecomfy.security.agent_generated_loader import (
    AgentGeneratedLoadError,
    ScanFailure,
    ScanReport,
)


EXPECTED_REBASELINE_RECOVERY_FIELDS = (
    "action",
    "endpoint",
    "reason",
    "last_known_baseline_graph_hash",
    "submit_graph_hash",
    "submit_structural_graph_hash",
    "client_graph_hash",
    "client_structural_graph_hash",
)

EXPECTED_SCOPED_ACCEPT_RECOVERY_FIELDS = (
    "action",
    "endpoint",
    "reason",
    "turn_id",
    "submit_graph_hash",
    "candidate_graph_hash",
)


def _json_paths_containing(value: object, needle: str, path: str = "$") -> list[str]:
    if isinstance(value, dict):
        paths: list[str] = []
        for key, item in value.items():
            paths.extend(_json_paths_containing(item, needle, f"{path}.{key}"))
        return paths
    if isinstance(value, list):
        paths = []
        for index, item in enumerate(value):
            paths.extend(_json_paths_containing(item, needle, f"{path}[{index}]"))
        return paths
    if isinstance(value, str) and needle in value:
        return [path]
    return []


def _json_key_paths(value: object, forbidden_keys: set[str], path: str = "$") -> list[str]:
    if isinstance(value, dict):
        paths: list[str] = []
        for key, item in value.items():
            child_path = f"{path}.{key}"
            if key in forbidden_keys:
                paths.append(child_path)
            paths.extend(_json_key_paths(item, forbidden_keys, child_path))
        return paths
    if isinstance(value, list):
        paths = []
        for index, item in enumerate(value):
            paths.extend(_json_key_paths(item, forbidden_keys, f"{path}[{index}]"))
        return paths
    return []


def _assert_public_projection_has_no_forbidden_sentinels(value: object) -> None:
    forbidden_keys = {
        "audit_path",
        "audit_ref",
        "batch_turns",
        "budget",
        "budget_trace",
        "debug_payload",
        "detail_json_path",
        "path",
        "prompt",
        "provider_diagnostics",
        "raw_prompt",
        "raw_session_state",
        "request_path",
        "response_path",
    }
    assert _json_key_paths(value, forbidden_keys) == []
    assert _json_paths_containing(value, "SECRET_PUBLIC_PROJECTION_SENTINEL") == []


def test_canonical_backend_contract_objects_serialize_snake_case() -> None:
    identity = TurnIdentity(
        session_id="sess-1",
        turn_id="0007",
        baseline_turn_id="0006",
        idempotency_key="submit:key",
    )
    candidate = ApplyCandidate(
        state="candidate",
        graph={"nodes": [{"id": 1}], "links": []},
        graph_hash="candidate-hash",
        structural_graph_hash="candidate-structural-hash",
        baseline_graph_hash="baseline-hash",
        submit_graph_hash="submit-hash",
        submit_structural_graph_hash="submit-structural-hash",
        turn_identity=identity,
    )
    snapshot = StageSnapshot(
        stage="ui_emit",
        ok=True,
        blocking=False,
        duration_ms=12,
        gates={"ui_emit_ok": True},
        artifacts=(ArtifactRef(path="turns/0007/candidate.ui.json", sha256="abc"),),
        issues=({"code": "warning"},),
        value={"summary": ["ok"]},
    )
    provider = ProviderStatus(
        provider="arnold",
        provider_available=True,
        ready=True,
        model="gpt-5.1",
        route="openai-codex",
        message="ready",
        error={"detail": {"code": "none"}},
    )

    assert identity.to_dict() == {
        "session_id": "sess-1",
        "turn_id": "0007",
        "baseline_turn_id": "0006",
        "idempotency_key": "submit:key",
    }
    assert candidate.to_dict() == {
        "state": "candidate",
        "graph": {"nodes": [{"id": 1}], "links": []},
        "graph_hash": "candidate-hash",
        "structural_graph_hash": "candidate-structural-hash",
        "baseline_graph_hash": "baseline-hash",
        "submit_graph_hash": "submit-hash",
        "submit_structural_graph_hash": "submit-structural-hash",
        "turn_identity": identity.to_dict(),
    }
    assert snapshot.to_dict() == {
        "stage": "ui_emit",
        "ok": True,
        "blocking": False,
        "duration_ms": 12,
        "gates": {"ui_emit_ok": True},
        "artifacts": [
            {
                "path": "turns/0007/candidate.ui.json",
                "sha256": "abc",
                "byte_count": None,
                "preview": None,
            }
        ],
        "issues": [{"code": "warning"}],
        "value": {"summary": ["ok"]},
    }
    assert provider.to_dict() == {
        "provider": "arnold",
        "provider_available": True,
        "ready": True,
        "contract_version": AGENT_EDIT_TURN_CONTRACT_VERSION,
        "model": "gpt-5.1",
        "route": "openai-codex",
        "message": "ready",
        "error": {"detail": {"code": "none"}},
    }


def test_contract_boundary_reexports_field_change_and_reuses_failure_envelope() -> None:
    assert ContractFieldChange is FieldChange
    assert AgentError is FailureEnvelope

    change = ContractFieldChange(uid="n1", field_path="widgets.seed", old=1, new=2)
    assert change.to_dict() == {
        "uid": "n1",
        "field_path": "widgets.seed",
        "old": 1,
        "new": 2,
    }


def test_backend_contract_dataclasses_validate_and_freeze_boundaries() -> None:
    with pytest.raises(ValueError, match="Unknown Apply eligibility reason"):
        ApplyEligibility(applyable=False, reason="not_a_reason", message="blocked")
    with pytest.raises(ValueError, match="Unknown TurnOutcome kind"):
        TurnOutcome(kind="not_a_kind")
    with pytest.raises(ValueError, match="Only failure TurnOutcome"):
        TurnOutcome(kind="noop", failure_kind=FailureKind.TIMEOUT_ERROR)
    with pytest.raises(ValueError, match="Failure TurnOutcome requires"):
        TurnOutcome(kind="failure", failure_kind=FailureKind.TIMEOUT_ERROR)

    identity = TurnIdentity(session_id="sess-1", turn_id="0007")
    with pytest.raises((TypeError, AttributeError)):
        identity.turn_id = "0008"  # type: ignore[misc]

    candidate = ApplyCandidate(
        state="candidate",
        graph={"nodes": [{"id": "1"}]},
        graph_hash="candidate-hash",
        structural_graph_hash="structural-hash",
    )
    with pytest.raises(TypeError):
        candidate.graph["nodes"] = []  # type: ignore[index]
    with pytest.raises(TypeError):
        candidate.graph["nodes"][0]["id"] = "2"  # type: ignore[index]

    snapshot = StageSnapshot(
        stage="ui_emit",
        ok=True,
        blocking=False,
        gates={"ui_emit_ok": True},
        issues=({"detail": {"raw": "issue"}},),
        value={"nested": {"ok": True}},
    )
    with pytest.raises(TypeError):
        snapshot.gates["ui_emit_ok"] = False  # type: ignore[index]
    with pytest.raises(TypeError):
        snapshot.issues[0]["detail"]["raw"] = "mutated"  # type: ignore[index]
    with pytest.raises(TypeError):
        snapshot.value["nested"]["ok"] = False  # type: ignore[index]


def test_failure_contract_sanitizes_user_facing_payload_but_keeps_debug_details() -> None:
    raw_detail = "Provider stack trace: api_key=sk-secret token=leaked"
    failure = classify_failure(
        "agent_response",
        RuntimeError(raw_detail),
        TurnContext(session_id="s1", turn_id="0009"),
    )

    payload = failure.to_dict()
    product_payload = dict(payload)
    product_payload.update(product_failure_envelope_fields(failure))

    assert failure.kind is FailureKind.PROVIDER_ERROR
    assert raw_detail not in payload["message"]
    assert raw_detail not in payload["user_facing_message"]
    assert raw_detail not in product_payload["message"]
    assert raw_detail not in product_payload["user_facing_message"]
    assert raw_detail not in product_payload["outcome"]["next_action"]
    assert raw_detail not in product_payload["outcome"].get("agent_failure_context", {})
    assert raw_detail not in product_payload["agent_failure_context"].get("explanation", "")
    assert payload["agent_failure_context"]["explanation"] == raw_detail
    assert (
        product_payload["debug"]["failure"]["agent_failure_context"]["explanation"]
        == raw_detail
    )
    assert _json_paths_containing(product_payload, raw_detail) == [
        "$.debug.failure.agent_failure_context.explanation"
    ]


def test_boundary_only_key_derivation_helpers_are_stable() -> None:
    identity = TurnIdentity(session_id="sess-1", turn_id="0007", idempotency_key="submit:key")
    candidate = ApplyCandidate(
        state="candidate",
        graph={"nodes": []},
        graph_hash="candidate-hash",
        structural_graph_hash="candidate-structural-hash",
        turn_identity=identity,
    )

    assert derive_pending_response_key(identity) == "pending:sess-1:0007"
    assert derive_pending_response_key(
        {"session_id": "sess-1", "idempotency_key": "submit:key"}
    ) == "pending:sess-1:submit:key"
    assert derive_pending_response_key({}) == "pending:no-session:no-turn"
    assert derive_apply_candidate_key(candidate) == "candidate:sess-1:0007:candidate-hash"
    assert derive_apply_candidate_key({"graph_hash": "candidate-hash"}) == (
        "candidate:candidate-hash"
    )


def test_turn_identity_key_derivation_rejects_invalid_boundary_values() -> None:
    assert derive_pending_response_key(
        {"session_id": 123, "turn_id": 456, "idempotency_key": object()}
    ) == "pending:no-session:no-turn"

    assert derive_apply_candidate_key(
        {"graph_hash": 123, "turn_identity": {"session_id": "sess-1", "turn_id": 7}}
    ) == "candidate:no-graph-hash"
    assert derive_apply_candidate_key(
        {"graph_hash": "candidate-hash"},
        identity={"session_id": "sess-2", "turn_id": "0008"},
    ) == "candidate:sess-2:0008:candidate-hash"
    assert derive_apply_candidate_key(
        {
            "graph_hash": "candidate-hash",
            "turn_identity": {"session_id": "sess-1", "turn_id": "0007"},
        },
        identity={"session_id": "sess-2"},
    ) == "candidate:candidate-hash"


def test_stage_snapshot_can_be_built_from_stage_result_without_aliases() -> None:
    result = StageResult(
        stage="validate",
        ok=True,
        blocking=False,
        duration_ms=4,
        value={"count": 1},
        artifacts=(ArtifactRef(path="audit.json"),),
        issues=({"code": "info"},),
        gate_updates={"ir_validate_ok": True},
    )

    assert StageSnapshot.from_stage_result(result).to_dict() == {
        "stage": "validate",
        "ok": True,
        "blocking": False,
        "duration_ms": 4,
        "gates": {"ir_validate_ok": True},
        "artifacts": [
            {
                "path": "audit.json",
                "sha256": None,
                "byte_count": None,
                "preview": None,
            }
        ],
        "issues": [{"code": "info"}],
        "value": {"count": 1},
    }


def test_failure_kind_enum_matches_closed_contract_exactly() -> None:
    assert [kind.value for kind in FailureKind] == [
        "SyntaxError",
        "ASTScanFailure",
        "OversizedPayload",
        "MalformedModelJSON",
        "MissingRequiredField",
        "ProviderError",
        "ProviderCreditError",
        "AgentRuntimeUnavailable",
        "AuthError",
        "TimeoutError",
        "ValidationError",
        "UnsatisfiedInputError",
        "RefusedEmit",
        "EditorAheadConflict",
        "StaleStateMismatch",
        "UnsupportedNonDAG",
        "LoweringFailure",
        "SchemaLessQueueBlocker",
        "LowConfidenceQueueBlocker",
        "EditorOnlyNodeQueueBlocker",
        "AuditWriteWarning",
        "AuditWriteFailure",
        "BatchBudgetExhausted",
        "ClarificationRequired",
        "ModelMistake",
        "Unrepresentable",
        "SchemaGap",
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


def test_turn_outcome_kinds_are_closed_and_ordered() -> None:
    assert TURN_OUTCOME_KINDS == (
        "edit",
        "clarify",
        "edit+clarify",
        "failure",
        "noop",
        "budget",
    )


def test_public_outcome_kinds_are_closed_and_ordered() -> None:
    assert PUBLIC_OUTCOME_KINDS == (
        "candidate",
        "noop",
        "clarify",
        "error",
    )


def test_turn_outcome_to_dict_serializes_edit_and_clarify_discriminants() -> None:
    outcome = TurnOutcome.edit_and_clarify(
        changes=(
            FieldChange(
                uid="node-7",
                field_path="widgets.seed",
                old={"value": 7},
                new={"value": 9},
            ),
        ),
        question="Should I also rename the output prefix?",
    )

    assert outcome.to_dict() == {
        "kind": "edit+clarify",
        "changes": [
            {
                "uid": "node-7",
                "field_path": "widgets.seed",
                "old": {"value": 7},
                "new": {"value": 9},
            }
        ],
        "question": "Should I also rename the output prefix?",
    }


def test_turn_outcome_failure_to_dict_includes_required_discriminants() -> None:
    failure = failure_envelope(
        FailureKind.TIMEOUT_ERROR,
        "agent_response",
        TurnContext(session_id="s1", turn_id="0001"),
        agent_failure_context={"explanation": "provider timed out"},
    )

    assert TurnOutcome.from_failure(failure).to_dict() == {
        "kind": "failure",
        "failure_kind": FailureKind.TIMEOUT_ERROR.value,
        "stage": "agent_response",
        "retryable": True,
        "next_action": "retry with the same request",
        "graph_unchanged": True,
    }


def test_public_outcome_from_turn_outcome_maps_internal_variants_to_public_union() -> None:
    edit = public_outcome_from_turn_outcome(
        TurnOutcome.edit(
            changes=(
                FieldChange(uid="n1", field_path="widgets.seed", old=1, new=2),
            )
        )
    )
    edit_and_clarify = public_outcome_from_turn_outcome(
        TurnOutcome.edit_and_clarify(question="before or after?")
    )
    clarify = public_outcome_from_turn_outcome(TurnOutcome.clarify(question="which model?"))
    noop = public_outcome_from_turn_outcome(TurnOutcome.noop(reason="nothing changed"))

    assert edit == {
        "kind": "candidate",
        "changes": [
            {
                "uid": "n1",
                "field_path": "widgets.seed",
                "old": 1,
                "new": 2,
            }
        ],
    }
    assert edit_and_clarify == {
        "kind": "candidate",
        "changes": [],
        "question": "before or after?",
        "clarification": {"message": "before or after?"},
    }
    assert clarify == {
        "kind": "clarify",
        "question": "which model?",
        "clarification": {"message": "which model?"},
    }
    assert noop == {
        "kind": "noop",
        "reason": "nothing changed",
    }


def test_public_outcome_from_turn_outcome_maps_budget_without_failure_to_candidate_or_noop() -> None:
    assert public_outcome_from_turn_outcome(
        TurnOutcome.budget(reason="ran out of turns"),
        response={"candidate": {"graph_hash": "abc123"}},
    ) == {
        "kind": "candidate",
        "budget_exhausted": True,
        "reason": "ran out of turns",
        "changes": [],
    }
    assert public_outcome_from_turn_outcome(
        TurnOutcome.budget(reason="ran out of turns"),
        response={"candidate": None},
    ) == {
        "kind": "noop",
        "budget_exhausted": True,
        "reason": "ran out of turns",
    }


def test_public_outcome_from_turn_outcome_maps_failure_to_error_and_promotes_recovery() -> None:
    failure = failure_envelope(
        FailureKind.STALE_STATE_MISMATCH,
        "ingest",
        TurnContext(session_id="s1", turn_id="0002"),
        agent_failure_context={
            "issues": [
                {
                    "code": "stale_state_mismatch",
                    "rebaseline_recovery": {"action": "rebaseline", "endpoint": "/vibecomfy/agent-edit/rebaseline"},
                }
            ]
        },
    )

    assert public_outcome_from_turn_outcome(TurnOutcome.from_failure(failure), response=failure.to_dict()) == {
        "kind": "error",
        "failure_kind": FailureKind.STALE_STATE_MISMATCH.value,
        "stage": "ingest",
        "retryable": False,
        "next_action": "resubmit from the current canvas",
        "graph_unchanged": True,
        "agent_failure_context": {
            "issues": [
                {
                    "code": "stale_state_mismatch",
                    "rebaseline_recovery": {"action": "rebaseline", "endpoint": "/vibecomfy/agent-edit/rebaseline"},
                }
            ]
        },
        "rebaseline_recovery": {"action": "rebaseline", "endpoint": "/vibecomfy/agent-edit/rebaseline"},
    }


def test_product_failure_outcome_payload_keeps_contract_version_and_context() -> None:
    failure = failure_envelope(
        FailureKind.MISSING_REQUIRED_FIELD,
        "agent_response",
        TurnContext(session_id="s1"),
        agent_failure_context={"explanation": "missing python"},
    )
    payload = failure.to_dict()
    payload.update(product_failure_envelope_fields(failure))

    assert payload["contract_version"] == AGENT_EDIT_TURN_CONTRACT_VERSION
    assert payload["outcome"]["kind"] == "error"
    assert payload["outcome"]["failure_kind"] == FailureKind.MISSING_REQUIRED_FIELD.value
    assert payload["candidate"] is None
    assert payload["eligibility"]["reason"] == "server_blocked"
    assert payload["audit_ref"] is None
    assert payload["debug"]["failure"]["kind"] == FailureKind.MISSING_REQUIRED_FIELD.value


def test_failure_envelope_to_dict_stamps_public_error_outcome() -> None:
    failure = failure_envelope(
        FailureKind.MISSING_REQUIRED_FIELD,
        "agent_response",
        TurnContext(session_id="s1"),
        agent_failure_context={"explanation": "missing python"},
    )

    assert failure.to_dict()["outcome"] == {
        "kind": "error",
        "failure_kind": FailureKind.MISSING_REQUIRED_FIELD.value,
        "stage": "agent_response",
        "retryable": True,
        "next_action": "wait and retry; model response is incomplete",
        "graph_unchanged": True,
        "agent_failure_context": {"explanation": "missing python"},
    }


def test_failure_envelope_to_dict_promotes_nested_recovery_without_dropping_context() -> None:
    recovery = {
        "action": "rebaseline",
        "endpoint": "/vibecomfy/agent-edit/rebaseline",
    }
    failure = failure_envelope(
        FailureKind.STALE_STATE_MISMATCH,
        "ingest",
        TurnContext(session_id="s1", turn_id="0002"),
        agent_failure_context={
            "issues": [
                {
                    "code": "stale_state_mismatch",
                    "rebaseline_recovery": recovery,
                    "detail": "client baseline is stale",
                }
            ]
        },
    )

    payload = failure.to_dict()

    assert payload["outcome"]["kind"] == "error"
    assert payload["outcome"]["rebaseline_recovery"] == recovery
    assert payload["rebaseline_recovery"] == recovery
    assert payload["agent_failure_context"] == {
        "issues": [
            {
                "code": "stale_state_mismatch",
                "rebaseline_recovery": recovery,
                "detail": "client baseline is stale",
            }
        ]
    }


def test_ensure_agent_edit_response_contract_accepts_scoped_conflict_recovery_issue() -> None:
    recovery = {
        "action": "rebaseline",
        "endpoint": "/vibecomfy/agent-edit/rebaseline",
        "reason": "scoped_accept_conflict",
        "turn_id": "turn-7",
        "submit_graph_hash": "submit-hash",
        "candidate_graph_hash": "candidate-hash",
    }

    payload = ensure_agent_edit_response_contract(
        {
            "ok": False,
            "kind": FailureKind.STALE_STATE_MISMATCH.value,
            "stage": "accept",
            "retryable": False,
            "next_action": "resubmit from the current canvas",
            "graph_unchanged": True,
            "agent_failure_context": {
                "explanation": "Scoped accept verification failed.",
                "issues": [
                    {
                        "code": "scoped_conflict",
                        "detail": "Node 2 prompt drifted after submit.",
                        "rebaseline_recovery": recovery,
                    }
                ],
            },
        },
        stage="accept",
    )

    assert payload["rebaseline_recovery"] == recovery
    assert payload["outcome"]["rebaseline_recovery"] == recovery
    assert payload["agent_failure_context"]["issues"][0]["rebaseline_recovery"] == recovery
    assert tuple(payload["rebaseline_recovery"]) == EXPECTED_SCOPED_ACCEPT_RECOVERY_FIELDS
    assert set(payload["rebaseline_recovery"]) == set(EXPECTED_SCOPED_ACCEPT_RECOVERY_FIELDS)
    assert "candidate_graph_hash" not in REBASELINE_RECOVERY_FIELDS


def test_rebaseline_recovery_fields_are_exact_canonical_tuple() -> None:
    assert REBASELINE_RECOVERY_FIELDS == EXPECTED_REBASELINE_RECOVERY_FIELDS
    assert len(REBASELINE_RECOVERY_FIELDS) == 8


def test_stale_rebaseline_recovery_issue_uses_only_canonical_recovery_fields(
    tmp_path,
) -> None:
    from vibecomfy.comfy_nodes.agent.edit import (
        AgentEditState,
        _stale_rebaseline_recovery_issue,
    )

    graph = {"nodes": [], "links": []}
    state = AgentEditState(
        task="Update the workflow.",
        graph=graph,
        request_payload={"graph": graph},
        schema_provider=None,
        baseline_graph_hash="baseline-hash",
        submit_graph_hash="submit-hash",
        submit_structural_graph_hash="submit-structural-hash",
        submitted_client_graph_hash="client-hash",
        submitted_client_structural_graph_hash="client-structural-hash",
        session_dir=tmp_path / "session",
        turn_dir=tmp_path / "session" / "turns" / "0001",
        request_path=tmp_path / "session" / "turns" / "0001" / "request.json",
        original_ui_path=tmp_path / "session" / "turns" / "0001" / "original.ui.json",
        before_py_path=tmp_path / "session" / "turns" / "0001" / "before.py",
        after_py_path=tmp_path / "session" / "turns" / "0001" / "after.py",
        projection_path=tmp_path / "session" / "turns" / "0001" / "projection.txt",
        model_request_path=tmp_path / "session" / "turns" / "0001" / "model_request.json",
        model_response_path=tmp_path / "session" / "turns" / "0001" / "model_response.json",
        candidate_ui_path=tmp_path / "session" / "turns" / "0001" / "candidate.ui.json",
        messages_path=tmp_path / "session" / "turns" / "0001" / "messages.jsonl",
    )

    issue = _stale_rebaseline_recovery_issue(
        state,
        {
            "reason": "hash_mismatch",
            "baseline_graph_hash": "baseline-hash",
        },
    )
    recovery = issue["rebaseline_recovery"]

    assert tuple(recovery) == REBASELINE_RECOVERY_FIELDS
    assert set(recovery) == set(REBASELINE_RECOVERY_FIELDS)
    assert recovery == {
        "action": "rebaseline",
        "endpoint": "/vibecomfy/agent-edit/rebaseline",
        "reason": "stale_state_recovery",
        "last_known_baseline_graph_hash": "baseline-hash",
        "submit_graph_hash": "submit-hash",
        "submit_structural_graph_hash": "submit-structural-hash",
        "client_graph_hash": "client-hash",
        "client_structural_graph_hash": "client-structural-hash",
    }


def test_route_stale_recovery_repair_emits_only_available_recovery_fields() -> None:
    # Private route-boundary helper coverage is intentional: _ensure_stale_recovery
    # repairs older flat failures into a public recovery payload at the route edge.
    from vibecomfy.comfy_nodes.agent.routes import _ensure_stale_recovery

    payload = _ensure_stale_recovery(
        {
            "kind": FailureKind.STALE_STATE_MISMATCH.value,
            "message": "Submitted graph no longer matches the current baseline.",
            "expected_baseline_graph_hash": "baseline-hash",
            "submit_structural_graph_hash": "submit-structural-hash",
            "outcome": {"kind": "error"},
            "agent_failure_context": {"reason": "stale_state_recovery"},
        }
    )
    recovery = payload["rebaseline_recovery"]

    route_repair_fields = {
        "action",
        "endpoint",
        "reason",
        "last_known_baseline_graph_hash",
        "submit_structural_graph_hash",
    }
    unavailable_hash_fields = {
        "submit_graph_hash",
        "client_graph_hash",
        "client_structural_graph_hash",
    }

    assert set(recovery) == route_repair_fields
    assert recovery == {
        "action": "rebaseline",
        "endpoint": "/vibecomfy/agent-edit/rebaseline",
        "reason": "stale_state_recovery",
        "last_known_baseline_graph_hash": "baseline-hash",
        "submit_structural_graph_hash": "submit-structural-hash",
    }
    assert unavailable_hash_fields.isdisjoint(recovery)
    assert payload["agent_failure_context"]["issues"][0]["rebaseline_recovery"] == recovery
    assert payload["outcome"]["rebaseline_recovery"] == recovery
    assert (
        set(payload["agent_failure_context"]["issues"][0]["rebaseline_recovery"])
        == route_repair_fields
    )
    assert set(payload["outcome"]["rebaseline_recovery"]) == route_repair_fields


def test_rebaseline_recovery_js_codegen_is_limited_to_canonical_tuple() -> None:
    from tools import generate_agent_contract_js

    fields = generate_agent_contract_js._load_fields()
    js_source = generate_agent_contract_js.generate_js(fields)
    normalizer_body = js_source.split("export function normalizeRebaselineRecovery", 1)[1]
    normalizer_body = normalizer_body.split("};", 1)[0]
    generated_fields = tuple(
        line.strip().split(":", 1)[0]
        for line in normalizer_body.splitlines()
        if "asString(recovery." in line
    )

    assert fields == REBASELINE_RECOVERY_FIELDS
    assert generated_fields == REBASELINE_RECOVERY_FIELDS
    assert set(generated_fields) == set(REBASELINE_RECOVERY_FIELDS)
    assert "candidate_graph_hash: asString(recovery.candidate_graph_hash)" not in js_source
    assert "submit_graph_hash: asString(recovery.submit_graph_hash)" in js_source


def test_turn_envelope_serializes_versioned_product_contract() -> None:
    context = TurnContext(session_id="s1", turn_id="0001")
    context.set_gate("python_load_ok", True)
    eligibility = context.apply_eligibility

    payload = turn_envelope(
        message="  Updated the save prefix.  ",
        outcome=TurnOutcome.edit(),
        candidate={"state": "candidate", "graph_hash": "abc123"},
        eligibility=eligibility,
        debug={"gates": context.gate_snapshot()},
    )

    assert payload == {
        "contract_version": AGENT_EDIT_TURN_CONTRACT_VERSION,
        "message": "Updated the save prefix.",
        "outcome": {"kind": "edit", "changes": []},
        "candidate": {"state": "candidate", "graph_hash": "abc123"},
        "eligibility": eligibility.to_dict(),
        "audit_ref": None,
        "debug": {"gates": context.gate_snapshot()},
    }


def test_ensure_agent_edit_response_contract_maps_internal_outcomes_and_flat_failures() -> None:
    success_payload = ensure_agent_edit_response_contract(
        {
            "ok": True,
            "message": "Updated the save prefix.",
            "candidate": {"graph_hash": "abc123"},
            "outcome": {"kind": "edit", "changes": []},
        },
        stage="submit",
    )
    failure_payload = ensure_agent_edit_response_contract(
        failure_envelope(
            FailureKind.TIMEOUT_ERROR,
            "agent_response",
            TurnContext(session_id="s1"),
            agent_failure_context={"explanation": "provider timed out"},
        ).to_dict(),
        stage="submit",
    )

    assert success_payload["outcome"] == {"kind": "candidate", "changes": []}
    assert failure_payload["outcome"]["kind"] == "error"
    assert failure_payload["outcome"]["failure_kind"] == FailureKind.TIMEOUT_ERROR.value


def test_success_envelope_keeps_canonical_eligibility_field() -> None:
    context = TurnContext(session_id="s1", turn_id="0001")
    context.set_gate("python_load_ok", True)

    payload = success_envelope(
        context,
        message="Applied the requested edit.",
        graph={"nodes": [], "links": []},
    )

    assert payload["eligibility"] == context.apply_eligibility.to_dict()
    assert "apply_eligibility" not in payload
    assert "apply_allowed" not in payload
    assert "canvas_apply_allowed" not in payload
    assert "queue_allowed" not in payload


def test_build_legacy_agent_edit_v1_adds_aliases_after_canonical_payload() -> None:
    from vibecomfy.comfy_nodes.agent.contracts import build_legacy_agent_edit_v1

    canonical = {
        "message": "Updated the workflow.",
        "outcome": {"kind": "candidate", "changes": []},
        "candidate": {
            "state": "candidate",
            "graph": {"nodes": [{"id": 1}], "links": []},
            "graph_hash": "candidate-hash",
            "structural_graph_hash": "candidate-structural-hash",
        },
        "eligibility": {
            "applyable": True,
            "reason": "applyable",
            "message": "Ready to apply.",
            "warnings": [],
        },
    }

    payload = build_legacy_agent_edit_v1(
        {
            **canonical,
            "canvas_apply_allowed": True,
            "queue_allowed": False,
        }
    )

    assert canonical.keys() <= payload.keys()
    assert payload["apply_eligibility"] == canonical["eligibility"]
    assert payload["apply_allowed"] is True
    assert payload["canvas_apply_allowed"] is True
    assert payload["queue_allowed"] is False
    assert payload["candidate_graph"] == canonical["candidate"]["graph"]
    assert payload["graph"] == canonical["candidate"]["graph"]


def test_build_legacy_agent_edit_v1_accepts_apply_eligibility_dataclass() -> None:
    from vibecomfy.comfy_nodes.agent.contracts import build_legacy_agent_edit_v1

    candidate_graph = {"nodes": [{"id": 1}], "links": []}
    eligibility = ApplyEligibility(
        applyable=True,
        reason="applyable",
        message="Ready to apply.",
    )

    # Defensive compatibility coverage: older internal callers may pass the
    # dataclass directly instead of the public mapping shape.
    payload = build_legacy_agent_edit_v1(
        {
            "message": "Updated the workflow.",
            "outcome": {"kind": "candidate", "changes": []},
            "candidate": {
                "state": "candidate",
                "graph": candidate_graph,
                "graph_hash": "candidate-hash",
                "structural_graph_hash": "candidate-structural-hash",
            },
            "eligibility": eligibility,
            "canvas_apply_allowed": True,
            "queue_allowed": False,
        }
    )

    assert payload["eligibility"] == eligibility.to_dict()
    assert payload["apply_eligibility"] == eligibility.to_dict()
    assert payload["apply_allowed"] is True
    assert payload["canvas_apply_allowed"] is True
    assert payload["queue_allowed"] is False
    assert payload["candidate_graph"] == candidate_graph
    assert payload["graph"] == candidate_graph


def test_build_legacy_agent_edit_v1_uses_apply_eligibility_mapping_fallback() -> None:
    from vibecomfy.comfy_nodes.agent.contracts import build_legacy_agent_edit_v1

    candidate_graph = {"nodes": [{"id": 1}], "links": []}
    eligibility = {
        "applyable": True,
        "reason": "applyable",
        "message": "Ready to apply.",
        "warnings": [],
    }

    payload = build_legacy_agent_edit_v1(
        {
            "message": "Updated the workflow.",
            "outcome": {"kind": "candidate", "changes": []},
            "candidate": {
                "state": "candidate",
                "graph": candidate_graph,
                "graph_hash": "candidate-hash",
                "structural_graph_hash": "candidate-structural-hash",
            },
            "apply_eligibility": eligibility,
            "canvas_apply_allowed": True,
            "queue_allowed": False,
        }
    )

    assert payload["eligibility"] == eligibility
    assert payload["apply_eligibility"] == eligibility
    assert payload["apply_allowed"] is True
    assert payload["canvas_apply_allowed"] is True
    assert payload["queue_allowed"] is False
    assert payload["candidate_graph"] == candidate_graph
    assert payload["graph"] == candidate_graph


def test_build_legacy_agent_edit_v1_preserves_plan_fields_and_non_plan_candidate_aliases() -> None:
    from vibecomfy.comfy_nodes.agent.contracts import build_legacy_agent_edit_v1

    candidate_graph = {
        "nodes": [
            {"id": 10, "type": "ADE_AnimateDiffLoaderWithContext"},
            {"id": 11, "type": "VHS_VideoCombine"},
        ],
        "links": [[1, 10, 0, 11, 0, "IMAGE"]],
    }
    queue_warning = {
        "applyable": True,
        "reason": "queue_blocked_warning",
        "message": "Apply is allowed, but Queue remains blocked for this candidate.",
        "warnings": ["queue_blocked"],
    }
    plan_payload = build_legacy_agent_edit_v1(
        {
            "message": "HotShotXL candidate ready.",
            "outcome": {"kind": "candidate", "changes": []},
            "candidate": {
                "state": "candidate",
                "graph": candidate_graph,
                "graph_hash": "candidate-hash",
                "structural_graph_hash": "candidate-structural-hash",
            },
            "eligibility": queue_warning,
            "canvas_apply_allowed": True,
            "queue_allowed": False,
            "gates": {
                "plan_validate_ok": True,
                "queue_validate_ok": False,
            },
            "execution_plan_status": {
                "plan_id": "hotshotxl-active-video-path",
                "ok": True,
                "blocking": False,
                "failed_condition_ids": [],
            },
            "execution_plan_feedback": "plan evaluation passed.",
            "artifacts": {
                "execution_plan": "turns/0001/execution_plan.json",
                "plan_evaluation": "turns/0001/plan_evaluation.json",
            },
            "debug": {
                "gates": {
                    "plan_validate_ok": True,
                    "queue_validate_ok": False,
                },
                "execution_plan_artifacts": {
                    "execution_plan": {
                        "path": "turns/0001/execution_plan.json",
                        "sha256": "plan-sha",
                        "byte_count": 42,
                        "preview": None,
                    },
                    "plan_evaluation": {
                        "path": "turns/0001/plan_evaluation.json",
                        "sha256": "eval-sha",
                        "byte_count": 84,
                        "preview": None,
                    },
                },
            },
        }
    )
    non_plan_payload = build_legacy_agent_edit_v1(
        {
            "message": "Regular candidate ready.",
            "outcome": {"kind": "candidate", "changes": []},
            "candidate": {
                "state": "candidate",
                "graph": candidate_graph,
                "graph_hash": "candidate-hash",
                "structural_graph_hash": "candidate-structural-hash",
            },
            "eligibility": queue_warning,
            "canvas_apply_allowed": True,
            "queue_allowed": False,
        }
    )

    assert plan_payload["apply_allowed"] is True
    assert plan_payload["canvas_apply_allowed"] is True
    assert plan_payload["queue_allowed"] is False
    assert plan_payload["apply_eligibility"]["reason"] == "queue_blocked_warning"
    assert plan_payload["gates"]["plan_validate_ok"] is True
    assert plan_payload["execution_plan_status"]["ok"] is True
    assert plan_payload["execution_plan_feedback"] == "plan evaluation passed."
    assert plan_payload["artifacts"]["execution_plan"].endswith("execution_plan.json")
    assert plan_payload["artifacts"]["plan_evaluation"].endswith("plan_evaluation.json")
    assert (
        plan_payload["debug"]["execution_plan_artifacts"]["plan_evaluation"]["path"]
        == "turns/0001/plan_evaluation.json"
    )
    assert non_plan_payload["apply_allowed"] is True
    assert non_plan_payload["canvas_apply_allowed"] is True
    assert non_plan_payload["queue_allowed"] is False
    assert non_plan_payload["apply_eligibility"] == queue_warning
    assert non_plan_payload["candidate_graph"] == candidate_graph
    assert "execution_plan_status" not in non_plan_payload
    assert "execution_plan_feedback" not in non_plan_payload


@pytest.mark.parametrize(
    ("apply_eligible", "expected_reason", "expected_message"),
    [
        (True, "applyable", "Ready to apply."),
        (False, "no_candidate", "No candidate is available to apply."),
    ],
)
def test_build_legacy_agent_edit_v1_uses_apply_eligible_boolean_fallback(
    apply_eligible: bool,
    expected_reason: str,
    expected_message: str,
) -> None:
    from vibecomfy.comfy_nodes.agent.contracts import build_legacy_agent_edit_v1

    payload = build_legacy_agent_edit_v1(
        {
            "message": "Updated the workflow.",
            "outcome": {"kind": "noop"},
            "apply_eligible": apply_eligible,
        }
    )

    assert payload["eligibility"] == {
        "applyable": apply_eligible,
        "reason": expected_reason,
        "message": expected_message,
        "warnings": [],
    }
    assert payload["apply_eligibility"] == payload["eligibility"]
    assert payload["apply_allowed"] is apply_eligible
    assert payload["canvas_apply_allowed"] is apply_eligible
    assert payload["queue_allowed"] is apply_eligible


@pytest.mark.parametrize(
    "candidate",
    [
        None,
        "not-a-candidate",
        {"state": "candidate"},
        {"state": "candidate", "graph": None},
        {"state": "candidate", "graph": []},
    ],
)
def test_build_legacy_agent_edit_v1_does_not_stamp_graph_aliases_without_candidate_graph(
    candidate: object,
) -> None:
    from vibecomfy.comfy_nodes.agent.contracts import build_legacy_agent_edit_v1

    canonical: dict[str, object] = {
        "message": "No graph candidate.",
        "outcome": {"kind": "noop"},
        "eligibility": {
            "applyable": False,
            "reason": "no_candidate",
            "message": "No candidate is available to apply.",
            "warnings": [],
        },
    }
    if candidate is not None:
        canonical["candidate"] = candidate

    payload = build_legacy_agent_edit_v1(canonical)

    assert "candidate_graph" not in payload
    assert "graph" not in payload
    assert payload["graph_unchanged"] is True


def test_build_legacy_agent_edit_v1_stamps_graph_aliases_and_defaults_changed() -> None:
    from vibecomfy.comfy_nodes.agent.contracts import build_legacy_agent_edit_v1

    candidate_graph = {"nodes": [{"id": 1}], "links": []}

    payload = build_legacy_agent_edit_v1(
        {
            "message": "Updated the workflow.",
            "outcome": {"kind": "candidate", "changes": []},
            "candidate": {
                "state": "candidate",
                "graph": candidate_graph,
            },
            "eligibility": {
                "applyable": True,
                "reason": "applyable",
                "message": "Ready to apply.",
                "warnings": [],
            },
        }
    )

    assert payload["candidate_graph"] == candidate_graph
    assert payload["graph"] == candidate_graph
    assert payload["graph_unchanged"] is False


@pytest.mark.parametrize("graph_unchanged", [True, False])
def test_build_legacy_agent_edit_v1_preserves_existing_graph_unchanged(
    graph_unchanged: bool,
) -> None:
    from vibecomfy.comfy_nodes.agent.contracts import build_legacy_agent_edit_v1

    candidate_graph = {"nodes": [{"id": 1}], "links": []}

    payload = build_legacy_agent_edit_v1(
        {
            "message": "Updated the workflow.",
            "outcome": {"kind": "candidate", "changes": []},
            "candidate": {
                "state": "candidate",
                "graph": candidate_graph,
            },
            "eligibility": {
                "applyable": True,
                "reason": "applyable",
                "message": "Ready to apply.",
                "warnings": [],
            },
            "graph_unchanged": graph_unchanged,
        }
    )

    assert payload["candidate_graph"] == candidate_graph
    assert payload["graph"] == candidate_graph
    assert payload["graph_unchanged"] is graph_unchanged


# ---------------------------------------------------------------------------
# T2: Focused contract tests — classifier stability, scan-code mappings,
# failure envelope shape, gate defaults, apply_allowed == canvas_apply_allowed
# ---------------------------------------------------------------------------


# --- Gate default stability ---


def test_all_design_gates_present_and_distinct() -> None:
    """Every design-level named gate exists and is distinct."""
    assert len(DEFAULT_GATE_NAMES) == 9
    assert len(set(DEFAULT_GATE_NAMES)) == 9
    assert set(DEFAULT_GATE_NAMES) == {
        "python_load_ok",
        "lower_ok",
        "ir_validate_ok",
        "ui_emit_ok",
        "ui_fidelity_ok",
        "ui_load_safe_ok",
        PLAN_VALIDATE_GATE_NAME,
        "queue_validate_ok",
        "state_match_ok",
    }


def test_canvas_apply_subset_is_proper_subset_of_all_gates() -> None:
    """canvas_apply_allowed checks every gate except queue_validate_ok."""
    assert set(CANVAS_APPLY_GATE_NAMES) == set(DEFAULT_GATE_NAMES) - {"queue_validate_ok", "lower_ok"}
    assert PLAN_VALIDATE_GATE_NAME in CANVAS_APPLY_GATE_NAMES
    assert "queue_validate_ok" not in CANVAS_APPLY_GATE_NAMES
    assert "lower_ok" not in CANVAS_APPLY_GATE_NAMES


def test_turn_context_set_gate_accepts_lower_ok() -> None:
    context = TurnContext(session_id="s1")
    context.set_gate("lower_ok", True, evidence={"stage": "lower"})
    assert context.gate_results["lower_ok"].ok is True
    assert dict(context.gate_results["lower_ok"].evidence) == {"stage": "lower"}


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


def test_classify_agent_response_json_error_with_noisy_import_tail_stays_malformed() -> None:
    ctx = TurnContext(session_id="s1")
    exc = RuntimeError(
        "JSONDecodeError: Expecting ',' delimiter: line 2 column 1463 (char 1464)\n\n"
        "Worker output tail:\n"
        "Could not register VibeComfy agent routes (No module named 'server'); "
        "the ComfyUI server may not be available."
    )

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


def test_classify_openrouter_credit_error_is_specific_and_non_retryable() -> None:
    ctx = TurnContext(session_id="s1")
    fe = classify_failure(
        "agent_response",
        RuntimeError(
            "ValueError: Agent returned an empty batch_repl response.\n\n"
            "Worker output tail:\n"
            "Error code: 402 - This request requires more credits, or fewer max_tokens. "
            "You requested up to 8192 tokens, but can only afford 3590. "
            "To increase, visit https://openrouter.ai/settings/credits"
        ),
        ctx,
    )

    assert fe.kind is FailureKind.PROVIDER_CREDIT_ERROR
    assert fe.retryable is False
    assert "OpenRouter" in fe.user_facing_message
    assert "temporarily unavailable" not in fe.user_facing_message


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


def test_classify_lower_stage_uses_lowering_failure() -> None:
    ctx = TurnContext(session_id="s1")
    fe = classify_failure("lower", RuntimeError("unsupported loop body"), ctx)
    assert fe.kind is FailureKind.LOWERING_FAILURE
    assert fe.stage == "lower"


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


def test_failure_envelope_serializes_lowering_failure_kind() -> None:
    fe = failure_envelope(FailureKind.LOWERING_FAILURE, "lower", None)
    payload = fe.to_dict()
    assert payload["kind"] == FailureKind.LOWERING_FAILURE.value
    assert payload["stage"] == "lower"


def test_failure_envelope_invalid_string_kind_raises() -> None:
    """An unrecognised string raises ValueError from the Enum constructor."""
    with pytest.raises(ValueError):
        failure_envelope("NotAKind", "load_python", None)


# ---------------------------------------------------------------------------
# T1: Focused contract tests — closed public outcome kinds, legacy/internal
# kind mapping, endpoint payload outcome stamping
# ---------------------------------------------------------------------------


def test_ensure_agent_edit_response_contract_rejects_unrecognized_outcome_kind() -> None:
    """ensure_agent_edit_response_contract must raise when the resolved public
    outcome kind is not in PUBLIC_OUTCOME_KINDS."""
    with pytest.raises(ValueError, match="invalid public outcome kind|Unknown TurnOutcome kind"):
        ensure_agent_edit_response_contract(
            {"ok": True, "outcome": {"kind": "bogus"}},
            stage="submit",
        )


def test_ensure_agent_edit_response_contract_normalizes_edit_to_candidate() -> None:
    """Internal 'edit' outcome kind is normalized to public 'candidate'."""
    payload = ensure_agent_edit_response_contract(
        {
            "ok": True,
            "message": "Applied rename.",
            "outcome": {"kind": "edit", "changes": [{"uid": "n1", "field_path": "widgets.prefix", "old": "a", "new": "b"}]},
        },
        stage="submit",
    )
    assert payload["outcome"]["kind"] == "candidate"
    assert len(payload["outcome"]["changes"]) == 1
    assert payload["outcome"]["changes"][0]["uid"] == "n1"


def test_ensure_agent_edit_response_contract_normalizes_edit_plus_clarify_to_candidate() -> None:
    """Internal 'edit+clarify' is normalized to public 'candidate' with
    clarification payload attached."""
    payload = ensure_agent_edit_response_contract(
        {
            "ok": True,
            "message": "Renamed and asked.",
            "outcome": {"kind": "edit+clarify", "question": "Keep this prefix?"},
        },
        stage="submit",
    )
    assert payload["outcome"]["kind"] == "candidate"
    assert payload["outcome"]["question"] == "Keep this prefix?"
    assert payload["outcome"]["clarification"] == {"message": "Keep this prefix?"}


def test_ensure_agent_edit_response_contract_preserves_public_noop() -> None:
    """Public 'noop' outcome kind passes through unchanged."""
    payload = ensure_agent_edit_response_contract(
        {
            "ok": True,
            "message": "Nothing to do.",
            "outcome": {"kind": "noop", "reason": "no changes detected"},
        },
        stage="submit",
    )
    assert payload["outcome"]["kind"] == "noop"
    assert payload["outcome"]["reason"] == "no changes detected"


def test_ensure_agent_edit_response_contract_preserves_public_clarify() -> None:
    """Public 'clarify' outcome kind passes through unchanged."""
    payload = ensure_agent_edit_response_contract(
        {
            "ok": True,
            "message": "Question for you.",
            "outcome": {"kind": "clarify", "question": "Which model?"},
        },
        stage="submit",
    )
    assert payload["outcome"]["kind"] == "clarify"
    assert payload["outcome"]["question"] == "Which model?"


def test_ensure_agent_edit_response_contract_preserves_public_error() -> None:
    """Public 'error' outcome kind passes through unchanged."""
    payload = ensure_agent_edit_response_contract(
        {
            "ok": False,
            "kind": "TimeoutError",
            "stage": "agent_response",
            "retryable": True,
            "next_action": "retry",
            "graph_unchanged": True,
            "agent_failure_context": {"explanation": "timed out"},
        },
        stage="submit",
    )
    assert payload["outcome"]["kind"] == "error"
    assert payload["outcome"]["failure_kind"] == "TimeoutError"


def test_ensure_agent_edit_response_contract_maps_flat_failure_to_error() -> None:
    """A flat failure response without explicit outcome is mapped to public 'error'."""
    failure = failure_envelope(
        FailureKind.MISSING_REQUIRED_FIELD,
        "ingest",
        None,
        agent_failure_context={"explanation": "no graph"},
    )
    payload = ensure_agent_edit_response_contract(
        failure.to_dict(),
        stage="submit",
    )
    assert payload["outcome"]["kind"] == "error"
    assert payload["outcome"]["failure_kind"] == "MissingRequiredField"
    assert payload["outcome"]["stage"] == "ingest"


def test_all_public_outcome_kinds_tested_by_ensure_contract() -> None:
    """Smoke-test: every member of PUBLIC_OUTCOME_KINDS can round-trip through
    ensure_agent_edit_response_contract."""
    # candidate (via internal edit)
    candidate = ensure_agent_edit_response_contract(
        {"ok": True, "outcome": {"kind": "edit"}},
        stage="submit",
    )
    assert candidate["outcome"]["kind"] == "candidate"

    # noop (already public)
    noop = ensure_agent_edit_response_contract(
        {"ok": True, "outcome": {"kind": "noop"}},
        stage="accept",
    )
    assert noop["outcome"]["kind"] == "noop"

    # clarify (already public)
    clarify = ensure_agent_edit_response_contract(
        {"ok": True, "outcome": {"kind": "clarify", "question": "q?"}},
        stage="submit",
    )
    assert clarify["outcome"]["kind"] == "clarify"

    # error (via flat failure)
    error = ensure_agent_edit_response_contract(
        failure_envelope(FailureKind.TIMEOUT_ERROR, "agent_response", None).to_dict(),
        stage="submit",
    )
    assert error["outcome"]["kind"] == "error"


def test_public_outcome_kinds_are_the_closed_contract_set() -> None:
    """The public outcome kinds are exactly the four contractual values."""
    assert PUBLIC_OUTCOME_KINDS == ("candidate", "noop", "clarify", "error")
    assert len(PUBLIC_OUTCOME_KINDS) == 4
    assert len(set(PUBLIC_OUTCOME_KINDS)) == 4


def test_internal_to_public_outcome_is_closed_authoritative_mapping() -> None:
    """Every internal kind has one declared public default; budget defaults to
    noop and is promoted only when a candidate payload exists."""
    assert dict(INTERNAL_TO_PUBLIC_OUTCOME) == {
        "edit": "candidate",
        "edit+clarify": "candidate",
        "clarify": "clarify",
        "failure": "error",
        "noop": "noop",
        "budget": "noop",
    }
    assert set(INTERNAL_TO_PUBLIC_OUTCOME) == set(TURN_OUTCOME_KINDS)
    assert set(INTERNAL_TO_PUBLIC_OUTCOME.values()) <= set(PUBLIC_OUTCOME_KINDS)


def test_budget_public_outcome_uses_mapping_default_and_candidate_override() -> None:
    assert INTERNAL_TO_PUBLIC_OUTCOME["budget"] == "noop"

    default_public = public_outcome_from_turn_outcome(
        {"kind": "budget", "reason": "turn budget exhausted"},
        response={},
    )
    candidate_public = public_outcome_from_turn_outcome(
        {"kind": "budget", "reason": "turn budget exhausted"},
        response={"candidate": {"graph_hash": "candidate-hash"}},
    )

    assert default_public == {
        "kind": "noop",
        "budget_exhausted": True,
        "reason": "turn budget exhausted",
    }
    assert candidate_public == {
        "kind": "candidate",
        "budget_exhausted": True,
        "reason": "turn budget exhausted",
        "changes": [],
    }


@pytest.mark.parametrize(
    "outcome",
    [
        {"kind": "error"},
        {
            "kind": "error",
            "failure_kind": FailureKind.TIMEOUT_ERROR.value,
            "stage": "agent_response",
            "retryable": "true",
            "next_action": "retry",
            "graph_unchanged": True,
        },
        {
            "kind": "error",
            "failure_kind": FailureKind.TIMEOUT_ERROR.value,
            "stage": "agent_response",
            "retryable": True,
            "next_action": "retry",
        },
    ],
)
def test_public_outcome_from_turn_outcome_rejects_malformed_public_error(outcome: dict[str, object]) -> None:
    with pytest.raises(ValueError, match="public error outcome"):
        public_outcome_from_turn_outcome(outcome)


def test_ensure_agent_edit_response_contract_maps_all_failure_hint_keys_to_error() -> None:
    assert set(FAILURE_HINT_KEYS) == {
        "agent_failure_context",
        "failureKind",
        "failure_kind",
        "nextAction",
        "next_action",
        "retryable",
    }

    payload = ensure_agent_edit_response_contract(
        {
            "ok": True,
            "failureKind": FailureKind.AUTH_ERROR.value,
            "stage": "agent_response",
            "retryable": False,
            "nextAction": "check credentials in Agent Settings",
            "graph_unchanged": True,
            "agent_failure_context": {"explanation": "HTTP 401"},
        },
        stage="agent_response",
    )

    assert payload["outcome"] == {
        "kind": "error",
        "failure_kind": FailureKind.AUTH_ERROR.value,
        "stage": "agent_response",
        "retryable": False,
        "next_action": "check credentials in Agent Settings",
        "graph_unchanged": True,
        "agent_failure_context": {"explanation": "HTTP 401"},
    }


def test_all_internal_turn_outcome_kinds_map_to_public_union() -> None:
    """Every internal TurnOutcome kind maps to a valid public kind via
    public_outcome_from_turn_outcome."""
    internal_to_public = {
        "edit": "candidate",
        "edit+clarify": "candidate",
        "clarify": "clarify",
        "noop": "noop",
        "failure": "error",
        # budget depends on response context — but the kind itself maps
    }
    for internal_kind in TURN_OUTCOME_KINDS:
        if internal_kind == "budget":
            # budget requires response context
            result = public_outcome_from_turn_outcome(
                {"kind": "budget", "reason": "exhausted"},
                response={"candidate": None},
            )
            assert result["kind"] in ("candidate", "noop")
        elif internal_kind == "failure":
            failure = failure_envelope(
                FailureKind.VALIDATION_ERROR, "validate", None
            )
            result = public_outcome_from_turn_outcome(
                TurnOutcome.from_failure(failure),
                response=failure.to_dict(),
            )
            assert result["kind"] == internal_to_public[internal_kind]
        else:
            # Non-failure, non-budget: construct a minimal outcome
            changes = (
                (FieldChange(uid="n1", field_path="x", old=1, new=2),)
                if internal_kind in ("edit", "edit+clarify")
                else ()
            )
            question = "q?" if internal_kind in ("clarify", "edit+clarify") else None
            result = public_outcome_from_turn_outcome(
                {
                    "kind": internal_kind,
                    "changes": [c.to_dict() for c in changes],
                    "question": question,
                }
            )
            assert result["kind"] == internal_to_public[internal_kind], (
                f"{internal_kind!r} should map to {internal_to_public[internal_kind]!r}, "
                f"got {result['kind']!r}"
            )


def test_public_projection_helpers_do_not_leak_raw_rehydrate_fields() -> None:
    sentinel = "SECRET_PUBLIC_PROJECTION_SENTINEL"
    raw_change_details = {
        "code": "queue_blocked",
        "severity": "warning",
        "message": "Queue remains blocked.",
        "lifecycle": "candidate",
        "stage": "queue_validate",
        "ok": False,
        "path": f"/private/{sentinel}/audit.json",
        "audit_path": f"/private/{sentinel}/audit.json",
        "request_path": f"/private/{sentinel}/request.json",
        "response_path": f"/private/{sentinel}/response.json",
        "raw_prompt": f"raw prompt {sentinel}",
        "prompt": f"expanded prompt {sentinel}",
        "budget": {"remaining": sentinel},
        "budget_trace": [{"remaining": sentinel}],
        "debug_payload": {"stack": sentinel},
        "raw_session_state": {"canvas": sentinel},
        "provider_diagnostics": {"trace": sentinel},
        "batch_turns": [
            {
                "stage": "agent_response",
                "ok": True,
                "code": "batch_step_complete",
                "message": "First batch turn completed.",
                "raw_prompt": f"batch prompt {sentinel}",
                "budget": {"remaining": sentinel},
                "debug_payload": {"trace": sentinel},
            }
        ],
    }
    raw_audit_ref = {
        "path": f"/private/{sentinel}/turns/0002/audit.json",
        "sha256": "abc123",
        "byte_count": 42,
        "preview": "audit ok",
    }
    raw_response = {
        "ok": True,
        "session_id": "sess-1",
        "turn_id": "0002",
        "message": "Candidate ready.",
        "outcome": {"kind": "edit", "changes": []},
        "candidate_graph_hash": "graph-hash",
        "change_details": raw_change_details,
        "audit_ref": raw_audit_ref,
        "debug_payload": {"response": sentinel},
        "raw_session_state": {"state": sentinel},
        "provider_diagnostics": {"tokens": sentinel},
        "budget": {"remaining": sentinel},
    }
    raw_latest_candidate = {
        **raw_response,
        "graph": {"nodes": [{"id": 1}], "links": []},
        "report": {
            "revision_evidence": {
                "scoped_diff": {
                    "summary": "1 changed node(s)",
                    "changed_nodes": ["1"],
                },
            },
        },
        "candidate": {"state": "candidate", "graph_hash": "graph-hash"},
    }

    public_values = [
        public_response_details(raw_response),
        public_latest_candidate(raw_latest_candidate),
        public_chat_rehydrate_payload(
            {
                "ok": True,
                "exists": True,
                "session_id": "sess-1",
                "latest_turn_id": "0002",
                "messages": [
                    {
                        "role": "assistant",
                        "text": "Candidate ready.",
                        "turn_id": "0002",
                        "timestamp": "2026-06-24T12:00:00Z",
                        "outcome": {"kind": "edit", "changes": []},
                        "change_details": raw_change_details,
                        "audit_ref": raw_audit_ref,
                        "debug_payload": {"message": sentinel},
                        "raw_prompt": f"message prompt {sentinel}",
                    }
                ],
                "latest_candidate": raw_latest_candidate,
                "diagnostics": [
                    {
                        "code": "reload_warning",
                        "message": "Reload warning.",
                        "path": f"/private/{sentinel}/diagnostic.json",
                        "debug_payload": {"diagnostic": sentinel},
                    }
                ],
                "audit_artifacts": [raw_audit_ref],
                "debug_payload": {"rehydrate": sentinel},
                "raw_session_state": {"state": sentinel},
                "provider_diagnostics": {"provider": sentinel},
            }
        ),
        public_session_json_payload(
            {
                "ok": True,
                "session_id": "sess-1",
                "latest_turn_id": "0002",
                "turn_count": 1,
                "messages": [
                    {
                        "role": "assistant",
                        "text": "Candidate ready.",
                        "turn_id": "0002",
                        "change_details": raw_change_details,
                        "audit_ref": raw_audit_ref,
                    }
                ],
                "turns": [
                    {
                        "turn_id": "0002",
                        "message_count": 2,
                        "error": None,
                        "audit_path": f"/private/{sentinel}/audit.json",
                        "detail_json_path": f"/private/{sentinel}/detail.json",
                        "request.json": {"path": f"/private/{sentinel}/request.json"},
                        "response.json": {"path": f"/private/{sentinel}/response.json"},
                        "chat.json": {"path": f"/private/{sentinel}/chat.json"},
                        "audit_ref": raw_audit_ref,
                        "raw_session_state": {"turn": sentinel},
                        "provider_diagnostics": {"turn": sentinel},
                    }
                ],
                "debug_payload": {"session": sentinel},
                "raw_session_state": {"session": sentinel},
                "provider_diagnostics": {"session": sentinel},
            }
        ),
    ]
    assert public_latest_candidate(raw_latest_candidate)["report"] == raw_latest_candidate["report"]
    assert (
        public_chat_rehydrate_payload(
            {
                "ok": True,
                "exists": True,
                "session_id": "sess-1",
                "latest_candidate": raw_latest_candidate,
            }
        )["latest_candidate"]["report"]
        == raw_latest_candidate["report"]
    )

    for value in public_values:
        assert value is not None
        _assert_public_projection_has_no_forbidden_sentinels(value)


def test_public_chat_rehydrate_projection_keeps_compact_reload_diagnostics() -> None:
    projected = public_chat_rehydrate_payload(
        {
            "ok": True,
            "exists": True,
            "session_id": "sess-1",
            "latest_turn_id": "0002",
            "messages": [
                {
                    "role": "assistant",
                    "text": "Candidate ready.",
                    "turn_id": "0002",
                    "change_details": {
                        "code": "queue_blocked",
                        "severity": "warning",
                        "message": "Queue remains blocked.",
                        "lifecycle": "candidate",
                        "stage": "queue_validate",
                        "ok": False,
                        "queue_allowed": False,
                        "candidate_nodes": 3,
                        "batch_turns": [
                            {
                                "code": "batch_step_complete",
                                "message": "Validated step one.",
                                "stage": "agent_response",
                                "ok": True,
                                "landed_operation_count": 2,
                            }
                        ],
                    },
                    "audit_ref": {
                        "path": "/private/session/turns/0002/audit.json",
                        "sha256": "abc123",
                        "byte_count": 42,
                        "preview": "audit ok",
                    },
                }
            ],
            "diagnostics": [
                {
                    "turn_id": "0001",
                    "source": "persisted",
                    "code": "prior_warning",
                    "message": "Prior warning.",
                    "severity": "info",
                    "stage": "ui_emit",
                    "ok": True,
                }
            ],
            "audit_artifacts": [
                {
                    "turn_id": "0001",
                    "source": "persisted",
                    "path": "/private/session/turns/0001/audit.json",
                    "sha256": "def456",
                    "byte_count": 24,
                    "preview": "prior audit ok",
                }
            ],
        }
    )

    assert projected["diagnostics"] == [
        {
            "turn_id": "0002",
            "source": "messages.change_details",
            "code": "queue_blocked",
            "severity": "warning",
            "message": "Queue remains blocked.",
            "lifecycle": "candidate",
            "stage": "queue_validate",
            "ok": False,
            "queue_allowed": False,
            "candidate_nodes": 3,
        },
        {
            "turn_id": "0002",
            "source": "messages.change_details.batch_turns[0]",
            "code": "batch_step_complete",
            "message": "Validated step one.",
            "stage": "agent_response",
            "ok": True,
            "landed_operation_count": 2,
        },
        {
            "turn_id": "0001",
            "source": "persisted",
            "code": "prior_warning",
            "message": "Prior warning.",
            "severity": "info",
            "stage": "ui_emit",
            "ok": True,
        },
    ]
    assert projected["audit_artifacts"] == [
        {
            "turn_id": "0002",
            "source": "messages",
            "sha256": "abc123",
            "byte_count": 42,
            "preview": "audit ok",
        },
        {
            "turn_id": "0001",
            "source": "persisted",
            "sha256": "def456",
            "byte_count": 24,
            "preview": "prior audit ok",
        },
    ]
    _assert_public_projection_has_no_forbidden_sentinels(projected)


def test_diagnostic_record_round_trips_through_dict() -> None:
    record = DiagnosticRecord(
        session_id="sess-1",
        turn_id="0003",
        path="/tmp/sess-1/turns/0003/response.json",
        mtime=1234567890.0,
        baseline_turn_id="0001",
        ok=True,
        kind="edit",
        outcome="candidate",
        lifecycle="candidate",
        fidelity_ok=True,
        state_match_ok=True,
        queue_validate_ok=True,
        canvas_apply_allowed=True,
        queue_allowed=True,
        candidate_nodes=7,
        task="make it pop",
        route="edit",
        protocol="v2",
        summary="changed saturation",
        is_baseline=False,
        accepted_at=None,
        live_token="token-abc",
    )
    payload = record.to_dict()
    restored = DiagnosticRecord.from_dict(payload)
    assert restored == record
    # Extra fields in older on-disk records are ignored.
    payload["future_field"] = "ignored"
    assert DiagnosticRecord.from_dict(payload) == record


def test_diagnostic_record_requires_string_identity_fields() -> None:
    base_payload = {
        "session_id": "sess-1",
        "turn_id": "0003",
    }
    invalid_values = (
        ("session_id", "<missing>"),
        ("session_id", None),
        ("session_id", 123),
        ("turn_id", "<missing>"),
        ("turn_id", None),
        ("turn_id", 123),
    )

    for field, value in invalid_values:
        payload = dict(base_payload)
        if value == "<missing>":
            del payload[field]
        else:
            payload[field] = value

        with pytest.raises(ValueError, match=rf"DiagnosticRecord\.{field} must be a string"):
            DiagnosticRecord.from_dict(payload)


def test_diagnostic_record_preserves_permissive_optional_historical_fields() -> None:
    payload = {
        "session_id": "sess-1",
        "turn_id": "0003",
        "path": 123,
        "mtime": "not-a-float",
        "baseline_turn_id": 456,
        "ok": "yes",
        "kind": 789,
        "outcome": {"kind": "candidate"},
        "lifecycle": ["candidate"],
        "fidelity_ok": "true",
        "state_match_ok": 1,
        "queue_validate_ok": None,
        "canvas_apply_allowed": "allowed",
        "queue_allowed": [],
        "candidate_nodes": "seven",
        "task": {"prompt": "make it pop"},
        "route": 42,
        "protocol": False,
        "summary": ["changed saturation"],
        "is_baseline": "no",
        "accepted_at": 123.45,
        "live_token": {"token": "abc"},
    }

    record = DiagnosticRecord.from_dict(payload)

    assert record.to_dict() == payload


def test_repair_field_changes_fills_missing_old_value_from_ui_graph() -> None:
    graph = {
        "nodes": [
            {
                "id": 1,
                "type": "KSampler",
                "widgets_values": [20, "euler", 1.0],
            }
        ]
    }
    changes = (FieldChange(uid="1", field_path="widgets_values[0]", old=None, new=25),)
    repaired = repair_field_changes(graph, changes)
    assert len(repaired) == 1
    assert repaired[0].old == 20
    assert repaired[0].new == 25


def test_repair_field_changes_keeps_tuple_when_nothing_changes() -> None:
    graph = {
        "nodes": [
            {
                "id": "n1",
                "properties": {"vibecomfy_uid": "n1"},
                "widgets_values": {"seed": 42},
            }
        ]
    }
    changes = (FieldChange(uid="n1", field_path="seed", old=42, new=43),)
    assert repair_field_changes(graph, changes) is changes
