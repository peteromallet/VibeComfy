"""Tests for store_from_ui_json — Pass 1 node entries + Pass 2 endpoint re-keying."""
import json
import tempfile
from pathlib import Path

import pytest

from vibecomfy.porting.layout_store import STORE_VERSION, store_from_ui_json


# ── helpers ──────────────────────────────────────────────────────────────────

def _node(lit_id, uid=None, pos=None, size=None, mode=0, color=None):
    props = {}
    if uid:
        props["vibecomfy_uid"] = uid
    return {
        "id": lit_id,
        "type": "TestNode",
        "pos": pos or [lit_id * 100, 200],
        "size": size or [200, 100],
        "mode": mode,
        "color": color,
        "flags": {},
        "properties": props,
    }


def _minimal_ui(nodes=None, groups=None, extra=None, definitions=None, lastRerouteId=None):
    ui = {"nodes": nodes or [], "groups": groups or []}
    if extra is not None:
        ui["extra"] = extra
    if definitions is not None:
        ui["definitions"] = definitions
    if lastRerouteId is not None:
        ui["lastRerouteId"] = lastRerouteId
    return ui


# ── envelope shape ────────────────────────────────────────────────────────────

def test_envelope_has_required_keys():
    envelope = store_from_ui_json(_minimal_ui())
    for key in ("store_version", "vibecomfy_version", "schema_hash", "entries",
                "groups", "extra", "lastRerouteId", "definitions",
                "virtual_wires", "unkeyed"):
        assert key in envelope, f"missing key: {key}"
    assert envelope["store_version"] == STORE_VERSION


# ── Pass 1: uid-keyed entries ─────────────────────────────────────────────────

def test_uid_node_appears_in_entries():
    ui = _minimal_ui(nodes=[_node(1, uid="abc-123")])
    env = store_from_ui_json(ui)
    assert "abc-123" in env["entries"]
    entry = env["entries"]["abc-123"]
    assert entry["pos"] is not None
    assert "1" not in env["unkeyed"]


def test_uidless_node_goes_to_unkeyed_not_entries():
    ui = _minimal_ui(nodes=[_node(5)])
    env = store_from_ui_json(ui)
    assert env["entries"] == {}
    assert "5" in env["unkeyed"]


def test_mixed_uid_and_uidless():
    ui = _minimal_ui(nodes=[
        _node(1, uid="uid-A"),
        _node(2),  # uidless
        _node(3, uid="uid-B"),
    ])
    env = store_from_ui_json(ui)
    assert set(env["entries"]) == {"uid-A", "uid-B"}
    assert "2" in env["unkeyed"]
    assert "1" not in env["unkeyed"]
    assert "3" not in env["unkeyed"]


def test_entry_carries_pos_size_mode_flags_color_properties():
    ui = _minimal_ui(nodes=[
        {
            "id": 10, "type": "X",
            "pos": [50, 60], "size": [300, 150],
            "mode": 2, "color": "#ff0000", "flags": {"collapsed": True},
            "properties": {"vibecomfy_uid": "uid-X", "extra_prop": "val"},
        }
    ])
    env = store_from_ui_json(ui)
    e = env["entries"]["uid-X"]
    assert e["pos"] == [50, 60]
    assert e["size"] == [300, 150]
    assert e["mode"] == 2
    assert e["color"] == "#ff0000"
    assert e["flags"] == {"collapsed": True}
    assert e["properties"]["extra_prop"] == "val"


# ── Pass 1: path input ────────────────────────────────────────────────────────

def test_accepts_file_path():
    ui = _minimal_ui(nodes=[_node(1, uid="file-uid")])
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump(ui, f)
        path = Path(f.name)
    try:
        env = store_from_ui_json(path)
        assert "file-uid" in env["entries"]
    finally:
        path.unlink()


def test_accepts_string_path():
    ui = _minimal_ui(nodes=[_node(1, uid="str-path-uid")])
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump(ui, f)
        path = f.name
    try:
        env = store_from_ui_json(path)
        assert "str-path-uid" in env["entries"]
    finally:
        Path(path).unlink()


# ── Pass 2: group re-keying ───────────────────────────────────────────────────

def test_group_node_ids_rekey_to_uids():
    ui = _minimal_ui(
        nodes=[_node(1, uid="uid-1"), _node(2, uid="uid-2")],
        groups=[{"title": "G", "bounding": [0, 0, 800, 600], "nodes": [1, 2]}],
    )
    env = store_from_ui_json(ui)
    assert env["groups"][0]["nodes"] == ["uid-1", "uid-2"]


def test_group_uid_already_rekey_passthrough():
    # groups whose node entries are strings already are passed through
    ui = _minimal_ui(
        nodes=[_node(3, uid="uid-3")],
        groups=[{"title": "H", "bounding": [0, 0, 400, 400], "nodes": ["uid-3"]}],
    )
    env = store_from_ui_json(ui)
    assert env["groups"][0]["nodes"] == ["uid-3"]


# ── Pass 2: virtual_wire re-keying ────────────────────────────────────────────

def test_virtual_wire_endpoints_rekeyed():
    ui = _minimal_ui(
        nodes=[_node(7, uid="uid-7"), _node(8, uid="uid-8")],
        extra={
            "virtual_wires": {
                "vw-key": {"type": "Get", "channel": "ch", "endpoints": [7, 8]},
            }
        },
    )
    env = store_from_ui_json(ui)
    vw = env["virtual_wires"]["vw-key"]
    assert vw["endpoints"] == ["uid-7", "uid-8"]
    assert "unkeyed_endpoints" not in env["extra"]


def test_unresolved_virtual_wire_endpoint_in_unkeyed_endpoints():
    ui = _minimal_ui(
        nodes=[_node(9, uid="uid-9")],
        extra={
            "virtual_wires": {
                "vw-x": {"type": "Set", "channel": "c", "endpoints": [9, 99]},
            }
        },
    )
    env = store_from_ui_json(ui)
    vw = env["virtual_wires"]["vw-x"]
    assert vw["endpoints"][0] == "uid-9"
    assert vw["endpoints"][1] == 99          # unresolved, kept as-is
    assert 99 in env["extra"]["unkeyed_endpoints"]


def test_multiple_unresolved_endpoints_accumulated():
    ui = _minimal_ui(
        nodes=[],
        extra={
            "virtual_wires": {
                "a": {"type": "Get", "channel": "x", "endpoints": [1, 2]},
                "b": {"type": "Set", "channel": "y", "endpoints": [3]},
            }
        },
    )
    env = store_from_ui_json(ui)
    assert set(env["extra"]["unkeyed_endpoints"]) == {1, 2, 3}


def test_virtual_wires_moved_out_of_extra_into_top_level():
    ui = _minimal_ui(
        nodes=[_node(1, uid="u1")],
        extra={"ds": {"scale": 1.0}, "virtual_wires": {"vw": {"type": "Get", "endpoints": [1]}}},
    )
    env = store_from_ui_json(ui)
    assert "virtual_wires" not in env["extra"]
    assert "vw" in env["virtual_wires"]
    assert env["extra"]["ds"] == {"scale": 1.0}


# ── Pass 2: definitions re-keying ────────────────────────────────────────────

def test_definitions_preserved_in_envelope():
    defs = {"sg-uuid": {"nodes": [{"id": 1, "pos": [0, 0], "size": [100, 50]}]}}
    ui = _minimal_ui(definitions=defs)
    env = store_from_ui_json(ui)
    assert "sg-uuid" in env["definitions"]


def test_lastRerouteId_preserved():
    ui = _minimal_ui(lastRerouteId=42)
    env = store_from_ui_json(ui)
    assert env["lastRerouteId"] == 42


# ── round-trip smoke ──────────────────────────────────────────────────────────

def test_round_trip_corpus_workflow():
    """Build envelope from a real corpus workflow; no crash, entries keyed."""
    import glob
    paths = glob.glob("workflow_corpus/**/*.json", recursive=True)
    assert paths, "no corpus files found"
    path = paths[0]
    import json as _json
    ui = _json.load(open(path))
    env = store_from_ui_json(ui)
    assert isinstance(env["entries"], dict)
    assert isinstance(env["groups"], list)
    assert isinstance(env["virtual_wires"], dict)
    assert "store_version" in env
