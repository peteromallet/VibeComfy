"""T20 response-stage retained-authority custody regressions."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from tests.test_comfy_nodes_agent_edit import (
    _layout_replayable_fixture,
    _make_state,
)
from tests.test_t20_snapshot_witness_binding import _authority
from vibecomfy.comfy_nodes.agent import edit as edit_facade
from vibecomfy.comfy_nodes.agent._frag_response_contract import (
    _build_batch_repl_response,
    _build_dev_success_response,
)
from vibecomfy.comfy_nodes.agent._frag_response_contract import (
    _validate_delta_evidence_for_apply,
    _verify_canonical_candidate_replay,
)
from vibecomfy.comfy_nodes.agent._frag_state import TurnContext
from vibecomfy.comfy_nodes.agent.edit_batch_repl import _publish_session_candidate
from vibecomfy.ingest.normalize import from_ui
from vibecomfy.porting.edit import admit as admit_module
from vibecomfy.porting.edit.admit import AdmissionAllowed, AdmissionSnapshot
from vibecomfy.porting.edit.ops import DELTA_SCHEMA_VERSION, parse_edit_op
from vibecomfy.schema import FrozenSchemaSnapshotProvider
from vibecomfy.schema.types import _digest_body, _schema_snapshot_digest


class _PoisonProvider:
    def __init__(self) -> None:
        self.calls = 0

    def get_schema(self, _class_type: str):
        self.calls += 1
        raise AssertionError("response custody must not consult the live provider")


def _empty_envelope() -> dict[str, object]:
    return {"schema_version": DELTA_SCHEMA_VERSION, "ops": []}


def _semantic_envelope() -> dict[str, object]:
    return {
        "schema_version": DELTA_SCHEMA_VERSION,
        "ops": [{"op": "set_mode", "target": ["", "1"], "mode": 2}],
    }


def _granted_context(session_id: str) -> TurnContext:
    context = TurnContext(session_id=session_id, turn_id="0001")
    for gate_name in context.gate_results:
        context.set_gate(gate_name, True)
    return context


def _published_add_link_state() -> tuple[object, dict[str, object]]:
    fixture = _layout_replayable_fixture()
    operations = tuple(
        parse_edit_op(statement["op"])
        for statement in fixture["batch_turns"][0]["statements"]
    )
    candidate_workflow = from_ui(
        deepcopy(fixture["after"]),
        schema_provider=fixture["schema_provider"],
        use_comfy_converter=False,
    )
    state = _make_state(
        graph=deepcopy(fixture["before"]),
        ui_payload=deepcopy(fixture["after"]),
        workflow=candidate_workflow,
        workflow_snapshot=fixture["workflow_snapshot"],
        schema_snapshot=fixture["schema_snapshot"],
        schema_provider=fixture["schema_provider"],
        batch_turns=fixture["batch_turns"],
        batch_exit_mode="done",
        route="dev",
        guard_original_ui=deepcopy(fixture["before"]),
    )
    session = SimpleNamespace(
        last_rendered_workflow=candidate_workflow,
        landed_ops=operations,
        resolved_ops=operations,
    )
    _publish_session_candidate(state, session)
    assert state.admission_schema_snapshot is fixture["schema_snapshot"]
    return state, fixture


def test_real_publisher_then_response_builder_uses_locked_add_link_authority() -> None:
    state, fixture = _published_add_link_state()
    retained_schema = fixture["schema_snapshot"]
    drifted = replace(
        retained_schema,
        generation=retained_schema.generation + 1,
        content_digest="",
    )
    state.schema_snapshot = replace(
        drifted,
        content_digest=_schema_snapshot_digest(_digest_body(drifted)),
    )
    poison = _PoisonProvider()
    state.schema_provider = poison

    response = _build_batch_repl_response(
        state,
        _granted_context("publisher-response-add-link"),
    )

    assert response["candidate"] is not None
    assert response["apply_allowed"] is True
    assert response["queue_allowed"] is True
    assert response["accepted_batch"]
    assert state.admission_schema_snapshot is retained_schema
    assert poison.calls == 0


def test_republication_emits_only_through_retained_frozen_schema() -> None:
    state, fixture = _published_add_link_state()
    operations = tuple(
        parse_edit_op(statement["op"])
        for statement in fixture["batch_turns"][0]["statements"]
    )
    candidate_workflow = from_ui(
        deepcopy(fixture["after"]),
        schema_provider=fixture["schema_provider"],
        use_comfy_converter=False,
    )
    session = SimpleNamespace(
        last_rendered_workflow=candidate_workflow,
        landed_ops=operations,
        resolved_ops=operations,
    )
    poison = _PoisonProvider()
    state.schema_provider = poison
    state.admission_schema_snapshot = None

    _publish_session_candidate(state, session)

    assert state.admission_schema_snapshot is fixture["schema_snapshot"]
    assert state.edited_workflow is candidate_workflow
    assert poison.calls == 0


def test_real_response_builder_rejects_stale_candidate_and_preserves_lock() -> None:
    state, fixture = _published_add_link_state()
    retained_schema = fixture["schema_snapshot"]
    state.ui_payload = deepcopy(state.ui_payload)
    preview = next(
        node
        for node in state.ui_payload["nodes"]
        if node.get("properties", {}).get("vibecomfy_uid") == "preview"
    )
    preview["type"] = "KSampler"
    preview["class_type"] = "KSampler"

    response = _build_batch_repl_response(
        state,
        _granted_context("publisher-response-stale-candidate"),
    )

    assert response["candidate"] is None
    assert response["apply_allowed"] is False
    assert response["queue_allowed"] is False
    assert state.admission_schema_snapshot is retained_schema


def test_real_response_builder_rejects_missing_lock_and_changed_evidence() -> None:
    missing_lock, _fixture = _published_add_link_state()
    missing_lock.admission_schema_snapshot = None
    response = _build_batch_repl_response(
        missing_lock,
        _granted_context("publisher-response-missing-lock"),
    )
    assert response["candidate"] is None
    assert response["apply_allowed"] is False
    assert response["queue_allowed"] is False
    assert missing_lock.admission_schema_snapshot is None

    changed_evidence, fixture = _published_add_link_state()
    retained_schema = fixture["schema_snapshot"]
    changed_evidence.batch_turns = deepcopy(changed_evidence.batch_turns)
    changed_evidence.batch_turns[0]["statements"][0]["op"]["node_id"] = "99"
    response = _build_batch_repl_response(
        changed_evidence,
        _granted_context("publisher-response-changed-evidence"),
    )
    assert response["candidate"] is None
    assert response["apply_allowed"] is False
    assert response["queue_allowed"] is False
    assert changed_evidence.admission_schema_snapshot is retained_schema


def test_delta_response_uses_cumulative_batch_evidence_when_legacy_delta_is_empty() -> None:
    """The published add/link batch is the delta contract's sole evidence."""
    state, fixture = _published_add_link_state()
    assert state.delta_ops == ()
    response = _build_dev_success_response(
        state,
        _granted_context("delta-cumulative-add-link"),
        contract="delta",
    )

    assert response["candidate"] is not None
    assert response["apply_allowed"] is True
    assert response["accepted_batch"] == [
        {"op": statement["op"]}
        for statement in fixture["batch_turns"][0]["statements"]
    ]
    assert response["agent_edit_protocol"] == "v2_delta"
    assert state.admission_schema_snapshot is fixture["schema_snapshot"]


def test_delta_response_missing_lock_fails_closed_without_provider_fallback() -> None:
    state, _fixture = _published_add_link_state()
    state.admission_schema_snapshot = None
    poison = _PoisonProvider()
    state.schema_provider = poison

    response = _build_dev_success_response(
        state,
        _granted_context("delta-missing-lock"),
        contract="delta",
    )

    assert response["candidate"] is None
    assert response["accepted_batch"] == []
    assert response["no_candidate_reason"] == "missing_schema_snapshot"
    assert state.admission_schema_snapshot is None
    assert poison.calls == 0


@pytest.mark.parametrize(
    "attribute, expected_reason",
    (
        ("workflow_snapshot", "missing_workflow_authority"),
        ("schema_snapshot", "missing_schema_snapshot"),
    ),
)
def test_delta_response_requires_retained_authority_pair(
    attribute: str,
    expected_reason: str,
) -> None:
    """Delta replay cannot substitute the mutable graph for ingress custody."""
    state, _fixture = _published_add_link_state()
    setattr(state, attribute, None)
    poison = _PoisonProvider()
    state.schema_provider = poison

    response = _build_dev_success_response(
        state,
        _granted_context(f"delta-missing-{attribute}"),
        contract="delta",
    )

    assert response["candidate"] is None
    assert response["accepted_batch"] == []
    assert response["no_candidate_reason"] == expected_reason
    assert response["apply_allowed"] is False
    assert response["queue_allowed"] is False
    assert poison.calls == 0


def _layout_response_state() -> tuple[object, dict[str, object]]:
    fixture = _layout_replayable_fixture()
    before = deepcopy(fixture["before"])
    candidate = deepcopy(before)
    candidate["nodes"][0]["pos"] = [99, 99]
    state = _make_state(
        graph=before,
        ui_payload=candidate,
        route="reorganise",
        workflow=fixture["workflow"],
        workflow_snapshot=fixture["workflow_snapshot"],
        schema_snapshot=fixture["schema_snapshot"],
        schema_provider=fixture["schema_provider"],
        batch_turns=(),
        batch_exit_mode="done",
    )
    return state, fixture


def test_real_response_builder_synthesizes_empty_reorganise_envelope() -> None:
    state, _fixture = _layout_response_state()
    response = _build_batch_repl_response(
        state,
        _granted_context("response-synthesized-empty-layout"),
    )

    assert response["candidate"] is not None
    assert response["accepted_batch"] == []
    assert response["apply_allowed"] is True
    assert response["queue_allowed"] is True


def test_real_response_builder_accepts_explicit_empty_reorganise_envelope() -> None:
    state, _fixture = _layout_response_state()
    with patch.object(
        edit_facade,
        "_build_cumulative_batch_repl_delta_envelope",
        return_value=_empty_envelope(),
    ):
        response = _build_batch_repl_response(
            state,
            _granted_context("response-explicit-empty-layout"),
        )

    assert response["candidate"] is not None
    assert response["accepted_batch"] == []
    assert response["apply_allowed"] is True
    assert response["queue_allowed"] is True


@pytest.mark.parametrize(
    "schema_snapshot, workflow_snapshot, expected_code",
    [
        (None, "valid", "missing_schema_snapshot"),
        ("valid", None, "missing_workflow_authority"),
        ({}, "valid", "malformed_schema_snapshot"),
        ("valid", {}, "malformed_workflow_snapshot"),
    ],
)
def test_real_response_builder_blocks_empty_reorganise_without_retained_pair(
    schema_snapshot,
    workflow_snapshot,
    expected_code: str,
) -> None:
    state, fixture = _layout_response_state()
    state.schema_snapshot = (
        fixture["schema_snapshot"] if schema_snapshot == "valid" else schema_snapshot
    )
    state.workflow_snapshot = (
        fixture["workflow_snapshot"]
        if workflow_snapshot == "valid"
        else workflow_snapshot
    )
    response = _build_batch_repl_response(
        state,
        _granted_context(f"response-empty-invalid-{expected_code}"),
    )

    assert response["candidate"] is None
    assert response["apply_allowed"] is False
    assert response["queue_allowed"] is False
    assert response["debug"]["delta_evidence"]["delta_evidence_code"] == expected_code


def test_response_empty_layout_requires_retained_pair_and_preserves_lock() -> None:
    _graph, _provider, workflow, retained, _index = _authority()
    poison = _PoisonProvider()
    state = _make_state(
        workflow=workflow,
        workflow_snapshot=retained.workflow,
        schema_snapshot=retained.schema,
        admission_schema_snapshot=None,
        schema_provider=poison,
    )

    with patch.object(
        edit_facade,
        "_build_cumulative_batch_repl_delta_envelope",
        return_value=None,
    ):
        valid, diagnostics, envelope = _validate_delta_evidence_for_apply(
            state, has_candidate=True, allow_empty_evidence=True
        )

    assert valid is True
    assert diagnostics["delta_evidence_synthesized_empty"] is True
    assert envelope == _empty_envelope()
    assert state.admission_schema_snapshot is None
    assert poison.calls == 0


def test_response_empty_layout_rejects_missing_or_malformed_retained_authority() -> None:
    _graph, _provider, workflow, retained, _index = _authority()
    poison = _PoisonProvider()
    cases = [
        (_make_state(workflow=workflow, schema_snapshot=None, workflow_snapshot=retained.workflow), "missing_schema_snapshot"),
        (_make_state(workflow=workflow, schema_snapshot=retained.schema, workflow_snapshot=None), "missing_workflow_authority"),
        (_make_state(workflow=workflow, schema_snapshot={}, workflow_snapshot=retained.workflow), "malformed_schema_snapshot"),
        (_make_state(workflow=workflow, schema_snapshot=retained.schema, workflow_snapshot=replace(retained.workflow, workflow={})), "malformed_workflow_snapshot"),
    ]
    for state, expected_code in cases:
        state.schema_provider = poison
        with patch.object(
            edit_facade,
            "_build_cumulative_batch_repl_delta_envelope",
            return_value=_empty_envelope(),
        ):
            valid, diagnostics, envelope = _validate_delta_evidence_for_apply(
                state, has_candidate=True, allow_empty_evidence=True
            )
        assert valid is False
        assert diagnostics["delta_evidence_code"] == expected_code
        assert envelope is None
    assert poison.calls == 0


def test_response_semantic_admission_uses_retained_ingress_and_existing_lock() -> None:
    _graph, _provider, workflow, retained, _index = _authority()
    poison = _PoisonProvider()
    state = _make_state(
        workflow=workflow.copy(),
        workflow_snapshot=retained.workflow,
        schema_snapshot=retained.schema,
        admission_schema_snapshot=retained.schema,
        schema_provider=poison,
    )
    captured: dict[str, object] = {}

    def capture_snapshot(workflow_arg, *args, **kwargs):
        captured["workflow"] = workflow_arg
        return AdmissionSnapshot(workflow=retained.workflow, schema=retained.schema)

    def capture_admit(snapshot, ops, *, working_workflow=None):
        captured["working_workflow"] = working_workflow
        captured["ops_count"] = len(ops)
        return AdmissionAllowed()

    with patch.object(
        edit_facade,
        "_build_cumulative_batch_repl_delta_envelope",
        return_value=_semantic_envelope(),
    ), patch.object(
        admit_module, "admission_snapshot_for", side_effect=capture_snapshot
    ), patch.object(admit_module, "admit_operations", side_effect=capture_admit):
        valid, _diagnostics, _envelope = _validate_delta_evidence_for_apply(
            state, has_candidate=True, allow_empty_evidence=False
        )

    assert valid is True
    assert captured["workflow"] is retained.workflow.workflow
    assert captured["working_workflow"] is retained.workflow.workflow
    assert captured["ops_count"] == 1
    assert state.admission_schema_snapshot is retained.schema
    assert poison.calls == 0


def test_response_semantic_candidate_without_publication_lock_fails_closed() -> None:
    _graph, _provider, workflow, retained, _index = _authority()
    state = _make_state(
        workflow=workflow,
        workflow_snapshot=retained.workflow,
        schema_snapshot=retained.schema,
        admission_schema_snapshot=None,
    )
    with patch.object(
        edit_facade,
        "_build_cumulative_batch_repl_delta_envelope",
        return_value=_semantic_envelope(),
    ):
        valid, diagnostics, envelope = _validate_delta_evidence_for_apply(
            state, has_candidate=True, allow_empty_evidence=False
        )
    assert valid is False
    assert diagnostics["delta_evidence_code"] == "missing_schema_snapshot"
    assert envelope is None


def test_replay_uses_frozen_lock_and_rejects_semantic_replay_without_lock(
    monkeypatch,
) -> None:
    _graph, _provider, workflow, retained, _index = _authority()
    poison = _PoisonProvider()
    state = _make_state(
        workflow=workflow,
        workflow_snapshot=retained.workflow,
        schema_snapshot=retained.schema,
        admission_schema_snapshot=retained.schema,
        schema_provider=poison,
        graph={},
        ui_payload={},
    )
    captured: dict[str, object] = {}

    class Receipt:
        replay_ok = True
        candidate_matches = True
        error = None

        @staticmethod
        def to_dict():
            return {"replay_ok": True, "candidate_matches": True}

    def verify(*args, **kwargs):
        captured["schema_provider"] = kwargs["schema_provider"]
        return Receipt()

    import vibecomfy.comfy_nodes.agent.authority_receipts as receipts

    monkeypatch.setattr(receipts, "verify_replay", verify)
    valid, reason, _diagnostics = _verify_canonical_candidate_replay(
        state, _semantic_envelope()
    )
    assert valid is True
    assert reason is None
    assert isinstance(captured["schema_provider"], FrozenSchemaSnapshotProvider)
    assert poison.calls == 0

    state.admission_schema_snapshot = None
    valid, reason, diagnostics = _verify_canonical_candidate_replay(
        state, _semantic_envelope()
    )
    assert valid is False
    assert reason == "missing_schema_snapshot"
    assert diagnostics["candidate_matches"] is False
