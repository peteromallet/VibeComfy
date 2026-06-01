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
    redact_closed_set,
    write_allocation_failure_audit,
    write_audit,
    write_text_artifact,
)
from vibecomfy.comfy_nodes import agent_provider
from vibecomfy.comfy_nodes.agent_contracts import (
    FailureKind,
    StageResult,
    TurnContext,
    failure_envelope,
)
from vibecomfy.comfy_nodes.agent_diagnostics import (
    queue_stage_diagnostics,
    queue_stage_result,
    validate_stage_diagnostics,
    validate_stage_result,
)
from vibecomfy.comfy_nodes.agent_gates import (
    EXPLICIT_QUEUE_BLOCKER_CODES,
    derive_gates,
    initialize_gates,
    update_queue_gate,
    update_state_match_gate,
)
from vibecomfy.comfy_nodes.agent_session import (
    accept_turn,
    allocate_turn,
    payload_hash,
    read_state,
    record_idempotent_response,
    reject_turn,
    write_state_atomic,
)
from vibecomfy.contracts import (
    INTENT_NODE_CONTRACT_INVALID_CODE,
    INTENT_NODE_EDITOR_ONLY_CODE,
    INTENT_NODE_QUEUE_BLOCKER_CODE,
    intent_node_properties,
)
from vibecomfy._graph_utils import UI_ONLY_CLASS_TYPES as GRAPH_UTILS_UI_ONLY_CLASS_TYPES
from vibecomfy.porting.emitter import UI_ONLY_CLASS_TYPES as EMITTER_UI_ONLY_CLASS_TYPES
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
    assert accepted["baseline_graph_hash"] == payload_hash(second_candidate_graph)
    assert accepted["unknown_transitions"] == []
    state = read_state(root / "s1")
    assert state["baseline_graph_hash"] == payload_hash(second_candidate_graph)
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
    baseline_candidate_hash = payload_hash(baseline_candidate_graph)

    accepted = accept_turn(
        session_root=root,
        session_id="s1",
        turn_id=baseline_turn_id,
        client_graph_hash=payload_hash(baseline_request["graph"]),
        request_payload={"turn_id": baseline_turn_id, "action": "accept"},
    )
    assert isinstance(accepted, dict)
    assert accepted["baseline_turn_id"] == baseline_turn_id
    assert accepted["baseline_graph_hash"] == baseline_candidate_hash

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
    assert rejected["baseline_graph_hash"] == baseline_candidate_hash
    assert rejected["candidate_graph_hash"] == payload_hash(rejected_candidate_graph)
    state = read_state(root / "s1")
    assert state["baseline_turn_id"] == baseline_turn_id
    assert state["baseline_graph_hash"] == baseline_candidate_hash
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
        "provider": None,
        "confidence": None,
        "diagnostic": "schema-less: emitting best-effort slots from link appearance order",
    }


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
    assert compiled["1"]["class_type"] == "vibecomfy.code"

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
