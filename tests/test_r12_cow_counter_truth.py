from __future__ import annotations

from copy import deepcopy

from vibecomfy.porting.edit.ops import (
    AddNodeOp,
    LinkSourceRef,
    LinkTargetRef,
    NodeFieldTarget,
    NodeTarget,
    RemoveLinkOp,
    RemoveNodeOp,
    SetNodeFieldOp,
    SubgraphInterfaceOp,
    UpsertLinkOp,
)
from vibecomfy.porting.emit.ui import guard_exit_ui, pin_untouched_ui


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


def test_guard_attributes_unknown_virtual_output_upsert() -> None:
    """Generated ``unknown_0`` output names resolve to the wildcard slot."""
    original = {
        "last_node_id": 3,
        "last_link_id": 3,
        "nodes": [
            {
                "id": 1,
                "type": "Reroute",
                "properties": {"vibecomfy_uid": "source"},
                "outputs": [{"name": "*", "type": "*", "links": [2]}],
            },
            {
                "id": 2,
                "type": "Target",
                "properties": {"vibecomfy_uid": "target"},
                "inputs": [{"name": "control", "type": "*", "link": 2}],
            },
        ],
        "links": [[2, 1, 0, 2, 0, "*"]],
    }
    candidate = deepcopy(original)
    candidate["links"] = [[2, 1, 0, 2, 0, ""]]
    operation = UpsertLinkOp(
        "upsert_link",
        LinkSourceRef("", "source", "unknown_0"),
        LinkTargetRef("", "target", "control"),
    )

    result = guard_exit_ui(original, candidate, (operation,))

    assert result.ok is True, result.diagnostics


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


def test_captured_link_ids_use_output_array_position_when_slot_index_is_absent() -> None:
    from vibecomfy.porting.emit.ui import _captured_link_id_map

    door = {
        "top": {"links": [[31, 105, 0, 8, 1, "VAE"]]},
        "nodes": {
            "105": {
                "outputs": [{"name": "VAE", "type": "VAE", "links": [31]}],
            },
            "8": {
                "inputs": [
                    {"name": "samples", "type": "LATENT", "link": None},
                    {"name": "vae", "type": "VAE", "link": 31},
                ],
            },
        },
    }

    assert _captured_link_id_map(door) == {("105", "0", "8", "vae"): 31}


def test_guard_attributes_upsert_from_a_node_added_in_the_same_delta() -> None:
    original = _counter_ui(node_counter=2, link_counter=2)
    candidate = deepcopy(original)
    candidate["last_node_id"] = 3
    candidate["last_link_id"] = 3
    candidate["nodes"].append(
        {
            "id": 3,
            "type": "LoadImage",
            "properties": {"vibecomfy_uid": "n1"},
            "outputs": [{"name": "IMAGE", "type": "IMAGE", "links": [3]}],
        }
    )
    candidate["nodes"][1]["inputs"][0]["link"] = 3
    candidate["links"] = [[3, 3, 0, 2, 0, "IMAGE"]]
    operations = (
        AddNodeOp(
            op="add_node",
            scope_path="",
            class_type="LoadImage",
            fields={},
            inputs={},
            uid="n1",
            node_id="3",
        ),
        UpsertLinkOp(
            op="upsert_link",
            source=LinkSourceRef("", "n1", "IMAGE"),
            target=LinkTargetRef("", "target", "image"),
        ),
    )

    result = guard_exit_ui(original, candidate, operations)

    assert result.ok is True, result.diagnostics


def test_guard_attributes_typed_multi_output_alias_from_new_node() -> None:
    original = _counter_ui(node_counter=2, link_counter=2)
    candidate = deepcopy(original)
    candidate["last_node_id"] = 3
    candidate["last_link_id"] = 3
    candidate["nodes"].append(
        {
            "id": 3,
            "type": "WanImageToVideo",
            "properties": {"vibecomfy_uid": "n1"},
            "outputs": [
                {"name": "positive", "type": "CONDITIONING", "links": None},
                {"name": "negative", "type": "CONDITIONING", "links": [3]},
                {"name": "latent", "type": "LATENT", "links": None},
            ],
        }
    )
    candidate["nodes"][1]["inputs"][0]["link"] = 3
    candidate["links"] = [[3, 3, 1, 2, 0, "CONDITIONING"]]
    operations = (
        AddNodeOp(
            op="add_node",
            scope_path="",
            class_type="WanImageToVideo",
            fields={},
            inputs={},
            uid="n1",
            node_id="3",
        ),
        UpsertLinkOp(
            op="upsert_link",
            source=LinkSourceRef("", "n1", "CONDITIONING_1"),
            target=LinkTargetRef("", "target", "image"),
        ),
    )

    result = guard_exit_ui(original, candidate, operations)

    assert result.ok is True, result.diagnostics


def test_emitter_resolves_typed_multi_output_alias_to_its_position() -> None:
    from vibecomfy.porting.emit.ui import _resolve_output_slot_and_type
    from vibecomfy.schema import NodeSchema, OutputSpec

    schema = NodeSchema(
        class_type="WanImageToVideo",
        pack=None,
        inputs={},
        outputs=[
            OutputSpec(type="CONDITIONING", name="positive"),
            OutputSpec(type="CONDITIONING", name="negative"),
            OutputSpec(type="LATENT", name="latent"),
        ],
    )

    assert _resolve_output_slot_and_type(
        "CONDITIONING_1", "WanImageToVideo", {"WanImageToVideo": schema}
    ) == (1, "CONDITIONING")
    assert _resolve_output_slot_and_type(
        "LATENT_2", "WanImageToVideo", {"WanImageToVideo": schema}
    ) == (2, "LATENT")


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


def test_guard_rejects_remove_node_with_dangling_incident_link() -> None:
    original = _counter_ui()
    candidate = _counter_ui()
    candidate["nodes"] = [original["nodes"][0], original["nodes"][1]]
    operation = RemoveNodeOp("remove_node", NodeTarget("", "target"))

    result = guard_exit_ui(original, candidate, (operation,))

    assert result.ok is False
    assert any(issue.code == "full_ui_link_changed_unattributed" for issue in result.diagnostics)


def test_guard_rejects_remove_link_subset_with_duplicate_target_endpoints() -> None:
    original = _counter_ui(
        link_counter=11,
        links=[[2, 1, 0, 2, 0, "IMAGE"], [10, 1, 0, 2, 0, "IMAGE"]],
    )
    candidate = _counter_ui(link_counter=11, links=[[10, 1, 0, 2, 0, "IMAGE"]])

    result = guard_exit_ui(original, candidate, (_remove_link_op(),))

    assert result.ok is False


def _upsert_topology_ui(source_id: int) -> dict:
    graph = _counter_ui(links=[[2, 1, 0, 2, 0, "IMAGE"]])
    graph["nodes"].append(
        {
            "id": source_id,
            "type": "Source",
            "properties": {"vibecomfy_uid": "source-2"},
            "outputs": [{"name": "IMAGE"}],
        }
    )
    return graph


def test_guard_repeated_upsert_uses_last_effective_operation() -> None:
    original = _upsert_topology_ui(3)
    candidate = _upsert_topology_ui(3)
    candidate["last_link_id"] = 11
    candidate["links"] = [[9, 1, 0, 2, 0, "IMAGE"]]
    operations = (
        UpsertLinkOp("upsert_link", LinkSourceRef("", "source", "IMAGE"), LinkTargetRef("", "target", "image")),
        UpsertLinkOp("upsert_link", LinkSourceRef("", "source-2", "IMAGE"), LinkTargetRef("", "target", "image")),
    )

    result = guard_exit_ui(original, candidate, operations)

    assert result.ok is False


def test_guard_repeated_upsert_accepts_last_source() -> None:
    original = _upsert_topology_ui(3)
    candidate = _upsert_topology_ui(3)
    candidate["last_link_id"] = 11
    candidate["links"] = [[9, 3, 0, 2, 0, "IMAGE"]]
    operations = (
        UpsertLinkOp("upsert_link", LinkSourceRef("", "source", "IMAGE"), LinkTargetRef("", "target", "image")),
        UpsertLinkOp("upsert_link", LinkSourceRef("", "source-2", "IMAGE"), LinkTargetRef("", "target", "image")),
    )

    assert guard_exit_ui(original, candidate, operations).ok is True


def test_guard_remove_then_upsert_accepts_socket_typed_replacement() -> None:
    original = _upsert_topology_ui(3)
    candidate = _upsert_topology_ui(3)
    candidate["last_link_id"] = 11
    candidate["links"] = [[9, 3, 0, 2, 0, "IMAGE"]]
    operations = (
        _remove_link_op(),
        UpsertLinkOp(
            "upsert_link",
            LinkSourceRef("", "source-2", "IMAGE"),
            LinkTargetRef("", "target", "image"),
        ),
    )

    assert guard_exit_ui(original, candidate, operations).ok is True


def test_guard_upsert_accepts_reusing_original_incoming_link_id() -> None:
    original = _upsert_topology_ui(3)
    candidate = _upsert_topology_ui(3)
    candidate["last_link_id"] = 11
    candidate["links"] = [[2, 3, 0, 2, 0, "IMAGE"]]
    operation = UpsertLinkOp(
        "upsert_link",
        LinkSourceRef("", "source-2", "IMAGE"),
        LinkTargetRef("", "target", "image"),
    )

    assert guard_exit_ui(original, candidate, (operation,)).ok is True


def _reroute_ui(*, reroute_type: str = "Reroute", links=None, link_counter: int = 9) -> tuple[dict, dict]:
    original = {
        "last_node_id": 5,
        "last_link_id": link_counter,
        "nodes": [
            {"id": 1, "type": "Source", "properties": {"vibecomfy_uid": "source"}, "outputs": [{"name": "out"}]},
            {"id": 2, "type": reroute_type, "properties": {"vibecomfy_uid": "reroute"}, "inputs": [{"name": "in"}], "outputs": [{"name": "out"}]},
            {"id": 3, "type": "Target", "properties": {"vibecomfy_uid": "target"}, "inputs": [{"name": "image"}]},
        ],
        "links": links or [[5, 1, 0, 2, 0, "IMAGE"], [2, 2, 0, 3, 0, "IMAGE"]],
    }
    candidate = {**original, "nodes": [original["nodes"][0], original["nodes"][2]], "links": [[2, 1, 0, 3, 0, "IMAGE"]]}
    return original, candidate


def test_guard_accepts_one_in_one_out_reroute_passthrough() -> None:
    original, candidate = _reroute_ui(link_counter=9)
    assert guard_exit_ui(original, candidate, (RemoveNodeOp("remove_node", NodeTarget("", "reroute")),)).ok


def test_guard_accepts_reroute_passthrough_with_decreased_link_counter() -> None:
    original, candidate = _reroute_ui(
        links=[[10, 1, 0, 2, 0, "IMAGE"], [2, 2, 0, 3, 0, "IMAGE"]],
        link_counter=11,
    )
    candidate["last_link_id"] = 3
    operation = RemoveNodeOp("remove_node", NodeTarget("", "reroute"))

    assert guard_exit_ui(original, candidate, (operation,)).ok is True


def test_guard_rejects_reroute_passthrough_on_non_reroute() -> None:
    original, candidate = _reroute_ui(reroute_type="PreviewImage")
    assert not guard_exit_ui(original, candidate, (RemoveNodeOp("remove_node", NodeTarget("", "reroute")),)).ok


def test_guard_rejects_reroute_passthrough_reusing_incoming_id() -> None:
    original, candidate = _reroute_ui()
    candidate["links"] = [[5, 1, 0, 3, 0, "IMAGE"]]
    assert not guard_exit_ui(original, candidate, (RemoveNodeOp("remove_node", NodeTarget("", "reroute")),)).ok


def test_guard_rejects_reroute_drop_all_when_passthrough_required() -> None:
    original, candidate = _reroute_ui()
    candidate["links"] = []
    assert not guard_exit_ui(original, candidate, (RemoveNodeOp("remove_node", NodeTarget("", "reroute")),)).ok


def test_guard_rejects_targetless_remove_link_before_attribution() -> None:
    original = _counter_ui()
    assert not guard_exit_ui(original, original, (RemoveLinkOp("remove_link", link_id=2),)).ok


def test_guard_rejects_duplicate_ui_identities_and_noncanonical_links() -> None:
    original = _counter_ui()
    duplicate_uid = {**original, "nodes": [*original["nodes"], {**original["nodes"][1], "id": 3}]}
    assert not guard_exit_ui(original, duplicate_uid, ()).ok
    duplicate_link = {**original, "links": [*original["links"], original["links"][0]]}
    assert not guard_exit_ui(original, duplicate_link, ()).ok
    idless = {**original, "links": [["x", 1, 0, 2, 0, "IMAGE"]]}
    assert not guard_exit_ui(original, idless, ()).ok
    negative = {**original, "links": [[-1, 1, 0, 2, 0, "IMAGE"]]}
    assert not guard_exit_ui(original, negative, ()).ok
    string_endpoints = {**original, "links": [[3, "1", 0, "2", 0, "IMAGE"]]}
    assert not guard_exit_ui(original, string_endpoints, ()).ok
    negative_endpoint = {**original, "links": [[3, 1, -1, 2, 0, "IMAGE"]]}
    result = guard_exit_ui(original, negative_endpoint, ())
    assert not result.ok
    assert any(issue.code == "full_ui_identity_malformed" for issue in result.diagnostics)
    colliding_native_ids = {
        **original,
        "nodes": [*original["nodes"], {**original["nodes"][0], "id": "01", "properties": {"vibecomfy_uid": "other"}}],
    }
    result = guard_exit_ui(colliding_native_ids, colliding_native_ids, ())
    assert not result.ok
    assert any(issue.code == "full_ui_identity_malformed" for issue in result.diagnostics)


def test_guard_unresolvable_upsert_is_a_fold_noop() -> None:
    original = _counter_ui()
    operation = UpsertLinkOp(
        "upsert_link",
        LinkSourceRef("", "ghost", "IMAGE"),
        LinkTargetRef("", "target", "image"),
    )

    assert guard_exit_ui(original, original, (operation,)).ok is True


def test_guard_allows_authorized_subgraph_removal() -> None:
    original = _counter_ui()
    original["definitions"] = {
        "subgraphs": [{"id": "sg-remove", "nodes": [], "links": []}]
    }
    candidate = deepcopy(original)
    candidate["definitions"]["subgraphs"] = []
    operation = SubgraphInterfaceOp(
        "subgraph_interface", "remove", "Removed", id="sg-remove"
    )

    result = guard_exit_ui(original, candidate, (operation,))

    assert result.ok is True


def test_pin_set_field_preserves_schema_less_link_type_on_unrelated_reemit() -> None:
    """A widget write must not replace an untouched ``*`` socket with UNKNOWN."""
    original = {
        "nodes": [
            {
                "id": 1,
                "type": "SchemaLessTarget",
                "properties": {"vibecomfy_uid": "target"},
                "inputs": [{"name": "control", "type": "*", "link": 4}],
                "widgets_values": [0],
            }
        ],
        "links": [[4, 2, 0, 1, 0, "*"]],
    }
    emitted = deepcopy(original)
    emitted["nodes"][0]["inputs"][0]["type"] = "UNKNOWN"
    emitted["nodes"][0]["widgets_values"] = [1]
    operation = SetNodeFieldOp(
        "set_node_field", NodeFieldTarget("", "target", "value"), 1
    )

    pinned = pin_untouched_ui(original, emitted, (operation,))

    assert pinned["nodes"][0]["inputs"] == original["nodes"][0]["inputs"]


def test_pin_set_field_preserves_unlinked_widget_input_descriptor() -> None:
    """A literal widget write must not delete its captured UI input record."""
    original = {
        "nodes": [
            {
                "id": 1,
                "type": "CustomWidgetTarget",
                "properties": {"vibecomfy_uid": "target", "kept": "original"},
                "inputs": [
                    {"name": "model", "type": "MODEL", "link": 4},
                    {
                        "name": "texture_quality",
                        "type": "COMBO",
                        "widget": {"name": "texture_quality"},
                        "link": None,
                    },
                ],
                "widgets_values": ["standard"],
            }
        ],
        "links": [[4, 2, 0, 1, 0, "MODEL"]],
    }
    emitted = deepcopy(original)
    emitted["nodes"][0]["inputs"] = [emitted["nodes"][0]["inputs"][0]]
    emitted["nodes"][0]["widgets_values"] = ["detailed"]
    emitted["nodes"][0]["properties"]["vibecomfy_id"] = "CustomWidgetTarget_0"
    emitted["nodes"][0]["properties"]["_vibecomfy_schema_provider"] = "unknown"
    operation = SetNodeFieldOp(
        "set_node_field",
        NodeFieldTarget("", "target", "texture_quality"),
        "detailed",
    )

    pinned = pin_untouched_ui(original, emitted, (operation,))

    assert pinned["nodes"][0]["inputs"] == original["nodes"][0]["inputs"]
    assert pinned["nodes"][0]["widgets_values"] == ["detailed"]
    assert pinned["nodes"][0]["properties"] == original["nodes"][0]["properties"]
