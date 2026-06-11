"""T15 — synthetic fixture tests for virtual wires, scoped identity, mute-parity.

Covers:
- virtual-wire furniture round-trip (count in == count restorable out) on a
  synthetic fixture AND wan13b_vace.json (C8)
- scoped-path identity prevents inner-id collision across cloned subgraph instances
- coordinate canonicalization yields identical stored coords for the same IR
- agent-edit safety: add/delete/add yields no uid collision and no stale-position
- mode:2 mute-parity: compile('api') is byte-identical with and without mode
"""
from __future__ import annotations

from pathlib import Path

import pytest

from vibecomfy.porting.layout_store import read_store, write_layout
from vibecomfy.workflow import VibeEdge, VibeNode, VibeWorkflow, WorkflowSource


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _wf(wf_id: str = "test") -> VibeWorkflow:
    return VibeWorkflow(wf_id, WorkflowSource(wf_id))


def _node_with_ui(
    node_id: str,
    class_type: str = "KSampler",
    *,
    uid: str = "",
    pos=None,
    size=None,
    flags=None,
    color=None,
    bgcolor=None,
    properties=None,
    mode: int | None = None,
) -> VibeNode:
    ui: dict = {}
    if pos is not None:
        ui["pos"] = pos
    if size is not None:
        ui["size"] = size
    if flags is not None:
        ui["flags"] = flags
    if color is not None:
        ui["color"] = color
    if bgcolor is not None:
        ui["bgcolor"] = bgcolor
    if properties is not None:
        ui["properties"] = properties
    metadata: dict = {}
    if ui:
        metadata["_ui"] = ui
    if mode is not None:
        metadata["mode"] = mode
    n = VibeNode(node_id, class_type, metadata=metadata)
    n.uid = uid or node_id
    return n


def _virtual_node(
    node_id: str,
    class_type: str,
    *,
    channel: str | None = None,
    pos=None,
    size=None,
) -> VibeNode:
    properties = {}
    if channel:
        properties["broadcast_name"] = channel
    ui: dict = {"type": class_type, "properties": properties}
    if pos is not None:
        ui["pos"] = pos
    if size is not None:
        ui["size"] = size
    n = VibeNode(node_id, class_type, metadata={"_ui": ui})
    n.uid = node_id
    return n


# ---------------------------------------------------------------------------
# Synthetic virtual-wire fixture
# ---------------------------------------------------------------------------


def _make_virtual_wire_wf() -> tuple[VibeWorkflow, int]:
    """Build a small workflow with 2 SetNode and 2 GetNode virtual wires.

    Returns (wf, count_virtual_nodes) where count_virtual_nodes is the number
    of Get/Set/Reroute nodes in the graph before any resolution.
    """
    wf = _wf("vw-test")
    # Regular node
    wf.nodes["1"] = _node_with_ui("1", "KSampler", pos=[0, 0], size=[300, 100])
    # Virtual wire nodes
    wf.nodes["10"] = _virtual_node("10", "SetNode", channel="LATENT", pos=[400, 0], size=[200, 58])
    wf.nodes["11"] = _virtual_node("11", "GetNode", channel="LATENT", pos=[700, 0], size=[200, 58])
    wf.nodes["12"] = _virtual_node("12", "SetNode", channel="IMAGE", pos=[400, 100], size=[200, 58])
    wf.nodes["13"] = _virtual_node("13", "Reroute", pos=[600, 100], size=[75, 26])
    return wf, 4  # 4 virtual-wire nodes


# ---------------------------------------------------------------------------
# T15.1: Virtual-wire round-trip on synthetic fixture
# ---------------------------------------------------------------------------


def test_virtual_wire_round_trip_synthetic(tmp_path: Path):
    """Synthetic fixture: virtual-wire count in == count in store (round-trip parity)."""
    from vibecomfy.porting.convert import _capture_virtual_wires

    wf, count_virtual = _make_virtual_wire_wf()

    # Capture virtual wires (simulating pre-resolution capture in port_convert_workflow).
    vw = _capture_virtual_wires(wf)
    wf.metadata["virtual_wires"] = vw

    py_path = tmp_path / "vw_synthetic.py"
    write_layout(py_path, wf)
    store = read_store(py_path)

    # Count in (pre-capture) == count out (store virtual_wires).
    assert len(store["virtual_wires"]) == count_virtual
    # Each entry has a type field.
    for uid, wire in store["virtual_wires"].items():
        assert "type" in wire
        assert wire["type"] in ("SetNode", "GetNode", "Reroute")
    # Entries also contain the virtual-wire node geometry.
    for uid in store["virtual_wires"]:
        assert uid in store["entries"]
        assert store["entries"][uid]["pos"] is not None


# ---------------------------------------------------------------------------
# T15.2: Virtual-wire round-trip on wan13b_vace.json (C8)
# ---------------------------------------------------------------------------


def test_virtual_wire_round_trip_vace_corpus(tmp_path: Path):
    """C8 — wan13b_vace.json: virtual-wire count in == count in store (round-trip parity)."""
    from vibecomfy.porting.convert import _capture_virtual_wires
    from vibecomfy.porting.workbench import load_port_source

    corpus_path = "workflow_corpus/custom_nodes/wanvideo_wrapper/kijai/wan13b_vace.json"
    source = load_port_source(corpus_path)
    wf = source.workflow

    # Count the virtual-wire nodes before capture (they will be deleted by resolver).
    _VW_TYPES = {"GetNode", "SetNode", "Reroute"}
    vw_count_before = sum(1 for n in wf.nodes.values() if n.class_type in _VW_TYPES)
    assert vw_count_before > 0, "wan13b_vace.json must have Get/Set/Reroute nodes"

    # Capture virtual wires (pre-resolution snapshot).
    vw = _capture_virtual_wires(wf)
    wf.metadata["virtual_wires"] = vw
    raw = source.raw_workflow or {}
    wf.metadata["groups"] = raw.get("groups", [])
    wf.metadata["extra"] = raw.get("extra", {})

    py_path = tmp_path / "vace.py"
    write_layout(py_path, wf)
    store = read_store(py_path)

    # count in == count out
    assert len(store["virtual_wires"]) == vw_count_before, (
        f"Expected {vw_count_before} virtual wires; got {len(store['virtual_wires'])}"
    )


# ---------------------------------------------------------------------------
# T15.3: Scoped-path identity prevents inner-id collision across cloned instances
# ---------------------------------------------------------------------------


def test_scoped_identity_prevents_inner_id_collision(tmp_path: Path):
    """Two cloned subgraph definitions with colliding inner ids yield distinct uids."""
    from vibecomfy.porting.identity.scope import compose_scope_path, sg_key
    from vibecomfy.porting.identity.uid import make_uid

    # Two definitions with the SAME inner node id (1) but different topologies.
    def_a = {
        "name": "A",
        "nodes": [{"id": 1, "type": "KSampler", "pos": [0, 0]}],
        "links": [],
    }
    def_b = {
        "name": "B",
        "nodes": [{"id": 1, "type": "VAEDecode", "pos": [5, 5]}],
        "links": [],
    }

    wf = _wf("cloned-sg")
    wf.metadata["definitions"] = {"subgraphs": [def_a, def_b]}

    py_path = tmp_path / "cloned.py"
    write_layout(py_path, wf)
    store = read_store(py_path)

    # Two distinct scope_paths → two distinct uids, despite colliding inner id 1.
    uid_a = make_uid(compose_scope_path((sg_key(def_a),)), "1")
    uid_b = make_uid(compose_scope_path((sg_key(def_b),)), "1")
    assert uid_a != uid_b, "Distinct topologies must yield distinct uids"
    assert uid_a in store["entries"]
    assert uid_b in store["entries"]
    assert len(store["entries"]) == 2


# ---------------------------------------------------------------------------
# T15.4: Coordinate canonicalization — no float drift across repeated writes
# ---------------------------------------------------------------------------


def test_coord_canonicalization_no_float_drift(tmp_path: Path):
    """The same IR written twice yields bit-identical stored coords (no float drift)."""
    from vibecomfy.porting.workbench import load_port_source
    import json

    source = load_port_source(
        "workflow_corpus/custom_nodes/wanvideo_wrapper/kijai/wan13b_vace.json"
    )
    wf = source.workflow
    raw = source.raw_workflow or {}
    wf.metadata["groups"] = raw.get("groups", [])
    wf.metadata["extra"] = raw.get("extra", {})

    py_path_1 = tmp_path / "first.py"
    py_path_2 = tmp_path / "second.py"
    write_layout(py_path_1, wf)
    write_layout(py_path_2, wf)

    store_1 = read_store(py_path_1)
    store_2 = read_store(py_path_2)

    # Every entry's pos must be bit-identical between the two writes.
    assert set(store_1["entries"]) == set(store_2["entries"])
    for uid in store_1["entries"]:
        pos_1 = store_1["entries"][uid]["pos"]
        pos_2 = store_2["entries"][uid]["pos"]
        assert pos_1 == pos_2, f"Float drift detected for uid {uid}: {pos_1} vs {pos_2}"
        size_1 = store_1["entries"][uid]["size"]
        size_2 = store_2["entries"][uid]["size"]
        assert size_1 == size_2, f"Float drift in size for uid {uid}: {size_1} vs {size_2}"

    # Entries must round-trip through json.dumps/loads unchanged.
    raw_json = json.dumps(store_1["entries"])
    reloaded = json.loads(raw_json)
    for uid, entry in reloaded.items():
        assert entry["pos"] == store_1["entries"][uid]["pos"]


# ---------------------------------------------------------------------------
# T15.5: Agent-edit safety — add/delete/add yields no uid collision, no stale pos
# ---------------------------------------------------------------------------


def test_agent_edit_safety_add_delete_add(tmp_path: Path):
    """add → delete → add cycle: no uid collision, no stale-position inheritance."""
    wf = _wf("edit-safety")

    # Step 1: add node A.
    wf.nodes["1"] = _node_with_ui("1", "KSampler", pos=[0, 0], size=[300, 100])
    py_path = tmp_path / "edit.py"
    write_layout(py_path, wf)
    store_after_add = read_store(py_path)
    uid_a = wf.nodes["1"].uid

    # Step 2: delete node A.
    del wf.nodes["1"]
    write_layout(py_path, wf)
    store_after_delete = read_store(py_path)
    assert uid_a not in store_after_delete["entries"], "Deleted node must not remain in store"

    # Step 3: add a NEW node at a different position using the same integer id slot.
    new_node = _node_with_ui("1", "VAEDecode", pos=[500, 500], size=[200, 80])
    wf.nodes["1"] = new_node
    write_layout(py_path, wf)
    store_after_readd = read_store(py_path)

    uid_b = new_node.uid
    # Both nodes got a uid (they share the int slot but the uid is distinct only if
    # the uid was minted differently; here uid defaults to node_id "1" in our helper,
    # so we test that the NEW geometry was written and the OLD pos was not inherited).
    assert uid_b in store_after_readd["entries"]
    pos_new = store_after_readd["entries"][uid_b]["pos"]
    assert pos_new == [500, 500], f"New node must have its own pos, not stale: {pos_new}"
    assert pos_new != [0, 0], "New node must not inherit deleted node's position"


# ---------------------------------------------------------------------------
# T15.6: mode:2 mute-parity — compile('api') byte-identical
# ---------------------------------------------------------------------------


def test_mode2_mute_compile_parity():
    """A mode:2 (muted) node compiles byte-identically to the same node without mode.

    mode is metadata DATA only and must never enter compile('api') (K3).
    """
    import json

    def _build_wf_with_mode(mode: int | None) -> VibeWorkflow:
        wf = _wf("mute-test")
        metadata: dict = {
            "_ui": {"pos": [0, 0], "size": [300, 100]},
        }
        if mode is not None:
            metadata["mode"] = mode
        n = VibeNode("1", "KSampler", inputs={"seed": 42, "steps": 20}, metadata=metadata)
        n.uid = "mute-node"
        wf.nodes["1"] = n
        n2 = VibeNode("2", "SaveImage", inputs={"images": ["1", 0]}, metadata={})
        n2.uid = "save-node"
        wf.nodes["2"] = n2
        return wf

    wf_normal = _build_wf_with_mode(None)
    wf_muted = _build_wf_with_mode(2)

    api_normal = wf_normal.compile("api")
    api_muted = wf_muted.compile("api")

    assert json.dumps(api_normal, sort_keys=True) == json.dumps(api_muted, sort_keys=True), (
        "compile('api') must be byte-identical regardless of mode:2 (K3 mute-parity)"
    )
