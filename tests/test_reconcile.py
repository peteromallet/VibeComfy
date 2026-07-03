"""Tests for vibecomfy.porting.layout.reconcile.reconcile.

Covers: widget-edit (matched), rewire (matched), node-deletion (removed),
no-store-entry (new), virtual-wire degradation, verbatim furniture carry,
the stage-2 legacy-hash bridge (T6: pre-uid round-trips, second-round-trip
exact, unmatched hash entries in unmatched_legacy), the stage-3 bipartite
assignment for twin/cloned nodes (T7: no-swap guarantee), and stage-4
subgraph inner-node preserve + content-hash miss fallback (T8).
"""
from __future__ import annotations

import json
import os

from vibecomfy.ingest.normalize import convert_to_vibe_format
from vibecomfy.porting.layout.reconcile import (
    ReconcileResult,
    _subgraph_content_hash,
    build_change_report,
    inner_node_uid,
    legacy_hash,
    reconcile,
)
from vibecomfy.workflow import VibeEdge, VibeNode, VibeWorkflow, WorkflowSource

_CORPUS_ROOT = os.path.join(os.path.dirname(__file__), "..", "ready_templates/sources")


# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------

def _two_node_api() -> dict:
    """Minimal two-node API: KSampler (uid=sampler-uid) + EmptyLatentImage (uid=latent-uid)."""
    return {
        "1": {
            "class_type": "KSampler",
            "inputs": {
                "seed": 42,
                "steps": 20,
                "cfg": 7.0,
                "sampler_name": "euler",
                "scheduler": "normal",
                "denoise": 1.0,
                "latent_image": [2, 0],
            },
            "_ui": {
                "id": 1,
                "pos": [100, 200],
                "size": [300, 200],
                "mode": 0,
                "properties": {"vibecomfy_uid": "sampler-uid"},
            },
        },
        "2": {
            "class_type": "EmptyLatentImage",
            "inputs": {"width": 512, "height": 512, "batch_size": 1},
            "_ui": {
                "id": 2,
                "pos": [0, 300],
                "size": [200, 100],
                "mode": 0,
                "properties": {"vibecomfy_uid": "latent-uid"},
            },
        },
    }


def _make_store(*uids: str, virtual_wires: list | None = None) -> dict:
    """Build a minimal prior_store envelope with furniture entries for the given uids."""
    entries = {}
    for i, uid in enumerate(uids):
        entries[uid] = {
            "pos": [float(i * 100), 0.0],
            "size": [200.0, 100.0],
            "mode": 0,
            "flags": {},
            "color": "#ffffff",
            "properties": {},
            "group": None,
        }
    return {
        "entries": entries,
        "groups": [],
        "extra": {},
        "definitions": {},
        "virtual_wires": virtual_wires or [],
    }


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_widget_edit_node_still_matched():
    """A node whose widget value was edited after the last save is still uid-matched.

    The uid exists in both the store and the current workflow, so it must appear
    in ReconcileResult.matched regardless of edit status.
    """
    wf = convert_to_vibe_format(_two_node_api())
    store = _make_store("sampler-uid", "latent-uid")

    # Simulate a post-save widget edit: change the seed
    wf.nodes["1"].inputs["seed"] = 999

    result = reconcile(wf, store)

    assert "sampler-uid" in result.matched, "widget-edited node must appear in matched"
    assert "latent-uid" in result.matched
    assert result.new == []
    assert result.removed == []


def test_widget_edit_furniture_carried_verbatim():
    """The matched entry carries VERBATIM furniture from the store, not the current IR pos."""
    wf = convert_to_vibe_format(_two_node_api())
    store = _make_store("sampler-uid", "latent-uid")

    # Simulate post-save widget edit
    wf.nodes["1"].inputs["seed"] = 999

    result = reconcile(wf, store)

    entry = result.matched["sampler-uid"]
    assert entry["pos"] == store["entries"]["sampler-uid"]["pos"]
    assert entry["size"] == store["entries"]["sampler-uid"]["size"]
    assert entry["mode"] == store["entries"]["sampler-uid"]["mode"]
    assert entry["flags"] == store["entries"]["sampler-uid"]["flags"]
    assert entry["color"] == store["entries"]["sampler-uid"]["color"]
    assert entry["properties"] == store["entries"]["sampler-uid"]["properties"]
    assert entry["group"] == store["entries"]["sampler-uid"]["group"]


def test_rewire_node_still_matched():
    """A node that had its incoming edge changed after the last save is still uid-matched."""
    wf = convert_to_vibe_format(_two_node_api())
    store = _make_store("sampler-uid", "latent-uid")

    # Simulate a post-save rewire: add a new latent node and redirect sampler's input
    new_node = VibeNode(
        id="3",
        class_type="EmptyLatentImage",
        inputs={"width": 768, "height": 768, "batch_size": 1},
        uid="latent-uid-b",
    )
    wf.nodes["3"] = new_node
    wf.edges = [e for e in wf.edges if not (e.to_node == "1" and e.to_input == "latent_image")]
    wf.edges.append(VibeEdge(from_node="3", from_output="0", to_node="1", to_input="latent_image"))

    result = reconcile(wf, store)

    assert "sampler-uid" in result.matched, "rewired node must appear in matched"
    # latent-uid-b is new (not in store)
    assert "latent-uid-b" in result.new


def test_node_deletion_appears_in_removed():
    """A node that was deleted from the IR after the last save appears in removed."""
    wf = convert_to_vibe_format(_two_node_api())
    store = _make_store("sampler-uid", "latent-uid")

    # Simulate post-save node deletion
    del wf.nodes["2"]
    wf.edges = [e for e in wf.edges if e.from_node != "2" and e.to_node != "2"]

    result = reconcile(wf, store)

    assert "latent-uid" in result.removed, "deleted node uid must appear in removed"
    assert "sampler-uid" in result.matched
    assert "latent-uid" not in result.matched


def test_new_node_appears_in_new():
    """A node added to the IR after the last save appears in new."""
    wf = convert_to_vibe_format(_two_node_api())
    # Store only knows about sampler-uid, not latent-uid
    store = _make_store("sampler-uid")

    result = reconcile(wf, store)

    assert "latent-uid" in result.new
    assert "sampler-uid" in result.matched
    assert result.removed == []


def test_empty_store_all_nodes_are_new():
    """Against an empty store every current uid is reported as new."""
    wf = convert_to_vibe_format(_two_node_api())
    store = _make_store()

    result = reconcile(wf, store)

    assert "sampler-uid" in result.new
    assert "latent-uid" in result.new
    assert result.matched == {}
    assert result.removed == []


def test_fully_matched_store():
    """When every store uid is present in current_wf, matched covers all and new/removed are empty."""
    wf = convert_to_vibe_format(_two_node_api())
    store = _make_store("sampler-uid", "latent-uid")

    result = reconcile(wf, store)

    assert set(result.matched) == {"sampler-uid", "latent-uid"}
    assert result.new == []
    assert result.removed == []
    assert result.bridge_minted == []


def test_unmatched_legacy_equals_removed_in_stage1():
    """In stage 1 (uid-exact only), unmatched_legacy is identical to removed."""
    wf = convert_to_vibe_format(_two_node_api())
    store = _make_store("sampler-uid", "latent-uid", "ghost-uid")

    result = reconcile(wf, store)

    assert result.removed == result.unmatched_legacy


def test_virtual_wire_degraded_when_endpoint_removed():
    """Virtual wires whose source or target uid is in removed are placed in degraded_virtual_wires."""
    wf = convert_to_vibe_format(_two_node_api())
    vw_good = {"source": "sampler-uid", "target": "latent-uid"}
    vw_bad = {"source": "sampler-uid", "target": "ghost-uid"}
    store = _make_store("sampler-uid", "latent-uid", "ghost-uid",
                        virtual_wires=[vw_good, vw_bad])

    result = reconcile(wf, store)

    assert vw_bad in result.degraded_virtual_wires
    assert vw_good not in result.degraded_virtual_wires


def test_virtual_wire_source_removed_degrades():
    """A virtual wire whose source uid was deleted is also degraded."""
    wf = convert_to_vibe_format(_two_node_api())
    del wf.nodes["2"]
    wf.edges = [e for e in wf.edges if e.from_node != "2" and e.to_node != "2"]

    vw = {"source": "latent-uid", "target": "sampler-uid"}
    store = _make_store("sampler-uid", "latent-uid", virtual_wires=[vw])

    result = reconcile(wf, store)

    assert vw in result.degraded_virtual_wires


def test_reconcile_does_not_mutate_store():
    """reconcile must not modify the prior_store entries dict."""
    wf = convert_to_vibe_format(_two_node_api())
    store = _make_store("sampler-uid", "latent-uid")
    original_pos = list(store["entries"]["sampler-uid"]["pos"])

    result = reconcile(wf, store)
    # Mutate the returned matched entry
    result.matched["sampler-uid"]["pos"] = [9999.0, 9999.0]

    # Prior store must be unchanged
    assert store["entries"]["sampler-uid"]["pos"] == original_pos


def test_result_is_reconcile_result_instance():
    wf = convert_to_vibe_format(_two_node_api())
    store = _make_store("sampler-uid")
    assert isinstance(reconcile(wf, store), ReconcileResult)


# ---------------------------------------------------------------------------
# T6: legacy structural-hash bridge (stage 2)
# ---------------------------------------------------------------------------


def _wf(wf_id: str) -> VibeWorkflow:
    return VibeWorkflow(id=wf_id, source=WorkflowSource(id=wf_id))


def _make_uidless_workflow() -> VibeWorkflow:
    """Two-node workflow where both nodes have uid='' (pre-uid files)."""
    wf = _wf("pre_uid_test")
    n1 = VibeNode(id="1", class_type="KSampler", inputs={"seed": 42, "steps": 20}, uid="")
    n2 = VibeNode(id="2", class_type="EmptyLatentImage", inputs={"width": 512, "height": 512}, uid="")
    wf.nodes["1"] = n1
    wf.nodes["2"] = n2
    wf.edges.append(VibeEdge(from_node="2", from_output="0", to_node="1", to_input="latent_image"))
    return wf


def _furniture(x: float = 0.0) -> dict:
    return {
        "pos": [x, 0.0],
        "size": [200.0, 100.0],
        "mode": 0,
        "flags": {},
        "color": "#ffffff",
        "properties": {},
        "group": None,
    }


def test_pre_uid_bridge_matches_by_hash():
    """Stage 2: uid-less nodes are matched via legacy_hash and uids are minted."""
    wf = _make_uidless_workflow()
    h1 = legacy_hash("1", wf)
    h2 = legacy_hash("2", wf)

    store = {
        "entries": {h1: _furniture(100.0), h2: _furniture(200.0)},
        "groups": [],
        "extra": {},
        "definitions": {},
        "virtual_wires": [],
    }

    result = reconcile(wf, store)

    assert len(result.bridge_minted) == 2, "both uid-less nodes must be bridge-matched"
    assert result.unmatched_legacy == [], "no orphan store entries remain"
    assert result.new == [], "no current nodes left unmatched"
    assert result.removed == [], "removed must also be empty after bridge"
    # Furniture was carried verbatim
    assert len(result.matched) == 2
    # Uids were assigned back to the IR nodes
    assert wf.nodes["1"].uid != "", "node 1 must have a minted uid"
    assert wf.nodes["2"].uid != "", "node 2 must have a minted uid"


def test_second_round_trip_uid_exact():
    """After bridge-minting uids, a second reconcile uses uid-exact (stage 1) only."""
    wf = _make_uidless_workflow()
    h1 = legacy_hash("1", wf)
    h2 = legacy_hash("2", wf)

    store_v1 = {
        "entries": {h1: _furniture(10.0), h2: _furniture(20.0)},
        "groups": [],
        "extra": {},
        "definitions": {},
        "virtual_wires": [],
    }

    # First reconcile: bridge mints uids
    result1 = reconcile(wf, store_v1)
    assert len(result1.bridge_minted) == 2

    uid1 = wf.nodes["1"].uid
    uid2 = wf.nodes["2"].uid

    # Build store v2 keyed by newly minted uids (as would be written after stage 2)
    store_v2 = {
        "entries": {uid1: _furniture(10.0), uid2: _furniture(20.0)},
        "groups": [],
        "extra": {},
        "definitions": {},
        "virtual_wires": [],
    }

    result2 = reconcile(wf, store_v2)

    assert result2.bridge_minted == [], "second round-trip must use uid-exact, not bridge"
    assert set(result2.matched) == {uid1, uid2}
    assert result2.new == []
    assert result2.unmatched_legacy == []


def test_unmatched_hash_entry_named_in_unmatched_legacy():
    """A hash-keyed store entry with no matching current node appears in unmatched_legacy."""
    wf = _make_uidless_workflow()
    h1 = legacy_hash("1", wf)

    # Store has entries for h1 AND for some unknown hash not in wf
    unknown_hash = "0" * 64  # 64-char hex string that won't match any node
    store = {
        "entries": {h1: _furniture(10.0), unknown_hash: _furniture(99.0)},
        "groups": [],
        "extra": {},
        "definitions": {},
        "virtual_wires": [],
    }

    result = reconcile(wf, store)

    assert unknown_hash in result.unmatched_legacy, "orphan hash entry must appear in unmatched_legacy"
    # h1 was matched (bridge), so it's not in unmatched_legacy
    assert h1 not in result.unmatched_legacy


def test_legacy_hash_is_rank_free():
    """Two workflows with the same structure but different ordering produce the same hash."""
    wf_a = _wf("a")
    wf_a.nodes["1"] = VibeNode(id="1", class_type="SaveImage", inputs={"filename_prefix": "out"}, uid="")
    wf_a.nodes["2"] = VibeNode(id="2", class_type="VAEDecode", inputs={}, uid="")
    wf_a.edges.append(VibeEdge("2", "0", "1", "images"))

    wf_b = _wf("b")
    wf_b.nodes["10"] = VibeNode(id="10", class_type="SaveImage", inputs={"filename_prefix": "out"}, uid="")
    wf_b.nodes["20"] = VibeNode(id="20", class_type="VAEDecode", inputs={}, uid="")
    wf_b.edges.append(VibeEdge("20", "0", "10", "images"))

    # Same structure, different integer ids → identical hashes
    h_a_save = legacy_hash("1", wf_a)
    h_b_save = legacy_hash("10", wf_b)
    h_a_vae = legacy_hash("2", wf_a)
    h_b_vae = legacy_hash("20", wf_b)

    assert h_a_save == h_b_save, "same-structure SaveImage nodes must hash identically"
    assert h_a_vae == h_b_vae, "same-structure VAEDecode nodes must hash identically"


def test_legacy_hash_differs_on_widget_change():
    """Changing a widget value produces a different hash."""
    wf1 = _wf("w1")
    wf1.nodes["1"] = VibeNode(id="1", class_type="KSampler", inputs={"seed": 42}, uid="")
    h1 = legacy_hash("1", wf1)

    wf2 = _wf("w2")
    wf2.nodes["1"] = VibeNode(id="1", class_type="KSampler", inputs={"seed": 99}, uid="")
    h2 = legacy_hash("1", wf2)

    assert h1 != h2, "different seed values must produce different hashes"


def test_bridge_mint_does_not_overwrite_uid_bearing_nodes():
    """Stage 2 must not touch nodes that already have a uid."""
    wf = convert_to_vibe_format(_two_node_api())
    store = _make_store("sampler-uid", "latent-uid")

    result = reconcile(wf, store)

    assert result.bridge_minted == [], "uid-bearing workflow must never trigger bridge minting"


# ---------------------------------------------------------------------------
# T7: stage 3 — stable bipartite assignment for twin / cloned nodes
# ---------------------------------------------------------------------------


def _twin_rn_workflow() -> VibeWorkflow:
    """Two structurally identical RandomNoise nodes at different canvas positions.

    Both nodes have uid='' (pre-uid file).  They are twins: same class_type,
    same inputs, no incoming edges → identical legacy_hash.
    """
    wf = _wf("twin_rn")
    n1 = VibeNode(
        id="1",
        class_type="RandomNoise",
        inputs={"noise_seed": 42},
        uid="",
        metadata={"_ui": {"id": 1, "pos": [0.0, 0.0], "size": [200.0, 100.0], "mode": 0, "properties": {}}},
    )
    n2 = VibeNode(
        id="2",
        class_type="RandomNoise",
        inputs={"noise_seed": 42},
        uid="",
        metadata={"_ui": {"id": 2, "pos": [1000.0, 0.0], "size": [200.0, 100.0], "mode": 0, "properties": {}}},
    )
    wf.nodes["1"] = n1
    wf.nodes["2"] = n2
    return wf


def test_twin_randomnoise_no_swap():
    """Stage 3: two twin RandomNoise nodes are each assigned to the nearest prior position.

    Node at [0,0] must be assigned to the prior entry at [0,0]; node at [1000,0]
    must be assigned to the prior entry at [1000,0].  A naive random assignment
    would scatter (swap), costing 2000 units vs 0.
    """
    wf = _twin_rn_workflow()
    shared_hash = legacy_hash("1", wf)
    assert shared_hash == legacy_hash("2", wf), "twin RandomNoise nodes must hash identically"

    # Prior store: two entries annotated with the shared hash, at distinct positions.
    store = {
        "entries": {
            "prior-rn-near": {
                **_furniture(0.0),
                "_legacy_hash": shared_hash,
            },
            "prior-rn-far": {
                **_furniture(1000.0),
                "_legacy_hash": shared_hash,
            },
        },
        "groups": [],
        "extra": {},
        "definitions": {},
        "virtual_wires": [],
    }

    result = reconcile(wf, store)

    assert len(result.bridge_minted) == 2, "both twin nodes must be matched via stage 3"
    assert result.new == [], "no current nodes should remain unmatched"
    assert result.unmatched_legacy == [], "no prior entries should remain unmatched"

    # Recover the assigned node → prior entry mapping via the minted uids.
    uid_for_node: dict[str, str] = {
        wf.nodes["1"].uid: "1",
        wf.nodes["2"].uid: "2",
    }

    # Each assigned uid must have furniture from the nearest prior position.
    for uid, node_id in uid_for_node.items():
        node = wf.nodes[node_id]
        assigned_pos = result.matched[uid]["pos"]
        node_pos = node.metadata["_ui"]["pos"]
        # Distance to assigned prior pos must be ≤ distance to the other prior pos.
        d_assigned = abs(node_pos[0] - assigned_pos[0])
        d_other = abs(node_pos[0] - (1000.0 if assigned_pos[0] == 0.0 else 0.0))
        assert d_assigned <= d_other, (
            f"node {node_id} at {node_pos} was assigned to pos {assigned_pos} "
            f"(dist {d_assigned}) — swapped to farther entry at dist {d_other}"
        )


def _twin_sampler_workflow() -> VibeWorkflow:
    """Two structurally identical KSampler nodes sharing upstream nodes via UIDs.

    Both samplers have uid='', same inputs, and receive from the same
    EmptyLatentImage node (uid-bearing).  Their legacy_hash is therefore
    identical — the 8b36a85a fixture family.
    """
    wf = _wf("cloned_samplers")
    latent = VibeNode(
        id="0",
        class_type="EmptyLatentImage",
        inputs={"width": 512, "height": 512, "batch_size": 1},
        uid="latent-shared",
        metadata={"_ui": {"id": 0, "pos": [0.0, 300.0], "size": [200.0, 100.0], "mode": 0, "properties": {}}},
    )
    s1 = VibeNode(
        id="1",
        class_type="KSampler",
        inputs={"seed": 42, "steps": 20, "cfg": 7.0, "sampler_name": "euler", "scheduler": "normal", "denoise": 1.0},
        uid="",
        metadata={"_ui": {"id": 1, "pos": [0.0, 0.0], "size": [300.0, 200.0], "mode": 0, "properties": {}}},
    )
    s2 = VibeNode(
        id="2",
        class_type="KSampler",
        inputs={"seed": 42, "steps": 20, "cfg": 7.0, "sampler_name": "euler", "scheduler": "normal", "denoise": 1.0},
        uid="",
        metadata={"_ui": {"id": 2, "pos": [1000.0, 0.0], "size": [300.0, 200.0], "mode": 0, "properties": {}}},
    )
    wf.nodes["0"] = latent
    wf.nodes["1"] = s1
    wf.nodes["2"] = s2
    # Both samplers receive the same latent (uid-bearing peer → peer_ref = "latent-shared")
    wf.edges.append(VibeEdge("0", "0", "1", "latent_image"))
    wf.edges.append(VibeEdge("0", "0", "2", "latent_image"))
    return wf


def test_cloned_samplers_8b36a85a_no_swap():
    """Stage 3: two cloned KSamplers (8b36a85a family) are each assigned without swap.

    Both nodes have the same legacy_hash because they share identical structure
    and receive from the same uid-bearing upstream node.  The bipartite assignment
    must place each sampler nearest to its prior position.
    """
    wf = _twin_sampler_workflow()
    shared_hash = legacy_hash("1", wf)
    assert shared_hash == legacy_hash("2", wf), "cloned KSampler nodes must hash identically"

    store = {
        "entries": {
            "prior-s-near": {
                **_furniture(0.0),
                "_legacy_hash": shared_hash,
            },
            "prior-s-far": {
                **_furniture(1000.0),
                "_legacy_hash": shared_hash,
            },
        },
        "groups": [],
        "extra": {},
        "definitions": {},
        "virtual_wires": [],
    }

    result = reconcile(wf, store)

    assert len(result.bridge_minted) == 2, "both cloned sampler nodes must be matched via stage 3"
    assert result.new == ["latent-shared"], "latent node (uid-bearing, not in store) is new"
    assert result.unmatched_legacy == [], "no prior entries should remain unmatched"

    uid_for_node: dict[str, str] = {
        wf.nodes["1"].uid: "1",
        wf.nodes["2"].uid: "2",
    }

    for uid, node_id in uid_for_node.items():
        node = wf.nodes[node_id]
        assigned_pos = result.matched[uid]["pos"]
        node_pos = node.metadata["_ui"]["pos"]
        d_assigned = abs(node_pos[0] - assigned_pos[0])
        d_other = abs(node_pos[0] - (1000.0 if assigned_pos[0] == 0.0 else 0.0))
        assert d_assigned <= d_other, (
            f"cloned sampler {node_id} at {node_pos} was swapped to farther pos {assigned_pos}"
        )


# ---------------------------------------------------------------------------
# T8: Subgraph inner-node preserve + content-hash miss fallback
# ---------------------------------------------------------------------------

_MUSIC_VIDEO_PATH = os.path.join(
    _CORPUS_ROOT,
    "custom_nodes",
    "ltxvideo",
    "runexx",
    "LTX-2.3_Music_Video_Creator_Low_RAM.json",
)

# The 6 UUID subgraph types present in the music-video monster, paired with their
# pre-computed content hashes (stable: derived from inputs schema + ver property).
_MUSIC_VIDEO_SUBGRAPHS = {
    "3bd4eeb9-31fa-461a-8c04-2b24dd0aabaf": "3bc043580e8a3662",
    "5e410bb1-405a-4d3d-808b-8f5f29426943": "2f7a34af7e181e4e",
    "17238add-9973-482f-8fa3-248d4ed29886": "c73298d250e63e81",
    "c4106aee-ad7a-4925-972b-6f5b3d34db6e": "066a135b2c6a16b8",
    "a3fb563d-4711-4225-9210-fbe61b1bd79d": "da3eabcd5ca852d0",
    "4acc9924-c0bd-470a-b000-46c75e61d004": "fa1d683f0bd3389d",
}


def _make_subgraph_node(uuid_type: str, pos=(0.0, 0.0), ver="0.18.1") -> VibeNode:
    """Create a minimal VibeNode that looks like a UUID subgraph container."""
    return VibeNode(
        id=uuid_type[:8],
        class_type=uuid_type,
        inputs={},
        widgets={},
        metadata={
            "_ui": {
                "id": 1,
                "type": uuid_type,
                "pos": list(pos),
                "size": [300, 100],
                "mode": 0,
                "inputs": [],
                "outputs": [],
                "properties": {"cnr_id": "comfy-core", "ver": ver},
                "widgets_values": [],
            }
        },
    )


def _subgraph_wf(uuid_type: str, pos=(0.0, 0.0), ver="0.18.1") -> VibeWorkflow:
    """Workflow with a single UUID subgraph container node."""
    node = _make_subgraph_node(uuid_type, pos=pos, ver=ver)
    node.uid = uuid_type[:8] + "-uid"
    wf = VibeWorkflow(id="test-wf",
        nodes={node.id: node},
        edges=[],
        inputs={},
        outputs=[],
        metadata={},
        source=WorkflowSource(id="test"),
    )
    return wf


def test_subgraph_content_hash_is_stable():
    """Same node structure produces same content hash every time."""
    uuid = "3bd4eeb9-31fa-461a-8c04-2b24dd0aabaf"
    node = _make_subgraph_node(uuid, ver="0.18.1")
    h1 = _subgraph_content_hash(node)
    h2 = _subgraph_content_hash(node)
    assert h1 == h2
    assert len(h1) == 16


def test_subgraph_content_hash_changes_with_ver():
    """Version bump produces different content hash."""
    uuid = "3bd4eeb9-31fa-461a-8c04-2b24dd0aabaf"
    h_old = _subgraph_content_hash(_make_subgraph_node(uuid, ver="0.17.0"))
    h_new = _subgraph_content_hash(_make_subgraph_node(uuid, ver="0.18.1"))
    assert h_old != h_new


def test_inner_node_uid_format():
    """inner_node_uid produces the expected scope-path key."""
    uid = inner_node_uid("abc-uuid", "deadbeef12345678", "inner-42")
    assert uid == "abc-uuid:deadbeef12345678:inner-42"


def test_subgraph_definition_hit_carries_inner_furniture():
    """Stage 4 hit: same content_hash → inner entries land in matched."""
    uuid = "3bd4eeb9-31fa-461a-8c04-2b24dd0aabaf"
    node = _make_subgraph_node(uuid, ver="0.18.1")
    node.uid = "outer-uid"
    h = _subgraph_content_hash(node)

    wf = VibeWorkflow(id="test-wf",
        nodes={node.id: node},
        edges=[],
        inputs={},
        outputs=[],
        metadata={},
        source=WorkflowSource(id="test"),
    )

    prior_store = {
        "entries": {"outer-uid": {"pos": [10, 20], "size": [300, 100], "mode": 0}},
        "definitions": {
            f"{uuid}:{h}": {
                "bounding": [0, 0, 400, 200],
                "inner_entries": {
                    "inner-1": {"pos": [50, 60], "size": [200, 80], "mode": 0},
                    "inner-2": {"pos": [100, 70], "size": [150, 60], "mode": 0},
                },
            }
        },
        "groups": [],
        "virtual_wires": [],
    }

    result = reconcile(wf, prior_store)

    assert result.definition_relayout == [], "no miss when hash matches"
    scoped_1 = inner_node_uid(uuid, h, "inner-1")
    scoped_2 = inner_node_uid(uuid, h, "inner-2")
    assert scoped_1 in result.matched, "inner-1 should be in matched"
    assert scoped_2 in result.matched, "inner-2 should be in matched"
    assert result.matched[scoped_1]["pos"] == [50, 60]
    assert result.matched[scoped_2]["pos"] == [100, 70]


def test_subgraph_definition_miss_reports_definition_relayout():
    """Stage 4 miss: different content_hash → subgraph in definition_relayout."""
    uuid = "5e410bb1-405a-4d3d-808b-8f5f29426943"
    node = _make_subgraph_node(uuid, ver="0.18.1")
    node.uid = "outer-uid-2"

    wf = VibeWorkflow(id="test-wf",
        nodes={node.id: node},
        edges=[],
        inputs={},
        outputs=[],
        metadata={},
        source=WorkflowSource(id="test"),
    )

    # Store has a definition keyed under a different (stale) hash.
    stale_hash = "0000000000000000"
    prior_store = {
        "entries": {"outer-uid-2": {"pos": [0, 0], "size": [200, 80], "mode": 0}},
        "definitions": {
            f"{uuid}:{stale_hash}": {
                "bounding": [10, 20, 300, 200],
                "inner_entries": {
                    "inner-a": {"pos": [15, 25], "size": [100, 50], "mode": 0},
                },
            }
        },
        "virtual_wires": [],
    }

    result = reconcile(wf, prior_store)

    assert uuid in result.definition_relayout, "miss should appear in definition_relayout"
    # Inner entries from stale hash must NOT be in matched.
    stale_scoped = inner_node_uid(uuid, stale_hash, "inner-a")
    assert stale_scoped not in result.matched, "stale inner entries must not be carried"


def test_subgraph_definition_miss_preserves_prior_bounding():
    """Stage 4 miss: prior bounding box is recorded for layout fallback."""
    uuid = "17238add-9973-482f-8fa3-248d4ed29886"
    node = _make_subgraph_node(uuid, ver="0.18.1")
    node.uid = "outer-uid-3"

    wf = VibeWorkflow(id="test-wf",
        nodes={node.id: node},
        edges=[],
        inputs={},
        outputs=[],
        metadata={},
        source=WorkflowSource(id="test"),
    )

    stale_hash = "aaaaaaaaaaaaaaaa"
    prior_bounding = [100.0, 200.0, 500.0, 300.0]
    prior_store = {
        "entries": {},
        "definitions": {
            f"{uuid}:{stale_hash}": {
                "bounding": prior_bounding,
                "inner_entries": {},
            }
        },
        "virtual_wires": [],
    }

    result = reconcile(wf, prior_store)

    assert uuid in result.definition_relayout
    assert uuid in result.definition_prior_bounding, "prior bounding must be recorded for layout fallback"
    assert result.definition_prior_bounding[uuid] == prior_bounding


def test_subgraph_definition_miss_no_prior_bounding_signals_m4_fallback():
    """Stage 4 miss with no prior definition → absent key means M4 fallback."""
    uuid = "c4106aee-ad7a-4925-972b-6f5b3d34db6e"
    node = _make_subgraph_node(uuid, ver="0.18.1")
    node.uid = "outer-uid-4"

    wf = VibeWorkflow(id="test-wf",
        nodes={node.id: node},
        edges=[],
        inputs={},
        outputs=[],
        metadata={},
        source=WorkflowSource(id="test"),
    )

    # definitions is empty — this subgraph was never seen before.
    prior_store = {"entries": {}, "definitions": {}, "virtual_wires": []}

    result = reconcile(wf, prior_store)

    # Not in definition_relayout because no prior definition at all — it's just new.
    assert uuid not in result.definition_prior_bounding
    assert uuid not in result.definition_relayout


def test_non_subgraph_nodes_unaffected_by_stage4():
    """Stage 4 only touches UUID-typed nodes; regular nodes are unaffected."""
    wf = _load_two_node_wf()
    prior_store = {
        "entries": {
            "sampler-uid": {"pos": [100, 200], "size": [300, 200], "mode": 0},
            "latent-uid": {"pos": [400, 200], "size": [200, 100], "mode": 0},
        },
        "definitions": {},
        "virtual_wires": [],
    }
    result = reconcile(wf, prior_store)
    assert result.definition_relayout == []
    assert result.definition_prior_bounding == {}
    assert "sampler-uid" in result.matched
    assert "latent-uid" in result.matched


def _load_two_node_wf() -> VibeWorkflow:
    """Load the canonical two-node fixture (from earlier test helpers)."""
    api = {
        "1": {
            "class_type": "KSampler",
            "inputs": {"seed": 42, "steps": 20, "latent_image": [2, 0]},
            "_ui": {
                "id": 1, "pos": [100, 200], "size": [300, 200], "mode": 0,
                "properties": {"vibecomfy_uid": "sampler-uid"},
            },
        },
        "2": {
            "class_type": "EmptyLatentImage",
            "inputs": {"width": 512, "height": 512, "batch_size": 1},
            "_ui": {
                "id": 2, "pos": [400, 200], "size": [200, 100], "mode": 0,
                "properties": {"vibecomfy_uid": "latent-uid"},
            },
        },
    }
    return convert_to_vibe_format(api)


def test_music_video_monster_subgraph_definitions_hit():
    """Stage 4 hit for all 6 UUID subgraph nodes in the music-video monster corpus file.

    Builds a synthetic store with 10 definitions (6 corpus + 4 extra synthetic
    entries for absent UUIDs) and verifies that all 6 corpus subgraph nodes
    are matched and their inner entries land in ReconcileResult.matched.
    """
    if not os.path.exists(_MUSIC_VIDEO_PATH):
        import pytest
        pytest.skip("music-video monster corpus file not found")

    data = json.load(open(_MUSIC_VIDEO_PATH))
    wf = convert_to_vibe_format(data)

    # Build synthetic definitions store with 10 entries (6 real + 4 synthetic extras).
    definitions: dict = {}
    expected_scoped: dict[str, list] = {}  # uuid → list of scoped inner keys

    for uuid, expected_hash in _MUSIC_VIDEO_SUBGRAPHS.items():
        def_key = f"{uuid}:{expected_hash}"
        inner_entries = {
            f"inner-{uuid[:4]}-1": {"pos": [10.0, 20.0], "size": [200, 80], "mode": 0},
            f"inner-{uuid[:4]}-2": {"pos": [30.0, 40.0], "size": [150, 60], "mode": 0},
        }
        definitions[def_key] = {
            "bounding": [0.0, 0.0, 400.0, 300.0],
            "inner_entries": inner_entries,
        }
        expected_scoped[uuid] = [
            inner_node_uid(uuid, expected_hash, iid) for iid in inner_entries
        ]

    # 4 extra synthetic definitions for UUIDs not in this workflow.
    extra_uuids = [
        "aaaaaaaa-bbbb-cccc-dddd-eeeeeeee0001",
        "aaaaaaaa-bbbb-cccc-dddd-eeeeeeee0002",
        "aaaaaaaa-bbbb-cccc-dddd-eeeeeeee0003",
        "aaaaaaaa-bbbb-cccc-dddd-eeeeeeee0004",
    ]
    for extra_uuid in extra_uuids:
        definitions[f"{extra_uuid}:0000000000000000"] = {
            "bounding": [0.0, 0.0, 100.0, 100.0],
            "inner_entries": {},
        }

    assert len(definitions) == 10, "store should have exactly 10 definition entries"

    prior_store = {
        "entries": {},
        "definitions": definitions,
        "virtual_wires": [],
    }

    result = reconcile(wf, prior_store)

    # All 6 corpus subgraph nodes should be hits.
    assert result.definition_relayout == [], (
        f"expected no misses, got: {result.definition_relayout}"
    )

    for uuid, scoped_keys in expected_scoped.items():
        for sk in scoped_keys:
            assert sk in result.matched, (
                f"inner entry {sk!r} missing from matched for subgraph {uuid}"
            )


def test_music_video_monster_subgraph_definitions_miss():
    """Stage 4 miss: stale hashes in store → all 6 nodes in definition_relayout."""
    if not os.path.exists(_MUSIC_VIDEO_PATH):
        import pytest
        pytest.skip("music-video monster corpus file not found")

    data = json.load(open(_MUSIC_VIDEO_PATH))
    wf = convert_to_vibe_format(data)

    stale_hash = "0000000000000000"
    definitions = {}
    for uuid in _MUSIC_VIDEO_SUBGRAPHS:
        definitions[f"{uuid}:{stale_hash}"] = {
            "bounding": [0.0, 0.0, 300.0, 200.0],
            "inner_entries": {"inner-stale": {"pos": [0.0, 0.0], "size": [100, 50], "mode": 0}},
        }

    prior_store = {"entries": {}, "definitions": definitions, "virtual_wires": []}
    result = reconcile(wf, prior_store)

    missed = set(result.definition_relayout)
    for uuid in _MUSIC_VIDEO_SUBGRAPHS:
        assert uuid in missed, f"subgraph {uuid} should be in definition_relayout on miss"

    # Prior bounding box must be available for each miss.
    for uuid in _MUSIC_VIDEO_SUBGRAPHS:
        assert uuid in result.definition_prior_bounding, (
            f"subgraph {uuid} must have prior bounding for layout fallback"
        )
        assert result.definition_prior_bounding[uuid] == [0.0, 0.0, 300.0, 200.0]


# ---------------------------------------------------------------------------
# T11: ChangeReport — no-cry-wolf for content_edits
# ---------------------------------------------------------------------------

def test_change_report_no_cry_wolf_for_content_edits():
    """content_edits must name only actually-edited nodes; stabilization ok in other section.

    A workflow with two matched nodes (A = unchanged, B = widget-edited) plus one
    bridge-minted node (C, legacy-hash bridged) is reconciled.  The ChangeReport's
    ``content_edits`` section must:
    - list A in ``preserved`` (not edited)
    - list B in ``edited`` (widget changed)
    - NOT list C in ``edited`` (bridge_minted is an identity event)

    The ``identity_stabilization`` section is allowed to report bridge_minted=C.
    """
    # Build a minimal workflow with two uid-bearing nodes.
    nodes = {
        "1": VibeNode(id="1", class_type="CLIPTextEncode", uid="uid-A"),
        "2": VibeNode(id="2", class_type="KSampler", uid="uid-B",
                      widgets={"steps": 20}),
    }
    wf = VibeWorkflow(id="test-wf",
        nodes=nodes,
        edges=[],
        source=WorkflowSource(id="test"),
    )

    prior_store = {
        "entries": {
            "uid-A": {"pos": [0, 0], "size": [200, 100], "mode": 0, "flags": {}, "color": "", "properties": {}, "group": None},
            "uid-B": {"pos": [300, 0], "size": [200, 100], "mode": 0, "flags": {}, "color": "", "properties": {}, "group": None},
        },
        "groups": [],
        "extra": {},
        "definitions": {},
        "virtual_wires": [],
    }

    result = reconcile(wf, prior_store)
    assert "uid-A" in result.matched
    assert "uid-B" in result.matched

    # Simulate a field delta: only uid-B had a widget edit.
    field_delta = {
        "uid-B": {"widget_values_sig": ((), (("steps", "20"),))},
    }

    report = build_change_report(result, field_delta)

    # content_edits: A preserved, B edited.
    assert "uid-A" in report.content_edits.preserved
    assert "uid-B" in report.content_edits.edited

    # Crucially: uid-A must NOT appear in edited.
    assert "uid-A" not in report.content_edits.edited

    # identity_stabilization may have bridge_minted but these are NOT content edits.
    # (In this fixture there are no bridged nodes, so it should be empty.)
    assert report.identity_stabilization.bridge_minted == []

    # Verify that stabilization events are allowed in identity_stabilization
    # even when content_edits has none.
    assert isinstance(report.identity_stabilization.definition_relayout, list)
    assert isinstance(report.identity_stabilization.unmatched_legacy, list)


# ---------------------------------------------------------------------------
# T11: Bound reconcile assignment cost — fallback and synthetic stress
# ---------------------------------------------------------------------------


def test_min_cost_assign_exhaustive_for_small_groups():
    """Exact exhaustive matching is used when min(n,m) ≤ 8 and budget is safe.

    Builds a workflow with 6 twin uid-less nodes, a store with 6 annotated
    prior entries, and asserts that every node is matched to its nearest
    prior position (exact behaviour unchanged for small groups).
    """
    from vibecomfy.porting.layout.reconcile import _use_exhaustive

    assert _use_exhaustive(6, 6) is True, "6×6 must use exhaustive"
    assert _use_exhaustive(8, 8) is True, "8×8 must use exhaustive (budget = 40320)"
    assert _use_exhaustive(7, 10) is False, (
        "7×10 → P(10,7)=604800 exceeds the 40320 budget"
    )
    assert _use_exhaustive(3, 10) is True, "3×10 → P(10,3)=720 ≤ budget"
    assert _use_exhaustive(9, 9) is False, "min(n,m)=9 > SAFE_K → fallback"
    assert _use_exhaustive(1, 1) is True, "trivial case"


def test_min_cost_assign_fallback_used_for_large_groups():
    """Deterministic greedy fallback is used when min(n,m) > 8.

    Creates a hash-collision group of 10 twin RandomNoise nodes and
    10 annotated prior entries.  Verifies that reconcile completes
    without hanging and all 10 nodes are matched.
    """
    wf = _wf("large_twin_group")
    # 10 structurally identical uid-less RandomNoise nodes at distinct positions.
    for i in range(10):
        nid = str(i)
        wf.nodes[nid] = VibeNode(
            id=nid,
            class_type="RandomNoise",
            inputs={"noise_seed": 42},
            uid="",
            metadata={
                "_ui": {
                    "id": i,
                    "pos": [float(i * 100), 0.0],
                    "size": [200.0, 100.0],
                    "mode": 0,
                    "properties": {},
                }
            },
        )

    shared_hash = legacy_hash("0", wf)
    for i in range(1, 10):
        assert legacy_hash(str(i), wf) == shared_hash, "all 10 nodes must hash identically"

    store = {
        "entries": {
            f"prior-{i}": {**_furniture(float(i * 100)), "_legacy_hash": shared_hash}
            for i in range(10)
        },
        "groups": [],
        "extra": {},
        "definitions": {},
        "virtual_wires": [],
    }

    result = reconcile(wf, store)

    assert len(result.bridge_minted) == 10, "all 10 nodes must be bridge-matched"
    assert result.new == [], "no nodes should remain unmatched"
    assert result.unmatched_legacy == [], "no prior entries should remain unmatched"

    # Each node should be assigned to the nearest prior position.
    # (Greedy may not be globally optimal but should be near-optimal.)
    for nid, node in wf.nodes.items():
        assert node.uid, f"node {nid} must have a minted uid"
        assigned_pos = result.matched[node.uid]["pos"]
        node_x = node.metadata["_ui"]["pos"][0]
        # Distance to assigned prior pos ≤ 500 (halfway to next) is reasonable
        assert abs(node_x - assigned_pos[0]) <= 500, (
            f"node {nid} at x={node_x} assigned to x={assigned_pos[0]} — too far"
        )


def test_100_node_synthetic_reconcile_completes():
    """A ~100-node hash-collision group completes reconcile without hanging.

    Creates 100 structurally identical uid-less nodes and 100 annotated
    prior entries, then reconciles.  The assignment uses the greedy
    fallback path (min(100,100) > 8) and must finish in a reasonable
    time without excessive memory use.
    """
    N = 100
    wf = _wf("synthetic_100")

    for i in range(N):
        nid = str(i)
        wf.nodes[nid] = VibeNode(
            id=nid,
            class_type="RandomNoise",
            inputs={"noise_seed": 42},
            uid="",
            metadata={
                "_ui": {
                    "id": i,
                    "pos": [float(i * 10), 0.0],
                    "size": [200.0, 100.0],
                    "mode": 0,
                    "properties": {},
                }
            },
        )

    shared_hash = legacy_hash("0", wf)
    # Sanity: all nodes share the same hash.
    for i in (1, N // 2, N - 1):
        assert legacy_hash(str(i), wf) == shared_hash

    store = {
        "entries": {
            f"prior-{i}": {**_furniture(float(i * 10)), "_legacy_hash": shared_hash}
            for i in range(N)
        },
        "groups": [],
        "extra": {},
        "definitions": {},
        "virtual_wires": [],
    }

    result = reconcile(wf, store)

    assert len(result.bridge_minted) == N, f"all {N} nodes must be bridge-matched"
    assert result.new == [], "no nodes should remain unmatched"
    assert result.unmatched_legacy == [], "no prior entries should remain unmatched"

    # Verify every node got a minted uid and furniture.
    for nid, node in wf.nodes.items():
        assert node.uid, f"node {nid} must have a minted uid"
        assert node.uid in result.matched, f"minted uid {node.uid} must be in matched"

    # Quick sanity: assigned positions should be near the node's canvas position.
    max_deviation = 0.0
    for nid, node in wf.nodes.items():
        node_x = node.metadata["_ui"]["pos"][0]
        assigned_x = result.matched[node.uid]["pos"][0]
        max_deviation = max(max_deviation, abs(node_x - assigned_x))

    # Greedy nearest-neighbour should keep every node within ~500px of its
    # original position (much tighter than the 1000px canvas span).
    assert max_deviation <= 500.0, (
        f"max deviation {max_deviation} exceeds 500px — assignment is too scattered"
    )
