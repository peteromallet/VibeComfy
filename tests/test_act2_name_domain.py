"""Action 2 — frozen name domain, slot-collision fallback, idempotent prune.

Canary 03fced: replay's sealed KSampler roster must include
``control_after_generate`` derived from object_info so live emit and replay
share one name authority.
"""

from __future__ import annotations

from vibecomfy.comfy_nodes.agent.authority_receipts import canonical_frozen_name_table
from vibecomfy.ingest.normalize import from_ui
from vibecomfy.porting.edit._diff import diff
from vibecomfy.porting.edit._interpret import interpret
from vibecomfy.porting.edit.admit import (
    AdmissionRejected,
    admission_snapshot_for,
    admit_operations,
)
from vibecomfy.porting.edit.ops import SetNodeFieldOp, normalize_delta_ops
from vibecomfy.porting.object_info.consume import (
    compact_literal_widget_order,
    get_class,
    object_info_widget_order,
    object_info_widget_value_order,
)
from vibecomfy.schema.provider import ObjectInfoIndexSchemaProvider
from vibecomfy.workflow import VibeNode, VibeWorkflow, WorkflowSource

OBJECT_INFO_ROOT = "vibecomfy/porting/cache/object_info"

_KSAMPLER_DOMAIN = (
    "seed",
    "control_after_generate",
    "steps",
    "cfg",
    "sampler_name",
    "scheduler",
    "denoise",
)


def _provider() -> ObjectInfoIndexSchemaProvider:
    return ObjectInfoIndexSchemaProvider(OBJECT_INFO_ROOT)


def _ksampler_ui() -> dict:
    return {
        "nodes": [
            {
                "id": 3,
                "type": "KSampler",
                "mode": 0,
                "pos": [0, 0],
                "size": [300, 200],
                "flags": {},
                "order": 0,
                "properties": {"Node name for S&R": "KSampler"},
                "inputs": [
                    {"name": "model", "type": "MODEL", "link": 1},
                    {"name": "positive", "type": "CONDITIONING", "link": 2},
                    {"name": "negative", "type": "CONDITIONING", "link": 3},
                    {"name": "latent_image", "type": "LATENT", "link": 4},
                ],
                "outputs": [
                    {"name": "LATENT", "type": "LATENT", "links": [5], "slot_index": 0}
                ],
                "widgets_values": [123, "fixed", 20, 8.0, "euler", "normal", 1.0],
            }
        ],
        "links": [],
    }


def test_control_after_generate_in_frozen_domain_from_object_info() -> None:
    """Sealed replay roster includes object_info's UI-only control slot."""
    entry = get_class("KSampler")
    assert entry is not None
    assert "control_after_generate" in object_info_widget_order("KSampler")
    assert object_info_widget_value_order("KSampler") == list(_KSAMPLER_DOMAIN)
    assert compact_literal_widget_order(entry) == list(_KSAMPLER_DOMAIN)

    provider = _provider()
    schema = provider.get_schema("KSampler")
    assert schema is not None
    assert schema.widget_input_order == _KSAMPLER_DOMAIN

    table = canonical_frozen_name_table(_ksampler_ui(), schema_provider=provider)
    assert table["3"] == _KSAMPLER_DOMAIN


def test_slot_collision_name_keyed_fallback_keeps_frame_rate() -> None:
    """Input-channel frame_rate write survives a slot-0 widget_0 collision."""
    pre = VibeWorkflow("pre", WorkflowSource("act2-slot-collision"))
    pre.nodes["2"] = VibeNode(
        "2",
        "VHS_VideoCombine",
        widgets={"widget_0": 8},
        inputs={"frame_rate": 8, "loop_count": 0, "filename_prefix": "AnimateDiff"},
        uid="2",
    )
    post = VibeWorkflow("post", WorkflowSource("act2-slot-collision"))
    post.nodes["2"] = VibeNode(
        "2",
        "VHS_VideoCombine",
        widgets={"widget_0": 8},
        inputs={"frame_rate": 24, "loop_count": 0, "filename_prefix": "AnimateDiff"},
        uid="2",
    )
    ops = diff(pre, post)
    frame_ops = [
        op
        for op in ops
        if isinstance(op, SetNodeFieldOp) and op.target.field_path == "frame_rate"
    ]
    assert frame_ops, ops
    assert frame_ops[0].value == 24


def test_idempotent_writes_are_pruned_not_fatal() -> None:
    """Already-set ops are dropped; a mixed batch still lands the real write."""
    provider = _provider()
    workflow = from_ui(
        dict(_ksampler_ui()), schema_provider=provider, use_comfy_converter=False
    )
    mixed = normalize_delta_ops(
        {
            "schema_version": "2.0.0",
            "ops": [
                {"op": "set_node_field", "target": ["", "3", "steps"], "value": 20},
                {"op": "set_node_field", "target": ["", "3", "cfg"], "value": 3.5},
            ],
        }
    )
    step = interpret(workflow, mixed, schema_provider=provider)
    assert step.ok, step.diagnostics
    assert len(step.landed_ops) == 1
    assert isinstance(step.landed_ops[0], SetNodeFieldOp)
    assert step.landed_ops[0].target.field_path == "cfg"
    assert step.landed_ops[0].value == 3.5
    node = next(iter(step.workflow.nodes.values()))
    assert (node.inputs or {}).get("cfg") == 3.5 or (node.widgets or {}).get("cfg") == 3.5

    admitted = admit_operations(
        admission_snapshot_for(workflow, provider),
        mixed,
        working_workflow=workflow,
    )
    assert not isinstance(admitted, AdmissionRejected), getattr(
        admitted, "typed_reason", admitted
    )

    vacuous = normalize_delta_ops(
        {
            "schema_version": "2.0.0",
            "ops": [
                {"op": "set_node_field", "target": ["", "3", "steps"], "value": 20},
            ],
        }
    )
    empty = interpret(workflow, vacuous, schema_provider=provider)
    assert empty.ok is False
    assert empty.landed_ops == ()
    assert any(item.code == "no_op" for item in empty.diagnostics)

    rejected = admit_operations(
        admission_snapshot_for(workflow, provider),
        vacuous,
        working_workflow=workflow,
    )
    assert isinstance(rejected, AdmissionRejected)
    assert rejected.typed_reason == "no_op"
