"""Small offline regressions for the r9 representation-fidelity contracts."""

from __future__ import annotations

from vibecomfy.porting.emit.ui import _compare_expected_ui_links, _expected_ui_links
from vibecomfy.porting.edit._gates import _GatesMixin
from vibecomfy.porting.edit._session_types import DoneResult, _diag
from vibecomfy.workflow import VibeWorkflow, WorkflowSource
from vibecomfy.workflow_bundle import (
    _ui_candidate_sidecar,
    materialize_ui_json,
    validate_sidecar,
)


def _ui_scope(*, source_id: int, target_id: int) -> dict:
    return {
        "nodes": [
            {"id": source_id, "type": "Source", "properties": {"vibecomfy_uid": "source"}},
            {"id": target_id, "type": "Target", "properties": {"vibecomfy_uid": "target"}},
        ],
        "links": [[9, source_id, 0, target_id, 0, "VALUE"]],
    }


def test_expected_link_fold_projects_native_ids_before_strict_compare() -> None:
    original = _ui_scope(source_id=1, target_id=2)
    candidate = _ui_scope(source_id=101, target_id=202)

    expected, _removed, _changed, diagnostics = _expected_ui_links(
        original, (), candidate_scope=candidate
    )

    assert not diagnostics
    assert expected[0]["parts"] == (9, 101, 0, 202, 0, "VALUE")
    assert not _compare_expected_ui_links(
        expected,
        candidate["links"],
        original,
        candidate,
        scope_path="",
        scope_ops=(),
    )


def test_ui_only_markdown_note_is_retained_as_sidecar_custody() -> None:
    workflow = VibeWorkflow("sidecar-ui-only", WorkflowSource("sidecar-ui-only"))
    workflow.add_node("Integer", uid="value", value=7)
    candidate = {
        "nodes": [
            {
                "id": 1,
                "type": "Integer",
                "properties": {"vibecomfy_uid": "value"},
                "pos": [0, 0],
            },
            {"id": 2, "type": "MarkdownNote", "pos": [20, 20], "title": "keep me"},
        ],
        "links": [],
        "groups": [],
    }

    sidecar = _ui_candidate_sidecar(workflow, candidate)
    assert sidecar["nodes"]["ui_only_2"]["class_type"] == "MarkdownNote"
    normalized = validate_sidecar(sidecar, workflow)
    assert "ui_only_2" in normalized["nodes"]
    materialized = materialize_ui_json(workflow, normalized)
    assert any(
        node.get("type") == "MarkdownNote" and node.get("title") == "keep me"
        for node in materialized["nodes"]
    )


def test_no_op_replay_is_checked_by_apply_gate() -> None:
    from tests.test_porting_edit_apply import _SchemaProvider, _fixture
    from vibecomfy.ingest.normalize import from_ui
    from vibecomfy.porting.edit import apply_gate
    from vibecomfy.porting.edit.ops import NodeFieldTarget, SetNodeFieldOp

    provider = _SchemaProvider()
    workflow = from_ui(_fixture(), schema_provider=provider, use_comfy_converter=False)
    op = SetNodeFieldOp(
        "set_node_field", NodeFieldTarget("", "2", "text"), "server-no-op"
    )
    result = apply_gate.verify_apply(
        workflow,
        workflow.copy(),
        landed_ops=(op,),
        schema_provider=provider,
    )

    assert result.ok is True
    assert result.apply_eligible is False
    assert result.reason == "empty_delta"


def test_apply_gate_rejects_unclaimed_scalar_injection() -> None:
    from tests.test_porting_edit_apply import _SchemaProvider, _fixture
    from vibecomfy.ingest.normalize import from_ui
    from vibecomfy.porting.edit import apply_gate
    from vibecomfy.porting.edit._ir_utils import apply_edits_cow
    from vibecomfy.porting.edit.ops import NodeFieldTarget, SetNodeFieldOp

    provider = _SchemaProvider()
    pre = from_ui(_fixture(), schema_provider=provider, use_comfy_converter=False)
    op = SetNodeFieldOp("set_node_field", NodeFieldTarget("", "2", "text"), "edited")
    post = apply_edits_cow(pre, (op,), schema_provider=provider)
    tampered = post.copy()
    # The accepted operation targets node 2; inject an unrelated scalar into
    # node 3 so the rejection cannot be explained by a wrong claimed value.
    tampered.nodes["3"].inputs["text"] = True

    result = apply_gate.verify_apply(
        pre, tampered, landed_ops=(op,), schema_provider=provider
    )

    assert result.ok is False
    assert result.reason == "replay_mismatch"
    assert any(d.code == "apply_gate_replay_mismatch" for d in result.diagnostics)


class _BaselineGateHarness(_GatesMixin):
    def __init__(self, *, changed_candidate: bool = False) -> None:
        self.changed_candidate = changed_candidate

    def _done_gate_b_region_hint_node_ids(self, **kwargs):
        return {"1"}

    def _done_gate_b_outside_signature(self, workflow, region_uids):
        return ("candidate-drift",) if self.changed_candidate and workflow is self.candidate else ("same",)

    @staticmethod
    def _done_gate_b_region_workflow(workflow, region_node_ids):
        return workflow

    def _done_gate_b_region_node_ids(self, **kwargs):
        return {"1"}

    def _compile_workflow_for_done_gate_b(self, workflow, *, label):
        if "affected region" in label:
            return workflow, {}
        return DoneResult(
            ok=False,
            summary=f"baseline compile failed ({label})",
            diagnostics=(
                _diag(
                    "done_gate_b_compile_failed",
                    f"Gate B could not compile {label} IR: ValueError: invalid bypass node",
                    severity="error",
                    detail={
                        "label": label,
                        "exception_type": "ValueError",
                        "exception_message": "invalid bypass node",
                    },
                ),
            ),
        )


def test_gate_b_baseline_failure_is_visible_but_affected_region_can_pass() -> None:
    harness = _BaselineGateHarness()
    original, working, candidate = object(), object(), object()
    harness.candidate = candidate

    result = harness._done_gate_b_workflows(
        original_workflow=original,
        working_workflow=working,
        candidate_workflow=candidate,
        ops=(),
    )

    assert result.ok is True
    assert "touched compile region is isomorphic" in result.summary
    assert any(d.code == "done_gate_b_baseline_compile_failed" for d in result.diagnostics)


def test_gate_b_baseline_carveout_rejects_changed_untouched_remainder() -> None:
    harness = _BaselineGateHarness(changed_candidate=True)
    original, working, candidate = object(), object(), object()
    harness.candidate = candidate

    result = harness._done_gate_b_workflows(
        original_workflow=original,
        working_workflow=working,
        candidate_workflow=candidate,
        ops=(),
    )

    assert result.ok is False
    assert result.diagnostics[0].code == "done_gate_b_unmodified_remainder_changed"


def test_edit_session_keeps_bypassed_baseline_diagnostic_but_rejects_candidate_drift() -> None:
    """The real session separates edit custody from whole-graph readiness."""
    from tests.test_porting_edit_session import _primitive_session
    from vibecomfy.porting.edit.session import EditSession
    from vibecomfy.porting.emit.ui import emit_ui_json
    from vibecomfy.workflow import VibeEdge, VibeNode, NodeMode

    seed = _primitive_session(frozen_authority=True)
    for workflow in (seed.workflow, seed._wf0):
        assert workflow is not None
        workflow.nodes["99"] = VibeNode(
            "99",
            "LoadImage",
            inputs={},
            uid="bypassed-invalid",
            mode=NodeMode.BYPASSED,
            native_output_names=["IMAGE"],
        )
        workflow.edges.append(VibeEdge("99", "IMAGE", "3", "value"))
    raw = emit_ui_json(
        seed._wf0,
        schema_provider=seed.schema_provider,
        include_virtual_wires=True,
    )
    session = EditSession(raw, schema_provider=seed.schema_provider)
    session.render()
    assert session.apply_batch("widget.seed = 42\n").ok

    done = session.done()
    assert done.ok is True
    assert any(d.code == "done_gate_b_baseline_compile_failed" for d in done.diagnostics)

    replayed, replay_diagnostics = session._replay_interpret_for_done()
    assert replayed is not None
    assert not replay_diagnostics
    tampered = replayed.copy()
    tampered.nodes["1"].inputs["in"] = True
    gate = session._done_gate_b_workflows(
        original_workflow=session._wf0,
        working_workflow=session.workflow,
        candidate_workflow=tampered,
        ops=tuple(session.landed_ops),
    )
    assert gate.ok is False
    assert gate.diagnostics[0].code == "done_gate_b_unmodified_remainder_changed"
