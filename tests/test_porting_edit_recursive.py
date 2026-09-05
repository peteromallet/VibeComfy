from __future__ import annotations

import pytest

from vibecomfy.identity.scope import sg_key
from vibecomfy.porting.edit._diff import diff
from vibecomfy.porting.edit.apply_gate import editable_signature, verify_apply
from vibecomfy.porting.edit._interpret import interpret
from vibecomfy.porting.edit._ir_utils import (
    RecursiveEditError,
    apply_edit_cow,
    build_recursive_edit_index,
)
from vibecomfy.porting.edit.ops import (
    AddNodeOp,
    AnchorRef,
    DELTA_DIAGNOSTIC_UNSUPPORTED_SCOPED_APPLY,
    EditOpParseError,
    ensure_root_scoped_delta_envelope,
    LinkSourceRef,
    LinkTargetRef,
    NodeFieldTarget,
    NodeTarget,
    RemoveLinkOp,
    RemoveNodeOp,
    SetModeOp,
    SetNodeFieldOp,
    SubgraphInterfaceOp,
    UpsertLinkOp,
)
from vibecomfy.porting.edit.session import EditSession
from vibecomfy.workflow import VibeEdge, VibeNode, VibeWorkflow, WorkflowCompileError, WorkflowSource


def _workflow() -> tuple[VibeWorkflow, str, str]:
    inner = {
        "name": "Inner",
        "nodes": [
            {"id": 2, "uid": "inner_i", "type": "Get", "inputs": [], "widgets_values": [1], "outputs": [], "mode": 0, "metadata": {"provenance": "untrusted_source"}},
            {"id": 3, "uid": "inner_i2", "type": "Set", "inputs": [{"name": "value", "type": "INT", "link": None, "value": 0}], "outputs": [], "mode": 0},
            {"id": 4, "uid": "inner_r", "type": "Reroute", "inputs": [], "outputs": []},
        ],
        "links": [[1, 2, 0, 3, 0, "VALUE"], [2, 2, 0, 4, 0, "VALUE"], [3, 4, 0, 3, 0, "VALUE"]],
    }
    outer = {
        "name": "Outer",
        "nodes": [{"id": 1, "uid": "outer_o", "type": "Reroute", "inputs": [], "outputs": []}],
        "links": [],
        "definitions": {"subgraphs": [inner]},
    }
    inner_key = sg_key(inner)
    outer["nodes"].extend(
        [
            {"id": 5, "uid": "occ_a", "type": inner_key, "inputs": [], "outputs": []},
            {"id": 6, "uid": "occ_b", "type": inner_key, "inputs": [], "outputs": []},
        ]
    )
    workflow = VibeWorkflow(
        "recursive",
        WorkflowSource(id="recursive"),
        definitions={"subgraphs": [outer]},
        boundary_ports=[],
        virtual_wires={},
    )
    return workflow, sg_key(outer), f"{sg_key(outer)}/{inner_key}"


def _valid_execution_workflow() -> tuple[VibeWorkflow, str, str]:
    """Depth-2 definition with authored Get/Set/Reroute fan-out.

    Unlike the small identity fixture above, this one has a root occurrence,
    typed interface/boundary bindings, and native port rosters so compile and
    UI materialization are both positive proofs.
    """
    inner = {
        "id": "inner",
        "name": "Inner",
        "nodes": [
            {
                "id": "inner_src",
                "uid": "inner_src",
                "type": "Get",
                "inputs": [{"name": "value", "type": "IMAGE", "link": None, "value": None}],
                "outputs": [{"name": "out", "type": "IMAGE"}],
            },
            {
                "id": "inner_core",
                "uid": "inner_core",
                "type": "EchoImage",
                "inputs": [{"name": "in", "type": "IMAGE", "link": None, "value": None}],
                "widgets_values": [1],
                "outputs": [{"name": "out", "type": "IMAGE"}],
                "mode": 0,
            },
            {
                "id": "inner_r",
                "uid": "inner_r",
                "type": "Reroute",
                "inputs": [{"name": "in", "type": "IMAGE", "link": None, "value": None}],
                "outputs": [{"name": "out", "type": "IMAGE"}],
            },
            {
                "id": "inner_set",
                "uid": "inner_set",
                "type": "Set",
                "inputs": [{"name": "in", "type": "IMAGE", "link": None, "value": None}],
                "outputs": [],
            },
        ],
        "links": [
            [1, "inner_src", 0, "inner_core", 0, "IMAGE"],
            [2, "inner_src", 0, "inner_r", 0, "IMAGE"],
            [3, "inner_src", 0, "inner_set", 0, "IMAGE"],
        ],
    }
    inner_key = sg_key(inner)
    outer = {
        "id": "outer",
        "name": "Outer",
        "nodes": [{"id": "inner_occ", "uid": "inner_occ", "type": inner_key, "inputs": [], "outputs": []}],
        "links": [],
        "definitions": {"subgraphs": [inner]},
    }
    outer_key = sg_key(outer)

    def source(node_id: str) -> VibeNode:
        return VibeNode(
            node_id,
            "Source",
            uid=node_id,
            native_output_names=["out"],
            metadata={"output_names": ["out"], "output_types": ["IMAGE"]},
        )

    def occurrence(node_id: str) -> VibeNode:
        return VibeNode(
            node_id,
            outer_key,
            uid=node_id,
            native_input_names=["input"],
            native_output_names=["output"],
            metadata={"input_types": ["IMAGE"], "output_types": ["IMAGE"]},
        )

    sink = VibeNode(
        "sink",
        "Sink",
        uid="sink",
        inputs={"image": None},
        native_input_names=["image"],
        metadata={"input_types": {"image": "IMAGE"}},
    )
    workflow = VibeWorkflow(
        "recursive-execution",
        WorkflowSource(id="recursive-execution"),
        nodes={"source": source("source"), "outer": occurrence("outer"), "sink": sink},
        edges=[
            VibeEdge("source", "out", "outer", "input"),
            VibeEdge("outer", "output", "sink", "image"),
        ],
        definitions={"subgraphs": [outer]},
        interfaces={
            outer_key: {
                "inputs": [{"name": "input", "direction": "input", "type": "IMAGE"}],
                "outputs": [{"name": "output", "direction": "output", "type": "IMAGE"}],
            },
            inner_key: {
                "inputs": [{"name": "input", "direction": "input", "type": "IMAGE"}],
                "outputs": [{"name": "output", "direction": "output", "type": "IMAGE"}],
            },
        },
        boundary_ports=[
            {"scope_path": outer_key, "name": "input", "direction": "input", "node_uid": "inner_occ", "field": "input"},
            {"scope_path": outer_key, "name": "output", "direction": "output", "node_uid": "inner_occ", "field": "output"},
            {"scope_path": inner_key, "name": "input", "direction": "input", "node_uid": "inner_src", "field": "value"},
            {"scope_path": inner_key, "name": "output", "direction": "output", "node_uid": "inner_core", "field": "out"},
        ],
    )
    return workflow, f"{outer_key}/{inner_key}", outer_key


def test_depth_two_index_uses_live_typed_references_and_cow() -> None:
    workflow, _outer, inner = _workflow()
    inner_definition = workflow.definitions["subgraphs"][0]["definitions"]["subgraphs"][0]
    inner_key = sg_key(inner_definition)
    index = build_recursive_edit_index(workflow)
    ref = index.node(inner, "inner_i")
    assert ref.node is workflow.definitions["subgraphs"][0]["definitions"]["subgraphs"][0]["nodes"][0]

    post = apply_edit_cow(workflow, SetNodeFieldOp("set_node_field", NodeFieldTarget(inner, "inner_i", "widget_0"), 2))
    post = apply_edit_cow(post, SetModeOp("set_mode", NodeTarget(inner, "inner_i"), 2))
    assert workflow.definitions["subgraphs"][0]["definitions"]["subgraphs"][0]["nodes"][0]["widgets_values"] == [1]
    node = post.definitions["subgraphs"][0]["definitions"]["subgraphs"][0]["nodes"][0]
    assert node["widgets_values"] == [2] and node["mode"] == 2
    assert sg_key(post.definitions["subgraphs"][0]["definitions"]["subgraphs"][0]) == inner_key


def test_recursive_definition_occurrences_keep_distinct_uids() -> None:
    workflow, outer, _inner = _workflow()
    scope = build_recursive_edit_index(workflow).scope(outer)
    assert {"occ_a", "occ_b"}.issubset(scope.nodes)
    assert scope.nodes["occ_a"].uid != scope.nodes["occ_b"].uid


def test_recursive_index_preserves_two_occurrences_fanout_and_typed_carriers() -> None:
    workflow, inner, outer = _valid_execution_workflow()
    index = build_recursive_edit_index(workflow)
    assert "inner_occ" in index.scope(outer).nodes
    assert set(index.scope(inner).nodes) == {"inner_src", "inner_core", "inner_r", "inner_set"}
    assert index.node(inner, "inner_core").node is workflow.definitions["subgraphs"][0]["definitions"]["subgraphs"][0]["nodes"][1]
    before_api = workflow.compile("api")
    before_projection = workflow._execution_projection()
    before_fanout = sum(
        1 for edge in before_projection.edges
        if edge.from_node.endswith("#inner_src")
    )
    post = apply_edit_cow(
        workflow,
        SetNodeFieldOp("set_node_field", NodeFieldTarget(inner, "inner_core", "widget_0"), 7),
    )
    post = apply_edit_cow(
        post,
        SetModeOp("set_mode", NodeTarget(inner, "inner_r"), 2),
    )
    after_projection = post._execution_projection()
    after_fanout = sum(
        1 for edge in after_projection.edges
        if edge.from_node.endswith("#inner_src")
    )
    after_api = post.compile("api")
    assert set(after_api) == set(before_api)
    assert {
        node_id: {key: value for key, value in node["inputs"].items() if key != "widget_0"}
        for node_id, node in after_api.items()
    } == {
        node_id: {key: value for key, value in node["inputs"].items() if key != "widget_0"}
        for node_id, node in before_api.items()
    }
    assert after_fanout == before_fanout == 2
    assert len(after_projection.edges) == len(before_projection.edges)
    from vibecomfy.porting.emit.ui import materialize_ui_json

    materialized = materialize_ui_json(post)
    assert materialized["definitions"]["subgraphs"]
    assert len(materialized["definitions"]["subgraphs"][0]["definitions"]["subgraphs"][0]["links"]) == 3
    assert post.boundary_ports == workflow.boundary_ports
    assert post.virtual_wires == workflow.virtual_wires
    assert len(workflow._execution_projection().edges) == len(before_projection.edges)


def test_recursive_diff_interpret_and_session_rollback_are_replayable() -> None:
    workflow, _outer, inner = _workflow()
    post = workflow.copy()
    node = post.definitions["subgraphs"][0]["definitions"]["subgraphs"][0]["nodes"][0]
    node["widgets_values"][0], node["mode"] = 3, 2
    delta = diff(workflow, post)
    replay = interpret(workflow, delta)
    assert replay.ok and replay.workflow.semantic_projection() == post.semantic_projection()

    session = EditSession({}, initial_workflow=workflow)
    result = session.apply_ops((SetModeOp("set_mode", NodeTarget(inner, "inner_i"), 2),))
    assert result.ok and session.touched_uids == {f"{inner}#inner_i"}
    field_result = session.apply_ops(
        (SetNodeFieldOp("set_node_field", NodeFieldTarget(inner, "inner_i", "widget_0"), 9),),
        expected_revision=1,
    )
    assert field_result.ok and session.revision == 2
    session.verify_delta_history()
    assert session.rollback() and session.revision == 3
    assert session.workflow.semantic_projection() != workflow.semantic_projection()
    assert session.rollback() and session.revision == 4
    assert session.workflow.semantic_projection() == workflow.semantic_projection()


def test_recursive_apply_gate_sees_typed_delta_and_empty_noop() -> None:
    workflow, _outer, inner = _workflow()
    post = workflow.copy()
    post.definitions["subgraphs"][0]["definitions"]["subgraphs"][0]["nodes"][0]["mode"] = 2
    assert editable_signature(workflow) != editable_signature(post)
    gate = verify_apply(workflow, post, landed_ops=diff(workflow, post))
    assert gate.ok and gate.apply_eligible
    noop = verify_apply(workflow, workflow, landed_ops=diff(workflow, workflow))
    assert noop.ok and not noop.apply_eligible and noop.reason == "empty_delta"

    renumbered = workflow.copy()
    inner_definition = renumbered.definitions["subgraphs"][0]["definitions"]["subgraphs"][0]
    renumbered_links = []
    for link in reversed(inner_definition["links"]):
        item = list(link)
        item[0] = int(item[0]) + 100
        renumbered_links.append(item)
    inner_definition["links"] = renumbered_links
    assert editable_signature(workflow) == editable_signature(renumbered)

    changed_topology = workflow.copy()
    changed_definition = changed_topology.definitions["subgraphs"][0]["definitions"]["subgraphs"][0]
    changed_definition["links"][0] = [1, 2, 0, 4, 0, "OTHER"]
    structural = verify_apply(
        workflow,
        changed_topology,
        landed_ops=(SetModeOp("set_mode", NodeTarget(inner, "inner_i"), 2),),
    )
    assert not structural.ok and structural.reason == "unsupported_structural_scope"

    for changed_link in (
        [1, 2, 1, 3, 0, "VALUE"],
        [1, 2, 0, 3, 1, "VALUE"],
    ):
        changed_endpoint = workflow.copy()
        changed_endpoint.definitions["subgraphs"][0]["definitions"]["subgraphs"][0]["links"][0] = changed_link
        structural = verify_apply(
            workflow,
            changed_endpoint,
            landed_ops=(SetModeOp("set_mode", NodeTarget(inner, "inner_i"), 2),),
        )
        assert not structural.ok and structural.reason == "unsupported_structural_scope"


def test_recursive_cycle_is_rejected_by_identity_and_apply_gate() -> None:
    workflow, _outer, _inner = _workflow()
    inner_definition = workflow.definitions["subgraphs"][0]["definitions"]["subgraphs"][0]
    inner_definition["definitions"] = {"subgraphs": [inner_definition]}
    with pytest.raises(RecursiveEditError) as error:
        build_recursive_edit_index(workflow)
    assert error.value.code == "recursive_definition_cycle"
    gate = verify_apply(workflow, workflow)
    assert not gate.ok and gate.reason == "unverifiable_identity"


def test_root_only_edit_evidence_is_explicitly_insufficient_for_recursive_ag06() -> None:
    root = VibeWorkflow(
        "root-only",
        WorkflowSource(id="root-only"),
        nodes={"n": VibeNode("n", "Source", uid="n")},
    )
    recursive_component = editable_signature(root)[3]
    assert recursive_component[:3] == ((), (), ())
    assert all(not part for part in recursive_component[:3]), "root-only evidence cannot satisfy recursive AG-06"
    assert {name for name, _value in recursive_component[3]} == {
        "interfaces", "boundary_ports", "virtual_wires", "groups"
    }


def test_sg_ordinal_paths_are_guard_only_and_never_edit_scope_identity() -> None:
    workflow, _outer, inner = _workflow()
    operation = SetModeOp("set_mode", NodeTarget(inner, "inner_i"), 2)
    projected = EditSession._guard_ops_for_ui(workflow, (operation,))[0]
    assert projected.target.scope_path == "sg0/sg0"
    with pytest.raises(RuntimeError, match="capture.*port through canonical Python.*reopen/reload"):
        EditSession({}, initial_workflow=workflow).node_ui("inner_i", inner)
    assert operation.target.scope_path == inner
    with pytest.raises(RecursiveEditError) as error:
        build_recursive_edit_index(workflow).scope(projected.target.scope_path)
    assert error.value.code in {"invalid_scope", "scope_unknown"}


def test_recursive_qualified_endpoint_fails_closed() -> None:
    workflow, _outer, _inner = _workflow()
    definition = workflow.definitions["subgraphs"][0]["definitions"]["subgraphs"][0]
    definition["links"][0][3] = "outer/inner_i2"
    with pytest.raises(RecursiveEditError) as error:
        build_recursive_edit_index(workflow)
    assert error.value.code == "unknown_target"


def test_recursive_clone_collision_and_native_boundary_fail_closed() -> None:
    workflow, _outer, _inner = _workflow()
    clone = workflow.definitions["subgraphs"][0]["definitions"]["subgraphs"][0].copy()
    workflow.definitions["subgraphs"].append(clone)
    with pytest.raises(RecursiveEditError, match="duplicate definition"):
        build_recursive_edit_index(workflow)

    sentinel, _outer, _inner = _workflow()
    definition = sentinel.definitions["subgraphs"][0]
    definition["links"] = [[1, -10, 0, "outer_o", 0, "X"]]
    with pytest.raises(RecursiveEditError) as error:
        build_recursive_edit_index(sentinel)
    assert error.value.code == "unsupported_boundary_encoding"
    for carrier in ("inputs", "outputs"):
        bad = _workflow()[0]
        bad_node = bad.definitions["subgraphs"][0]["definitions"]["subgraphs"][0]["nodes"][0]
        bad_node[carrier] = [{"name": "value", "link": -10}]
        with pytest.raises(RecursiveEditError) as error:
            build_recursive_edit_index(bad)
        assert error.value.code == "unsupported_boundary_encoding"
    bad_boundary = _valid_execution_workflow()[0]
    bad_boundary.boundary_ports[0] = {
        **bad_boundary.boundary_ports[0], "node_uid": "missing"
    }
    with pytest.raises(RecursiveEditError) as error:
        build_recursive_edit_index(bad_boundary)
    assert error.value.code in {"boundary_port_unresolved", "boundary_port_missing"}
    bad_wire = _valid_execution_workflow()[0]
    bad_wire.virtual_wires = {
        "wire": {"legs": [{
            "scope_path": _valid_execution_workflow()[2],
            "leg_index": 0, "occurrence_index": 0,
            "from_node": "missing", "from_output": 0,
            "to_node": "inner_core", "to_input": "in",
        }]}
    }
    with pytest.raises(RecursiveEditError) as error:
        build_recursive_edit_index(bad_wire)
    assert error.value.code == "virtual_wire_unresolved"

    malformed = _workflow()[0]
    malformed.definitions["subgraphs"].append(
        malformed.definitions["subgraphs"][0]["definitions"]["subgraphs"][0].copy()
    )
    gate = verify_apply(malformed, malformed, landed_ops=())
    assert not gate.ok and gate.reason == "unverifiable_identity"
    assert gate.diagnostics[0].code == "apply_gate_unverifiable_identity"
    assert "capture -> port through canonical Python -> reopen/reload" in gate.diagnostics[0].message


@pytest.mark.parametrize(
    "operation",
    [
        lambda scope: AddNodeOp("add_node", scope, "Foo", {}, {}),
        lambda scope: RemoveNodeOp("remove_node", NodeTarget(scope, "inner_i")),
        lambda scope: UpsertLinkOp(
            "upsert_link",
            LinkSourceRef(scope, "inner_i", 0),
            LinkTargetRef(scope, "inner_i2", "value"),
        ),
        lambda scope: RemoveLinkOp("remove_link", target=LinkTargetRef(scope, "inner_i2", "value")),
        lambda scope: SubgraphInterfaceOp(
            "subgraph_interface", "change", "Inner", scope_path=scope
        ),
    ],
)
def test_recursive_structural_matrix_fails_before_session_mutation(operation) -> None:
    workflow, _outer, inner = _workflow()
    before = workflow.semantic_projection()
    session = EditSession({}, initial_workflow=workflow)
    result = session.apply_ops((operation(inner),))
    assert not result.ok and result.reason == "unsupported_structural_scope"
    assert result.revision == 0 and session.revision == 0
    assert session.workflow.semantic_projection() == before


def test_recursive_structural_edits_fail_before_mutation() -> None:
    workflow, outer, _inner = _workflow()
    before = workflow.definitions
    operations = (
        AddNodeOp("add_node", outer, "New", {}, {}),
        RemoveNodeOp("remove_node", NodeTarget(outer, "outer_o")),
        UpsertLinkOp("upsert_link", LinkSourceRef(outer, "outer_o", 0), LinkTargetRef(outer, "outer_o", "value")),
    )
    for operation in operations:
        with pytest.raises(RecursiveEditError) as error:
            apply_edit_cow(workflow, operation)
        assert error.value.code == "unsupported_structural_scope"
        assert workflow.definitions == before
    grouped = AddNodeOp(
        "add_node", "", "New", {}, {},
        anchor=AnchorRef("near", group_title="unsupported"),
    )
    with pytest.raises(RecursiveEditError) as error:
        apply_edit_cow(workflow, grouped)
    assert error.value.code == "unsupported_operation"


@pytest.mark.parametrize("nested_ref", ["input", "anchor"])
def test_nested_add_node_refs_are_rejected_by_scope_precheck(nested_ref: str) -> None:
    workflow, _outer, inner = _workflow()
    kwargs = {
        "inputs": {
            "value": LinkSourceRef(inner, "inner_i", "widget_0")
        }
        if nested_ref == "input"
        else {},
        "anchor": (
            AnchorRef("near", near=NodeTarget(inner, "inner_i"))
            if nested_ref == "anchor"
            else None
        ),
    }
    result = EditSession({}, initial_workflow=workflow).apply_ops(
        (AddNodeOp("add_node", "", "Foo", {}, **kwargs),)
    )
    assert not result.ok and result.reason == "unsupported_structural_scope"


def test_recursive_scope_inputs_fail_closed_for_ordinal_unknown_mixed_stale_and_live() -> None:
    workflow, _outer, inner = _workflow()
    for scope in ("sg0", "unknown_scope"):
        session = EditSession({}, initial_workflow=workflow)
        result = session.apply_ops((SetModeOp("set_mode", NodeTarget(scope, "inner_i"), 2),))
        assert not result.ok and result.reason in {"invalid_scope", "scope_unknown"}
        assert session.revision == 0

    mixed = EditSession({}, initial_workflow=workflow)
    mixed_result = mixed.apply_ops(
        (
            SetModeOp("set_mode", NodeTarget(inner, "inner_i"), 2),
            SetModeOp("set_mode", NodeTarget("", "missing"), 2),
        )
    )
    assert not mixed_result.ok and mixed_result.reason == "unsupported_structural_scope"
    stale = EditSession({}, initial_workflow=workflow)
    assert stale.apply_ops((SetModeOp("set_mode", NodeTarget(inner, "inner_i"), 2),), expected_revision=0).ok
    stale_result = stale.apply_ops((SetModeOp("set_mode", NodeTarget(inner, "inner_i2"), 2),), expected_revision=0)
    assert not stale_result.ok and stale_result.reason == "stale_revision"

    metadata_workflow, _outer, metadata_inner = _workflow()
    metadata_node = metadata_workflow.definitions["subgraphs"][0]["definitions"]["subgraphs"][0]["nodes"][0]
    metadata_node["metadata"] = {"raw_only": 1}
    raw_edit = EditSession({}, initial_workflow=metadata_workflow).apply_ops(
        (SetNodeFieldOp("set_node_field", NodeFieldTarget(metadata_inner, "inner_i", "raw_only"), 2),)
    )
    assert not raw_edit.ok and raw_edit.reason == "unknown_field"


def test_recursive_live_delta_consumers_and_root_interface_law_are_fenced() -> None:
    _workflow_value, _outer, inner = _workflow()
    with pytest.raises(EditOpParseError) as error:
        ensure_root_scoped_delta_envelope(
            {
                "schema_version": "2.0.0",
                "ops": [
                    {
                        "op": "set_mode",
                        "target": [inner, "inner_i"],
                        "mode": 2,
                    }
                ],
            }
        )
    assert error.value.code == DELTA_DIAGNOSTIC_UNSUPPORTED_SCOPED_APPLY
    message = str(error.value)
    assert "capture" in message and "port through canonical Python" in message
    assert "reopen/reload" in message
    for add in (
        {
            "op": "add_node", "scope_path": "", "uid": "new", "node_id": "new",
            "class_type": "Foo", "fields": {},
            "inputs": {"value": [inner, "inner_i", 0]},
        },
        {
            "op": "add_node", "scope_path": "", "uid": "new", "node_id": "new",
            "class_type": "Foo", "fields": {},
            "inputs": {},
            "anchor": {
                "relation": "between",
                "between": [[inner, "inner_i"], [inner, "inner_i2"]],
            },
        },
    ):
        with pytest.raises(EditOpParseError) as nested_error:
            ensure_root_scoped_delta_envelope({"schema_version": "2.0.0", "ops": [add]})
        assert nested_error.value.code == DELTA_DIAGNOSTIC_UNSUPPORTED_SCOPED_APPLY

    pre = VibeWorkflow(
        "metadata-interface",
        WorkflowSource(id="metadata-interface"),
        metadata={
            "definitions": {
                "subgraphs": [
                    {
                        "id": "sg-root",
                        "name": "Root",
                        "inputs": [{"name": "in", "type": "IMAGE"}],
                        "outputs": [],
                        "nodes": [],
                        "links": [],
                    }
                ]
            }
        },
    )
    post = pre.copy()
    post.metadata["definitions"]["subgraphs"][0]["inputs"] = [{"name": "edited", "type": "IMAGE"}]
    delta = diff(pre, post)
    assert len(delta) == 1 and isinstance(delta[0], SubgraphInterfaceOp)
    replay = interpret(pre, delta)
    assert replay.ok
    assert replay.workflow.interfaces == {}
    assert replay.workflow.metadata["definitions"]["subgraphs"][0]["inputs"][0]["name"] == "edited"


def test_recursive_list_input_and_widget_channels_are_shared_edit_fields() -> None:
    workflow, _outer, inner = _workflow()
    node = workflow.definitions["subgraphs"][0]["definitions"]["subgraphs"][0]["nodes"][0]
    node["inputs"] = [{"name": "value", "type": "INT", "link": None, "value": 1}]
    node["widgets_values"] = ["before"]
    outer_definition = workflow.definitions["subgraphs"][0]
    inner_definition = outer_definition["definitions"]["subgraphs"][0]
    inner = f"{sg_key(outer_definition)}/{sg_key(inner_definition)}"
    post = apply_edit_cow(
        workflow,
        SetNodeFieldOp("set_node_field", NodeFieldTarget(inner, "inner_i", "value"), 4),
    )
    post = apply_edit_cow(
        post,
        SetNodeFieldOp("set_node_field", NodeFieldTarget(inner, "inner_i", "widget_0"), "after"),
    )
    edited = post.definitions["subgraphs"][0]["definitions"]["subgraphs"][0]["nodes"][0]
    assert edited["inputs"][0]["value"] == 4
    assert edited["widgets_values"] == ["after"]
    session = EditSession({}, initial_workflow=workflow)
    result = session.apply_ops((
        SetNodeFieldOp("set_node_field", NodeFieldTarget(inner, "inner_i", "value"), 8),
    ))
    assert result.ok
    assert session.workflow.definitions["subgraphs"][0]["definitions"]["subgraphs"][0]["nodes"][0]["inputs"][0]["value"] == 8


def test_recursive_provenance_is_monotone_without_raw_metadata_authority() -> None:
    workflow, _outer, inner = _workflow()
    node = workflow.definitions["subgraphs"][0]["definitions"]["subgraphs"][0]["nodes"][0]
    node["metadata"] = {"provenance": "user_confirmed"}
    post = apply_edit_cow(
        workflow,
        SetModeOp("set_mode", NodeTarget(inner, "inner_i"), 2),
    )
    assert node["metadata"]["provenance"] == "user_confirmed"
    assert str(post.definitions["subgraphs"][0]["definitions"]["subgraphs"][0]["nodes"][0]["metadata"]["provenance"]) == "Provenance.AGENT_GENERATED"

    absent_workflow, _outer, absent_inner = _workflow()
    absent_node = absent_workflow.definitions["subgraphs"][0]["definitions"]["subgraphs"][0]["nodes"][1]
    assert "metadata" not in absent_node
    absent_post = apply_edit_cow(
        absent_workflow,
        SetModeOp("set_mode", NodeTarget(absent_inner, "inner_i2"), 2),
    )
    assert absent_post.definitions["subgraphs"][0]["definitions"]["subgraphs"][0]["nodes"][1]["metadata"]["provenance"]
    absent_session = EditSession({}, initial_workflow=absent_workflow)
    absent_result = absent_session.apply_ops(
        (SetModeOp("set_mode", NodeTarget(absent_inner, "inner_i2"), 2),)
    )
    assert absent_result.ok
    assert absent_session.workflow.definitions["subgraphs"][0]["definitions"]["subgraphs"][0]["nodes"][1]["metadata"]["provenance"]


def test_recursive_identity_link_and_group_fields_fail_closed() -> None:
    workflow, _outer, inner = _workflow()
    node = workflow.definitions["subgraphs"][0]["definitions"]["subgraphs"][0]["nodes"][0]
    node["group"] = "g"
    outer_definition = workflow.definitions["subgraphs"][0]
    inner_definition = outer_definition["definitions"]["subgraphs"][0]
    inner = f"{sg_key(outer_definition)}/{sg_key(inner_definition)}"
    for field in ("type", "class_type", "id", "uid", "properties", "group"):
        with pytest.raises(RecursiveEditError) as error:
            apply_edit_cow(
                workflow,
                SetNodeFieldOp("set_node_field", NodeFieldTarget(inner, "inner_i", field), "changed"),
            )
        assert error.value.code == "unsupported_structural_scope"
    node["inputs"] = [{"name": "value", "type": "INT", "link": 1}]
    outer_definition = workflow.definitions["subgraphs"][0]
    inner_definition = outer_definition["definitions"]["subgraphs"][0]
    inner = f"{sg_key(outer_definition)}/{sg_key(inner_definition)}"
    with pytest.raises(RecursiveEditError) as error:
        apply_edit_cow(
            workflow,
            SetNodeFieldOp("set_node_field", NodeFieldTarget(inner, "inner_i", "value"), 3),
        )
    assert error.value.code == "unsupported_structural_scope"

    grouped = workflow.copy()
    grouped.definitions["subgraphs"][0]["definitions"]["subgraphs"][0]["groups"] = [
        {"title": "unsupported-group", "bounds": [0, 0, 10, 10]}
    ]
    with pytest.raises(RecursiveEditError) as error:
        diff(workflow, grouped)
    assert error.value.code == "unsupported_structural_scope"


def test_root_interface_cannot_shadow_typed_recursive_definitions() -> None:
    workflow, _outer, inner = _workflow()
    before = workflow.semantic_projection()
    result = interpret(
        workflow,
        (SubgraphInterfaceOp("subgraph_interface", "change", "Inner", scope_path=""),),
    )
    assert not result.ok
    assert result.workflow.semantic_projection() == before

    mixed = workflow.copy()
    mixed.metadata["definitions"] = {
        "subgraphs": [{"id": "shadow", "name": "Shadow", "nodes": [], "links": []}]
    }
    with pytest.raises(RecursiveEditError) as error:
        diff(workflow, mixed)
    assert error.value.code == "unsupported_structural_scope"
