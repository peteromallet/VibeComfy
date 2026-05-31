from __future__ import annotations

import json
import warnings
from typing import Any

import pytest

from vibecomfy.porting.layout_store import store_from_ui_json
from vibecomfy.porting.refuse import RefusedEmit
from vibecomfy.porting.ui_emitter import emit_ui_json
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
        "KSampler",
        widgets={f"widget_{idx}": idx for idx in range(20)},
    )

    report: list[dict[str, Any]] = []
    with pytest.raises(RefusedEmit) as exc_info:
        emit_ui_json(wf, schema_provider=_provider(), recovery_report=report)

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


def test_isolated_pinned_node_with_stale_raw_link_ref_refuses() -> None:
    raw_ui = _raw_dynamic_ui()
    raw_ui["nodes"][0]["inputs"] = [{"name": "image", "type": "IMAGE", "link": 42}]
    wf = _wf()
    wf.nodes["7"] = VibeNode(
        "7",
        "DynamicRows",
        uid="uid-dynamic",
        raw_widgets=_raw_widgets(),
    )

    with warnings.catch_warnings(), pytest.raises(RefusedEmit) as exc_info:
        warnings.simplefilter("ignore")
        emit_ui_json(
            wf,
            prior_store=store_from_ui_json(raw_ui),
            prior_ui_payload=raw_ui,
        )

    assert exc_info.value.diff["7"]["axis"] == "pinned_link_refs"
    assert exc_info.value.diff["7"]["reason"] == "pinned_link_id_mismatch"
    assert exc_info.value.diff["7"]["details"]["original_reason"] == "unmappable_input_link"
    assert exc_info.value.diff["7"]["details"]["raw_link"] == 42
