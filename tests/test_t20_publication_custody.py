"""T20 actual-caller custody regressions for batch candidate publication.

These tests deliberately drive the public stage delegate, rather than calling
``_publish_session_candidate`` directly.  Publication failures must happen
before candidate-artifact writes and before either durable state or admission
lock publication.
"""

from __future__ import annotations

import copy
import json
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest

from tests.test_comfy_nodes_agent_edit import (
    _batch_repl_provider,
    _frozen_fixture_schema_provider,
    _ui_graph,
)
from vibecomfy.comfy_nodes.agent._frag_state import AgentEditState, TurnContext
from vibecomfy.comfy_nodes.agent import edit as agent_edit_module
from vibecomfy.ingest.snapshot import snapshot_of
from vibecomfy.porting.edit.admit import AdmissionRejected
from vibecomfy.porting.edit.session import EditSession
from vibecomfy.schema import SchemaSnapshotError


def _state(tmp_path: Path, *, retained_schema: Any = "valid") -> AgentEditState:
    graph = _ui_graph()
    provider = _frozen_fixture_schema_provider(_batch_repl_provider(), graph)
    baseline = EditSession(copy.deepcopy(graph), schema_provider=provider)
    root = tmp_path / "session"
    turns = root / "turn_001"
    turns.mkdir(parents=True)
    state = AgentEditState(
        task="change the save prefix to after",
        graph=graph,
        request_payload={},
        schema_provider=provider,
        baseline_graph_hash=None,
        submit_graph_hash=None,
        submit_structural_graph_hash=None,
        submitted_client_graph_hash=None,
        submitted_client_structural_graph_hash=None,
        session_dir=root,
        turn_dir=turns,
        request_path=root / "request.json",
        original_ui_path=root / "original.ui.json",
        before_py_path=turns / "before.py",
        after_py_path=turns / "after.py",
        projection_path=turns / "projection.txt",
        model_request_path=turns / "model_request.json",
        model_response_path=turns / "model_response.json",
        candidate_ui_path=turns / "candidate.ui.json",
        messages_path=turns / "messages.jsonl",
        revision_evidence_path=turns / "revision_evidence.json",
        execution_plan_path=turns / "execution_plan.json",
        plan_evaluation_path=turns / "plan_evaluation.json",
        workflow=baseline.workflow,
        workflow_snapshot=snapshot_of(baseline.workflow),
        schema_snapshot=provider.snapshot if retained_schema == "valid" else retained_schema,
        guard_original_ui=copy.deepcopy(graph),
    )
    state.original_ui_path.write_text(json.dumps(graph), encoding="utf-8")
    return state


def _client(batch: str):
    def respond(_messages: list[dict[str, str]]) -> dict[str, str]:
        return {"batch": batch, "message": "test response"}

    return respond


def _assert_publication_untouched(
    state: AgentEditState,
    candidate: Path,
    old: bytes,
    *,
    expected_lock: Any = None,
) -> None:
    assert candidate.read_bytes() == old
    assert state.admission_schema_snapshot is expected_lock
    assert state.edited_workflow is None
    assert state.ui_payload is None
    assert state.python_after == ""


@pytest.mark.parametrize(
    "retained_schema, batch",
    [
        (None, 'saveimage.filename_prefix = "after"\ndone()'),
        ({}, 'saveimage.filename_prefix = "after"\ndone()'),
        (None, 'clarify("Need the target prefix")'),
    ],
    ids=["missing-schema-edit", "malformed-schema-edit", "missing-schema-empty-delta"],
)
def test_stage_actual_publication_requires_retained_authority_before_artifact_write(
    tmp_path: Path,
    retained_schema: Any,
    batch: str,
) -> None:
    state = _state(tmp_path, retained_schema=retained_schema)
    candidate = state.candidate_ui_path
    old = b"existing-candidate-artifact\n"
    candidate.write_bytes(old)
    context = TurnContext(session_id="t20-publication-authority", turn_id="0001")

    with pytest.raises(SchemaSnapshotError):
        agent_edit_module._stage_agent_batch_repl(
            state, context, deepseek_client=_client(batch)
        )

    _assert_publication_untouched(state, candidate, old)


@pytest.mark.parametrize(
    "retained_workflow, batch, code",
    [
        (None, 'saveimage.filename_prefix = "after"\ndone()', "missing_workflow_authority"),
        ({}, 'saveimage.filename_prefix = "after"\ndone()', "malformed_workflow_snapshot"),
        (None, 'clarify("Need the target prefix")', "missing_workflow_authority"),
        ({}, 'clarify("Need the target prefix")', "malformed_workflow_snapshot"),
    ],
    ids=[
        "missing-workflow-edit",
        "wrong-type-workflow-edit",
        "missing-workflow-empty-delta",
        "wrong-type-workflow-empty-delta",
    ],
)
def test_stage_actual_publication_requires_retained_workflow_before_artifact_write(
    tmp_path: Path,
    retained_workflow: Any,
    batch: str,
    code: str,
) -> None:
    state = _state(tmp_path)
    state.workflow_snapshot = retained_workflow
    retained_lock = state.schema_snapshot
    state.admission_schema_snapshot = retained_lock
    candidate = state.candidate_ui_path
    old = b"existing-candidate-artifact\n"
    candidate.write_bytes(old)
    context = TurnContext(session_id="t20-publication-workflow-authority", turn_id="0001")

    with pytest.raises(SchemaSnapshotError) as caught:
        agent_edit_module._stage_agent_batch_repl(
            state, context, deepseek_client=_client(batch)
        )

    assert caught.value.code == code
    _assert_publication_untouched(
        state,
        candidate,
        old,
        expected_lock=retained_lock,
    )


@pytest.mark.parametrize(
    "batch",
    [
        'saveimage.filename_prefix = "after"\ndone()',
        'clarify("Need the target prefix")',
    ],
    ids=["malformed-workflow-payload-edit", "malformed-workflow-payload-empty-delta"],
)
def test_stage_actual_publication_rejects_malformed_nested_workflow_before_artifact_write(
    tmp_path: Path,
    batch: str,
) -> None:
    state = _state(tmp_path)
    retained_lock = state.schema_snapshot
    state.workflow_snapshot = replace(state.workflow_snapshot, workflow={})
    state.admission_schema_snapshot = retained_lock
    candidate = state.candidate_ui_path
    old = b"existing-candidate-artifact\n"
    candidate.write_bytes(old)
    context = TurnContext(session_id="t20-publication-malformed-workflow", turn_id="0001")

    with pytest.raises(SchemaSnapshotError) as caught:
        agent_edit_module._stage_agent_batch_repl(
            state, context, deepseek_client=_client(batch)
        )

    assert caught.value.code == "malformed_workflow_snapshot"
    _assert_publication_untouched(
        state,
        candidate,
        old,
        expected_lock=retained_lock,
    )


def test_stage_actual_publication_rejection_preserves_candidate_and_lock(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    state = _state(tmp_path)
    candidate = state.candidate_ui_path
    old = b"existing-candidate-artifact\n"
    candidate.write_bytes(old)
    context = TurnContext(session_id="t20-publication-rejection", turn_id="0001")

    real_admit_operations = __import__(
        "vibecomfy.porting.edit.admit", fromlist=["admit_operations"]
    ).admit_operations
    calls = 0

    def reject_on_publication(*args: Any, **kwargs: Any) -> Any:
        nonlocal calls
        calls += 1
        # The apply gate admits the real edit first.  The second canonical
        # batch admission is the actual publication-custody check.
        if calls == 1:
            return real_admit_operations(*args, **kwargs)
        return AdmissionRejected(typed_reason="test_rejected")

    monkeypatch.setattr(
        "vibecomfy.porting.edit.admit.admit_operations", reject_on_publication
    )
    with pytest.raises(SchemaSnapshotError, match="test_rejected"):
        agent_edit_module._stage_agent_batch_repl(
            state,
            context,
            deepseek_client=_client('saveimage.filename_prefix = "after"\ndone()'),
        )

    _assert_publication_untouched(state, candidate, old)


def test_stage_actual_publication_emit_refusal_preserves_candidate_and_lock(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    state = _state(tmp_path)
    candidate = state.candidate_ui_path
    old = b"existing-candidate-artifact\n"
    candidate.write_bytes(old)
    context = TurnContext(session_id="t20-publication-emit", turn_id="0001")

    def refuse(*_args: Any, **_kwargs: Any) -> dict[str, Any]:
        raise SchemaSnapshotError("test emit refusal", code="emit_refused")

    monkeypatch.setattr(
        "vibecomfy.comfy_nodes.agent.edit_batch_repl._emit_ui_json", refuse
    )
    with pytest.raises(SchemaSnapshotError, match="test emit refusal"):
        agent_edit_module._stage_agent_batch_repl(
            state,
            context,
            deepseek_client=_client('saveimage.filename_prefix = "after"\ndone()'),
        )

    _assert_publication_untouched(state, candidate, old)


def test_stage_actual_publication_valid_batch_overwrites_candidate_after_emit(
    tmp_path: Path,
) -> None:
    state = _state(tmp_path)
    candidate = state.candidate_ui_path
    candidate.write_bytes(b"old-candidate-artifact\n")
    context = TurnContext(session_id="t20-publication-valid", turn_id="0001")

    result = agent_edit_module._stage_agent_batch_repl(
        state,
        context,
        deepseek_client=_client('saveimage.filename_prefix = "after"\ndone()'),
    )

    assert result.ok is True
    assert result.value["mode"] == "done"
    assert candidate.read_bytes() != b"old-candidate-artifact\n"
    assert json.loads(candidate.read_text(encoding="utf-8"))["nodes"]
    assert state.admission_schema_snapshot == state.schema_snapshot
    assert state.edited_workflow is not None
