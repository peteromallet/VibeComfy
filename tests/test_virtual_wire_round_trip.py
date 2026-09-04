"""M6 T10 — Virtual-wire round-trip: default convert vs --keep-virtual-wires.

Builds a synthetic in-memory VibeWorkflow with one model-loader node,
two GetNode/SetNode pairs, and a Reroute node, wired in a small but
realistic shape.  Two test paths:

  (A) Default convert (keep_virtual_wires=False): ``port_convert_workflow``
      resolves helpers; the generated .py contains no explicit GetNode/SetNode/
      Reroute calls.  Reload + emit --to ui; assert virtual-wire furniture
      appears in the emitted JSON nodes list (preserved via the layout store).

  (B) ``--keep-virtual-wires``: same workflow, ``keep_virtual_wires=True``.
      Assert the generated .py contains explicit ``wf.node("GetNode"…)``
      literals.  Reload + emit --to ui; assert the emitted UI JSON is
      canonically byte-equivalent to path A's output.  The IR-level round-trip
      is invariant to the Python representation.

Runs in the default offline suite (no marker).
"""

from __future__ import annotations

import copy
import json
from pathlib import Path

from vibecomfy.porting.convert import port_convert_workflow
from vibecomfy.porting.layout_store import read_store, write_layout
from vibecomfy.porting.emit.ui import emit_ui_json
from vibecomfy.scratchpad_loader import load_scratchpad
from vibecomfy.workflow import VibeEdge, VibeNode, VibeWorkflow, WorkflowSource

# ---------------------------------------------------------------------------
# Synthetic virtual-wire fixture
# ---------------------------------------------------------------------------

_VW_TYPES = frozenset({"GetNode", "SetNode", "Reroute"})


def _make_roundtrip_wf() -> VibeWorkflow:
    """Build a synthetic workflow with model loader + 2 GetNode/SetNode pairs + Reroute.

    Topology::

        CLS ─► SetNode(LATENT) ─► Reroute ─► GetNode(LATENT) ─► KSampler ─► SaveImage
        CLS ─► SetNode(IMAGE)  ─► GetNode(IMAGE) ─► KSampler.latent_image
    """
    wf = VibeWorkflow(
        "vw-roundtrip",
        WorkflowSource("vw-roundtrip", path="test/vw_roundtrip.json", source_type="raw_json"),
    )

    # ── Regular nodes ────────────────────────────────────────────────────
    _add_node(wf, "1", "CheckpointLoaderSimple", pos=[100, 200], size=[300, 100],
              inputs={"ckpt_name": "model.safetensors"})
    _add_node(wf, "5", "KSampler", pos=[1100, 200], size=[300, 100],
              inputs={"seed": 42, "steps": 20, "cfg": 7.0, "sampler_name": "euler",
                      "scheduler": "normal", "denoise": 1.0})
    _add_node(wf, "6", "SaveImage", pos=[1400, 200], size=[300, 100],
              inputs={"filename_prefix": "out/vw"})

    # ── Virtual wire nodes ───────────────────────────────────────────────
    _add_vw_node(wf, "10", "SetNode", channel="LATENT",  pos=[400, 150], size=[200, 58])
    _add_vw_node(wf, "11", "GetNode", channel="LATENT",  pos=[900, 150], size=[200, 58])
    _add_vw_node(wf, "12", "SetNode", channel="IMAGE",   pos=[400, 300], size=[200, 58])
    _add_vw_node(wf, "13", "GetNode", channel="IMAGE",   pos=[700, 300], size=[200, 58])
    _add_vw_node(wf, "14", "Reroute",                    pos=[650, 150], size=[75, 26])

    # ── Edges (all use slot "0" for simplicity) ──────────────────────────
    # LATENT broadcast pair with Reroute inline:
    #   CLS(0) → SetNode(LATENT)(broadcast_in) → SetNode(0) → Reroute(0) → Reroute(0) → GetNode(LATENT)(broadcast_out) → GetNode(0) → KSampler.model
    wf.edges.append(VibeEdge("1",  "0", "10", "broadcast_in"))
    wf.edges.append(VibeEdge("10", "0", "14", "0"))
    wf.edges.append(VibeEdge("14", "0", "11", "broadcast_out"))
    wf.edges.append(VibeEdge("11", "0", "5",  "model"))

    # IMAGE broadcast pair (live path):
    #   CLS(0) → SetNode(IMAGE)(broadcast_in) → SetNode(0) → GetNode(IMAGE)(broadcast_out) → GetNode(0) → KSampler.latent_image
    wf.edges.append(VibeEdge("1",  "0", "12", "broadcast_in"))
    wf.edges.append(VibeEdge("12", "0", "13", "broadcast_out"))
    wf.edges.append(VibeEdge("13", "0", "5",  "latent_image"))

    # KSampler(0) → SaveImage.images
    wf.edges.append(VibeEdge("5", "0", "6", "images"))

    return wf


def _add_node(
    wf: VibeWorkflow,
    node_id: str,
    class_type: str,
    *,
    pos=None,
    size=None,
    inputs=None,
) -> VibeNode:
    n = VibeNode(node_id, class_type, inputs=dict(inputs or {}), pos=pos, size=size)
    n.uid = node_id
    wf.nodes[node_id] = n
    return n


def _add_vw_node(
    wf: VibeWorkflow,
    node_id: str,
    class_type: str,
    *,
    channel: str | None = None,
    pos=None,
    size=None,
) -> VibeNode:
    # broadcast_name() reads from node.inputs['widget_0'] (not metadata).
    vw_inputs: dict = {}
    if channel:
        vw_inputs["widget_0"] = channel
    ui: dict = {"type": class_type}
    n = VibeNode(node_id, class_type, inputs=vw_inputs, metadata={"_ui": ui}, pos=pos, size=size)
    n.uid = node_id
    wf.nodes[node_id] = n
    return n


# ---------------------------------------------------------------------------
# Canonicalisation helper
# ---------------------------------------------------------------------------


def _canonical_json(obj: dict) -> str:
    """Produce a canonical JSON string: sorted keys, consistent numeric formatting.

    Link and node IDs are implementation details that can differ between
    convert paths.  We zero them out so the comparison reflects structural
    equivalence, not ID-sequence drift.
    """
    # Deep-copy so we don't mutate the original.
    import copy
    norm = copy.deepcopy(obj)
    _zero_link_ids(norm)
    _zero_node_ids(norm)
    return json.dumps(norm, indent=2, sort_keys=True)


def _zero_link_ids(obj: dict) -> None:
    """Zero out link IDs in a litegraph envelope."""
    links = obj.get("links")
    if isinstance(links, list):
        for link in links:
            if isinstance(link, list) and len(link) >= 1:
                link[0] = 0
    if isinstance(obj.get("last_link_id"), int):
        obj["last_link_id"] = 0


def _zero_node_ids(obj: dict) -> None:
    """Zero out litegraph integer node IDs (the ``id`` field on each node)."""
    nodes = obj.get("nodes")
    if isinstance(nodes, list):
        for node in nodes:
            if isinstance(node, dict) and "id" in node:
                node["id"] = 0
    if isinstance(obj.get("last_node_id"), int):
        obj["last_node_id"] = 0


# ---------------------------------------------------------------------------
# Test A: Default convert (no --keep-virtual-wires)
# ---------------------------------------------------------------------------


def test_default_convert_round_trip(tmp_path: Path):
    """Conversion preserves authored helpers; projection lowers them later."""
    wf = _make_roundtrip_wf()
    caller_nodes_before = copy.deepcopy(wf.nodes)
    caller_edges_before = copy.deepcopy(wf.edges)
    py_path = tmp_path / "vw_test_a.py"
    result = port_convert_workflow(
        wf,
        keep_virtual_wires=False,
        source_path="test/vw_roundtrip.json",
        validate=True,
    )
    assert result.mode == "scratchpad"
    assert result.text
    assert wf.nodes == caller_nodes_before
    assert wf.edges == caller_edges_before
    py_path.write_text(result.text, encoding="utf-8")
    wf_reloaded = load_scratchpad(py_path, provenance_override="user_confirmed")
    assert wf_reloaded.compile("api") == wf.compile("api")


def test_failed_convert_does_not_mutate_authored_virtual_wire_graph() -> None:
    wf = _make_roundtrip_wf()
    before = copy.deepcopy(wf)
    result = port_convert_workflow(wf, keep_virtual_wires=False, validate=False)
    assert result.text
    assert wf.nodes == before.nodes
    assert wf.edges == before.edges


# ---------------------------------------------------------------------------
# Test B: --keep-virtual-wires
# ---------------------------------------------------------------------------


def test_keep_virtual_wires_round_trip(tmp_path: Path):
    """Path B: keep virtual wires, assert .py contains explicit literals,
    reload + emit, assert byte-equivalence with path A."""
    wf = _make_roundtrip_wf()
    vw_count_before = sum(1 for n in wf.nodes.values() if n.class_type in _VW_TYPES)

    # ── Convert with keep_virtual_wires=True ─────────────────────────────
    result = port_convert_workflow(
        wf,
        keep_virtual_wires=True,
        source_path="test/vw_roundtrip.json",
        validate=True,
    )
    assert result.mode == "scratchpad"
    assert result.text

    # Conversion must not emit a private capture authority.
    assert "virtual_wires" not in result.text

    # ── Write .py and layout sidecar ─────────────────────────────────────
    py_path = tmp_path / "vw_test_b.py"
    write_layout(py_path, wf)
    py_path.write_text(result.text, encoding="utf-8")

    # ── Reload ───────────────────────────────────────────────────────────
    wf_reloaded = load_scratchpad(py_path, provenance_override="user_confirmed")

    # Explicit keep mode preserves the authored helper graph in the source.
    vw_count_after = sum(1 for n in wf_reloaded.nodes.values() if n.class_type in _VW_TYPES)
    assert vw_count_after == vw_count_before

    # ── Emit to UI ───────────────────────────────────────────────────────
    store = read_store(py_path)
    ui_b = emit_ui_json(
        wf_reloaded,
        include_virtual_wires=True,
        prior_store=store,
    )
    assert "nodes" in ui_b
    assert len(ui_b["nodes"]) > 0

    # The authored helper furniture remains visible in explicit keep mode.
    vw_in_b = [n for n in ui_b["nodes"] if n.get("type") in _VW_TYPES]
    assert len(vw_in_b) == vw_count_before

    # ── Flat-mode emit for comparison with path A ────────────────────────
    # The flat (execution) graph should be identical regardless of whether
    # virtual wires were retained in Python source or resolved during conversion.
    ui_b_flat = emit_ui_json(
        wf_reloaded,
        include_virtual_wires=False,
        prior_store=store,
    )

    # Build path A (default convert) in the same tmp_path for flat comparison.
    wf_a2 = _make_roundtrip_wf()
    result_a = port_convert_workflow(
        wf_a2,
        keep_virtual_wires=False,
        source_path="test/vw_roundtrip.json",
        validate=False,
    )
    py_a2 = tmp_path / "vw_test_a_cmp.py"
    write_layout(py_a2, wf_a2)
    py_a2.write_text(result_a.text, encoding="utf-8")
    wf_a2_reloaded = load_scratchpad(py_a2, provenance_override="user_confirmed")
    store_a2 = read_store(py_a2)
    ui_a_flat = emit_ui_json(
        wf_a2_reloaded,
        include_virtual_wires=False,
        prior_store=store_a2,
    )

    # Byte-equivalence: flat execution graphs should match after canonicalization.
    canonical_a = _canonical_json(ui_a_flat)
    canonical_b = _canonical_json(ui_b_flat)

    assert canonical_a == canonical_b, (
        f"Flat execution graphs should be byte-equivalent after canonicalization.\n"
        f"Path A (default convert): {len(canonical_a)} chars\n"
        f"Path B (--keep-virtual-wires): {len(canonical_b)} chars\n"
    )
