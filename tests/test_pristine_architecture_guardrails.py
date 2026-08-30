"""Guardrail regression tests for the pristine-agent-architecture epic.

These tests encode the new boundaries in code so future refactors cannot
accidentally re-introduce raw execution data into the normal UI, break stage
display, or drop explicit evidence paths.
"""

from __future__ import annotations

import errno
import json
import os
from pathlib import Path

import pytest

from vibecomfy.comfy_nodes.agent.audit import write_audit
from vibecomfy.comfy_nodes.agent import _session_storage
from vibecomfy.comfy_nodes.agent.contracts import (
    DEFAULT_GATE_NAMES,
    PUBLIC_OUTCOME_KINDS,
    ApplyEligibility,
    DiagnosticRecord,
    FailureEnvelope,
    FailureKind,
    GateResult,
    StageResult,
    TurnContext,
    TurnOutcome,
    classify_failure,
    failure_envelope,
    public_outcome_from_turn_outcome,
    repair_field_changes,
    success_envelope,
    turn_envelope,
)
from vibecomfy.comfy_nodes.agent.session import (
    DurableReadError,
    default_state,
    iter_turn_records,
    read_state,
)
from vibecomfy.porting.edit.types import FieldChange


def _state_for_storage_test() -> dict[str, object]:
    return {"schema_version": 1, "turns": {"t1": {"state": "submitted"}}}


def test_session_state_atomic_write_fsyncs_file_then_replace_then_directory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    events: list[str] = []
    real_fsync = _session_storage.os.fsync
    real_replace = _session_storage.os.replace

    def record_fsync(fd: int) -> None:
        events.append("fsync")
        real_fsync(fd)

    def record_replace(
        source: str | os.PathLike[str], target: str | os.PathLike[str]
    ) -> None:
        events.append("replace")
        real_replace(source, target)

    monkeypatch.setattr(_session_storage.os, "fsync", record_fsync)
    monkeypatch.setattr(_session_storage.os, "replace", record_replace)

    _session_storage.write_state_atomic_impl(
        tmp_path, _state_for_storage_test(), state_file_name="session_state.json"
    )

    assert events == ["fsync", "replace", "fsync"]
    assert not list(tmp_path.glob(".session_state.json.*.tmp"))
    assert json.loads((tmp_path / "session_state.json").read_text()) == _state_for_storage_test()


@pytest.mark.parametrize("fault", ["file_fsync", "replace", "directory_fsync"])
def test_session_state_atomic_write_cleans_temp_on_durability_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, fault: str
) -> None:
    target = tmp_path / "session_state.json"
    target.write_text('{"old": true}\n', encoding="utf-8")
    real_fsync = _session_storage.os.fsync
    calls = 0

    def fail_fsync(fd: int) -> None:
        nonlocal calls
        calls += 1
        if (fault == "file_fsync" and calls == 1) or (
            fault == "directory_fsync" and calls == 2
        ):
            raise OSError(errno.EIO, f"synthetic {fault}")
        real_fsync(fd)

    def fail_replace(
        source: str | os.PathLike[str], destination: str | os.PathLike[str]
    ) -> None:
        raise OSError(errno.EIO, "synthetic replace")

    monkeypatch.setattr(_session_storage.os, "fsync", fail_fsync)
    if fault == "replace":
        monkeypatch.setattr(_session_storage.os, "replace", fail_replace)

    with pytest.raises(OSError, match="synthetic"):
        _session_storage.write_state_atomic_impl(
            tmp_path, _state_for_storage_test(), state_file_name="session_state.json"
        )

    assert not list(tmp_path.glob(".session_state.json.*.tmp"))
    if fault != "directory_fsync":
        assert target.read_text(encoding="utf-8") == '{"old": true}\n'


@pytest.mark.parametrize(
    ("operation", "error_number", "raises"),
    [
        ("open", errno.EINVAL, False),
        ("open", errno.EIO, True),
        ("fsync", errno.EINVAL, False),
        ("fsync", errno.EIO, True),
    ],
)
def test_session_state_directory_fsync_handles_only_unsupported_errors(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    operation: str,
    error_number: int,
    raises: bool,
) -> None:
    if operation == "open":

        def fail_open(path: str | os.PathLike[str], flags: int) -> int:
            raise OSError(error_number, "synthetic directory open")

        monkeypatch.setattr(_session_storage.os, "open", fail_open)
    else:
        calls = 0

        def fail_fsync(fd: int) -> None:
            nonlocal calls
            calls += 1
            raise OSError(error_number, "synthetic directory fsync")

        monkeypatch.setattr(_session_storage.os, "fsync", fail_fsync)

    if raises:
        with pytest.raises(OSError, match="synthetic"):
            _session_storage._fsync_parent_directory(tmp_path)
    else:
        _session_storage._fsync_parent_directory(tmp_path)


# ---------------------------------------------------------------------------
# 1. Internal sentinel values never appear in normal UI / response payloads
# ---------------------------------------------------------------------------


def _walk_values(value: object):
    if isinstance(value, dict):
        for v in value.values():
            yield from _walk_values(v)
    elif isinstance(value, (list, tuple)):
        for item in value:
            yield from _walk_values(item)
    else:
        yield value


def test_response_envelope_is_json_safe_and_has_no_internal_sentinels() -> None:
    context = TurnContext(session_id="s", turn_id="t")
    eligibility = ApplyEligibility(
        applyable=True, reason="applyable", message="Ready"
    )
    response = success_envelope(
        context,
        message="Done",
        graph={"nodes": [{"id": 1}]},
        apply_eligibility=eligibility,
    )
    payload = turn_envelope(
        message="Done",
        outcome=TurnOutcome.noop(),
        candidate={"nodes": [{"id": 1}]},
        eligibility=eligibility,
    )
    for data in (response, payload):
        # Must serialize cleanly.
        json.dumps(data)
        # No internal sentinel objects leak out.
        for value in _walk_values(data):
            assert not type(value).__name__.startswith("_MISSING")
            assert not type(value).__name__.startswith("_ABSENT")


def test_public_outcome_never_leaks_internal_kind() -> None:
    for kind in ("edit", "edit+clarify", "noop"):
        internal = TurnOutcome(kind=kind)
        public = public_outcome_from_turn_outcome(internal)
        assert public["kind"] in PUBLIC_OUTCOME_KINDS
        assert public["kind"] not in {"edit", "edit+clarify", "failure"}


def test_auth_error_failure_payload_is_public_and_sentinel_free() -> None:
    assert FailureKind.AUTH_ERROR.value == "AuthError"

    envelope = failure_envelope(
        FailureKind.AUTH_ERROR,
        stage="agent_response",
        context=TurnContext(session_id="s", turn_id="t"),
        agent_failure_context={"explanation": "HTTP 401"},
    )
    data = envelope.to_dict()

    json.dumps(data)
    assert data["kind"] == "AuthError"
    assert data["outcome"]["kind"] == "error"
    assert data["outcome"]["failure_kind"] == "AuthError"
    assert data["outcome"]["stage"] == "agent_response"
    assert data["outcome"]["retryable"] is False
    assert data["outcome"]["graph_unchanged"] is True
    assert data["message"] == data["user_facing_message"]
    assert "***" not in json.dumps(data)


def test_turn_envelope_keeps_public_json_key_shape() -> None:
    eligibility = ApplyEligibility(
        applyable=False,
        reason="server_blocked",
        message="Server validation gates blocked Apply.",
    )
    payload = turn_envelope(
        message="  Candidate emitted.  ",
        outcome={"kind": "candidate", "changes": []},
        candidate={"state": "candidate", "graph_hash": "abc123"},
        eligibility=eligibility,
        debug={"stage": "ui_emit"},
    )

    json.dumps(payload)
    assert set(payload) == {
        "contract_version",
        "message",
        "outcome",
        "candidate",
        "eligibility",
        "audit_ref",
        "debug",
    }
    assert payload["message"] == "Candidate emitted."
    assert payload["outcome"]["kind"] in PUBLIC_OUTCOME_KINDS
    assert payload["eligibility"] == eligibility.to_dict()


# ---------------------------------------------------------------------------
# 2. Stage display still shows the correct user-facing stage
# ---------------------------------------------------------------------------


def test_stage_result_round_trips_user_facing_stage() -> None:
    stage = StageResult(stage="validate", ok=True, blocking=False)
    payload = stage.to_dict()
    assert payload["stage"] == "validate"
    assert payload["ok"] is True


def test_failure_envelope_keeps_stage_for_display() -> None:
    envelope = failure_envelope(
        FailureKind.VALIDATION_ERROR,
        stage="queue_validate",
        context=TurnContext(session_id="s"),
    )
    assert isinstance(envelope, FailureEnvelope)
    assert envelope.stage == "queue_validate"
    data = envelope.to_dict()
    assert data["stage"] == "queue_validate"
    assert "validation" in data["user_facing_message"].lower()


# ---------------------------------------------------------------------------
# 3. Apply candidate / eligibility consistency
# ---------------------------------------------------------------------------


def test_apply_eligibility_matches_gate_state() -> None:
    context = TurnContext(session_id="s", turn_id="t")
    # All gates false -> not applyable.
    assert context.apply_eligibility.applyable is False
    assert context.apply_allowed is False

    for name in DEFAULT_GATE_NAMES:
        context.set_gate(name, True)
    eligibility = context.apply_eligibility
    assert eligibility.applyable is True
    assert eligibility.reason == "applyable"
    assert context.apply_allowed is True


def test_apply_eligibility_payload_is_consistent() -> None:
    eligibility = ApplyEligibility(
        applyable=True, reason="applyable", message="OK"
    )
    payload = {
        **eligibility.to_dict(),
        "canvas_apply_allowed": True,
        "queue_allowed": True,
    }
    assert payload["applyable"] is True
    assert payload["canvas_apply_allowed"] is True
    assert payload["queue_allowed"] is True


def test_partial_rehydrated_gates_normalize_apply_and_queue_eligibility() -> None:
    rehydrated_context = TurnContext(
        session_id="s",
        turn_id="t",
        gate_results={
            "python_load_ok": True,
            "lower_ok": True,
            "ir_validate_ok": GateResult(name="ir_validate_ok", ok=True),
            "ui_emit_ok": True,
            "ui_fidelity_ok": True,
            "ui_load_safe_ok": True,
            "plan_validate_ok": True,
            "state_match_ok": True,
        },
    )

    assert tuple(rehydrated_context.gate_results) == DEFAULT_GATE_NAMES
    assert rehydrated_context.gate_results["queue_validate_ok"].ok is False
    assert rehydrated_context.canvas_apply_allowed is True
    assert rehydrated_context.queue_allowed is False

    eligibility = rehydrated_context.apply_eligibility
    assert eligibility.applyable is True
    assert eligibility.reason == "queue_blocked_warning"
    assert eligibility.warnings == ("queue_blocked",)

    rehydrated_context.set_gate("queue_validate_ok", True)
    assert rehydrated_context.canvas_apply_allowed is True
    assert rehydrated_context.queue_allowed is True
    assert rehydrated_context.apply_eligibility.reason == "applyable"


# ---------------------------------------------------------------------------
# 4. Session rehydrate safety
# ---------------------------------------------------------------------------


def test_read_state_normalizes_empty_baseline(tmp_path: Path) -> None:
    session_dir = tmp_path / "sess"
    session_dir.mkdir()
    state = read_state(session_dir)
    assert state["schema_version"] == 1
    assert isinstance(state["turns"], dict)
    assert isinstance(state["idempotency_records"], dict)
    assert isinstance(state["next_turn_index"], int)


def test_read_state_raises_for_corrupt_json(tmp_path: Path) -> None:
    session_dir = tmp_path / "corrupt"
    session_dir.mkdir()
    (session_dir / "session_state.json").write_text("{not json", encoding="utf-8")

    with pytest.raises(DurableReadError) as exc_info:
        read_state(session_dir)
    assert exc_info.value.status == "corrupt"


def test_read_state_raises_for_invalid_utf8(tmp_path: Path) -> None:
    session_dir = tmp_path / "invalid-utf8"
    session_dir.mkdir()
    (session_dir / "session_state.json").write_bytes(b"\xff\xfe\xfa")

    with pytest.raises(DurableReadError) as exc_info:
        read_state(session_dir)
    assert exc_info.value.status == "unreadable"


def test_read_state_raises_for_unreadable_state_path(tmp_path: Path) -> None:
    session_dir = tmp_path / "unreadable"
    (session_dir / "session_state.json").mkdir(parents=True)

    with pytest.raises(DurableReadError) as exc_info:
        read_state(session_dir)
    assert exc_info.value.status == "unreadable"


@pytest.mark.parametrize("payload", [None, [], "state", 7])
def test_read_state_raises_for_non_dict_json(
    tmp_path: Path, payload: object
) -> None:
    session_dir = tmp_path / "non-dict"
    session_dir.mkdir()
    (session_dir / "session_state.json").write_text(
        json.dumps(payload), encoding="utf-8"
    )

    with pytest.raises(DurableReadError) as exc_info:
        read_state(session_dir)
    assert exc_info.value.status == "corrupt"


def test_read_state_normalizes_schema_mismatched_containers_and_indexes(
    tmp_path: Path,
) -> None:
    session_dir = tmp_path / "schema-mismatch"
    session_dir.mkdir()
    (session_dir / "session_state.json").write_text(
        json.dumps(
            {
                "turns": ["not", "a", "dict"],
                "idempotency_records": None,
                "next_turn_index": 0,
                "next_rebaseline_index": "bad",
            }
        ),
        encoding="utf-8",
    )

    state = read_state(session_dir)

    assert state["turns"] == {}
    assert state["idempotency_records"] == {}
    assert state["next_turn_index"] == 1
    assert state["next_rebaseline_index"] == 1
    assert state["schema_version"] == 1


def test_read_state_preserves_partial_dict_and_normalizes_baseline(
    tmp_path: Path,
) -> None:
    session_dir = tmp_path / "partial-valid"
    session_dir.mkdir()
    (session_dir / "session_state.json").write_text(
        json.dumps(
            {
                "next_turn_index": 5,
                "next_rebaseline_index": 3,
                "baseline_turn_id": "0001",
                "turns": {
                    "0001": {
                        "state": "accepted",
                        "candidate_graph_hash": "legacy-candidate-hash",
                    },
                },
                "idempotency_records": {
                    "accept:key": {"turn_id": "0001", "response_hash": "abc"},
                },
            }
        ),
        encoding="utf-8",
    )

    state = read_state(session_dir)

    assert state["turns"]["0001"]["state"] == "accepted"
    assert state["idempotency_records"]["accept:key"]["turn_id"] == "0001"
    assert state["next_turn_index"] == 5
    assert state["next_rebaseline_index"] == 3
    assert state["baseline_turn_id"] is None
    assert state["baseline_graph_hash"] == "legacy-candidate-hash"
    assert state["baseline_graph_hash_kind"] == "raw"
    assert state["baseline_source"] == "legacy"
    assert state["schema_version"] == 1


def test_default_state_has_required_keys() -> None:
    state = default_state()
    assert "turns" in state
    assert "idempotency_records" in state
    assert "baseline_turn_id" in state
    assert "next_turn_index" in state


# ---------------------------------------------------------------------------
# 5. Explicit audit / debug evidence availability
# ---------------------------------------------------------------------------


def test_write_audit_produces_readable_record(tmp_path: Path) -> None:
    context = TurnContext(session_id="sess", turn_id="0001")
    ref = write_audit(
        tmp_path / "audit",
        context=context,
        turn_state="candidate",
        response={"ok": True, "task": "test"},
    )
    audit_path = Path(ref.path)
    assert audit_path.exists()
    data = json.loads(audit_path.read_text(encoding="utf-8"))
    assert data["session_id"] == "sess"
    assert data["turn_id"] == "0001"
    assert isinstance(ref.diagnostic_record, DiagnosticRecord)
    assert ref.diagnostic_record.session_id == "sess"


def test_iter_turn_records_reads_explicit_evidence(tmp_path: Path) -> None:
    session_root = tmp_path / "sessions"
    session_dir = session_root / "sess"
    turn_dir = session_dir / "turns" / "0001"
    turn_dir.mkdir(parents=True)
    (session_dir / "session_state.json").write_text(
        json.dumps(
            {
                "baseline_turn_id": "0001",
                "turns": {
                    "0001": {"state": "candidate", "agent_edit_protocol": "v2"}
                },
            }
        ),
        encoding="utf-8",
    )
    (turn_dir / "request.json").write_text(
        json.dumps({"task": "evidence test"}), encoding="utf-8"
    )
    (turn_dir / "response.json").write_text(
        json.dumps({"ok": True, "graph": {"nodes": [{"id": 1}]}}),
        encoding="utf-8",
    )

    records = list(iter_turn_records(session_root, "sess"))
    assert len(records) == 1
    record = records[0]
    assert record.session_id == "sess"
    assert record.turn_id == "0001"
    assert record.lifecycle == "candidate"
    assert record.task == "evidence test"


@pytest.mark.parametrize(
    ("artifact", "payload", "expected_path"),
    [
        (
            "response.json",
            {"ok": 1, "graph": {"nodes": []}},
            "response.json",
        ),
        (
            "response.json",
            {"gates": [], "graph": {"nodes": []}},
            "response.json",
        ),
        (
            "request.json",
            {"task": [], "route": "agent-edit"},
            "request.json",
        ),
    ],
)
def test_iter_turn_records_reports_typed_corruption_for_malformed_diagnostics(
    tmp_path: Path,
    artifact: str,
    payload: dict[str, object],
    expected_path: str,
) -> None:
    session_root = tmp_path / "sessions"
    session_dir = session_root / "sess"
    turn_dir = session_dir / "turns" / "0001"
    turn_dir.mkdir(parents=True)
    (session_dir / "session_state.json").write_text(
        json.dumps({"turns": {"0001": {"state": "candidate"}}}),
        encoding="utf-8",
    )
    (turn_dir / "request.json").write_text(
        json.dumps(
            {"task": "valid task", "route": "agent-edit"}
            if artifact == "response.json"
            else {"route": "agent-edit"}
        ),
        encoding="utf-8",
    )
    (turn_dir / "response.json").write_text(
        json.dumps({"ok": True, "graph": {"nodes": []}}), encoding="utf-8"
    )
    (turn_dir / artifact).write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(DurableReadError) as exc_info:
        list(iter_turn_records(session_root, "sess"))

    assert exc_info.value.status == "corrupt"
    assert exc_info.value.path is not None
    assert exc_info.value.path.name == expected_path


# ---------------------------------------------------------------------------
# 6. Field-change repair remains canonical
# ---------------------------------------------------------------------------


def test_repair_field_changes_keeps_none_for_genuinely_absent_fields() -> None:
    graph = {"nodes": []}
    changes = (FieldChange(uid="missing", field_path="seed", old=None, new=10),)
    repaired = repair_field_changes(graph, changes)
    assert repaired[0].old is None


def test_failure_classification_round_trips_without_internal_sentinels() -> None:
    exc = ValueError("missing required input")
    envelope = classify_failure("validate", exc, TurnContext(session_id="s"))
    data = envelope.to_dict()
    json.dumps(data)
    for value in _walk_values(data):
        assert not type(value).__name__.startswith("_MISSING")
