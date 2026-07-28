from __future__ import annotations

from dataclasses import replace

import pytest

from vibecomfy.porting.edit.apply import apply_delta
from vibecomfy.porting.edit.apply_types import (
    AppliedAddNodeSpec,
    VALUE_DEFAULT_FIELDS_MARKER,
    ValueDefaultBinding,
    ValueDefaultContext,
    ValueUserOverride,
)
from vibecomfy.porting.edit.ops import AddNodeOp, NodeFieldTarget, SetNodeFieldOp
from vibecomfy.porting.edit.session import EditSession
from vibecomfy.schema import InputSpec, NodeSchema
from vibecomfy.executor.research import _build_precedent_slices


class _Provider:
    def __init__(self, schema: NodeSchema) -> None:
        self.schema = schema

    def get_schema(self, class_type: str) -> NodeSchema | None:
        return self.schema if class_type == self.schema.class_type else None


def _schema(*, default: int | None = 20, required: bool = True) -> NodeSchema:
    return NodeSchema(
        class_type="ValueDefaultNode",
        pack=None,
        inputs={
            "steps": InputSpec(
                "INT",
                required=required,
                default=default,
                min=1,
                max=100,
            ),
        },
        outputs=[],
    )


def _empty_ui() -> dict:
    return {
        "last_node_id": 0,
        "last_link_id": 0,
        "nodes": [],
        "links": [],
        "groups": [],
        "config": {},
        "extra": {},
        "version": 0.4,
    }


def _binding(
    value,
    *,
    confidence: str = "high",
    instance: str = "source-1",
    selection_status: str = "unique",
) -> ValueDefaultBinding:
    return ValueDefaultBinding(
        class_type="ValueDefaultNode",
        source_instance_id=instance,
        role_label="sampling",
        canonical_field="steps",
        value=value,
        provenance="source_template",
        confidence=confidence,
        selection_status=selection_status,
        name_resolution_status="canonical",
        conflict_status="unique_value",
        source_index=0,
        source_shape=1,
    )


def _add(fields=None) -> AddNodeOp:
    return AddNodeOp(
        op="add_node",
        scope_path="",
        class_type="ValueDefaultNode",
        fields=fields or {},
        inputs={},
    )


def _applied_value(result) -> int:
    assert result.ok and result.candidate is not None
    return result.candidate["nodes"][0]["widgets_values"][0]


def test_value_default_explicit_user_precedence() -> None:
    context = ValueDefaultContext(
        bindings=(_binding(33),),
        user_overrides=(
            ValueUserOverride("ValueDefaultNode", "steps", 12),
        ),
    )
    result = apply_delta(
        _empty_ui(),
        (_add(),),
        schema_provider=_Provider(_schema()),
        value_default_context=context,
    )

    assert _applied_value(result) == 12
    applied = result.resolved_ops[0][1]
    assert isinstance(applied, AppliedAddNodeSpec)
    assert applied.op.fields["steps"] == 12
    assert applied.op.fields[VALUE_DEFAULT_FIELDS_MARKER] == ["steps"]
    assert applied.value_default_receipts[0].provenance == "user"


def test_value_default_exact_user_request_precedence_but_vague_request_has_no_authority() -> None:
    exact = ValueDefaultContext(
        bindings=(_binding(33),),
        user_request="Please use 12 steps for this node.",
    )
    exact_result = apply_delta(
        _empty_ui(),
        (_add(),),
        schema_provider=_Provider(_schema()),
        value_default_context=exact,
    )
    assert _applied_value(exact_result) == 12

    vague = ValueDefaultContext(
        bindings=(_binding(33),),
        user_request="Please use more steps for this node.",
    )
    vague_result = apply_delta(
        _empty_ui(),
        (_add({"steps": 40}),),
        schema_provider=_Provider(_schema()),
        value_default_context=vague,
    )
    assert vague_result.ok is True
    assert _applied_value(vague_result) == 33
    assert any(
        issue.code == "value_default_literal_normalized"
        and issue.severity == "warning"
        for issue in vague_result.diagnostics
    )

    negated = ValueDefaultContext(
        bindings=(_binding(33),),
        user_request="I don't want you to set steps to 12.",
    )
    negated_result = apply_delta(
        _empty_ui(),
        (_add({"steps": 12}),),
        schema_provider=_Provider(_schema()),
        value_default_context=negated,
    )
    assert negated_result.ok is True
    assert _applied_value(negated_result) == 33


def test_value_default_high_confidence_prior_used() -> None:
    result = apply_delta(
        _empty_ui(),
        (_add(),),
        schema_provider=_Provider(_schema()),
        value_default_context=ValueDefaultContext(bindings=(_binding(37),)),
    )

    assert _applied_value(result) == 37
    receipt_details = [
        diagnostic.detail.get("value_default_receipts")
        for diagnostic in result.diagnostics
        if diagnostic.code == "add_node_applied"
    ]
    assert receipt_details[0][0]["provenance"] == "source_template"


def test_value_default_session_persists_effective_fields_for_replay() -> None:
    provider = _Provider(_schema())
    provider.schemas = lambda: {"ValueDefaultNode": provider.schema}
    session = EditSession(
        _empty_ui(),
        schema_provider=provider,
        value_default_context=ValueDefaultContext(bindings=(_binding(37),)),
    )

    batch = session.apply_batch("restored = ValueDefaultNode()")

    assert batch.ok is True
    assert batch.landed_ops[0].fields["steps"] == 37
    assert batch.landed_ops[0].fields[VALUE_DEFAULT_FIELDS_MARKER] == ["steps"]
    assert session.working_ui["nodes"][0]["widgets_values"][0] == 37
    assert session.value_default_context is not None
    assert session.value_default_context.protected_nodes[0].uid

    replay = apply_delta(
        _empty_ui(),
        batch.landed_ops,
        schema_provider=provider,
    )
    assert replay.ok and replay.candidate is not None
    assert replay.candidate["nodes"] == session.working_ui["nodes"]

    later = EditSession(
        session.working_ui,
        schema_provider=provider,
        value_default_context=ValueDefaultContext(
            user_overrides=(
                ValueUserOverride("ValueDefaultNode", "steps", 12),
            ),
        ),
    )
    later.render()
    uid = session.value_default_context.protected_nodes[0].uid
    later_name = later.name_by_uid[uid]
    edit = later.apply_batch(f"{later_name}.steps = 12")
    assert edit.ok is True
    assert later.working_ui["nodes"][0]["widgets_values"][0] == 12


@pytest.mark.parametrize(
    "context",
    [
        ValueDefaultContext(bindings=(_binding(44, confidence="medium"),)),
        ValueDefaultContext(
            bindings=(
                _binding(31, instance="source-1", selection_status="ambiguous"),
                _binding(47, instance="source-2", selection_status="ambiguous"),
            ),
            selected_instances=(
                ("ValueDefaultNode", "source-1"),
                ("ValueDefaultNode", "source-2"),
            ),
        ),
        ValueDefaultContext(
            bindings=(
                _binding(31, instance="source-1", selection_status="ambiguous"),
                _binding(31, instance="source-2", selection_status="ambiguous"),
            ),
            selected_instances=(
                ("ValueDefaultNode", "source-1"),
                ("ValueDefaultNode", "source-2"),
            ),
        ),
    ],
)
def test_value_default_low_confidence_or_conflict_refused(context) -> None:
    result = apply_delta(
        _empty_ui(),
        (_add(),),
        schema_provider=_Provider(_schema(default=20)),
        value_default_context=context,
    )

    assert _applied_value(result) == 20
    applied = result.resolved_ops[0][1]
    assert isinstance(applied, AppliedAddNodeSpec)
    assert applied.value_default_receipts == ()


def test_value_default_invalid_prior_uses_schema_default() -> None:
    result = apply_delta(
        _empty_ui(),
        (_add(),),
        schema_provider=_Provider(_schema(default=20)),
        value_default_context=ValueDefaultContext(bindings=(_binding(1000),)),
    )

    assert _applied_value(result) == 20
    applied = result.resolved_ops[0][1]
    assert isinstance(applied, AppliedAddNodeSpec)
    assert applied.value_default_receipts == ()


def test_value_default_required_literal_without_default_keeps_pre_feature_warning() -> None:
    result = apply_delta(
        _empty_ui(),
        (_add(),),
        schema_provider=_Provider(_schema(default=None, required=True)),
        value_default_context=ValueDefaultContext(),
    )

    assert result.ok is True
    assert result.candidate is not None
    assert any(
        issue.code == "missing_required_add_node_input"
        and issue.severity == "warning"
        for issue in result.diagnostics
    )


def test_value_default_edit_after_requires_and_accepts_user_receipt() -> None:
    provider = _Provider(_schema(default=20))
    add_context = ValueDefaultContext(bindings=(_binding(37),))
    added = apply_delta(
        _empty_ui(),
        (_add(),),
        schema_provider=provider,
        value_default_context=add_context,
    )
    assert added.ok and added.candidate is not None
    applied = added.resolved_ops[0][1]
    assert isinstance(applied, AppliedAddNodeSpec)
    protected = add_context.protect_node(
        scope_path="",
        uid=applied.uid,
        class_type="ValueDefaultNode",
        fields=("steps",),
    )
    authorized = replace(
        protected,
        user_overrides=(
            ValueUserOverride("ValueDefaultNode", "steps", 12),
        ),
    )
    edit = SetNodeFieldOp(
        op="set_node_field",
        target=NodeFieldTarget("", applied.uid, "steps"),
        value=12,
    )

    refused = apply_delta(
        added.candidate,
        (replace(edit, value=13),),
        schema_provider=provider,
        value_default_context=protected,
    )
    assert refused.ok is False
    assert any(
        issue.code == "unauthorized_set_node_field_override"
        for issue in refused.diagnostics
    )

    accepted = apply_delta(
        added.candidate,
        (edit,),
        schema_provider=provider,
        value_default_context=authorized,
    )
    assert accepted.ok and accepted.candidate is not None
    assert accepted.candidate["nodes"][0]["widgets_values"][0] == 12
    assert any(
        issue.code == "value_default_edit_receipt"
        and issue.detail["basis"] == "explicit_user_value"
        for issue in accepted.diagnostics
    )


def test_value_default_direct_multi_op_apply_gates_edit_after_add() -> None:
    unauthorized_edit = SetNodeFieldOp(
        op="set_node_field",
        target=NodeFieldTarget("", "1", "steps"),
        value=13,
    )
    result = apply_delta(
        _empty_ui(),
        (_add(), unauthorized_edit),
        schema_provider=_Provider(_schema()),
        value_default_context=ValueDefaultContext(bindings=(_binding(37),)),
    )

    assert result.ok is False
    assert any(
        issue.code == "unauthorized_set_node_field_override"
        for issue in result.diagnostics
    )


def test_value_default_selected_source_instance_is_consumed_once() -> None:
    result = apply_delta(
        _empty_ui(),
        (_add(), _add()),
        schema_provider=_Provider(_schema(default=20)),
        value_default_context=ValueDefaultContext(bindings=(_binding(37),)),
    )

    assert result.ok and result.candidate is not None
    assert [
        node["widgets_values"][0] for node in result.candidate["nodes"]
    ] == [37, 20]


def test_value_default_replay_marker_is_not_added_to_unbound_canonical_add() -> None:
    result = apply_delta(
        _empty_ui(),
        (
            replace(
                _add({"steps": 20}),
                uid="caller-identity",
                node_id="1",
            ),
        ),
        schema_provider=_Provider(_schema(default=20)),
    )

    assert result.ok and result.candidate is not None
    node = result.candidate["nodes"][0]
    assert "vibecomfy_value_default_fields" not in node["properties"]
    applied = result.resolved_ops[0][1]
    assert isinstance(applied, AppliedAddNodeSpec)
    assert VALUE_DEFAULT_FIELDS_MARKER not in applied.op.fields


def test_value_default_result_is_identical_without_any_golden_access(monkeypatch) -> None:
    import pathlib

    original_open = pathlib.Path.open

    def _deny_golden(self, *args, **kwargs):
        lowered = str(self).lower()
        if "golden" in lowered or "predicates.py" in lowered:
            raise AssertionError(f"value-default binder attempted forbidden read: {self}")
        return original_open(self, *args, **kwargs)

    monkeypatch.setattr(pathlib.Path, "open", _deny_golden)
    provider = _Provider(_schema(default=20))
    context = ValueDefaultContext(bindings=(_binding(37),))

    without_golden = apply_delta(
        _empty_ui(),
        (_add(),),
        schema_provider=provider,
        value_default_context=context,
    )
    graph_with_irrelevant_metadata = _empty_ui()
    graph_with_irrelevant_metadata["extra"]["evaluation"] = {"available": False}
    also_without_golden = apply_delta(
        graph_with_irrelevant_metadata,
        (_add(),),
        schema_provider=provider,
        value_default_context=context,
    )

    assert without_golden.ok and also_without_golden.ok
    assert without_golden.candidate["nodes"] == also_without_golden.candidate["nodes"]


def test_value_default_qualified_prior_normalizes_model_literal_without_blocking() -> None:
    result = apply_delta(
        _empty_ui(),
        (_add({"steps": 99}),),
        schema_provider=_Provider(_schema(default=20)),
        value_default_context=ValueDefaultContext(bindings=(_binding(37),)),
    )

    assert result.ok is True
    assert _applied_value(result) == 37
    assert any(
        issue.code == "value_default_literal_normalized"
        and issue.severity == "warning"
        for issue in result.diagnostics
    )


def test_value_default_unqualified_prior_preserves_model_literal() -> None:
    result = apply_delta(
        _empty_ui(),
        (_add({"steps": 41}),),
        schema_provider=_Provider(_schema(default=20)),
        value_default_context=ValueDefaultContext(
            bindings=(_binding(37, confidence="medium"),),
        ),
    )

    assert result.ok is True
    assert _applied_value(result) == 41
    applied = result.resolved_ops[0][1]
    assert isinstance(applied, AppliedAddNodeSpec)
    assert applied.value_default_receipts == ()


def test_value_default_empty_context_does_not_block_case00_constructor_literals() -> None:
    schema = NodeSchema(
        class_type="ImageScaleBy",
        pack=None,
        inputs={
            "image": InputSpec("IMAGE", required=True),
            "upscale_method": InputSpec(
                "STRING",
                required=True,
                choices=("nearest-exact", "bilinear", "area", "bicubic", "lanczos"),
            ),
            "scale_by": InputSpec(
                "FLOAT",
                required=True,
                default=1.0,
                min=0.01,
                max=8.0,
            ),
        },
        outputs=[],
    )
    result = apply_delta(
        _empty_ui(),
        (
            AddNodeOp(
                op="add_node",
                scope_path="",
                class_type="ImageScaleBy",
                fields={"upscale_method": "lanczos", "scale_by": 2.0},
                inputs={},
            ),
        ),
        schema_provider=_Provider(schema),
        value_default_context=ValueDefaultContext(),
    )

    assert result.ok is True
    assert result.candidate is not None
    assert result.candidate["nodes"][0]["widgets_values"] == ["lanczos", 2.0]
    assert not any(
        issue.code == "value_default_literal_normalized"
        for issue in result.diagnostics
    )


def test_value_default_alias_unmatched_prior_does_not_block_case01_literal() -> None:
    sigma_string = "0.85, 0.7250, 0.4219, 0.0"
    schema = NodeSchema(
        class_type="ManualSigmas",
        pack=None,
        inputs={
            "widget_0": InputSpec("STRING", required=True),
        },
        outputs=[],
    )
    context = ValueDefaultContext(
        bindings=(
            ValueDefaultBinding(
                class_type="ManualSigmas",
                source_instance_id="refinement",
                role_label="refinement",
                canonical_field="sigmas",
                value=sigma_string,
                provenance="source_template",
                confidence="high",
                selection_status="unique",
                name_resolution_status="canonical",
                conflict_status="unique_value",
            ),
        ),
    )
    result = apply_delta(
        _empty_ui(),
        (
            AddNodeOp(
                op="add_node",
                scope_path="",
                class_type="ManualSigmas",
                fields={"sigmas": sigma_string},
                inputs={},
            ),
        ),
        schema_provider=_Provider(schema),
        value_default_context=context,
    )

    assert result.ok is True
    assert result.candidate is not None
    assert result.candidate["nodes"][0]["widgets_values"] == [sigma_string]
    assert not any(
        issue.code == "value_default_literal_normalized"
        for issue in result.diagnostics
    )


def test_binding_envelope_preserves_conflicting_same_class_instances_until_selected() -> None:
    slices = _build_precedent_slices((
        {
            "source": "source_workflow",
            "class_type": "ValueDefaultNode",
            "source_template": "fixture/template",
            "provenance_instances": (
                {
                    "node_id": "source-1",
                    "widget_values": ({"name": "steps", "value": 31},),
                    "incident_edges": (),
                },
                {
                    "node_id": "source-2",
                    "widget_values": ({"name": "steps", "value": 47},),
                    "incident_edges": (),
                },
            ),
        },
    ))

    assert len(slices) == 2
    assert {
        slice_.binding_envelope["selector"]["source_instance_id"]
        for slice_ in slices
    } == {"source-1", "source-2"}
    assert all(
        slice_.binding_envelope["fields"][0]["conflict_status"] == "conflicting"
        and slice_.binding_envelope["fields"][0]["eligibility_status"]
        == "pending_source_selection"
        for slice_ in slices
    )

    context = ValueDefaultContext.from_precedent_slices(
        tuple(slice_.to_dict() for slice_ in slices),
        adaptation_plan={
            "selected_slice": {
                "source_class_type": "ValueDefaultNode",
                "node_ids": ["source-2"],
            },
        },
    )
    result = apply_delta(
        _empty_ui(),
        (_add(),),
        schema_provider=_Provider(_schema()),
        value_default_context=context,
    )
    assert _applied_value(result) == 47


def test_binding_envelope_keeps_provisional_widget_name_as_non_bindable_evidence() -> None:
    slices = _build_precedent_slices((
        {
            "source": "source_workflow",
            "class_type": "ValueDefaultNode",
            "source_template": "fixture/template",
            "provenance_instances": (
                {
                    "node_id": "source-1",
                    "widget_values": ({"name": "widget_0", "value": 88},),
                    "incident_edges": (),
                },
            ),
        },
    ))
    field = slices[0].binding_envelope["fields"][0]
    assert field["name_resolution_status"] == "provisional"
    assert field["eligible"] is False
    context = ValueDefaultContext.from_precedent_slices((slices[0].to_dict(),))
    result = apply_delta(
        _empty_ui(),
        (_add(),),
        schema_provider=_Provider(_schema(default=20)),
        value_default_context=context,
    )
    assert _applied_value(result) == 20


def test_value_default_precedent_prompt_keeps_normal_construction_additive() -> None:
    from vibecomfy.comfy_nodes.agent.edit import _build_precedent_adaptation_prompt

    prompt = _build_precedent_adaptation_prompt(
        None,
        precedent_slices=(
            {
                "source_class_type": "ValueDefaultNode",
                "node_ids": ["source-1"],
                "binding_envelope": {"version": 1},
            },
        ),
    )

    assert "construct and wire the node normally" in prompt
    assert "supply a schema-valid literal yourself" in prompt
    assert "never a reason to clarify, defer, or leave the graph unchanged" in prompt
    assert "Do not copy binding JSON back" in prompt
