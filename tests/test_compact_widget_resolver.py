from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

from vibecomfy.porting.edit.apply import apply_delta, resolve_delta
from vibecomfy.porting.edit.ops import parse_edit_delta
from vibecomfy.porting.edit.projection import ProjectionOptions, render_edit_projection
from vibecomfy.porting.emit.ui import (
    _build_widget_values,
    _widget_names_for_emission,
    derive_widget_shape_evidence,
)
from vibecomfy.porting.strict_ready import (
    HIDDEN_MODEL_FILENAME,
    STRICT_READY_UNRESOLVED_WIDGETS,
    validate_strict_ready_workflow,
)
from vibecomfy.porting.widget_shape_fence import (
    WidgetShapeDecision,
    WidgetShapeReason,
    decide_widget_shape,
)
from vibecomfy.porting.widgets.compact_resolver import (
    compact_widget_names_for_node,
    widget_index_for_field,
    widget_value_for_field,
)
from vibecomfy.porting.emit.ui import WidgetShapeEvidence
from vibecomfy.schema import get_authoring_schema_provider
from vibecomfy.workflow import RawWidgetPayload, VibeNode, VibeOutput, VibeWorkflow, WorkflowSource


ROOT = Path(__file__).resolve().parents[1]


def _corpus_node(path: str, node_id: str) -> VibeNode:
    data = json.loads((ROOT / path).read_text(encoding="utf-8"))
    node = data["nodes"][node_id]
    raw = node["raw_widgets"]
    return VibeNode(
        id=str(node["id"]),
        class_type=str(node["class_type"]),
        inputs=dict(node.get("inputs") or {}),
        widgets=dict(node.get("widgets") or {}),
        metadata=dict(node.get("metadata") or {}),
        uid=str(node.get("uid") or ""),
        raw_widgets=RawWidgetPayload(
            values=list(raw["values"]),
            shape=str(raw["shape"]),
            source=str(raw["source"]),
            has_dict_rows=bool(raw["has_dict_rows"]),
            length=int(raw["length"]),
        ),
    )


def _corpus_ui_node(path: str, node_id: str) -> dict[str, Any]:
    data = json.loads((ROOT / path).read_text(encoding="utf-8"))
    node = data["nodes"][node_id]
    ui = copy.deepcopy(node["metadata"]["_ui"])
    ui.setdefault("properties", {})
    return ui


def _single_node_ui(node: dict[str, Any]) -> dict[str, Any]:
    node_id = node.get("id")
    assert isinstance(node_id, int)
    return {
        "last_node_id": node_id,
        "last_link_id": 0,
        "nodes": [node],
        "links": [],
    }


def _minimal_ready_workflow() -> VibeWorkflow:
    wf = VibeWorkflow("image/test", WorkflowSource(id="image/test", source_type="ready_template"))
    wf.add_node("SaveImage", images=["1", 0], filename_prefix="strict-ready")
    wf.register_input("filename_prefix", "1", "filename_prefix")
    wf.outputs.append(VibeOutput(node_id="1", output_type="IMAGE", name="image"))
    return wf


def test_svd_motion_bucket_resolves_to_compact_index_and_emits_compact_values() -> None:
    node = _corpus_node("external_workflows/corpus/fc240f1c4331a5e5.json", "12")

    assert widget_index_for_field(node, "motion_bucket_id") == 3
    assert widget_value_for_field(node, "motion_bucket_id") == 127

    resolution = compact_widget_names_for_node(node, node.class_type)
    assert resolution.names == (
        "width",
        "height",
        "video_frames",
        "motion_bucket_id",
        "fps",
        "augmentation_level",
    )

    widget_names = _widget_names_for_emission(node.class_type, None, node=node)
    emitted_values = _build_widget_values(node, widget_names)
    assert emitted_values == [1024, 576, 14, 127, 6, 0]
    assert len(emitted_values) == 6
    assert len(emitted_values) != 9
    assert derive_widget_shape_evidence(node, None).value_domain == "compact"


def test_svd_schema_provider_aliases_are_compact_widget_value_order() -> None:
    node = _corpus_node("external_workflows/corpus/fc240f1c4331a5e5.json", "12")
    provider = get_authoring_schema_provider()

    resolution = compact_widget_names_for_node(node, node.class_type, schema_provider=provider)

    assert resolution.source == "schema_provider"
    assert resolution.names == (
        "width",
        "height",
        "video_frames",
        "motion_bucket_id",
        "fps",
        "augmentation_level",
    )
    assert widget_index_for_field(node, "motion_bucket_id", schema_provider=provider) == 3
    assert widget_index_for_field(node, "clip_vision", schema_provider=provider) is None
    assert widget_index_for_field(node, "init_image", schema_provider=provider) is None
    assert widget_index_for_field(node, "vae", schema_provider=provider) is None


def test_set_node_field_rejects_svd_link_only_input_with_schema_provider() -> None:
    ui_node = _corpus_ui_node("external_workflows/corpus/fc240f1c4331a5e5.json", "12")
    original = _single_node_ui(copy.deepcopy(ui_node))
    delta = parse_edit_delta(
        [
            {
                "op": "set_node_field",
                "target": ["", "12", "clip_vision"],
                "value": "not-a-widget",
            }
        ]
    )

    result = resolve_delta(original, delta, schema_provider=get_authoring_schema_provider())

    assert result.ok is False
    assert any(issue.code == "socket_input_not_literal_widget" for issue in result.diagnostics)
    assert any("input socket, not a widget" in issue.message for issue in result.diagnostics)


def test_set_node_field_applies_svd_motion_bucket_with_schema_provider() -> None:
    ui_node = _corpus_ui_node("external_workflows/corpus/fc240f1c4331a5e5.json", "12")
    original = _single_node_ui(copy.deepcopy(ui_node))
    delta = parse_edit_delta(
        [
            {
                "op": "set_node_field",
                "target": ["", "12", "motion_bucket_id"],
                "value": 200,
            }
        ]
    )

    result = apply_delta(original, delta, schema_provider=get_authoring_schema_provider())

    assert result.ok is True
    assert result.candidate is not None
    assert result.candidate["nodes"][0]["widgets_values"][3] == 200
    assert not any(issue.code == "non_widget_field_not_editable" for issue in result.diagnostics)


def test_style_model_apply_strength_uses_hidden_widget_padding_from_object_info() -> None:
    provider = get_authoring_schema_provider()
    node: dict[str, Any] = {
        "id": 12,
        "type": "StyleModelApply",
        "pos": [0, 0],
        "size": [240, 120],
        "flags": {},
        "order": 0,
        "mode": 0,
        "inputs": [
            {"name": "conditioning", "type": "CONDITIONING", "link": 1},
            {"name": "style_model", "type": "STYLE_MODEL", "link": 2},
            {"name": "clip_vision_output", "type": "CLIP_VISION_OUTPUT", "link": 3},
        ],
        "outputs": [{"name": "CONDITIONING", "type": "CONDITIONING", "slot_index": 0}],
        "properties": {},
        "widgets_values": [None, None, 1.0, "multiply"],
    }

    resolution = compact_widget_names_for_node(node, "StyleModelApply", schema_provider=provider)

    assert resolution.source == "schema_provider_leading_null_padding"
    assert resolution.names == ("widget_0", "widget_1", "strength", "strength_type")
    assert widget_index_for_field(node, "strength", schema_provider=provider) == 2
    assert widget_index_for_field(node, "strength_type", schema_provider=provider) == 3
    assert widget_index_for_field(node, "widget_0", schema_provider=provider) is None

    projection = render_edit_projection(
        _single_node_ui(copy.deepcopy(node)),
        schema_provider=provider,
        options=ProjectionOptions(full_detail_node_limit=10),
    )
    assert 'target=["", "12", "strength"] source=widgets_values[2] value=1.0' in projection.text
    assert 'target=["", "12", "widget_0"]' not in projection.text

    result = apply_delta(
        _single_node_ui(copy.deepcopy(node)),
        parse_edit_delta(
            [
                {
                    "op": "set_node_field",
                    "target": ["", "12", "strength"],
                    "value": 0.65,
                }
            ]
        ),
        schema_provider=provider,
    )

    assert result.ok is True
    assert result.candidate is not None
    assert result.candidate["nodes"][0]["widgets_values"] == [None, None, 0.65, "multiply"]


def test_empty_latent_image_batch_size_round_trips_by_named_widget() -> None:
    provider = get_authoring_schema_provider()
    node: dict[str, Any] = {
        "id": 9,
        "type": "EmptyLatentImage",
        "pos": [0, 0],
        "size": [220, 110],
        "flags": {},
        "order": 0,
        "mode": 0,
        "inputs": [],
        "outputs": [{"name": "LATENT", "type": "LATENT", "slot_index": 0}],
        "properties": {},
        "widgets_values": [512, 512, 16],
    }

    assert compact_widget_names_for_node(node, "EmptyLatentImage", schema_provider=provider).names == (
        "width",
        "height",
        "batch_size",
    )
    assert widget_index_for_field(node, "batch_size", schema_provider=provider) == 2

    projection = render_edit_projection(
        _single_node_ui(copy.deepcopy(node)),
        schema_provider=provider,
        options=ProjectionOptions(full_detail_node_limit=10),
    )
    assert 'target=["", "9", "batch_size"] source=widgets_values[2] value=16' in projection.text

    result = apply_delta(
        _single_node_ui(copy.deepcopy(node)),
        parse_edit_delta(
            [
                {
                    "op": "set_node_field",
                    "target": ["", "9", "batch_size"],
                    "value": 8,
                }
            ]
        ),
        schema_provider=provider,
    )

    assert result.ok is True
    assert result.candidate is not None
    assert result.candidate["nodes"][0]["widgets_values"] == [512, 512, 8]


def test_acn_source_backed_schema_resolves_strength_and_rejects_stub_names() -> None:
    node = _corpus_node("external_workflows/corpus/19d221f074b42462.json", "60")

    assert list(node.widgets.values()) == [0.6, 0, 0.75]
    resolution = compact_widget_names_for_node(node, node.class_type)
    assert resolution.names == ("strength", "start_percent", "end_percent")
    assert resolution.source == "committed_widget_schema"
    assert "mask_optional" not in resolution.names
    assert "timestep_kf" not in resolution.names
    assert "latent_kf_override" not in resolution.names
    assert widget_index_for_field(node, "strength") == 0
    assert widget_index_for_field(node, "start_percent") == 1
    assert widget_index_for_field(node, "end_percent") == 2
    assert widget_index_for_field(node, "latent_kf_override") is None


def test_render_projection_and_apply_use_same_compact_widget_names() -> None:
    cases = [
        (
            "external_workflows/corpus/19d221f074b42462.json",
            "60",
            "strength",
            0,
            0.5,
        ),
        (
            "external_workflows/corpus/fc240f1c4331a5e5.json",
            "12",
            "motion_bucket_id",
            3,
            200,
        ),
    ]

    for path, node_id, field_name, expected_index, new_value in cases:
        ui_node = _corpus_ui_node(path, node_id)
        original = _single_node_ui(copy.deepcopy(ui_node))

        projection = render_edit_projection(
            original,
            options=ProjectionOptions(full_detail_node_limit=10),
        )
        assert f'target=["", "{node_id}", "{field_name}"] source=widgets_values[{expected_index}]' in projection.text

        delta = parse_edit_delta(
            [
                {
                    "op": "set_node_field",
                    "target": ["", node_id, field_name],
                    "value": new_value,
                }
            ]
        )
        result = apply_delta(original, delta)

        assert result.ok is True
        assert result.candidate is not None
        changed = result.candidate["nodes"][0]["widgets_values"]
        assert changed[expected_index] == new_value
        assert len(changed) == len(ui_node["widgets_values"])


def test_unknown_widget_names_render_as_widget_n_and_fail_closed_on_apply() -> None:
    node = {
        "id": 1,
        "type": "NoTrustworthyNames",
        "pos": [0, 0],
        "size": [210, 58],
        "flags": {},
        "order": 0,
        "mode": 0,
        "inputs": [],
        "outputs": [],
        "properties": {},
        "widgets_values": [123],
    }
    original = _single_node_ui(copy.deepcopy(node))

    assert compact_widget_names_for_node(node, "NoTrustworthyNames").names == ("widget_0",)
    assert widget_index_for_field(node, "fabricated_name") is None

    projection = render_edit_projection(
        original,
        options=ProjectionOptions(full_detail_node_limit=10),
    )
    assert 'target=["", "1", "widget_0"] source=widgets_values[0] value=123' in projection.text
    assert "fabricated_name" not in projection.text

    delta = parse_edit_delta(
        [
            {
                "op": "set_node_field",
                "target": ["", "1", "fabricated_name"],
                "value": 456,
            }
        ]
    )
    result = resolve_delta(original, delta)

    assert result.ok is False
    assert any(issue.code == "unknown_node_field" for issue in result.diagnostics)


def test_per_node_ui_widget_names_beat_object_info() -> None:
    node: dict[str, Any] = {
        "class_type": "SVD_img2vid_Conditioning",
        "widgets_values": [1, 2],
        "metadata": {"_ui": {"widgets": [{"name": "a"}, {"name": "b"}]}},
    }

    resolution = compact_widget_names_for_node(node, "SVD_img2vid_Conditioning")
    assert resolution.names == ("a", "b")
    assert resolution.source == "_ui.widgets"
    assert widget_index_for_field(node, "a") == 0
    assert widget_index_for_field(node, "b") == 1


def test_duplicate_widget_names_require_explicit_widget_key() -> None:
    node: dict[str, Any] = {
        "class_type": "SyntheticDuplicateWidgets",
        "widgets_values": [1, 2],
        "metadata": {"_ui": {"widgets": [{"name": "dup"}, {"name": "dup"}]}},
    }

    resolution = compact_widget_names_for_node(node, "SyntheticDuplicateWidgets")
    assert resolution.names == ("widget_0", "widget_1")
    assert any("duplicate widget names" in warning for warning in resolution.warnings)
    assert widget_index_for_field(node, "dup") is None
    assert widget_index_for_field(node, "widget_0") == 0
    assert widget_index_for_field(node, "widget_1") == 1

    ui_node = {
        "id": 1,
        "type": "SyntheticDuplicateWidgets",
        "pos": [0, 0],
        "size": [210, 58],
        "flags": {},
        "order": 0,
        "mode": 0,
        "inputs": [],
        "outputs": [],
        "properties": {},
        "metadata": node["metadata"],
        "widgets_values": [1, 2],
    }
    duplicate_name = parse_edit_delta(
        [
            {
                "op": "set_node_field",
                "target": ["", "1", "dup"],
                "value": 9,
            }
        ]
    )
    explicit_widget = parse_edit_delta(
        [
            {
                "op": "set_node_field",
                "target": ["", "1", "widget_1"],
                "value": 9,
            }
        ]
    )

    duplicate_result = resolve_delta(_single_node_ui(copy.deepcopy(ui_node)), duplicate_name)
    assert duplicate_result.ok is False
    assert any(issue.code == "unknown_node_field" for issue in duplicate_result.diagnostics)

    explicit_result = apply_delta(_single_node_ui(copy.deepcopy(ui_node)), explicit_widget)
    assert explicit_result.ok is True
    assert explicit_result.candidate is not None
    assert explicit_result.candidate["nodes"][0]["widgets_values"] == [1, 9]


def test_widget_apply_refuses_to_grow_widgets_values_past_compact_count() -> None:
    original = _single_node_ui(
        {
            "id": 1,
            "type": "NoTrustworthyNames",
            "pos": [0, 0],
            "size": [210, 58],
            "flags": {},
            "order": 0,
            "mode": 0,
            "inputs": [],
            "outputs": [],
            "properties": {},
            "widgets_values": [1],
        }
    )
    before = copy.deepcopy(original)
    delta = parse_edit_delta(
        [
            {
                "op": "set_node_field",
                "target": ["", "1", "widget_3"],
                "value": 99,
            }
        ]
    )

    result = apply_delta(original, delta)

    assert result.ok is False
    assert result.candidate is None
    assert result.mutation_started is False
    assert any(issue.code == "unknown_node_field" for issue in result.diagnostics)
    assert original == before

    verdict = decide_widget_shape(
        WidgetShapeEvidence(
            node_id="1",
            class_type="NoTrustworthyNames",
            schema_less=False,
            confidence=1.0,
            raw_widget_count=None,
            candidate_widget_count=4,
            schema_widget_count=1,
            compacted_widget_names=("widget_0", "widget_1", "widget_2", "widget_3"),
            raw_widget_shape=None,
            has_dict_rows=False,
            overflow=True,
            provider="test_provider",
            explicit_widget_overflow=True,
            raw_widget_length_recovered=False,
        ),
        raw_widget_payloads={},
        raw_payloads={},
        layout_entries={},
    )
    assert verdict.decision is WidgetShapeDecision.REFUSE
    assert WidgetShapeReason.OVERFLOW in verdict.reasons


def test_strict_ready_unresolved_widgets_are_not_silenced_by_candidate_ui_aliases() -> None:
    wf = _minimal_ready_workflow()
    wf.nodes["2"] = VibeNode(
        id="2",
        class_type="KnownNode",
        metadata={"_ui": {"widgets": [{"name": "prompt"}]}},
    )
    widget_analysis = {
        "unresolved_widget_aliases": [
            {"node_id": "2", "class_type": "KnownNode", "input": "widget_0"},
        ],
        "suggestions": [
            {"class_type": "KnownNode", "schema_source": "schema_provider", "suggested_schema_entry": ["prompt"]},
        ],
    }

    issues = validate_strict_ready_workflow(wf, widget_analysis=widget_analysis)

    assert any(
        issue.code == STRICT_READY_UNRESOLVED_WIDGETS
        and issue.detail["target"] == "node:2.widget_0"
        for issue in issues
    )


def test_strict_ready_hidden_model_filenames_are_not_silenced_by_candidate_ui_aliases() -> None:
    wf = _minimal_ready_workflow()
    wf.nodes["2"] = VibeNode(
        id="2",
        class_type="CheckpointLoaderSimple",
        metadata={"_ui": {"widgets": [{"name": "ckpt_name"}]}},
    )
    api_prompt = {
        "2": {
            "class_type": "CheckpointLoaderSimple",
            "inputs": {"widget_0": "model.safetensors"},
        }
    }

    issues = validate_strict_ready_workflow(wf, api_prompt=api_prompt)

    assert any(
        issue.code == HIDDEN_MODEL_FILENAME
        and issue.severity == "error"
        and issue.detail["target"] == "node:2.widget_0"
        for issue in issues
    )


# ── PR-D: TripoTextToModelNode geometry_quality schema drift ─────────────────

_TRIpo_12_WIDGETS = [
    "Generate a 3D model of a steampunk-inspired spider drone.\n",
    "",                          # negative_prompt
    "v2.5-20250123",             # model_version
    "None",                      # style
    True,                        # texture
    True,                        # pbr
    42,                          # image_seed
    42,                          # model_seed
    42,                          # texture_seed
    "detailed",                  # texture_quality (pre-geometry_quality schema)
    -1,                          # face_limit
    False,                       # quad
]

_TRIpo_13_WIDGETS = list(_TRIpo_12_WIDGETS[:-2]) + ["standard", -1, False, "detailed"]


def _tripo_ui_node(widgets: list[Any]) -> dict[str, Any]:
    return {
        "id": 3,
        "type": "TripoTextToModelNode",
        "pos": [0, 0],
        "size": [320, 540],
        "flags": {},
        "order": 0,
        "mode": 0,
        "inputs": [],
        "outputs": [
            {"name": "model_file", "type": "STRING", "links": None, "slot_index": 0},
            {"name": "model task_id", "type": "MODEL_TASK_ID", "links": None, "slot_index": 1},
        ],
        "properties": {"vibecomfy_uid": "3"},
        "widgets_values": list(widgets),
    }


def test_tripo_stale_node_geometry_quality_reports_node_field_not_resolvable() -> None:
    """PR-D: a 12-widget TripoTextToModelNode predates `geometry_quality`; the
    apply path must not call it 'non-widget' — it must say the node instance
    cannot resolve it and hint at the settable fields."""
    original = _single_node_ui(_tripo_ui_node(_TRIpo_12_WIDGETS))
    delta = parse_edit_delta(
        [
            {
                "op": "set_node_field",
                "target": ["", "3", "geometry_quality"],
                "value": "detailed",
            }
        ]
    )

    result = resolve_delta(original, delta, schema_provider=get_authoring_schema_provider())

    assert result.ok is False
    assert any(issue.code == "node_field_not_resolvable" for issue in result.diagnostics)
    hint = next(
        issue.message for issue in result.diagnostics if issue.code == "node_field_not_resolvable"
    )
    assert "geometry_quality" in hint
    assert "texture_quality" in hint
    assert "no widget for it" in hint


def test_tripo_stale_node_texture_quality_still_settable() -> None:
    """Control: fields the node DOES have stay settable through the real
    projection/setter mapping."""
    original = _single_node_ui(_tripo_ui_node(_TRIpo_12_WIDGETS))
    delta = parse_edit_delta(
        [
            {
                "op": "set_node_field",
                "target": ["", "3", "texture_quality"],
                "value": "standard",
            }
        ]
    )

    result = apply_delta(original, delta, schema_provider=get_authoring_schema_provider())

    assert result.ok is True
    assert result.candidate is not None
    assert result.candidate["nodes"][0]["widgets_values"][9] == "standard"


def test_tripo_current_node_geometry_quality_resolvable() -> None:
    """A 13-widget (current-schema) node CAN set geometry_quality — the setter
    mapping exists; only the stale node shape cannot."""
    original = _single_node_ui(_tripo_ui_node(_TRIpo_13_WIDGETS))
    delta = parse_edit_delta(
        [
            {
                "op": "set_node_field",
                "target": ["", "3", "geometry_quality"],
                "value": "detailed",
            }
        ]
    )

    result = apply_delta(original, delta, schema_provider=get_authoring_schema_provider())

    assert result.ok is True
    assert result.candidate["nodes"][0]["widgets_values"][12] == "detailed"


def test_filter_signature_rows_drops_schema_drifted_literals_for_in_graph_nodes() -> None:
    """PR-D: the in-graph signature catalog must stop advertising literal fields
    that no in-graph node of the class can resolve (Tripo geometry_quality),
    while classes without nodes keep their full schema."""
    from vibecomfy.porting.emitter import (
        emit_available_node_signatures,
        filter_signature_rows_to_in_graph_nodes,
    )

    provider = get_authoring_schema_provider()
    rows = emit_available_node_signatures(provider, focus_types=["TripoTextToModelNode"])
    assert rows, "authoring provider should know TripoTextToModelNode"
    full_names = {field.name for field in rows[0].inputs}
    assert "geometry_quality" in full_names
    assert "texture_quality" in full_names

    node = _tripo_ui_node(_TRIpo_12_WIDGETS)
    filtered = filter_signature_rows_to_in_graph_nodes(rows, {"nodes": [node]})
    assert len(filtered) == 1
    filtered_names = {field.name for field in filtered[0].inputs}
    assert "geometry_quality" not in filtered_names
    assert "texture_quality" in filtered_names
    assert "face_limit" in filtered_names

    # Without in-graph nodes the row is untouched (new-node authoring keeps the
    # full current schema).
    untouched = filter_signature_rows_to_in_graph_nodes(rows, {"nodes": []})
    assert {field.name for field in untouched[0].inputs} == full_names
