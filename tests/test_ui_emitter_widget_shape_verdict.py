from __future__ import annotations

import json
import warnings
from typing import Any

import pytest

from vibecomfy.porting.layout_store import store_from_ui_json
from vibecomfy.porting.layout.delta import canonical_semantic_link_set
from vibecomfy.porting.refuse import RefusedEmit
from vibecomfy.porting.emit.ui import emit_ui_json
from vibecomfy.porting.lowering import clone_uid
from vibecomfy.schema.provider import InputSpec, NodeSchema, OutputSpec
from vibecomfy.ingest.snapshot import capture_ingest_snapshot
from vibecomfy.workflow import RawWidgetPayload, VibeEdge, VibeNode, VibeWorkflow, WorkflowSource


class _Provider:
    def __init__(self, schemas: dict[str, NodeSchema]) -> None:
        self._schemas = schemas

    def get_schema(self, class_type: str) -> NodeSchema | None:
        return self._schemas.get(class_type)


def _schema(
    class_type: str,
    inputs: dict[str, InputSpec],
    outputs: list[OutputSpec] | None = None,
) -> NodeSchema:
    return NodeSchema(
        class_type=class_type,
        pack=None,
        inputs=inputs,
        outputs=outputs or [],
        source_provider="test_provider",
        confidence=1.0,
    )


def _provider() -> _Provider:
    return _Provider(
        {
            "KSampler": _schema(
                "KSampler",
                {"seed": InputSpec("INT")},
                [OutputSpec("IMAGE", "IMAGE")],
            ),
            "SaveImage": _schema("SaveImage", {"images": InputSpec("IMAGE")}),
        }
    )


def _provider_with_defaults() -> _Provider:
    return _Provider(
        {
            "KSampler": NodeSchema(
                class_type="KSampler",
                pack=None,
                inputs={
                    "seed": InputSpec("INT", default=42),
                    "steps": InputSpec("INT", default=20),
                    "cfg": InputSpec("FLOAT", default=7.0),
                },
                outputs=[OutputSpec("IMAGE", "IMAGE")],
                source_provider="object_info_index",
                confidence=1.0,
            )
        }
    )


def _provider_object_info_generated() -> _Provider:
    return _Provider(
        {
            "PrimitiveInt": NodeSchema(
                class_type="PrimitiveInt",
                pack=None,
                inputs={"value": InputSpec("INT")},
                outputs=[],
                source_provider="object_info_index",
                confidence=1.0,
            ),
            "Florence2Run": NodeSchema(
                class_type="Florence2Run",
                pack=None,
                inputs={
                    "text_input": InputSpec("STRING", default=""),
                    "task": InputSpec("STRING", default="detailed_caption"),
                    "fill_mask": InputSpec("BOOLEAN", default=True),
                    "keep_alive": InputSpec("BOOLEAN", default=False),
                    "max_new_tokens": InputSpec("INT", default=1024),
                },
                outputs=[OutputSpec("STRING", "STRING")],
                source_provider="object_info_index",
                confidence=1.0,
            ),
        }
    )


def _wf() -> VibeWorkflow:
    return VibeWorkflow("wf", WorkflowSource("wf", None, "test"))


def _raw_dynamic_ui() -> dict[str, Any]:
    return {
        "nodes": [
            {
                "id": 7,
                "type": "DynamicRows",
                "pos": [10, 20],
                "size": [300, 120],
                "flags": {},
                "order": 0,
                "mode": 0,
                "inputs": [],
                "outputs": [],
                "properties": {"vibecomfy_uid": "uid-dynamic"},
                "widgets_values": [{"lora": "a"}, {"lora": "b"}],
            }
        ],
        "links": [],
    }


def _raw_widgets() -> RawWidgetPayload:
    return RawWidgetPayload(
        values=[{"lora": "a"}, {"lora": "b"}],
        shape="list",
        source="ui.widgets_values",
        has_dict_rows=True,
        length=2,
    )


def _raw_power_lora_widgets() -> RawWidgetPayload:
    return RawWidgetPayload(
        values=[
            {"lora": "detail.safetensors", "strength": 0.55},
            {"lora": "style.safetensors", "strength": 0.75},
            {"lora": "motion.safetensors", "strength": 0.35},
        ],
        shape="list",
        source="ui.widgets_values",
        has_dict_rows=True,
        length=3,
    )


def _raw_power_lora_ui() -> dict[str, Any]:
    return {
        "nodes": [
            {
                "id": 11,
                "type": "Power Lora Loader (rgthree)",
                "pos": [40, 60],
                "size": [360, 180],
                "flags": {"collapsed": False},
                "order": 0,
                "mode": 0,
                "inputs": [],
                "outputs": [
                    {"name": "MODEL", "type": "MODEL", "links": None, "slot_index": 0},
                    {"name": "CLIP", "type": "CLIP", "links": None, "slot_index": 1},
                ],
                "properties": {"vibecomfy_uid": "uid-power-lora"},
                "widgets_values": list(_raw_power_lora_widgets().values),
            }
        ],
        "links": [],
    }


def _raw_connected_dynamic_ui() -> dict[str, Any]:
    return {
        "nodes": [
            {
                "id": 7,
                "type": "DynamicRows",
                "pos": [10, 20],
                "size": [300, 120],
                "flags": {},
                "order": 0,
                "mode": 0,
                "inputs": [{"name": "image", "type": "IMAGE", "link": 42}],
                "outputs": [{"name": "IMAGE", "type": "IMAGE", "links": [43], "slot_index": 0}],
                "properties": {"vibecomfy_uid": "uid-dynamic"},
                "widgets_values": [{"lora": "a"}, {"lora": "b"}],
            }
        ],
        "links": [
            [42, 1, 0, 7, 0, "IMAGE"],
            [43, 7, 0, 9, 0, "IMAGE"],
        ],
    }


def test_power_lora_style_overflow_pins_from_full_raw_ui_payload() -> None:
    raw_ui = _raw_power_lora_ui()
    wf = _wf()
    wf.nodes["11"] = VibeNode(
        "11",
        "Power Lora Loader (rgthree)",
        uid="uid-power-lora",
        widgets={
            "widget_0": {"lora": "detail.safetensors", "strength": 0.55},
            "widget_1": {"lora": "style.safetensors", "strength": 0.75},
            "widget_2": {"lora": "motion.safetensors", "strength": 0.35},
        },
        raw_widgets=_raw_power_lora_widgets(),
    )

    report: list[dict[str, Any]] = []
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        ui = emit_ui_json(
            wf,
            schema_provider=_Provider(
                {
                    "Power Lora Loader (rgthree)": _schema(
                        "Power Lora Loader (rgthree)",
                        {"widget_0": InputSpec("STRING"), "widget_1": InputSpec("STRING")},
                    )
                }
            ),
            prior_store=store_from_ui_json(raw_ui),
            prior_ui_payload=raw_ui,
            recovery_report=report,
        )

    assert ui["nodes"][0]["widgets_values"] == raw_ui["nodes"][0]["widgets_values"]
    entry = next(item for item in report if item.get("node_id") == "11")
    assert entry["widget_shape_verdict"] == "pin_opaque"
    assert "overflow" in entry["widget_shape_reasons"]
    assert entry["widget_shape_details"]["evidence"]["overflow"] is True
    assert not any(
        item.get("widget_shape_verdict") == "safe_to_regenerate"
        and item.get("widget_shape_details", {}).get("evidence", {}).get("overflow")
        for item in report
    )


def test_recovery_entries_include_widget_shape_verdict_for_safe_nodes() -> None:
    wf = _wf()
    wf.nodes["1"] = VibeNode("1", "KSampler", widgets={"widget_0": 4})

    report: list[dict[str, Any]] = []
    emit_ui_json(wf, schema_provider=_provider(), recovery_report=report)

    assert report
    assert all("widget_shape_verdict" in entry for entry in report)
    node_entry = next(entry for entry in report if entry.get("node_id") == "1")
    assert node_entry["widget_shape_verdict"] == "safe_to_regenerate"


def test_overflow_refuses_before_returning_envelope_and_reports_verdict() -> None:
    wf = _wf()
    wf.nodes["1"] = VibeNode(
        "1",
        "ProgrammaticOverflow",
        widgets={f"widget_{idx}": idx for idx in range(20)},
    )

    report: list[dict[str, Any]] = []
    with pytest.raises(RefusedEmit) as exc_info:
        emit_ui_json(
            wf,
            schema_provider=_Provider(
                {
                    "ProgrammaticOverflow": _schema(
                        "ProgrammaticOverflow",
                        {"seed": InputSpec("INT")},
                    )
                }
            ),
            recovery_report=report,
        )

    assert "1" in exc_info.value.diff
    assert exc_info.value.diff["1"]["axis"] == "widget_shape"
    assert exc_info.value.diff["1"]["reason"] == "overflow"
    assert report[0]["widget_shape_verdict"] == "refuse"
    assert "overflow" in report[0]["widget_shape_reasons"]


def test_pinned_dynamic_node_bypasses_widget_regeneration() -> None:
    raw_ui = _raw_dynamic_ui()
    wf = _wf()
    wf.nodes["7"] = VibeNode(
        "7",
        "DynamicRows",
        uid="uid-dynamic",
        raw_widgets=_raw_widgets(),
    )

    report: list[dict[str, Any]] = []
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        ui = emit_ui_json(
            wf,
            prior_store=store_from_ui_json(raw_ui),
            prior_ui_payload=raw_ui,
            recovery_report=report,
        )

    node = ui["nodes"][0]
    assert node["widgets_values"] == [{"lora": "a"}, {"lora": "b"}]
    assert report[0]["widget_shape_verdict"] == "pin_opaque"
    assert report[0]["widget_shape_details"]["reasons"] == ["schema_less", "dict_row_dynamic_widgets"]


def test_dynamic_node_without_prior_raw_ui_payload_refuses() -> None:
    wf = _wf()
    wf.nodes["7"] = VibeNode(
        "7",
        "DynamicRows",
        uid="uid-dynamic",
        raw_widgets=_raw_widgets(),
    )

    with warnings.catch_warnings(), pytest.raises(RefusedEmit) as exc_info:
        warnings.simplefilter("ignore")
        emit_ui_json(wf)

    assert exc_info.value.diff["7"]["axis"] == "widget_shape"
    assert exc_info.value.diff["7"]["reason"] == "schema_less"
    reasons = set(exc_info.value.diff["7"]["reasons"])
    assert "dict_row_dynamic_widgets" in reasons
    assert "no_prior_ui_payload" in reasons
    assert "missing_layout_entry" in reasons


def test_identity_matched_overflow_carries_forward_raw_ui() -> None:
    raw_ui = {
        "nodes": [
            {
                "id": 1,
                "type": "KSampler",
                "pos": [10, 20],
                "size": [300, 120],
                "flags": {},
                "order": 0,
                "mode": 0,
                "inputs": [],
                "outputs": [],
                "properties": {"vibecomfy_uid": "uid-ksampler"},
                "widgets_values": list(range(12)),
            }
        ],
        "links": [],
    }
    wf = _wf()
    wf.nodes["1"] = VibeNode(
        "1",
        "KSampler",
        uid="uid-ksampler",
        widgets={"widget_0": 4},
        metadata={"_ui": raw_ui["nodes"][0]},
    )

    report: list[dict[str, Any]] = []
    ui = emit_ui_json(wf, schema_provider=_provider(), recovery_report=report)

    assert ui["nodes"][0]["id"] == 1
    entry = next(item for item in report if item.get("node_id") == "1")
    assert entry["widget_shape_verdict"] == "pin_opaque"
    assert entry["widget_shape_recovery"] == "carry_forward_raw_ui"


def test_schema_known_generated_node_uses_schema_defaults_and_marks_recovery() -> None:
    wf = _wf()
    wf.nodes["1"] = VibeNode("1", "KSampler")

    report: list[dict[str, Any]] = []
    ui = emit_ui_json(wf, schema_provider=_provider_with_defaults(), recovery_report=report)

    assert ui["nodes"][0]["widgets_values"] == [42, "fixed", 20, 7.0, None, None, 1.0]
    entry = next(item for item in report if item.get("node_id") == "1")
    assert entry["widget_shape_verdict"] == "safe_to_regenerate"
    assert entry["widget_shape_recovery"] == "schema_default_regenerate"


def test_schema_default_regeneration_preserves_ingested_positional_widget_values() -> None:
    from vibecomfy.ingest.normalize import convert_to_vibe_format

    provider = _Provider(
        {
            "EmptyLatentImage": NodeSchema(
                class_type="EmptyLatentImage",
                pack=None,
                inputs={
                    "width": InputSpec("INT", default=512),
                    "height": InputSpec("INT", default=512),
                    "batch_size": InputSpec("INT", default=1),
                },
                outputs=[OutputSpec("LATENT", "LATENT")],
                source_provider="object_info_index",
                confidence=1.0,
            )
        }
    )
    wf = convert_to_vibe_format(
        {
            "9": {
                "class_type": "EmptyLatentImage",
                "inputs": {"widget_0": 512, "widget_1": 512, "widget_2": 16},
            }
        }
    )

    report: list[dict[str, Any]] = []
    ui = emit_ui_json(wf, schema_provider=provider, recovery_report=report)

    node = next(item for item in ui["nodes"] if item["type"] == "EmptyLatentImage")
    assert node["widgets_values"] == [512, 512, 16]
    entry = next(item for item in report if item.get("node_id") == "9")
    assert entry["widget_shape_verdict"] == "safe_to_regenerate"
    assert entry["widget_shape_recovery"] == "schema_default_regenerate"


def test_schema_known_generated_explicit_overflow_uses_schema_defaults_and_marks_recovery() -> None:
    wf = _wf()
    wf.nodes["1"] = VibeNode(
        "1",
        "KSampler",
        widgets={f"widget_{idx}": idx for idx in range(10)},
    )

    report: list[dict[str, Any]] = []
    ui = emit_ui_json(
        wf,
        schema_provider=_provider_with_defaults(),
        recovery_report=report,
    )

    assert ui["nodes"][0]["widgets_values"] == [42, "fixed", 20, 7.0, None, None, 1.0]
    entry = next(item for item in report if item.get("node_id") == "1")
    assert entry["widget_shape_verdict"] == "safe_to_regenerate"
    assert entry["widget_shape_recovery"] == "schema_default_regenerate"


def test_single_slot_object_info_generated_overflow_still_refuses() -> None:
    provider = _Provider(
        {
            "SingleSlotGenerated": NodeSchema(
                class_type="SingleSlotGenerated",
                pack=None,
                inputs={"value": InputSpec("INT")},
                outputs=[],
                source_provider="object_info_index",
                confidence=1.0,
            ),
        }
    )
    wf = _wf()
    wf.nodes["1"] = VibeNode(
        "1",
        "SingleSlotGenerated",
        widgets={"widget_0": 7, "widget_1": 9},
    )

    report: list[dict[str, Any]] = []
    with pytest.raises(RefusedEmit):
        emit_ui_json(
            wf,
            schema_provider=provider,
            recovery_report=report,
        )

    entry = next(item for item in report if item.get("node_id") == "1")
    assert entry["widget_shape_verdict"] == "refuse"


def test_existing_static_overflow_recovers_by_preserving_observed_raw_widget_slot() -> None:
    provider = _Provider(
        {
            "ObservedUndercounted": NodeSchema(
                class_type="ObservedUndercounted",
                pack=None,
                inputs={"value": InputSpec("INT")},
                outputs=[],
                source_provider="object_info_index",
                confidence=1.0,
            ),
        }
    )
    wf = _wf()
    wf.nodes["1"] = VibeNode(
        "1",
        "ObservedUndercounted",
        widgets={"widget_0": 11},
        raw_widgets=RawWidgetPayload(
            values=[7, "fixed"],
            shape="list",
            source="ui.widgets_values",
            has_dict_rows=False,
            length=2,
        ),
    )

    report: list[dict[str, Any]] = []
    ui = emit_ui_json(
        wf,
        schema_provider=provider,
        recovery_report=report,
    )

    assert ui["nodes"][0]["widgets_values"] == [11, "fixed"]
    entry = next(item for item in report if item.get("node_id") == "1")
    assert entry["widget_shape_verdict"] == "safe_to_regenerate"
    assert entry["widget_shape_recovery"] == "observed_widget_shape_regenerate"


def test_primitive_int_control_after_generate_metadata_emits_second_ui_slot() -> None:
    from vibecomfy.schema import get_schema_provider

    wf = _wf()
    wf.nodes["1"] = VibeNode(
        "1",
        "PrimitiveInt",
        widgets={"widget_0": 11, "widget_1": "fixed"},
    )

    report: list[dict[str, Any]] = []
    ui = emit_ui_json(
        wf,
        schema_provider=get_schema_provider(),
        recovery_report=report,
    )

    assert ui["nodes"][0]["widgets_values"] == [11, "fixed"]
    entry = next(item for item in report if item.get("node_id") == "1")
    assert entry["widget_shape_verdict"] == "safe_to_regenerate"


def test_object_info_generated_without_raw_widget_order_uses_schema_defaults() -> None:
    wf = _wf()
    wf.nodes["1"] = VibeNode(
        "1",
        "Florence2Run",
        widgets={f"widget_{idx}": idx for idx in range(10)},
    )

    report: list[dict[str, Any]] = []
    ui = emit_ui_json(
        wf,
        schema_provider=_provider_object_info_generated(),
        recovery_report=report,
    )

    assert ui["nodes"][0]["type"] == "Florence2Run"
    entry = next(item for item in report if item.get("node_id") == "1")
    assert entry["widget_shape_verdict"] == "safe_to_regenerate"
    assert entry["widget_shape_recovery"] == "schema_default_regenerate"


def test_metadata_ui_dynamic_node_pins_without_external_prior_payload() -> None:
    raw_ui = _raw_dynamic_ui()
    wf = _wf()
    wf.nodes["7"] = VibeNode(
        "7",
        "DynamicRows",
        uid="uid-dynamic",
        raw_widgets=_raw_widgets(),
        metadata={"_ui": raw_ui["nodes"][0]},
    )

    report: list[dict[str, Any]] = []
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        ui = emit_ui_json(wf, recovery_report=report)

    assert ui["nodes"][0]["widgets_values"] == raw_ui["nodes"][0]["widgets_values"]
    entry = next(item for item in report if item.get("node_id") == "7")
    assert entry["widget_shape_verdict"] == "pin_opaque"
    assert entry["has_raw_ui_payload"] is True


def test_raw_widget_values_length_recovery_marker_is_reported() -> None:
    raw_ui = _raw_dynamic_ui()
    wf = _wf()
    wf.nodes["7"] = VibeNode(
        "7",
        "DynamicRows",
        uid="uid-dynamic",
        raw_widgets=RawWidgetPayload(
            values=[{"lora": "a"}, {"lora": "b"}],
            shape="list",
            source="ui.widgets_values",
            has_dict_rows=True,
            length=None,  # type: ignore[arg-type]
        ),
        metadata={"_ui": raw_ui["nodes"][0]},
    )

    report: list[dict[str, Any]] = []
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        emit_ui_json(wf, recovery_report=report)

    entry = next(item for item in report if item.get("node_id") == "7")
    assert entry["widget_shape_recovery"] == "raw_widgets_values_length"


def test_prior_store_only_dynamic_node_refuses_without_full_raw_payload() -> None:
    raw_ui = _raw_dynamic_ui()
    wf = _wf()
    wf.nodes["7"] = VibeNode(
        "7",
        "DynamicRows",
        uid="uid-dynamic",
        raw_widgets=_raw_widgets(),
    )

    with warnings.catch_warnings(), pytest.raises(RefusedEmit) as exc_info:
        warnings.simplefilter("ignore")
        emit_ui_json(wf, prior_store=store_from_ui_json(raw_ui))

    reasons = set(exc_info.value.diff["7"]["reasons"])
    assert "dict_row_dynamic_widgets" in reasons
    assert "no_prior_ui_payload" in reasons
    assert "missing_layout_entry" not in reasons


def test_dynamic_node_widget_value_edit_refuses_instead_of_pinning() -> None:
    raw_ui = _raw_dynamic_ui()
    wf = _wf()
    wf.nodes["7"] = VibeNode(
        "7",
        "DynamicRows",
        uid="uid-dynamic",
        widgets={"widget_0": "old"},
        raw_widgets=_raw_widgets(),
    )
    wf.metadata["_ingest_snapshot"] = capture_ingest_snapshot({}, wf)
    wf.nodes["7"].widgets["widget_0"] = "new"

    with warnings.catch_warnings(), pytest.raises(RefusedEmit) as exc_info:
        warnings.simplefilter("ignore")
        emit_ui_json(
            wf,
            prior_store=store_from_ui_json(raw_ui),
            prior_ui_payload=raw_ui,
        )

    reasons = set(exc_info.value.diff["7"]["reasons"])
    assert "dict_row_dynamic_widgets" in reasons
    assert "widget_delta" in reasons
    assert "field_delta" in exc_info.value.diff["7"]["details"]


def test_dynamic_node_edge_touch_refuses_instead_of_pinning() -> None:
    raw_ui = _raw_dynamic_ui()
    wf = _wf()
    wf.nodes["7"] = VibeNode(
        "7",
        "DynamicRows",
        uid="uid-dynamic",
        raw_widgets=_raw_widgets(),
    )
    wf.nodes["9"] = VibeNode("9", "SaveImage", widgets={"filename_prefix": "out"})
    wf.metadata["_ingest_snapshot"] = capture_ingest_snapshot({}, wf)
    wf.edges.append(VibeEdge("7", "0", "9", "images"))

    with warnings.catch_warnings(), pytest.raises(RefusedEmit) as exc_info:
        warnings.simplefilter("ignore")
        emit_ui_json(
            wf,
            schema_provider=_provider(),
            prior_store=store_from_ui_json(raw_ui),
            prior_ui_payload=raw_ui,
        )

    reasons = set(exc_info.value.diff["7"]["reasons"])
    assert "dict_row_dynamic_widgets" in reasons
    assert "link_delta" in reasons
    assert "link_delta" in exc_info.value.diff["7"]["details"]


def test_pinned_connected_node_rewrites_stale_local_link_refs_to_global_links() -> None:
    raw_ui = _raw_connected_dynamic_ui()
    wf = _wf()
    wf.nodes["7"] = VibeNode(
        "7",
        "DynamicRows",
        uid="uid-dynamic",
        raw_widgets=_raw_widgets(),
    )
    wf.nodes["1"] = VibeNode("1", "KSampler", widgets={"widget_0": 4})
    wf.nodes["9"] = VibeNode("9", "SaveImage", widgets={"filename_prefix": "out"})
    wf.edges.extend(
        [
            VibeEdge("1", "0", "7", "image"),
            VibeEdge("7", "0", "9", "images"),
        ]
    )

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        ui = emit_ui_json(
            wf,
            schema_provider=_provider(),
            prior_store=store_from_ui_json(raw_ui),
            prior_ui_payload=raw_ui,
        )

    pinned = next(node for node in ui["nodes"] if node["id"] == 7)
    link_ids = {link[0] for link in ui["links"]}
    assert pinned["inputs"][0]["link"] in link_ids
    assert set(pinned["outputs"][0]["links"]).issubset(link_ids)
    assert pinned["inputs"][0]["link"] == 1
    assert pinned["outputs"][0]["links"] == [2]
    assert "42" not in json.dumps(ui)
    assert "43" not in json.dumps(ui)


# ---------------------------------------------------------------------------
# B03 — canonical semantic pin comparison
# ---------------------------------------------------------------------------


def _semantic_pin_workflow() -> tuple[VibeWorkflow, dict[str, Any]]:
    raw_ui = _raw_connected_dynamic_ui()
    wf = _wf()
    wf.nodes["7"] = VibeNode(
        "7",
        "DynamicRows",
        uid="uid-dynamic",
        raw_widgets=_raw_widgets(),
    )
    return wf, raw_ui


def _emit_semantic_pin(wf: VibeWorkflow, raw_ui: dict[str, Any]) -> dict[str, Any]:
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        return emit_ui_json(
            wf,
            schema_provider=_provider(),
            prior_store=store_from_ui_json(raw_ui),
            prior_ui_payload=raw_ui,
        )


def test_pinned_semantic_set_get_fanout_preserves_terminal_consumer_set() -> None:
    wf, raw_ui = _semantic_pin_workflow()
    wf.nodes["10"] = VibeNode("10", "SetNode", uid="set", widgets={"widget_0": "BUS"})
    wf.nodes["11"] = VibeNode("11", "GetNode", uid="get", widgets={"widget_0": "BUS"})
    for node_id in range(20, 24):
        wf.nodes[str(node_id)] = VibeNode(str(node_id), "SaveImage", uid=f"consumer-{node_id}")
    wf.edges = [VibeEdge("7", "0", "10", "value")]
    wf.edges.extend(VibeEdge("11", "0", str(node_id), "images") for node_id in range(20, 24))
    wf.metadata["_ingest_snapshot"] = capture_ingest_snapshot({}, wf)

    del wf.nodes["10"]
    del wf.nodes["11"]
    wf.edges = [VibeEdge("7", "0", str(node_id), "images") for node_id in range(20, 24)]

    emitted = _emit_semantic_pin(wf, raw_ui)
    assert next(node for node in emitted["nodes"] if node["id"] == 7)["widgets_values"] == [
        {"lora": "a"},
        {"lora": "b"},
    ]


def test_pinned_semantic_reroute_one_to_one_and_link_renumbering_pins() -> None:
    wf, raw_ui = _semantic_pin_workflow()
    wf.nodes["8"] = VibeNode("8", "Reroute", uid="reroute")
    wf.nodes["9"] = VibeNode("9", "SaveImage", uid="consumer")
    wf.edges = [VibeEdge("7", "0", "8", ""), VibeEdge("8", "0", "9", "images")]
    wf.metadata["_ingest_snapshot"] = capture_ingest_snapshot({}, wf)

    del wf.nodes["8"]
    wf.edges = [VibeEdge("7", "0", "9", "images")]
    # Unrelated earlier-sorting edge changes the emitted numeric link id only.
    wf.nodes["1"] = VibeNode("1", "KSampler", uid="unrelated-source")
    wf.nodes["2"] = VibeNode("2", "SaveImage", uid="unrelated-consumer")
    wf.edges.insert(0, VibeEdge("1", "0", "2", "images"))

    emitted = _emit_semantic_pin(wf, raw_ui)
    pinned = next(node for node in emitted["nodes"] if node["id"] == 7)
    assert pinned["outputs"][0]["links"] == [2]


def test_pinned_semantic_loop_cloned_consumers_collapse_to_source_uid() -> None:
    wf, raw_ui = _semantic_pin_workflow()
    wf.nodes["9"] = VibeNode("9", "SaveImage", uid="consumer")
    wf.edges = [VibeEdge("7", "0", "9", "images")]
    wf.metadata["_ingest_snapshot"] = capture_ingest_snapshot({}, wf)

    del wf.nodes["9"]
    wf.edges = []
    for iteration in range(3):
        node_id = str(20 + iteration)
        lowered_uid = clone_uid("loop", "consumer", iteration)
        wf.nodes[node_id] = VibeNode(
            node_id,
            "SaveImage",
            uid=lowered_uid,
            metadata={
                "vibecomfy.lowering": {
                    "source_uid": "consumer",
                    "loop_uid": "loop",
                    "iteration_index": iteration,
                }
            },
        )
        wf.edges.append(VibeEdge("7", "0", node_id, "images"))

    _emit_semantic_pin(wf, raw_ui)


def test_pinned_semantic_unchanged_lowered_loop_pins() -> None:
    """B03 finding 3: snapshot taken AFTER lowering on an UNCHANGED workflow
    must not fabricate a ``semantic_link_set`` delta (the valid pin is not
    refused).

    The before set holds loop-clone consumer uids (``loop:iter0:consumer``,
    ``loop:iter1:consumer``) while the live set collapses them to
    ``consumer``; symmetric alias normalization makes the delta empty so the
    unchanged lowered workflow pins instead of refusing.
    """
    wf, raw_ui = _semantic_pin_workflow()
    wf.edges = []
    for iteration in range(2):
        node_id = str(20 + iteration)
        lowered_uid = clone_uid("loop", "consumer", iteration)
        wf.nodes[node_id] = VibeNode(
            node_id,
            "SaveImage",
            uid=lowered_uid,
            metadata={
                "vibecomfy.lowering": {
                    "source_uid": "consumer",
                    "loop_uid": "loop",
                    "iteration_index": iteration,
                }
            },
        )
        wf.edges.append(VibeEdge("7", "0", node_id, "images"))
    # Snapshot captured AFTER lowering; the workflow is UNCHANGED from here on.
    wf.metadata["_ingest_snapshot"] = capture_ingest_snapshot({}, wf)

    _emit_semantic_pin(wf, raw_ui)


def test_pinned_semantic_single_broadcast_consumer_expands_to_lowered_fanout() -> None:
    """The corpus regression: one Set/Get route becomes N direct clone links."""
    wf, raw_ui = _semantic_pin_workflow()
    wf.nodes["10"] = VibeNode("10", "SetNode", uid="set", widgets={"widget_0": "BUS"})
    wf.nodes["11"] = VibeNode("11", "GetNode", uid="get", widgets={"widget_0": "BUS"})
    wf.nodes["12"] = VibeNode("12", "SaveImage", uid="consumer")
    wf.edges = [
        VibeEdge("7", "image", "10", "value"),
        VibeEdge("11", "0", "12", "images"),
    ]
    wf.metadata["_ingest_snapshot"] = capture_ingest_snapshot({}, wf)

    del wf.nodes["10"]
    del wf.nodes["11"]
    del wf.nodes["12"]
    wf.edges = []
    for iteration in range(4):
        node_id = str(20 + iteration)
        lowered_uid = clone_uid("loop", "consumer", iteration)
        wf.nodes[node_id] = VibeNode(
            node_id,
            "SaveImage",
            uid=lowered_uid,
            metadata={
                "vibecomfy.lowering": {
                    "source_uid": "consumer",
                    "loop_uid": "loop",
                    "iteration_index": iteration,
                }
            },
        )
        wf.edges.append(VibeEdge("7", "image", node_id, "images"))

    _emit_semantic_pin(wf, raw_ui)


def test_pinned_semantic_nested_scoped_broadcast_preserves_scope() -> None:
    nodes = {
        "source": ("outer:sg/inner:sg#source", "Producer", None),
        "set": ("outer:sg/inner:sg#set", "SetNode", "BUS"),
        "get": ("outer:sg/inner:sg#get", "GetNode", "BUS"),
        "consumer": ("outer:sg/inner:sg#consumer", "Consumer", None),
    }
    nested, issues = canonical_semantic_link_set(
        nodes,
        [
            ("source", "image", "set", "value"),
            ("get", "0", "consumer", "images"),
        ],
    )
    flat, flat_issues = canonical_semantic_link_set(
        {"source": nodes["source"], "consumer": nodes["consumer"]},
        [("source", "image", "consumer", "images")],
    )
    assert nested == flat == (
        ("outer:sg/inner:sg#source", "image", "outer:sg/inner:sg#consumer", "images"),
    )
    assert issues == flat_issues == ()


@pytest.mark.parametrize(
    ("after_links", "expected_after"),
    [
        ([], []),
        (
            [
                ("source", "model", "consumer", "images"),
                ("source", "model", "other", "images"),
            ],
            [
                ["source-uid", "model", "consumer-uid", "images"],
                ["source-uid", "model", "other-uid", "images"],
            ],
        ),
        ([("source", "model", "other", "images")], [["source-uid", "model", "other-uid", "images"]]),
        ([("source", "model", "consumer", "mask")], [["source-uid", "model", "consumer-uid", "mask"]]),
        ([("source", "clip", "consumer", "images")], [["source-uid", "clip", "consumer-uid", "images"]]),
    ],
    ids=["removed", "added", "repointed", "consumer_input_changed", "source_output_changed"],
)
def test_pinned_semantic_genuine_consumer_change_refuses(
    after_links: list[tuple[str, str, str, str]],
    expected_after: list[list[str]],
) -> None:
    wf, raw_ui = _semantic_pin_workflow()
    wf.nodes["9"] = VibeNode("9", "SaveImage", uid="consumer-uid")
    wf.nodes["10"] = VibeNode("10", "SaveImage", uid="other-uid")
    wf.nodes["7"].uid = "source-uid"
    raw_ui["nodes"][0]["properties"]["vibecomfy_uid"] = "source-uid"
    wf.edges = [VibeEdge("7", "model", "9", "images")]
    wf.metadata["_ingest_snapshot"] = capture_ingest_snapshot({}, wf)
    id_for = {"source": "7", "consumer": "9", "other": "10"}
    wf.edges = [VibeEdge(id_for[a], b, id_for[c], d) for a, b, c, d in after_links]

    with warnings.catch_warnings(), pytest.raises(RefusedEmit) as exc_info:
        warnings.simplefilter("ignore")
        _emit_semantic_pin(wf, raw_ui)

    link_delta = exc_info.value.diff["7"]["details"]["link_delta"]["semantic_link_set"]
    assert link_delta["before"] == [["source-uid", "model", "consumer-uid", "images"]]
    assert link_delta["after"] == expected_after


@pytest.mark.parametrize(
    ("nodes", "links", "issue_prefix"),
    [
        (
            {"r": ("reroute", "Reroute", None), "c": ("consumer", "Consumer", None)},
            [("r", "0", "c", "input")],
            "reroute_source_count:r:0",
        ),
        (
            {
                "r1": ("reroute-1", "Reroute", None),
                "r2": ("reroute-2", "Reroute", None),
                "c": ("consumer", "Consumer", None),
            },
            [("r1", "0", "r2", ""), ("r2", "0", "r1", ""), ("r1", "0", "c", "input")],
            "cyclic_path:",
        ),
        (
            {"g": ("get", "GetNode", "MISSING"), "c": ("consumer", "Consumer", None)},
            [("g", "0", "c", "input")],
            "broadcast_setter_count:g:MISSING:0",
        ),
        (
            {
                "s1": ("source-1", "Producer", None),
                "s2": ("source-2", "Producer", None),
                "r": ("reroute", "Reroute", None),
                "c": ("consumer", "Consumer", None),
            },
            [
                ("s1", "0", "r", ""),
                ("s2", "0", "r", ""),
                ("r", "0", "c", "input"),
            ],
            "reroute_source_count:r:2",
        ),
    ],
    ids=["orphaned_reroute", "cyclic_reroute", "orphaned_broadcast", "ambiguous_reroute"],
)
def test_pinned_semantic_unresolved_paths_fail_closed_deterministically(
    nodes: dict[str, tuple[str, str, str | None]],
    links: list[tuple[str, str, str, str]],
    issue_prefix: str,
) -> None:
    first = canonical_semantic_link_set(nodes, links)
    second = canonical_semantic_link_set(nodes, reversed(links))
    assert first == second
    assert any(issue.startswith(issue_prefix) for issue in first[1])


def test_pinned_semantic_orphaned_consumer_path_refuses_with_resolution_issue() -> None:
    wf, raw_ui = _semantic_pin_workflow()
    wf.nodes["9"] = VibeNode("9", "SaveImage", uid="consumer")
    wf.edges = [VibeEdge("7", "0", "9", "images")]
    wf.metadata["_ingest_snapshot"] = capture_ingest_snapshot({}, wf)

    wf.nodes["11"] = VibeNode("11", "GetNode", uid="orphan-get", widgets={"widget_0": "MISSING"})
    wf.edges = [VibeEdge("11", "0", "9", "images")]

    with warnings.catch_warnings(), pytest.raises(RefusedEmit) as exc_info:
        warnings.simplefilter("ignore")
        _emit_semantic_pin(wf, raw_ui)

    semantic_delta = exc_info.value.diff["7"]["details"]["link_delta"]["semantic_link_set"]
    assert semantic_delta["before"] == [["uid-dynamic", "0", "consumer", "images"]]
    assert semantic_delta["after"] == []
    assert semantic_delta["after_resolution_issues"] == [
        "broadcast_setter_count:11:MISSING:0"
    ]


def test_pinned_semantic_cyclic_consumer_path_refuses_fail_closed() -> None:
    wf, raw_ui = _semantic_pin_workflow()
    wf.nodes["9"] = VibeNode("9", "SaveImage", uid="consumer")
    wf.edges = [VibeEdge("7", "0", "9", "images")]
    wf.metadata["_ingest_snapshot"] = capture_ingest_snapshot({}, wf)

    wf.nodes["11"] = VibeNode("11", "Reroute", uid="reroute-1")
    wf.nodes["12"] = VibeNode("12", "Reroute", uid="reroute-2")
    wf.edges = [
        VibeEdge("11", "0", "12", ""),
        VibeEdge("12", "0", "11", ""),
        VibeEdge("11", "0", "9", "images"),
    ]

    with warnings.catch_warnings(), pytest.raises(RefusedEmit) as exc_info:
        warnings.simplefilter("ignore")
        _emit_semantic_pin(wf, raw_ui)

    semantic_delta = exc_info.value.diff["7"]["details"]["link_delta"]["semantic_link_set"]
    assert semantic_delta["after"] == []
    assert len(semantic_delta["after_resolution_issues"]) == 1
    assert semantic_delta["after_resolution_issues"][0].startswith("cyclic_path:")


def test_pinned_semantic_multiplicity_dedupes_but_ports_remain_identity() -> None:
    nodes = {
        "s": ("source", "Producer", None),
        "c": ("consumer", "Consumer", None),
    }
    semantic, issues = canonical_semantic_link_set(
        nodes,
        [
            ("s", "model", "c", "input"),
            ("s", "model", "c", "input"),
            ("s", "clip", "c", "input"),
        ],
    )
    assert semantic == (
        ("source", "clip", "consumer", "input"),
        ("source", "model", "consumer", "input"),
    )
    assert issues == ()


def test_pinned_output_link_count_mismatch_overlays_ir_ids() -> None:
    """Captured raw _ui may list extra stale output links; pin must emit the IR link set."""
    # Reuse the connected DynamicRows fixture but put TWO stale links on the
    # pinned node's output while the IR has only one outgoing edge.
    raw_ui = _raw_connected_dynamic_ui()
    raw_ui["nodes"][0]["outputs"][0]["links"] = [43, 999]
    wf = _wf()
    wf.nodes["7"] = VibeNode(
        "7",
        "DynamicRows",
        uid="uid-dynamic",
        raw_widgets=_raw_widgets(),
    )
    wf.nodes["1"] = VibeNode("1", "KSampler", widgets={"widget_0": 4})
    wf.nodes["9"] = VibeNode("9", "SaveImage", widgets={"filename_prefix": "out"})
    wf.edges.extend(
        [
            VibeEdge("1", "0", "7", "image"),
            VibeEdge("7", "0", "9", "images"),
        ]
    )

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        ui = emit_ui_json(
            wf,
            schema_provider=_provider(),
            prior_store=store_from_ui_json(raw_ui),
            prior_ui_payload=raw_ui,
        )

    # Emit succeeded (no RefusedEmit) and the pinned output carries exactly the
    # single remapped global link id, not the stale captured pair.
    pinned = next(node for node in ui["nodes"] if node["id"] == 7)
    assert pinned["outputs"][0]["links"] == [2]
    assert "999" not in json.dumps(ui)
    assert "43" not in json.dumps(ui)


def test_isolated_pinned_node_drops_stale_raw_link_ref() -> None:
    """Rich edges are authority: a captured input link with no IR edge is dropped."""
    raw_ui = _raw_dynamic_ui()
    raw_ui["nodes"][0]["inputs"] = [{"name": "image", "type": "IMAGE", "link": 42}]
    wf = _wf()
    wf.nodes["7"] = VibeNode(
        "7",
        "DynamicRows",
        uid="uid-dynamic",
        raw_widgets=_raw_widgets(),
    )

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        ui = emit_ui_json(
            wf,
            prior_store=store_from_ui_json(raw_ui),
            prior_ui_payload=raw_ui,
        )

    pinned = next(node for node in ui["nodes"] if node["id"] == 7)
    image_inputs = [item for item in (pinned.get("inputs") or []) if item.get("name") == "image"]
    assert image_inputs
    assert image_inputs[0].get("link") is None
    assert "42" not in json.dumps(ui)


def test_collateral_overflow_pins_while_edited_ksampler_regenerates() -> None:
    """Collateral overflow node pins opaque beside an edited KSampler.

    When a prior UI payload contains both an overflowing node and a
    KSampler, and only the KSampler is edited (widget delta), the
    collateral overflow node should pin opaque while the KSampler
    regenerates normally.
    """
    raw_ui = {
        "nodes": [
            {
                "id": 1,
                "type": "KSampler",
                "pos": [10, 20],
                "size": [300, 120],
                "flags": {},
                "order": 0,
                "mode": 0,
                "inputs": [],
                "outputs": [],
                "properties": {"vibecomfy_uid": "uid-ksampler"},
                "widgets_values": [42, "fixed", 20, 7.0, "euler", "normal", 1.0],
            },
            {
                "id": 7,
                "type": "OverflowNode",
                "pos": [400, 20],
                "size": [300, 120],
                "flags": {},
                "order": 1,
                "mode": 0,
                "inputs": [],
                "outputs": [],
                "properties": {"vibecomfy_uid": "uid-overflow"},
                "widgets_values": [10, 20, 30],
            },
        ],
        "links": [],
    }

    provider = _Provider(
        {
            "KSampler": _schema(
                "KSampler",
                {
                    "seed": InputSpec("INT"),
                    "steps": InputSpec("INT"),
                    "cfg": InputSpec("FLOAT"),
                    "sampler_name": InputSpec("STRING"),
                    "scheduler": InputSpec("STRING"),
                    "denoise": InputSpec("FLOAT"),
                },
                [OutputSpec("IMAGE", "IMAGE")],
            ),
            "OverflowNode": _schema(
                "OverflowNode",
                {"value": InputSpec("INT")},
                [OutputSpec("INT", "INT")],
            ),
        }
    )

    wf = _wf()
    wf.nodes["1"] = VibeNode(
        "1",
        "KSampler",
        uid="uid-ksampler",
        widgets={"widget_0": 42},
    )
    # Simulate an edit: change the seed widget value
    wf.metadata["_ingest_snapshot"] = capture_ingest_snapshot({}, wf)
    wf.nodes["1"].widgets["widget_0"] = 99

    wf.nodes["7"] = VibeNode(
        "7",
        "OverflowNode",
        uid="uid-overflow",
        widgets={"widget_0": 10, "widget_1": 20, "widget_2": 30},
    )

    report: list[dict[str, Any]] = []
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        ui = emit_ui_json(
            wf,
            schema_provider=provider,
            prior_store=store_from_ui_json(raw_ui),
            prior_ui_payload=raw_ui,
            recovery_report=report,
        )

    # Collateral overflow node should be pinned opaque
    overflow_entry = next(item for item in report if item.get("node_id") == "7")
    assert overflow_entry["widget_shape_verdict"] == "pin_opaque"
    assert overflow_entry["widget_shape_recovery"] == "carry_forward_raw_ui"

    # Its widgets_values should be the original raw payload
    overflow_ui = next(node for node in ui["nodes"] if node["id"] == 7)
    assert overflow_ui["widgets_values"] == [10, 20, 30]

    # KSampler should have regenerated (or refused) — at minimum the
    # report must contain a verdict for it
    ksampler_entry = next(item for item in report if item.get("node_id") == "1")
    assert ksampler_entry["widget_shape_verdict"] in {
        "safe_to_regenerate",
        "pin_opaque",
        "refuse",
    }
