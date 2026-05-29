"""Tests for control_after_generate retention through JSON→IR ingest (T3).

Proves:
1. 'randomize' and 'fixed' captured from the named-inputs dict (api-format path).
2. 'fixed' captured from _ui.widgets_values KSampler None-slot path.
3. Absent control_after_generate → metadata key unset (never guessed).
4. compile("api") guard: control_after_generate absent from compiled output
   even when captured in metadata (byte-identical compile path preserved).
"""
from __future__ import annotations

import json

from vibecomfy.ingest.normalize import convert_to_vibe_format


def _ksampler_api_node(*, control: str | None = None) -> dict:
    inputs: dict = {
        "seed": 42,
        "steps": 20,
        "cfg": 7.0,
        "sampler_name": "euler",
        "scheduler": "normal",
        "denoise": 1.0,
    }
    if control is not None:
        inputs["control_after_generate"] = control
    return {"class_type": "KSampler", "inputs": inputs}


def _ksampler_api_node_with_ui(*, control: str) -> dict:
    """KSampler node as produced by _normalize_ui_to_api with _ui.widgets_values.

    KSampler widget schema: ["seed", None, "steps", "cfg", "sampler_name", "scheduler", "denoise"]
    Slot index 1 is None (the control_after_generate UI slot).
    """
    return {
        "class_type": "KSampler",
        "inputs": {
            "seed": 42,
            "steps": 20,
            "cfg": 7.0,
            "sampler_name": "euler",
            "scheduler": "normal",
            "denoise": 1.0,
        },
        "_ui": {"widgets_values": [42, control, 20, 7.0, "euler", "normal", 1.0]},
    }


def _workflow_from_node(node: dict, node_id: str = "1"):  # type: ignore[return]
    return convert_to_vibe_format({node_id: node})


# ── Case 1a: 'randomize' captured from named inputs dict ─────────────────────


def test_control_after_generate_randomize_from_inputs() -> None:
    wf = _workflow_from_node(_ksampler_api_node(control="randomize"))
    assert wf.nodes["1"].metadata.get("control_after_generate") == "randomize"


# ── Case 1b: 'fixed' captured from named inputs dict ─────────────────────────


def test_control_after_generate_fixed_from_inputs() -> None:
    wf = _workflow_from_node(_ksampler_api_node(control="fixed"))
    assert wf.nodes["1"].metadata.get("control_after_generate") == "fixed"


# ── Case 2: 'fixed' captured from _ui.widgets_values None-slot ───────────────


def test_control_after_generate_fixed_from_ui_widgets() -> None:
    wf = _workflow_from_node(_ksampler_api_node_with_ui(control="fixed"))
    assert wf.nodes["1"].metadata.get("control_after_generate") == "fixed"


# ── Case 3: absent → metadata key unset (never guessed) ──────────────────────


def test_control_after_generate_absent_leaves_metadata_unset() -> None:
    wf = _workflow_from_node(_ksampler_api_node())
    assert "control_after_generate" not in wf.nodes["1"].metadata, (
        "control_after_generate must not be guessed when absent from source"
    )


# ── Case 4a: compile("api") excludes control_after_generate ──────────────────


def test_compile_api_excludes_control_after_generate() -> None:
    """compile('api') must not include control_after_generate even when metadata carries it."""
    wf = _workflow_from_node(_ksampler_api_node(control="randomize"))
    assert wf.nodes["1"].metadata.get("control_after_generate") == "randomize", "precondition: metadata captured"
    compiled = wf.compile("api")
    assert "control_after_generate" not in compiled.get("1", {}).get("inputs", {}), (
        "compile('api') must filter control_after_generate via _is_ui_only_prompt_input"
    )


# ── Case 4b: compile("api") byte-identical with and without the capture ───────


def test_compile_api_byte_identical_with_and_without_control_capture() -> None:
    """compile('api') output is identical regardless of control_after_generate presence.

    This is the guard asserting the T2 ingest change leaves the compiled API dict
    byte-for-byte unchanged: a node with control_after_generate captured in metadata
    compiles identically to the same node without it at all.
    """
    wf_without = _workflow_from_node(_ksampler_api_node())
    wf_with = _workflow_from_node(_ksampler_api_node(control="randomize"))

    compiled_without = wf_without.compile("api")
    compiled_with = wf_with.compile("api")

    assert json.dumps(compiled_without, sort_keys=True) == json.dumps(compiled_with, sort_keys=True), (
        "compile('api') output must be byte-for-byte identical with and without "
        "control_after_generate — the ingest metadata capture must not alter the compiled dict"
    )


# ═══════════════════════════════════════════════════════════════════════════════
# T6 — Identity capture & determinism on the flat walking-skeleton fixture
# ═══════════════════════════════════════════════════════════════════════════════


def _load_flat_wf():
    """Load the flat.json walking-skeleton fixture → VibeWorkflow (cached helper)."""
    import json as _json

    with open("tests/fixtures/walking_skeleton/flat.json") as fh:
        raw = _json.load(fh)
    return convert_to_vibe_format(raw)


def test_flat_every_node_has_nonempty_uid_equal_to_litegraph_id() -> None:
    """Every node gets a non-empty uid equal to its source litegraph id."""
    wf = _load_flat_wf()
    raw = json.load(open("tests/fixtures/walking_skeleton/flat.json"))
    raw_ids = {str(n["id"]) for n in raw["nodes"]}

    for nid, node in wf.nodes.items():
        assert node.uid, f"node {nid} has empty uid"
        assert node.uid in raw_ids, f"node {nid} uid {node.uid!r} not in raw ids {raw_ids}"
        assert node.uid == nid, (
            f"node {nid} uid {node.uid!r} does not equal its own litegraph id {nid}"
        )


def test_flat_pre_existing_vibecomfy_uid_read_back_not_fresh_mint() -> None:
    """A node with pre-existing properties['vibecomfy_uid'] reads that value back."""
    import json as _json

    raw = _json.load(open("tests/fixtures/walking_skeleton/flat.json"))
    # Stamp a synthetic vibecomfy_uid onto KSampler (id=5) properties
    for node in raw["nodes"]:
        if node["id"] == 5:
            node.setdefault("properties", {})["vibecomfy_uid"] = "custom-ksampler-uuid"

    wf = convert_to_vibe_format(raw)
    ksampler = wf.nodes["5"]
    assert ksampler.uid == "custom-ksampler-uuid", (
        f"Pre-existing vitecomfy_uid not preserved: got {ksampler.uid!r}"
    )


def test_flat_pos_size_reachable_via_metadata_ui() -> None:
    """Captured pos/size are reachable via metadata['_ui']."""
    wf = _load_flat_wf()
    raw = json.load(open("tests/fixtures/walking_skeleton/flat.json"))
    raw_by_id = {str(n["id"]): n for n in raw["nodes"]}

    for nid, node in wf.nodes.items():
        _ui = node.metadata.get("_ui")
        assert isinstance(_ui, dict), f"node {nid} missing _ui metadata"
        assert "pos" in _ui, f"node {nid} _ui missing pos"
        assert "size" in _ui, f"node {nid} _ui missing size"
        expected = raw_by_id[nid]
        assert _ui["pos"] == expected["pos"], (
            f"node {nid} pos mismatch: {_ui['pos']} != {expected['pos']}"
        )
        assert _ui["size"] == expected["size"], (
            f"node {nid} size mismatch: {_ui['size']} != {expected['size']}"
        )


def test_flat_determinism_same_source_identical_uids() -> None:
    """Same source → identical uids across two ingests."""
    wf1 = _load_flat_wf()
    wf2 = _load_flat_wf()

    for nid in sorted(wf1.nodes.keys(), key=lambda x: int(x) if x.isdigit() else 0):
        assert nid in wf2.nodes, f"node {nid} missing from second ingest"
        assert wf1.nodes[nid].uid == wf2.nodes[nid].uid, (
            f"node {nid}: non-deterministic uid {wf1.nodes[nid].uid!r} vs {wf2.nodes[nid].uid!r}"
        )


# ── T4: mode/flags/color/bgcolor retention (K3 invariant) ────────────────────


def _node_with_mode(mode: int = 4, **extra_vis: object) -> dict:
    """API-format node with _ui carrying litegraph visual fields."""
    _ui: dict = {"id": 1, "mode": mode}
    for k, v in extra_vis.items():
        _ui[k] = v
    return {"class_type": "KSampler", "inputs": {"seed": 1}, "_ui": _ui}


def _node_without_mode() -> dict:
    return {"class_type": "KSampler", "inputs": {"seed": 1}}


def test_mode_captured_from_pure_python_path() -> None:
    """Pure-Python path: mode:4 lands in metadata['mode'] (via full _ui)."""
    raw_ui = {
        "nodes": [
            {
                "id": 1,
                "type": "KSampler",
                "mode": 4,
                "inputs": [],
                "widgets_values": [42, "fixed", 20, 7.0, "euler", "normal", 1.0],
            }
        ],
        "links": [],
    }
    from vibecomfy.ingest.normalize import normalize_to_api
    api = normalize_to_api(raw_ui, use_comfy_converter=False)
    wf = convert_to_vibe_format(api)
    assert wf.nodes["1"].metadata.get("mode") == 4


def test_mode_captured_from_comfy_converter_path() -> None:
    """Comfy-converter path: mode:4 in _merge_slim_ui lands in metadata['mode']."""
    # Simulate the result of convert_ui_to_api + _merge_slim_ui by providing
    # an API-format node that already has a slim _ui with mode set.
    api_node = _node_with_mode(mode=4)
    wf = convert_to_vibe_format({"1": api_node})
    assert wf.nodes["1"].metadata.get("mode") == 4


def test_flags_color_bgcolor_captured() -> None:
    """flags, color, bgcolor are also captured into metadata."""
    api_node = _node_with_mode(mode=0, flags={"pinned": True}, color="#ff0000", bgcolor="#000000")
    wf = convert_to_vibe_format({"1": api_node})
    assert wf.nodes["1"].metadata.get("flags") == {"pinned": True}
    assert wf.nodes["1"].metadata.get("color") == "#ff0000"
    assert wf.nodes["1"].metadata.get("bgcolor") == "#000000"


def test_mode_absent_leaves_metadata_unset() -> None:
    """Nodes with no mode field do not get a metadata['mode'] key."""
    wf = convert_to_vibe_format({"1": _node_without_mode()})
    assert "mode" not in wf.nodes["1"].metadata


def test_mode_does_not_enter_inputs_or_widgets() -> None:
    """mode must never appear in node.inputs or node.widgets (K3 invariant)."""
    api_node = _node_with_mode(mode=4)
    wf = convert_to_vibe_format({"1": api_node})
    node = wf.nodes["1"]
    assert "mode" not in node.inputs
    assert "mode" not in node.widgets


def test_compile_api_byte_identical_with_and_without_mode() -> None:
    """compile('api') output is identical regardless of mode in metadata."""
    api_with_mode = _node_with_mode(mode=4)
    api_without_mode = _node_without_mode()

    wf_with = convert_to_vibe_format({"1": api_with_mode})
    wf_without = convert_to_vibe_format({"1": api_without_mode})

    import json
    compiled_with = json.dumps(wf_with.compile(), sort_keys=True)
    compiled_without = json.dumps(wf_without.compile(), sort_keys=True)
    assert compiled_with == compiled_without, (
        "compile('api') output must not change when mode is present in metadata"
    )
