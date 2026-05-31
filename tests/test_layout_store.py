"""Tests for vibecomfy.porting.layout_store (T3).

Covers sidecar_path_for naming, write→read round-trip, skip-empty-uid,
skip-no-pos, and absent-sidecar fallback.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from vibecomfy.porting.layout_store import (
    STORE_VERSION,
    gc,
    migrate_store,
    read_layout,
    read_store,
    sidecar_path_for,
    write_layout,
)
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
    assert layout["1"]["pos"] == [0, 120]
    assert layout["1"]["size"] == [315, 98]
    assert layout["2"]["pos"] == [430, 10]
    assert layout["2"]["size"] == [430, 160]


def test_sidecar_schema_version(tmp_path: Path):
    """M1.5 schema-version assertion updated (authorized by SD3): envelope v2."""
    py_path = tmp_path / "flat.py"
    wf = _wf()
    wf.nodes["1"] = _node("1", uid="1", pos=[0, 0], size=[100, 100])
    write_layout(py_path, wf)

    raw = json.loads(sidecar_path_for(py_path).read_text())
    assert raw["store_version"] == STORE_VERSION == 2
    assert "layout_version" not in raw
    # Envelope sections present.
    for key in ("entries", "groups", "extra", "lastRerouteId", "definitions", "virtual_wires"):
        assert key in raw
    assert "vibecomfy_version" in raw
    assert "schema_hash" in raw


def test_envelope_full_round_trip(tmp_path: Path):
    """Full envelope round-trips per-uid blob + graph-level sections."""
    py_path = tmp_path / "flat.py"
    wf = _wf()
    n = VibeNode(
        "1",
        "SaveImage",
        metadata={
            "_ui": {
                "pos": [10, 20],
                "size": [300, 100],
                "flags": {"collapsed": True},
                "color": "#223",
                "bgcolor": "#000",
                "properties": {"vibecomfy_uid": "abc", "extra": 1},
            }
        },
    )
    n.uid = "1"
    wf.nodes["1"] = n
    wf.metadata["_layout"] = {
        "groups": [{"title": "g1", "bounding": [0, 0, 50, 50]}],
        "extra": {"ds": {"scale": 1.5, "offset": [3, 4]}},
        "lastRerouteId": 7,
        "definitions": {"sub": {"nodes": []}},
        "virtual_wires": {"u9": {"type": "GetNode", "channel": "LATENT", "endpoints": ["a", "b"]}},
    }

    write_layout(py_path, wf)
    store = read_store(py_path)

    entry = store["entries"]["1"]
    assert entry["pos"] == [10, 20]
    assert entry["size"] == [300, 100]
    assert entry["flags"] == {"collapsed": True}
    assert entry["color"] == "#223"
    assert entry["bgcolor"] == "#000"
    assert entry["properties"] == {"vibecomfy_uid": "abc", "extra": 1}

    assert store["groups"] == [{"title": "g1", "bounding": [0, 0, 50, 50]}]
    assert store["extra"]["ds"] == {"scale": 1.5, "offset": [3, 4]}
    assert store["lastRerouteId"] == 7
    assert store["definitions"] == {"sub": {"nodes": []}}
    assert store["virtual_wires"]["u9"]["channel"] == "LATENT"


def test_pos_canonicalized_on_write(tmp_path: Path):
    """Fractional pos/size are snapped to whole pixels (T3 round-half-even)."""
    py_path = tmp_path / "flat.py"
    wf = _wf()
    wf.nodes["1"] = _node("1", uid="1", pos=[0.5, 1.5], size=[2.5, 100.4])
    write_layout(py_path, wf)

    entry = read_layout(py_path)["1"]
    assert entry["pos"] == [0, 2]  # 0.5->0, 1.5->2 (banker's rounding)
    assert entry["size"] == [2, 100]


def test_envelope_graceful_absent_sections(tmp_path: Path):
    """When metadata has no _layout sections, envelope still serializes defaults."""
    py_path = tmp_path / "flat.py"
    wf = _wf()
    wf.nodes["1"] = _node("1", uid="1", pos=[0, 0], size=[10, 10])
    write_layout(py_path, wf)

    store = read_store(py_path)
    assert store["groups"] == []
    assert store["extra"] == {}
    assert store["lastRerouteId"] is None
    assert store["definitions"] == {}
    assert store["virtual_wires"] == {}


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


# ---------------------------------------------------------------------------
# migrate_store (T6): v1 flat schema -> v2 envelope
# ---------------------------------------------------------------------------


def _v1_flat_fixture() -> dict:
    return {
        "layout_version": 1,
        "nodes": {
            "1": {"pos": [0, 120], "size": [315, 98]},
            "2": {"pos": [430, 10], "size": [430, 160]},
        },
    }


def test_migrate_v1_flat_to_envelope_preserves_pos_size():
    """A v1 flat fixture migrates to the envelope, preserving pos/size per entry."""
    migrated = migrate_store(_v1_flat_fixture())

    assert migrated["store_version"] == STORE_VERSION == 2
    assert "layout_version" not in migrated
    # Envelope sections present.
    for key in ("entries", "groups", "extra", "lastRerouteId", "definitions", "virtual_wires"):
        assert key in migrated

    entries = migrated["entries"]
    assert entries["1"]["pos"] == [0, 120]
    assert entries["1"]["size"] == [315, 98]
    assert entries["2"]["pos"] == [430, 10]
    assert entries["2"]["size"] == [430, 160]


def test_migrate_canonicalizes_fractional_coords():
    """Fractional v1 pos/size are snapped (T3 round-half-even) during migration."""
    migrated = migrate_store({"layout_version": 1, "nodes": {"1": {"pos": [0.5, 1.5], "size": [2.5, 100.4]}}})
    entry = migrated["entries"]["1"]
    assert entry["pos"] == [0, 2]
    assert entry["size"] == [2, 100]


def test_migrate_is_noop_for_v2_envelope():
    """An already-v2 envelope is returned unchanged."""
    py_path_unused = {"store_version": 2, "entries": {"1": {"pos": [1, 2]}}}
    assert migrate_store(py_path_unused) is py_path_unused


def test_migrate_unrecognized_returns_unchanged():
    data = {"something_else": 1}
    assert migrate_store(data) is data


def test_read_store_migrates_v1_sidecar_on_load(tmp_path: Path):
    """A v1 flat sidecar on disk is migrated to the envelope on read."""
    py_path = tmp_path / "flat.py"
    sidecar_path_for(py_path).write_text(json.dumps(_v1_flat_fixture()), encoding="utf-8")

    store = read_store(py_path)
    assert store["store_version"] == 2
    assert store["entries"]["1"]["pos"] == [0, 120]
    assert store["entries"]["2"]["size"] == [430, 160]

    # read_layout sees the migrated entries too.
    layout = read_layout(py_path)
    assert layout["1"]["pos"] == [0, 120]


# ---------------------------------------------------------------------------
# migrate_store: v1 flat fixture with stable vibecomfy_uid keys (T6)
# ---------------------------------------------------------------------------


def _v1_flat_fixture_with_stable_uids() -> dict:
    """A v1 flat layout where node keys are stable vibecomfy_uid values.

    Unlike the simple integer-string fixture above, these keys mimic the
    scoped uid shape that ``make_uid`` produces for subgraph-inner nodes
    (e.g. ``scope_key#local_id``).  This exercises the migration path for a
    v1 sidecar that was already keyed by vibecomfy_uid identities rather than
    raw litegraph integer ids.
    """
    return {
        "layout_version": 1,
        "nodes": {
            "Upscale@sha256abc123#7": {
                "pos": [12, 34],
                "size": [200, 100],
                "flags": {"collapsed": False},
                "color": "#ff0000",
                "bgcolor": "#000000",
                "properties": {"vibecomfy_uid": "Upscale@sha256abc123#7", "cnr_id": "SomeNode"},
            },
            "Upscale@sha256abc123#9": {
                "pos": [56, 78],
                "size": [150, 80],
                "mode": 4,
            },
            "flat_root_node": {
                "pos": [100, 200],
                "size": [300, 120],
                "properties": {"vibecomfy_uid": "flat_root_node", "extra_key": "survives"},
            },
        },
    }


def test_migrate_v1_with_stable_uids_preserves_positions():
    """A v1 flat fixture with stable vibecomfy_uid keys migrates to v2
    with positions attached to the exact same uid strings."""
    migrated = migrate_store(_v1_flat_fixture_with_stable_uids())

    assert migrated["store_version"] == STORE_VERSION == 2
    assert "layout_version" not in migrated
    for key in ("entries", "groups", "extra", "lastRerouteId", "definitions", "virtual_wires"):
        assert key in migrated

    entries = migrated["entries"]
    # Every uid from the v1 fixture is present.
    assert set(entries) == {"Upscale@sha256abc123#7", "Upscale@sha256abc123#9", "flat_root_node"}

    # Positions remain attached to the same uids.
    assert entries["Upscale@sha256abc123#7"]["pos"] == [12, 34]
    assert entries["Upscale@sha256abc123#7"]["size"] == [200, 100]
    assert entries["Upscale@sha256abc123#9"]["pos"] == [56, 78]
    assert entries["Upscale@sha256abc123#9"]["size"] == [150, 80]
    assert entries["flat_root_node"]["pos"] == [100, 200]
    assert entries["flat_root_node"]["size"] == [300, 120]

    # Ancillary fields survive migration.
    assert entries["Upscale@sha256abc123#7"]["flags"] == {"collapsed": False}
    assert entries["Upscale@sha256abc123#7"]["color"] == "#ff0000"
    assert entries["Upscale@sha256abc123#7"]["bgcolor"] == "#000000"
    assert entries["Upscale@sha256abc123#7"]["properties"] == {
        "vibecomfy_uid": "Upscale@sha256abc123#7",
        "cnr_id": "SomeNode",
    }
    assert entries["Upscale@sha256abc123#9"]["mode"] == 4
    assert entries["flat_root_node"]["properties"] == {
        "vibecomfy_uid": "flat_root_node",
        "extra_key": "survives",
    }


def test_v1_stable_uids_read_store_write_store_roundtrip(tmp_path: Path):
    """Full round-trip: v1 sidecar on disk → read_store (migrate) →
    write_store → read_store → positions still attached to same uids."""
    from vibecomfy.porting.layout_store import write_store

    py_path = tmp_path / "roundtrip.py"

    # Write the v1 fixture to the sidecar path.
    sidecar_path_for(py_path).write_text(
        json.dumps(_v1_flat_fixture_with_stable_uids()), encoding="utf-8"
    )

    # read_store migrates the v1 data to a v2 envelope.
    store_after_migrate = read_store(py_path)
    assert store_after_migrate["store_version"] == 2
    assert (
        store_after_migrate["entries"]["Upscale@sha256abc123#7"]["pos"] == [12, 34]
    )
    assert (
        store_after_migrate["entries"]["flat_root_node"]["pos"] == [100, 200]
    )

    # Write the migrated envelope back to disk.
    written_path = write_store(py_path, store_after_migrate)
    assert written_path == sidecar_path_for(py_path)
    assert written_path.exists()

    # Read the written v2 envelope back.
    store_after_roundtrip = read_store(py_path)
    entries = store_after_roundtrip["entries"]

    # Every uid and its position survive the full round-trip.
    assert set(entries) == {"Upscale@sha256abc123#7", "Upscale@sha256abc123#9", "flat_root_node"}
    assert entries["Upscale@sha256abc123#7"]["pos"] == [12, 34]
    assert entries["Upscale@sha256abc123#7"]["size"] == [200, 100]
    assert entries["Upscale@sha256abc123#9"]["pos"] == [56, 78]
    assert entries["Upscale@sha256abc123#9"]["size"] == [150, 80]
    assert entries["flat_root_node"]["pos"] == [100, 200]
    assert entries["flat_root_node"]["size"] == [300, 120]

    # Properties blob survives the full write→read cycle too.
    assert entries["flat_root_node"]["properties"] == {
        "vibecomfy_uid": "flat_root_node",
        "extra_key": "survives",
    }


def test_v2_envelope_schema_hash_noop_migration_path(tmp_path: Path):
    """A v2 envelope with the current schema_hash passes through migrate_store
    unchanged (identity no-op), and a write→read round-trip preserves every
    uid→position attachment.

    This test documents the **expected** no-op schema-hash migration path:
    ``migrate_store`` currently gates on ``store_version`` and
    ``layout_version`` only — it does **not** inspect ``schema_hash``.
    If a future schema-shape change alters ``schema_hash`` without bumping
    ``STORE_VERSION``, this test documents that the current contract is
    *no migration* (the envelope round-trips verbatim).  That posture may
    need to change when a real schema drift is introduced; until then this
    test locks the baseline.
    """
    from vibecomfy.porting.layout_store import _schema_hash, write_store

    py_path = tmp_path / "v2_noop.py"

    # Build a v2 envelope directly with the current schema_hash.
    envelope = {
        "store_version": STORE_VERSION,
        "vibecomfy_version": "0",
        "schema_hash": _schema_hash(),
        "entries": {
            "scope_a#7": {"pos": [10, 20], "size": [100, 200], "flags": None,
                          "color": None, "bgcolor": None, "mode": 0, "properties": {}},
            "scope_b#3": {"pos": [30, 40], "size": [150, 250], "flags": None,
                          "color": None, "bgcolor": None, "mode": 0, "properties": {}},
        },
        "groups": [],
        "extra": {},
        "lastRerouteId": None,
        "definitions": {},
        "virtual_wires": {},
    }

    # migrate_store must return the identical object (no-op).
    assert migrate_store(envelope) is envelope

    # Write the envelope to disk and read it back.
    write_store(py_path, envelope)
    store = read_store(py_path)

    assert store["store_version"] == 2
    assert store["schema_hash"] == _schema_hash()
    entries = store["entries"]
    assert set(entries) == {"scope_a#7", "scope_b#3"}
    assert entries["scope_a#7"]["pos"] == [10, 20]
    assert entries["scope_b#3"]["pos"] == [30, 40]

    # read_layout sees the same entries.
    layout = read_layout(py_path)
    assert layout["scope_a#7"]["pos"] == [10, 20]
    assert layout["scope_b#3"]["size"] == [150, 250]


# ---------------------------------------------------------------------------
# gc (T7): prune dead-uid entries
# ---------------------------------------------------------------------------


def _envelope_with(entries: dict, virtual_wires: dict | None = None) -> dict:
    return {
        "store_version": 2,
        "entries": dict(entries),
        "virtual_wires": dict(virtual_wires or {}),
    }


def test_gc_drops_dead_uids_retains_live():
    data = _envelope_with({"1": {"pos": [0, 0]}, "2": {"pos": [1, 1]}, "3": {"pos": [2, 2]}})
    result = gc(data, live_uids={"1", "3"})

    assert set(result["entries"]) == {"1", "3"}
    assert result["entries"]["1"]["pos"] == [0, 0]
    assert result["entries"]["3"]["pos"] == [2, 2]
    assert "2" not in result["entries"]


def test_gc_prunes_virtual_wires_by_uid():
    data = _envelope_with(
        {"1": {"pos": [0, 0]}},
        virtual_wires={"1": {"type": "GetNode"}, "9": {"type": "SetNode"}},
    )
    result = gc(data, live_uids=["1"])
    assert set(result["entries"]) == {"1"}
    assert set(result["virtual_wires"]) == {"1"}


def test_gc_empty_live_set_drops_all():
    data = _envelope_with({"1": {"pos": [0, 0]}, "2": {"pos": [1, 1]}})
    result = gc(data, live_uids=[])
    assert result["entries"] == {}


def test_gc_noop_on_non_envelope():
    data = {"not": "an envelope"}
    assert gc(data, live_uids=["1"]) is data


# ---------------------------------------------------------------------------
# T11: subgraph-inner scoped-uid assembly over metadata['definitions']
# ---------------------------------------------------------------------------


def _sg_def(name: str, nodes: list[dict], links: list | None = None) -> dict:
    return {"name": name, "nodes": nodes, "links": links or []}


def test_inner_definition_entries_keyed_by_scoped_uid(tmp_path: Path):
    """Inner nodes of a captured subgraph definition land in the store keyed by
    a scoped uid (scope_path#local), with canonicalized geometry."""
    from vibecomfy.porting.scope import compose_scope_path, sg_key
    from vibecomfy.porting.uid import make_uid

    inner = {"id": 7, "type": "KSampler", "pos": [10.4, 20.6], "size": [200, 100]}
    definition = _sg_def("Upscale", [inner])

    wf = _wf()
    wf.nodes["1"] = _node("1", uid="1", pos=[0, 0], size=[100, 100])
    wf.metadata["definitions"] = {"subgraphs": [definition]}

    py_path = tmp_path / "flat.py"
    write_layout(py_path, wf)
    store = read_store(py_path)

    scope_path = compose_scope_path((sg_key(definition),))
    expected_uid = make_uid(scope_path, "7")
    assert expected_uid in store["entries"]
    # snap_pos round-half-even canonicalization applied to the inner node.
    assert store["entries"][expected_uid]["pos"] == [10, 21]
    # Top-level node still present alongside the inner entry.
    assert "1" in store["entries"]


def test_inner_definition_uses_vibecomfy_uid_property(tmp_path: Path):
    """An inner node carrying properties['vibecomfy_uid'] is keyed by that uid."""
    from vibecomfy.porting.scope import compose_scope_path, sg_key
    from vibecomfy.porting.uid import make_uid

    inner = {
        "id": 7,
        "type": "KSampler",
        "pos": [0, 0],
        "properties": {"vibecomfy_uid": "carried-uid"},
    }
    definition = _sg_def("Upscale", [inner])

    wf = _wf()
    wf.metadata["definitions"] = {"subgraphs": [definition]}

    py_path = tmp_path / "flat.py"
    write_layout(py_path, wf)
    store = read_store(py_path)

    scope_path = compose_scope_path((sg_key(definition),))
    assert make_uid(scope_path, "carried-uid") in store["entries"]


def test_inner_definition_clones_share_definition_no_crash(tmp_path: Path):
    """Two definitions with colliding inner ids yield distinct scoped uids."""
    d1 = _sg_def("A", [{"id": 1, "type": "KSampler", "pos": [0, 0]}])
    d2 = _sg_def(
        "B", [{"id": 1, "type": "VAEDecode", "pos": [5, 5]}]
    )  # same inner id, different topology

    wf = _wf()
    wf.metadata["definitions"] = {"subgraphs": [d1, d2]}

    py_path = tmp_path / "flat.py"
    write_layout(py_path, wf)
    store = read_store(py_path)

    # Distinct scope_paths -> distinct uids despite the colliding inner id 1.
    assert len(store["entries"]) == 2


# ---------------------------------------------------------------------------
# T12: Capture-verification tests — corpus spot-checks
# ---------------------------------------------------------------------------


def _load_with_furniture(corpus_path: str, tmp_path: Path, tmp_suffix: str = "wf") -> tuple:
    """Load a corpus JSON, populate graph-level furniture from raw_workflow, write layout.

    Returns (wf, store, entries) for assertion.
    """
    from vibecomfy.porting.workbench import load_port_source

    source = load_port_source(corpus_path)
    wf = source.workflow
    raw = source.raw_workflow or {}
    # Populate graph-level sections into metadata so write_layout can read them.
    wf.metadata["groups"] = raw.get("groups", [])
    wf.metadata["extra"] = raw.get("extra", {})
    if "lastRerouteId" in raw:
        wf.metadata["lastRerouteId"] = raw["lastRerouteId"]

    py_path = tmp_path / f"{tmp_suffix}.py"
    write_layout(py_path, wf)
    store = read_store(py_path)
    return wf, store, store["entries"]


def test_corpus_vace_cnr_id_ver_properties_survive(tmp_path: Path):
    """wan13b_vace.json: cnr_id/ver properties, pos/size, flags survive ingest→store (C9)."""
    wf, store, entries = _load_with_furniture(
        "workflow_corpus/custom_nodes/wanvideo_wrapper/kijai/wan13b_vace.json",
        tmp_path,
        "vace",
    )

    # At least all nodes with _ui.pos have entries.
    assert len(entries) > 0

    # Node carrying cnr_id + ver (full properties blob).
    cnr_entry = next(
        (e for e in entries.values() if e.get("properties", {}).get("cnr_id")),
        None,
    )
    assert cnr_entry is not None, "No entry with cnr_id found"
    assert cnr_entry["properties"]["cnr_id"] == "ComfyUI-WanVideoWrapper"
    assert cnr_entry["properties"]["ver"]  # non-empty hash string
    assert cnr_entry["pos"] is not None
    assert cnr_entry["size"] is not None

    # Node with only partial properties (previousName, no cnr_id) — unknown key survives.
    partial_entry = next(
        (
            e
            for e in entries.values()
            if e.get("properties")
            and "previousName" in e["properties"]
            and "cnr_id" not in e["properties"]
        ),
        None,
    )
    assert partial_entry is not None, "No partial-props entry found"
    # 'previousName' is an unknown/extra key — must survive verbatim.
    assert "previousName" in partial_entry["properties"]

    # flags survive (GetNode 124 is collapsed).
    uid_124 = "124"
    if uid_124 in entries:
        assert entries[uid_124]["flags"] == {"collapsed": True}

    # color/bgcolor survive.
    colored = next(
        (e for e in entries.values() if e.get("color")),
        None,
    )
    assert colored is not None, "No entry with color found"
    assert colored.get("bgcolor")

    # Graph-level sections survive.
    assert len(store["groups"]) == 4
    assert "ds" in store["extra"]
    assert store["lastRerouteId"] is None


def test_corpus_recammaster_note_partial_props_survive(tmp_path: Path):
    """wan13b_recammaster.json: Note nodes and partial-props nodes survive ingest→store (C9)."""
    wf, store, entries = _load_with_furniture(
        "workflow_corpus/custom_nodes/wanvideo_wrapper/kijai/wan13b_recammaster.json",
        tmp_path,
        "recammaster",
    )

    # groups and extra.ds survive.
    assert len(store["groups"]) == 3
    assert "ds" in store["extra"]

    # Note nodes (class_type == 'Note') have entries in the store.
    note_uids = [nid for nid, n in wf.nodes.items() if n.class_type == "Note"]
    assert len(note_uids) >= 5, "Expected ≥5 Note nodes in recammaster"
    for uid in note_uids:
        assert uid in entries, f"Note node {uid} missing from store entries"
        assert entries[uid]["pos"] is not None

    # Partial-properties nodes (previousName only, no cnr_id) survive.
    partial_entries = [
        e
        for e in entries.values()
        if e.get("properties")
        and "previousName" in e["properties"]
        and "cnr_id" not in e["properties"]
    ]
    assert len(partial_entries) >= 3, "Expected ≥3 partial-props entries"
    for e in partial_entries:
        assert "previousName" in e["properties"]


def test_python_template_no_furniture_stores_empty_layout(tmp_path: Path):
    """Python-authored workflow with no _ui and no definitions stores an empty but valid envelope."""
    wf = _wf("programmatic")
    n = VibeNode("1", "KSampler", metadata={})
    n.uid = "some-uid"
    wf.nodes["1"] = n

    py_path = tmp_path / "programmatic.py"
    write_layout(py_path, wf)  # must not raise

    store = read_store(py_path)
    assert store["store_version"] == STORE_VERSION
    assert store["entries"] == {}
    assert store["groups"] == []
    assert store["virtual_wires"] == {}
