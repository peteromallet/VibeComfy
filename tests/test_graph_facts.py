from __future__ import annotations

from copy import deepcopy

from vibecomfy.executor.graph_facts import (
    GraphFieldTarget,
    compare_effective_field,
    inspect_effective_field,
    widget_field_name_for_index,
)


def _linked_steps_graph(*, raw_steps: int = 20, source_value: int = 77) -> dict:
    return {
        "nodes": [
            {
                "id": 1,
                "type": "PrimitiveInt",
                "class_type": "PrimitiveInt",
                "widgets_values": [source_value],
                "outputs": [{"name": "INT", "type": "INT", "links": [10]}],
            },
            {
                "id": 2,
                "type": "KSampler",
                "class_type": "KSampler",
                "widgets_values": [123, "fixed", raw_steps, 7.0, "euler", "normal", 1.0],
                "inputs": [
                    {"name": "steps", "type": "INT", "widget": {"name": "steps"}, "link": 10},
                ],
            },
        ],
        "links": [
            [10, 1, 0, 2, 0, "INT"],
        ],
    }


def _linked_steps_graph_with_control_widget(*, source_value: int = 77) -> dict:
    graph = _linked_steps_graph(source_value=source_value)
    graph["nodes"][0]["widgets_values"] = [source_value, "fixed"]
    return graph


def test_widget_index_resolves_field_name_and_current_value() -> None:
    graph = {
        "nodes": [
            {
                "id": 2,
                "type": "KSampler",
                "class_type": "KSampler",
                "widgets_values": [123, "fixed", 20, 7.0, "euler", "normal", 1.0],
            },
        ],
    }

    assert widget_field_name_for_index(graph, 2, 2) == "steps"

    fact = inspect_effective_field(graph, GraphFieldTarget(node_id=2, field_name="steps", widget_index=2))
    assert fact.field_name == "steps"
    assert fact.widget_index == 2
    assert fact.raw_value == 20
    assert fact.raw_value_known is True
    assert fact.effective_value == 20
    assert fact.effective_value_known is True
    assert fact.overridden is False
    assert fact.inert_static_edit is False


def test_static_widget_is_overridden_and_inert_when_semantic_input_is_linked() -> None:
    graph = _linked_steps_graph()

    fact = inspect_effective_field(graph, GraphFieldTarget(node_id=2, field_name="steps", widget_index=2))

    assert fact.field_name == "steps"
    assert fact.raw_value == 20
    assert fact.overridden is True
    assert fact.inert_static_edit is True
    assert fact.link_id == 10


def test_linked_source_value_is_resolved_for_simple_constant_widget_node() -> None:
    graph = _linked_steps_graph(source_value=77)

    fact = inspect_effective_field(graph, GraphFieldTarget(node_id=2, field_name="steps", widget_index=2))

    assert fact.effective_value == 77
    assert fact.effective_value_known is True
    assert fact.source is not None
    assert fact.source.node_id == 1
    assert fact.source.class_type == "PrimitiveInt"
    assert fact.source.field_name == "value"
    assert fact.source.widget_index == 0
    assert fact.source.value == 77
    assert fact.source.value_known is True
    assert fact.source.outgoing_link_count == 1


def test_linked_source_value_is_resolved_for_primitive_with_control_widget() -> None:
    graph = _linked_steps_graph_with_control_widget(source_value=77)

    fact = inspect_effective_field(graph, GraphFieldTarget(node_id=2, field_name="steps", widget_index=2))

    assert fact.effective_value == 77
    assert fact.effective_value_known is True
    assert fact.source is not None
    assert fact.source.field_name == "value"
    assert fact.source.widget_index == 0
    assert fact.source.value_source == "primitive_widget_value"


def test_linked_source_reports_shared_output_fanout() -> None:
    graph = _linked_steps_graph(source_value=77)
    graph["nodes"].append(
        {
            "id": 3,
            "type": "OtherConsumer",
            "class_type": "OtherConsumer",
            "widgets_values": [0],
            "inputs": [
                {"name": "count", "type": "INT", "widget": {"name": "count"}, "link": 11},
            ],
        }
    )
    graph["links"].append([11, 1, 0, 3, 0, "INT"])

    fact = inspect_effective_field(graph, GraphFieldTarget(node_id=2, field_name="steps", widget_index=2))

    assert fact.source is not None
    assert fact.source.outgoing_link_count == 2


def test_linked_source_follows_single_reroute_passthrough() -> None:
    graph = _linked_steps_graph_with_control_widget(source_value=77)
    graph["nodes"].insert(
        1,
        {
            "id": 3,
            "type": "Reroute",
            "class_type": "Reroute",
            "inputs": [{"name": "", "type": "*", "link": 9}],
            "outputs": [{"name": "", "type": "*", "links": [10]}],
            "widgets_values": [],
        },
    )
    graph["links"] = [
        [9, 1, 0, 3, 0, "*"],
        [10, 3, 0, 2, 0, "INT"],
    ]

    fact = inspect_effective_field(graph, GraphFieldTarget(node_id=2, field_name="steps", widget_index=2))

    assert fact.effective_value == 77
    assert fact.effective_value_known is True
    assert fact.source is not None
    assert fact.source.node_id == 1
    assert fact.source.class_type == "PrimitiveInt"
    assert fact.source.outgoing_link_count == 1


def test_linked_source_value_is_unknown_for_non_primitive_single_input_node() -> None:
    graph = {
        "nodes": [
            {
                "id": 1,
                "type": "VideoGenerator",
                "class_type": "VideoGenerator",
                "inputs": {"duration": 8},
                "outputs": [{"name": "VIDEO", "type": "VIDEO", "links": [10]}],
            },
            {
                "id": 2,
                "type": "VideoCombine",
                "class_type": "VideoCombine",
                "widgets_values": [0],
                "inputs": [
                    {"name": "frame_count", "type": "INT", "widget": {"name": "frame_count"}, "link": 10},
                ],
            },
        ],
        "links": [
            [10, 1, 0, 2, 0, "VIDEO"],
        ],
    }

    fact = inspect_effective_field(graph, GraphFieldTarget(node_id=2, widget_index=0))

    assert fact.overridden is True
    assert fact.effective_value_known is False
    assert fact.source is not None
    assert fact.source.class_type == "VideoGenerator"
    assert fact.source.value_known is False
    assert fact.source.value_source == "source_not_known_constant"


def test_effective_comparison_ignores_overridden_static_widget_change() -> None:
    before = _linked_steps_graph_with_control_widget(source_value=77)
    before["nodes"][1]["widgets_values"][2] = 20
    after = deepcopy(before)
    after["nodes"][1]["widgets_values"][2] = 25

    change = compare_effective_field(
        before,
        after,
        GraphFieldTarget(node_id=2, field_name="steps", widget_index=2),
    )

    assert change.before.raw_value == 20
    assert change.after.raw_value == 25
    assert change.raw_changed is True
    assert change.before.effective_value == 77
    assert change.after.effective_value == 77
    assert change.effective_changed is False
