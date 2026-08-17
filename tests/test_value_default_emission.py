from __future__ import annotations

from dataclasses import replace

import pytest

from vibecomfy.porting.edit.session import EditSession
from vibecomfy.porting.edit.value_defaults import (
    VALUE_DEFAULT_FIELDS_MARKER,
    ValueDefaultBinding,
    ValueDefaultContext,
    ValueUserOverride,
)
from vibecomfy.schema import InputSpec, NodeSchema


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


def _session(context=None, *, schema=None) -> EditSession:
    provider = _Provider(schema or _schema())
    return EditSession(
        _empty_ui(),
        schema_provider=provider,
        value_default_context=context,
    )


def _widget_steps(session: EditSession) -> int:
    return session.working_ui["nodes"][0]["widgets_values"][0]


def test_value_default_explicit_user_precedence() -> None:
    context = ValueDefaultContext(
        bindings=(_binding(33),),
        user_overrides=(
            ValueUserOverride("ValueDefaultNode", "steps", 12),
        ),
    )
    session = _session(context)
    batch = session.apply_batch("n = ValueDefaultNode()")

    assert batch.ok is True
    assert _widget_steps(session) == 12
    assert batch.landed_ops[0].fields["steps"] == 12
    assert batch.landed_ops[0].fields[VALUE_DEFAULT_FIELDS_MARKER] == ["steps"]


def test_value_default_exact_user_request_precedence_but_vague_request_has_no_authority() -> None:
    exact = ValueDefaultContext(
        bindings=(_binding(33),),
        user_request="Please use 12 steps for this node.",
    )
    exact_session = _session(exact)
    exact_batch = exact_session.apply_batch("n = ValueDefaultNode()")
    assert exact_batch.ok is True
    assert _widget_steps(exact_session) == 12

    vague = ValueDefaultContext(
        bindings=(_binding(33),),
        user_request="Please use more steps for this node.",
    )
    vague_session = _session(vague)
    vague_batch = vague_session.apply_batch("n = ValueDefaultNode(steps=40)")
    assert vague_batch.ok is True
    assert _widget_steps(vague_session) == 33
    assert any(
        issue.code == "value_default_literal_normalized"
        and issue.severity == "warning"
        for issue in vague_batch.diagnostics
    )

    negated = ValueDefaultContext(
        bindings=(_binding(33),),
        user_request="I don't want you to set steps to 12.",
    )
    negated_session = _session(negated)
    negated_batch = negated_session.apply_batch("n = ValueDefaultNode(steps=12)")
    assert negated_batch.ok is True
    assert _widget_steps(negated_session) == 33


def test_value_default_high_confidence_prior_used() -> None:
    session = _session(ValueDefaultContext(bindings=(_binding(37),)))
    batch = session.apply_batch("n = ValueDefaultNode()")

    assert batch.ok is True
    assert _widget_steps(session) == 37


def test_value_default_session_persists_effective_fields_for_replay() -> None:
    provider = _Provider(_schema())
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

    replay = EditSession(_empty_ui(), schema_provider=provider)
    replay_batch = replay.apply_batch("restored = ValueDefaultNode(steps=37)")
    assert replay_batch.ok is True
    assert replay.working_ui["nodes"][0]["widgets_values"] == session.working_ui["nodes"][0]["widgets_values"]

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
    session = _session(context, schema=_schema(default=20))
    batch = session.apply_batch("n = ValueDefaultNode()")

    assert batch.ok is True
    assert _widget_steps(session) == 20


def test_value_default_invalid_prior_uses_schema_default() -> None:
    session = _session(
        ValueDefaultContext(bindings=(_binding(1000),)),
        schema=_schema(default=20),
    )
    batch = session.apply_batch("n = ValueDefaultNode()")

    assert batch.ok is True
    assert _widget_steps(session) == 20


def test_value_default_required_literal_without_default_keeps_pre_feature_warning() -> None:
    session = _session(
        ValueDefaultContext(),
        schema=_schema(default=None, required=True),
    )
    batch = session.apply_batch("n = ValueDefaultNode()")

    assert batch.ok is True
    assert any(
        issue.code == "missing_required_add_node_input"
        and issue.severity == "warning"
        for issue in batch.diagnostics
    )


def test_value_default_edit_after_requires_and_accepts_user_receipt() -> None:
    provider = _Provider(_schema(default=20))
    add_context = ValueDefaultContext(bindings=(_binding(37),))
    added = EditSession(
        _empty_ui(),
        schema_provider=provider,
        value_default_context=add_context,
    )
    added_batch = added.apply_batch("n = ValueDefaultNode()")
    assert added_batch.ok is True
    uid = added.working_ui["nodes"][0]["properties"]["vibecomfy_uid"]
    protected = add_context.protect_node(
        scope_path="",
        uid=uid,
        class_type="ValueDefaultNode",
        fields=("steps",),
    )
    authorized = replace(
        protected,
        user_overrides=(
            ValueUserOverride("ValueDefaultNode", "steps", 12),
        ),
    )

    refused = EditSession(
        added.working_ui,
        schema_provider=provider,
        value_default_context=protected,
    )
    refused.render()
    name = refused.name_by_uid[uid]
    refused_batch = refused.apply_batch(f"{name}.steps = 13")
    assert refused_batch.ok is False
    assert any(
        issue.code == "unauthorized_set_node_field_override"
        for issue in refused_batch.diagnostics
    )

    accepted = EditSession(
        added.working_ui,
        schema_provider=provider,
        value_default_context=authorized,
    )
    accepted.render()
    name = accepted.name_by_uid[uid]
    accepted_batch = accepted.apply_batch(f"{name}.steps = 12")
    assert accepted_batch.ok is True
    assert accepted.working_ui["nodes"][0]["widgets_values"][0] == 12
    assert any(
        issue.code == "value_default_edit_receipt"
        and issue.detail["basis"] == "explicit_user_value"
        for issue in accepted_batch.diagnostics
    )


def test_value_default_direct_multi_op_apply_gates_edit_after_add() -> None:
    session = _session(ValueDefaultContext(bindings=(_binding(37),)))
    batch = session.apply_batch("n = ValueDefaultNode()\nn.steps = 13\n")

    assert batch.ok is False
    assert any(
        issue.code == "unauthorized_set_node_field_override"
        for issue in batch.diagnostics
    )


def test_value_default_selected_source_instance_is_consumed_once() -> None:
    session = _session(
        ValueDefaultContext(bindings=(_binding(37),)),
        schema=_schema(default=20),
    )
    batch = session.apply_batch("a = ValueDefaultNode()\nb = ValueDefaultNode()\n")

    assert batch.ok is True
    assert [
        node["widgets_values"][0] for node in session.working_ui["nodes"]
    ] == [37, 20]


def test_value_default_replay_marker_is_not_added_to_unbound_canonical_add() -> None:
    session = _session(schema=_schema(default=20))
    batch = session.apply_batch("n = ValueDefaultNode(steps=20)")

    assert batch.ok is True
    node = session.working_ui["nodes"][0]
    assert "vibecomfy_value_default_fields" not in node["properties"]
    assert VALUE_DEFAULT_FIELDS_MARKER not in batch.landed_ops[0].fields


def test_value_default_result_is_identical_without_any_golden_access(monkeypatch) -> None:
    import pathlib

    original_open = pathlib.Path.open

    def _deny_golden(self, *args, **kwargs):
        lowered = str(self).lower()
        if "golden" in lowered or "predicates.py" in lowered:
            raise AssertionError(f"value-default binder attempted forbidden read: {self}")
        return original_open(self, *args, **kwargs)

    monkeypatch.setattr(pathlib.Path, "open", _deny_golden)
    context = ValueDefaultContext(bindings=(_binding(37),))

    without_golden = _session(context, schema=_schema(default=20))
    without_golden.apply_batch("n = ValueDefaultNode()")
    graph_with_irrelevant_metadata = _empty_ui()
    graph_with_irrelevant_metadata["extra"]["evaluation"] = {"available": False}
    also = EditSession(
        graph_with_irrelevant_metadata,
        schema_provider=_Provider(_schema(default=20)),
        value_default_context=context,
    )
    also.apply_batch("n = ValueDefaultNode()")

    assert without_golden.working_ui["nodes"] == also.working_ui["nodes"]


def test_value_default_qualified_prior_normalizes_model_literal_without_blocking() -> None:
    session = _session(
        ValueDefaultContext(bindings=(_binding(37),)),
        schema=_schema(default=20),
    )
    batch = session.apply_batch("n = ValueDefaultNode(steps=99)")

    assert batch.ok is True
    assert _widget_steps(session) == 37
    assert any(
        issue.code == "value_default_literal_normalized"
        and issue.severity == "warning"
        for issue in batch.diagnostics
    )


def test_value_default_unqualified_prior_preserves_model_literal() -> None:
    session = _session(
        ValueDefaultContext(bindings=(_binding(37, confidence="medium"),)),
        schema=_schema(default=20),
    )
    batch = session.apply_batch("n = ValueDefaultNode(steps=41)")

    assert batch.ok is True
    assert _widget_steps(session) == 41


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
    session = EditSession(
        _empty_ui(),
        schema_provider=_Provider(schema),
        value_default_context=ValueDefaultContext(),
    )
    batch = session.apply_batch("n = ImageScaleBy(upscale_method='lanczos', scale_by=2.0)")

    assert batch.ok is True
    assert session.working_ui["nodes"][0]["widgets_values"] == ["lanczos", 2.0]
    assert not any(
        issue.code == "value_default_literal_normalized"
        for issue in batch.diagnostics
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
    session = EditSession(
        _empty_ui(),
        schema_provider=_Provider(schema),
        value_default_context=context,
    )
    batch = session.apply_batch(f"n = ManualSigmas(sigmas={sigma_string!r})")

    assert batch.ok is True
    assert session.working_ui["nodes"][0]["widgets_values"] == [sigma_string]
    assert not any(
        issue.code == "value_default_literal_normalized"
        for issue in batch.diagnostics
    )
