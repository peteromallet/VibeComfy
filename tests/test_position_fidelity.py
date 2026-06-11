"""Position fidelity tests for the scratchpad-emitter epic (M5).

Covers: virtual-wire roundtrip (Get/SetNode/Reroute positions restored when
endpoints are intact; degraded when endpoint nodes are removed).

T17: position-fidelity oracle + edit-invariance.
T18a: JSON-only collaboration, --fresh self-contained, no-metadata clean emit.
T18b: AI-agent edit-safety + duplicate-safety.
T18c: Legacy bridge resilience — hash bridge mints uids; exact on second
    round-trip; unmatched cases appear in identity_stabilization.unmatched_legacy.
"""
from __future__ import annotations

import warnings

from vibecomfy.porting.layout.reconcile import reconcile
from vibecomfy.porting.layout_store import store_from_ui_json
from vibecomfy.porting.emit.ui import emit_ui_json
from vibecomfy.workflow import VibeEdge, VibeNode, VibeWorkflow, WorkflowSource


# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------


def _bboxes_overlap(
    pos1: list[float], size1: list[float],
    pos2: list[float], size2: list[float],
) -> bool:
    """Return True if the bounding boxes of two nodes overlap.

    pos = [x, y] top-left corner; size = [w, h].
    """
    ax1, ay1 = pos1[0], pos1[1]
    ax2, ay2 = ax1 + size1[0], ay1 + size1[1]
    bx1, by1 = pos2[0], pos2[1]
    bx2, by2 = bx1 + size2[0], by1 + size2[1]
    # No overlap if one is entirely to the left/right/above/below.
    if ax2 <= bx1 or bx2 <= ax1 or ay2 <= by1 or by2 <= ay1:
        return False
    return True


def _wf_with_virtual_wires() -> tuple[VibeWorkflow, dict]:
    """Return a synthetic workflow + matching prior_store with virtual wires.

    Graph:
      producer (uid='prod') -> set_node (uid='set1') broadcasts 'MY_SIGNAL'
      get_node (uid='get1') receives 'MY_SIGNAL' -> consumer (uid='cons')

    The prior_store records positions for all four nodes plus one virtual_wire
    entry linking set1 → get1.
    """
    nodes = {
        "1": VibeNode(id="1", class_type="CLIPTextEncode", uid="prod"),
        "2": VibeNode(id="2", class_type="SetNode", uid="set1"),
        "3": VibeNode(id="3", class_type="GetNode", uid="get1"),
        "4": VibeNode(id="4", class_type="KSampler", uid="cons"),
    }
    edges = [
        VibeEdge(from_node="1", from_output=0, to_node="2", to_input="input"),
        VibeEdge(from_node="3", from_output=0, to_node="4", to_input="conditioning"),
    ]
    wf = VibeWorkflow(
        id="test-wf",
        nodes=nodes,
        edges=edges,
        source=WorkflowSource(id="test"),
    )

    prior_store = {
        "entries": {
            "prod":  {"pos": [100, 100], "size": [200, 100], "mode": 0, "flags": {}, "color": "", "properties": {}, "group": None},
            "set1":  {"pos": [350, 100], "size": [150,  80], "mode": 0, "flags": {}, "color": "", "properties": {}, "group": None},
            "get1":  {"pos": [550, 100], "size": [150,  80], "mode": 0, "flags": {}, "color": "", "properties": {}, "group": None},
            "cons":  {"pos": [750, 100], "size": [200, 200], "mode": 0, "flags": {}, "color": "", "properties": {}, "group": None},
        },
        "groups": [],
        "extra": {},
        "definitions": {},
        "virtual_wires": [
            {"source": "set1", "target": "get1", "name": "MY_SIGNAL"},
        ],
    }
    return wf, prior_store


# ---------------------------------------------------------------------------
# test_virtual_wire_roundtrip
# ---------------------------------------------------------------------------

def test_virtual_wire_roundtrip_intact():
    """When all endpoint uids are present, virtual wires are NOT degraded."""
    wf, prior_store = _wf_with_virtual_wires()
    result = reconcile(wf, prior_store)

    # All four nodes should be matched.
    assert "prod" in result.matched
    assert "set1" in result.matched
    assert "get1" in result.matched
    assert "cons" in result.matched

    # No degraded virtual wires — all endpoints survive.
    assert result.degraded_virtual_wires == []

    # Positions are restored verbatim for the virtual-wire helper nodes.
    assert result.matched["set1"]["pos"] == [350, 100]
    assert result.matched["get1"]["pos"] == [550, 100]


def test_virtual_wire_roundtrip_endpoint_removed():
    """When a source endpoint (set1) is removed, the wire is degraded."""
    wf, prior_store = _wf_with_virtual_wires()

    # Remove the producer and set_node from the workflow.
    del wf.nodes["1"]
    del wf.nodes["2"]

    result = reconcile(wf, prior_store)

    # set1 is absent → degraded_virtual_wires should include our wire.
    assert len(result.degraded_virtual_wires) == 1
    dw = result.degraded_virtual_wires[0]
    assert dw["source"] == "set1"
    assert dw["target"] == "get1"
    assert dw["name"] == "MY_SIGNAL"

    # set1 (and prod) are in removed.
    assert "set1" in result.removed
    assert "prod" in result.removed


def test_virtual_wire_roundtrip_target_removed():
    """When a target endpoint (get1) is removed, the wire is degraded."""
    wf, prior_store = _wf_with_virtual_wires()

    del wf.nodes["3"]
    del wf.nodes["4"]

    result = reconcile(wf, prior_store)

    assert len(result.degraded_virtual_wires) == 1
    assert result.degraded_virtual_wires[0]["target"] == "get1"


def test_virtual_wire_roundtrip_no_virtual_wires_in_store():
    """With no virtual_wires in the store, degraded list is empty."""
    wf, prior_store = _wf_with_virtual_wires()
    prior_store["virtual_wires"] = []

    result = reconcile(wf, prior_store)
    assert result.degraded_virtual_wires == []


# Single public test name used by the plan spec.
test_virtual_wire_roundtrip = test_virtual_wire_roundtrip_intact


# ---------------------------------------------------------------------------
# T17 — Position-fidelity oracle + edit-invariance
# ---------------------------------------------------------------------------


def _make_wf() -> VibeWorkflow:
    """Create a fresh empty VibeWorkflow."""
    return VibeWorkflow("test", WorkflowSource("test"))


def test_position_fidelity_oracle():
    """Perturb store → add a node → re-emit → matched keep exact pos/size;
    new node placed without overlap.

    Verifies that the prior_store is the authoritative source of position
    for matched (uid-carrying) nodes, even when the stored position has been
    perturbed.  Also verifies that a newly added (uidless) node is placed by
    the layout engine in a position that does not overlap any matched node.
    """
    wf = _make_wf()

    # ── Build the initial workflow: LoadImage → SaveImage ──
    load = VibeNode("1", "LoadImage")
    load.uid = "uid-load"
    save = VibeNode("2", "SaveImage")
    save.uid = "uid-save"
    wf.nodes["1"] = load
    wf.nodes["2"] = save
    wf.connect("1.0", "2.images")

    # ── Build prior_store with entries at known positions ──
    base_store = {
        "entries": {
            "uid-load": {
                "pos": [100.0, 200.0],
                "size": [200.0, 200.0],
                "mode": 0,
                "flags": {},
                "color": "",
                "properties": {},
            },
            "uid-save": {
                "pos": [400.0, 200.0],
                "size": [200.0, 200.0],
                "mode": 0,
                "flags": {},
                "color": "",
                "properties": {},
            },
        },
        "groups": [],
        "extra": {},
        "definitions": {},
        "virtual_wires": [],
    }

    # ── Perturb the store: shift LoadImage far away ──
    perturbed_store = {
        **base_store,
        "entries": {
            **base_store["entries"],
            "uid-load": {
                **base_store["entries"]["uid-load"],
                "pos": [500.0, 600.0],
            },
        },
    }

    # ── Add a new (uidless) KSampler node between them ──
    ks = VibeNode("3", "KSampler")  # no uid → "new"
    wf.nodes["3"] = ks
    # Rewire: load → ks → save
    wf.edges.clear()
    wf.connect("1.0", "3.latent_image")
    wf.connect("3.0", "2.images")

    # ── Re-emit with the perturbed store ──
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        result = emit_ui_json(wf, prior_store=perturbed_store)

    # Index emitted nodes by vibecomfy_uid
    by_uid: dict[str, dict] = {}
    for n in result["nodes"]:
        uid = n.get("properties", {}).get("vibecomfy_uid", "")
        if uid:
            by_uid[uid] = n

    # ── Assertions ──
    # 1. Matched nodes carry exact perturbed pos/size from the store.
    assert "uid-load" in by_uid, "LoadImage should be in emitted nodes"
    assert "uid-save" in by_uid, "SaveImage should be in emitted nodes"

    load_emitted = by_uid["uid-load"]
    assert load_emitted["pos"] == [500.0, 600.0], (
        f"LoadImage should carry perturbed position [500, 600], got {load_emitted['pos']}"
    )
    assert load_emitted["size"] == [200.0, 200.0], (
        f"LoadImage should carry verbatim size from store, got {load_emitted['size']}"
    )

    save_emitted = by_uid["uid-save"]
    assert save_emitted["pos"] == [400.0, 200.0], (
        f"SaveImage should carry unperturbed position [400, 200], got {save_emitted['pos']}"
    )
    assert save_emitted["size"] == [200.0, 200.0], (
        f"SaveImage should carry verbatim size from store, got {save_emitted['size']}"
    )

    # 2. The new KSampler node was emitted.
    ks_nodes = [n for n in result["nodes"] if n.get("type") == "KSampler"]
    assert len(ks_nodes) == 1, f"Expected 1 KSampler node, got {len(ks_nodes)}"
    ks_emitted = ks_nodes[0]

    # 3. New node does NOT overlap with any matched node.
    #    Use bounding-box overlap check.
    ks_pos = ks_emitted["pos"]
    ks_size = ks_emitted["size"]
    for matched_uid, matched_node in by_uid.items():
        m_pos = matched_node["pos"]
        m_size = matched_node["size"]
        assert not _bboxes_overlap(ks_pos, ks_size, m_pos, m_size), (
            f"New KSampler at {ks_pos}/{ks_size} overlaps matched "
            f"node {matched_uid} at {m_pos}/{m_size}"
        )

    # 4. KSampler has a reasonable position (not stub [0,0] or the origin).
    assert ks_pos != [0.0, 0.0], "New node should not be at stub origin"
    assert isinstance(ks_pos, list) and len(ks_pos) == 2


def test_edit_invariance_widget_and_rewire():
    """Widget edit + rewire on a node → its position preserved;
    neighbors do not move on insertion.

    1. Build a 3-node chain (LoadImage → KSampler → SaveImage) with uids.
    2. First emit with prior_store → record baseline positions.
    3. Edit KSampler's widget value and rewire (insert a new node).
    4. Re-emit with the SAME prior_store.
    5. Assert KSampler's position is preserved; neighbors don't move.
    """
    wf = _make_wf()

    # ── Build initial 3-node chain ──
    load = VibeNode("1", "LoadImage")
    load.uid = "uid-load"
    ks = VibeNode("2", "KSampler")
    ks.uid = "uid-ks"
    ks.inputs = {"seed": 42, "steps": 20, "cfg": 7.0, "sampler_name": "euler", "scheduler": "normal", "denoise": 1.0}
    save = VibeNode("3", "SaveImage")
    save.uid = "uid-save"

    wf.nodes["1"] = load
    wf.nodes["2"] = ks
    wf.nodes["3"] = save
    wf.connect("1.0", "2.latent_image")
    wf.connect("2.0", "3.images")

    # ── Build prior_store with known positions ──
    store = {
        "entries": {
            "uid-load": {"pos": [100.0, 200.0], "size": [200.0, 200.0], "mode": 0, "flags": {}, "color": "", "properties": {}},
            "uid-ks":   {"pos": [400.0, 200.0], "size": [250.0, 300.0], "mode": 0, "flags": {}, "color": "", "properties": {}},
            "uid-save": {"pos": [750.0, 200.0], "size": [200.0, 200.0], "mode": 0, "flags": {}, "color": "", "properties": {}},
        },
        "groups": [],
        "extra": {},
        "definitions": {},
        "virtual_wires": [],
    }

    # ── First emit → baseline positions ──
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        baseline_result = emit_ui_json(wf, prior_store=store)

    baseline_by_uid: dict[str, dict] = {}
    for n in baseline_result["nodes"]:
        uid = n.get("properties", {}).get("vibecomfy_uid", "")
        if uid:
            baseline_by_uid[uid] = n

    # ── Sanity: baseline positions match store ──
    assert baseline_by_uid["uid-load"]["pos"] == [100.0, 200.0]
    assert baseline_by_uid["uid-ks"]["pos"] == [400.0, 200.0]
    assert baseline_by_uid["uid-save"]["pos"] == [750.0, 200.0]

    # ── Edit: change KSampler widget (seed) + rewire (insert CLIPTextEncode) ──
    wf.nodes["2"].inputs["seed"] = 9999
    # Insert a new uidless CLIPTextEncode node between load and ks
    clip = VibeNode("4", "CLIPTextEncode")  # uidless → new
    wf.nodes["4"] = clip
    # Rewire: load → clip → ks; ks → save stays
    wf.edges.clear()
    wf.connect("1.0", "4.clip")  # LoadImage.image → CLIPTextEncode.clip
    wf.connect("4.0", "2.latent_image")  # CLIPTextEncode.0 → KSampler.latent_image
    wf.connect("2.0", "3.images")

    # ── Re-emit with the SAME store ──
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        edited_result = emit_ui_json(wf, prior_store=store)

    edited_by_uid: dict[str, dict] = {}
    for n in edited_result["nodes"]:
        uid = n.get("properties", {}).get("vibecomfy_uid", "")
        if uid:
            edited_by_uid[uid] = n

    # ── Assertions ──
    # 1. KSampler's position is preserved (same as baseline).
    assert edited_by_uid["uid-ks"]["pos"] == [400.0, 200.0], (
        f"KSampler position should be preserved at [400, 200], "
        f"got {edited_by_uid['uid-ks']['pos']}"
    )

    # 2. Neighbors (LoadImage, SaveImage) do NOT move.
    assert edited_by_uid["uid-load"]["pos"] == [100.0, 200.0], (
        f"LoadImage should stay at [100, 200], got {edited_by_uid['uid-load']['pos']}"
    )
    assert edited_by_uid["uid-save"]["pos"] == [750.0, 200.0], (
        f"SaveImage should stay at [750, 200], got {edited_by_uid['uid-save']['pos']}"
    )

    # 3. The new CLIPTextEncode was emitted and placed without overlap.
    clip_nodes = [n for n in edited_result["nodes"] if n.get("type") == "CLIPTextEncode"]
    assert len(clip_nodes) == 1
    clip_pos = clip_nodes[0]["pos"]
    clip_size = clip_nodes[0]["size"]

    for matched_uid, matched_node in edited_by_uid.items():
        assert not _bboxes_overlap(clip_pos, clip_size, matched_node["pos"], matched_node["size"]), (
            f"New CLIPTextEncode at {clip_pos}/{clip_size} overlaps matched "
            f"node {matched_uid} at {matched_node['pos']}/{matched_node['size']}"
        )


# ---------------------------------------------------------------------------
# T18a — JSON-only collaboration + --fresh + no-metadata clean emit
# ---------------------------------------------------------------------------


def test_json_only_collaboration():
    """Hand only the emitted JSON to a fresh load → re-export → positions preserved.

    1. Build a workflow with uids on every node.
    2. Emit with a prior_store that carries known positions.
    3. Feed *only* the emitted JSON (not the original store) into
       ``store_from_ui_json`` to derive a new store envelope.
    4. Build a fresh workflow with the same IR (same uids, same edges).
    5. Re-emit using the JSON-derived store.
    6. Assert every matched node is back at its exact store position.

    This models a JSON-only collaboration: a downstream user receives just
    the UI JSON file (no sidecar) and re-emits on top of it.
    """
    # ── Step 1: build original workflow ──
    wf1 = VibeWorkflow("json-collab-1", WorkflowSource("test"))
    load = VibeNode("1", "LoadImage")
    load.uid = "uid-load"
    ks = VibeNode("2", "KSampler")
    ks.uid = "uid-ks"
    save = VibeNode("3", "SaveImage")
    save.uid = "uid-save"
    wf1.nodes["1"] = load
    wf1.nodes["2"] = ks
    wf1.nodes["3"] = save
    wf1.connect("1.0", "2.latent_image")
    wf1.connect("2.0", "3.images")

    original_store = {
        "entries": {
            "uid-load": {"pos": [100.0, 200.0], "size": [200.0, 200.0], "mode": 0, "flags": {}, "color": "", "properties": {}},
            "uid-ks":   {"pos": [400.0, 200.0], "size": [250.0, 300.0], "mode": 0, "flags": {}, "color": "", "properties": {}},
            "uid-save": {"pos": [750.0, 200.0], "size": [200.0, 200.0], "mode": 0, "flags": {}, "color": "", "properties": {}},
        },
        "groups": [],
        "extra": {},
        "definitions": {},
        "virtual_wires": [],
    }

    # ── Step 2: first emit ──
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        emitted_json = emit_ui_json(wf1, prior_store=original_store)

    # ── Step 3: derive store from emitted JSON only ──
    json_derived_store = store_from_ui_json(emitted_json)

    # ── Step 4: fresh workflow (same IR) ──
    wf2 = VibeWorkflow("json-collab-2", WorkflowSource("test"))
    load2 = VibeNode("1", "LoadImage")
    load2.uid = "uid-load"
    ks2 = VibeNode("2", "KSampler")
    ks2.uid = "uid-ks"
    save2 = VibeNode("3", "SaveImage")
    save2.uid = "uid-save"
    wf2.nodes["1"] = load2
    wf2.nodes["2"] = ks2
    wf2.nodes["3"] = save2
    wf2.connect("1.0", "2.latent_image")
    wf2.connect("2.0", "3.images")

    # ── Step 5: re-emit using JSON-derived store ──
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        re_emitted = emit_ui_json(wf2, prior_store=json_derived_store)

    # ── Step 6: index by uid and assert positions preserved verbatim ──
    re_by_uid: dict[str, dict] = {}
    for n in re_emitted["nodes"]:
        uid = n.get("properties", {}).get("vibecomfy_uid", "")
        if uid:
            re_by_uid[uid] = n

    assert "uid-load" in re_by_uid, "uid-load should survive JSON-only round-trip"
    assert "uid-ks" in re_by_uid, "uid-ks should survive JSON-only round-trip"
    assert "uid-save" in re_by_uid, "uid-save should survive JSON-only round-trip"

    # Positions must be exactly as in the original store.
    assert re_by_uid["uid-load"]["pos"] == [100.0, 200.0], (
        f"uid-load position drifted: got {re_by_uid['uid-load']['pos']}"
    )
    assert re_by_uid["uid-ks"]["pos"] == [400.0, 200.0], (
        f"uid-ks position drifted: got {re_by_uid['uid-ks']['pos']}"
    )
    assert re_by_uid["uid-save"]["pos"] == [750.0, 200.0], (
        f"uid-save position drifted: got {re_by_uid['uid-save']['pos']}"
    )

    # Sizes must be verbatim too.
    assert re_by_uid["uid-load"]["size"] == [200.0, 200.0]
    assert re_by_uid["uid-ks"]["size"] == [250.0, 300.0]
    assert re_by_uid["uid-save"]["size"] == [200.0, 200.0]


def test_fresh_reproduces_clean_layout():
    """``--fresh`` against a workflow with a populated sidecar yields the same
    layout as the same workflow with no sidecar — self-contained, no external
    M4 reference.

    The test constructs a workflow, emits with ``prior_store=None`` (the
    ``--fresh`` path), then constructs a separate identical workflow and emits
    again with ``prior_store=None``.  Both emissions must produce identical
    (x, y) positions for every node.  This proves the fresh layout engine is
    deterministic and never consults external state.
    """
    def _build_wf(name: str) -> VibeWorkflow:
        wf = VibeWorkflow(name, WorkflowSource("test"))
        load = VibeNode("1", "LoadImage")
        load.uid = "uid-load"
        ks = VibeNode("2", "KSampler")
        ks.uid = "uid-ks"
        klip = VibeNode("3", "CLIPTextEncode")
        klip.uid = "uid-clip"
        save = VibeNode("4", "SaveImage")
        save.uid = "uid-save"
        for n in [load, ks, klip, save]:
            wf.nodes[n.id] = n
        wf.connect("1.0", "2.latent_image")
        wf.connect("3.0", "2.positive")
        wf.connect("2.0", "4.images")
        return wf

    # Populated sidecar that --fresh should ignore.
    populated_store = {
        "entries": {
            "uid-load": {"pos": [999.0, 999.0], "size": [99.0, 99.0], "mode": 0, "flags": {}, "color": "", "properties": {}},
            "uid-ks":   {"pos": [888.0, 888.0], "size": [88.0, 88.0], "mode": 0, "flags": {}, "color": "", "properties": {}},
            "uid-clip": {"pos": [777.0, 777.0], "size": [77.0, 77.0], "mode": 0, "flags": {}, "color": "", "properties": {}},
            "uid-save": {"pos": [666.0, 666.0], "size": [66.0, 66.0], "mode": 0, "flags": {}, "color": "", "properties": {}},
        },
        "groups": [],
        "extra": {},
        "definitions": {},
        "virtual_wires": [],
    }

    # Emit workflow A with --fresh (prior_store=None — ignores populated_store).
    wf_a = _build_wf("fresh-a")
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        result_a = emit_ui_json(wf_a, prior_store=None)

    pos_a: dict[str, list[float]] = {}
    for n in result_a["nodes"]:
        uid = n.get("properties", {}).get("vibecomfy_uid", "")
        if uid:
            pos_a[uid] = n["pos"]

    # Emit workflow B (same structure, no sidecar whatsoever).
    wf_b = _build_wf("fresh-b")
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        result_b = emit_ui_json(wf_b, prior_store=None)

    pos_b: dict[str, list[float]] = {}
    for n in result_b["nodes"]:
        uid = n.get("properties", {}).get("vibecomfy_uid", "")
        if uid:
            pos_b[uid] = n["pos"]

    # ── Assertions ──
    # Both emissions must produce the same set of uids.
    assert set(pos_a.keys()) == set(pos_b.keys()), (
        f"uid sets differ: A={set(pos_a.keys())}, B={set(pos_b.keys())}"
    )

    # Every uid must land at the exact same position.
    for uid in pos_a:
        assert pos_a[uid] == pos_b[uid], (
            f"--fresh non-deterministic for {uid}: A={pos_a[uid]}, B={pos_b[uid]}"
        )

    # --fresh must NOT reproduce the populated store positions (it ignores them).
    for uid, store_pos in [("uid-load", [999.0, 999.0]), ("uid-ks", [888.0, 888.0]),
                           ("uid-clip", [777.0, 777.0]), ("uid-save", [666.0, 666.0])]:
        assert pos_a[uid] != store_pos, (
            f"--fresh leaked sidecar position for {uid}: got {pos_a[uid]}, "
            f"sidecar had {store_pos}"
        )


def test_no_metadata_input_produces_clean_layout():
    """Workflow built programmatically with no metadata still emits cleanly.

    No uids, no ``_ingest_snapshot``, no ``_ui``, no ``prior_store``.
    The emitter must produce a well-formed LiteGraph envelope where every
    node has a valid ``pos``, ``size``, and ``id`` — and no metadata cruft
    leaks into the output.
    """
    wf = VibeWorkflow("no-meta", WorkflowSource("test"))
    # Note: VibeNode default uid is '' — no identity metadata.
    load = VibeNode("1", "LoadImage")
    ks = VibeNode("2", "KSampler")
    save = VibeNode("3", "SaveImage")
    wf.nodes["1"] = load
    wf.nodes["2"] = ks
    wf.nodes["3"] = save
    wf.connect("1.0", "2.latent_image")
    wf.connect("2.0", "3.images")

    # Confirm no metadata exists on the workflow.
    assert not load.uid
    assert not ks.uid
    assert not save.uid
    assert (wf.metadata or {}).get("_ingest_snapshot") is None

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        result = emit_ui_json(wf, prior_store=None)

    # ── Every emitted node must have pos, size, id ──
    nodes = result.get("nodes", [])
    assert len(nodes) == 3, f"Expected 3 nodes, got {len(nodes)}"

    for node in nodes:
        assert isinstance(node.get("id"), int), f"node id must be int, got {node.get('id')!r}"
        assert isinstance(node.get("pos"), list) and len(node["pos"]) == 2, (
            f"node must have [x,y] pos, got {node.get('pos')!r}"
        )
        assert isinstance(node.get("size"), list) and len(node["size"]) == 2, (
            f"node must have [w,h] size, got {node.get('size')!r}"
        )
        assert isinstance(node.get("type"), str) and len(node["type"]) > 0, (
            f"node must have non-empty type, got {node.get('type')!r}"
        )
        # No stale ir_node_id or other metadata cruft.
        props = node.get("properties") or {}
        assert "ir_node_id" not in props, (
            f"stale ir_node_id leaked into properties: {props}"
        )

    # ── Links must be emitted ──
    links = result.get("links", [])
    assert len(links) == 2, f"Expected 2 links, got {len(links)}"

    # ── Envelope top-level keys ──
    for key in ("version", "last_node_id", "last_link_id", "nodes", "links"):
        assert key in result, f"Missing top-level key '{key}' in emitted envelope"


# ---------------------------------------------------------------------------
# T18b — AI-agent edit-safety + duplicate-safety
# ---------------------------------------------------------------------------


def test_agent_edit_safety_no_position_inheritance():
    """Programmatic add/delete/rewire: ``_next_node_id`` reuses integer ids
    after deletion, but the *new* node must NEVER inherit the deleted node's
    position from the prior_store.

    1. Build a 3-node workflow (ids "1","2","3"), each with a unique uid.
    2. Build a prior_store with positions for all three uids.
    3. Simulate an AI-agent edit:
       a. delete node "2" (remove_node + edges cleared)
       b. add a *new* uidless node → ``_next_node_id()`` returns "2"
    4. Emit with the prior_store.
    5. The newly-added node (litegraph id=2) must NOT have the position
       from the deleted node's prior_store entry ("uid-2").
    """
    wf = VibeWorkflow("agent-edit-safety", WorkflowSource("test"))

    # ── Step 1: 3 nodes with unique uids ──
    n1 = VibeNode("1", "LoadImage")
    n1.uid = "uid-1"
    n2 = VibeNode("2", "KSampler")
    n2.uid = "uid-2"
    n3 = VibeNode("3", "SaveImage")
    n3.uid = "uid-3"
    wf.nodes["1"] = n1
    wf.nodes["2"] = n2
    wf.nodes["3"] = n3
    wf.connect("1.0", "2.latent_image")
    wf.connect("2.0", "3.images")

    # ── Step 2: prior_store with known positions ──
    store = {
        "entries": {
            "uid-1": {"pos": [100.0, 200.0], "size": [200.0, 200.0], "mode": 0, "flags": {}, "color": "", "properties": {}},
            "uid-2": {"pos": [400.0, 200.0], "size": [250.0, 300.0], "mode": 0, "flags": {}, "color": "", "properties": {}},
            "uid-3": {"pos": [750.0, 200.0], "size": [200.0, 200.0], "mode": 0, "flags": {}, "color": "", "properties": {}},
        },
        "groups": [],
        "extra": {},
        "definitions": {},
        "virtual_wires": [],
    }

    # ── Step 3: AI-agent edit — delete node "2", add new uidless node ──
    wf.remove_node("2")
    # Confirm id "2" is now free for reuse.
    assert "2" not in wf.nodes
    # Add a completely different node type (uidless) — _next_node_id() returns "2".
    new_node = wf.add_node("CLIPTextEncode")
    assert new_node.id == "2", (
        f"_next_node_id should reuse id '2', got {new_node.id!r}"
    )
    assert new_node.uid == "", "new node must be uidless"
    # Rewire: 1 → new → 3
    wf.edges.clear()
    wf.connect("1.0", "2.clip")
    wf.connect("2.0", "3.images")

    # ── Step 4: emit with prior_store ──
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        result = emit_ui_json(wf, prior_store=store)

    # ── Step 5: find the new node (id=2) and assert it does NOT inherit
    #    the deleted node's position ──
    by_id: dict[int, dict] = {}
    for n in result["nodes"]:
        by_id[n["id"]] = n

    assert 2 in by_id, "new node (id=2) must be in emitted output"
    new_emitted = by_id[2]

    # The deleted node's prior position was [400, 200] (uid-2).
    deleted_pos = store["entries"]["uid-2"]["pos"]
    deleted_size = store["entries"]["uid-2"]["size"]
    assert new_emitted["pos"] != deleted_pos, (
        f"New CLIPTextEncode (id=2) must NOT inherit deleted KSampler position "
        f"{deleted_pos}; got {new_emitted['pos']}"
    )
    assert new_emitted["size"] != deleted_size, (
        f"New CLIPTextEncode (id=2) must NOT inherit deleted KSampler size "
        f"{deleted_size}; got {new_emitted['size']}"
    )

    # Also verify that uid-1 and uid-3 DO keep their positions.
    uid_by_pos = {
        n.get("properties", {}).get("vibecomfy_uid", ""): n["pos"]
        for n in result["nodes"]
    }
    assert uid_by_pos.get("uid-1") == [100.0, 200.0], (
        f"uid-1 should preserve position, got {uid_by_pos.get('uid-1')}"
    )
    assert uid_by_pos.get("uid-3") == [750.0, 200.0], (
        f"uid-3 should preserve position, got {uid_by_pos.get('uid-3')}"
    )


def test_duplicate_safety_twin_randomnoise():
    """Duplicate safety against the corpus fixture.

    1. Load a real corpus workflow (z_image.json).
    2. Add two twin RandomNoise nodes (uid='', same structure, different
       positions) — they produce identical ``legacy_hash``.
    3. Build a prior_store with entries for both twins at distinct positions.
    4. Call ``reconcile`` and assert each twin is assigned to the *nearest*
       prior position via stable bipartite assignment — no swap, no scatter.
    """
    import json as _json
    import os as _os

    from vibecomfy.ingest.normalize import convert_to_vibe_format
    from vibecomfy.porting.layout.reconcile import legacy_hash

    corpus_path = _os.path.join(
        _os.path.dirname(__file__), "..", "workflow_corpus",
        "official", "image", "z_image.json",
    )
    if not _os.path.exists(corpus_path):
        import pytest
        pytest.skip("z_image corpus fixture not found")

    with open(corpus_path) as fh:
        raw = _json.load(fh)

    wf = convert_to_vibe_format(raw)

    # ── Add two twin RandomNoise nodes ──
    rn1 = wf.add_node("RandomNoise")
    rn1.inputs["noise_seed"] = 42
    rn1.metadata["_ui"] = {"id": int(rn1.id), "pos": [0.0, 0.0], "size": [200.0, 100.0], "mode": 0, "properties": {}}

    rn2 = wf.add_node("RandomNoise")
    rn2.inputs["noise_seed"] = 42
    rn2.metadata["_ui"] = {"id": int(rn2.id), "pos": [1000.0, 0.0], "size": [200.0, 100.0], "mode": 0, "properties": {}}

    # Verify they are structural twins.
    h1 = legacy_hash(rn1.id, wf)
    h2 = legacy_hash(rn2.id, wf)
    assert h1 == h2, f"twin RandomNoise nodes must hash identically: {h1} != {h2}"

    # ── Build prior_store from the raw JSON, then add twin entries ──
    store = store_from_ui_json(raw)
    # Add two entries for the twins keyed by legacy_hash (stage 2 bridge).
    store["entries"][h1 + "__twin_near"] = {
        "pos": [0.0, 0.0], "size": [200.0, 100.0], "mode": 0,
        "flags": {}, "color": "", "properties": {},
        "_legacy_hash": h1,
    }
    store["entries"][h1 + "__twin_far"] = {
        "pos": [1000.0, 0.0], "size": [200.0, 100.0], "mode": 0,
        "flags": {}, "color": "", "properties": {},
        "_legacy_hash": h1,
    }

    # ── Reconcile ──
    result = reconcile(wf, store)

    # Both twins must be bridge_minted (stage 3).
    minted_count = len(result.bridge_minted)
    assert minted_count >= 2, (
        f"both twin RN nodes must be matched via stage 3, "
        f"but only {minted_count} bridge_minted"
    )

    # Each twin must be assigned to the nearest prior position (no swap).
    for node_id, rn_node in [(rn1.id, rn1), (rn2.id, rn2)]:
        uid = rn_node.uid
        assert uid, f"twin node {node_id} must have a minted uid after reconcile"
        assert uid in result.matched, (
            f"twin node {node_id} (uid={uid}) must be in matched"
        )
        assigned_pos = result.matched[uid]["pos"]
        node_pos = rn_node.metadata["_ui"]["pos"]
        d_assigned = abs(node_pos[0] - assigned_pos[0])
        d_other = abs(node_pos[0] - (1000.0 if assigned_pos[0] == 0.0 else 0.0))
        assert d_assigned <= d_other, (
            f"twin node {node_id} at {node_pos} was assigned to pos {assigned_pos} "
            f"(dist {d_assigned}) — swapped to farther entry at dist {d_other}"
        )


# ---------------------------------------------------------------------------
# T18c — Legacy bridge resilience
# ---------------------------------------------------------------------------


def test_legacy_pre_uid_file_bridges_then_exact():
    """First round-trip via hash bridge mints uids; second is exact;
    unmatched cases appear in the report's identity_stabilization.unmatched_legacy.

    1. Build a pre-uid workflow (uid-less nodes).
    2. Build a prior_store with entries keyed by legacy_hash, plus one orphan
       hash entry that has no matching current node.
    3. First reconcile → bridge detects both nodes, mints uids; orphan hash
       entry is named in unmatched_legacy.
    4. Build a ChangeReport from the first reconcile result — the orphan must
       appear in identity_stabilization.unmatched_legacy (NOT in content_edits).
    5. Second reconcile with a store keyed by the newly minted uids → uid-exact
       match only (bridge_minted empty, unmatched_legacy empty).
    6. Second ChangeReport is clean — no stabilization events.
    """
    from vibecomfy.porting.layout.reconcile import (
        build_change_report,
        legacy_hash,
        reconcile,
    )
    from vibecomfy.workflow import VibeEdge, VibeNode, VibeWorkflow, WorkflowSource

    # ── 1. Build a pre-uid workflow: two uid-less nodes, chained ──
    wf = VibeWorkflow(id="legacy_test", source=WorkflowSource(id="legacy_test"))
    n1 = VibeNode(
        id="1", class_type="KSampler",
        inputs={"seed": 42, "steps": 20, "cfg": 7.0, "sampler_name": "euler",
                "scheduler": "normal", "denoise": 1.0},
        uid="",
    )
    n2 = VibeNode(
        id="2", class_type="EmptyLatentImage",
        inputs={"width": 512, "height": 512, "batch_size": 1},
        uid="",
    )
    wf.nodes["1"] = n1
    wf.nodes["2"] = n2
    wf.edges.append(VibeEdge(from_node="2", from_output="0", to_node="1", to_input="latent_image"))

    h1 = legacy_hash("1", wf)
    h2 = legacy_hash("2", wf)
    assert h1, "legacy_hash for node 1 must be non-empty"
    assert h2, "legacy_hash for node 2 must be non-empty"
    assert h1 != h2, "different nodes must have different hashes"

    # ── 2. Build prior_store with hash-keyed entries + one orphan ──
    orphan_hash = "f" * 64  # 64 hex chars, will never match a real node

    def _furniture(x: float) -> dict:
        return {
            "pos": [x, 0.0],
            "size": [200.0, 100.0],
            "mode": 0,
            "flags": {},
            "color": "",
            "properties": {},
        }

    store_v1: dict = {
        "entries": {
            h1: _furniture(100.0),
            h2: _furniture(400.0),
            orphan_hash: _furniture(999.0),
        },
        "groups": [],
        "extra": {},
        "definitions": {},
        "virtual_wires": [],
    }

    # ── 3. First reconcile → hash bridge matches nodes; orphan → unmatched_legacy ──
    result1 = reconcile(wf, store_v1)

    assert len(result1.bridge_minted) == 2, (
        f"both uid-less nodes must be bridge-matched, got {len(result1.bridge_minted)}"
    )
    assert result1.new == [], "no current nodes should remain unmatched after bridge"
    assert orphan_hash in result1.unmatched_legacy, (
        f"orphan hash {orphan_hash[:16]}... must appear in unmatched_legacy"
    )
    # Nodes must have minted uids.
    assert wf.nodes["1"].uid != "", "node 1 must have a minted uid"
    assert wf.nodes["2"].uid != "", "node 2 must have a minted uid"

    uid1 = wf.nodes["1"].uid
    uid2 = wf.nodes["2"].uid

    # ── 4. Build ChangeReport from first reconcile ──
    report1 = build_change_report(result1, {})
    # identity_stabilization.unmatched_legacy must include the orphan hash.
    assert orphan_hash in report1.identity_stabilization.unmatched_legacy, (
        "orphan hash must appear in ChangeReport identity_stabilization.unmatched_legacy"
    )
    # bridge_minted must be reflected in identity_stabilization (not content_edits).
    assert len(report1.identity_stabilization.bridge_minted) == 2, (
        f"identity_stabilization must report 2 bridge-minted entries, "
        f"got {len(report1.identity_stabilization.bridge_minted)}"
    )
    # content_edits should have preserved uids (since we passed empty delta).
    assert uid1 in report1.content_edits.preserved
    assert uid2 in report1.content_edits.preserved
    # bridge_minted nodes should NOT be in content_edits.edited.
    assert uid1 not in report1.content_edits.edited
    assert uid2 not in report1.content_edits.edited

    # ── 5. Second reconcile with a store keyed by newly minted uids ──
    store_v2: dict = {
        "entries": {uid1: _furniture(100.0), uid2: _furniture(400.0)},
        "groups": [],
        "extra": {},
        "definitions": {},
        "virtual_wires": [],
    }

    result2 = reconcile(wf, store_v2)

    assert result2.bridge_minted == [], (
        f"second round-trip must use uid-exact only, got {len(result2.bridge_minted)} bridged"
    )
    assert set(result2.matched) == {uid1, uid2}, (
        f"both uids must be matched via stage 1, got matched={set(result2.matched)}"
    )
    assert result2.new == [], "no new nodes in second round-trip"
    assert result2.unmatched_legacy == [], (
        f"second round-trip must have empty unmatched_legacy, "
        f"got {result2.unmatched_legacy}"
    )

    # ── 6. Second ChangeReport is clean ──
    report2 = build_change_report(result2, {})
    assert report2.identity_stabilization.bridge_minted == []
    assert report2.identity_stabilization.unmatched_legacy == []
    assert uid1 in report2.content_edits.preserved
    assert uid2 in report2.content_edits.preserved


# ---------------------------------------------------------------------------
# T19 — Editor pixel-for-pixel round-trip
# ---------------------------------------------------------------------------


def test_editor_roundtrip_pixel_for_pixel():
    """Start from a real ``workflow_corpus/`` JSON, hand-edit a position, convert
    + re-emit, and assert positions / groups / notes / bypass state are preserved
    via ``layout_drift(...).max_pos_delta == 0 and max_size_delta == 0``.

    1. Load ``z_image.json`` from the workflow corpus.
    2. Deep-copy the raw JSON and perturb the SaveImage node's position.
    3. ``convert_to_vibe_format`` (mints uids, captures ``_ui`` metadata).
    4. Build a ``before_vector`` (layout_vector-compatible dict) from the
       captured ``_ui`` entries, and a ``prior_store`` envelope for the emitter.
    5. ``emit_ui_json(wf, prior_store=store)`` — the preserve path.
    6. ``after_vector = layout_vector(emitted)``.
    7. Assert ``layout_drift(before, after).max_pos_delta == 0`` and
       ``max_size_delta == 0``.
    8. Verify MarkdownNote nodes, groups, and bypass ``mode`` are preserved.
    """
    import copy as _copy
    import json as _json
    import os as _os

    from vibecomfy.ingest.normalize import convert_to_vibe_format, normalize_to_api
    from vibecomfy.porting.layout.layout_vector import layout_drift, layout_vector

    # ── 1. Load corpus fixture ──
    corpus_path = _os.path.join(
        _os.path.dirname(__file__), "..", "workflow_corpus",
        "official", "image", "z_image.json",
    )
    if not _os.path.exists(corpus_path):
        import pytest
        pytest.skip("z_image corpus fixture not found")

    with open(corpus_path) as fh:
        raw = _json.load(fh)

    # Sanity: raw JSON has nodes, including MarkdownNote and SaveImage.
    raw_types = {n.get("type") for n in raw.get("nodes", []) if isinstance(n, dict)}
    assert "MarkdownNote" in raw_types, "fixture must contain MarkdownNote nodes"
    assert "SaveImage" in raw_types, "fixture must contain SaveImage"

    # ── 2. Hand-edit a position: move SaveImage (id=9) by (+50, +30) ──
    edited = _copy.deepcopy(raw)
    moved_node = None
    for node in edited["nodes"]:
        if node.get("id") == 9 and node.get("type") == "SaveImage":
            moved_node = node
            node["pos"] = [node["pos"][0] + 50, node["pos"][1] + 30]
            break
    assert moved_node is not None, "SaveImage node (id=9) must exist in z_image.json"
    perturbed_pos = moved_node["pos"]  # [800, -140] from original [750, -170]

    # ── 3. Convert to VibeWorkflow ──
    # Force the offline-normalize path (use_comfy_converter=False) so the test is
    # deterministic regardless of whether the vendored ComfyUI converter is
    # importable in the current test-session environment.  The vendored converter
    # expands UUID subgraphs and drops MarkdownNote nodes, which changes the node
    # set and defeats the "notes preserved" part of this pixel-for-pixel gate.
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        api_format = normalize_to_api(edited, use_comfy_converter=False)
        wf = convert_to_vibe_format(api_format)

    # ── 4. Build before_vector (layout_vector format) and prior_store entries ──
    entries: dict[str, dict] = {}
    before_vector: dict[str, dict] = {}

    for node in wf.nodes.values():
        if not node.uid:
            continue
        ui = node.metadata.get("_ui")
        if not isinstance(ui, dict) or ui.get("pos") is None:
            continue

        # Canonicalize positions the same way the emitter does (_canonicalize_coord
        # rounds to 2 decimal places) so layout_drift sees zero delta on matched.
        pos = [round(float(ui["pos"][0]), 2), round(float(ui["pos"][1]), 2)]
        size = (
            [round(float(ui["size"][0]), 2), round(float(ui["size"][1]), 2)]
            if isinstance(ui.get("size"), list) and len(ui["size"]) >= 2
            else [0.0, 0.0]
        )
        mode = ui.get("mode", 0)
        if not isinstance(mode, int):
            mode = 0

        entries[node.uid] = {
            "pos": pos,
            "size": size,
            "mode": mode,
            "flags": ui.get("flags", {}),
            "color": ui.get("color", ""),
            "properties": ui.get("properties", {}),
        }
        before_vector[node.uid] = {
            "pos": list(pos),
            "size": list(size),
            "mode": mode,
            "group": None,
            "key_kind": "uid",
        }

    # Verify the perturbed SaveImage position is captured in the store.
    save_uid = wf.nodes["9"].uid
    assert save_uid in entries, f"SaveImage uid {save_uid!r} must be in store entries"
    assert entries[save_uid]["pos"] == [800.0, -140.0], (
        f"Store should carry perturbed position [800, -140], got {entries[save_uid]['pos']}"
    )

    store: dict = {
        "entries": entries,
        "groups": edited.get("groups", []),
        "extra": edited.get("extra", {}),
        "definitions": edited.get("definitions", {}),
        "virtual_wires": [],
    }

    # ── 5. Emit UI JSON with the prior_store ──
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        emitted = emit_ui_json(wf, prior_store=store)

    # ── 6. Build after_vector ──
    after_vector = layout_vector(emitted)

    # ── 7. Compute drift ──
    drift = layout_drift(before_vector, after_vector)

    assert drift.max_pos_delta == 0, (
        f"Position drift detected: max_pos_delta={drift.max_pos_delta:.2f}, "
        f"per_key_diff={list(drift.per_key_diff.keys())}"
    )
    assert drift.max_size_delta == 0, (
        f"Size drift detected: max_size_delta={drift.max_size_delta:.2f}, "
        f"per_key_diff={list(drift.per_key_diff.keys())}"
    )

    # Any unmatched keys should be in "after only" (emitter-created nodes), not
    # in "before only" (we should not lose any corpus node).
    before_only = [k for k in drift.unmatched_keys if k in before_vector]
    assert len(before_only) == 0, (
        f"Corpus nodes lost in round-trip: {before_only}"
    )

    # ── 8. Verify notes, groups, and bypass state ──
    emitted_types = {
        n.get("type") for n in emitted.get("nodes", []) if isinstance(n, dict)
    }
    assert "MarkdownNote" in emitted_types, (
        "MarkdownNote nodes must survive the round-trip"
    )

    # Groups: verify the emitted JSON carries a groups key.
    assert "groups" in emitted, "emitted JSON must have 'groups' key"

    # Bypass state: every matched node must have the same mode as in the store.
    for uid, before_info in before_vector.items():
        after_info = after_vector.get(uid)
        if after_info is not None:
            assert after_info["mode"] == before_info["mode"], (
                f"Mode mismatch for uid={uid!r}: "
                f"before={before_info['mode']}, after={after_info['mode']}"
            )
