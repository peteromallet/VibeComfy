from __future__ import annotations

from vibecomfy.comfy_nodes.agent.candidate_transaction import (
    capture_ingress_schema_snapshot,
)
from vibecomfy.porting.edit._interpret import interpret
from vibecomfy.porting.edit.ops import (
    LinkTargetRef,
    NodeFieldTarget,
    RemoveLinkOp,
    SetNodeFieldOp,
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


def test_observable_cow_rejects_socket_materialization_and_retains_edge() -> None:
    workflow = _target_workflow(socket=True)
    provider = _missing_node_provider(
        {
            "id": "target",
            "type": "MissingNode",
            "properties": {"vibecomfy_uid": "target"},
            "inputs": [{"name": "socket", "type": "IMAGE", "link": 1}],
        }
    )
    operation = SetNodeFieldOp(
        op="set_node_field",
        target=NodeFieldTarget("", "target", "socket"),
        value="literal",
    )

    result = interpret(workflow, (operation,), schema_provider=provider)

    assert result.ok is False
    assert result.statements[0].reason == "missing_touched_schema"
    assert result.workflow.nodes["target"].inputs["socket"] == ["source", 0]
    assert result.workflow.nodes["target"].widgets == {}
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


def _counter_ui(*, node_counter: int = 5, link_counter: int = 3, links=None) -> dict:
    return {
        "last_node_id": node_counter,
        "last_link_id": link_counter,
        "nodes": [],
        "links": [[2, 1, 0, 2, 0, "IMAGE"]] if links is None else links,
    }


def _remove_link_op() -> RemoveLinkOp:
    return RemoveLinkOp(
        op="remove_link",
        target=LinkTargetRef("", "target", "image"),
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
