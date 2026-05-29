"""Frozen sidecar layout store for M1.5. Schema is FROZEN for M2.

Sidecar schema: {"layout_version": 1, "nodes": {uid: {"pos": [x, y], "size": [w, h]}}}

The sidecar lives alongside the converted .py file with the suffix .layout.json
(e.g. flat.py → flat.layout.json).
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from vibecomfy.workflow import VibeWorkflow


def sidecar_path_for(py_path: Path) -> Path:
    """Return the sidecar layout path for a given .py file path.

    flat.py → flat.layout.json
    """
    return py_path.with_suffix(".layout.json")


def write_layout(py_path: Path, wf: VibeWorkflow) -> Path:
    """Serialize each node's uid → pos/size to the sidecar file.

    Skips nodes with an empty uid or no pos captured in metadata["_ui"].
    Returns the sidecar path written.
    """
    nodes: dict[str, dict] = {}
    for node in wf.nodes.values():
        uid = node.uid
        if not uid:
            continue
        ui = node.metadata.get("_ui")
        if not isinstance(ui, dict):
            continue
        pos = ui.get("pos")
        if pos is None:
            continue
        size = ui.get("size")
        nodes[uid] = {"pos": pos, "size": size}

    sidecar = sidecar_path_for(py_path)
    sidecar.write_text(
        json.dumps({"layout_version": 1, "nodes": nodes}, indent=2),
        encoding="utf-8",
    )
    return sidecar


def read_layout(py_path: Path) -> dict[str, dict]:
    """Load the sidecar layout file for py_path.

    Returns {uid: {pos, size}} mapping, or {} if the sidecar is absent.
    """
    sidecar = sidecar_path_for(py_path)
    if not sidecar.exists():
        return {}
    try:
        data = json.loads(sidecar.read_text(encoding="utf-8"))
        return data.get("nodes", {})
    except (json.JSONDecodeError, OSError):
        return {}
