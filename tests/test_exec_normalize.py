from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from vibecomfy.comfy_backend import ComfyCompatibility
from vibecomfy.ingest.normalize import (
    EXEC_SOURCE_MAX_BYTES,
    EXEC_SOURCE_MAX_TOTAL_BYTES,
    convert_to_vibe_format,
    normalize_to_api,
)


def _exec_io() -> dict[str, list[list[str]]]:
    return {
        "inputs": [["image", "IMAGE"]],
        "outputs": [["image", "IMAGE"]],
    }


def _ui_exec_node(source: str) -> dict:
    return {
        "nodes": [
            {
                "id": 1,
                "type": "vibecomfy.exec",
                "inputs": [{"name": "in_0", "type": "IMAGE", "link": None}],
                "widgets_values": {"source": source, "io": _exec_io()},
                "properties": {},
            }
        ],
        "links": [],
    }


def _api_exec_node(source: str, *, include_ui: bool = True) -> dict[str, object]:
    node: dict[str, object] = {
        "class_type": "vibecomfy.exec",
        "inputs": {
            "source": source,
            "io": _exec_io(),
            "in_0": ["2", 0],
        },
    }
    if include_ui:
        node["_ui"] = {"properties": {"vibecomfy": {"io": {"inputs": [["stale", "STRING"]]}}}}
    return node


def test_exec_ui_normalize_routes_source_and_io_to_widgets_and_derives_metadata() -> None:
    api = normalize_to_api(_ui_exec_node("return {'image': image}"), use_comfy_converter=False)
    workflow = convert_to_vibe_format(api)

    node = workflow.nodes["1"]
    assert node.inputs == {}
    assert node.widgets["source"] == "return {'image': image}"
    assert node.widgets["io"] == _exec_io()
    assert node.metadata["_ui"]["properties"]["vibecomfy"]["io"] == _exec_io()


def test_exec_api_reload_rebuilds_only_derived_io_metadata_from_widget_value() -> None:
    workflow = convert_to_vibe_format({"1": _api_exec_node("return {'image': image}")})

    node = workflow.nodes["1"]
    assert "source" not in node.inputs
    assert "io" not in node.inputs
    assert any(
        edge.from_node == "2" and edge.from_output == "0" and edge.to_node == "1" and edge.to_input == "in_0"
        for edge in workflow.edges
    )
    assert node.widgets["source"] == "return {'image': image}"
    assert node.widgets["io"] == _exec_io()
    assert node.metadata["_ui"]["properties"]["vibecomfy"]["io"] == _exec_io()


def test_exec_converter_output_path_enforces_limits_and_rebuilds_metadata() -> None:
    fake_module = MagicMock()
    fake_module.convert_ui_to_api = MagicMock(return_value={"1": _api_exec_node("return {'image': image}", include_ui=False)})
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
    ), patch("vibecomfy.ingest.normalize.check_comfy_compatibility", return_value=compatible):
        api = normalize_to_api(_ui_exec_node("return {'image': image}"))

    workflow = convert_to_vibe_format(api)
    assert workflow.nodes["1"].metadata["_ui"]["properties"]["vibecomfy"]["io"] == _exec_io()


def test_exec_source_per_node_limit_allows_exact_boundary() -> None:
    convert_to_vibe_format({"1": _api_exec_node("x" * EXEC_SOURCE_MAX_BYTES, include_ui=False)})


def test_exec_source_per_node_limit_rejects_over_boundary() -> None:
    with pytest.raises(ValueError, match=f"exceeds {EXEC_SOURCE_MAX_BYTES} bytes"):
        convert_to_vibe_format({"1": _api_exec_node("x" * (EXEC_SOURCE_MAX_BYTES + 1), include_ui=False)})


def test_exec_source_total_limit_rejects_aggregate_overflow() -> None:
    per_node = "x" * EXEC_SOURCE_MAX_BYTES
    node_count = (EXEC_SOURCE_MAX_TOTAL_BYTES // EXEC_SOURCE_MAX_BYTES) + 1
    api = {str(index): _api_exec_node(per_node, include_ui=False) for index in range(1, node_count + 1)}

    with pytest.raises(ValueError, match=f"total exceeds {EXEC_SOURCE_MAX_TOTAL_BYTES} bytes"):
        convert_to_vibe_format(api)
