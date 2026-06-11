from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from vibecomfy.commands import port as port_mod
from vibecomfy.porting.layout_store import store_from_ui_json
from vibecomfy.porting.emit.ui import extract_raw_ui_node_map
from vibecomfy.workflow import VibeNode, VibeWorkflow, WorkflowSource


def _raw_ui() -> dict[str, Any]:
    return {
        "nodes": [
            {
                "id": 7,
                "type": "DynamicRows",
                "pos": [10, 20],
                "size": [300, 120],
                "widgets_values": [{"lora": "a"}, {"lora": "b"}],
                "properties": {"vibecomfy_uid": "uid-dynamic"},
            }
        ],
        "links": [],
    }


def test_store_from_ui_json_is_furniture_only_while_raw_map_keeps_full_node() -> None:
    raw_ui = _raw_ui()

    store = store_from_ui_json(raw_ui)
    raw_map = extract_raw_ui_node_map(raw_ui)

    assert store["entries"]["uid-dynamic"]["pos"] == [10, 20]
    assert "widgets_values" not in store["entries"]["uid-dynamic"]
    assert raw_map["uid-dynamic"]["widgets_values"] == [{"lora": "a"}, {"lora": "b"}]


def test_cmd_port_export_passes_from_ui_payload_separately_from_prior_store(
    tmp_path: Path,
    monkeypatch,
) -> None:
    source_py = tmp_path / "workflow.py"
    source_py.write_text("# generated scratchpad\n", encoding="utf-8")
    from_ui_path = tmp_path / "prior.json"
    raw_ui = _raw_ui()
    from_ui_path.write_text(json.dumps(raw_ui), encoding="utf-8")

    wf = VibeWorkflow("workflow", WorkflowSource("workflow", str(source_py), "python"))
    wf.nodes["7"] = VibeNode("7", "DynamicRows", uid="uid-dynamic")
    captured: dict[str, Any] = {}

    monkeypatch.setattr(port_mod, "_build_conversion_provider", lambda args: None)
    monkeypatch.setattr(port_mod, "load_workflow_reference", lambda *args, **kwargs: wf)

    def fake_emit_ui_json(workflow, **kwargs):
        captured.update(kwargs)
        return {"nodes": [], "links": [], "groups": [], "extra": {}}

    monkeypatch.setattr(port_mod, "emit_ui_json", fake_emit_ui_json)

    code = port_mod._cmd_port_export(
        argparse.Namespace(
            workflow=str(source_py),
            ready=False,
            to="ui",
            json=False,
            out=str(tmp_path / "out.json"),
            from_path=str(from_ui_path),
            fresh=False,
            strict=False,
            main_positions=False,
            no_virtual_wires=False,
            force_drop=False,
        )
    )

    assert code == 0
    assert captured["prior_store"]["entries"]["uid-dynamic"]["pos"] == [10, 20]
    assert "widgets_values" not in captured["prior_store"]["entries"]["uid-dynamic"]
    assert captured["prior_ui_payload"] == raw_ui
