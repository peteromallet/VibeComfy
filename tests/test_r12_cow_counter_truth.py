from __future__ import annotations

from vibecomfy.comfy_nodes.agent.candidate_transaction import (
    capture_ingress_schema_snapshot,
)
from vibecomfy.porting.edit._interpret import interpret
from vibecomfy.porting.edit.ops import (
    LinkSourceRef,
    LinkTargetRef,
    NodeFieldTarget,
    NodeTarget,
    RemoveLinkOp,
    RemoveNodeOp,
    SetNodeFieldOp,
    UpsertLinkOp,
)
from vibecomfy.porting.emit.ui import guard_exit_ui
from vibecomfy.schema import FrozenSchemaSnapshotProvider
from vibecomfy.workflow import VibeEdge, VibeNode, VibeWorkflow, WorkflowSource


class _NoSchemaProvider:
    def get_schema(self, _class_type: str):
        return None


def _missing_node_provider(raw_node: dict) -> FrozenSchemaSnapshotProvider:
    snapshot = capture_ingress_schema_snapshot(
        schema_provider=_NoSchemaProvider(),
        graph={"nodes": [raw_node], "links": []},
    )
    return FrozenSchemaSnapshotProvider(snapshot)


def _target_workflow(*, socket: bool) -> VibeWorkflow:
    workflow = VibeWorkflow("r12", WorkflowSource("test"))
    workflow.nodes["target"] = VibeNode(
        "target",
        "MissingNode",
        inputs={"socket": ["source", 0]} if socket else {},
        widgets={"literal": 7} if not socket else {},
        uid="target",
    )
    if socket:
        workflow.nodes["source"] = VibeNode("source", "Source", uid="source")
        workflow.edges.append(VibeEdge("source", "IMAGE", "target", "socket"))
    return workflow


def _socket_provider() -> FrozenSchemaSnapshotProvider:
    return _missing_node_provider(
        {
            "id": "target",
            "type": "MissingNode",
            "properties": {"vibecomfy_uid": "target"},
            "inputs": [{"name": "socket", "type": "IMAGE", "link": 1}],
        }
    )


def test_observable_cow_rejects_socket_materialization_and_retains_edge() -> None:
    workflow = _target_workflow(socket=True)
    operation = SetNodeFieldOp(
        op="set_node_field",
        target=NodeFieldTarget("", "target", "socket"),
        value="literal",
    )

    result = interpret(workflow, (operation,), schema_provider=_socket_provider())

    assert result.ok is False
    assert result.statements[0].reason == "missing_touched_schema"
    assert result.workflow.nodes["target"].inputs["socket"] == ["source", 0]
    assert result.workflow.nodes["target"].widgets == {}
    assert result.workflow.edges == [VibeEdge("source", "IMAGE", "target", "socket")]


def test_widget_carrier_cannot_override_connected_socket() -> None:
    workflow = _target_workflow(socket=True)
    workflow.nodes["target"].widgets["socket"] = 3
    operation = SetNodeFieldOp(
        op="set_node_field",
        target=NodeFieldTarget("", "target", "socket"),
        value="literal",
    )

    result = interpret(workflow, (operation,), schema_provider=_socket_provider())

    assert result.ok is False
    assert result.workflow.nodes["target"].widgets["socket"] == 3
    assert result.workflow.edges == [VibeEdge("source", "IMAGE", "target", "socket")]


def test_link_shaped_widget_carrier_cannot_authorize_materialization() -> None:
    workflow = _target_workflow(socket=True)
    workflow.nodes["target"].widgets["socket"] = ["source", 0]
    operation = SetNodeFieldOp(
        op="set_node_field",
        target=NodeFieldTarget("", "target", "socket"),
        value="literal",
    )

    result = interpret(workflow, (operation,), schema_provider=_socket_provider())

    assert result.ok is False
    assert result.workflow.nodes["target"].widgets["socket"] == ["source", 0]
    assert result.workflow.edges == [VibeEdge("source", "IMAGE", "target", "socket")]


def test_observable_cow_batch_keeps_prior_literal_and_socket_edge_atomicity() -> None:
    workflow = _target_workflow(socket=True)
    workflow.nodes["target"].widgets["literal"] = 7
    provider = _missing_node_provider(
        {
            "id": "target",
            "type": "MissingNode",
            "properties": {"vibecomfy_uid": "target"},
            "inputs": [
                {"name": "socket", "type": "IMAGE", "link": 1},
                {"name": "literal", "type": "STRING", "link": None},
            ],
            "widgets_values": [7],
        }
    )
    operations = (
        SetNodeFieldOp("set_node_field", NodeFieldTarget("", "target", "literal"), 8),
        SetNodeFieldOp("set_node_field", NodeFieldTarget("", "target", "socket"), "literal"),
    )

    result = interpret(workflow, operations, schema_provider=provider)

    assert result.ok is False
    assert result.workflow.nodes["target"].widgets["literal"] == 8
    assert result.workflow.nodes["target"].inputs["socket"] == ["source", 0]
    assert result.workflow.edges == [VibeEdge("source", "IMAGE", "target", "socket")]


def test_observable_cow_still_allows_retained_literal_widget() -> None:
    workflow = _target_workflow(socket=False)
    provider = _missing_node_provider(
        {
            "id": "target",
            "type": "MissingNode",
            "properties": {"vibecomfy_uid": "target"},
            "widgets_values": {"literal": 7},
        }
    )
    operation = SetNodeFieldOp(
        op="set_node_field",
        target=NodeFieldTarget("", "target", "literal"),
        value=8,
    )

    result = interpret(workflow, (operation,), schema_provider=provider)

    assert result.ok is True
    assert result.workflow.nodes["target"].widgets["literal"] == 8


def _counter_ui(*, node_counter=5, link_counter=3, links=None, nodes=None) -> dict:
    return {
        "last_node_id": node_counter,
        "last_link_id": link_counter,
        "nodes": [
            {
                "id": 1,
                "type": "Source",
                "properties": {"vibecomfy_uid": "source"},
                "outputs": [{"name": "IMAGE"}],
            },
            {
                "id": 2,
                "type": "Target",
                "properties": {"vibecomfy_uid": "target"},
                "inputs": [{"name": "image"}, {"name": "other"}],
            },
        ]
        if nodes is None
        else nodes,
        "links": [[2, 1, 0, 2, 0, "IMAGE"]] if links is None else links,
    }


def _remove_link_op(target: str = "target", field: str = "image") -> RemoveLinkOp:
    return RemoveLinkOp(
        op="remove_link",
        target=LinkTargetRef("", target, field),
    )


def test_guard_rejects_node_counter_decrease_even_with_link_removal() -> None:
    original = _counter_ui(node_counter=5, link_counter=3)
    candidate = _counter_ui(node_counter=4, link_counter=0, links=[])

    result = guard_exit_ui(original, candidate, (_remove_link_op(),))

    assert result.ok is False
    assert any(
        issue.code == "full_ui_counter_changed_unattributed"
        and (issue.detail or {}).get("field") == "last_node_id"
        for issue in result.diagnostics
    )


def test_guard_allows_link_counter_recompute_only_for_actual_link_removal() -> None:
    original = _counter_ui(node_counter=5, link_counter=3)
    candidate = _counter_ui(node_counter=5, link_counter=0, links=[])

    result = guard_exit_ui(original, candidate, (_remove_link_op(),))

    assert result.ok is True


def test_guard_rejects_link_counter_decrease_without_actual_removal() -> None:
    original = _counter_ui(node_counter=5, link_counter=3)
    candidate = _counter_ui(node_counter=5, link_counter=0)

    result = guard_exit_ui(original, candidate, (_remove_link_op(),))

    assert result.ok is False
    assert any(
        issue.code == "full_ui_counter_changed_unattributed"
        and (issue.detail or {}).get("field") == "last_link_id"
        for issue in result.diagnostics
    )


def test_guard_rejects_link_counter_decrease_to_wrong_topology_value() -> None:
    original = _counter_ui(node_counter=5, link_counter=4)
    candidate = _counter_ui(
        node_counter=5,
        link_counter=1,
        links=[[2, 1, 0, 2, 0, "IMAGE"]],
    )

    result = guard_exit_ui(original, candidate, (_remove_link_op(),))

    assert result.ok is False
    assert any(
        issue.code == "full_ui_counter_changed_unattributed"
        and (issue.detail or {}).get("field") == "last_link_id"
        for issue in result.diagnostics
    )


def test_guard_correlates_sparse_removed_id_to_exact_input_endpoint() -> None:
    original = _counter_ui(
        node_counter=5,
        link_counter=11,
        links=[
            [2, 1, 0, 2, 0, "IMAGE"],
            [10, 1, 0, 2, 1, "IMAGE"],
        ],
    )
    candidate = _counter_ui(
        node_counter=5,
        link_counter=3,
        links=[[2, 1, 0, 2, 0, "IMAGE"]],
    )

    result = guard_exit_ui(original, candidate, (_remove_link_op(field="other"),))

    assert result.ok is True


def test_guard_rejects_unrelated_and_ghost_remove_link_counter_decreases() -> None:
    original = _counter_ui(node_counter=5, link_counter=11)
    candidate = _counter_ui(node_counter=5, link_counter=0, links=[])

    unrelated = guard_exit_ui(original, candidate, (_remove_link_op("source", "image"),))
    ghost = guard_exit_ui(original, candidate, (_remove_link_op("ghost", "image"),))

    assert unrelated.ok is False
    assert ghost.ok is False
    assert any(
        issue.code == "full_ui_counter_changed_unattributed" for issue in unrelated.diagnostics
    )
    assert any(issue.code == "full_ui_counter_changed_unattributed" for issue in ghost.diagnostics)


def test_guard_rejects_remove_node_without_incident_links() -> None:
    nodes = _counter_ui()["nodes"] + [
        {
            "id": 3,
            "type": "Unconnected",
            "properties": {"vibecomfy_uid": "unconnected"},
        }
    ]
    original = _counter_ui(node_counter=5, link_counter=3, nodes=nodes)
    candidate = _counter_ui(
        node_counter=5,
        link_counter=0,
        nodes=nodes[:2],
        links=[],
    )
    operation = RemoveNodeOp("remove_node", NodeTarget("", "unconnected"))

    result = guard_exit_ui(original, candidate, (operation,))

    assert result.ok is False
    assert any(
        issue.code == "full_ui_counter_changed_unattributed" for issue in result.diagnostics
    )
    assert any(issue.code == "full_ui_link_removed_unattributed" for issue in result.diagnostics)


def test_guard_rejects_add_remove_mixture_for_counter_decrease() -> None:
    original = _counter_ui(
        node_counter=5,
        link_counter=11,
        links=[
            [2, 1, 0, 2, 0, "IMAGE"],
            [10, 1, 0, 2, 1, "IMAGE"],
        ],
    )
    candidate = _counter_ui(
        node_counter=5,
        link_counter=6,
        links=[[5, 1, 0, 2, 0, "IMAGE"]],
    )

    result = guard_exit_ui(original, candidate, (_remove_link_op(),))

    assert result.ok is False
    assert any(
        issue.code == "full_ui_counter_changed_unattributed" for issue in result.diagnostics
    )


def test_guard_rejects_malformed_and_arbitrary_materialized_counters() -> None:
    for node_counter, link_counter in ((False, 3), (5, True), (5, -1), (-1, 3)):
        original = _counter_ui()
        candidate = _counter_ui(node_counter=node_counter, link_counter=link_counter)
        result = guard_exit_ui(original, candidate, ())
        assert result.ok is False
        assert any(
            issue.code == "full_ui_counter_changed_unattributed"
            for issue in result.diagnostics
        )

    original = _counter_ui(node_counter=None, link_counter=None)
    candidate = _counter_ui(node_counter=99, link_counter=99)
    result = guard_exit_ui(original, candidate, ())
    assert result.ok is False


def test_guard_allows_remove_node_only_for_all_incident_links() -> None:
    original = _counter_ui(node_counter=5, link_counter=3)
    candidate = _counter_ui(node_counter=5, link_counter=0, nodes=[original["nodes"][0]], links=[])
    operation = RemoveNodeOp("remove_node", NodeTarget("", "target"))

    result = guard_exit_ui(original, candidate, (operation,))

    assert result.ok is True


def test_guard_does_not_suppress_unrelated_repoint_with_link_operation() -> None:
    original = _counter_ui(node_counter=5, link_counter=3)
    candidate = _counter_ui(
        node_counter=5,
        link_counter=3,
        links=[[2, 1, 0, 2, 1, "IMAGE"]],
    )
    operation = UpsertLinkOp(
        "upsert_link",
        LinkSourceRef("", "source", "IMAGE"),
        LinkTargetRef("", "target", "image"),
    )

    result = guard_exit_ui(original, candidate, (operation,))

    assert result.ok is False
    assert any(issue.code == "full_ui_link_changed_unattributed" for issue in result.diagnostics)
