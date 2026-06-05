from __future__ import annotations

import json
import os
import threading
import warnings
from pathlib import Path

import pytest

from vibecomfy.comfy_nodes.agent_audit import (
    REDACTED,
    artifact_entry,
    normalize_agent_edit_v2_metadata,
    redact_closed_set,
    write_allocation_failure_audit,
    write_audit,
    write_text_artifact,
)
from vibecomfy.comfy_nodes import agent_provider
from vibecomfy.comfy_nodes import megaplan_runtime
from vibecomfy.comfy_nodes.agent_contracts import (
    APPLY_ELIGIBILITY_REASONS,
    FailureKind,
    StageResult,
    TurnContext,
    derive_apply_eligibility,
    failure_envelope,
)
from vibecomfy.comfy_nodes.agent_diagnostics import (
    lower_stage_result,
    queue_stage_diagnostics,
    queue_stage_result,
    validate_stage_diagnostics,
    validate_stage_result,
)
from vibecomfy.comfy_nodes.agent_edit import (
    AgentEditState,
    _failure_response,
    _stale_rebaseline_recovery_issue,
)
from vibecomfy.comfy_nodes.agent_gates import (
    EXPLICIT_QUEUE_BLOCKER_CODES,
    derive_gates,
    initialize_gates,
    update_queue_gate,
    update_state_match_gate,
)
from vibecomfy.comfy_nodes.agent_session import (
    STRUCTURAL_PROJECTION_VERSION,
    accept_turn,
    allocate_turn,
    payload_hash,
    read_state,
    record_idempotent_response,
    rebaseline_session,
    reject_turn,
    structural_graph_hash,
    write_state_atomic,
)
from vibecomfy.contracts import (
    INTENT_NODE_CONTRACT_INVALID_CODE,
    INTENT_NODE_EDITOR_ONLY_CODE,
    INTENT_NODE_QUEUE_BLOCKER_CODE,
    RUNTIME_CODE_CONTRACT_VERSION,
    RUNTIME_CODE_EXECUTION_MODE,
    RUNTIME_CODE_POLICY_VERSION,
    intent_node_properties,
)
from vibecomfy._graph_utils import UI_ONLY_CLASS_TYPES as GRAPH_UTILS_UI_ONLY_CLASS_TYPES
from vibecomfy.porting.emitter import UI_ONLY_CLASS_TYPES as EMITTER_UI_ONLY_CLASS_TYPES
from vibecomfy.porting.lowering import LoweringDiagnostic, LoweringEvidence, LoweringResult
from vibecomfy.porting.ui_emitter import emit_ui_json
from vibecomfy.schema.provider import InputSpec, NodeSchema
from vibecomfy.workflow import ValidationIssue, VibeEdge, VibeNode, VibeWorkflow, WorkflowSource


class _Provider:
    def __init__(self, schemas: dict[str, NodeSchema]) -> None:
        self._schemas = schemas

    def get_schema(self, class_type: str) -> NodeSchema | None:
        return self._schemas.get(class_type)


def _schema(class_type: str, *, required_inputs: tuple[str, ...] = ()) -> NodeSchema:
    return NodeSchema(
        class_type=class_type,
        pack=None,
        inputs={
            name: InputSpec(type="IMAGE", required=True, default=None)
            for name in required_inputs
        },
        outputs=[],
        source_provider="test",
        confidence=1.0,
    )


def _schema_with_inputs(class_type: str, **inputs: InputSpec) -> NodeSchema:
    return NodeSchema(
        class_type=class_type,
        pack=None,
        inputs=inputs,
        outputs=[],
        source_provider="test",
        confidence=1.0,
    )


def _response_writer(base: Path):
    def _write(response: dict) -> Path:
        path = base / f"{response['action']}-{response['turn_id']}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(response, indent=2, sort_keys=True), encoding="utf-8")
        return path

    return _write


def _intent_metadata(*, kind: str, uid: str, intent: dict[str, object]) -> dict[str, object]:
    return {
        "_ui": {
            "properties": intent_node_properties(
                kind=kind,
                uid=uid,
                intent=intent,
                inputs=[("prompt", "STRING")],
                outputs=[("image", "IMAGE")],
            )
        }
    }


def _runtime_code_metadata(*, uid: str = "runtime-code", source: str = "value + 1") -> dict[str, object]:
    return {
        "_ui": {
            "properties": intent_node_properties(
                kind="code",
                uid=uid,
                intent={"source": source, "spec": "json metadata expression"},
                inputs=[("value", "INT")],
                outputs=[("result", "JSON")],
                extra_vibecomfy={
                    "runtime": {
                        "runtime_backed": True,
                        "runtime_contract_version": "runtime_code_v1",
                        "execution_mode": "expression_v1",
                        "timeout_ms": 1000,
                        "max_source_bytes": 16384,
                        "allowed_builtins": ["abs", "len", "min", "max", "round"],
                        "redaction_policy": ["source_hash_only", "closed_set_redaction"],
                        "policy_version": "runtime_code_policy_v1",
                        "passthrough_on_non_json": False,
                    }
                },
            )
        }
    }


def _request_graph(label: str) -> dict:
    return {
        "graph": {
            "nodes": [
                {
                    "id": 1,
                    "type": "SaveImage",
                    "widgets_values": [label],
                }
            ],
            "links": [],
        },
        "client_graph_hash": f"client-{label}",
        "task": f"edit {label}",
    }


def _record_candidate_response(
    *,
    root: Path,
    session_id: str,
    allocation,
    graph: dict | None = None,
    idempotency_key: str | None = None,
) -> dict:
    turn_id = str(allocation.context.turn_id)
    candidate_graph = graph or {"nodes": [{"id": 2, "type": "PreviewImage"}], "links": []}
    response = {"ok": True, "turn_id": turn_id, "graph": candidate_graph}
    record_idempotent_response(
        session_root=root,
        session_id=session_id,
        scope="edit",
        idempotency_key=idempotency_key,
        request_hash=allocation.request_hash,
        response=response,
        response_path=allocation.turn_dir / "response.json",
        operation="edit",
        turn_id=turn_id,
    )
    return candidate_graph


def test_session_allocates_zero_padded_turns_under_lock(tmp_path: Path) -> None:
    root = tmp_path / "sessions"
    allocated: list[str] = []

    def _allocate(index: int) -> None:
        allocation = allocate_turn(
            session_root=root,
            session_id="s1",
            request_payload={"index": index},
        )
        allocated.append(str(allocation.context.turn_id))

    threads = [threading.Thread(target=_allocate, args=(index,)) for index in range(6)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert sorted(allocated) == ["0001", "0002", "0003", "0004", "0005", "0006"]
    state = read_state(root / "s1")
    assert state["next_turn_index"] == 7
    assert sorted(state["turns"]) == sorted(allocated)


def test_session_idempotency_replays_same_hash_and_conflicts_on_different_hash(
    tmp_path: Path,
) -> None:
    root = tmp_path / "sessions"
    request = {"task": "change prefix"}
    allocation = allocate_turn(
        session_root=root,
        session_id="s1",
        request_payload=request,
        idempotency_key="same",
    )
    response = {"ok": True, "turn_id": allocation.context.turn_id}
    record_idempotent_response(
        session_root=root,
        session_id="s1",
        scope="edit",
        idempotency_key="same",
        request_hash=allocation.request_hash,
        response=response,
        response_path=allocation.turn_dir / "response.json",
        operation="edit",
        turn_id=allocation.context.turn_id,
    )

    replay = allocate_turn(
        session_root=root,
        session_id="s1",
        request_payload=request,
        idempotency_key="same",
    )
    assert replay.replay is not None
    assert replay.replay.response == response

    conflict = allocate_turn(
        session_root=root,
        session_id="s1",
        request_payload={"task": "different"},
        idempotency_key="same",
    )
    assert conflict.conflict is not None
    assert conflict.conflict.failure.kind is FailureKind.STALE_STATE_MISMATCH


# ── T8: idempotency regression tests (no hash-value assertions) ──────────


def test_edit_idempotency_replays_same_request_body(
    tmp_path: Path,
) -> None:
    """Duplicate same-body replay for the edit endpoint: the exact same
    payload with the same idempotency key returns the recorded response.

    This test does NOT assert on any hash value so that failures isolate
    idempotency plumbing from protocol-hash semantics."""
    root = tmp_path / "sessions"
    request = {"task": "edit replay A", "graph": {"nodes": [{"id": 1, "type": "Note"}], "links": []}}
    allocation = allocate_turn(
        session_root=root,
        session_id="s1",
        request_payload=request,
        idempotency_key="edit-replay-1",
    )
    response = {"ok": True, "turn_id": allocation.context.turn_id, "label": "first"}
    record_idempotent_response(
        session_root=root,
        session_id="s1",
        scope="edit",
        idempotency_key="edit-replay-1",
        request_hash=allocation.request_hash,
        response=response,
        response_path=allocation.turn_dir / "response.json",
        operation="edit",
        turn_id=allocation.context.turn_id,
    )

    replay = allocate_turn(
        session_root=root,
        session_id="s1",
        request_payload=request,
        idempotency_key="edit-replay-1",
    )
    assert replay.replay is not None
    assert replay.replay.response == response


def test_edit_idempotency_conflicts_on_different_request_body(
    tmp_path: Path,
) -> None:
    """Duplicate different-body conflict for the edit endpoint: a different
    payload with the same idempotency key after recording produces a
    stale-state conflict.

    This test does NOT assert on any hash value so that failures isolate
    idempotency plumbing from protocol-hash semantics."""
    root = tmp_path / "sessions"
    request_a = {"task": "edit A", "graph": {"nodes": [{"id": 1, "type": "Note"}], "links": []}}
    allocation = allocate_turn(
        session_root=root,
        session_id="s1",
        request_payload=request_a,
        idempotency_key="edit-conflict-2",
    )
    response = {"ok": True, "turn_id": allocation.context.turn_id}
    record_idempotent_response(
        session_root=root,
        session_id="s1",
        scope="edit",
        idempotency_key="edit-conflict-2",
        request_hash=allocation.request_hash,
        response=response,
        response_path=allocation.turn_dir / "response.json",
        operation="edit",
        turn_id=allocation.context.turn_id,
    )

    conflict = allocate_turn(
        session_root=root,
        session_id="s1",
        request_payload={"task": "edit B", "graph": {"nodes": [{"id": 2, "type": "PreviewImage"}], "links": []}},
        idempotency_key="edit-conflict-2",
    )
    assert conflict.conflict is not None
    assert conflict.conflict.failure.kind is FailureKind.STALE_STATE_MISMATCH


def test_accept_idempotency_replays_same_request_body(
    tmp_path: Path,
) -> None:
    """Duplicate same-body replay for the accept endpoint: calling
    accept_turn twice with the same idempotency key and payload returns
    the identical response."""
    root = tmp_path / "sessions"
    request = _request_graph("accept-replay")
    allocation = allocate_turn(session_root=root, session_id="s1", request_payload=request)
    turn_id = str(allocation.context.turn_id)
    _record_candidate_response(root=root, session_id="s1", allocation=allocation)
    action_hash = payload_hash(request["graph"])

    first = accept_turn(
        session_root=root,
        session_id="s1",
        turn_id=turn_id,
        client_graph_hash=action_hash,
        request_payload={"turn_id": turn_id, "action": "accept"},
        idempotency_key="accept-replay-2",
        response_writer=_response_writer(tmp_path / "responses"),
    )
    assert isinstance(first, dict)

    replayed = accept_turn(
        session_root=root,
        session_id="s1",
        turn_id=turn_id,
        client_graph_hash=action_hash,
        request_payload={"turn_id": turn_id, "action": "accept"},
        idempotency_key="accept-replay-2",
        response_writer=_response_writer(tmp_path / "responses"),
    )
    assert replayed == first


def test_accept_idempotency_conflicts_on_different_request_body(
    tmp_path: Path,
) -> None:
    """Duplicate different-body conflict for the accept endpoint: calling
    accept_turn with the same idempotency key but a different request
    payload produces an editor-ahead conflict."""
    root = tmp_path / "sessions"
    request = _request_graph("accept-conflict")
    allocation = allocate_turn(session_root=root, session_id="s1", request_payload=request)
    turn_id = str(allocation.context.turn_id)
    _record_candidate_response(root=root, session_id="s1", allocation=allocation)
    action_hash = payload_hash(request["graph"])

    first = accept_turn(
        session_root=root,
        session_id="s1",
        turn_id=turn_id,
        client_graph_hash=action_hash,
        request_payload={"turn_id": turn_id, "action": "accept", "mode": "safe"},
        idempotency_key="accept-conflict-2",
        response_writer=_response_writer(tmp_path / "responses"),
    )
    assert isinstance(first, dict)

    conflict = accept_turn(
        session_root=root,
        session_id="s1",
        turn_id=turn_id,
        client_graph_hash=action_hash,
        request_payload={"turn_id": turn_id, "action": "accept", "mode": "force"},
        idempotency_key="accept-conflict-2",
        response_writer=_response_writer(tmp_path / "responses"),
    )
    assert not isinstance(conflict, dict)
    assert conflict.kind is FailureKind.EDITOR_AHEAD_CONFLICT


def test_reject_idempotency_replays_same_request_body(
    tmp_path: Path,
) -> None:
    """Duplicate same-body replay for the reject endpoint: calling
    reject_turn twice with the same idempotency key and payload returns
    the identical response."""
    root = tmp_path / "sessions"
    request = _request_graph("reject-replay")
    allocation = allocate_turn(session_root=root, session_id="s1", request_payload=request)
    turn_id = str(allocation.context.turn_id)
    _record_candidate_response(root=root, session_id="s1", allocation=allocation)
    action_hash = payload_hash(request["graph"])

    first = reject_turn(
        session_root=root,
        session_id="s1",
        turn_id=turn_id,
        client_graph_hash=action_hash,
        request_payload={"turn_id": turn_id, "action": "reject"},
        idempotency_key="reject-replay-1",
        response_writer=_response_writer(tmp_path / "responses"),
    )
    assert isinstance(first, dict)

    replayed = reject_turn(
        session_root=root,
        session_id="s1",
        turn_id=turn_id,
        client_graph_hash=action_hash,
        request_payload={"turn_id": turn_id, "action": "reject"},
        idempotency_key="reject-replay-1",
        response_writer=_response_writer(tmp_path / "responses"),
    )
    assert replayed == first


def test_reject_idempotency_conflicts_on_different_request_body(
    tmp_path: Path,
) -> None:
    """Duplicate different-body conflict for the reject endpoint: calling
    reject_turn with the same idempotency key but a different request
    payload produces an editor-ahead conflict."""
    root = tmp_path / "sessions"
    request = _request_graph("reject-conflict")
    allocation = allocate_turn(session_root=root, session_id="s1", request_payload=request)
    turn_id = str(allocation.context.turn_id)
    _record_candidate_response(root=root, session_id="s1", allocation=allocation)
    action_hash = payload_hash(request["graph"])

    first = reject_turn(
        session_root=root,
        session_id="s1",
        turn_id=turn_id,
        client_graph_hash=action_hash,
        request_payload={"turn_id": turn_id, "action": "reject", "mode": "soft"},
        idempotency_key="reject-conflict-1",
        response_writer=_response_writer(tmp_path / "responses"),
    )
    assert isinstance(first, dict)

    conflict = reject_turn(
        session_root=root,
        session_id="s1",
        turn_id=turn_id,
        client_graph_hash=action_hash,
        request_payload={"turn_id": turn_id, "action": "reject", "mode": "hard"},
        idempotency_key="reject-conflict-1",
        response_writer=_response_writer(tmp_path / "responses"),
    )
    assert not isinstance(conflict, dict)
    assert conflict.kind is FailureKind.EDITOR_AHEAD_CONFLICT


def test_accept_reject_mutations_are_atomic_and_conflict_aware(tmp_path: Path) -> None:
    root = tmp_path / "sessions"
    request = _request_graph("hash-a")
    allocation = allocate_turn(
        session_root=root,
        session_id="s1",
        request_payload=request,
    )
    turn_id = str(allocation.context.turn_id)
    _record_candidate_response(root=root, session_id="s1", allocation=allocation)
    action_hash = payload_hash(request["graph"])

    accepted = accept_turn(
        session_root=root,
        session_id="s1",
        turn_id=turn_id,
        client_graph_hash=action_hash,
        request_payload={"turn_id": turn_id, "action": "accept"},
        idempotency_key="accept-1",
        response_writer=_response_writer(tmp_path / "responses"),
    )
    assert isinstance(accepted, dict)
    assert accepted["baseline_turn_id"] == turn_id
    state = read_state(root / "s1")
    assert state["baseline_turn_id"] == turn_id
    assert state["turns"][turn_id]["state"] == "accepted"
    assert state["idempotency_records"]["accept:accept-1"]["response_hash"] == payload_hash(accepted)

    replayed = accept_turn(
        session_root=root,
        session_id="s1",
        turn_id=turn_id,
        client_graph_hash=action_hash,
        request_payload={"turn_id": turn_id, "action": "accept"},
        idempotency_key="accept-1",
        response_writer=_response_writer(tmp_path / "responses"),
    )
    assert replayed == accepted

    rejected = reject_turn(
        session_root=root,
        session_id="s1",
        turn_id=turn_id,
        client_graph_hash=action_hash,
        request_payload={"turn_id": turn_id, "action": "reject"},
    )
    assert not isinstance(rejected, dict)
    assert rejected.kind is FailureKind.EDITOR_AHEAD_CONFLICT


def test_accept_updates_baseline_and_reject_replays_idempotently(tmp_path: Path) -> None:
    root = tmp_path / "sessions"
    first_request = _request_graph("first")
    first = allocate_turn(session_root=root, session_id="s1", request_payload=first_request)
    _record_candidate_response(root=root, session_id="s1", allocation=first)

    accepted = accept_turn(
        session_root=root,
        session_id="s1",
        turn_id=str(first.context.turn_id),
        client_graph_hash=payload_hash(first_request["graph"]),
        request_payload={"turn_id": str(first.context.turn_id), "action": "accept"},
        idempotency_key="accept-first",
        response_writer=_response_writer(tmp_path / "responses"),
    )
    assert isinstance(accepted, dict)
    assert accepted["baseline_turn_id"] == str(first.context.turn_id)

    second_request = _request_graph("second")
    second = allocate_turn(session_root=root, session_id="s1", request_payload=second_request)
    _record_candidate_response(root=root, session_id="s1", allocation=second)
    updated = accept_turn(
        session_root=root,
        session_id="s1",
        turn_id=str(second.context.turn_id),
        client_graph_hash=payload_hash(second_request["graph"]),
        request_payload={"turn_id": str(second.context.turn_id), "action": "accept"},
        idempotency_key="accept-second",
        response_writer=_response_writer(tmp_path / "responses"),
    )
    assert isinstance(updated, dict)
    assert updated["baseline_turn_id"] == str(second.context.turn_id)

    third_request = _request_graph("third")
    third = allocate_turn(session_root=root, session_id="s1", request_payload=third_request)
    _record_candidate_response(root=root, session_id="s1", allocation=third)
    rejected = reject_turn(
        session_root=root,
        session_id="s1",
        turn_id=str(third.context.turn_id),
        client_graph_hash=payload_hash(third_request["graph"]),
        request_payload={"turn_id": str(third.context.turn_id), "action": "reject"},
        idempotency_key="reject-first",
        response_writer=_response_writer(tmp_path / "responses"),
    )
    replayed = reject_turn(
        session_root=root,
        session_id="s1",
        turn_id=str(third.context.turn_id),
        client_graph_hash=payload_hash(third_request["graph"]),
        request_payload={"turn_id": str(third.context.turn_id), "action": "reject"},
        idempotency_key="reject-first",
        response_writer=_response_writer(tmp_path / "responses"),
    )

    assert isinstance(rejected, dict)
    assert replayed == rejected
    state = read_state(root / "s1")
    assert state["baseline_turn_id"] == str(second.context.turn_id)
    assert state["turns"][str(third.context.turn_id)]["state"] == "rejected"
    assert state["turns"][str(second.context.turn_id)]["state"] == "accepted"


def test_session_protocol_hashes_graph_subdict_and_records_candidate_hash(
    tmp_path: Path,
) -> None:
    root = tmp_path / "sessions"
    request = _request_graph("before")
    allocation = allocate_turn(
        session_root=root,
        session_id="s1",
        request_payload=request,
        idempotency_key="edit-1",
    )
    turn_id = str(allocation.context.turn_id)
    submit_graph_hash = payload_hash(request["graph"])

    state = read_state(root / "s1")
    turn_record = state["turns"][turn_id]
    assert turn_record["submit_graph_hash"] == submit_graph_hash
    assert turn_record["submit_structural_graph_hash"] == structural_graph_hash(request["graph"])
    assert turn_record["submitted_client_graph_hash"] == "client-before"
    assert turn_record["submit_graph_hash"] != payload_hash(request)

    response = {
        "ok": True,
        "turn_id": turn_id,
        "graph": {"nodes": [{"id": 2, "type": "PreviewImage"}], "links": []},
    }
    record_idempotent_response(
        session_root=root,
        session_id="s1",
        scope="edit",
        idempotency_key="edit-1",
        request_hash=allocation.request_hash,
        response=response,
        response_path=allocation.turn_dir / "response.json",
        operation="edit",
        turn_id=turn_id,
    )

    state = read_state(root / "s1")
    assert state["turns"][turn_id]["candidate_graph_hash"] == payload_hash(response["graph"])
    assert state["turns"][turn_id]["candidate_structural_graph_hash"] == structural_graph_hash(
        response["graph"]
    )


def test_allocate_turn_captures_submitted_baseline_snapshot(tmp_path: Path) -> None:
    root = tmp_path / "sessions"
    first_request = _request_graph("first-baseline-snapshot")
    first = allocate_turn(session_root=root, session_id="s1", request_payload=first_request)
    first_id = str(first.context.turn_id)
    first_candidate = _record_candidate_response(root=root, session_id="s1", allocation=first)

    state = read_state(root / "s1")
    first_record = state["turns"][first_id]
    assert first_record["submitted_baseline_graph_hash"] is None
    assert first_record["submitted_baseline_graph_hash_kind"] is None
    assert first_record["submitted_baseline_graph_hash_version"] is None
    assert first_record["submitted_baseline_source"] == "none"
    assert first_record["submitted_baseline_rebaseline_id"] is None

    accepted = accept_turn(
        session_root=root,
        session_id="s1",
        turn_id=first_id,
        client_graph_hash=payload_hash(first_request["graph"]),
        request_payload={"turn_id": first_id, "action": "accept"},
    )
    assert isinstance(accepted, dict)

    second_request = _request_graph("second-baseline-snapshot")
    second = allocate_turn(session_root=root, session_id="s1", request_payload=second_request)
    second_id = str(second.context.turn_id)
    state = read_state(root / "s1")
    second_record = state["turns"][second_id]
    assert second_record["submitted_baseline_graph_hash"] == structural_graph_hash(first_candidate)
    assert second_record["submitted_baseline_graph_hash_kind"] == "structural"
    assert second_record["submitted_baseline_graph_hash_version"] == 2
    assert second_record["submitted_baseline_source"] == "turn"
    assert second_record["submitted_baseline_turn_id"] == first_id


def test_rebaseline_session_updates_structural_baseline_and_persists_source_graph(
    tmp_path: Path,
) -> None:
    root = tmp_path / "sessions"
    graph = _request_graph("rebaseline-success")["graph"]

    response = rebaseline_session(
        session_root=root,
        session_id="s1",
        request_payload={
            "session_id": "s1",
            "graph": graph,
            "last_known_baseline_graph_hash": None,
            "reason": "continue_from_canvas",
            "idempotency_key": "reb-1",
        },
        idempotency_key="reb-1",
    )

    assert isinstance(response, dict)
    assert response["ok"] is True
    assert response["action"] == "rebaseline"
    assert response["baseline_turn_id"] is None
    assert response["baseline_graph_hash"] == structural_graph_hash(graph)
    assert response["baseline_graph_hash_kind"] == "structural"
    assert response["baseline_source"] == "rebaseline"
    assert response["rebaseline_id"] == "0001"

    session_dir = root / "s1"
    graph_path = session_dir / "_rebaseline" / "0001" / "graph.ui.json"
    metadata_path = session_dir / "_rebaseline" / "0001" / "metadata.json"
    assert json.loads(graph_path.read_text(encoding="utf-8")) == graph
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    assert metadata["action"] == "rebaseline"
    assert metadata["reason"] == "continue_from_canvas"
    assert metadata["next_baseline_graph_hash"] == structural_graph_hash(graph)

    state = read_state(session_dir)
    assert state["baseline_graph_hash"] == structural_graph_hash(graph)
    assert state["baseline_turn_id"] is None
    assert state["baseline_rebaseline_id"] == "0001"
    assert state["baseline_graph_source_path"] == "_rebaseline/0001/graph.ui.json"


def test_rebaseline_session_enforces_explicit_null_cas_and_does_not_mutate_on_mismatch(
    tmp_path: Path,
) -> None:
    root = tmp_path / "sessions"
    first_graph = _request_graph("rebaseline-first")["graph"]
    first = rebaseline_session(
        session_root=root,
        session_id="s1",
        request_payload={
            "session_id": "s1",
            "graph": first_graph,
            "last_known_baseline_graph_hash": None,
            "reason": "continue_from_canvas",
        },
    )
    assert isinstance(first, dict)

    second_graph = _request_graph("rebaseline-stale")["graph"]
    failure = rebaseline_session(
        session_root=root,
        session_id="s1",
        request_payload={
            "session_id": "s1",
            "graph": second_graph,
            "last_known_baseline_graph_hash": None,
            "reason": "stale_state_recovery",
        },
    )

    assert not isinstance(failure, dict)
    assert failure.kind is FailureKind.STALE_STATE_MISMATCH
    assert (
        failure.agent_failure_context["reason"]
        == "rebaseline_structural_baseline_cas_mismatch"
    )
    state = read_state(root / "s1")
    assert state["baseline_graph_hash"] == structural_graph_hash(first_graph)
    assert state["baseline_rebaseline_id"] == "0001"
    assert state["next_rebaseline_index"] == 2
    assert not (root / "s1" / "_rebaseline" / "0002").exists()


def test_rebaseline_session_replays_same_idempotency_key_and_conflicts_on_different_body(
    tmp_path: Path,
) -> None:
    root = tmp_path / "sessions"
    graph = _request_graph("rebaseline-replay")["graph"]
    payload = {
        "session_id": "s1",
        "graph": graph,
        "last_known_baseline_graph_hash": None,
        "reason": "continue_from_canvas",
        "idempotency_key": "reb-replay",
    }

    first = rebaseline_session(
        session_root=root,
        session_id="s1",
        request_payload=payload,
        idempotency_key="reb-replay",
    )
    replay = rebaseline_session(
        session_root=root,
        session_id="s1",
        request_payload=payload,
        idempotency_key="reb-replay",
    )
    conflict = rebaseline_session(
        session_root=root,
        session_id="s1",
        request_payload={**payload, "reason": "undo"},
        idempotency_key="reb-replay",
    )

    assert isinstance(first, dict)
    assert replay == first
    assert not isinstance(conflict, dict)
    assert conflict.agent_failure_context["idempotency_key"] == "reb-replay"
    state = read_state(root / "s1")
    assert sorted(path.name for path in (root / "s1" / "_rebaseline").iterdir()) == ["0001"]
    assert state["idempotency_records"]["rebaseline:reb-replay"]["rebaseline_id"] == "0001"


def test_read_state_normalizes_turn_baseline_from_candidate_artifact_on_projection_drift(
    tmp_path: Path,
) -> None:
    session_dir = tmp_path / "s-turn-normalize"
    candidate_graph = _request_graph("normalize-turn")["graph"]
    turn_dir = session_dir / "turns" / "0001"
    turn_dir.mkdir(parents=True, exist_ok=True)
    (turn_dir / "candidate.ui.json").write_text(
        json.dumps(candidate_graph, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    state = read_state(session_dir)
    state["turns"]["0001"] = {
        "state": "accepted",
        "candidate_graph_hash": payload_hash(candidate_graph),
        "candidate_structural_graph_hash": "stale-structural-hash",
        "candidate_structural_graph_hash_version": STRUCTURAL_PROJECTION_VERSION - 1,
    }
    state["baseline_turn_id"] = "0001"
    state["baseline_graph_hash"] = "stale-structural-hash"
    state["baseline_graph_hash_kind"] = "structural"
    state["baseline_graph_hash_version"] = STRUCTURAL_PROJECTION_VERSION - 1
    state["baseline_source"] = "turn"
    write_state_atomic(session_dir, state)

    normalized = read_state(session_dir)

    expected = structural_graph_hash(candidate_graph)
    assert normalized["baseline_turn_id"] == "0001"
    assert normalized["baseline_graph_hash"] == expected
    assert normalized["baseline_graph_hash_kind"] == "structural"
    assert normalized["baseline_graph_hash_version"] == STRUCTURAL_PROJECTION_VERSION
    assert normalized["baseline_source"] == "turn"
    assert normalized["baseline_graph_source_path"] == "turns/0001/candidate.ui.json"
    assert normalized["turns"]["0001"]["candidate_structural_graph_hash"] == expected
    assert (
        normalized["turns"]["0001"]["candidate_structural_graph_hash_version"]
        == STRUCTURAL_PROJECTION_VERSION
    )


def test_read_state_normalizes_rebaseline_baseline_from_source_artifact_on_projection_drift(
    tmp_path: Path,
) -> None:
    session_dir = tmp_path / "s-rebaseline-normalize"
    graph = _request_graph("normalize-rebaseline")["graph"]
    graph_path = session_dir / "_rebaseline" / "0003" / "graph.ui.json"
    graph_path.parent.mkdir(parents=True, exist_ok=True)
    graph_path.write_text(
        json.dumps(graph, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    state = read_state(session_dir)
    state["baseline_turn_id"] = None
    state["baseline_graph_hash"] = "stale-rebaseline-hash"
    state["baseline_graph_hash_kind"] = "structural"
    state["baseline_graph_hash_version"] = STRUCTURAL_PROJECTION_VERSION - 1
    state["baseline_source"] = "rebaseline"
    state["baseline_rebaseline_id"] = "0003"
    state["baseline_graph_source_path"] = "_rebaseline/0003/graph.ui.json"
    write_state_atomic(session_dir, state)

    normalized = read_state(session_dir)

    expected = structural_graph_hash(graph)
    assert normalized["baseline_turn_id"] is None
    assert normalized["baseline_graph_hash"] == expected
    assert normalized["baseline_graph_hash_kind"] == "structural"
    assert normalized["baseline_graph_hash_version"] == STRUCTURAL_PROJECTION_VERSION
    assert normalized["baseline_source"] == "rebaseline"
    assert normalized["baseline_rebaseline_id"] == "0003"
    assert normalized["baseline_graph_source_path"] == "_rebaseline/0003/graph.ui.json"


def test_rebaseline_session_rejects_unknown_reason_without_writing_artifacts(
    tmp_path: Path,
) -> None:
    root = tmp_path / "sessions"
    graph = _request_graph("rebaseline-invalid-reason")["graph"]

    failure = rebaseline_session(
        session_root=root,
        session_id="s1",
        request_payload={
            "session_id": "s1",
            "graph": graph,
            "last_known_baseline_graph_hash": None,
            "reason": "invalid-reason",
            "idempotency_key": "reb-invalid",
        },
        idempotency_key="reb-invalid",
    )

    assert not isinstance(failure, dict)
    assert failure.kind is FailureKind.VALIDATION_ERROR
    assert failure.agent_failure_context["reason"] == "invalid-reason"
    assert list(failure.agent_failure_context["allowed_reasons"]) == [
        "undo",
        "stale_state_recovery",
        "continue_from_canvas",
    ]
    assert not (root / "s1" / "_rebaseline").exists()
    state = read_state(root / "s1")
    assert state["baseline_graph_hash"] is None
    assert state["baseline_source"] == "none"


def test_legacy_turn_derives_expected_baseline_from_submit_structural_hash(
    tmp_path: Path,
) -> None:
    root = tmp_path / "sessions"
    first_request = _request_graph("legacy-baseline")
    first = allocate_turn(session_root=root, session_id="s1", request_payload=first_request)
    first_id = str(first.context.turn_id)
    first_candidate = _record_candidate_response(root=root, session_id="s1", allocation=first)
    accepted_first = accept_turn(
        session_root=root,
        session_id="s1",
        turn_id=first_id,
        client_graph_hash=payload_hash(first_request["graph"]),
        request_payload={"turn_id": first_id, "action": "accept"},
    )
    assert isinstance(accepted_first, dict)

    legacy_request = {
        "graph": first_candidate,
        "client_graph_hash": payload_hash(first_candidate),
        "task": "edit legacy-derived",
    }
    legacy = allocate_turn(session_root=root, session_id="s1", request_payload=legacy_request)
    legacy_id = str(legacy.context.turn_id)
    _record_candidate_response(root=root, session_id="s1", allocation=legacy)
    state = read_state(root / "s1")
    legacy_record = state["turns"][legacy_id]
    for key in list(legacy_record):
        if key.startswith("submitted_baseline_"):
            del legacy_record[key]
    write_state_atomic(root / "s1", state)

    accepted_legacy = accept_turn(
        session_root=root,
        session_id="s1",
        turn_id=legacy_id,
        client_graph_hash=payload_hash(legacy_request["graph"]),
        request_payload={"turn_id": legacy_id, "action": "accept"},
    )

    assert isinstance(accepted_legacy, dict)
    assert (
        accepted_legacy["expected_baseline_graph_hash"] == structural_graph_hash(first_candidate)
    )
    assert accepted_legacy["expected_baseline_graph_hash_kind"] == "structural"


def test_legacy_turn_without_trustworthy_expected_baseline_fails_closed(
    tmp_path: Path,
) -> None:
    root = tmp_path / "sessions"
    session_dir = root / "s1"
    state = read_state(session_dir)
    state["baseline_graph_hash"] = "legacy-raw-baseline"
    state["baseline_graph_hash_kind"] = "raw"
    state["baseline_source"] = "legacy"
    write_state_atomic(session_dir, state)

    request = _request_graph("legacy-untrusted")
    allocation = allocate_turn(session_root=root, session_id="s1", request_payload=request)
    turn_id = str(allocation.context.turn_id)
    _record_candidate_response(root=root, session_id="s1", allocation=allocation)
    state = read_state(session_dir)
    turn_record = state["turns"][turn_id]
    for key in list(turn_record):
        if key.startswith("submitted_baseline_"):
            del turn_record[key]
    write_state_atomic(session_dir, state)

    failure = accept_turn(
        session_root=root,
        session_id="s1",
        turn_id=turn_id,
        client_graph_hash=payload_hash(request["graph"]),
        request_payload={"turn_id": turn_id, "action": "accept"},
    )

    assert not isinstance(failure, dict)
    assert failure.kind is FailureKind.STALE_STATE_MISMATCH
    assert failure.agent_failure_context["reason"] == "legacy_expected_baseline_untrusted"
    assert failure.agent_failure_context["recovery"]["action"] == "rebaseline"
    state = read_state(session_dir)
    assert state["turns"][turn_id]["state"] == "candidate"
    assert state["turns"][turn_id]["action_request_hash"] is None
    assert state["baseline_graph_hash"] == "legacy-raw-baseline"
    assert state["baseline_graph_hash_kind"] == "raw"


def test_accept_structural_cas_mismatch_fails_without_action_writes(
    tmp_path: Path,
) -> None:
    root = tmp_path / "sessions"
    first_request = _request_graph("cas-first")
    first = allocate_turn(session_root=root, session_id="s1", request_payload=first_request)
    first_id = str(first.context.turn_id)
    first_candidate = _record_candidate_response(root=root, session_id="s1", allocation=first)
    accepted_first = accept_turn(
        session_root=root,
        session_id="s1",
        turn_id=first_id,
        client_graph_hash=payload_hash(first_request["graph"]),
        request_payload={"turn_id": first_id, "action": "accept"},
    )
    assert isinstance(accepted_first, dict)

    stale_request = _request_graph("cas-stale")
    stale_allocation = allocate_turn(
        session_root=root,
        session_id="s1",
        request_payload=stale_request,
    )
    stale_id = str(stale_allocation.context.turn_id)
    stale_candidate = _record_candidate_response(
        root=root,
        session_id="s1",
        allocation=stale_allocation,
        idempotency_key="edit-cas-stale",
    )
    state = read_state(root / "s1")
    stale_record = state["turns"][stale_id]
    del stale_record["candidate_structural_graph_hash"]
    del stale_record["candidate_structural_graph_hash_version"]
    state["baseline_turn_id"] = None
    state["baseline_graph_hash"] = structural_graph_hash(
        {"nodes": [{"id": 77, "type": "PreviewImage"}], "links": []}
    )
    state["baseline_graph_hash_kind"] = "structural"
    state["baseline_graph_hash_version"] = 2
    state["baseline_source"] = "rebaseline"
    state["baseline_rebaseline_id"] = "manual-cas-drift"
    state["baseline_graph_source_path"] = "_rebaseline/manual-cas-drift/graph.ui.json"
    write_state_atomic(root / "s1", state)

    failure = accept_turn(
        session_root=root,
        session_id="s1",
        turn_id=stale_id,
        client_graph_hash=payload_hash(stale_request["graph"]),
        request_payload={"turn_id": stale_id, "action": "accept"},
        idempotency_key="cas-stale",
        response_writer=_response_writer(root / "responses"),
    )

    assert not isinstance(failure, dict)
    assert failure.kind is FailureKind.STALE_STATE_MISMATCH
    assert failure.agent_failure_context["reason"] == "structural_baseline_cas_mismatch"
    assert failure.agent_failure_context["expected_baseline_graph_hash"] == structural_graph_hash(
        first_candidate
    )
    assert failure.agent_failure_context["submitted_baseline_graph_hash"] == structural_graph_hash(
        first_candidate
    )
    state = read_state(root / "s1")
    stale_record = state["turns"][stale_id]
    assert stale_record["state"] == "candidate"
    assert stale_record["client_graph_hash"] is None
    assert stale_record["action_request_hash"] is None
    assert stale_record["action_client_graph_hash"] is None
    assert "candidate_structural_graph_hash" not in stale_record
    assert "accept:cas-stale" not in state["idempotency_records"]
    assert state["baseline_turn_id"] is None
    assert state["baseline_source"] == "rebaseline"
    assert state["baseline_graph_hash"] != structural_graph_hash(stale_candidate)


def test_accept_reject_validate_against_submit_graph_hash_before_action_writes(
    tmp_path: Path,
) -> None:
    root = tmp_path / "sessions"
    request = _request_graph("before")
    allocation = allocate_turn(session_root=root, session_id="s1", request_payload=request)
    turn_id = str(allocation.context.turn_id)

    stale = accept_turn(
        session_root=root,
        session_id="s1",
        turn_id=turn_id,
        client_graph_hash=payload_hash({"different": True}),
        request_payload={"turn_id": turn_id, "action": "accept"},
    )

    assert not isinstance(stale, dict)
    assert stale.kind is FailureKind.STALE_STATE_MISMATCH
    state = read_state(root / "s1")
    turn_record = state["turns"][turn_id]
    assert turn_record["state"] == "candidate"
    assert turn_record["client_graph_hash"] is None
    assert turn_record["action_request_hash"] is None
    assert turn_record["action_client_graph_hash"] is None


def test_accept_reject_fail_closed_when_candidate_hash_missing_before_action_writes(
    tmp_path: Path,
) -> None:
    root = tmp_path / "sessions"
    request = _request_graph("before")
    allocation = allocate_turn(session_root=root, session_id="s1", request_payload=request)
    turn_id = str(allocation.context.turn_id)

    failure = accept_turn(
        session_root=root,
        session_id="s1",
        turn_id=turn_id,
        client_graph_hash=payload_hash(request["graph"]),
        request_payload={"turn_id": turn_id, "action": "accept"},
    )

    assert not isinstance(failure, dict)
    assert failure.kind is FailureKind.STALE_STATE_MISMATCH
    assert failure.agent_failure_context["candidate_graph_hash_present"] is False
    state = read_state(root / "s1")
    turn_record = state["turns"][turn_id]
    assert turn_record["state"] == "candidate"
    assert turn_record["client_graph_hash"] is None
    assert turn_record["action_request_hash"] is None
    assert turn_record["action_client_graph_hash"] is None
    assert state["baseline_turn_id"] is None
    assert state["baseline_graph_hash"] is None


def test_accept_reject_fail_closed_when_submit_hash_missing_before_action_writes(
    tmp_path: Path,
) -> None:
    root = tmp_path / "sessions"
    request = _request_graph("before")
    allocation = allocate_turn(session_root=root, session_id="s1", request_payload=request)
    turn_id = str(allocation.context.turn_id)
    candidate_graph = {"nodes": [{"id": 9, "type": "SaveImage"}], "links": []}
    record_idempotent_response(
        session_root=root,
        session_id="s1",
        scope="edit",
        idempotency_key=None,
        request_hash=allocation.request_hash,
        response={"ok": True, "turn_id": turn_id, "graph": candidate_graph},
        response_path=allocation.turn_dir / "response.json",
        operation="edit",
        turn_id=turn_id,
    )
    state = read_state(root / "s1")
    del state["turns"][turn_id]["submit_graph_hash"]
    write_state_atomic(root / "s1", state)

    failure = accept_turn(
        session_root=root,
        session_id="s1",
        turn_id=turn_id,
        client_graph_hash=payload_hash(request["graph"]),
        request_payload={"turn_id": turn_id, "action": "accept"},
    )

    assert not isinstance(failure, dict)
    assert failure.kind is FailureKind.STALE_STATE_MISMATCH
    assert failure.agent_failure_context["submit_graph_hash_present"] is False
    state = read_state(root / "s1")
    turn_record = state["turns"][turn_id]
    assert turn_record["state"] == "candidate"
    assert turn_record["client_graph_hash"] is None
    assert turn_record["action_request_hash"] is None
    assert turn_record["action_client_graph_hash"] is None
    assert state["baseline_turn_id"] is None
    assert state["baseline_graph_hash"] is None


def test_v2_accept_records_live_canvas_token_mismatch_diagnostic_and_updates_baseline(
    tmp_path: Path,
) -> None:
    root = tmp_path / "sessions"
    request = _request_graph("v2-same-canvas")
    request["client_live_canvas_token"] = "live:rev:1:client-v2-same-canvas"
    allocation = allocate_turn(session_root=root, session_id="s1", request_payload=request)
    turn_id = str(allocation.context.turn_id)
    candidate_graph = {"nodes": [{"id": 2, "type": "PreviewImage"}], "links": []}
    record_idempotent_response(
        session_root=root,
        session_id="s1",
        scope="edit",
        idempotency_key=None,
        request_hash=allocation.request_hash,
        response={
            "ok": True,
            "turn_id": turn_id,
            "graph": candidate_graph,
            "delta_ops": [{"op": "set_mode", "target": {"scope_path": [], "uid": "2"}, "mode": 4}],
        },
        response_path=allocation.turn_dir / "response.json",
        operation="edit",
        turn_id=turn_id,
    )
    submit_graph_hash = payload_hash(request["graph"])
    candidate_graph_hash = payload_hash(candidate_graph)

    accepted = accept_turn(
        session_root=root,
        session_id="s1",
        turn_id=turn_id,
        client_graph_hash=request["client_graph_hash"],
        request_payload={
            "turn_id": turn_id,
            "action": "accept",
            "submit_graph_hash": submit_graph_hash,
            "candidate_graph_hash": candidate_graph_hash,
            "client_live_canvas_token": "live:rev:2:client-v2-same-canvas",
        },
    )

    assert isinstance(accepted, dict)
    assert accepted["ok"] is True
    assert accepted["baseline_turn_id"] == turn_id
    assert accepted["baseline_graph_hash"] == structural_graph_hash(candidate_graph)
    assert accepted["baseline_graph_hash_kind"] == "structural"
    assert accepted["candidate_graph_hash"] == candidate_graph_hash
    assert accepted["submitted_client_live_canvas_token"] == request["client_live_canvas_token"]
    assert accepted["diagnostics"][0]["code"] == "client_live_canvas_token_mismatch"
    assert (
        accepted["diagnostics"][0]["detail"]["client_live_canvas_token"]
        == "live:rev:2:client-v2-same-canvas"
    )
    state = read_state(root / "s1")
    assert state["baseline_turn_id"] == turn_id
    assert state["baseline_graph_hash"] == structural_graph_hash(candidate_graph)
    assert state["baseline_graph_hash_kind"] == "structural"
    assert state["turns"][turn_id]["state"] == "accepted"


def test_new_submit_marks_prior_candidates_unknown_and_accept_updates_baseline_graph_hash(
    tmp_path: Path,
) -> None:
    root = tmp_path / "sessions"
    first_request = _request_graph("first")
    second_request = _request_graph("second")
    first = allocate_turn(session_root=root, session_id="s1", request_payload=first_request)
    first_id = str(first.context.turn_id)
    first_candidate_graph = {"nodes": [{"id": 9, "type": "SaveImage"}], "links": []}
    record_idempotent_response(
        session_root=root,
        session_id="s1",
        scope="edit",
        idempotency_key="candidate-first",
        request_hash=first.request_hash,
        response={"ok": True, "turn_id": first_id, "graph": first_candidate_graph},
        response_path=first.turn_dir / "response.json",
        operation="edit",
        turn_id=first_id,
    )
    second = allocate_turn(session_root=root, session_id="s1", request_payload=second_request)
    second_id = str(second.context.turn_id)
    state = read_state(root / "s1")

    assert list(second.unknown_transitions) == [
        {
            "session_id": "s1",
            "turn_id": first_id,
            "from_state": "candidate",
            "to_state": "unknown",
            "reason": "superseded_by_new_submit",
            "superseded_by_turn_id": second_id,
            "transitioned_at": state["turns"][first_id]["unknown_at"],
        }
    ]
    assert state["turns"][first_id]["state"] == "unknown"

    rejected_unknown = reject_turn(
        session_root=root,
        session_id="s1",
        turn_id=first_id,
        client_graph_hash=payload_hash(first_request["graph"]),
        request_payload={"turn_id": first_id, "action": "reject"},
    )
    assert not isinstance(rejected_unknown, dict)
    assert rejected_unknown.kind is FailureKind.STALE_STATE_MISMATCH

    second_candidate_graph = {"nodes": [{"id": 10, "type": "PreviewImage"}], "links": []}
    record_idempotent_response(
        session_root=root,
        session_id="s1",
        scope="edit",
        idempotency_key="candidate-second",
        request_hash=second.request_hash,
        response={"ok": True, "turn_id": second_id, "graph": second_candidate_graph},
        response_path=second.turn_dir / "response.json",
        operation="edit",
        turn_id=second_id,
    )

    accepted = accept_turn(
        session_root=root,
        session_id="s1",
        turn_id=second_id,
        client_graph_hash=payload_hash(second_request["graph"]),
        request_payload={"turn_id": second_id, "action": "accept"},
    )

    assert isinstance(accepted, dict)
    assert accepted["baseline_graph_hash"] == structural_graph_hash(second_candidate_graph)
    assert accepted["unknown_transitions"] == []
    state = read_state(root / "s1")
    assert state["baseline_graph_hash"] == structural_graph_hash(second_candidate_graph)
    assert state["turns"][second_id]["state"] == "accepted"


def test_reject_preserves_existing_baseline_graph_hash(
    tmp_path: Path,
) -> None:
    root = tmp_path / "sessions"
    baseline_request = _request_graph("baseline")
    baseline_allocation = allocate_turn(
        session_root=root,
        session_id="s1",
        request_payload=baseline_request,
    )
    baseline_turn_id = str(baseline_allocation.context.turn_id)
    baseline_candidate_graph = _record_candidate_response(
        root=root,
        session_id="s1",
        allocation=baseline_allocation,
        graph={"nodes": [{"id": 2, "type": "PreviewImage", "widgets_values": ["baseline"]}], "links": []},
    )
    baseline_candidate_structural_hash = structural_graph_hash(baseline_candidate_graph)

    accepted = accept_turn(
        session_root=root,
        session_id="s1",
        turn_id=baseline_turn_id,
        client_graph_hash=payload_hash(baseline_request["graph"]),
        request_payload={"turn_id": baseline_turn_id, "action": "accept"},
    )
    assert isinstance(accepted, dict)
    assert accepted["baseline_turn_id"] == baseline_turn_id
    assert accepted["baseline_graph_hash"] == baseline_candidate_structural_hash

    rejected_request = _request_graph("reject-next")
    rejected_allocation = allocate_turn(
        session_root=root,
        session_id="s1",
        request_payload=rejected_request,
    )
    rejected_turn_id = str(rejected_allocation.context.turn_id)
    rejected_candidate_graph = _record_candidate_response(
        root=root,
        session_id="s1",
        allocation=rejected_allocation,
        graph={"nodes": [{"id": 3, "type": "SaveImage", "widgets_values": ["reject-next"]}], "links": []},
    )

    rejected = reject_turn(
        session_root=root,
        session_id="s1",
        turn_id=rejected_turn_id,
        client_graph_hash=payload_hash(rejected_request["graph"]),
        request_payload={"turn_id": rejected_turn_id, "action": "reject"},
    )

    assert isinstance(rejected, dict)
    assert rejected["baseline_turn_id"] == baseline_turn_id
    assert rejected["baseline_graph_hash"] == baseline_candidate_structural_hash
    assert rejected["candidate_graph_hash"] == payload_hash(rejected_candidate_graph)
    state = read_state(root / "s1")
    assert state["baseline_turn_id"] == baseline_turn_id
    assert state["baseline_graph_hash"] == baseline_candidate_structural_hash
    assert state["turns"][rejected_turn_id]["state"] == "rejected"


def test_accept_idempotency_conflicts_on_reused_key_with_different_request_payload(
    tmp_path: Path,
) -> None:
    root = tmp_path / "sessions"
    request = _request_graph("candidate")
    allocation = allocate_turn(session_root=root, session_id="s1", request_payload=request)
    turn_id = str(allocation.context.turn_id)
    _record_candidate_response(root=root, session_id="s1", allocation=allocation)
    action_hash = payload_hash(request["graph"])

    first = accept_turn(
        session_root=root,
        session_id="s1",
        turn_id=turn_id,
        client_graph_hash=action_hash,
        request_payload={"turn_id": turn_id, "action": "accept", "mode": "safe"},
        idempotency_key="accept-same",
        response_writer=_response_writer(tmp_path / "responses"),
    )
    conflict = accept_turn(
        session_root=root,
        session_id="s1",
        turn_id=turn_id,
        client_graph_hash=action_hash,
        request_payload={"turn_id": turn_id, "action": "accept", "mode": "force"},
        idempotency_key="accept-same",
        response_writer=_response_writer(tmp_path / "responses"),
    )

    assert isinstance(first, dict)
    assert not isinstance(conflict, dict)
    assert conflict.kind is FailureKind.EDITOR_AHEAD_CONFLICT
    assert conflict.agent_failure_context["idempotency_key"] == "accept-same"


def test_concurrent_accept_and_reject_leave_single_terminal_turn_state(tmp_path: Path) -> None:
    root = tmp_path / "sessions"
    request = _request_graph("candidate")
    allocation = allocate_turn(session_root=root, session_id="s1", request_payload=request)
    turn_id = str(allocation.context.turn_id)
    _record_candidate_response(root=root, session_id="s1", allocation=allocation)
    action_hash = payload_hash(request["graph"])
    results: list[dict | object] = []

    def _run_accept() -> None:
        results.append(
            accept_turn(
                session_root=root,
                session_id="s1",
                turn_id=turn_id,
                client_graph_hash=action_hash,
                request_payload={"turn_id": turn_id, "action": "accept"},
                idempotency_key="accept-concurrent",
                response_writer=_response_writer(tmp_path / "responses"),
            )
        )

    def _run_reject() -> None:
        results.append(
            reject_turn(
                session_root=root,
                session_id="s1",
                turn_id=turn_id,
                client_graph_hash=action_hash,
                request_payload={"turn_id": turn_id, "action": "reject"},
                idempotency_key="reject-concurrent",
                response_writer=_response_writer(tmp_path / "responses"),
            )
        )

    accept_thread = threading.Thread(target=_run_accept)
    reject_thread = threading.Thread(target=_run_reject)
    accept_thread.start()
    reject_thread.start()
    accept_thread.join()
    reject_thread.join()

    successes = [result for result in results if isinstance(result, dict)]
    failures = [result for result in results if not isinstance(result, dict)]

    assert len(successes) == 1
    assert len(failures) == 1
    assert failures[0].kind is FailureKind.EDITOR_AHEAD_CONFLICT

    state = read_state(root / "s1")
    terminal_state = state["turns"][turn_id]["state"]
    assert terminal_state in {"accepted", "rejected"}
    if terminal_state == "accepted":
        assert state["baseline_turn_id"] == turn_id
    else:
        assert state["baseline_turn_id"] is None


def test_audit_redacts_closed_set_and_references_raw_artifacts(tmp_path: Path) -> None:
    raw_path = tmp_path / "raw.txt"
    raw_ref = write_text_artifact(raw_path, "x" * 600)
    context_allocation = allocate_turn(
        session_root=tmp_path / "sessions",
        session_id="s1",
        request_payload={"task": "audit"},
    )
    context = context_allocation.context
    context.record_stage(StageResult(stage="agent", ok=True, blocking=False))
    audit_ref = write_audit(
        tmp_path / "audit",
        context=context,
        turn_state="candidate",
        stage_results=context.stage_results,
        response={"ok": True, "Authorization": "Bearer secret"},
        artifacts={"raw": raw_path, "already_ref": raw_ref},
        metadata={
            "api_key": "sk-secret",
            "nested": {"provider_secret": "secret-value"},
        },
    )

    audit = json.loads(Path(audit_ref.path).read_text(encoding="utf-8"))
    assert audit["turn_state"] == "candidate"
    assert audit["redactions"] == ["api_key", "auth_header", "provider_secret"]
    assert audit["metadata"]["api_key"] == REDACTED
    assert audit["metadata"]["nested"]["provider_secret"] == REDACTED
    assert audit["response_ref"]["sha256"]
    assert audit["artifacts"]["raw"]["sha256"] == raw_ref.sha256
    assert audit["artifacts"]["raw"]["byte_count"] == 600
    assert len(audit["artifacts"]["raw"]["preview"]) == 512
    assert "inline" in artifact_entry(raw_path)


def test_audit_preserves_bounded_intent_node_metadata_snapshot(tmp_path: Path) -> None:
    context_allocation = allocate_turn(
        session_root=tmp_path / "sessions",
        session_id="s1",
        request_payload={"task": "audit-intent"},
    )
    context = context_allocation.context
    properties = intent_node_properties(
        kind="code",
        uid="intent-audit-1",
        intent={"source": "value = image", "spec": "inspect only"},
        inputs=[("image", "IMAGE")],
        outputs=[("image", "IMAGE")],
    )

    audit_ref = write_audit(
        tmp_path / "audit-intent",
        context=context,
        turn_state="candidate",
        metadata={
            "intent_nodes": [
                {
                    "node_id": "17",
                    "class_type": "vibecomfy.code",
                    "properties": properties,
                }
            ]
        },
    )

    audit = json.loads(Path(audit_ref.path).read_text(encoding="utf-8"))

    assert audit["metadata"]["intent_nodes"] == [
        {
            "node_id": "17",
            "class_type": "vibecomfy.code",
            "properties": properties,
        }
    ]


def test_audit_redacts_runtime_backed_intent_source_to_hash(tmp_path: Path) -> None:
    context_allocation = allocate_turn(
        session_root=tmp_path / "sessions",
        session_id="s1",
        request_payload={"task": "audit-runtime-intent"},
    )
    context = context_allocation.context
    properties = intent_node_properties(
        kind="code",
        uid="runtime-audit-1",
        intent={"source": "value + 1", "spec": "increment"},
        inputs=[("value", "INT")],
        outputs=[("result", "JSON")],
        extra_vibecomfy={
            "runtime": {
                "runtime_backed": True,
                "runtime_contract_version": "runtime_code_v1",
                "execution_mode": "expression_v1",
                "timeout_ms": 1000,
                "max_source_bytes": 128,
                "allowed_builtins": ["max"],
                "redaction_policy": ["source_hash_only", "closed_set_redaction"],
                "policy_version": "runtime_code_policy_v1",
                "passthrough_on_non_json": False,
            }
        },
    )

    audit_ref = write_audit(
        tmp_path / "audit-runtime-intent",
        context=context,
        turn_state="candidate",
        metadata={
            "intent_nodes": [
                {
                    "node_id": "17",
                    "class_type": "vibecomfy.code",
                    "properties": properties,
                }
            ]
        },
    )

    audit = json.loads(Path(audit_ref.path).read_text(encoding="utf-8"))
    source = audit["metadata"]["intent_nodes"][0]["properties"]["vibecomfy"]["intent"]["source"]

    assert source["redacted"] is True
    assert source["byte_count"] == len("value + 1")
    assert len(source["sha256"]) == 64
    assert "value + 1" not in json.dumps(audit)


def test_success_audit_is_deterministic_and_sorted_with_failure_payload(tmp_path: Path) -> None:
    context_allocation = allocate_turn(
        session_root=tmp_path / "sessions",
        session_id="s1",
        request_payload={"task": "audit"},
    )
    context = context_allocation.context
    context.record_stage(StageResult(stage="validate", ok=True, blocking=False))
    failure = failure_envelope(
        FailureKind.VALIDATION_ERROR,
        "validate",
        context,
        agent_failure_context={"explanation": "broken", "provider_secret": "hide-me"},
    )

    first_dir = tmp_path / "audit-a"
    second_dir = tmp_path / "audit-b"
    first_ref = write_audit(
        first_dir,
        context=context,
        stage_results=context.stage_results,
        failure=failure,
        response={"Authorization": "Bearer secret", "ok": False},
        metadata={"provider_secret": "secret", "api_key": "sk-secret"},
    )
    second_ref = write_audit(
        second_dir,
        context=context,
        stage_results=context.stage_results,
        failure=failure,
        response={"ok": False, "Authorization": "Bearer secret"},
        metadata={"api_key": "sk-secret", "provider_secret": "secret"},
    )

    first_text = Path(first_ref.path).read_text(encoding="utf-8")
    second_text = Path(second_ref.path).read_text(encoding="utf-8")
    first = json.loads(first_text)
    second = json.loads(second_text)

    assert first["failure"]["kind"] == FailureKind.VALIDATION_ERROR.value
    assert first["failure"]["agent_failure_context"]["provider_secret"] == REDACTED
    assert first["redactions"] == ["api_key", "auth_header", "provider_secret"]
    assert first["response_ref"]["sha256"] == second["response_ref"]["sha256"]
    assert first["response_ref"]["byte_count"] == second["response_ref"]["byte_count"]
    assert first_text.index('"artifacts"') < first_text.index('"created_at"') < first_text.index('"failure"')


def test_allocation_failure_audit_uses_fallback_directory_and_redacts(
    tmp_path: Path,
) -> None:
    failure = failure_envelope(
        FailureKind.MISSING_REQUIRED_FIELD,
        "ingest",
        {"session_id": "s1", "turn_id": None, "baseline_turn_id": None},
        agent_failure_context={"api_key": "secret"},
    )
    audit_ref = write_allocation_failure_audit(
        tmp_path / "s1",
        session_id="s1",
        failure=failure,
        request={"auth_header": "Bearer secret"},
    )

    assert "_allocation_failures" in audit_ref.path
    audit = json.loads(Path(audit_ref.path).read_text(encoding="utf-8"))
    assert audit["turn_state"] is None
    assert audit["failure"]["agent_failure_context"]["api_key"] == REDACTED
    assert audit["artifacts"]["request"]["auth_header"] == REDACTED


def test_allocation_failure_audit_uses_failure_digest_when_request_is_absent(tmp_path: Path) -> None:
    failure = failure_envelope(
        FailureKind.MISSING_REQUIRED_FIELD,
        "ingest",
        {"session_id": "s1", "turn_id": None, "baseline_turn_id": None},
        agent_failure_context={"provider_secret": "secret"},
    )

    audit_ref = write_allocation_failure_audit(tmp_path / "s1", session_id="s1", failure=failure)
    audit = json.loads(Path(audit_ref.path).read_text(encoding="utf-8"))

    assert audit["turn_state"] is None
    assert audit["artifacts"] == {}
    assert audit["failure"]["agent_failure_context"]["provider_secret"] == REDACTED


def test_audit_failure_envelope_carries_warning_or_failure_without_audit_ref() -> None:
    warning = failure_envelope(
        FailureKind.AUDIT_WRITE_WARNING,
        "audit",
        {"session_id": "s1", "turn_id": "0001", "baseline_turn_id": "0000"},
        audit_error="warning: response artifact write degraded",
    )
    failure = failure_envelope(
        FailureKind.AUDIT_WRITE_FAILURE,
        "audit",
        {"session_id": "s1", "turn_id": "0001", "baseline_turn_id": "0000"},
        audit_error="disk full",
    )

    warning_payload = warning.to_dict()
    failure_payload = failure.to_dict()

    assert warning_payload["kind"] == FailureKind.AUDIT_WRITE_WARNING.value
    assert warning_payload["audit_ref"] is None
    assert warning_payload["audit_error"] == "warning: response artifact write degraded"
    assert failure_payload["kind"] == FailureKind.AUDIT_WRITE_FAILURE.value
    assert failure_payload["audit_ref"] is None
    assert failure_payload["audit_error"] == "disk full"


def test_normalize_agent_edit_v2_metadata_fills_delta_defaults_without_v1_artifacts() -> None:
    payload = normalize_agent_edit_v2_metadata(
        {
            "enabled": True,
            "delta_ops": {
                "ops": [{"op": "set_mode", "target": ["", "u1"], "mode": 2}],
                "diagnostics": [{"code": "automatic_link_removal", "severity": "info"}],
                "automatic_link_removals": [{"scope_path": "", "uid": "u1", "link_id": 7}],
                "re_stitches": [{"scope_path": "", "uid": "u2", "class_type": "Reroute"}],
                "guard_result": {"ok": True, "diagnostics": []},
                "normalize": {"fallback_used": True},
            },
        }
    )

    assert payload == {
        "enabled": True,
        "op_count": 1,
        "delta_ops": {
            "ops": [{"op": "set_mode", "target": ["", "u1"], "mode": 2}],
            "diagnostics": [{"code": "automatic_link_removal", "severity": "info"}],
            "automatic_link_removals": [{"scope_path": "", "uid": "u1", "link_id": 7}],
            "re_stitches": [{"scope_path": "", "uid": "u2", "class_type": "Reroute"}],
            "guard_result": {"ok": True, "diagnostics": []},
            "normalize": {"fallback_used": True, "allow_list_used": False},
        },
    }


def test_redaction_closed_set_values_are_exact() -> None:
    redacted = redact_closed_set(
        {
            "api_key": "a",
            "authorization": "Bearer abc",
            "credential_payload": {"password": "x"},
            "env_variable": "DEEPSEEK_API_KEY",
            "provider_secret": "secret",
            "ordinary": "Bearer not-key-but-token",
        }
    )

    assert set(redacted.categories) == {
        "api_key",
        "auth_header",
        "credential_payload",
        "env_variable",
        "provider_secret",
        "bearer_token",
    }
    assert redacted.value["api_key"] == REDACTED
    assert redacted.value["ordinary"] == REDACTED


def test_validate_stage_diagnostics_reuses_existing_validation_sources() -> None:
    workflow = VibeWorkflow("validate", WorkflowSource("validate"))
    workflow.nodes["1"] = VibeNode("1", "SaveImage", inputs={})
    provider = _Provider({"SaveImage": _schema("SaveImage", required_inputs=("images",))})

    diagnostics = validate_stage_diagnostics(workflow, schema_provider=provider)
    result = validate_stage_result(workflow, schema_provider=provider)

    assert diagnostics.failure_kind is FailureKind.UNSATISFIED_INPUT_ERROR
    assert result.ok is False
    assert result.blocking is True
    assert result.gate_updates["ir_validate_ok"] is False
    assert {issue["source"] for issue in diagnostics.issues} == {"validate_against_schema"}
    assert any(issue["code"] == "missing_required_input" for issue in diagnostics.issues)


def test_lower_stage_result_sets_lower_gate_and_keeps_validation_evidence() -> None:
    workflow = VibeWorkflow("lowered", WorkflowSource("lowered"))
    lowering = LoweringResult(
        ok=True,
        workflow=workflow,
        evidence=(
            LoweringEvidence(
                loop_uid="loop-1",
                loop_node_id="1",
                original_intent_hash="abc123",
                variable="prompt",
                iterations=2,
                iteration_values=("a", "b"),
                lowered_node_count=4,
                validation_result={"ok": True, "issue_count": 0, "error_count": 0, "warning_count": 0, "issues": []},
            ),
        ),
        diagnostics=(),
        lowered_count=1,
    )

    result = lower_stage_result(lowering)

    assert result.stage == "lower"
    assert result.ok is True
    assert result.blocking is False
    assert result.gate_updates["lower_ok"] is True
    assert result.value["failure_kind"] is None
    assert result.value["lowered_count"] == 1
    assert result.value["evidence"][0]["validation_result"]["ok"] is True


def test_lower_stage_result_passes_noop_lowering_with_zero_count() -> None:
    workflow = VibeWorkflow("unchanged", WorkflowSource("unchanged"))
    lowering = LoweringResult(
        ok=True,
        workflow=workflow,
        evidence=(),
        diagnostics=(),
        lowered_count=0,
    )

    result = lower_stage_result(lowering)

    assert result.stage == "lower"
    assert result.ok is True
    assert result.blocking is False
    assert result.gate_updates["lower_ok"] is True
    assert result.value == {
        "failure_kind": None,
        "lowered_count": 0,
        "evidence": [],
    }


def test_lower_stage_result_maps_failed_lowered_copy_validation_to_lowering_failure() -> None:
    lowering = LoweringResult(
        ok=False,
        workflow=None,
        evidence=(),
        diagnostics=(
            LoweringDiagnostic(
                code="lowered_copy_validation_failed",
                message="Node 3 (SaveImage) input images is incompatible.",
                loop_node_id="10",
                loop_uid="loop-10",
                detail={"validation_issue": {"code": "invalid_link_shape"}},
            ),
        ),
        lowered_count=0,
    )

    result = lower_stage_result(lowering)

    assert result.stage == "lower"
    assert result.ok is False
    assert result.blocking is True
    assert result.gate_updates["lower_ok"] is False
    assert result.value["failure_kind"] == FailureKind.LOWERING_FAILURE.value
    assert result.issues == (
        {
            "source": "lower_workflow",
            "code": "lowered_copy_validation_failed",
            "message": "Node 3 (SaveImage) input images is incompatible.",
            "severity": "error",
            "detail": {
                "validation_issue": {"code": "invalid_link_shape"},
                "loop_uid": "loop-10",
                "loop_node_id": "10",
            },
        },
    )


def test_validate_stage_classifies_compile_failures_as_validation_error() -> None:
    workflow = VibeWorkflow("validate", WorkflowSource("validate"))
    workflow.nodes["1"] = VibeNode("1", "SaveImage", inputs={})
    workflow.edges.append(VibeEdge("missing", 0, "1", "images"))

    diagnostics = validate_stage_diagnostics(workflow)

    assert diagnostics.failure_kind is FailureKind.VALIDATION_ERROR
    assert any(issue["code"] == "api_compile_failed" for issue in diagnostics.issues)


def test_validate_stage_reports_invalid_link_shapes_as_validation_errors() -> None:
    workflow = VibeWorkflow("validate", WorkflowSource("validate"))
    workflow.nodes["1"] = VibeNode("1", "SaveImage", inputs={"images": {"node_id": "2", "output": 0}})
    provider = _Provider(
        {
            "SaveImage": _schema_with_inputs(
                "SaveImage",
                images=InputSpec(type="IMAGE", required=True, default=None),
            )
        }
    )

    diagnostics = validate_stage_diagnostics(workflow, schema_provider=provider)

    assert diagnostics.failure_kind is FailureKind.VALIDATION_ERROR
    assert any(issue["code"] == "invalid_link_shape" for issue in diagnostics.issues)


def test_validate_stage_blocks_unresolved_execution_affecting_helper_broadcasts() -> None:
    workflow = VibeWorkflow("helper", WorkflowSource("helper"))
    workflow.nodes["1"] = VibeNode("1", "GetNode", inputs={"widget_0": "missing_image"})
    workflow.nodes["2"] = VibeNode("2", "SaveImage", inputs={})
    workflow.connect("1.0", "2.images")

    diagnostics = validate_stage_diagnostics(workflow)

    assert diagnostics.failure_kind is FailureKind.VALIDATION_ERROR
    assert any(issue["source"] == "workflow.helper_diagnostics" for issue in diagnostics.issues)
    assert any(issue["code"] == "helper_broadcast_unresolved" for issue in diagnostics.issues)
    assert any(issue["code"] == "api_compile_failed" for issue in diagnostics.issues)


def test_validate_stage_classifies_unsupported_subgraph_shapes_as_non_dag() -> None:
    workflow = VibeWorkflow("subgraph", WorkflowSource("subgraph"))

    def _validate(*, schema_provider=None):
        return type(
            "Report",
            (),
            {
                "issues": [
                    ValidationIssue(
                        "subgraph_freshness_error",
                        "Subgraph content hash changed.",
                        severity="error",
                        detail={"subgraph_id": "sg-1"},
                    )
                ]
            },
        )()

    workflow.validate = _validate  # type: ignore[method-assign]

    diagnostics = validate_stage_diagnostics(workflow)

    assert diagnostics.failure_kind is FailureKind.UNSUPPORTED_NON_DAG
    assert diagnostics.blocking is True
    assert any(issue["code"] == "subgraph_freshness_error" for issue in diagnostics.issues)


def test_validate_stage_flags_invalid_model_picker_values_when_schema_choices_exist() -> None:
    workflow = VibeWorkflow("models", WorkflowSource("models"))
    workflow.nodes["1"] = VibeNode("1", "CheckpointLoaderSimple", inputs={"ckpt_name": "missing.safetensors"})
    provider = _Provider(
        {
            "CheckpointLoaderSimple": _schema_with_inputs(
                "CheckpointLoaderSimple",
                ckpt_name=InputSpec(
                    type="STRING",
                    required=True,
                    default=None,
                    choices=["model-a.safetensors", "model-b.safetensors"],
                )
            )
        }
    )

    diagnostics = validate_stage_diagnostics(workflow, schema_provider=provider)

    assert diagnostics.failure_kind is FailureKind.VALIDATION_ERROR
    assert any(issue["code"] == "value_not_in_enum" for issue in diagnostics.issues)


def test_validate_stage_leaves_helper_info_non_blocking() -> None:
    workflow = VibeWorkflow("helper", WorkflowSource("helper"))
    workflow.nodes["1"] = VibeNode("1", "MarkdownNote", inputs={"widget_0": "note"})
    workflow.nodes["2"] = VibeNode("2", "LoadImage", inputs={"image": "a.png"})
    workflow.nodes["3"] = VibeNode("3", "SetNode", inputs={"widget_0": "img", "IMAGE": ["2", 0]})
    workflow.nodes["4"] = VibeNode("4", "GetNode", inputs={"widget_0": "img"})
    workflow.nodes["5"] = VibeNode("5", "SaveImage", inputs={"images": ["4", 0]})

    diagnostics = validate_stage_diagnostics(workflow)

    assert diagnostics.ok is True
    assert diagnostics.failure_kind is None
    assert any(issue["source"] == "workflow.helper_diagnostics" for issue in diagnostics.issues)


def test_gate_derivation_requires_canvas_gates_state_match_and_queue_without_blockers() -> None:
    context = TurnContext(session_id="s1")
    initialize_gates(context)
    for name in (
        "python_load_ok",
        "ir_validate_ok",
        "ui_emit_ok",
        "ui_fidelity_ok",
        "ui_load_safe_ok",
    ):
        context.set_gate(name, True, evidence={"test": name})

    update_state_match_gate(
        context,
        baseline_graph_hash="baseline",
        client_graph_hash="different",
    )
    assert context.canvas_apply_allowed is False
    assert context.queue_allowed is False

    update_state_match_gate(
        context,
        baseline_graph_hash="baseline",
        client_graph_hash="baseline",
    )
    assert context.canvas_apply_allowed is True
    assert context.queue_allowed is False

    blockers = update_queue_gate(
        context,
        queue_blockers=({"code": "schema_less_queue_blocker", "severity": "error"},),
    )
    assert blockers
    assert context.queue_allowed is False

    derived = derive_gates(context, queue_blockers=())
    assert derived.canvas_apply_allowed is True
    assert derived.queue_allowed is True
    assert context.gate_results["state_match_ok"].evidence["reason"] == "no_baseline_hash_required"


def test_state_match_gate_records_hash_diagnostics_for_backend_submit_hashes() -> None:
    context = TurnContext(session_id="s1")
    initialize_gates(context)

    update_state_match_gate(
        context,
        baseline_graph_hash="baseline-hash",
        client_graph_hash="submit-hash",
        client_graph_hash_label="submit_graph_hash",
    )

    evidence = context.gate_results["state_match_ok"].evidence
    assert context.gate_results["state_match_ok"].ok is False
    assert evidence["reason"] == "hash_mismatch"
    assert evidence["baseline_graph_hash"] == "baseline-hash"
    assert evidence["client_graph_hash"] == "submit-hash"
    assert evidence["client_graph_hash_label"] == "submit_graph_hash"


def test_stale_ingest_recovery_issue_promotes_to_failure_response(tmp_path: Path) -> None:
    graph = _request_graph("stale-recovery")["graph"]
    state = AgentEditState(
        task="edit stale",
        graph=graph,
        request_payload={"graph": graph},
        schema_provider=None,
        baseline_graph_hash="baseline-structural",
        submit_graph_hash=payload_hash(graph),
        submit_structural_graph_hash="submitted-structural",
        submitted_client_graph_hash="client-raw",
        submitted_client_structural_graph_hash="client-structural",
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
    context = TurnContext(session_id="s1", turn_id="0001")
    initialize_gates(context)
    issue = _stale_rebaseline_recovery_issue(
        state,
        {
            "reason": "hash_mismatch",
            "baseline_graph_hash": "baseline-structural",
            "client_graph_hash": "submitted-structural",
        },
    )
    context.record_stage(
        StageResult(stage="ingest", ok=False, blocking=True, issues=(issue,))
    )
    failure = failure_envelope(
        FailureKind.STALE_STATE_MISMATCH,
        "ingest",
        context,
        agent_failure_context={
            "explanation": "Stage ingest blocked the agent edit.",
            "issues": [issue],
        },
    )

    response = _failure_response(state, context, failure)

    assert response["apply_allowed"] is False
    assert response["queue_allowed"] is False
    assert response["apply_eligibility"]["reason"] == "stale_canvas"
    assert response["rebaseline_recovery"]["endpoint"] == "/vibecomfy/agent-edit/rebaseline"
    assert response["rebaseline_recovery"]["reason"] == "stale_state_recovery"
    assert (
        response["agent_failure_context"]["issues"][0]["rebaseline_recovery"]
        == response["rebaseline_recovery"]
    )


def test_generic_submit_failure_response_reports_no_candidate_apply_eligibility(tmp_path: Path) -> None:
    graph = _request_graph("no-candidate-failure")["graph"]
    state = AgentEditState(
        task="edit blocked",
        graph=graph,
        request_payload={"graph": graph},
        schema_provider=None,
        baseline_graph_hash="baseline-structural",
        submit_graph_hash=payload_hash(graph),
        submit_structural_graph_hash="submitted-structural",
        submitted_client_graph_hash="client-raw",
        submitted_client_structural_graph_hash="client-structural",
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
    context = TurnContext(session_id="s1", turn_id="0001")
    initialize_gates(context)
    context.record_stage(
        StageResult(
            stage="validate",
            ok=False,
            blocking=True,
            issues=(
                {
                    "code": "validation_blocked",
                    "severity": "error",
                    "message": "Validation blocked the candidate.",
                },
            ),
        )
    )
    failure = failure_envelope(
        FailureKind.VALIDATION_ERROR,
        "validate",
        context,
        agent_failure_context={
            "explanation": "Stage validate blocked the agent edit.",
            "issues": [
                {
                    "code": "validation_blocked",
                    "severity": "error",
                    "message": "Validation blocked the candidate.",
                }
            ],
        },
    )

    response = _failure_response(state, context, failure)

    assert response["apply_allowed"] is False
    assert response["queue_allowed"] is False
    assert response["apply_eligibility"]["reason"] == "no_candidate"


def test_gate_derivation_keeps_canvas_false_when_only_validation_gate_passes() -> None:
    context = TurnContext(session_id="s1")
    initialize_gates(context)
    context.set_gate("ir_validate_ok", True, evidence={"test": "validation_only"})

    derived = derive_gates(context, queue_blockers=())

    assert context.canvas_apply_allowed is False
    assert context.queue_allowed is False
    assert derived.canvas_apply_allowed is False
    assert derived.queue_allowed is False


def test_gate_derivation_leaves_skipped_gates_false_without_baseline_hash() -> None:
    context = TurnContext(session_id="s1")
    initialize_gates(context)

    derived = derive_gates(context, queue_blockers=())

    assert derived.gates["python_load_ok"].ok is False
    assert derived.gates["ui_emit_ok"].ok is False
    assert derived.gates["state_match_ok"].ok is True
    assert context.canvas_apply_allowed is False
    assert context.queue_allowed is False


def test_queue_stage_diagnostics_derive_queue_only_blockers_from_emit_evidence() -> None:
    recovery = [
        {
            "node_id": "10",
            "class_type": "vibecomfy.code",
            "kind": "code",
            "uid": "intent-10",
            "provider": "widget_schema",
            "confidence": 0.2,
            "schema_less": True,
            "diagnostic": "schema-less: emitting best-effort slots from link appearance order",
            "lowered": False,
            "runtime_backed": False,
        },
        {
            "node_id": "11",
            "class_type": "UnknownNode",
            "provider": None,
            "confidence": None,
            "schema_less": True,
            "diagnostic": "schema-less: emitting best-effort slots from link appearance order",
        },
        {
            "node_id": "12",
            "class_type": "FallbackNode",
            "provider": "widget_schema",
            "confidence": 0.3,
            "schema_less": False,
            "diagnostic": "low-confidence (0.3): widget_schema_fallback",
        },
        {"stripped_helpers": ["helper-1"], "count": 1},
    ]
    change = {"content_edits": {"stripped_helpers": ["helper-1"]}}

    diagnostics = queue_stage_diagnostics(recovery_report=recovery, change_report=change)
    result = queue_stage_result(recovery_report=recovery, change_report=change)

    assert diagnostics.ok is False
    assert diagnostics.blocking is False
    assert {issue["code"] for issue in diagnostics.issues} == {
        INTENT_NODE_QUEUE_BLOCKER_CODE,
        "schema_less_queue_blocker",
        "low_confidence_queue_blocker",
        "editor_only_node_queue_blocker",
    }
    intent_issue = next(
        issue for issue in diagnostics.issues if issue["code"] == INTENT_NODE_QUEUE_BLOCKER_CODE
    )
    assert intent_issue["failure_kind"] == FailureKind.EDITOR_ONLY_NODE_QUEUE_BLOCKER.value
    assert intent_issue["detail"] == {
        "node_id": "10",
        "class_type": "vibecomfy.code",
        "kind": "code",
        "uid": "intent-10",
        "lowered": False,
        "runtime_backed": False,
        "class_runtime_backed": True,
        "runtime_contract_valid": None,
        "intent_contract_valid": None,
        "contract_problem_codes": None,
        "provider": "widget_schema",
        "confidence": 0.2,
        "diagnostic": "schema-less: emitting best-effort slots from link appearance order",
    }
    assert result.stage == "queue_validate"
    assert result.ok is False
    assert result.blocking is False
    assert result.gate_updates["queue_validate_ok"] is False


def test_queue_diagnostics_detect_intent_nodes_before_generic_schema_confidence_checks() -> None:
    diagnostics = queue_stage_diagnostics(
        recovery_report=[
            {
                "node_id": "17",
                "class_type": "vibecomfy.loop",
                "kind": "loop",
                "uid": "intent-17",
                "provider": None,
                "confidence": None,
                "schema_less": True,
                "diagnostic": "schema-less: emitting best-effort slots from link appearance order",
            }
        ],
        change_report={},
    )

    assert diagnostics.ok is False
    assert diagnostics.blocking is False
    assert [issue["code"] for issue in diagnostics.issues] == [INTENT_NODE_QUEUE_BLOCKER_CODE]
    assert diagnostics.failure_kind == FailureKind.EDITOR_ONLY_NODE_QUEUE_BLOCKER
    assert diagnostics.issues[0]["detail"] == {
        "node_id": "17",
        "class_type": "vibecomfy.loop",
        "kind": "loop",
        "uid": "intent-17",
        "lowered": False,
        "runtime_backed": False,
        "class_runtime_backed": False,
        "runtime_contract_valid": None,
        "intent_contract_valid": None,
        "contract_problem_codes": None,
        "provider": None,
        "confidence": None,
        "diagnostic": "schema-less: emitting best-effort slots from link appearance order",
    }


def test_queue_diagnostics_ignore_synthetic_lowered_intent_provenance() -> None:
    diagnostics = queue_stage_diagnostics(
        recovery_report=[
            {
                "node_id": "17",
                "class_type": "vibecomfy.loop",
                "kind": "loop",
                "uid": "intent-17",
                "provider": "static_lowering",
                "confidence": 1.0,
                "schema_less": False,
                "diagnostic": "statically lowered to 4 native node(s)",
                "lowered": True,
                "runtime_backed": False,
                "lowered_native_count": 4,
            }
        ],
        change_report={},
    )

    assert diagnostics.ok is True
    assert diagnostics.failure_kind is None
    assert diagnostics.issues == ()


def test_queue_diagnostics_still_block_actual_unlowered_intent_with_lowered_provenance_present() -> None:
    diagnostics = queue_stage_diagnostics(
        recovery_report=[
            {
                "node_id": "17",
                "class_type": "vibecomfy.loop",
                "kind": "loop",
                "uid": "intent-17",
                "provider": "static_lowering",
                "confidence": 1.0,
                "schema_less": False,
                "diagnostic": "statically lowered to 4 native node(s)",
                "lowered": True,
                "runtime_backed": False,
                "lowered_native_count": 4,
            },
            {
                "node_id": "18",
                "class_type": "vibecomfy.code",
                "kind": "code",
                "uid": "intent-18",
                "provider": "widget_schema",
                "confidence": 1.0,
                "schema_less": False,
                "diagnostic": None,
                "lowered": False,
                "runtime_backed": False,
            },
        ],
        change_report={},
    )

    assert diagnostics.ok is False
    assert [issue["code"] for issue in diagnostics.issues] == [INTENT_NODE_QUEUE_BLOCKER_CODE]
    assert diagnostics.issues[0]["detail"]["node_id"] == "18"
    assert diagnostics.issues[0]["detail"]["lowered"] is False


def test_recovery_marks_valid_runtime_backed_code_as_queue_ready() -> None:
    workflow = VibeWorkflow("runtime-code", WorkflowSource("runtime-code"))
    workflow.nodes["44"] = VibeNode(
        "44",
        "vibecomfy.code",
        inputs={"value": 41},
        metadata=_runtime_code_metadata(uid="intent-44"),
    )

    recovery: list[dict[str, object]] = []
    emit_ui_json(
        workflow,
        schema_provider=_Provider({"vibecomfy.code": _schema("vibecomfy.code")}),
        recovery_report=recovery,
    )

    entry = next(item for item in recovery if item.get("node_id") == "44")
    assert entry["runtime_backed"] is True
    assert entry["runtime_contract_valid"] is True
    assert entry["intent_contract_valid"] is True
    assert entry["contract_problem_codes"] == []

    diagnostics = queue_stage_diagnostics(recovery_report=recovery, change_report={})
    assert diagnostics.ok is True
    assert diagnostics.issues == ()


def test_queue_diagnostics_block_stale_runtime_backed_flags_without_valid_contract() -> None:
    diagnostics = queue_stage_diagnostics(
        recovery_report=[
            {
                "node_id": "44",
                "class_type": "vibecomfy.code",
                "kind": "code",
                "uid": "intent-44",
                "provider": "test",
                "confidence": 1.0,
                "schema_less": False,
                "diagnostic": None,
                "lowered": False,
                "runtime_backed": True,
            }
        ],
        change_report={},
    )

    assert diagnostics.ok is False
    assert [issue["code"] for issue in diagnostics.issues] == [INTENT_NODE_QUEUE_BLOCKER_CODE]
    assert diagnostics.issues[0]["detail"]["runtime_backed"] is True
    assert diagnostics.issues[0]["detail"]["runtime_contract_valid"] is None


def test_queue_diagnostics_block_loop_even_with_stale_runtime_backed_flag() -> None:
    diagnostics = queue_stage_diagnostics(
        recovery_report=[
            {
                "node_id": "17",
                "class_type": "vibecomfy.loop",
                "kind": "loop",
                "uid": "intent-17",
                "provider": "test",
                "confidence": 1.0,
                "schema_less": False,
                "diagnostic": None,
                "lowered": False,
                "runtime_backed": True,
                "runtime_contract_valid": True,
                "intent_contract_valid": True,
            }
        ],
        change_report={},
    )

    assert diagnostics.ok is False
    assert [issue["code"] for issue in diagnostics.issues] == [INTENT_NODE_QUEUE_BLOCKER_CODE]
    assert diagnostics.issues[0]["detail"]["class_runtime_backed"] is False


def test_runtime_backed_code_fixture_is_queueable_after_compile_schema_and_recovery() -> None:
    workflow = VibeWorkflow("runtime-code-fixture", WorkflowSource("runtime-code-fixture"))
    workflow.nodes["44"] = VibeNode(
        "44",
        "vibecomfy.code",
        inputs={"value": 41},
        metadata=_runtime_code_metadata(uid="intent-44", source="value + 1"),
    )
    schema_provider = _Provider({"vibecomfy.code": _schema("vibecomfy.code")})

    compiled = workflow.compile("api")
    validate = validate_stage_diagnostics(workflow, schema_provider=schema_provider)
    recovery: list[dict[str, object]] = []
    emit_ui_json(workflow, schema_provider=schema_provider, recovery_report=recovery)
    queue = queue_stage_diagnostics(recovery_report=recovery, change_report={})

    assert validate.ok is True
    assert compiled["44"]["inputs"]["source"] == "value + 1"
    assert compiled["44"]["inputs"]["runtime_backed"] is True
    assert compiled["44"]["inputs"]["runtime_contract_version"] == RUNTIME_CODE_CONTRACT_VERSION
    assert compiled["44"]["inputs"]["execution_mode"] == RUNTIME_CODE_EXECUTION_MODE
    assert compiled["44"]["inputs"]["policy_version"] == RUNTIME_CODE_POLICY_VERSION
    assert queue.ok is True
    assert queue.issues == ()


@pytest.mark.parametrize(
    ("entry_overrides", "expected_detail"),
    (
        ({"runtime_contract_valid": False, "contract_problem_codes": ["execution_mode_invalid"]}, "runtime_contract_valid"),
        ({"intent_contract_valid": False, "contract_problem_codes": ["missing_uid"]}, "intent_contract_valid"),
        ({"schema_less": True, "provider": None, "confidence": None}, "provider"),
        ({"confidence": 0.3, "provider": "object_info"}, "confidence"),
    ),
)
def test_runtime_backed_code_fixture_blocks_pre_queue_when_contract_or_schema_is_not_proven(
    entry_overrides: dict[str, object],
    expected_detail: str,
) -> None:
    entry: dict[str, object] = {
        "node_id": "44",
        "class_type": "vibecomfy.code",
        "kind": "code",
        "uid": "intent-44",
        "provider": "object_info",
        "confidence": 1.0,
        "schema_less": False,
        "diagnostic": None,
        "lowered": False,
        "runtime_backed": True,
        "runtime_contract_valid": True,
        "intent_contract_valid": True,
        "contract_problem_codes": [],
    }
    entry.update(entry_overrides)

    diagnostics = queue_stage_diagnostics(recovery_report=[entry], change_report={})

    assert diagnostics.ok is False
    assert [issue["code"] for issue in diagnostics.issues] == [INTENT_NODE_QUEUE_BLOCKER_CODE]
    assert expected_detail in diagnostics.issues[0]["detail"]


def test_runtime_backed_code_fixture_blocks_pre_queue_when_custom_node_readiness_is_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from vibecomfy import comfy_nodes

    monkeypatch.delitem(comfy_nodes.NODE_CLASS_MAPPINGS, "vibecomfy.code")
    diagnostics = queue_stage_diagnostics(
        recovery_report=[
            {
                "node_id": "44",
                "class_type": "vibecomfy.code",
                "kind": "code",
                "uid": "intent-44",
                "provider": "object_info",
                "confidence": 1.0,
                "schema_less": False,
                "diagnostic": None,
                "lowered": False,
                "runtime_backed": True,
                "runtime_contract_valid": True,
                "intent_contract_valid": True,
                "contract_problem_codes": [],
            }
        ],
        change_report={},
    )

    assert diagnostics.ok is False
    assert [issue["code"] for issue in diagnostics.issues] == [INTENT_NODE_QUEUE_BLOCKER_CODE]
    assert diagnostics.issues[0]["detail"]["class_runtime_backed"] is None


def test_valid_intent_queue_blocker_keeps_canvas_apply_true_and_queue_false() -> None:
    context = TurnContext(session_id="s1")
    initialize_gates(context)
    for name in (
        "python_load_ok",
        "ir_validate_ok",
        "ui_emit_ok",
        "ui_fidelity_ok",
        "ui_load_safe_ok",
        "state_match_ok",
    ):
        context.set_gate(name, True, evidence={"test": name})

    diagnostics = queue_stage_diagnostics(
        recovery_report=[
            {
                "node_id": "44",
                "class_type": "vibecomfy.code",
                "kind": "code",
                "uid": "intent-44",
                "provider": "widget_schema",
                "confidence": 1.0,
                "schema_less": False,
                "diagnostic": None,
                "lowered": False,
                "runtime_backed": False,
            }
        ],
        change_report={},
    )

    assert diagnostics.failure_kind == FailureKind.EDITOR_ONLY_NODE_QUEUE_BLOCKER
    assert [issue["code"] for issue in diagnostics.issues] == [INTENT_NODE_QUEUE_BLOCKER_CODE]

    derived = derive_gates(context, queue_blockers=diagnostics.issues)
    assert derived.canvas_apply_allowed is True
    assert derived.queue_allowed is False
    assert context.canvas_apply_allowed is True
    assert context.queue_allowed is False


def test_queue_blockers_keep_canvas_apply_true_but_force_queue_false() -> None:
    context = TurnContext(session_id="s1")
    initialize_gates(context)
    for name in (
        "python_load_ok",
        "ir_validate_ok",
        "ui_emit_ok",
        "ui_fidelity_ok",
        "ui_load_safe_ok",
        "state_match_ok",
    ):
        context.set_gate(name, True, evidence={"test": name})

    blockers = queue_stage_diagnostics(
        recovery_report=[
            {
                "node_id": "12",
                "class_type": "FallbackNode",
                "provider": "widget_schema",
                "confidence": 0.3,
                "schema_less": False,
                "diagnostic": "low-confidence (0.3): widget_schema_fallback",
            }
        ],
        change_report={},
    ).issues
    derived = derive_gates(context, queue_blockers=blockers)

    assert derived.canvas_apply_allowed is True
    assert derived.queue_allowed is False
    assert context.canvas_apply_allowed is True
    assert context.queue_allowed is False
    assert derived.apply_eligibility.applyable is True
    assert derived.apply_eligibility.reason == "queue_blocked_warning"


def test_apply_eligibility_reasons_are_defined_once_and_preserve_compat_fields() -> None:
    assert set(APPLY_ELIGIBILITY_REASONS) == {
        "applyable",
        "no_candidate",
        "not_latest",
        "superseded",
        "server_blocked",
        "stale_canvas",
        "queue_blocked_warning",
    }
    context = TurnContext(session_id="s1", turn_id="0001")
    initialize_gates(context)
    for name in (
        "python_load_ok",
        "ir_validate_ok",
        "ui_emit_ok",
        "ui_fidelity_ok",
        "ui_load_safe_ok",
        "state_match_ok",
    ):
        context.set_gate(name, True, evidence={"test": name})
    context.set_gate("queue_validate_ok", False, evidence={"test": "queue_warning"})

    eligibility = derive_apply_eligibility(context)

    assert context.canvas_apply_allowed is True
    assert context.apply_allowed is True
    assert context.queue_allowed is False
    assert eligibility.applyable is True
    assert eligibility.reason == "queue_blocked_warning"
    assert eligibility.to_dict()["warnings"] == ["queue_blocked"]

    stale = derive_apply_eligibility(
        context,
        live_structural_graph_hash="live",
        submit_structural_graph_hash="submitted",
    )
    assert stale.applyable is False
    assert stale.reason == "stale_canvas"

    superseded = derive_apply_eligibility(context, candidate_state="unknown")
    assert superseded.applyable is False
    assert superseded.reason == "superseded"


def test_queue_diagnostics_schema_less_only_blocks_queue_when_canvas_passes() -> None:
    context = TurnContext(session_id="s1")
    initialize_gates(context)
    for name in (
        "python_load_ok",
        "ir_validate_ok",
        "ui_emit_ok",
        "ui_fidelity_ok",
        "ui_load_safe_ok",
        "state_match_ok",
    ):
        context.set_gate(name, True, evidence={"test": name})

    recovery = [
        {
            "node_id": "11",
            "class_type": "UnknownNode",
            "provider": None,
            "confidence": None,
            "schema_less": True,
            "diagnostic": "schema-less: emitting best-effort slots from link appearance order",
        }
    ]
    diagnostics = queue_stage_diagnostics(recovery_report=recovery, change_report={})
    assert diagnostics.ok is False
    assert {issue["code"] for issue in diagnostics.issues} == {"schema_less_queue_blocker"}

    blockers = diagnostics.issues
    derived = derive_gates(context, queue_blockers=blockers)

    assert derived.canvas_apply_allowed is True
    assert derived.queue_allowed is False
    assert context.canvas_apply_allowed is True
    assert context.queue_allowed is False


def test_queue_diagnostics_low_confidence_only_blocks_queue_when_canvas_passes() -> None:
    context = TurnContext(session_id="s1")
    initialize_gates(context)
    for name in (
        "python_load_ok",
        "ir_validate_ok",
        "ui_emit_ok",
        "ui_fidelity_ok",
        "ui_load_safe_ok",
        "state_match_ok",
    ):
        context.set_gate(name, True, evidence={"test": name})

    recovery = [
        {
            "node_id": "12",
            "class_type": "FallbackNode",
            "provider": "widget_schema",
            "confidence": 0.3,
            "schema_less": False,
            "diagnostic": "low-confidence (0.3): widget_schema_fallback",
        }
    ]
    diagnostics = queue_stage_diagnostics(recovery_report=recovery, change_report={})
    assert diagnostics.ok is False
    assert {issue["code"] for issue in diagnostics.issues} == {"low_confidence_queue_blocker"}

    blockers = diagnostics.issues
    derived = derive_gates(context, queue_blockers=blockers)

    assert derived.canvas_apply_allowed is True
    assert derived.queue_allowed is False
    assert context.canvas_apply_allowed is True
    assert context.queue_allowed is False


def test_queue_diagnostics_editor_only_only_blocks_queue_when_canvas_passes() -> None:
    context = TurnContext(session_id="s1")
    initialize_gates(context)
    for name in (
        "python_load_ok",
        "ir_validate_ok",
        "ui_emit_ok",
        "ui_fidelity_ok",
        "ui_load_safe_ok",
        "state_match_ok",
    ):
        context.set_gate(name, True, evidence={"test": name})

    change = {"content_edits": {"stripped_helpers": ["helper-1", "helper-2"]}}
    diagnostics = queue_stage_diagnostics(recovery_report=[], change_report=change)
    assert diagnostics.ok is False
    assert {issue["code"] for issue in diagnostics.issues} == {"editor_only_node_queue_blocker"}

    blockers = diagnostics.issues
    derived = derive_gates(context, queue_blockers=blockers)

    assert derived.canvas_apply_allowed is True
    assert derived.queue_allowed is False
    assert context.canvas_apply_allowed is True
    assert context.queue_allowed is False


def test_validate_stage_keeps_valid_intent_warning_canvas_allowing() -> None:
    workflow = VibeWorkflow("intent-valid", WorkflowSource("intent-valid"))
    workflow.nodes["1"] = VibeNode(
        "1",
        "vibecomfy.code",
        metadata=_intent_metadata(kind="code", uid="intent-1", intent={"source": "value = 1"}),
    )

    diagnostics = validate_stage_diagnostics(workflow)
    result = validate_stage_result(workflow)

    assert diagnostics.ok is True
    assert diagnostics.blocking is False
    assert {issue["code"] for issue in diagnostics.issues} == {INTENT_NODE_EDITOR_ONLY_CODE}
    assert result.gate_updates["ir_validate_ok"] is True


def test_validate_stage_marks_invalid_intent_contract_as_ir_validation_failure() -> None:
    workflow = VibeWorkflow("intent-invalid", WorkflowSource("intent-invalid"))
    workflow.nodes["1"] = VibeNode(
        "1",
        "vibecomfy.code",
        metadata=_intent_metadata(kind="code", uid="intent-1", intent={"source": "import os\nvalue = 1"}),
    )

    diagnostics = validate_stage_diagnostics(workflow)
    result = validate_stage_result(workflow)

    assert diagnostics.ok is False
    assert diagnostics.blocking is True
    assert diagnostics.failure_kind == FailureKind.VALIDATION_ERROR
    assert {issue["code"] for issue in diagnostics.issues} == {INTENT_NODE_CONTRACT_INVALID_CODE}
    assert result.gate_updates["ir_validate_ok"] is False


def test_intent_nodes_are_not_treated_as_ui_only_helpers_in_s4() -> None:
    assert not any(class_type.startswith("vibecomfy.") for class_type in GRAPH_UTILS_UI_ONLY_CLASS_TYPES)
    assert not any(class_type.startswith("vibecomfy.") for class_type in EMITTER_UI_ONLY_CLASS_TYPES)

    workflow = VibeWorkflow("intent-compile", WorkflowSource("intent-compile"))
    workflow.nodes["1"] = VibeNode(
        "1",
        "vibecomfy.code",
        metadata=_intent_metadata(kind="code", uid="intent-compile-1", intent={"source": "value = 1"}),
    )

    compiled = workflow.compile("api")
    assert "1" not in compiled

    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)
        emitted = emit_ui_json(workflow)

    assert any(node["type"] == "vibecomfy.code" for node in emitted["nodes"])


def test_explicit_intent_queue_blocker_code_blocks_queue_without_changing_canvas_gate_names() -> None:
    context = TurnContext(session_id="s1")
    initialize_gates(context)
    for name in (
        "python_load_ok",
        "ir_validate_ok",
        "ui_emit_ok",
        "ui_fidelity_ok",
        "ui_load_safe_ok",
        "state_match_ok",
    ):
        context.set_gate(name, True, evidence={"test": name})

    blockers = (
        {
            "code": INTENT_NODE_QUEUE_BLOCKER_CODE,
            "severity": "error",
            "detail": {"node_id": "17", "class_type": "vibecomfy.code"},
        },
    )
    derived = derive_gates(context, queue_blockers=blockers)

    assert INTENT_NODE_QUEUE_BLOCKER_CODE in EXPLICIT_QUEUE_BLOCKER_CODES
    assert derived.canvas_apply_allowed is True
    assert derived.queue_allowed is False


def test_queue_gate_preserves_substring_fallback_for_legacy_queue_blocker_codes() -> None:
    context = TurnContext(session_id="s1")
    initialize_gates(context)
    for name in (
        "python_load_ok",
        "ir_validate_ok",
        "ui_emit_ok",
        "ui_fidelity_ok",
        "ui_load_safe_ok",
        "state_match_ok",
    ):
        context.set_gate(name, True, evidence={"test": name})

    context.record_stage(
        StageResult(
            stage="queue_validate",
            ok=False,
            blocking=False,
            issues=(
                {
                    "code": "legacy_editor-only_queue_blocker",
                    "severity": "error",
                    "detail": {"node_id": "legacy-1"},
                },
            ),
        )
    )

    blockers = update_queue_gate(context)

    assert blockers[0]["code"] == "legacy_editor-only_queue_blocker"
    assert context.queue_allowed is False


def test_queue_diagnostics_unresolved_model_widget_blocks_queue_when_canvas_passes() -> None:
    context = TurnContext(session_id="s1")
    initialize_gates(context)
    for name in (
        "python_load_ok",
        "ir_validate_ok",
        "ui_emit_ok",
        "ui_fidelity_ok",
        "ui_load_safe_ok",
        "state_match_ok",
    ):
        context.set_gate(name, True, evidence={"test": name})

    recovery = [
        {
            "node_id": "13",
            "class_type": "CheckpointLoaderSimple",
            "provider": "schema_provider",
            "confidence": None,
            "schema_less": False,
            "diagnostic": "unresolved model: 'missing.safetensors' not found",
        }
    ]
    diagnostics = queue_stage_diagnostics(recovery_report=recovery, change_report={})
    assert diagnostics.ok is False
    assert {issue["code"] for issue in diagnostics.issues} == {"low_confidence_queue_blocker"}
    issue = diagnostics.issues[0]
    assert issue["detail"]["node_id"] == "13"
    assert issue["detail"]["confidence"] is None
    assert "unresolved" in issue["message"].lower()

    blockers = diagnostics.issues
    derived = derive_gates(context, queue_blockers=blockers)

    assert derived.canvas_apply_allowed is True
    assert derived.queue_allowed is False
    assert context.canvas_apply_allowed is True
    assert context.queue_allowed is False


def test_queue_diagnostics_all_blockers_combined_canvas_true_queue_false() -> None:
    context = TurnContext(session_id="s1")
    initialize_gates(context)
    for name in (
        "python_load_ok",
        "ir_validate_ok",
        "ui_emit_ok",
        "ui_fidelity_ok",
        "ui_load_safe_ok",
        "state_match_ok",
    ):
        context.set_gate(name, True, evidence={"test": name})

    recovery = [
        {
            "node_id": "11",
            "class_type": "UnknownNode",
            "provider": None,
            "confidence": None,
            "schema_less": True,
            "diagnostic": "schema-less",
        },
        {
            "node_id": "12",
            "class_type": "FallbackNode",
            "provider": "widget_schema",
            "confidence": 0.2,
            "schema_less": False,
            "diagnostic": "low-confidence",
        },
        {
            "node_id": "13",
            "class_type": "ModelLoader",
            "provider": "schema_provider",
            "confidence": None,
            "schema_less": False,
            "diagnostic": "unresolved model",
        },
    ]
    change = {"content_edits": {"stripped_helpers": ["helper-1"]}}

    diagnostics = queue_stage_diagnostics(recovery_report=recovery, change_report=change)
    assert diagnostics.ok is False
    codes = {issue["code"] for issue in diagnostics.issues}
    assert "schema_less_queue_blocker" in codes
    assert "low_confidence_queue_blocker" in codes
    assert "editor_only_node_queue_blocker" in codes

    blockers = diagnostics.issues
    derived = derive_gates(context, queue_blockers=blockers)

    assert derived.canvas_apply_allowed is True
    assert derived.queue_allowed is False
    assert context.canvas_apply_allowed is True
    assert context.queue_allowed is False


def test_queue_diagnostics_clean_recovery_allows_queue_when_canvas_passes() -> None:
    context = TurnContext(session_id="s1")
    initialize_gates(context)
    for name in (
        "python_load_ok",
        "ir_validate_ok",
        "ui_emit_ok",
        "ui_fidelity_ok",
        "ui_load_safe_ok",
        "state_match_ok",
    ):
        context.set_gate(name, True, evidence={"test": name})

    recovery = [
        {
            "node_id": "1",
            "class_type": "LoadImage",
            "provider": "object_info",
            "confidence": 1.0,
            "schema_less": False,
            "diagnostic": "resolved from object_info",
        },
        {
            "node_id": "2",
            "class_type": "SaveImage",
            "provider": "object_info",
            "confidence": 1.0,
            "schema_less": False,
            "diagnostic": "resolved from object_info",
        },
    ]
    diagnostics = queue_stage_diagnostics(recovery_report=recovery, change_report={})
    assert diagnostics.ok is True
    assert len(diagnostics.issues) == 0

    derived = derive_gates(context, queue_blockers=())

    assert derived.canvas_apply_allowed is True
    assert derived.queue_allowed is True
    assert context.canvas_apply_allowed is True
    assert context.queue_allowed is True


def test_agent_provider_lazy_loads_arnold_and_normalizes_response(monkeypatch) -> None:
    calls: list[dict] = []

    class Runtime:
        @staticmethod
        def run_agent_turn(**kwargs):
            calls.append(kwargs)
            return {"python": "print('ok')", "message": "done"}

    monkeypatch.setattr(agent_provider, "_load_arnold_runtime", lambda: Runtime)

    result = agent_provider.run_agent_turn("change it", "before", route="anthropic", model="m1")

    assert result.python == "print('ok')"
    assert result.message == "done"
    assert result.route == "arnold"
    assert calls[0]["route"] == "arnold"
    assert calls[0]["messages"][0]["role"] == "system"
    assert "Return only JSON with keys `python` and `message`." in calls[0]["messages"][0]["content"]
    assert "Prefer direct static graph edits first." in calls[0]["messages"][0]["content"]
    assert "Use `vibecomfy.loop` only for bounded, visible sweeps" in calls[0]["messages"][0]["content"]
    assert "Use `vibecomfy.code` only for inspectable typed logic" in calls[0]["messages"][0]["content"]
    assert "intent_node_properties(...)" in calls[0]["messages"][0]["content"]
    assert "User request:\nchange it" in calls[0]["messages"][1]["content"]
    assert "Current scratchpad Python" in calls[0]["messages"][1]["content"]
    assert result.audit_metadata["requested_route"] == "anthropic"
    assert result.audit_metadata["route_metadata"]["normalized_route"] == "arnold"
    assert result.audit_metadata["route_metadata"]["tos_acknowledgement_required"] is True
    assert result.audit_metadata["legacy_deepseek_fallback_enabled"] is False


def test_agent_provider_delta_path_uses_separate_v2_prompt_and_normalizer(monkeypatch) -> None:
    calls: list[dict] = []

    class Runtime:
        @staticmethod
        def run_agent_turn_delta(**kwargs):
            calls.append(kwargs)
            return {
                "delta": [
                    {
                        "op": "set_node_field",
                        "target": ["", "seed-node", "inputs.seed"],
                        "value": 123,
                    }
                ],
                "message": "Changed the seed.",
            }

    monkeypatch.setattr(agent_provider, "_load_arnold_runtime", lambda: Runtime)

    result = agent_provider.run_agent_turn_delta(
        "change the seed",
        "node [, seed-node] KSampler fields: inputs.seed=1",
        op_schema={"type": "object", "required": ["delta", "message"]},
        route="deepseek",
        model="m2",
    )

    assert result.message == "Changed the seed."
    assert result.route == "deepseek"
    assert result.model == "m2"
    assert len(result.delta) == 1
    assert calls[0]["route"] == "deepseek"
    assert calls[0]["projection"] == "node [, seed-node] KSampler fields: inputs.seed=1"
    assert calls[0]["op_schema"] == {"type": "object", "required": ["delta", "message"]}
    assert "Return only JSON with keys `delta` and `message`." in calls[0]["messages"][0]["content"]
    assert "Return only JSON with keys `python` and `message`." not in calls[0]["messages"][0]["content"]
    assert "Address-preserving UI projection" in calls[0]["messages"][1]["content"]
    assert result.audit_metadata["response_contract"] == "delta"


def test_agent_provider_v1_normalizer_still_rejects_delta_only_response() -> None:
    with pytest.raises(agent_provider.MissingRequiredField, match=r"key `python`"):
        agent_provider._normalize_agent_response(  # type: ignore[attr-defined]
            {"delta": [], "message": "Changed nothing."},
            route="arnold",
            model="agent-edit",
        )


def test_agent_provider_run_agent_turn_surfaces_unavailable_runtime_as_provider_error(monkeypatch) -> None:
    def _missing():
        raise agent_provider.ProviderError("not installed")

    monkeypatch.setattr(agent_provider, "_load_arnold_runtime", _missing)

    with pytest.raises(agent_provider.ProviderError, match="not installed"):
        agent_provider.run_agent_turn("task", "source")


def test_agent_provider_status_reports_unavailable_without_secret_values(monkeypatch) -> None:
    monkeypatch.setenv("ARNOLD_API_KEY", "secret-value")
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)

    def _missing():
        raise agent_provider.ProviderError("not installed")

    monkeypatch.setattr(agent_provider, "_load_arnold_runtime", _missing)

    status = agent_provider.get_agent_status(route="openai-codex", model="m1")

    assert status["ok"] is False
    assert status["provider_available"] is False
    assert status["route"] == "arnold"
    assert status["requested_route"] == "openai-codex"
    assert status["route_metadata"]["normalized_route"] == "arnold"
    assert status["route_metadata"]["browser_api_key_allowed"] is False
    assert "openai-codex" in status["route_options"]
    assert status["credential_presence"] == {
        "arnold_api_key": True,
        "hermes_api_key": False,
        "deepseek_api_key": False,
    }
    assert "secret-value" not in json.dumps(status)


def test_agent_provider_maps_malformed_and_missing_fields(monkeypatch) -> None:
    class RuntimeMalformed:
        @staticmethod
        def run_agent_turn(**_kwargs):
            return "not-json"

    monkeypatch.setattr(agent_provider, "_load_arnold_runtime", lambda: RuntimeMalformed)
    try:
        agent_provider.run_agent_turn("task", "source")
    except agent_provider.MalformedModelJSON:
        pass
    else:
        raise AssertionError("expected malformed model json")

    class RuntimeMissing:
        @staticmethod
        def run_agent_turn(**_kwargs):
            return {"python": "x = 1"}

    monkeypatch.setattr(agent_provider, "_load_arnold_runtime", lambda: RuntimeMissing)
    try:
        agent_provider.run_agent_turn("task", "source")
    except agent_provider.MissingRequiredField:
        pass
    else:
        raise AssertionError("expected missing required field")


def test_agent_provider_delta_maps_malformed_missing_and_bad_ops(monkeypatch) -> None:
    class RuntimeMalformed:
        @staticmethod
        def run_agent_turn_delta(**_kwargs):
            return "not-json"

    monkeypatch.setattr(agent_provider, "_load_arnold_runtime", lambda: RuntimeMalformed)
    with pytest.raises(
        agent_provider.MalformedModelJSON,
        match=r"keys `delta` and `message`|valid JSON",
    ):
        agent_provider.run_agent_turn_delta("task", "projection")

    class RuntimeMissing:
        @staticmethod
        def run_agent_turn_delta(**_kwargs):
            return {"delta": []}

    monkeypatch.setattr(agent_provider, "_load_arnold_runtime", lambda: RuntimeMissing)
    with pytest.raises(agent_provider.MissingRequiredField, match=r"key `message`"):
        agent_provider.run_agent_turn_delta("task", "projection")

    class RuntimeBadDelta:
        @staticmethod
        def run_agent_turn_delta(**_kwargs):
            return {"delta": [{"op": "bogus"}], "message": "bad delta"}

    monkeypatch.setattr(agent_provider, "_load_arnold_runtime", lambda: RuntimeBadDelta)
    with pytest.raises(agent_provider.MalformedModelJSON, match=r"Unsupported edit op 'bogus'\."):
        agent_provider.run_agent_turn_delta("task", "projection")


def test_agent_provider_status_uses_runtime_status_without_leaking_secrets(monkeypatch) -> None:
    calls: list[dict[str, object]] = []

    monkeypatch.setenv("ARNOLD_API_KEY", "secret-value")
    monkeypatch.setenv("HERMES_API_KEY", "hermes-secret")
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)

    class Runtime:
        @staticmethod
        def get_agent_status(**kwargs):
            calls.append(kwargs)
            return {"ok": True, "route": "runtime-route", "detail": "healthy"}

    monkeypatch.setattr(agent_provider, "_load_arnold_runtime", lambda: Runtime)

    status = agent_provider.get_agent_status(route="deepseek", model="m1")

    assert status["ok"] is True
    assert status["provider_available"] is True
    assert calls == [{"route": "deepseek", "model": "m1"}]
    assert status["route"] == "deepseek"
    assert status["requested_route"] == "deepseek"
    assert status["route_metadata"]["browser_api_key_allowed"] is True
    assert status["credential_presence"] == {
        "arnold_api_key": True,
        "hermes_api_key": True,
        "deepseek_api_key": False,
    }
    assert "secret-value" not in json.dumps(status)
    assert "hermes-secret" not in json.dumps(status)


def test_agent_provider_status_redacts_runtime_status_secret_fields(monkeypatch) -> None:
    class Runtime:
        @staticmethod
        def get_agent_status(**_kwargs):
            return {
                "ok": True,
                "api_key": "runtime-secret",
                "authorization": "Bearer runtime-token",
                "detail": "healthy",
            }

    monkeypatch.setattr(agent_provider, "_load_arnold_runtime", lambda: Runtime)

    status = agent_provider.get_agent_status()

    assert status["ok"] is True
    assert status["detail"] == "healthy"
    assert "runtime-secret" not in json.dumps(status)
    assert "runtime-token" not in json.dumps(status)


def test_agent_provider_saves_only_deepseek_key_atomically(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    env_path = tmp_path / ".hermes" / ".env"
    env_path.parent.mkdir(parents=True)
    env_path.write_text("EXISTING=value\nDEEPSEEK_API_KEY=old\n", encoding="utf-8")
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)

    result = agent_provider.handle_credential_submission(
        {"provider": "deepseek", "api_key": "deepseek-secret"},
        env_path=env_path,
    )

    assert result == {
        "ok": True,
        "stored": True,
        "provider": "deepseek",
        "key_name": "DEEPSEEK_API_KEY",
        "path": str(env_path),
    }
    text = env_path.read_text(encoding="utf-8")
    assert "EXISTING=value" in text
    assert "DEEPSEEK_API_KEY=deepseek-secret" in text
    assert "deepseek-secret" not in json.dumps(result)
    assert os.environ.get("DEEPSEEK_API_KEY") != "deepseek-secret"


def test_agent_provider_ignores_claude_and_codex_key_submissions(tmp_path: Path) -> None:
    env_path = tmp_path / ".hermes" / ".env"

    claude = agent_provider.handle_credential_submission(
        {"provider": "anthropic", "api_key": "claude-secret"},
        env_path=env_path,
    )
    codex = agent_provider.handle_credential_submission(
        {"provider": "openai-codex", "api_key": "codex-secret"},
        env_path=env_path,
    )

    assert claude["ok"] is True
    assert claude["stored"] is False
    assert claude["ignored"] is True
    assert claude["provider"] == "arnold"
    assert claude["requested_route"] == "anthropic"
    assert "Arnold/Hermes" in claude["reason"]
    assert codex["ok"] is True
    assert codex["stored"] is False
    assert codex["ignored"] is True
    assert codex["provider"] == "arnold"
    assert codex["requested_route"] == "openai-codex"
    assert "Arnold/Hermes" in codex["reason"]
    assert not env_path.exists()
    assert "claude-secret" not in json.dumps(claude)
    assert "codex-secret" not in json.dumps(codex)


# ── Batch-REPL provider wire contract (M2 T1) ──────────────────────────


def test_extract_batch_fence_prose_before_and_after() -> None:
    """Prose before and after a single ```batch fence is preserved as message."""
    text = "Here is my plan.\n\n```batch\nadd_node(\"Foo\")\n```\n\nLet me know if this works."
    batch_code, prose = agent_provider.extract_batch_fence(text)
    assert batch_code == 'add_node("Foo")'
    assert "Here is my plan." in prose
    assert "Let me know if this works." in prose


def test_extract_batch_fence_prose_before_only() -> None:
    """Prose before a fence with nothing after is preserved."""
    text = "I'll add a node.\n\n```batch\nadd_node(\"Bar\")\n```"
    batch_code, prose = agent_provider.extract_batch_fence(text)
    assert batch_code == 'add_node("Bar")'
    assert 'add_node("Bar")' not in prose
    assert "I'll add a node." in prose


def test_extract_batch_fence_prose_after_only() -> None:
    """Prose after a fence with nothing before is preserved."""
    text = "```batch\nremove_node(\"42\")\n```\n\nDone."
    batch_code, prose = agent_provider.extract_batch_fence(text)
    assert batch_code == 'remove_node("42")'
    assert 'remove_node("42")' not in prose
    assert "Done." in prose


def test_extract_batch_fence_ignores_non_batch_fenced_code() -> None:
    """Non-```batch fenced blocks are treated as prose, not parsed."""
    text = (
        "Here is some context.\n\n"
        "```python\nprint('hello')\n```\n\n"
        "```batch\nset_node_field('n1', 'text', 'new value')\n```\n\n"
        "Hope that helps!\n\n"
        "```json\n{\"key\": \"value\"}\n```"
    )
    batch_code, prose = agent_provider.extract_batch_fence(text)
    assert batch_code == "set_node_field('n1', 'text', 'new value')"
    assert "print('hello')" in prose
    assert '{"key": "value"}' in prose
    assert "Here is some context." in prose
    assert "Hope that helps!" in prose


def test_extract_batch_fence_missing_fence_raises_malformed() -> None:
    """A response with no ```batch fence raises MalformedModelJSON."""
    with pytest.raises(agent_provider.MalformedModelJSON, match="does not contain"):
        agent_provider.extract_batch_fence("Just some prose, no code block.")


def test_extract_batch_fence_multiple_fences_raises_malformed() -> None:
    """A response with multiple ```batch fences raises MalformedModelJSON."""
    text = "```batch\nx = 1\n```\n\n```batch\ny = 2\n```"
    with pytest.raises(agent_provider.MalformedModelJSON, match="multiple"):
        agent_provider.extract_batch_fence(text)


def test_extract_batch_fence_empty_fence_is_valid() -> None:
    """An empty ```batch fence is accepted (no statements yet)."""
    text = "Nothing to do.\n\n```batch\n```\n\nMaybe later."
    batch_code, prose = agent_provider.extract_batch_fence(text)
    assert batch_code == ""
    assert "Nothing to do." in prose
    assert "Maybe later." in prose


def test_build_batch_messages_turn_zero_includes_full_python_scoped_catalog_and_names() -> None:
    """Turn 0 messages include render, in-graph signatures, and names-only index."""
    messages = agent_provider.build_batch_messages(
        task="Add a node",
        python_source="workflow = ...",
        signature_catalog="FooNode(input: IMAGE, output: IMAGE)",
        available_node_names="BarNode, FooNode, ImageScaleBy",
        budget_remaining=12,
        max_batches=12,
    )
    system = messages[0]["content"]
    user = messages[1]["content"]

    # System prompt uses "live Python objects" framing
    assert "live Python objects" in system
    assert "Two moves" in system
    assert "Add:" in system
    assert "Change:" in system
    assert "x = NodeType(field=val, input=other.OUTPUT)" in system
    assert "obj.attr = value" in system
    assert "Privileged calls" in system
    assert "del x" in system
    assert '"bypassed" | "muted" | "enabled"' in system
    assert "bypass does NOT pass input through" in system
    assert "search(focus_types" in system
    assert "done()" in system
    assert 'clarify("' in system.lower() or "clarify(" in system
    assert "Output rule" in system
    assert "Known limits" in system
    assert "Envelope" in system
    assert "Prose + exactly one" in system
    assert "```batch" in system
    assert "ImageScaleBy(image=<decode_var>.IMAGE" in system
    assert "do NOT search for them" in system
    assert "search(" in system
    # Size ceiling: system prompt must stay under 2600 chars
    assert len(system) < 2600, f"system prompt is {len(system)} chars, expected <2600"
    # No execution-semantics phrasing
    assert "return only json" not in system.lower()
    assert "delta" not in system.lower()
    assert "execute the code" not in system.lower()
    assert "run the code" not in system.lower()

    # User message includes full Python and catalog
    assert "Add a node" in user
    assert "workflow = ..." in user
    assert "```python" in user
    assert "FooNode" in user
    assert "Signatures for nodes currently in the graph:" in user
    assert "Other available node type names" in user
    assert "BarNode, FooNode, ImageScaleBy" in user


def test_build_batch_messages_later_turn_includes_diff_and_report_only() -> None:
    """Later-turn messages include diff + report, not full Python."""
    messages = agent_provider.build_batch_messages(
        task="Fix the field",
        turn_number=3,
        diff="-old line\n+new line",
        report="✓ Statement 0: set_node_field — landed",
        budget_remaining=9,
        max_batches=12,
    )
    system = messages[0]["content"]
    user = messages[1]["content"]

    # System does NOT require JSON delta responses
    assert "return only json" not in system.lower()
    assert "delta" not in system.lower()
    assert "execute the code" not in system.lower()
    assert "run the code" not in system.lower()
    assert len(system) < 2600, f"system prompt is {len(system)} chars, expected <2600"

    # User message includes diff + report, NOT full Python
    assert "Fix the field" in user
    assert "```diff" in user
    assert "-old line" in user
    assert "+new line" in user
    assert "✓ Statement 0" in user
    # No full Python re-dump
    assert "```python" not in user
    assert "Current scratchpad Python" not in user


def test_build_batch_messages_no_json_delta_wording() -> None:
    """The batch system prompt never mentions JSON delta requirements."""
    # Test both turn 0 and later-turn variants
    for turn in (0, 1):
        messages = agent_provider.build_batch_messages(
            task="test",
            turn_number=turn,
            python_source="x=1" if turn == 0 else "",
            diff="diff" if turn > 0 else "",
            report="report" if turn > 0 else "",
        )
        system = messages[0]["content"]
        user = messages[1]["content"]
        combined = (system + user).lower()
        # No JSON-delta response requirements (may mention JSON only to forbid)
        assert "return only json" not in system.lower()
        assert "delta" not in system.lower()
        # No markdown fence hints for JSON
        assert "```json" not in system
        # No execution-semantics phrasing
        assert "execute the code" not in system.lower()
        assert "run the code" not in system.lower()
        # Size ceiling
        assert len(system) < 2600, f"system prompt is {len(system)} chars, expected <2600"


def test_build_batch_messages_system_prompt_contains_all_three_mode_strings() -> None:
    """The system prompt includes all three mode strings: bypassed, muted, enabled."""
    messages = agent_provider.build_batch_messages(
        task="test",
        python_source="x=1",
    )
    system = messages[0]["content"]
    assert '"bypassed"' in system
    assert '"muted"' in system
    assert '"enabled"' in system
    assert "bypass does NOT pass input through" in system


def test_build_batch_messages_system_prompt_contains_all_four_privileged_calls() -> None:
    """The system prompt includes all four privileged calls: del, mode, search, done."""
    messages = agent_provider.build_batch_messages(
        task="test",
        python_source="x=1",
    )
    system = messages[0]["content"]
    assert "del x" in system
    assert "node.mode" in system
    assert "search(" in system
    assert "done()" in system
    assert "clarify(" in system


def test_build_batch_messages_system_prompt_no_execution_semantics() -> None:
    """The system prompt contains no 'execute', 'run the code', or JSON-delta phrasing."""
    messages = agent_provider.build_batch_messages(
        task="test",
        python_source="x=1",
    )
    system = messages[0]["content"]
    system_lower = system.lower()
    assert "return only json" not in system_lower
    assert "delta" not in system_lower
    assert "execute the code" not in system_lower
    assert "run the code" not in system_lower
    assert "json response" not in system_lower


def test_build_batch_messages_system_prompt_size_under_ceiling() -> None:
    """System prompt stays under 2600 chars with budget line included."""
    messages = agent_provider.build_batch_messages(
        task="test",
        python_source="x=1",
        budget_remaining=3,
        max_batches=5,
    )
    system = messages[0]["content"]
    assert len(system) < 2600, f"system prompt is {len(system)} chars, expected <2600"


def test_batch_turn_result_to_dict() -> None:
    """BatchTurnResult.to_dict() includes batch, message, route, model, audit_metadata."""
    result = agent_provider.BatchTurnResult(
        batch='add_node("N")',
        message="Adding a node.",
        route="arnold",
        model="test-model",
        audit_metadata={"response_contract": "batch_repl"},
    )
    d = result.to_dict()
    assert d["batch"] == 'add_node("N")'
    assert d["message"] == "Adding a node."
    assert d["route"] == "arnold"
    assert d["model"] == "test-model"
    assert d["audit_metadata"]["response_contract"] == "batch_repl"


def test_run_agent_turn_batch_audit_metadata_marks_batch_repl(monkeypatch) -> None:
    """run_agent_turn_batch audit metadata includes response_contract='batch_repl'."""
    class BatchRuntime:
        @staticmethod
        def run_agent_turn(**_kwargs):
            return "Prose\n\n```batch\nset_node_field('n1', 'text', 'hello')\n```\n\nDone."

    monkeypatch.setattr(agent_provider, "_load_arnold_runtime", lambda: BatchRuntime)
    result = agent_provider.run_agent_turn_batch(
        task="test",
        messages=[{"role": "user", "content": "test"}],
        route="arnold",
        model="test-model",
    )
    assert result.batch == "set_node_field('n1', 'text', 'hello')"
    assert "Prose" in result.message
    assert result.route == "arnold"
    assert result.model == "test-model"
    md = dict(result.audit_metadata or {})
    assert md.get("response_contract") == "batch_repl"
    assert md.get("provider") == "arnold"


def test_run_agent_turn_batch_uses_runtime_batch_entrypoint(monkeypatch) -> None:
    """run_agent_turn_batch prefers the batch runtime contract over python fallback."""
    calls: list[dict[str, object]] = []

    class BatchRuntime:
        @staticmethod
        def run_agent_turn_batch(**kwargs):
            calls.append(kwargs)
            return {
                "content": "Updated the prompt.\n\n```batch\ntext_prompt.text = \"lake\"\ndone()\n```"
            }

        @staticmethod
        def run_agent_turn(**_kwargs):
            raise AssertionError("python replacement fallback should not be used")

    monkeypatch.setattr(agent_provider, "_load_arnold_runtime", lambda: BatchRuntime)
    result = agent_provider.run_agent_turn_batch(
        task="set prompt",
        messages=[{"role": "user", "content": "set prompt"}],
        route="deepseek",
        model="deepseek-chat",
    )

    assert result.batch == 'text_prompt.text = "lake"\ndone()'
    assert result.route == "deepseek"
    assert result.model == "deepseek-chat"
    assert calls[0]["route"] == "deepseek"
    assert calls[0]["model"] == "deepseek-chat"


def test_run_agent_turn_batch_empty_content_is_malformed(monkeypatch) -> None:
    """Two empty batch responses still fail as malformed model output."""
    calls: list[dict[str, object]] = []

    class EmptyBatchRuntime:
        @staticmethod
        def run_agent_turn_batch(**kwargs):
            calls.append(kwargs)
            return {"content": ""}

    monkeypatch.setattr(agent_provider, "_load_arnold_runtime", lambda: EmptyBatchRuntime)
    with pytest.raises(agent_provider.MalformedModelJSON, match="batch_repl response was empty"):
        agent_provider.run_agent_turn_batch(
            task="set prompt",
            messages=[{"role": "user", "content": "set prompt"}],
        )
    assert len(calls) == 2
    assert calls[1]["messages"][-1]["role"] == "system"  # type: ignore[index]
    assert "previous reply was empty or unparseable" in calls[1]["messages"][-1]["content"]  # type: ignore[index]


def test_run_agent_turn_batch_retries_empty_content_once_then_succeeds(monkeypatch) -> None:
    """The batch path retries one empty/unparseable response before surfacing failure."""
    calls: list[dict[str, object]] = []
    responses = iter(
        [
            {"content": ""},
            {"content": "Done.\n\n```batch\nsaveimage.filename_prefix = \"after\"\ndone()\n```"},
        ]
    )

    class RetryBatchRuntime:
        @staticmethod
        def run_agent_turn_batch(**kwargs):
            calls.append(kwargs)
            return next(responses)

    monkeypatch.setattr(agent_provider, "_load_arnold_runtime", lambda: RetryBatchRuntime)
    result = agent_provider.run_agent_turn_batch(
        task="set prompt",
        messages=[{"role": "user", "content": "set prompt"}],
        route="deepseek",
        model="deepseek-chat",
    )

    assert result.batch == 'saveimage.filename_prefix = "after"\ndone()'
    assert result.message == "Done."
    assert len(calls) == 2
    assert calls[1]["messages"][-1]["role"] == "system"  # type: ignore[index]
    assert "previous reply was empty or unparseable" in calls[1]["messages"][-1]["content"]  # type: ignore[index]
    metadata = dict(result.audit_metadata or {})
    assert metadata["batch_repl_retry"]["count"] == 1
    assert "batch_repl response was empty" in metadata["batch_repl_retry"]["reason"]


def test_megaplan_runtime_batch_turn_uses_batch_repl_worker_contract(monkeypatch) -> None:
    """The shipped megaplan adapter asks the worker for raw batch_repl content."""
    calls: list[dict[str, object]] = []

    monkeypatch.setattr(megaplan_runtime, "_resolve_deepseek_key", lambda: "test-key")

    def _fake_run_worker(agent_kwargs, system_msg, user_msg, *, response_contract="python"):
        calls.append(
            {
                "agent_kwargs": agent_kwargs,
                "system_msg": system_msg,
                "user_msg": user_msg,
                "response_contract": response_contract,
            }
        )
        return {"content": "Done.\n\n```batch\ndone()\n```"}

    monkeypatch.setattr(megaplan_runtime, "_run_worker", _fake_run_worker)

    response = megaplan_runtime.run_agent_turn_batch(
        task="finish",
        route="deepseek",
        model="deepseek-chat",
        messages=[
            {"role": "system", "content": "system batch prompt"},
            {"role": "user", "content": "user batch prompt"},
        ],
    )

    assert response == {"content": "Done.\n\n```batch\ndone()\n```"}
    assert calls[0]["response_contract"] == "batch_repl"
    assert calls[0]["system_msg"] == "system batch prompt"
    assert calls[0]["user_msg"] == "user batch prompt"
    assert calls[0]["agent_kwargs"]["model"] == "deepseek-v4-pro"


def test_run_agent_turn_batch_rejects_missing_fence(monkeypatch) -> None:
    """run_agent_turn_batch raises MalformedModelJSON when response has no fence."""
    class NoFenceRuntime:
        @staticmethod
        def run_agent_turn(**_kwargs):
            return "Just prose with no code block."

    monkeypatch.setattr(agent_provider, "_load_arnold_runtime", lambda: NoFenceRuntime)
    with pytest.raises(agent_provider.MalformedModelJSON, match="does not contain"):
        agent_provider.run_agent_turn_batch(
            task="test",
            messages=[{"role": "user", "content": "test"}],
        )


def test_run_agent_turn_batch_provider_error_wraps_generic(monkeypatch) -> None:
    """run_agent_turn_batch wraps unexpected exceptions as ProviderError."""
    class BrokenRuntime:
        @staticmethod
        def run_agent_turn(**_kwargs):
            raise ValueError("something broke")

    monkeypatch.setattr(agent_provider, "_load_arnold_runtime", lambda: BrokenRuntime)
    with pytest.raises(agent_provider.ProviderError, match="something broke"):
        agent_provider.run_agent_turn_batch(
            task="test",
            messages=[{"role": "user", "content": "test"}],
        )
