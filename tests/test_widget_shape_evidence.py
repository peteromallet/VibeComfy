from __future__ import annotations

from typing import Any

from vibecomfy.porting.ui_emitter import (
    WidgetShapeEvidence,
    derive_widget_shape_evidence,
)
from vibecomfy.schema.provider import InputSpec, NodeSchema
from vibecomfy.workflow import RawWidgetPayload, VibeNode


class _Provider:
    def __init__(
        self,
        schemas: dict[str, NodeSchema],
        raw_orders: dict[str, list[str | None]] | None = None,
    ) -> None:
        self._schemas = schemas
        self._raw_orders = raw_orders or {}

    def get_schema(self, class_type: str) -> NodeSchema | None:
        return self._schemas.get(class_type)

    def raw_widget_order(self, class_type: str) -> list[str | None] | None:
        return self._raw_orders.get(class_type)


def _schema(class_type: str, inputs: dict[str, InputSpec]) -> NodeSchema:
    return NodeSchema(
        class_type=class_type,
        pack=None,
        inputs=inputs,
        outputs=[],
        source_provider="test_provider",
        confidence=1.0,
    )


def _evidence(node: VibeNode, provider: _Provider | None) -> WidgetShapeEvidence:
    result = derive_widget_shape_evidence(node, provider)
    assert isinstance(result, WidgetShapeEvidence)
    return result


def test_static_node_counts_raw_candidate_and_schema_widgets() -> None:
    node = VibeNode(
        "1",
        "StaticPrompt",
        inputs={"text": "hello", "steps": 12},
        raw_widgets=RawWidgetPayload(
            values=["hello", 12],
            shape="list",
            source="ui.widgets_values",
            has_dict_rows=False,
            length=2,
        ),
    )
    provider = _Provider(
        {
            "StaticPrompt": _schema(
                "StaticPrompt",
                {"text": InputSpec("STRING"), "steps": InputSpec("INT")},
            )
        }
    )

    evidence = _evidence(node, provider)

    assert evidence.node_id == "1"
    assert evidence.class_type == "StaticPrompt"
    assert evidence.schema_less is False
    assert evidence.provider == "test_provider"
    assert evidence.confidence == 1.0
    assert evidence.raw_widget_count == 2
    assert evidence.candidate_widget_count == 2
    assert evidence.schema_widget_count == 2
    assert evidence.compacted_widget_names == ("text", "steps")
    assert evidence.raw_widget_shape == "list"
    assert evidence.has_dict_rows is False
    assert evidence.overflow is False


def test_schema_less_node_preserves_candidate_count_without_overflow_verdict() -> None:
    node = VibeNode("1", "UnknownDynamic", widgets={"widget_0": "kept"})

    evidence = _evidence(node, _Provider({}))

    assert evidence.schema_less is True
    assert evidence.provider is None
    assert evidence.confidence is None
    assert evidence.raw_widget_count is None
    assert evidence.candidate_widget_count == 1
    assert evidence.schema_widget_count is None
    assert evidence.compacted_widget_names == ()
    assert evidence.raw_widget_shape is None
    assert evidence.has_dict_rows is False
    assert evidence.overflow is False


def test_dict_row_dynamic_node_counts_raw_payload_and_marks_overflow() -> None:
    rows: list[Any] = [
        {"lora": "detail.safetensors", "strength": 0.45},
        {"lora": "style.safetensors", "strength": 0.2},
    ]
    node = VibeNode(
        "7",
        "DynamicRows",
        inputs={"widget_0": rows[0], "widget_1": rows[1]},
        metadata={"_ui": {"widgets_values": rows}},
    )
    provider = _Provider(
        {"DynamicRows": _schema("DynamicRows", {"rows": InputSpec("STRING")})}
    )

    evidence = _evidence(node, provider)

    assert evidence.raw_widget_count == 2
    assert evidence.candidate_widget_count == 2
    assert evidence.schema_widget_count == 1
    assert evidence.raw_widget_shape == "list"
    assert evidence.has_dict_rows is True
    assert evidence.overflow is True


def test_programmatic_widget_overflow_uses_candidate_count_without_raw_payload() -> None:
    node = VibeNode(
        "9",
        "ProgrammaticOverflow",
        widgets={"widget_0": "a", "widget_1": "b", "widget_2": "c"},
    )
    provider = _Provider(
        {
            "ProgrammaticOverflow": _schema(
                "ProgrammaticOverflow",
                {"value": InputSpec("STRING")},
            )
        }
    )

    evidence = _evidence(node, provider)

    assert evidence.raw_widget_count is None
    assert evidence.raw_widget_shape is None
    assert evidence.candidate_widget_count == 3
    assert evidence.schema_widget_count == 1
    assert evidence.has_dict_rows is False
    assert evidence.overflow is True


def test_raw_scalar_widget_overflow_is_not_hidden_by_compacted_candidate_count() -> None:
    node = VibeNode(
        "12",
        "ShrinkingStatic",
        inputs={"first": "a", "second": "b"},
        metadata={"_ui": {"widgets_values": ["a", "b", "c", "d", "e"]}},
    )
    provider = _Provider(
        {
            "ShrinkingStatic": _schema(
                "ShrinkingStatic",
                {"first": InputSpec("STRING"), "second": InputSpec("STRING")},
            )
        }
    )

    evidence = _evidence(node, provider)

    assert evidence.raw_widget_count == 5
    assert evidence.candidate_widget_count == 2
    assert evidence.schema_widget_count == 2
    assert evidence.has_dict_rows is False
    assert evidence.overflow is True
