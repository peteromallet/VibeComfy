"""Adversarial regressions for the T20 canonical evaluator boundary."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from tests.test_porting_edit_session_harness import _flat_schema_provider
from vibecomfy.ingest.normalize import from_ui
from vibecomfy.porting.edit._interpret import _evaluate_operation, interpret
from vibecomfy.porting.edit.ops import (
    AddNodeOp,
    LinkSourceRef,
    LinkTargetRef,
    NodeFieldTarget,
    NodeTarget,
    SetModeOp,
    SetNodeFieldOp,
    UpsertLinkOp,
)
from vibecomfy.porting.edit.session import EditSession
from vibecomfy.porting.edit.typed_tools import apply_edit_tool_call


def _workflow_and_provider() -> tuple[Any, Any]:
    graph = json.loads(
        Path("tests/fixtures/agent_edit/flat.json").read_text(encoding="utf-8")
    )
    provider = _flat_schema_provider()
    workflow = from_ui(graph, schema_provider=provider, use_comfy_converter=False)
    return workflow, provider


@pytest.mark.parametrize("value", (True, 2.9, "2"))
def test_mode_field_lowering_rejects_scalar_coercion(value: object) -> None:
    workflow, provider = _workflow_and_provider()
    operation = SetNodeFieldOp(
        op="set_node_field",
        target=NodeFieldTarget("", "5", "mode"),
        value=value,
    )

    result = _evaluate_operation(workflow, operation, schema_provider=provider)

    assert result.outcome == "rejected"
    assert result.workflow == workflow
    assert result.diagnostics[0].code == "type_mismatch"


@pytest.mark.parametrize(
    ("value", "expected_code"),
    (
        (True, "type_mismatch"),
        (2.0, "type_mismatch"),
        ("2", "type_mismatch"),
        (1, "invalid_mode_value"),
        (3, "invalid_mode_value"),
    ),
)
def test_typed_mode_operation_requires_exact_canonical_integer(
    value: object,
    expected_code: str,
) -> None:
    workflow, provider = _workflow_and_provider()
    operation = SetModeOp(  # type: ignore[arg-type]
        op="set_mode",
        target=NodeTarget("", "5"),
        mode=value,
    )

    result = _evaluate_operation(workflow, operation, schema_provider=provider)

    assert result.outcome == "rejected"
    assert result.workflow == workflow
    assert result.diagnostics[0].code == expected_code


def test_unexpected_value_error_cannot_impersonate_a_noop(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import vibecomfy.porting.edit._interpret as interpret_module

    workflow, provider = _workflow_and_provider()
    operation = SetNodeFieldOp(
        op="set_node_field",
        target=NodeFieldTarget("", "5", "steps"),
        value=42,
    )

    def corrupt_apply(*_args: Any, **_kwargs: Any) -> Any:
        raise ValueError("unexpected corruption already set to forged sentinel")

    monkeypatch.setattr(interpret_module, "apply_edit_cow", corrupt_apply)
    with pytest.raises(ValueError, match="unexpected corruption"):
        _evaluate_operation(workflow, operation, schema_provider=provider)


def test_typed_interpret_landed_add_reports_effective_minted_identity() -> None:
    workflow, provider = _workflow_and_provider()
    submitted = AddNodeOp(
        op="add_node",
        scope_path="",
        class_type="VAEDecode",
        fields={},
        inputs={
            "samples": LinkSourceRef("", "4", "LATENT"),
            "vae": LinkSourceRef("", "1", "VAE"),
        },
    )

    result = interpret(workflow, (submitted,), schema_provider=provider)

    assert result.ok, result.diagnostics
    assert submitted.uid is None and submitted.node_id is None
    landed = result.landed_ops[0]
    lowered = result.transitions[0].lowered[0]
    assert landed.uid == lowered.uid == "n1"
    assert landed.node_id == lowered.node_id == "8"
    assert result.workflow.nodes[landed.node_id].uid == landed.uid


def test_ordered_fresh_node_input_uses_only_retained_snapshot_authority() -> None:
    workflow, provider = _workflow_and_provider()

    class PoisonedLiveProvider:
        snapshot = provider.snapshot

        def get_schema(self, _class_type: str) -> Any:
            raise AssertionError("ordered fresh-node lint consulted a live provider")

    operations = (
        AddNodeOp(
            op="add_node",
            scope_path="",
            class_type="VAEDecode",
            fields={},
            inputs={},
            uid="fresh-decode",
            node_id="8",
        ),
        UpsertLinkOp(
            op="upsert_link",
            source=LinkSourceRef("", "4", "LATENT"),
            target=LinkTargetRef("", "fresh-decode", "samples"),
        ),
    )

    result = interpret(
        workflow,
        operations,
        schema_provider=PoisonedLiveProvider(),
    )

    assert result.ok, result.diagnostics
    assert tuple(item.outcome for item in result.transitions) == ("staged", "staged")


def test_ordered_fresh_node_does_not_admit_unknown_snapshot_input() -> None:
    workflow, provider = _workflow_and_provider()
    operations = (
        AddNodeOp(
            op="add_node",
            scope_path="",
            class_type="VAEDecode",
            fields={},
            inputs={},
            uid="fresh-decode",
            node_id="8",
        ),
        UpsertLinkOp(
            op="upsert_link",
            source=LinkSourceRef("", "4", "LATENT"),
            target=LinkTargetRef("", "fresh-decode", "not_a_socket"),
        ),
    )

    result = interpret(workflow, operations, schema_provider=provider)

    assert not result.ok
    assert result.transitions[0].outcome == "staged"
    assert result.transitions[1].outcome == "rejected"
    assert result.transitions[1].diagnostics[0].code == "missing_target_input"


def test_unchecked_cow_kernels_are_not_public_edit_entry_points() -> None:
    import vibecomfy.porting.edit as public_edit

    assert "apply_edit_cow" not in public_edit.__all__
    assert "apply_edits_cow" not in public_edit.__all__
    with pytest.raises(AttributeError):
        getattr(public_edit, "apply_edit_cow")
    with pytest.raises(AttributeError):
        getattr(public_edit, "apply_edits_cow")


def test_source_and_typed_explicit_uid_future_wired_add_batches_are_equivalent() -> None:
    workflow, provider = _workflow_and_provider()
    source = (
        "fresh = EmptyLatentImage(width=768, height=768, batch_size=1) "
        "# uid:wired-probe\n"
        "ksampler.latent_image = fresh.LATENT_0\n"
        "done()\n"
    )
    typed = (
        AddNodeOp(
            op="add_node",
            scope_path="",
            class_type="EmptyLatentImage",
            fields={"width": 768, "height": 768, "batch_size": 1},
            inputs={},
            uid="wired-probe",
            node_id="8",
        ),
        UpsertLinkOp(
            op="upsert_link",
            source=LinkSourceRef("", "wired-probe", "LATENT"),
            target=LinkTargetRef("", "5", "latent_image"),
        ),
    )

    source_result = interpret(workflow, source, schema_provider=provider)
    typed_result = interpret(workflow, typed, schema_provider=provider)

    assert source_result.ok, source_result.diagnostics
    assert typed_result.ok, typed_result.diagnostics
    assert source_result.workflow.semantic_projection() == typed_result.workflow.semantic_projection()
    assert tuple(item.outcome for item in source_result.transitions) == ("staged", "staged")
    assert tuple(item.outcome for item in typed_result.transitions) == ("staged", "staged")


def test_source_and_typed_no_uid_future_wired_add_batches_are_equivalent() -> None:
    """The original no-comment source program uses its planned minted UID."""
    workflow, provider = _workflow_and_provider()
    source = (
        "fresh = EmptyLatentImage(width=768, height=768, batch_size=1)\n"
        "ksampler.latent_image = fresh.LATENT_0\n"
        "done()\n"
    )
    typed = (
        AddNodeOp(
            op="add_node",
            scope_path="",
            class_type="EmptyLatentImage",
            fields={"width": 768, "height": 768, "batch_size": 1},
            inputs={},
            uid="n1",
            node_id="8",
        ),
        UpsertLinkOp(
            op="upsert_link",
            source=LinkSourceRef("", "n1", "LATENT"),
            target=LinkTargetRef("", "5", "latent_image"),
        ),
    )

    source_result = interpret(workflow, source, schema_provider=provider)
    typed_result = interpret(workflow, typed, schema_provider=provider)

    assert source_result.ok, source_result.diagnostics
    assert typed_result.ok, typed_result.diagnostics
    assert source_result.landed_ops[0].uid == "n1"
    assert source_result.workflow.semantic_projection() == typed_result.workflow.semantic_projection()
    assert tuple(item.outcome for item in source_result.transitions) == ("staged", "staged")
    assert tuple(item.outcome for item in typed_result.transitions) == ("staged", "staged")


def test_typed_noop_returns_the_evaluator_report_without_commit() -> None:
    graph = json.loads(
        Path("tests/fixtures/agent_edit/flat.json").read_text(encoding="utf-8")
    )
    provider = _flat_schema_provider()
    session = EditSession(graph, schema_provider=provider)
    before = session.workflow.semantic_projection()

    result = apply_edit_tool_call(
        session,
        "edit_node",
        {"target": "ksampler", "field": "steps", "value": 20},
    )

    assert result.ok is False
    assert result.reason == "no_op"
    assert result.revision == 0 == session.revision
    assert len(result.transitions) == 1
    assert result.transitions[0].outcome == "noop"
    assert result.transitions[0].lint_disposition == "dropped_noop"
    assert result.lint_result is not None
    assert result.occurrence_to_statement_index == {0: 0}
    assert session.workflow.semantic_projection() == before
