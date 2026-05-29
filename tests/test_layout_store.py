"""Tests for vibecomfy.porting.layout_store (T3).

Covers sidecar_path_for naming, write→read round-trip, skip-empty-uid,
skip-no-pos, and absent-sidecar fallback.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from vibecomfy.porting.layout_store import read_layout, sidecar_path_for, write_layout
from vibecomfy.workflow import VibeNode, VibeWorkflow, WorkflowSource


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _wf(wf_id: str = "test") -> VibeWorkflow:
    return VibeWorkflow(wf_id, WorkflowSource(wf_id))


def _node(node_id: str, uid: str = "", pos=None, size=None) -> VibeNode:
    ui: dict = {}
    if pos is not None:
        ui["pos"] = pos
    if size is not None:
        ui["size"] = size
    metadata = {"_ui": ui} if ui else {}
    n = VibeNode(node_id, "SaveImage", metadata=metadata)
    n.uid = uid
    return n


# ---------------------------------------------------------------------------
# sidecar_path_for
# ---------------------------------------------------------------------------


def test_sidecar_path_suffix(tmp_path: Path):
    py_path = tmp_path / "flat.py"
    assert sidecar_path_for(py_path) == tmp_path / "flat.layout.json"


def test_sidecar_path_naming(tmp_path: Path):
    """SD-naming: my_workflow.py → my_workflow.layout.json."""
    py_path = tmp_path / "my_workflow.py"
    sidecar = sidecar_path_for(py_path)
    assert sidecar.name == "my_workflow.layout.json"


# ---------------------------------------------------------------------------
# write → read round-trip
# ---------------------------------------------------------------------------


def test_write_read_round_trip(tmp_path: Path):
    py_path = tmp_path / "flat.py"
    wf = _wf()
    wf.nodes["1"] = _node("1", uid="1", pos=[0, 120], size=[315, 98])
    wf.nodes["2"] = _node("2", uid="2", pos=[430, 10], size=[430, 160])

    written = write_layout(py_path, wf)
    assert written == sidecar_path_for(py_path)
    assert written.exists()

    layout = read_layout(py_path)
    assert layout["1"] == {"pos": [0, 120], "size": [315, 98]}
    assert layout["2"] == {"pos": [430, 10], "size": [430, 160]}


def test_sidecar_schema_version(tmp_path: Path):
    """Written sidecar must have layout_version: 1."""
    py_path = tmp_path / "flat.py"
    wf = _wf()
    wf.nodes["1"] = _node("1", uid="1", pos=[0, 0], size=[100, 100])
    write_layout(py_path, wf)

    raw = json.loads(sidecar_path_for(py_path).read_text())
    assert raw["layout_version"] == 1
    assert "nodes" in raw


# ---------------------------------------------------------------------------
# Skip conditions
# ---------------------------------------------------------------------------


def test_skip_empty_uid(tmp_path: Path):
    """Nodes with empty uid are not written to the sidecar."""
    py_path = tmp_path / "flat.py"
    wf = _wf()
    wf.nodes["1"] = _node("1", uid="", pos=[0, 120], size=[315, 98])
    write_layout(py_path, wf)

    layout = read_layout(py_path)
    assert layout == {}


def test_skip_no_pos(tmp_path: Path):
    """Nodes with uid but no pos in _ui are skipped."""
    py_path = tmp_path / "flat.py"
    wf = _wf()
    # Node has uid but _ui has no pos
    n = VibeNode("1", "SaveImage", metadata={"_ui": {"size": [100, 100]}})
    n.uid = "1"
    wf.nodes["1"] = n
    write_layout(py_path, wf)

    layout = read_layout(py_path)
    assert layout == {}


def test_skip_no_ui_metadata(tmp_path: Path):
    """Nodes with uid but no _ui metadata entry are skipped."""
    py_path = tmp_path / "flat.py"
    wf = _wf()
    n = VibeNode("1", "SaveImage", metadata={})
    n.uid = "1"
    wf.nodes["1"] = n
    write_layout(py_path, wf)

    layout = read_layout(py_path)
    assert layout == {}


# ---------------------------------------------------------------------------
# Absent sidecar returns {}
# ---------------------------------------------------------------------------


def test_read_absent_sidecar(tmp_path: Path):
    """read_layout returns {} when no sidecar file exists."""
    py_path = tmp_path / "nonexistent.py"
    assert read_layout(py_path) == {}


# ---------------------------------------------------------------------------
# Mixed: some nodes written, some skipped
# ---------------------------------------------------------------------------


def test_mixed_nodes(tmp_path: Path):
    """Only nodes with uid and pos are written; others skipped."""
    py_path = tmp_path / "flat.py"
    wf = _wf()
    wf.nodes["1"] = _node("1", uid="1", pos=[0, 120], size=[315, 98])
    wf.nodes["2"] = _node("2", uid="", pos=[430, 10], size=[430, 160])  # empty uid
    wf.nodes["3"] = _node("3", uid="3", pos=None, size=[210, 46])        # no pos

    write_layout(py_path, wf)
    layout = read_layout(py_path)

    assert "1" in layout
    assert "2" not in layout
    assert "3" not in layout
