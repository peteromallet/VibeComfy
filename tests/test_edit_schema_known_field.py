from __future__ import annotations

from vibecomfy.ingest.normalize import from_ui
from vibecomfy.porting.edit._interpret import interpret
from vibecomfy.porting.edit._ir_utils import apply_edit_cow
from vibecomfy.porting.edit._op_validate import _validate_one
from vibecomfy.porting.edit.ops import NodeFieldTarget, SetNodeFieldOp
from vibecomfy.schema import InputSpec, NodeSchema, OutputSpec
from vibecomfy.schema.types import (
    FrozenSchemaSnapshotProvider,
    capture_schema_snapshot,
    schema_payload_from_node_schema,
)


def _schema(class_type: str, inputs: dict, outputs: list | None = None) -> NodeSchema:
    return NodeSchema(
        class_type=class_type,
        pack="core",
        inputs=inputs,
        outputs=list(outputs or []),
    )


def _provider(schemas: dict[str, NodeSchema], *, node_classes: dict[str, str]) -> FrozenSchemaSnapshotProvider:
    payload = {
        class_type: schema_payload_from_node_schema(class_type, schema)
        for class_type, schema in schemas.items()
    }
    return FrozenSchemaSnapshotProvider(
        capture_schema_snapshot(
            class_types=list(schemas),
            request_snapshot={
                "contract_version": "schema_snapshot_v1",
                "schemas": payload,
                "missing_classes": [],
                "node_classes": dict(node_classes),
            },
        )
    )


def _linked_seed_ui() -> dict:
    return {
        "last_node_id": 8,
        "last_link_id": 10,
        "nodes": [
            {
                "id": 5,
                "type": "KSampler",
                "pos": [0, 0],
                "size": [210, 80],
                "flags": {},
                "order": 1,
                "mode": 0,
                "inputs": [
                    {"name": "model", "type": "MODEL", "link": None},
                    {"name": "seed", "type": "INT", "widget": {"name": "seed"}, "link": 10},
                ],
                "outputs": [{"name": "LATENT", "type": "LATENT", "links": []}],
                "properties": {"vibecomfy_uid": "5"},
                "widgets_values": [],
            },
            {
                "id": 8,
                "type": "PrimitiveInt",
                "pos": [240, 0],
                "size": [210, 58],
                "flags": {},
                "order": 0,
                "mode": 0,
                "inputs": [],
                "outputs": [{"name": "value", "type": "INT", "links": [10], "slot_index": 0}],
                "properties": {"vibecomfy_uid": "8"},
                "widgets_values": [7],
            },
        ],
        "links": [[10, 8, 0, 5, 1, "INT"]],
        "groups": [],
        "config": {},
        "extra": {},
        "version": 0.4,
    }


def _schemas() -> dict[str, NodeSchema]:
    return {
        "KSampler": _schema(
            "KSampler",
            {
                "seed": InputSpec(type="INT"),
                "steps": InputSpec(type="INT", min=1, max=100),
                "model": InputSpec(type="MODEL", required=True),
            },
            [OutputSpec(type="LATENT", name="LATENT")],
        ),
        "PrimitiveInt": _schema(
            "PrimitiveInt",
            {"value": InputSpec(type="INT")},
            [OutputSpec(type="INT", name="value")],
        ),
    }


def test_schema_known_linked_seed_field_is_accepted() -> None:
    ui = _linked_seed_ui()
    provider = _provider(_schemas(), node_classes={"5": "KSampler", "8": "PrimitiveInt"})
    op = SetNodeFieldOp(
        op="set_node_field",
        target=NodeFieldTarget(scope_path="", uid="5", field_path="seed"),
        value=12345,
    )

    workflow = from_ui(dict(ui), schema_provider=provider, use_comfy_converter=False)
    _validate_one(workflow, op, provider)
    post = apply_edit_cow(workflow, op, schema_provider=provider)
    sampler = next(node for node in post.nodes.values() if str(node.uid) == "5")
    assert sampler.widgets.get("seed") == 12345 or sampler.inputs.get("seed") == 12345
    assert all(
        not (str(edge.to_node) == str(sampler.id) and edge.to_input == "seed")
        for edge in post.edges
    )

    result = interpret(workflow, (op,), schema_provider=provider)
    assert result.ok is True
    assert any(getattr(issue, "code", "") == "automatic_link_removal" for issue in result.diagnostics)
    assert result.lint_result is not None
    assert result.lint_result.normalizations[0].disposition == "passed"
    assert all(
        getattr(issue, "code", "") != "unknown_field"
        for issue in tuple(result.diagnostics) + tuple(result.lint_result.issues)
    )


def test_unresolvable_unknown_field_is_rejected() -> None:
    ui = _linked_seed_ui()
    provider = _provider(_schemas(), node_classes={"5": "KSampler", "8": "PrimitiveInt"})
    op = SetNodeFieldOp(
        op="set_node_field",
        target=NodeFieldTarget(scope_path="", uid="5", field_path="not_a_real_field"),
        value=12345,
    )

    workflow = from_ui(dict(ui), schema_provider=provider, use_comfy_converter=False)
    result = interpret(workflow, (op,), schema_provider=provider)
    assert result.ok is False
    assert any(
        getattr(issue, "code", "") in {"unknown_field", "unknown_target_field"}
        for issue in result.diagnostics
    )
