"""Tests for control_after_generate retention through JSON→IR ingest (T3).

Proves:
1. 'randomize' and 'fixed' captured from the named-inputs dict (api-format path).
2. 'fixed' captured from _ui.widgets_values KSampler None-slot path.
3. Absent control_after_generate → metadata key unset (never guessed).
4. compile("api") guard: control_after_generate absent from compiled output
   even when captured in metadata (byte-identical compile path preserved).
"""
from __future__ import annotations

import json
from collections import Counter
from copy import deepcopy
from pathlib import Path

import pytest

from vibecomfy.ingest.normalize import (
    door_import_source_kind,
    from_api,
    from_envelope,
    from_ui,
    ingest_workflow_and_ui,
    normalize_to_api,
)
from vibecomfy.porting.emit.ui import emit_ui_json


def _t06_recursive_graph(*, links=None, **extra):
    definition = {
        "name": "Outer",
        "nodes": [
            {"id": "source", "type": "Source", "inputs": [], "outputs": [{"name": "out", "links": [1]}]},
            {"id": "sink", "type": "Sink", "inputs": [{"name": "value", "link": 1}], "outputs": []},
        ],
        "links": links if links is not None else [[1, "source", 0, "sink", 0, "X"]],
    }
    definition.update(extra)
    return {"nodes": [{"id": 1, "type": "Outer", "inputs": [], "outputs": [], "widgets_values": []}],
            "links": [], "definitions": {"subgraphs": [definition]}}


def test_bundle_source_kind_classification_stays_at_ingest_door() -> None:
    assert door_import_source_kind({"nodes": []}) == "ui"
    assert door_import_source_kind(
        {"vibecomfy_format_version": "1.0", "nodes": {}}
    ) == "envelope"
    assert door_import_source_kind({"prompt": {"1": {"class_type": "A", "inputs": {}}}}) == "api"
    assert door_import_source_kind({"malformed": True}) == "api"
    assert door_import_source_kind(
        {
            "vibecomfy_format_version": "1.0",
            "nodes": {},
            "prompt": {"nodes": []},
        }
    ) == "envelope"
    assert door_import_source_kind(
        {"nodes": [], "prompt": {"1": {"class_type": "A", "inputs": {}}}}
    ) == "ui"
    assert door_import_source_kind(
        {"nodes": {}, "prompt": {"nodes": []}}
    ) == "api"


def test_t06_rework_native_sentinel_never_bypasses_config_extra() -> None:
    raw = _t06_recursive_graph(
        links=[[1, "-10", 0, "sink", 0, "X"]], config={}, extra={}
    )
    with pytest.raises(ValueError, match="unsupported_boundary_encoding"):
        from_ui(raw, use_comfy_converter=False)


def test_t06_rework_native_sentinel_legacy_definition_is_rejected() -> None:
    raw = _t06_recursive_graph(
        links=[[1, "-10", 0, "sink", 0, "X"]],
        inputNode={"id": -10},
        outputNode={"id": -20},
    )
    with pytest.raises(ValueError, match="unsupported_boundary_encoding"):
        from_ui(raw, use_comfy_converter=False)


def test_t06_rework_unknown_metadata_is_stripped_but_known_rejects() -> None:
    unknown = from_api({"1": {"class_type": "MysteryNode", "inputs": {}, "foo": "x", "summary": "y"}})
    assert "foo" not in unknown.nodes["1"].metadata
    assert "summary" not in unknown.nodes["1"].metadata
    assert unknown.nodes["1"].metadata["schema_source"]["provider"] == ""
    with pytest.raises(ValueError, match="metadata key 'foo'.*reconciliation action"):
        from_api({"1": {"class_type": "KSampler", "inputs": {}, "schema_source": {"provider": "authoritative_object_info"}, "foo": "x"}})
    with pytest.raises(ValueError, match="metadata key 'summary'.*reconciliation action"):
        from_api({"1": {"class_type": "KSampler", "inputs": {}, "schema_source": {"provider": "workflow_json_provisional"}, "summary": "y"}})


def test_t06_rework_recursive_interfaces_and_boundaries_are_local_and_typed() -> None:
    malformed_interface = _t06_recursive_graph()
    malformed_interface["interfaces"] = {"Outer:missing": [{"name": "x", "direction": "input"}]}
    with pytest.raises(ValueError, match="interface scope|interface .*owner"):
        from_ui(malformed_interface, use_comfy_converter=False)
    malformed_direction = _t06_recursive_graph()
    malformed_direction["interfaces"] = {"Outer": {"inputs": [{"name": "x", "direction": "evil"}]}}
    with pytest.raises(ValueError, match="direction"):
        from_ui(malformed_direction, use_comfy_converter=False)
    malformed_boundary = _t06_recursive_graph()
    malformed_boundary["boundary_ports"] = [{"scope_path": "Unknown", "name": "x", "direction": "input", "node_uid": "sink", "field": "value"}]
    with pytest.raises(ValueError, match="boundary.*scope|boundary.*owner"):
        from_ui(malformed_boundary, use_comfy_converter=False)


def test_t06_rework_virtual_wire_scope_and_set_ambiguity_fail_closed() -> None:
    raw = _t06_recursive_graph(virtual_wires={"BUS": {"legs": [{
        "scope_path": "other", "leg_index": 0, "occurrence_index": 0,
        "from_node": "1", "from_output": "0", "to_node": "1", "to_input": "x",
    }]}})
    with pytest.raises(ValueError, match="crosses scope|scope_path"):
        from_ui(raw, use_comfy_converter=False)
    graph = {
        "nodes": [
            {"id": 1, "type": "Source", "inputs": [], "outputs": [{"name": "out"}], "widgets_values": []},
            {"id": 2, "type": "SetNode", "inputs": [{"name": "value", "link": 1}], "outputs": [], "widgets_values": ["BUS"]},
            {"id": 3, "type": "SetNode", "inputs": [{"name": "value", "link": 2}], "outputs": [], "widgets_values": ["BUS"]},
            {"id": 4, "type": "GetNode", "inputs": [], "outputs": [{"name": "out"}], "widgets_values": ["BUS"]},
            {"id": 5, "type": "Sink", "inputs": [{"name": "value", "link": 3}], "outputs": [], "widgets_values": []},
        ],
        "links": [[1, 1, 0, 2, 0, "X"], [2, 1, 0, 3, 0, "X"], [3, 4, 0, 5, 0, "X"]],
    }
    with pytest.raises(ValueError, match="ambiguous|multiple.*SetNode"):
        from_ui(graph, use_comfy_converter=False)


def test_t06_rework_recursive_links_are_exact_and_match_rosters() -> None:
    bad_type = _t06_recursive_graph(links=[[1, "source", 0, "sink", 0, 123]])
    with pytest.raises(ValueError, match="type"):
        from_ui(bad_type, use_comfy_converter=False)
    bad_mapping = _t06_recursive_graph(links=[{"id": 1, "origin_id": "source", "origin_slot": 0,
                                                "target_id": "sink", "target_slot": 0, "type": "X", "evil": 1}])
    with pytest.raises(ValueError, match="exact link fields"):
        from_ui(bad_mapping, use_comfy_converter=False)
    missing_target = _t06_recursive_graph(
        links=[[1, "source", 0, "sink", 1, "X"]],
    )
    with pytest.raises(ValueError, match="target_slot|input record|roster"):
        from_ui(missing_target, use_comfy_converter=False)
    bad_output = _t06_recursive_graph(links=[[1, "source", 99, "sink", 0, "X"]])
    with pytest.raises(ValueError, match="origin_slot|output roster"):
        from_ui(bad_output, use_comfy_converter=False)
    orphan = _t06_recursive_graph(
        links=[[2, "source", 0, "sink", 0, "X"]],
    )
    with pytest.raises(ValueError, match="orphan|link.*record|output"):
        from_ui(orphan, use_comfy_converter=False)


def test_t06_rework_recursive_snapshot_records_topology_and_digest() -> None:
    from vibecomfy.ingest.snapshot import capture_workflow_snapshot, snapshot_of

    workflow = from_ui(_t06_recursive_graph(), use_comfy_converter=False)
    snapshot = snapshot_of(workflow)
    assert snapshot is not None
    recursive_uids = [uid for uid in snapshot.field_snapshot if "#" in uid]
    assert recursive_uids
    assert any(snapshot.field_snapshot[uid]["incoming_edge_sig"] for uid in recursive_uids)
    before = snapshot.semantic_digest
    definition = workflow.definitions["subgraphs"][0]
    definition["links"][0][3] = "source"
    recaptured = capture_workflow_snapshot(None, workflow, source_representation="ui")
    assert recaptured.semantic_digest != before


def test_t06_rework_root_virtual_leg_scope_must_be_empty_string() -> None:
    raw = {
        "nodes": [{"id": 1, "type": "Source", "inputs": [], "outputs": [], "widgets_values": []}],
        "links": [],
        "virtual_wires": {"BUS": {"legs": [{
            "scope_path": None, "leg_index": 0, "occurrence_index": 0,
            "from_node": "1", "from_output": "0", "to_node": "1", "to_input": "x",
        }]}}
    }
    with pytest.raises(ValueError, match="scope"):
        from_ui(raw, use_comfy_converter=False)


def test_t06_rework_envelope_captures_authored_set_get_helpers() -> None:
    envelope = {
        "id": "helper-envelope",
        "vibecomfy_format_version": "1.0",
        "source": {"id": "helper-envelope", "source_type": "vibe", "path": None, "provenance": {}},
        "requirements": {"models": [], "custom_nodes": [], "missing_models": [], "missing_nodes": [], "unsupported": []},
        "nodes": {
            "1": {"id": "1", "class_type": "Source", "pack": None, "inputs": {}, "widgets": {}, "metadata": {}, "uid": "1"},
            "2": {"id": "2", "class_type": "SetNode", "pack": None, "inputs": {}, "widgets": {"widget_0": "BUS"}, "metadata": {}, "uid": "2"},
            "3": {"id": "3", "class_type": "GetNode", "pack": None, "inputs": {}, "widgets": {"widget_0": "BUS"}, "metadata": {}, "uid": "3"},
            "4": {"id": "4", "class_type": "Sink", "pack": None, "inputs": {}, "widgets": {}, "metadata": {}, "uid": "4"},
        },
        "edges": [
            {"from_node": "1", "from_output": "0", "to_node": "2", "to_input": "value"},
            {"from_node": "3", "from_output": "0", "to_node": "4", "to_input": "value"},
        ],
        "inputs": {}, "outputs": [], "metadata": {}, "strict_types": False,
    }
    workflow = from_envelope(envelope)
    assert workflow.virtual_wires["BUS"]["legs"][0]["scope_path"] == ""
    assert set(workflow.nodes) == {"1", "2", "3", "4"}
    assert len(workflow.edges) == 2


def test_t06_rework_recursive_capture_persists_at_depth_two() -> None:
    def definition(name: str, nested=None):
        value = {
            "name": name,
            "nodes": [
                {"id": "source", "type": "Source", "inputs": [], "outputs": [{"name": "out", "links": [1]}]},
                {"id": "set", "type": "SetNode", "inputs": [{"name": "value", "link": 1}], "outputs": [], "widgets_values": ["BUS"]},
                {"id": "get", "type": "GetNode", "inputs": [], "outputs": [{"name": "out", "links": [2]}], "widgets_values": ["BUS"]},
                {"id": "sink", "type": "Sink", "inputs": [{"name": "value", "link": 2}], "outputs": []},
            ],
            "links": [[1, "source", 0, "set", 0, "X"], [2, "get", 0, "sink", 0, "X"]],
        }
        if nested is not None:
            value["definitions"] = {"subgraphs": [nested]}
        return value
    inner = definition("Inner")
    outer = definition("Outer", inner)
    raw = {"nodes": [{"id": 1, "type": "Outer", "inputs": [], "outputs": [], "widgets_values": []}], "links": [], "definitions": {"subgraphs": [outer]}}
    workflow = from_ui(raw, use_comfy_converter=False)
    outer_norm = workflow.definitions["subgraphs"][0]
    inner_norm = outer_norm["definitions"]["subgraphs"][0]
    assert outer_norm["virtual_wires"]["BUS"]["legs"]
    assert inner_norm["virtual_wires"]["BUS"]["legs"]
    assert outer_norm["virtual_wires"]["BUS"]["legs"][0]["scope_path"] != inner_norm["virtual_wires"]["BUS"]["legs"][0]["scope_path"]


def test_t06_rework_definition_boundary_missing_name_has_stable_error() -> None:
    raw = _t06_recursive_graph(boundary_ports=[{"scope_path": "Outer", "direction": "input", "node_uid": "sink", "field": "value"}])
    with pytest.raises(ValueError, match="boundary port 0.*name|boundary.*name"):
        from_ui(raw, use_comfy_converter=False)


@pytest.mark.parametrize(
    "marker_fields",
    [
        {"inputNode": {"id": -10}, "outputNode": {"id": -20}},
        {"inputNode": {"id": -10}},
        {"outputNode": {"id": -20}},
        {"nodes": [{"id": -10, "type": "Input", "inputs": [], "outputs": []}, {"id": -20, "type": "Output", "inputs": [], "outputs": []}]},
        {"config": {"inputNode": -10, "outputNode": -20}},
        {"extra": {"inputNode": -10, "outputNode": -20}},
    ],
)
def test_t06_rework_every_native_marker_shape_rejects_from_ui(marker_fields) -> None:
    raw = _t06_recursive_graph(**marker_fields)
    with pytest.raises(ValueError, match="unsupported_boundary_encoding"):
        from_ui(raw, use_comfy_converter=False)


def test_t06_rework_nested_native_marker_and_envelope_reject() -> None:
    inner = _t06_recursive_graph()["definitions"]["subgraphs"][0]
    outer = _t06_recursive_graph()
    outer["definitions"]["subgraphs"][0]["definitions"] = {"subgraphs": [{**inner, "inputNode": {"id": -10}}]}
    with pytest.raises(ValueError, match="unsupported_boundary_encoding"):
        from_ui(outer, use_comfy_converter=False)
    envelope = {
        "id": "e", "vibecomfy_format_version": "1.0",
        "source": {"id": "e", "source_type": "vibe", "path": None, "provenance": {}},
        "requirements": {"models": [], "custom_nodes": [], "missing_models": [], "missing_nodes": [], "unsupported": []},
        "nodes": {"1": {"id": "1", "class_type": "Outer", "pack": None, "inputs": {}, "widgets": {}, "metadata": {}, "uid": "1"}},
        "edges": [], "inputs": {}, "outputs": [], "metadata": {}, "strict_types": False,
        "definitions": {"subgraphs": [{"name": "Outer", "nodes": [{"id": "source", "type": "Source", "inputs": [], "outputs": []}], "links": [], "outputNode": {"id": -20}}]},
    }
    with pytest.raises(ValueError, match="unsupported_boundary_encoding"):
        from_envelope(envelope)


@pytest.mark.parametrize("marker_id", [-10, "-20"])
def test_t06_rework_mapped_native_marker_rejects_from_ui_and_envelope(marker_id) -> None:
    definition = {
        "name": "MappedOuter",
        "nodes": {"entry": {"id": marker_id, "type": "Input", "inputs": [], "outputs": []}},
        "links": [],
    }
    ui = {"nodes": [{"id": 1, "type": "MappedOuter", "inputs": [], "outputs": [], "widgets_values": []}], "links": [], "definitions": {"subgraphs": [definition]}}
    with pytest.raises(ValueError, match="unsupported_boundary_encoding"):
        from_ui(ui, use_comfy_converter=False)
    envelope = {
        "id": "mapped", "vibecomfy_format_version": "1.0",
        "source": {"id": "mapped", "source_type": "vibe", "path": None, "provenance": {}},
        "requirements": {"models": [], "custom_nodes": [], "missing_models": [], "missing_nodes": [], "unsupported": []},
        "nodes": {"1": {"id": "1", "class_type": "MappedOuter", "pack": None, "inputs": {}, "widgets": {}, "metadata": {}, "uid": "1"}},
        "edges": [], "inputs": {}, "outputs": [], "metadata": {}, "strict_types": False,
        "definitions": {"subgraphs": [definition]},
    }
    with pytest.raises(ValueError, match="unsupported_boundary_encoding"):
        from_envelope(envelope)


def test_t06_recursive_import_normalizes_scope_and_unresolved_schema() -> None:
    raw = {
        "nodes": [{"id": 1, "type": "Outer", "inputs": [], "outputs": [], "widgets_values": []}],
        "links": [],
        "definitions": {"subgraphs": [{
            "name": "Outer",
            "nodes": [{"id": "inner", "type": "Inner", "inputs": [], "outputs": []}],
            "links": [],
        }]},
    }
    workflow = from_ui(raw, use_comfy_converter=False)
    definition = workflow.definitions["subgraphs"][0]
    assert definition["sg_key"] in definition["scope_path"]
    assert definition["nodes"][0]["uid"] == "inner"
    assert workflow.nodes["1"].metadata["schema_source"] == {
        "provider": "", "path": None, "cache_path": None, "server_url": None,
        "package": None, "version": None, "hash": None, "confidence": 0.0,
    }


def test_t06_import_rejects_unclassified_metadata_and_nonfinite_semantics() -> None:
    with pytest.raises(ValueError, match="node '1'.*metadata key 'summary'.*reconciliation action"):
        from_api({"1": {"class_type": "Known", "inputs": {}, "schema_source": {"provider": "authoritative_object_info"}, "summary": "opaque"}})
    with pytest.raises(ValueError, match="nonfinite semantic value"):
        from_api({"1": {"class_type": "Known", "inputs": {"value": float("nan")}}})


def test_t06_ui_links_are_exact_and_capture_set_get_before_projection() -> None:
    raw = {
        "nodes": [
            {"id": 1, "type": "Source", "inputs": [], "outputs": [{"name": "out"}], "widgets_values": []},
            {"id": 2, "type": "SetNode", "inputs": [{"name": "value", "link": 1}], "outputs": [], "widgets_values": ["BUS"]},
            {"id": 3, "type": "GetNode", "inputs": [], "outputs": [{"name": "out"}], "widgets_values": ["BUS"]},
            {"id": 4, "type": "Sink", "inputs": [{"name": "value", "link": 2}], "outputs": [], "widgets_values": []},
        ],
        "links": [[1, 1, 0, 2, 0, "X"], [2, 3, 0, 4, 0, "X"]],
    }
    workflow = from_ui(raw, use_comfy_converter=False)
    assert workflow.virtual_wires["BUS"]["legs"] == [{
        "scope_path": "", "leg_index": 0, "occurrence_index": 0,
        "from_node": "1", "from_output": "0", "to_node": "4", "to_input": "value",
    }]
    malformed = {**raw, "links": [[1, 1, 0, 2, 0]]}
    with pytest.raises(ValueError, match="exact six-field"):
        from_ui(malformed, use_comfy_converter=False)


def _ksampler_api_node(*, control: str | None = None) -> dict:
    inputs: dict = {
        "seed": 42,
        "steps": 20,
        "cfg": 7.0,
        "sampler_name": "euler",
        "scheduler": "normal",
        "denoise": 1.0,
    }
    if control is not None:
        inputs["control_after_generate"] = control
    return {"class_type": "KSampler", "inputs": inputs}


def _ksampler_api_node_with_ui(*, control: str) -> dict:
    """KSampler node as produced by _normalize_ui_to_api with _ui.widgets_values.

    KSampler widget schema: ["seed", None, "steps", "cfg", "sampler_name", "scheduler", "denoise"]
    Slot index 1 is None (the control_after_generate UI slot).
    """
    return {
        "class_type": "KSampler",
        "inputs": {
            "seed": 42,
            "steps": 20,
            "cfg": 7.0,
            "sampler_name": "euler",
            "scheduler": "normal",
            "denoise": 1.0,
        },
        "_ui": {"widgets_values": [42, control, 20, 7.0, "euler", "normal", 1.0]},
    }


def _workflow_from_node(node: dict, node_id: str = "1"):  # type: ignore[return]
    return from_api({node_id: node})


def test_ui_ingest_captures_exact_native_socket_rosters() -> None:
    workflow = from_ui(
        {
            "last_node_id": 1,
            "last_link_id": 0,
            "nodes": [
                {
                    "id": 1,
                    "type": "RosterNode",
                    "inputs": [{"name": "first"}, None, {"name": "third"}],
                    "outputs": [{"name": "result"}, None],
                    "widgets_values": [],
                }
            ],
            "links": [],
            "groups": [],
        },
        use_comfy_converter=False,
    )
    node = workflow.nodes["1"]
    assert node.native_input_names == ["first", None, "third"]
    assert node.native_output_names == ["result", None]
    assert "_ui" in node.metadata
    assert "inputs" not in node.native_input_names


# ── Case 1a: 'randomize' captured from named inputs dict ─────────────────────


def test_control_after_generate_randomize_from_inputs() -> None:
    wf = _workflow_from_node(_ksampler_api_node(control="randomize"))
    assert wf.nodes["1"].metadata.get("control_after_generate") == "randomize"


# ── Case 1b: 'fixed' captured from named inputs dict ─────────────────────────


def test_control_after_generate_fixed_from_inputs() -> None:
    wf = _workflow_from_node(_ksampler_api_node(control="fixed"))
    assert wf.nodes["1"].metadata.get("control_after_generate") == "fixed"


# ── Case 2: 'fixed' captured from _ui.widgets_values None-slot ───────────────


def test_control_after_generate_fixed_from_ui_widgets() -> None:
    wf = _workflow_from_node(_ksampler_api_node_with_ui(control="fixed"))
    assert wf.nodes["1"].metadata.get("control_after_generate") == "fixed"


def test_ui_widget_roster_outranks_schema_with_leading_custom_socket() -> None:
    """Exact UI names prevent a custom linked socket from shifting literals.

    TripoTextureNode's schema begins with the custom ``MODEL_TASK_ID`` socket.
    That type is not a universal link-only token, while the LiteGraph node
    carries an exact widget roster.  The ingest door must therefore bind the
    six serialized values to those six UI names instead of offsetting them by
    the socket and dropping the first boolean on key collision.
    """
    from vibecomfy.schema.provider import ObjectInfoIndexSchemaProvider

    raw = {
        "nodes": [
            {
                "id": 7,
                "type": "TripoTextToModelNode",
                "inputs": [],
                "outputs": [
                    {
                        "name": "model task_id",
                        "type": "MODEL_TASK_ID",
                        "links": [2],
                        "slot_index": 1,
                    }
                ],
                "widgets_values": [],
            },
            {
                "id": 26,
                "type": "TripoTextureNode",
                "inputs": [
                    {"name": "model_task_id", "type": "MODEL_TASK_ID", "link": 2},
                    {
                        "name": "texture",
                        "type": "BOOLEAN",
                        "link": None,
                        "widget": {"name": "texture"},
                    },
                    {
                        "name": "pbr",
                        "type": "BOOLEAN",
                        "link": None,
                        "widget": {"name": "pbr"},
                    },
                    {
                        "name": "texture_seed",
                        "type": "INT",
                        "link": None,
                        "widget": {"name": "texture_seed"},
                    },
                    {
                        "name": "texture_quality",
                        "type": "COMBO",
                        "link": None,
                        "widget": {"name": "texture_quality"},
                    },
                    {
                        "name": "texture_alignment",
                        "type": "COMBO",
                        "link": None,
                        "widget": {"name": "texture_alignment"},
                    },
                    {
                        "name": "texture_prompt",
                        "type": "STRING",
                        "link": None,
                        "widget": {"name": "texture_prompt"},
                    },
                ],
                "outputs": [],
                "widgets_values": [True, True, 42, "standard", "original_image", ""],
            },
        ],
        "links": [[2, 7, 1, 26, 0, "MODEL_TASK_ID"]],
    }
    provider = ObjectInfoIndexSchemaProvider("vibecomfy/porting/cache/object_info")

    api = normalize_to_api(raw, schema_provider=provider, use_comfy_converter=False)

    assert api["26"]["inputs"] == {
        "model_task_id": ["7", 1],
        "texture": True,
        "pbr": True,
        "texture_seed": 42,
        "texture_quality": "standard",
        "texture_alignment": "original_image",
        "texture_prompt": "",
    }
    assert api["26"]["_input_provenance"] == {
        "model_task_id": "edge",
        "texture": "widget",
        "pbr": "widget",
        "texture_seed": "widget",
        "texture_quality": "widget",
        "texture_alignment": "widget",
        "texture_prompt": "widget",
    }

    workflow = from_api(api, schema_provider=provider)
    texture_node = workflow.nodes["26"]
    assert texture_node.inputs == {
        "texture": True,
        "pbr": True,
        "texture_seed": 42,
        "texture_quality": "standard",
        "texture_alignment": "original_image",
        "texture_prompt": "",
    }
    texture_node.inputs["texture_quality"] = "detailed"
    emitted = emit_ui_json(workflow, schema_provider=provider)
    emitted_texture = next(node for node in emitted["nodes"] if node["id"] == 26)
    assert emitted_texture["widgets_values"] == [
        True,
        True,
        42,
        "detailed",
        "original_image",
        "",
    ]


def test_public_raw_widgets_alias_is_preserved_as_raw_widget_payload() -> None:
    wf = _workflow_from_node(
        {
            "class_type": "PrimitiveInt",
            "inputs": {"widget_0": 7, "widget_1": "fixed"},
            "raw_widgets": {
                "values": [7, "fixed"],
                "shape": "list",
                "source": "ui.widgets_values",
                "has_dict_rows": False,
                "length": 2,
            },
        }
    )

    node = wf.nodes["1"]
    assert node.raw_widgets is not None
    assert node.raw_widgets.values == [7, "fixed"]
    assert node.raw_widgets.length == 2
    assert "raw_widgets" not in node.metadata


def test_vibe_shape_decodes_rich_node_raw_widgets_payload() -> None:
    """The rich decoder turns a serialized RawWidgetPayload into node.raw_widgets
    and preserves node metadata._ui verbatim (lossless envelope decode)."""
    rich_ui = {
        "_ui": {
            "id": 1,
            "type": "PrimitiveInt",
            "widgets_values": [7, "fixed"],
        }
    }
    wf = from_envelope(
        {
            "id": "test",
            "vibecomfy_format_version": "1.0",
            "compiled_api": {
                "1": {
                    "class_type": "PrimitiveInt",
                    "inputs": {"widget_0": 7, "widget_1": "fixed"},
                }
            },
            "nodes": {
                "1": {
                    "id": "1",
                    "class_type": "PrimitiveInt",
                    "inputs": {},
                    "widgets": {"widget_0": 7, "widget_1": "fixed"},
                    "metadata": rich_ui,
                    "uid": "1",
                    "raw_widgets": {
                        "values": [7, "fixed"],
                        "shape": "list",
                        "source": "ui.widgets_values",
                        "has_dict_rows": False,
                        "length": 2,
                    },
                }
            },
            "edges": [],
            "inputs": {},
            "outputs": [],
            "requirements": {},
            "source": {"id": "test"},
            "strict_types": False,
        }
    )

    node = wf.nodes["1"]
    assert node.raw_widgets is not None
    assert node.raw_widgets.values == [7, "fixed"]
    assert node.raw_widgets.length == 2
    assert node.raw_widgets.shape == "list"
    # metadata._ui is preserved verbatim (plus the provenance stamp).
    assert node.metadata["_ui"] == rich_ui["_ui"]
    assert node.metadata["provenance"] == "untrusted_source"

def test_vibe_shape_carries_dynamic_dict_raw_ui_for_widget_pin() -> None:
    wf = from_envelope(
        {
            "id": "test",
            "vibecomfy_format_version": "1.0",
            "compiled_api": {
                "81": {
                    "class_type": "VHS_SplitImages",
                    "inputs": {"images": ["105", 0], "split_index": 24},
                }
            },
            "nodes": {
                "81": {
                    "id": "81",
                    "class_type": "VHS_SplitImages",
                    "inputs": {},
                    "widgets": {"split_index": 24},
                    "uid": "81",
                    "raw_widgets": {
                        "values": {"split_index": 24},
                        "shape": "dict",
                        "source": "ui.widgets_values",
                        "has_dict_rows": True,
                        "length": 1,
                    },
                    "metadata": {
                        "_ui": {
                            "id": 81,
                            "type": "VHS_SplitImages",
                            "pos": [1075, 1136],
                            "size": [315, 118],
                            "flags": {},
                            "order": 28,
                            "mode": 0,
                            "inputs": [{"name": "images", "type": "IMAGE", "link": 198}],
                            "outputs": [{"name": "IMAGE_A", "type": "IMAGE", "links": []}],
                            "properties": {"Node name for S&R": "VHS_SplitImages"},
                            "widgets_values": {"split_index": 24},
                        }
                    },
                }
            },
            "edges": [],
            "inputs": {},
            "outputs": [],
            "requirements": {},
            "source": {"id": "test"},
            "strict_types": False,
        }
    )

    node = wf.nodes["81"]
    assert node.raw_widgets is not None
    assert node.raw_widgets.values == {"split_index": 24}
    assert node.metadata["_ui"]["widgets_values"] == {"split_index": 24}
    assert node.metadata["_ui"]["inputs"][0]["link"] == 198


# ── Case 3: absent → metadata key unset (never guessed) ──────────────────────


def test_control_after_generate_absent_leaves_metadata_unset() -> None:
    wf = _workflow_from_node(_ksampler_api_node())
    assert "control_after_generate" not in wf.nodes["1"].metadata, (
        "control_after_generate must not be guessed when absent from source"
    )


# ── Case 4a: compile("api") excludes control_after_generate ──────────────────


def test_compile_api_excludes_control_after_generate() -> None:
    """compile('api') must not include control_after_generate even when metadata carries it."""
    wf = _workflow_from_node(_ksampler_api_node(control="randomize"))
    assert wf.nodes["1"].metadata.get("control_after_generate") == "randomize", "precondition: metadata captured"
    compiled = wf.compile("api")
    assert "control_after_generate" not in compiled.get("1", {}).get("inputs", {}), (
        "compile('api') must filter control_after_generate via _is_ui_only_prompt_input"
    )


# ── Case 4b: compile("api") byte-identical with and without the capture ───────


def test_compile_api_byte_identical_with_and_without_control_capture() -> None:
    """compile('api') output is identical regardless of control_after_generate presence.

    This is the guard asserting the T2 ingest change leaves the compiled API dict
    byte-for-byte unchanged: a node with control_after_generate captured in metadata
    compiles identically to the same node without it at all.
    """
    wf_without = _workflow_from_node(_ksampler_api_node())
    wf_with = _workflow_from_node(_ksampler_api_node(control="randomize"))

    compiled_without = wf_without.compile("api")
    compiled_with = wf_with.compile("api")

    assert json.dumps(compiled_without, sort_keys=True) == json.dumps(compiled_with, sort_keys=True), (
        "compile('api') output must be byte-for-byte identical with and without "
        "control_after_generate — the ingest metadata capture must not alter the compiled dict"
    )


# ═══════════════════════════════════════════════════════════════════════════════
# T6 — Identity capture & determinism on the flat walking-skeleton fixture
# ═══════════════════════════════════════════════════════════════════════════════


def _load_flat_wf():
    """Load the flat.json walking-skeleton fixture → VibeWorkflow (cached helper)."""
    import json as _json

    with open("tests/fixtures/walking_skeleton/flat.json") as fh:
        raw = _json.load(fh)
    return from_ui(raw)


def test_flat_every_node_has_nonempty_uid_equal_to_litegraph_id() -> None:
    """Every node gets a non-empty uid equal to its source litegraph id."""
    wf = _load_flat_wf()
    raw = json.load(open("tests/fixtures/walking_skeleton/flat.json"))
    raw_ids = {str(n["id"]) for n in raw["nodes"]}

    for nid, node in wf.nodes.items():
        assert node.uid, f"node {nid} has empty uid"
        assert node.uid in raw_ids, f"node {nid} uid {node.uid!r} not in raw ids {raw_ids}"
        assert node.uid == nid, (
            f"node {nid} uid {node.uid!r} does not equal its own litegraph id {nid}"
        )


def test_flat_pre_existing_vibecomfy_uid_read_back_not_fresh_mint() -> None:
    """A node with pre-existing properties['vibecomfy_uid'] reads that value back."""
    import json as _json

    raw = _json.load(open("tests/fixtures/walking_skeleton/flat.json"))
    # Stamp a synthetic vibecomfy_uid onto KSampler (id=5) properties
    for node in raw["nodes"]:
        if node["id"] == 5:
            node.setdefault("properties", {})["vibecomfy_uid"] = "custom-ksampler-uuid"

    wf = from_ui(raw)
    ksampler = wf.nodes["5"]
    assert ksampler.uid == "custom-ksampler-uuid", (
        f"Pre-existing vitecomfy_uid not preserved: got {ksampler.uid!r}"
    )


def test_flat_pos_size_reachable_via_metadata_ui() -> None:
    """Captured pos/size are reachable via metadata['_ui']."""
    wf = _load_flat_wf()
    raw = json.load(open("tests/fixtures/walking_skeleton/flat.json"))
    raw_by_id = {str(n["id"]): n for n in raw["nodes"]}

    for nid, node in wf.nodes.items():
        _ui = node.metadata.get("_ui")
        assert isinstance(_ui, dict), f"node {nid} missing _ui metadata"
        assert "pos" in _ui, f"node {nid} _ui missing pos"
        assert "size" in _ui, f"node {nid} _ui missing size"
        expected = raw_by_id[nid]
        assert _ui["pos"] == expected["pos"], (
            f"node {nid} pos mismatch: {_ui['pos']} != {expected['pos']}"
        )
        assert _ui["size"] == expected["size"], (
            f"node {nid} size mismatch: {_ui['size']} != {expected['size']}"
        )
        assert node.pos == [float(coord) for coord in expected["pos"]]
        assert node.size == [float(coord) for coord in expected["size"]]


def test_flat_determinism_same_source_identical_uids() -> None:
    """Same source → identical uids across two ingests."""
    wf1 = _load_flat_wf()
    wf2 = _load_flat_wf()

    for nid in sorted(wf1.nodes.keys(), key=lambda x: int(x) if x.isdigit() else 0):
        assert nid in wf2.nodes, f"node {nid} missing from second ingest"
        assert wf1.nodes[nid].uid == wf2.nodes[nid].uid, (
            f"node {nid}: non-deterministic uid {wf1.nodes[nid].uid!r} vs {wf2.nodes[nid].uid!r}"
        )


# ── T4: mode/flags/color/bgcolor retention (K3 invariant) ────────────────────


def _node_with_mode(mode: int = 4, **extra_vis: object) -> dict:
    """API-format node with _ui carrying litegraph visual fields."""
    _ui: dict = {"id": 1, "mode": mode}
    for k, v in extra_vis.items():
        _ui[k] = v
    return {"class_type": "KSampler", "inputs": {"seed": 1}, "_ui": _ui}


def _node_without_mode() -> dict:
    return {"class_type": "KSampler", "inputs": {"seed": 1}}


def test_mode_captured_from_pure_python_path() -> None:
    """Pure-Python path: mode:4 lands on the first-class VibeNode.mode field."""
    raw_ui = {
        "nodes": [
            {
                "id": 1,
                "type": "KSampler",
                "mode": 4,
                "inputs": [],
                "widgets_values": [42, "fixed", 20, 7.0, "euler", "normal", 1.0],
            }
        ],
        "links": [],
    }
    from vibecomfy.ingest.normalize import normalize_to_api
    api = normalize_to_api(raw_ui, use_comfy_converter=False)
    wf = from_api(api)
    from vibecomfy.workflow import NodeMode
    assert wf.nodes["1"].mode is NodeMode.BYPASSED
    # _ui.mode is left in place so emit_ui_json furniture stays intact.
    assert wf.nodes["1"].metadata["_ui"]["mode"] == 4
    # No duplicate furniture copy is written on new ingests.
    assert "mode" not in wf.nodes["1"].metadata


def test_mode_captured_from_comfy_converter_path() -> None:
    """Comfy-converter path: mode:4 in _merge_slim_ui lands on VibeNode.mode."""
    # Simulate the result of convert_ui_to_api + _merge_slim_ui by providing
    # an API-format node that already has a slim _ui with mode set.
    api_node = _node_with_mode(mode=4)
    wf = from_api({"1": api_node})
    from vibecomfy.workflow import NodeMode
    assert wf.nodes["1"].mode is NodeMode.BYPASSED
    assert wf.nodes["1"].metadata["_ui"]["mode"] == 4
    assert "mode" not in wf.nodes["1"].metadata


def test_flags_color_bgcolor_captured() -> None:
    """flags, color, bgcolor are also captured into metadata."""
    api_node = _node_with_mode(mode=0, flags={"pinned": True}, color="#ff0000", bgcolor="#000000")
    wf = from_api({"1": api_node})
    assert wf.nodes["1"].metadata.get("flags") == {"pinned": True}
    assert wf.nodes["1"].metadata.get("color") == "#ff0000"
    assert wf.nodes["1"].metadata.get("bgcolor") == "#000000"


def test_mode_absent_leaves_field_zero_and_metadata_unset() -> None:
    """Nodes with no mode field get semantic enabled mode and no metadata key."""
    wf = from_api({"1": _node_without_mode()})
    from vibecomfy.workflow import NodeMode
    assert wf.nodes["1"].mode is NodeMode.ENABLED
    assert "mode" not in wf.nodes["1"].metadata


def test_mode_does_not_enter_inputs_or_widgets() -> None:
    """mode must never appear in node.inputs or node.widgets (K3 invariant)."""
    api_node = _node_with_mode(mode=4)
    wf = from_api({"1": api_node})
    node = wf.nodes["1"]
    from vibecomfy.workflow import NodeMode
    assert node.mode is NodeMode.BYPASSED
    assert "mode" not in node.inputs
    assert "mode" not in node.widgets


def test_compile_api_honors_ingest_captured_mode() -> None:
    """mode is first-class: ingest-captured mode=4 bypasses the node at compile.

    The pre-P10 decoupling (captured mode never tripping compile) existed only
    because mode was not a schema field.  The field is now the compile signal:
    a mode=4 node is dropped/bypassed, while mode=0 compiles identically to
    an absent mode.
    """
    import json

    wf_bypassed = from_api({"1": _node_with_mode(mode=4)})
    wf_zero = from_api({"1": _node_with_mode(mode=0)})
    wf_absent = from_api({"1": _node_without_mode()})

    assert "1" not in wf_bypassed.compile("api"), "mode=4 node must be bypassed"

    compiled_zero = json.dumps(wf_zero.compile(), sort_keys=True)
    compiled_absent = json.dumps(wf_absent.compile(), sort_keys=True)
    assert compiled_zero == compiled_absent, (
        "compile('api') output must be identical for mode=0 vs absent mode"
    )


# ══════════════════════════════════════════════════════════════════════════════
# T19 — comfy_converter_strict parameter semantics (offline, no comfy needed)
# ══════════════════════════════════════════════════════════════════════════════

# Minimal UI-shaped workflow usable as a normalize_to_api input.
_MINIMAL_UI_RAW: dict = {
    "nodes": [{"id": 1, "type": "SaveImage", "inputs": [], "widgets_values": ["output"]}],
    "links": [],
}


def test_live_and_offline_ui_ingest_copy_identical_first_class_geometry() -> None:
    from unittest.mock import MagicMock, patch

    from vibecomfy.comfy_backend import ComfyCompatibility

    raw = {
        "nodes": [
            {
                "id": 1,
                "type": "SaveImage",
                "inputs": [],
                "pos": [10, 20.5],
                "size": [300.25, 180],
            }
        ],
        "links": [],
    }
    converted = {"1": {"class_type": "SaveImage", "inputs": {}}}
    fake_module = MagicMock()
    fake_module.convert_ui_to_api = MagicMock(return_value=deepcopy(converted))
    compatible = ComfyCompatibility(
        ok=True,
        reason_code="ok",
        expected={"commit": "expected", "version": "pinned"},
        actual={"commit": "expected", "version": None},
        safe_families=[],
    )

    offline = from_ui(raw, use_comfy_converter=False)
    with patch.dict(
        "sys.modules",
        {
            "comfy": MagicMock(),
            "comfy.component_model": MagicMock(),
            "comfy.component_model.workflow_convert": fake_module,
        },
    ), patch(
        "vibecomfy.ingest.normalize.check_comfy_compatibility",
        return_value=compatible,
    ):
        live = from_ui(raw)

    assert live.nodes["1"].pos == offline.nodes["1"].pos == [10.0, 20.5]
    assert live.nodes["1"].size == offline.nodes["1"].size == [300.25, 180.0]
    raw["nodes"][0]["pos"][0] = 999
    raw["nodes"][0]["size"][0] = 999
    assert live.nodes["1"].pos == offline.nodes["1"].pos == [10.0, 20.5]
    assert live.nodes["1"].size == offline.nodes["1"].size == [300.25, 180.0]


def test_api_ingest_tolerates_malformed_geometry_and_retains_raw_ui() -> None:
    raw_ui = {"pos": [1], "size": [float("inf"), 2], "custom": {"keep": True}}
    workflow = from_api(
        {"1": {"class_type": "SaveImage", "inputs": {}, "_ui": raw_ui}}
    )
    node = workflow.nodes["1"]

    assert node.pos is None
    assert node.size is None
    assert node.metadata["_ui"] == raw_ui
    assert node.metadata["_ui"] is not raw_ui


def test_comfy_converter_strict_absent_comfy_falls_through_to_offline() -> None:
    """comfy_converter_strict=True with comfy absent: import guard skips cleanly.

    When ``use_comfy_converter=True`` (default) but the comfy package cannot be
    imported, the ImportError guard fires before strict mode is ever consulted.
    The call must succeed by falling through to the offline converter — no
    exception propagated, result is a valid API dict.
    """
    from unittest.mock import patch
    from vibecomfy.ingest.normalize import normalize_to_api

    # Simulate comfy being absent by making the import raise ImportError.
    with patch.dict("sys.modules", {"comfy": None, "comfy.component_model": None,
                                    "comfy.component_model.workflow_convert": None}):
        result = normalize_to_api(_MINIMAL_UI_RAW, comfy_converter_strict=True)

    assert isinstance(result, dict), "offline fallback must produce a dict"
    assert "1" in result, "offline result must contain the single node"


def test_comfy_converter_strict_no_op_when_use_comfy_converter_false() -> None:
    """comfy_converter_strict is a no-op when use_comfy_converter=False.

    When the comfy converter is disabled entirely (``use_comfy_converter=False``),
    the strict flag must have no effect — the call succeeds using the offline
    converter regardless of the flag value.
    """
    from vibecomfy.ingest.normalize import normalize_to_api

    result_default = normalize_to_api(
        _MINIMAL_UI_RAW, use_comfy_converter=False, comfy_converter_strict=False
    )
    result_strict = normalize_to_api(
        _MINIMAL_UI_RAW, use_comfy_converter=False, comfy_converter_strict=True
    )

    import json
    assert json.dumps(result_default, sort_keys=True) == json.dumps(result_strict, sort_keys=True), (
        "comfy_converter_strict must be a no-op when use_comfy_converter=False — "
        "both calls must produce identical output"
    )


def test_comfy_converter_default_raises_when_converter_errors() -> None:
    """Default normalize_to_api() is strict when convert_ui_to_api raises.

    When comfy IS importable but ``convert_ui_to_api`` raises an exception, the
    default call must propagate that exception rather than silently falling back
    to the offline converter.
    """
    from unittest.mock import MagicMock, patch
    from vibecomfy.comfy_backend import ComfyCompatibility
    from vibecomfy.ingest.normalize import normalize_to_api

    failing_converter = MagicMock(side_effect=RuntimeError("converter_exploded"))
    fake_module = MagicMock()
    fake_module.convert_ui_to_api = failing_converter
    compatible = ComfyCompatibility(
        ok=True,
        reason_code="ok",
        expected={"commit": "expected", "version": "pinned"},
        actual={"commit": "expected", "version": None},
        safe_families=[],
    )

    with patch.dict("sys.modules", {
        "comfy": MagicMock(),
        "comfy.component_model": MagicMock(),
        "comfy.component_model.workflow_convert": fake_module,
    }), patch("vibecomfy.ingest.normalize.check_comfy_compatibility", return_value=compatible):
        try:
            normalize_to_api(_MINIMAL_UI_RAW)
        except RuntimeError as exc:
            assert "converter_exploded" in str(exc)
        else:
            raise AssertionError(
                "Expected RuntimeError to propagate by default when "
                "convert_ui_to_api raises"
            )


def test_comfy_converter_strict_false_tolerant_when_converter_errors() -> None:
    """comfy_converter_strict=False keeps the explicit tolerant fallback path.

    When comfy IS importable but ``convert_ui_to_api`` raises, the explicit
    ``comfy_converter_strict=False`` opt-out must still fall through to the
    offline converter.
    """
    from unittest.mock import MagicMock, patch
    from vibecomfy.ingest.normalize import normalize_to_api

    failing_converter = MagicMock(side_effect=RuntimeError("converter_exploded"))
    fake_module = MagicMock()
    fake_module.convert_ui_to_api = failing_converter

    with patch.dict("sys.modules", {
        "comfy": MagicMock(),
        "comfy.component_model": MagicMock(),
        "comfy.component_model.workflow_convert": fake_module,
    }), pytest.warns(UserWarning, match="falling back to the offline normalizer"):
        result = normalize_to_api(_MINIMAL_UI_RAW, comfy_converter_strict=False)

    assert isinstance(result, dict), "offline fallback must produce a dict"
    assert "1" in result, "offline result must contain the single node"


def test_comfy_converter_strict_surfaces_version_skew_before_converter_exec() -> None:
    """Strict live-converter paths fence on skew before calling convert_ui_to_api."""
    from unittest.mock import MagicMock, patch

    from vibecomfy.comfy_backend import ComfyCompatibility, ComfyCompatibilityError
    from vibecomfy.ingest.normalize import normalize_to_api

    converter = MagicMock(side_effect=RuntimeError("raw_traceback_should_not_escape"))
    fake_module = MagicMock()
    fake_module.convert_ui_to_api = converter
    mismatch = ComfyCompatibility(
        ok=False,
        reason_code="comfyui_version_skew",
        expected={"commit": "expected", "version": "pinned"},
        actual={"commit": "actual", "version": "other"},
        safe_families=[],
    )

    with patch.dict("sys.modules", {
        "comfy": MagicMock(),
        "comfy.component_model": MagicMock(),
        "comfy.component_model.workflow_convert": fake_module,
    }), patch("vibecomfy.ingest.normalize.check_comfy_compatibility", return_value=mismatch):
        with pytest.raises(ComfyCompatibilityError, match="comfyui_version_skew") as excinfo:
            normalize_to_api(_MINIMAL_UI_RAW, comfy_converter_strict=True)

    converter.assert_not_called()
    assert excinfo.value.compatibility == mismatch


def test_comfy_converter_lenient_skew_falls_back_offline_without_converter_exec() -> None:
    """Lenient live-converter paths still skip converter execution on version skew."""
    from unittest.mock import MagicMock, patch

    from vibecomfy.comfy_backend import ComfyCompatibility
    from vibecomfy.ingest.normalize import normalize_to_api

    converter = MagicMock(side_effect=RuntimeError("raw_traceback_should_not_escape"))
    fake_module = MagicMock()
    fake_module.convert_ui_to_api = converter
    mismatch = ComfyCompatibility(
        ok=False,
        reason_code="comfyui_version_skew",
        expected={"commit": "expected", "version": "pinned"},
        actual={"commit": "actual", "version": "other"},
        safe_families=[],
    )

    with patch.dict("sys.modules", {
        "comfy": MagicMock(),
        "comfy.component_model": MagicMock(),
        "comfy.component_model.workflow_convert": fake_module,
    }), patch("vibecomfy.ingest.normalize.check_comfy_compatibility", return_value=mismatch), pytest.warns(
        UserWarning, match="comfyui_version_skew"
    ):
        result = normalize_to_api(_MINIMAL_UI_RAW, comfy_converter_strict=False)

    converter.assert_not_called()
    assert isinstance(result, dict)
    assert "1" in result


@pytest.mark.parametrize(
    "bad_node",
    [
        {},
        {"id": None},
        {"id": True},
        {"id": 1.0},
        {"id": "  "},
    ],
)
def test_raw_ui_node_identity_rejected_before_offline_normalization(
    bad_node: dict[str, object],
) -> None:
    raw = {"nodes": [bad_node], "links": []}

    with pytest.raises(ValueError, match=r"node 0: .*id"):
        normalize_to_api(raw, use_comfy_converter=False)


def test_raw_ui_node_identity_rejected_before_live_converter() -> None:
    from unittest.mock import MagicMock, patch

    from vibecomfy.comfy_backend import ComfyCompatibility

    converter = MagicMock(return_value={})
    fake_module = MagicMock()
    fake_module.convert_ui_to_api = converter
    compatible = ComfyCompatibility(
        ok=True,
        reason_code="ok",
        expected={"commit": "expected", "version": "pinned"},
        actual={"commit": "expected", "version": None},
        safe_families=[],
    )
    raw = {
        "nodes": [{"id": 1, "type": "SaveImage"}, {"id": "1", "type": "SaveImage"}],
        "links": [],
    }

    with patch.dict(
        "sys.modules",
        {
            "comfy": MagicMock(),
            "comfy.component_model": MagicMock(),
            "comfy.component_model.workflow_convert": fake_module,
        },
    ), patch(
        "vibecomfy.ingest.normalize.check_comfy_compatibility",
        return_value=compatible,
    ):
        with pytest.raises(ValueError, match="duplicate canonical id '1'"):
            normalize_to_api(raw)

    converter.assert_not_called()


def test_raw_ui_node_identity_accepts_integer_and_string_ids_on_both_paths() -> None:
    raw = {
        "nodes": [
            {"id": 1, "type": "SaveImage", "inputs": [], "widgets_values": []},
            {"id": "named", "type": "SaveImage", "inputs": [], "widgets_values": []},
        ],
        "links": [],
    }

    offline = normalize_to_api(raw, use_comfy_converter=False)
    assert set(offline) == {"1", "named"}

    from unittest.mock import MagicMock, patch

    from vibecomfy.comfy_backend import ComfyCompatibility

    converted = {
        "1": {"class_type": "SaveImage", "inputs": {}},
        "named": {"class_type": "SaveImage", "inputs": {}},
    }
    fake_module = MagicMock()
    fake_module.convert_ui_to_api = MagicMock(return_value=deepcopy(converted))
    compatible = ComfyCompatibility(
        ok=True,
        reason_code="ok",
        expected={"commit": "expected", "version": "pinned"},
        actual={"commit": "expected", "version": None},
        safe_families=[],
    )
    with patch.dict(
        "sys.modules",
        {
            "comfy": MagicMock(),
            "comfy.component_model": MagicMock(),
            "comfy.component_model.workflow_convert": fake_module,
        },
    ), patch(
        "vibecomfy.ingest.normalize.check_comfy_compatibility",
        return_value=compatible,
    ):
        live = normalize_to_api(raw)

    assert set(live) == {"1", "named"}


# ═══════════════════════════════════════════════════════════════════════════════
# B02-C1 — lossless rich-envelope decode (serialized Vibe → IR → canonical UI)
# ═══════════════════════════════════════════════════════════════════════════════

_CORPUS_90A1D5 = (
    Path(__file__).resolve().parent
    / "fixtures/b02_corpus_mini/90a1d5ff9044902e.json"
)


def _load_90a1d5() -> dict:
    return json.loads(_CORPUS_90A1D5.read_text(encoding="utf-8"))


def _ui_projection(ui: dict) -> dict:
    """Deterministic projection of a canonical UI envelope for idempotence compare."""
    nodes = sorted(
        (
            node["id"],
            node["type"],
            node.get("mode"),
            (node.get("properties") or {}).get("vibecomfy_uid"),
            json.dumps(node.get("widgets_values"), sort_keys=True),
        )
        for node in ui.get("nodes", [])
    )
    links = sorted((link[1], link[2], link[3], link[4]) for link in ui.get("links", []))
    return {
        "node_count": len(nodes),
        "nodes": nodes,
        "link_count": len(links),
        "links": links,
        "groups": ui.get("groups", []),
    }


def test_vibe_rich_ingest_preserves_90a1d5() -> None:
    """The rich envelope decodes fully and derives its two-node execution view fresh."""
    raw = _load_90a1d5()
    assert "compiled_api" not in raw

    wf = from_envelope(raw)

    assert len(wf.nodes) == 15
    assert len(wf.edges) == 10
    assert len(wf.outputs) == len(raw["outputs"])
    assert wf.id == raw["id"]
    assert wf.source.id == raw["source"]["id"]
    assert wf.strict_types is False
    assert wf.metadata["external_workflow"] is True
    assert len(wf.compile("api")) == 2

    uids = [node.uid for node in wf.nodes.values()]
    assert len(set(uids)) == 15, "uids must all be distinct"
    assert all(isinstance(uid, str) and uid.strip() for uid in uids)

    modes = Counter(node.mode for node in wf.nodes.values())
    assert dict(modes) == {4: 9, 0: 6}

    assert wf.nodes["10"].class_type == "TripoRefineNode"
    assert wf.nodes["10"].uid == raw["nodes"]["10"]["uid"]

    # Lossless: every rich node's uid/metadata._ui/inputs/widgets decode verbatim.
    for nid, node in wf.nodes.items():
        rich = raw["nodes"][nid]
        assert node.uid == rich["uid"], f"node {nid}: uid not preserved exactly"
        assert node.class_type == rich["class_type"], f"node {nid}: class_type mismatch"
        assert node.metadata["_ui"] == rich["metadata"]["_ui"], (
            f"node {nid}: metadata._ui not preserved verbatim"
        )
        assert node.metadata["provenance"] == "untrusted_source"
        assert node.inputs == rich["inputs"]
        assert node.widgets == rich["widgets"]

    # Canonical UI carries every rich node with the same id/class/mode/uid projection.
    _, normalized = ingest_workflow_and_ui(raw)
    assert len(normalized["nodes"]) == 15
    assert len(normalized["links"]) == 10
    by_id = {str(node["id"]): node for node in normalized["nodes"]}
    assert set(by_id) == set(raw["nodes"])
    for nid, rich in raw["nodes"].items():
        ui_node = by_id[nid]
        assert ui_node["type"] == rich["class_type"]
        assert ui_node["mode"] == rich["metadata"]["_ui"]["mode"]
        assert (ui_node.get("properties") or {})["vibecomfy_uid"] == rich["uid"]


def test_vibe_rich_ingest_ignores_optional_compiled_api_evidence() -> None:
    """Rich structure remains authoritative without stored execution evidence or with bad evidence."""
    raw = _load_90a1d5()

    assert "compiled_api" not in raw
    assert len(from_envelope(raw).nodes) == 15

    malformed_evidence = deepcopy(raw)
    malformed_evidence["compiled_api"] = {"10": "not-an-api-node"}
    workflow = from_envelope(malformed_evidence)
    assert len(workflow.nodes) == 15
    assert workflow.nodes["10"].class_type == "TripoRefineNode"


def test_public_loaders_preserve_rich_envelope_90a1d5() -> None:
    """load_workflow_any / load_port_source decode envelopes losslessly (P1).

    Public loaders must return the full 15-node IR, not the 2-node compile
    view: they decode the envelope directly instead of compile-then-reingest.
    The execution view (compile("api")) is unchanged at 2 nodes.
    """
    from vibecomfy.cli_loader import load_workflow_any
    from vibecomfy.porting.workbench import load_port_source

    corpus = str(_CORPUS_90A1D5)

    wf = load_workflow_any(corpus)
    assert len(wf.nodes) == 15
    assert wf.nodes["10"].class_type == "TripoRefineNode"
    assert len(wf.compile("api")) == 2

    loaded = load_port_source(corpus)
    assert len(loaded.workflow.nodes) == 15
    assert loaded.workflow.nodes["10"].class_type == "TripoRefineNode"
    assert len(loaded.workflow.compile("api")) == 2
    assert loaded.source_kind in {"indexed_json", "raw_json"}


def test_vibe_rich_ingest_is_idempotent() -> None:
    """rich->UI and UI->IR->UI produce identical projections (nodes, edges, widgets, groups)."""
    raw = _load_90a1d5()

    _, ui1 = ingest_workflow_and_ui(raw)  # rich -> UI
    assert len(ui1["nodes"]) == 15 and len(ui1["links"]) == 10

    # UI -> IR via the deterministic offline normalizer (the comfy converter
    # intentionally drops mode-4 bypassed nodes — ComfyUI semantics, unchanged).
    api2 = normalize_to_api(ui1, use_comfy_converter=False)
    wf2 = from_api(api2)
    assert len(wf2.nodes) == 15 and len(wf2.edges) == 10

    wf2.groups = deepcopy(ui1.get("groups"))
    ui2 = emit_ui_json(wf2, schema_provider=None)

    assert _ui_projection(ui1) == _ui_projection(ui2)


def test_vibe_rich_ingest_rejects_malformed_mixed_entries() -> None:
    """Malformed/mixed rich entries raise ValueError; no partial graph is returned."""
    raw = _load_90a1d5()

    mixed_nodes = deepcopy(raw)
    mixed_nodes["nodes"]["999"] = "not-a-node"
    with pytest.raises(ValueError, match="must be mappings"):
        from_envelope(mixed_nodes)

    key_mismatch = deepcopy(raw)
    key_mismatch["nodes"]["10"]["id"] = "11"
    with pytest.raises(ValueError, match="must equal node.id"):
        from_envelope(key_mismatch)

    blank_uid = deepcopy(raw)
    blank_uid["nodes"]["10"]["uid"] = "  "
    with pytest.raises(ValueError, match="uid must be a nonblank string"):
        from_envelope(blank_uid)

    negative_length = deepcopy(raw)
    negative_length["nodes"]["10"]["raw_widgets"]["length"] = -1
    with pytest.raises(ValueError, match="nonnegative integer"):
        from_envelope(negative_length)

    non_mapping_edges = deepcopy(raw)
    non_mapping_edges["edges"] = ["not-an-edge"]
    with pytest.raises(ValueError, match="must be mappings"):
        from_envelope(non_mapping_edges)


def test_vibe_rich_ingest_rejects_dangling_endpoint_edges() -> None:
    """Edges referencing endpoint node ids absent from nodes raise ValueError."""
    raw = _load_90a1d5()

    dangling_from = deepcopy(raw)
    dangling_from["edges"] = [
        {"from_node": "999", "from_output": "0", "to_node": "3", "to_input": "model_task_id"}
    ]
    with pytest.raises(ValueError, match="must exist in nodes"):
        from_envelope(dangling_from)

    dangling_to = deepcopy(raw)
    dangling_to["edges"] = [
        {"from_node": "3", "from_output": "0", "to_node": "424242", "to_input": "model_file"}
    ]
    with pytest.raises(ValueError, match="must exist in nodes"):
        from_envelope(dangling_to)

    blank_endpoint = deepcopy(raw)
    blank_endpoint["edges"] = [
        {"from_node": "", "from_output": "0", "to_node": "3", "to_input": "model_task_id"}
    ]
    with pytest.raises(ValueError, match="from_node must be a nonblank string"):
        from_envelope(blank_endpoint)


def test_vibe_rich_ingest_rejects_incomplete_envelope() -> None:
    """A vibe envelope missing required top-level sections is rejected, never partial."""
    raw = _load_90a1d5()

    for field in ("source", "requirements", "inputs", "edges"):
        partial = deepcopy(raw)
        del partial[field]
        with pytest.raises(ValueError):
            from_envelope(partial)

    bad_outputs = deepcopy(raw)
    bad_outputs["outputs"] = "not-a-list"
    with pytest.raises(ValueError, match="outputs.*must be a list"):
        from_envelope(bad_outputs)

    bad_strict = deepcopy(raw)
    bad_strict["strict_types"] = "yes"
    with pytest.raises(ValueError, match="strict_types must be a boolean"):
        from_envelope(bad_strict)


# ═══════════════════════════════════════════════════════════════════════════════
# P5 — VibeWorkflow.to_envelope / from_envelope (one writer, one fail-closed reader)
# ═══════════════════════════════════════════════════════════════════════════════


def test_to_envelope_from_envelope_round_trip_90a1d5() -> None:
    """to_envelope(from_envelope(90a1d5)) preserves 15/10/15 uids/modes; compile stays 2."""
    from vibecomfy.workflow import FORMAT_VERSION, VibeWorkflow, from_envelope

    raw = _load_90a1d5()
    wf = from_envelope(raw)
    assert len(wf.nodes) == 15
    assert len(wf.edges) == 10
    assert {node.uid for node in wf.nodes.values()} == {
        node.uid for node in wf.nodes.values()
    }
    assert all(node.uid.strip() for node in wf.nodes.values())
    assert dict(Counter(node.metadata.get("mode") for node in wf.nodes.values())) == {4: 9, 0: 6}

    envelope = wf.to_envelope()
    assert envelope["vibecomfy_format_version"] == FORMAT_VERSION
    assert "compiled_api" not in envelope
    assert len(envelope["nodes"]) == 15
    assert len(envelope["edges"]) == 10

    wf2 = VibeWorkflow.from_envelope(envelope)
    assert len(wf2.nodes) == 15
    assert len(wf2.edges) == 10
    assert {node.uid for node in wf2.nodes.values()} == {node.uid for node in wf.nodes.values()}
    assert dict(Counter(node.metadata.get("mode") for node in wf2.nodes.values())) == {4: 9, 0: 6}
    for nid, node in wf2.nodes.items():
        original = raw["nodes"][nid]
        assert node.uid == original["uid"]
        assert node.metadata["_ui"] == original["metadata"]["_ui"]
        assert node.inputs == original["inputs"]
        assert node.widgets == original["widgets"]
    assert len(wf2.compile("api")) == 2
    assert set(wf2.compile("api")) == {"3", "17"}


def test_from_envelope_hand_built_old_style_without_compiled_api() -> None:
    """A hand-built (old-style) envelope without compiled_api still decodes losslessly."""
    from vibecomfy.workflow import VibeWorkflow

    envelope = {
        "id": "hand-built",
        "vibecomfy_format_version": "1.0",
        "source": {"id": "hand-built", "source_type": "vibe", "path": None, "provenance": {}},
        "requirements": {
            "models": [],
            "custom_nodes": [],
            "missing_models": [],
            "missing_nodes": [],
            "unsupported": [],
        },
        "nodes": {
            "1": {
                "id": "1",
                "class_type": "CheckpointLoaderSimple",
                "pack": None,
                "inputs": {"ckpt_name": "model.safetensors"},
                "widgets": {},
                "metadata": {"_ui": {"mode": 0}, "mode": 0},
                "uid": "uid-loader",
            },
            "2": {
                "id": "2",
                "class_type": "PreviewImage",
                "pack": None,
                "inputs": {},
                "widgets": {},
                "metadata": {"_ui": {"mode": 4}, "mode": 4},
                "uid": "uid-preview",
            },
        },
        "edges": [
            {
                "from_node": "1",
                "from_output": "MODEL",
                "to_node": "2",
                "to_input": "images",
            }
        ],
        "inputs": {},
        "outputs": [{"node_id": "2", "output_type": "IMAGE"}],
        "metadata": {"note": "old-style"},
        "strict_types": False,
    }
    assert "compiled_api" not in envelope

    wf = VibeWorkflow.from_envelope(envelope)
    assert len(wf.nodes) == 2
    assert len(wf.edges) == 1
    assert wf.nodes["1"].uid == "uid-loader"
    assert wf.nodes["1"].inputs["ckpt_name"] == "model.safetensors"
    from vibecomfy.workflow import NodeMode
    assert wf.nodes["1"].mode is NodeMode.ENABLED
    assert wf.nodes["2"].mode is NodeMode.BYPASSED
    assert wf.nodes["2"].metadata["mode"] == 4
    assert wf.nodes["2"].metadata["_ui"]["mode"] == 4
    assert wf.outputs[0].node_id == "2"
    written = wf.to_envelope()
    assert "compiled_api" not in written
    assert written["nodes"]["1"]["uid"] == "uid-loader"
    # Law 1 door: an UNTOUCHED old-style envelope round-trips byte-identically
    # (wire form preserved — mode stays in the legacy metadata location rather
    # than being re-rendered as a first-class field).
    assert written == envelope
    assert written["nodes"]["2"]["metadata"]["mode"] == 4
    assert written["nodes"]["2"]["metadata"]["_ui"]["mode"] == 4


def test_envelope_first_class_mode_beats_stale_ui_and_missing_mode_uses_furniture() -> None:
    """Importer: semantic first-class mode is authoritative; furniture is a gap fill."""
    from vibecomfy.workflow import NodeMode, VibeWorkflow

    def _node(mode, ui_mode: int) -> dict:
        entry = {
            "id": "1",
            "class_type": "LoadImage",
            "pack": None,
            "inputs": {"image": "a.png"},
            "widgets": {},
            "metadata": {"_ui": {"mode": ui_mode}},
            "uid": "uid-1",
        }
        if mode is not None:
            entry["mode"] = mode
        return entry

    def _envelope(node: dict) -> dict:
        return {
            "id": "mode-authority",
            "source": {"id": "mode-authority"},
            "requirements": {},
            "nodes": {"1": node},
            "edges": [],
            "inputs": {},
            "outputs": [],
            "metadata": {},
            "strict_types": False,
        }

    enabled = VibeWorkflow.from_envelope(
        _envelope(_node(mode=NodeMode.ENABLED, ui_mode=4))
    )
    assert enabled.nodes["1"].mode is NodeMode.ENABLED
    assert "1" in enabled.compile("api")

    bypassed = VibeWorkflow.from_envelope(
        _envelope(_node(mode="bypassed", ui_mode=0))
    )
    assert bypassed.nodes["1"].mode is NodeMode.BYPASSED
    assert "1" not in bypassed.compile("api")

    legacy_envelope = _envelope(_node(mode=None, ui_mode=4))
    assert "mode" not in legacy_envelope["nodes"]["1"]
    legacy = VibeWorkflow.from_envelope(legacy_envelope)
    assert legacy.nodes["1"].mode is NodeMode.BYPASSED
    assert "1" not in legacy.compile("api")


def test_from_envelope_fails_closed_on_malformed_input() -> None:
    """from_envelope raises on malformed input; it never returns a partial graph."""
    from vibecomfy.workflow import VibeWorkflow

    good = {
        "id": "closed",
        "source": {"id": "closed"},
        "requirements": {},
        "nodes": {
            "1": {
                "id": "1",
                "class_type": "PreviewImage",
                "inputs": {},
                "widgets": {},
                "metadata": {},
                "uid": "uid-1",
            }
        },
        "edges": [],
        "inputs": {},
        "outputs": [],
    }
    assert len(VibeWorkflow.from_envelope(good).nodes) == 1

    blank_uid = deepcopy(good)
    blank_uid["nodes"]["2"] = {
        "id": "2",
        "class_type": "PreviewImage",
        "inputs": {},
        "widgets": {},
        "metadata": {},
        "uid": "",
    }
    with pytest.raises(ValueError, match="uid must be a nonblank string"):
        VibeWorkflow.from_envelope(blank_uid)

    mixed_node = deepcopy(good)
    mixed_node["nodes"]["2"] = "not-a-mapping"
    with pytest.raises(ValueError, match="node entries must be mappings"):
        VibeWorkflow.from_envelope(mixed_node)

    missing_source = deepcopy(good)
    del missing_source["source"]
    with pytest.raises(ValueError, match="source"):
        VibeWorkflow.from_envelope(missing_source)

    missing_requirements = deepcopy(good)
    del missing_requirements["requirements"]
    with pytest.raises(ValueError, match="requirements"):
        VibeWorkflow.from_envelope(missing_requirements)

    not_an_object = ["not", "an", "envelope"]
    with pytest.raises(ValueError, match="must be a JSON object"):
        VibeWorkflow.from_envelope(not_an_object)  # type: ignore[arg-type]


# ═══════════════════════════════════════════════════════════════════════════════
# P6 — named importers (from_envelope / from_ui / from_api)
# ═══════════════════════════════════════════════════════════════════════════════


def test_named_from_envelope_preserves_90a1d5() -> None:
    """The public ingest from_envelope door is lossless on the 90a1d5 fixture."""
    from vibecomfy.ingest import from_envelope

    raw = _load_90a1d5()
    wf = from_envelope(raw)
    assert len(wf.nodes) == 15
    assert len(wf.edges) == 10
    assert {node.uid for node in wf.nodes.values()} == {
        node.uid for node in wf.nodes.values()
    }
    assert dict(Counter(node.metadata.get("mode") for node in wf.nodes.values())) == {4: 9, 0: 6}
    assert len(wf.compile("api")) == 2
    assert set(wf.compile("api")) == {"3", "17"}


def _ir_projection(workflow) -> dict:
    return {
        "ids": sorted(workflow.nodes),
        "classes": {nid: node.class_type for nid, node in workflow.nodes.items()},
        "uids": {nid: node.uid for nid, node in workflow.nodes.items()},
        "inputs": {nid: node.inputs for nid, node in workflow.nodes.items()},
        "widgets": {nid: node.widgets for nid, node in workflow.nodes.items()},
        "edges": [
            (edge.from_node, edge.from_output, edge.to_node, edge.to_input)
            for edge in workflow.edges
        ],
    }


def test_from_ui_matches_ui_fixture_invariants() -> None:
    raw = json.loads(
        (Path(__file__).parent / "fixtures/reorganise/simple_text_to_image.json").read_text(
            encoding="utf-8"
        )
    )
    wf = from_ui(raw)
    assert _ir_projection(wf)["ids"]
    assert all(node.uid for node in wf.nodes.values())
    assert all(node.class_type for node in wf.nodes.values())


def test_from_api_matches_api_fixture_invariants() -> None:
    raw = json.loads(
        (Path(__file__).parent / "fixtures/reorganise/simple_text_to_image.json").read_text(
            encoding="utf-8"
        )
    )
    api = normalize_to_api(raw, use_comfy_converter=False)
    wf = from_api(api)
    assert _ir_projection(wf)["ids"]
    assert all(node.uid for node in wf.nodes.values())
    assert all(node.class_type for node in wf.nodes.values())


def test_ingest_workflow_and_ui_accepts_api_prompt_dict() -> None:
    """Agent Edit must accept a ComfyUI API-format prompt dict (node id -> node)."""
    api_prompt = {
        "107": {"class_type": "SaveImage", "inputs": {"images": ["108", 0]}},
        "108": {"class_type": "VAEDecode", "inputs": {}},
    }
    _, normalized = ingest_workflow_and_ui(api_prompt)
    node_ids = {node["id"] for node in normalized["nodes"]}
    assert node_ids == {107, 108}, node_ids
    assert normalized["links"], "API edges must become canonical UI links"


def test_ir_door_rejects_subgraph_fixture_native_boundary_payloads() -> None:
    path = Path(__file__).parent / "fixtures/agent_edit/subgraphed_wan_i2v.json"
    raw = json.loads(path.read_bytes())
    with pytest.raises(ValueError, match="unsupported_boundary_encoding"):
        from_ui(raw, source_path=str(path), use_comfy_converter=False)


def test_ir_door_exact_json_equality_across_the_spike_corpus() -> None:
    """Law 1: exact ``json.dumps`` equality for the three spike corpus files."""
    import warnings as _warnings

    from vibecomfy.porting.emit.ui import emit_ui_json as _emit

    corpus = [
        (
            Path(__file__).parent / "fixtures/b02_corpus_mini/90a1d5ff9044902e.json",
            "envelope",
        ),
        (
            Path(__file__).parent / "fixtures/agent_edit/subgraphed_wan_i2v.json",
            "ui",
        ),
        (
            Path(__file__).parent
            / ".."
            / "ready_templates/sources/custom_nodes/ltxvideo/runexx/LTX-2.3_Custom_Audio.json",
            "ui",
        ),
    ]
    for path, kind in corpus:
        raw = json.loads(path.read_bytes())
        if kind == "envelope":
            emitted = from_envelope(raw).to_envelope()
        else:
            if path.name == "subgraphed_wan_i2v.json":
                with pytest.raises(ValueError, match="unsupported_boundary_encoding"):
                    from_ui(raw, source_path=str(path), use_comfy_converter=False)
                continue
            workflow = from_ui(raw, source_path=str(path), use_comfy_converter=False)
            with _warnings.catch_warnings():
                _warnings.simplefilter("ignore")
                emitted = _emit(workflow)
        assert json.dumps(emitted, ensure_ascii=False, separators=(",", ":")) == json.dumps(
            raw, ensure_ascii=False, separators=(",", ":")
        ), path


# ═══════════════════════════════════════════════════════════════════════════════
# Batch 3 — one retained ingest authority
# ═══════════════════════════════════════════════════════════════════════════════


def _batch3_agent_state(tmp_path, graph, *, workflow=None):
    from vibecomfy.comfy_nodes.agent._frag_state import AgentEditState

    return AgentEditState(
        task="batch 3 acceptance",
        graph=graph,
        request_payload={},
        schema_provider=None,
        baseline_graph_hash=None,
        submit_graph_hash=None,
        submit_structural_graph_hash=None,
        submitted_client_graph_hash=None,
        submitted_client_structural_graph_hash=None,
        session_dir=tmp_path,
        turn_dir=tmp_path,
        request_path=tmp_path / "request.json",
        original_ui_path=tmp_path / "original.ui.json",
        before_py_path=tmp_path / "before.py",
        after_py_path=tmp_path / "after.py",
        projection_path=tmp_path / "projection.txt",
        model_request_path=tmp_path / "model_request.json",
        model_response_path=tmp_path / "model_response.json",
        candidate_ui_path=tmp_path / "candidate.ui.json",
        messages_path=tmp_path / "messages.jsonl",
        workflow=workflow,
    )


def test_batch3_same_workflow_object_crosses_ingest_into_state_and_session(
    tmp_path,
) -> None:
    """One IR across ingest: the door's VibeWorkflow object is retained on
    AgentEditState.workflow at allocation and reused (identity, not a copy) by
    the ingest stage and the EditSession — never rebuilt from raw JSON."""
    from vibecomfy.comfy_nodes.agent._frag_ingest import _stage_ingest_v2
    from vibecomfy.comfy_nodes.agent.contracts import TurnContext
    from vibecomfy.porting.edit.session import EditSession

    raw = deepcopy(_MINIMAL_UI_RAW)
    workflow, ui = ingest_workflow_and_ui(raw)
    assert ui == raw, "UI projection preserves the input values"
    assert ui is not raw, "UI projection is detached from the caller's raw input"
    ui["nodes"][0]["type"] = "MutatedProjection"
    assert raw["nodes"][0]["type"] == "SaveImage"
    assert workflow is not None

    state = _batch3_agent_state(tmp_path, raw, workflow=workflow)
    _stage_ingest_v2(state, TurnContext(session_id="b3-a", turn_id="t1"))
    assert state.workflow is workflow, (
        "ingest stage must reuse the retained IR, not rebuild it"
    )

    session = EditSession(raw, initial_workflow=workflow)
    assert session.workflow is workflow, (
        "EditSession must hold the retained IR object, not re-derive it"
    )


def test_batch3_agent_edit_state_workflow_allocated_exactly_once_and_reused(
    tmp_path,
) -> None:
    """AgentEditState.workflow is allocated exactly once (through the single
    named door) and reused across stages — a second stage call never rebuilds
    it and never re-runs the shape dispatch."""
    from vibecomfy.comfy_nodes.agent._frag_ingest import _stage_ingest, _stage_ingest_v2
    from vibecomfy.comfy_nodes.agent.contracts import TurnContext

    raw = deepcopy(_MINIMAL_UI_RAW)
    state = _batch3_agent_state(tmp_path, raw)  # no workflow yet
    context = TurnContext(session_id="b3-b", turn_id="t1")

    result = _stage_ingest_v2(state, context)
    assert result.ok
    allocated = state.workflow
    assert allocated is not None

    # Second stage (and a different ingest stage) reuse the same object.
    result2 = _stage_ingest_v2(state, TurnContext(session_id="b3-b", turn_id="t2"))
    assert result2.ok
    assert state.workflow is allocated, "workflow must be allocated exactly once"

    state2 = _batch3_agent_state(tmp_path, deepcopy(raw), workflow=allocated)
    _stage_ingest(state2, TurnContext(session_id="b3-b", turn_id="t3"))
    assert state2.workflow is allocated, "workflow must be reused across stages"


def test_native_typed_port_authority_survives_ui_envelope_and_ui_emit() -> None:
    from vibecomfy.schema import InputSpec, NodeSchema, OutputSpec

    class Provider:
        def get_schema(self, class_type):
            if class_type == "LoadImage":
                return NodeSchema(
                    "LoadImage", "core",
                    {"image": InputSpec("CHOICE", required=True, asset_kind="image")},
                    [OutputSpec("IMAGE", "IMAGE")],
                )
            return None

    raw = {
        "nodes": [{
            "id": 1, "type": "LoadImage", "mode": 0,
            "inputs": [{"name": "image", "type": "CHOICE", "shape": 7}],
            "outputs": [{"name": "IMAGE", "type": "IMAGE", "links": None}],
            "widgets_values": ["source.png"],
        }],
        "links": [],
    }
    workflow = from_ui(raw, schema_provider=Provider(), use_comfy_converter=False)
    node = workflow.nodes["1"]
    assert node.native_input_names == ["image"]
    assert node.native_input_types == ["CHOICE"]
    assert node.native_input_optional == [True]
    assert node.native_input_asset_kinds == ["image"]
    assert node.native_output_names == ["IMAGE"]
    assert node.native_output_types == ["IMAGE"]

    rebuilt = from_envelope(workflow.to_envelope())
    assert rebuilt.nodes["1"].native_input_types == ["CHOICE"]
    assert rebuilt.nodes["1"].native_input_optional == [True]
    assert rebuilt.nodes["1"].native_input_asset_kinds == ["image"]
    assert rebuilt.nodes["1"].native_output_types == ["IMAGE"]

    emitted = emit_ui_json(rebuilt, schema_provider=Provider())
    emitted_node = emitted["nodes"][0]
    assert emitted_node["inputs"] == [{
        "name": "image", "type": "CHOICE", "shape": 7,
    }]
    assert emitted_node["outputs"][0]["type"] == "IMAGE"


def test_native_typed_port_authority_rejects_misaligned_carriers() -> None:
    from vibecomfy.workflow import VibeNode

    with pytest.raises(ValueError, match="native_input_types length"):
        VibeNode(
            "1", "Node", native_input_names=["a", "b"],
            native_input_types=["IMAGE"],
        )
    with pytest.raises(ValueError, match="native_input_names"):
        VibeNode("1", "Node", native_input_optional=[True])


def test_native_choice_list_socket_type_normalizes_without_losing_widget_literal() -> None:
    raw = {
        "nodes": [{
            "id": 92,
            "type": "VHS_VideoCombine",
            "inputs": [{
                "name": "pix_fmt",
                "type": ["yuv420p", "yuv420p10le"],
                "widget": {"name": "pix_fmt"},
            }],
            "outputs": [],
            "widgets_values": ["yuv420p10le"],
        }],
        "links": [],
    }

    workflow = from_ui(raw, use_comfy_converter=False)
    node = workflow.nodes["92"]
    assert node.native_input_names == ["pix_fmt"]
    assert node.native_input_types == ["CHOICE"]
    assert node.inputs["pix_fmt"] == "yuv420p10le"
    assert node.raw_widgets is not None
    assert node.raw_widgets.values == ["yuv420p10le"]


@pytest.mark.parametrize("malformed", [[], [""], ["ok", 1], [True], [{}]])
def test_native_choice_list_socket_type_rejects_malformed_claims(malformed) -> None:
    raw = {
        "nodes": [{
            "id": 1, "type": "ChoiceNode",
            "inputs": [{"name": "choice", "type": malformed}],
            "outputs": [],
        }],
        "links": [],
    }
    with pytest.raises(ValueError, match="choice list must contain only nonblank strings"):
        from_ui(raw, use_comfy_converter=False)


def test_image_upload_schema_marker_survives_frozen_schema_payload() -> None:
    from copy import deepcopy

    from vibecomfy.porting.edit.admit import _validate_schema_payload_structure
    from vibecomfy.schema import NodeSchema, node_schema_from_payload, schema_payload_from_node_schema
    from vibecomfy.schema.types import SchemaSnapshotError
    from vibecomfy.schema.provider import _parse_input_spec

    spec = _parse_input_spec([[], {"image_upload": True}], required=True)
    assert spec.asset_kind == "image"
    payload = schema_payload_from_node_schema(
        "LoadImage", NodeSchema("LoadImage", "core", {"image": spec}, [])
    )
    assert payload["inputs"]["image"]["asset_kind"] == "image"
    restored = node_schema_from_payload("LoadImage", payload)
    assert restored.inputs["image"].asset_kind == "image"

    # The admission door accepts the complete canonical carrier while keeping
    # forged or malformed asset claims fail-closed.  Build only the nested
    # shell required by the structural validator so this test exercises the
    # same codec path used by real editor snapshots.
    provenance = {
        "source_provider": None, "source_path": None, "source_cache_path": None,
        "source_server_url": None, "source_package": None, "source_version": None,
        "source_hash": None, "confidence": 1.0, "conflicts": [],
        "ignored_evidence": [],
    }
    payload["widget_input_order"] = []
    payload["provenance"] = provenance
    snapshot_payload = {
        "contract_version": "schema-snapshot-v1",
        "identity": {
            "runtime_fingerprint": None, "cache_fingerprint": None,
            "request_fingerprint": None, "server_url": None,
        },
        "content_digest": "test-digest",
        "precedence": [], "selected_source": "test", "generation": 0,
        "conflicts": [], "timestamp": None, "version": "schema-snapshot-v1",
        "schemas": {"LoadImage": payload}, "missing_classes": [],
        "input_order": {"LoadImage": ["image"]}, "node_classes": {},
        "workflow_observation_authoritative": False,
        "ambient_lookup_forbidden": True,
    }
    _validate_schema_payload_structure(snapshot_payload, label="schema")

    for malformed in ("", "audio", True, 1, [], {}):
        tampered = deepcopy(snapshot_payload)
        tampered["schemas"]["LoadImage"]["inputs"]["image"]["asset_kind"] = malformed
        with pytest.raises(SchemaSnapshotError, match="canonical 'image' claim"):
            _validate_schema_payload_structure(tampered, label="schema")

    missing = deepcopy(snapshot_payload)
    del missing["schemas"]["LoadImage"]["inputs"]["image"]["asset_kind"]
    with pytest.raises(SchemaSnapshotError, match="incomplete or unknown fields"):
        _validate_schema_payload_structure(missing, label="schema")


def test_recursive_node_decodes_typed_optional_socket_carriers() -> None:
    from vibecomfy.workflow import _raw_recursive_node

    node = _raw_recursive_node({
        "id": "inner", "type": "Inner",
        "inputs": [{"name": "latent", "type": "LATENT", "shape": 7}],
        "outputs": [{"name": "LATENT", "type": "LATENT"}],
        "native_output_slots": [3, 0, 3],
    }, "inner")
    assert node.native_input_names == ["latent"]
    assert node.native_input_types == ["LATENT"]
    assert node.native_input_optional == [True]
    assert node.native_output_names == ["LATENT"]
    assert node.native_output_types == ["LATENT"]
    assert node.native_output_slots == [0, 3]
