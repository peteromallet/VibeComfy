from __future__ import annotations

from vibecomfy.porting.edit._ir_utils import apply_edit_cow
from vibecomfy.porting.edit.ops import NodeFieldTarget, SetNodeFieldOp
from vibecomfy.porting.emit.emit_agent_edit import emit_agent_edit_python
from vibecomfy.porting.emit.ui import emit_ui_json
from vibecomfy.schema import InputSpec, NodeSchema, OutputSpec
from vibecomfy.workflow import RawWidgetPayload, VibeNode, VibeWorkflow, WorkflowSource


class _PrimitiveProvider:
    def get_schema(self, class_type: str) -> NodeSchema | None:
        if class_type != "Float":
            return None
        return NodeSchema(
            "Float",
            "core",
            {"value": InputSpec("FLOAT")},
            [OutputSpec("FLOAT", "FLOAT")],
        )


def _float_workflow() -> VibeWorkflow:
    workflow = VibeWorkflow("float-alias", WorkflowSource("test"))
    workflow.nodes["218"] = VibeNode(
        "218",
        "Float",
        uid="218",
        inputs={"value": 25.0},
        widgets={"widget_0": "25"},
        raw_widgets=RawWidgetPayload(
            values=["25"],
            shape="list",
            source="ui.widgets_values",
            has_dict_rows=False,
            length=1,
        ),
        metadata={
            "input_aliases": ["value"],
            "_ui": {
                "id": 218,
                "type": "Float",
                "pos": [0, 0],
                "size": [180, 60],
                "flags": {},
                "order": 0,
                "mode": 0,
                "properties": {},
                "widgets_values": ["25"],
            },
        },
    )
    return workflow


def test_float_value_write_updates_every_serialized_alias_and_candidate() -> None:
    provider = _PrimitiveProvider()
    edited = apply_edit_cow(
        _float_workflow(),
        SetNodeFieldOp(
            op="set_node_field",
            target=NodeFieldTarget(scope_path="", uid="218", field_path="value"),
            value=24.0,
        ),
        schema_provider=provider,
    )

    node = edited.nodes["218"]
    assert node.inputs["value"] == 24.0
    assert node.widgets["widget_0"] == 24.0
    assert node.raw_widgets is not None
    assert node.raw_widgets.values[0] == 24.0
    source = emit_agent_edit_python(edited)
    assert "value=24.0" in source
    assert "widget_0=" not in source
    candidate = emit_ui_json(edited, schema_provider=provider)
    assert candidate is not None
    assert candidate["nodes"][0]["widgets_values"][0] == 24.0


def test_float_widget_zero_write_updates_named_value() -> None:
    provider = _PrimitiveProvider()
    edited = apply_edit_cow(
        _float_workflow(),
        SetNodeFieldOp(
            op="set_node_field",
            target=NodeFieldTarget(scope_path="", uid="218", field_path="widget_0"),
            value=24,
        ),
        schema_provider=provider,
    )

    assert edited.nodes["218"].inputs["value"] == 24
    assert edited.nodes["218"].widgets["widget_0"] == 24
