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
from collections import Counter
from copy import deepcopy
from pathlib import Path

import pytest

from vibecomfy.comfy_nodes.agent.graph_normalization import normalize_agent_edit_graph
from vibecomfy.ingest.normalize import convert_to_vibe_format, from_api, from_ui, normalize_to_api
from vibecomfy.porting.emit.ui import emit_ui_json


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


def test_public_raw_widgets_alias_is_preserved_as_raw_widget_payload() -> None:
    wf = _workflow_from_node(
        {
            "class_type": "PrimitiveInt",
            "inputs": {"widget_0": 7, "widget_1": "fixed"},
            "raw_widgets": {
                "values": [7, "fixed"],
                "shape": "list",
                "source": "ui.widgets_values",
                "has_dict_rows": False,
                "length": 2,
            },
        }
    )

    node = wf.nodes["1"]
    assert node.raw_widgets is not None
    assert node.raw_widgets.values == [7, "fixed"]
    assert node.raw_widgets.length == 2
    assert "raw_widgets" not in node.metadata


def test_vibe_shape_decodes_rich_node_raw_widgets_payload() -> None:
    """The rich decoder turns a serialized RawWidgetPayload into node.raw_widgets
    and preserves node metadata._ui verbatim (lossless envelope decode)."""
    rich_ui = {
        "_ui": {
            "id": 1,
            "type": "PrimitiveInt",
            "widgets_values": [7, "fixed"],
        }
    }
    wf = convert_to_vibe_format(
        {
            "id": "test",
            "vibecomfy_format_version": "1.0",
            "compiled_api": {
                "1": {
                    "class_type": "PrimitiveInt",
                    "inputs": {"widget_0": 7, "widget_1": "fixed"},
                }
            },
            "nodes": {
                "1": {
                    "id": "1",
                    "class_type": "PrimitiveInt",
                    "inputs": {},
                    "widgets": {"widget_0": 7, "widget_1": "fixed"},
                    "metadata": rich_ui,
                    "uid": "1",
                    "raw_widgets": {
                        "values": [7, "fixed"],
                        "shape": "list",
                        "source": "ui.widgets_values",
                        "has_dict_rows": False,
                        "length": 2,
                    },
                }
            },
            "edges": [],
            "inputs": {},
            "outputs": [],
            "requirements": {},
            "source": {"id": "test"},
            "strict_types": False,
        }
    )

    node = wf.nodes["1"]
    assert node.raw_widgets is not None
    assert node.raw_widgets.values == [7, "fixed"]
    assert node.raw_widgets.length == 2
    assert node.raw_widgets.shape == "list"
    # metadata._ui is preserved verbatim (plus the provenance stamp).
    assert node.metadata["_ui"] == rich_ui["_ui"]
    assert node.metadata["provenance"] == "untrusted_source"

def test_vibe_shape_carries_dynamic_dict_raw_ui_for_widget_pin() -> None:
    wf = convert_to_vibe_format(
        {
            "id": "test",
            "vibecomfy_format_version": "1.0",
            "compiled_api": {
                "81": {
                    "class_type": "VHS_SplitImages",
                    "inputs": {"images": ["105", 0], "split_index": 24},
                }
            },
            "nodes": {
                "81": {
                    "id": "81",
                    "class_type": "VHS_SplitImages",
                    "inputs": {},
                    "widgets": {"split_index": 24},
                    "uid": "81",
                    "raw_widgets": {
                        "values": {"split_index": 24},
                        "shape": "dict",
                        "source": "ui.widgets_values",
                        "has_dict_rows": True,
                        "length": 1,
                    },
                    "metadata": {
                        "_ui": {
                            "id": 81,
                            "type": "VHS_SplitImages",
                            "pos": [1075, 1136],
                            "size": [315, 118],
                            "flags": {},
                            "order": 28,
                            "mode": 0,
                            "inputs": [{"name": "images", "type": "IMAGE", "link": 198}],
                            "outputs": [{"name": "IMAGE_A", "type": "IMAGE", "links": []}],
                            "properties": {"Node name for S&R": "VHS_SplitImages"},
                            "widgets_values": {"split_index": 24},
                        }
                    },
                }
            },
            "edges": [],
            "inputs": {},
            "outputs": [],
            "requirements": {},
            "source": {"id": "test"},
            "strict_types": False,
        }
    )

    node = wf.nodes["81"]
    assert node.raw_widgets is not None
    assert node.raw_widgets.values == {"split_index": 24}
    assert node.metadata["_ui"]["widgets_values"] == {"split_index": 24}
    assert node.metadata["_ui"]["inputs"][0]["link"] == 198


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
    """Pure-Python path: mode:4 lands on the first-class VibeNode.mode field."""
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
    assert wf.nodes["1"].mode == 4
    # _ui.mode is left in place so emit_ui_json furniture stays intact.
    assert wf.nodes["1"].metadata["_ui"]["mode"] == 4
    # No duplicate furniture copy is written on new ingests.
    assert "mode" not in wf.nodes["1"].metadata


def test_mode_captured_from_comfy_converter_path() -> None:
    """Comfy-converter path: mode:4 in _merge_slim_ui lands on VibeNode.mode."""
    # Simulate the result of convert_ui_to_api + _merge_slim_ui by providing
    # an API-format node that already has a slim _ui with mode set.
    api_node = _node_with_mode(mode=4)
    wf = convert_to_vibe_format({"1": api_node})
    assert wf.nodes["1"].mode == 4
    assert wf.nodes["1"].metadata["_ui"]["mode"] == 4
    assert "mode" not in wf.nodes["1"].metadata


def test_flags_color_bgcolor_captured() -> None:
    """flags, color, bgcolor are also captured into metadata."""
    api_node = _node_with_mode(mode=0, flags={"pinned": True}, color="#ff0000", bgcolor="#000000")
    wf = convert_to_vibe_format({"1": api_node})
    assert wf.nodes["1"].metadata.get("flags") == {"pinned": True}
    assert wf.nodes["1"].metadata.get("color") == "#ff0000"
    assert wf.nodes["1"].metadata.get("bgcolor") == "#000000"


def test_mode_absent_leaves_field_zero_and_metadata_unset() -> None:
    """Nodes with no mode field get mode 0 and no metadata['mode'] key."""
    wf = convert_to_vibe_format({"1": _node_without_mode()})
    assert wf.nodes["1"].mode == 0
    assert "mode" not in wf.nodes["1"].metadata


def test_mode_does_not_enter_inputs_or_widgets() -> None:
    """mode must never appear in node.inputs or node.widgets (K3 invariant)."""
    api_node = _node_with_mode(mode=4)
    wf = convert_to_vibe_format({"1": api_node})
    node = wf.nodes["1"]
    assert node.mode == 4
    assert "mode" not in node.inputs
    assert "mode" not in node.widgets


def test_compile_api_honors_ingest_captured_mode() -> None:
    """mode is first-class: ingest-captured mode=4 bypasses the node at compile.

    The pre-P10 decoupling (captured mode never tripping compile) existed only
    because mode was not a schema field.  The field is now the compile signal:
    a mode=4 node is dropped/bypassed, while mode=0 compiles identically to
    an absent mode.
    """
    import json

    wf_bypassed = convert_to_vibe_format({"1": _node_with_mode(mode=4)})
    wf_zero = convert_to_vibe_format({"1": _node_with_mode(mode=0)})
    wf_absent = convert_to_vibe_format({"1": _node_without_mode()})

    assert "1" not in wf_bypassed.compile("api"), "mode=4 node must be bypassed"

    compiled_zero = json.dumps(wf_zero.compile(), sort_keys=True)
    compiled_absent = json.dumps(wf_absent.compile(), sort_keys=True)
    assert compiled_zero == compiled_absent, (
        "compile('api') output must be identical for mode=0 vs absent mode"
    )


# ══════════════════════════════════════════════════════════════════════════════
# T19 — comfy_converter_strict parameter semantics (offline, no comfy needed)
# ══════════════════════════════════════════════════════════════════════════════

# Minimal UI-shaped workflow usable as a normalize_to_api input.
_MINIMAL_UI_RAW: dict = {
    "nodes": [{"id": 1, "type": "SaveImage", "inputs": [], "widgets_values": ["output"]}],
    "links": [],
}


def test_comfy_converter_strict_absent_comfy_falls_through_to_offline() -> None:
    """comfy_converter_strict=True with comfy absent: import guard skips cleanly.

    When ``use_comfy_converter=True`` (default) but the comfy package cannot be
    imported, the ImportError guard fires before strict mode is ever consulted.
    The call must succeed by falling through to the offline converter — no
    exception propagated, result is a valid API dict.
    """
    from unittest.mock import patch
    from vibecomfy.ingest.normalize import normalize_to_api

    # Simulate comfy being absent by making the import raise ImportError.
    with patch.dict("sys.modules", {"comfy": None, "comfy.component_model": None,
                                    "comfy.component_model.workflow_convert": None}):
        result = normalize_to_api(_MINIMAL_UI_RAW, comfy_converter_strict=True)

    assert isinstance(result, dict), "offline fallback must produce a dict"
    assert "1" in result, "offline result must contain the single node"


def test_comfy_converter_strict_no_op_when_use_comfy_converter_false() -> None:
    """comfy_converter_strict is a no-op when use_comfy_converter=False.

    When the comfy converter is disabled entirely (``use_comfy_converter=False``),
    the strict flag must have no effect — the call succeeds using the offline
    converter regardless of the flag value.
    """
    from vibecomfy.ingest.normalize import normalize_to_api

    result_default = normalize_to_api(
        _MINIMAL_UI_RAW, use_comfy_converter=False, comfy_converter_strict=False
    )
    result_strict = normalize_to_api(
        _MINIMAL_UI_RAW, use_comfy_converter=False, comfy_converter_strict=True
    )

    import json
    assert json.dumps(result_default, sort_keys=True) == json.dumps(result_strict, sort_keys=True), (
        "comfy_converter_strict must be a no-op when use_comfy_converter=False — "
        "both calls must produce identical output"
    )


def test_comfy_converter_default_raises_when_converter_errors() -> None:
    """Default normalize_to_api() is strict when convert_ui_to_api raises.

    When comfy IS importable but ``convert_ui_to_api`` raises an exception, the
    default call must propagate that exception rather than silently falling back
    to the offline converter.
    """
    from unittest.mock import MagicMock, patch
    from vibecomfy.comfy_backend import ComfyCompatibility
    from vibecomfy.ingest.normalize import normalize_to_api

    failing_converter = MagicMock(side_effect=RuntimeError("converter_exploded"))
    fake_module = MagicMock()
    fake_module.convert_ui_to_api = failing_converter
    compatible = ComfyCompatibility(
        ok=True,
        reason_code="ok",
        expected={"commit": "expected", "version": "pinned"},
        actual={"commit": "expected", "version": None},
        safe_families=[],
    )

    with patch.dict("sys.modules", {
        "comfy": MagicMock(),
        "comfy.component_model": MagicMock(),
        "comfy.component_model.workflow_convert": fake_module,
    }), patch("vibecomfy.ingest.normalize.check_comfy_compatibility", return_value=compatible):
        try:
            normalize_to_api(_MINIMAL_UI_RAW)
        except RuntimeError as exc:
            assert "converter_exploded" in str(exc)
        else:
            raise AssertionError(
                "Expected RuntimeError to propagate by default when "
                "convert_ui_to_api raises"
            )


def test_comfy_converter_strict_false_tolerant_when_converter_errors() -> None:
    """comfy_converter_strict=False keeps the explicit tolerant fallback path.

    When comfy IS importable but ``convert_ui_to_api`` raises, the explicit
    ``comfy_converter_strict=False`` opt-out must still fall through to the
    offline converter.
    """
    from unittest.mock import MagicMock, patch
    from vibecomfy.ingest.normalize import normalize_to_api

    failing_converter = MagicMock(side_effect=RuntimeError("converter_exploded"))
    fake_module = MagicMock()
    fake_module.convert_ui_to_api = failing_converter

    with patch.dict("sys.modules", {
        "comfy": MagicMock(),
        "comfy.component_model": MagicMock(),
        "comfy.component_model.workflow_convert": fake_module,
    }), pytest.warns(UserWarning, match="falling back to the offline normalizer"):
        result = normalize_to_api(_MINIMAL_UI_RAW, comfy_converter_strict=False)

    assert isinstance(result, dict), "offline fallback must produce a dict"
    assert "1" in result, "offline result must contain the single node"


def test_comfy_converter_strict_surfaces_version_skew_before_converter_exec() -> None:
    """Strict live-converter paths fence on skew before calling convert_ui_to_api."""
    from unittest.mock import MagicMock, patch

    from vibecomfy.comfy_backend import ComfyCompatibility, ComfyCompatibilityError
    from vibecomfy.ingest.normalize import normalize_to_api

    converter = MagicMock(side_effect=RuntimeError("raw_traceback_should_not_escape"))
    fake_module = MagicMock()
    fake_module.convert_ui_to_api = converter
    mismatch = ComfyCompatibility(
        ok=False,
        reason_code="comfyui_version_skew",
        expected={"commit": "expected", "version": "pinned"},
        actual={"commit": "actual", "version": "other"},
        safe_families=[],
    )

    with patch.dict("sys.modules", {
        "comfy": MagicMock(),
        "comfy.component_model": MagicMock(),
        "comfy.component_model.workflow_convert": fake_module,
    }), patch("vibecomfy.ingest.normalize.check_comfy_compatibility", return_value=mismatch):
        with pytest.raises(ComfyCompatibilityError, match="comfyui_version_skew") as excinfo:
            normalize_to_api(_MINIMAL_UI_RAW, comfy_converter_strict=True)

    converter.assert_not_called()
    assert excinfo.value.compatibility == mismatch


def test_comfy_converter_lenient_skew_falls_back_offline_without_converter_exec() -> None:
    """Lenient live-converter paths still skip converter execution on version skew."""
    from unittest.mock import MagicMock, patch

    from vibecomfy.comfy_backend import ComfyCompatibility
    from vibecomfy.ingest.normalize import normalize_to_api

    converter = MagicMock(side_effect=RuntimeError("raw_traceback_should_not_escape"))
    fake_module = MagicMock()
    fake_module.convert_ui_to_api = converter
    mismatch = ComfyCompatibility(
        ok=False,
        reason_code="comfyui_version_skew",
        expected={"commit": "expected", "version": "pinned"},
        actual={"commit": "actual", "version": "other"},
        safe_families=[],
    )

    with patch.dict("sys.modules", {
        "comfy": MagicMock(),
        "comfy.component_model": MagicMock(),
        "comfy.component_model.workflow_convert": fake_module,
    }), patch("vibecomfy.ingest.normalize.check_comfy_compatibility", return_value=mismatch), pytest.warns(
        UserWarning, match="comfyui_version_skew"
    ):
        result = normalize_to_api(_MINIMAL_UI_RAW, comfy_converter_strict=False)

    converter.assert_not_called()
    assert isinstance(result, dict)
    assert "1" in result


# ═══════════════════════════════════════════════════════════════════════════════
# B02-C1 — lossless rich-envelope decode (serialized Vibe → IR → canonical UI)
# ═══════════════════════════════════════════════════════════════════════════════

_CORPUS_90A1D5 = (
    Path(__file__).resolve().parent.parent
    / "external_workflows/corpus/90a1d5ff9044902e.json"
)


def _load_90a1d5() -> dict:
    return json.loads(_CORPUS_90A1D5.read_text(encoding="utf-8"))


def _ui_projection(ui: dict) -> dict:
    """Deterministic projection of a canonical UI envelope for idempotence compare."""
    nodes = sorted(
        (
            node["id"],
            node["type"],
            node.get("mode"),
            (node.get("properties") or {}).get("vibecomfy_uid"),
            json.dumps(node.get("widgets_values"), sort_keys=True),
        )
        for node in ui.get("nodes", [])
    )
    links = sorted((link[1], link[2], link[3], link[4]) for link in ui.get("links", []))
    return {
        "node_count": len(nodes),
        "nodes": nodes,
        "link_count": len(links),
        "links": links,
        "groups": ui.get("groups", []),
    }


def test_vibe_rich_ingest_preserves_90a1d5() -> None:
    """The rich envelope decodes to the full 15-node IR, NOT the 2-node compiled_api."""
    raw = _load_90a1d5()
    assert len(raw["compiled_api"]) == 2, "precondition: compiled_api is stale/partial evidence"

    wf = convert_to_vibe_format(raw)

    assert len(wf.nodes) == 15
    assert len(wf.edges) == 10
    assert len(wf.outputs) == len(raw["outputs"])
    assert wf.id == raw["id"]
    assert wf.source.id == raw["source"]["id"]
    assert wf.strict_types is False
    assert wf.metadata["external_workflow"] is True

    uids = [node.uid for node in wf.nodes.values()]
    assert len(set(uids)) == 15, "uids must all be distinct"
    assert all(isinstance(uid, str) and uid.strip() for uid in uids)

    modes = Counter(node.mode for node in wf.nodes.values())
    assert dict(modes) == {4: 9, 0: 6}

    assert wf.nodes["10"].class_type == "TripoRefineNode"
    assert wf.nodes["10"].uid == raw["nodes"]["10"]["uid"]

    # Lossless: every rich node's uid/metadata._ui/inputs/widgets decode verbatim.
    for nid, node in wf.nodes.items():
        rich = raw["nodes"][nid]
        assert node.uid == rich["uid"], f"node {nid}: uid not preserved exactly"
        assert node.class_type == rich["class_type"], f"node {nid}: class_type mismatch"
        assert node.metadata["_ui"] == rich["metadata"]["_ui"], (
            f"node {nid}: metadata._ui not preserved verbatim"
        )
        assert node.metadata["provenance"] == "untrusted_source"
        assert node.inputs == rich["inputs"]
        assert node.widgets == rich["widgets"]

    # Canonical UI carries every rich node with the same id/class/mode/uid projection.
    normalized = normalize_agent_edit_graph(raw)
    assert len(normalized["nodes"]) == 15
    assert len(normalized["links"]) == 10
    by_id = {str(node["id"]): node for node in normalized["nodes"]}
    assert set(by_id) == set(raw["nodes"])
    for nid, rich in raw["nodes"].items():
        ui_node = by_id[nid]
        assert ui_node["type"] == rich["class_type"]
        assert ui_node["mode"] == rich["metadata"]["_ui"]["mode"]
        assert (ui_node.get("properties") or {})["vibecomfy_uid"] == rich["uid"]


def test_vibe_rich_ingest_treats_compiled_api_as_optional_evidence() -> None:
    """Rich structure remains authoritative when execution evidence is absent or bad."""
    raw = _load_90a1d5()

    without_evidence = deepcopy(raw)
    without_evidence.pop("compiled_api")
    assert len(convert_to_vibe_format(without_evidence).nodes) == 15

    malformed_evidence = deepcopy(raw)
    malformed_evidence["compiled_api"] = {"10": "not-an-api-node"}
    workflow = convert_to_vibe_format(malformed_evidence)
    assert len(workflow.nodes) == 15
    assert workflow.nodes["10"].class_type == "TripoRefineNode"


def test_public_loaders_preserve_rich_envelope_90a1d5() -> None:
    """load_workflow_any / load_port_source decode envelopes losslessly (P1).

    Public loaders must return the full 15-node IR, not the 2-node compile
    view: they decode the envelope directly instead of compile-then-reingest.
    The execution view (compile("api")) is unchanged at 2 nodes.
    """
    from vibecomfy.cli_loader import load_workflow_any
    from vibecomfy.porting.workbench import load_port_source

    corpus = str(_CORPUS_90A1D5)

    wf = load_workflow_any(corpus)
    assert len(wf.nodes) == 15
    assert wf.nodes["10"].class_type == "TripoRefineNode"
    assert len(wf.compile("api")) == 2

    loaded = load_port_source(corpus)
    assert len(loaded.workflow.nodes) == 15
    assert loaded.workflow.nodes["10"].class_type == "TripoRefineNode"
    assert len(loaded.workflow.compile("api")) == 2
    assert loaded.source_kind in {"indexed_json", "raw_json"}


def test_vibe_rich_ingest_is_idempotent() -> None:
    """rich->UI and UI->IR->UI produce identical projections (nodes, edges, widgets, groups)."""
    raw = _load_90a1d5()

    ui1 = normalize_agent_edit_graph(raw)  # rich -> UI
    assert len(ui1["nodes"]) == 15 and len(ui1["links"]) == 10

    # UI -> IR via the deterministic offline normalizer (the comfy converter
    # intentionally drops mode-4 bypassed nodes — ComfyUI semantics, unchanged).
    api2 = normalize_to_api(ui1, use_comfy_converter=False)
    wf2 = convert_to_vibe_format(api2)
    assert len(wf2.nodes) == 15 and len(wf2.edges) == 10

    ui2 = emit_ui_json(wf2, schema_provider=None, groups=deepcopy(ui1.get("groups")))

    assert _ui_projection(ui1) == _ui_projection(ui2)


def test_vibe_rich_ingest_rejects_malformed_mixed_entries() -> None:
    """Malformed/mixed rich entries raise ValueError; no partial graph is returned."""
    raw = _load_90a1d5()

    mixed_nodes = deepcopy(raw)
    mixed_nodes["nodes"]["999"] = "not-a-node"
    with pytest.raises(ValueError, match="must be mappings"):
        convert_to_vibe_format(mixed_nodes)

    key_mismatch = deepcopy(raw)
    key_mismatch["nodes"]["10"]["id"] = "11"
    with pytest.raises(ValueError, match="must equal node.id"):
        convert_to_vibe_format(key_mismatch)

    blank_uid = deepcopy(raw)
    blank_uid["nodes"]["10"]["uid"] = "  "
    with pytest.raises(ValueError, match="uid must be a nonblank string"):
        convert_to_vibe_format(blank_uid)

    negative_length = deepcopy(raw)
    negative_length["nodes"]["10"]["raw_widgets"]["length"] = -1
    with pytest.raises(ValueError, match="nonnegative integer"):
        convert_to_vibe_format(negative_length)

    non_mapping_edges = deepcopy(raw)
    non_mapping_edges["edges"] = ["not-an-edge"]
    with pytest.raises(ValueError, match="must be mappings"):
        convert_to_vibe_format(non_mapping_edges)


def test_vibe_rich_ingest_rejects_dangling_endpoint_edges() -> None:
    """Edges referencing endpoint node ids absent from nodes raise ValueError."""
    raw = _load_90a1d5()

    dangling_from = deepcopy(raw)
    dangling_from["edges"] = [
        {"from_node": "999", "from_output": "0", "to_node": "3", "to_input": "model_task_id"}
    ]
    with pytest.raises(ValueError, match="must exist in nodes"):
        convert_to_vibe_format(dangling_from)

    dangling_to = deepcopy(raw)
    dangling_to["edges"] = [
        {"from_node": "3", "from_output": "0", "to_node": "424242", "to_input": "model_file"}
    ]
    with pytest.raises(ValueError, match="must exist in nodes"):
        convert_to_vibe_format(dangling_to)

    blank_endpoint = deepcopy(raw)
    blank_endpoint["edges"] = [
        {"from_node": "", "from_output": "0", "to_node": "3", "to_input": "model_task_id"}
    ]
    with pytest.raises(ValueError, match="from_node must be a nonblank string"):
        convert_to_vibe_format(blank_endpoint)


def test_vibe_rich_ingest_rejects_incomplete_envelope() -> None:
    """A vibe envelope missing required top-level sections is rejected, never partial."""
    raw = _load_90a1d5()

    for field in ("source", "requirements", "inputs", "edges"):
        partial = deepcopy(raw)
        del partial[field]
        with pytest.raises(ValueError):
            convert_to_vibe_format(partial)

    bad_outputs = deepcopy(raw)
    bad_outputs["outputs"] = "not-a-list"
    with pytest.raises(ValueError, match="outputs.*must be a list"):
        convert_to_vibe_format(bad_outputs)

    bad_strict = deepcopy(raw)
    bad_strict["strict_types"] = "yes"
    with pytest.raises(ValueError, match="strict_types must be a boolean"):
        convert_to_vibe_format(bad_strict)


# ═══════════════════════════════════════════════════════════════════════════════
# P5 — VibeWorkflow.to_envelope / from_envelope (one writer, one fail-closed reader)
# ═══════════════════════════════════════════════════════════════════════════════


def test_to_envelope_from_envelope_round_trip_90a1d5() -> None:
    """to_envelope(from_envelope(90a1d5)) preserves 15/10/15 uids/modes; compile stays 2."""
    from vibecomfy.workflow import FORMAT_VERSION, VibeWorkflow, from_envelope

    raw = _load_90a1d5()
    wf = from_envelope(raw)
    via_convert = convert_to_vibe_format(raw)
    assert set(wf.nodes) == set(via_convert.nodes)
    assert len(wf.nodes) == 15
    assert len(wf.edges) == 10
    assert {node.uid for node in wf.nodes.values()} == {
        node.uid for node in via_convert.nodes.values()
    }
    assert all(node.uid.strip() for node in wf.nodes.values())
    assert dict(Counter(node.metadata.get("mode") for node in wf.nodes.values())) == {4: 9, 0: 6}

    envelope = wf.to_envelope()
    assert envelope["vibecomfy_format_version"] == FORMAT_VERSION
    assert "compiled_api" not in envelope
    assert len(envelope["nodes"]) == 15
    assert len(envelope["edges"]) == 10

    wf2 = VibeWorkflow.from_envelope(envelope)
    assert len(wf2.nodes) == 15
    assert len(wf2.edges) == 10
    assert {node.uid for node in wf2.nodes.values()} == {node.uid for node in wf.nodes.values()}
    assert dict(Counter(node.metadata.get("mode") for node in wf2.nodes.values())) == {4: 9, 0: 6}
    for nid, node in wf2.nodes.items():
        original = raw["nodes"][nid]
        assert node.uid == original["uid"]
        assert node.metadata["_ui"] == original["metadata"]["_ui"]
        assert node.inputs == original["inputs"]
        assert node.widgets == original["widgets"]
    assert len(wf2.compile("api")) == 2
    assert set(wf2.compile("api")) == {"3", "17"}


def test_from_envelope_hand_built_old_style_without_compiled_api() -> None:
    """A hand-built (old-style) envelope without compiled_api still decodes losslessly."""
    from vibecomfy.workflow import VibeWorkflow

    envelope = {
        "id": "hand-built",
        "vibecomfy_format_version": "1.0",
        "source": {"id": "hand-built", "source_type": "vibe", "path": None, "provenance": {}},
        "requirements": {
            "models": [],
            "custom_nodes": [],
            "missing_models": [],
            "missing_nodes": [],
            "unsupported": [],
        },
        "nodes": {
            "1": {
                "id": "1",
                "class_type": "CheckpointLoaderSimple",
                "pack": None,
                "inputs": {"ckpt_name": "model.safetensors"},
                "widgets": {},
                "metadata": {"_ui": {"mode": 0}, "mode": 0},
                "uid": "uid-loader",
            },
            "2": {
                "id": "2",
                "class_type": "PreviewImage",
                "pack": None,
                "inputs": {},
                "widgets": {},
                "metadata": {"_ui": {"mode": 4}, "mode": 4},
                "uid": "uid-preview",
            },
        },
        "edges": [
            {
                "from_node": "1",
                "from_output": "MODEL",
                "to_node": "2",
                "to_input": "images",
            }
        ],
        "inputs": {},
        "outputs": [{"node_id": "2", "output_type": "IMAGE"}],
        "metadata": {"note": "old-style"},
        "strict_types": False,
    }
    assert "compiled_api" not in envelope

    wf = VibeWorkflow.from_envelope(envelope)
    assert len(wf.nodes) == 2
    assert len(wf.edges) == 1
    assert wf.nodes["1"].uid == "uid-loader"
    assert wf.nodes["1"].inputs["ckpt_name"] == "model.safetensors"
    assert wf.nodes["1"].mode == 0
    assert wf.nodes["2"].mode == 4
    assert wf.nodes["2"].metadata["mode"] == 4
    assert wf.nodes["2"].metadata["_ui"]["mode"] == 4
    assert wf.outputs[0].node_id == "2"
    written = wf.to_envelope()
    assert "compiled_api" not in written
    assert written["nodes"]["1"]["uid"] == "uid-loader"
    assert written["nodes"]["2"]["mode"] == 4
    assert written["nodes"]["2"]["metadata"]["_ui"]["mode"] == 4


def test_from_envelope_fails_closed_on_malformed_input() -> None:
    """from_envelope raises on malformed input; it never returns a partial graph."""
    from vibecomfy.workflow import VibeWorkflow

    good = {
        "id": "closed",
        "source": {"id": "closed"},
        "requirements": {},
        "nodes": {
            "1": {
                "id": "1",
                "class_type": "PreviewImage",
                "inputs": {},
                "widgets": {},
                "metadata": {},
                "uid": "uid-1",
            }
        },
        "edges": [],
        "inputs": {},
        "outputs": [],
    }
    assert len(VibeWorkflow.from_envelope(good).nodes) == 1

    blank_uid = deepcopy(good)
    blank_uid["nodes"]["2"] = {
        "id": "2",
        "class_type": "PreviewImage",
        "inputs": {},
        "widgets": {},
        "metadata": {},
        "uid": "",
    }
    with pytest.raises(ValueError, match="uid must be a nonblank string"):
        VibeWorkflow.from_envelope(blank_uid)

    mixed_node = deepcopy(good)
    mixed_node["nodes"]["2"] = "not-a-mapping"
    with pytest.raises(ValueError, match="node entries must be mappings"):
        VibeWorkflow.from_envelope(mixed_node)

    missing_source = deepcopy(good)
    del missing_source["source"]
    with pytest.raises(ValueError, match="source"):
        VibeWorkflow.from_envelope(missing_source)

    missing_requirements = deepcopy(good)
    del missing_requirements["requirements"]
    with pytest.raises(ValueError, match="requirements"):
        VibeWorkflow.from_envelope(missing_requirements)

    not_an_object = ["not", "an", "envelope"]
    with pytest.raises(ValueError, match="must be a JSON object"):
        VibeWorkflow.from_envelope(not_an_object)  # type: ignore[arg-type]


# ═══════════════════════════════════════════════════════════════════════════════
# P6 — named importers (from_envelope / from_ui / from_api)
# ═══════════════════════════════════════════════════════════════════════════════


def test_named_from_envelope_preserves_90a1d5() -> None:
    """The public ingest from_envelope door is lossless on the 90a1d5 fixture."""
    from vibecomfy.ingest import from_envelope
    from vibecomfy.ingest.normalize import convert_to_vibe_format

    raw = _load_90a1d5()
    wf = from_envelope(raw)
    via_convert = convert_to_vibe_format(raw)
    assert len(wf.nodes) == 15
    assert len(wf.edges) == 10
    assert set(wf.nodes) == set(via_convert.nodes)
    assert {node.uid for node in wf.nodes.values()} == {
        node.uid for node in via_convert.nodes.values()
    }
    assert dict(Counter(node.metadata.get("mode") for node in wf.nodes.values())) == {4: 9, 0: 6}
    assert len(wf.compile("api")) == 2
    assert set(wf.compile("api")) == {"3", "17"}


def _ir_projection(workflow) -> dict:
    return {
        "ids": sorted(workflow.nodes),
        "classes": {nid: node.class_type for nid, node in workflow.nodes.items()},
        "uids": {nid: node.uid for nid, node in workflow.nodes.items()},
        "inputs": {nid: node.inputs for nid, node in workflow.nodes.items()},
        "widgets": {nid: node.widgets for nid, node in workflow.nodes.items()},
        "edges": [
            (edge.from_node, edge.from_output, edge.to_node, edge.to_input)
            for edge in workflow.edges
        ],
    }


def test_from_ui_matches_convert_on_ui_fixture() -> None:
    raw = json.loads(
        (Path(__file__).parent / "fixtures/reorganise/simple_text_to_image.json").read_text(
            encoding="utf-8"
        )
    )
    assert _ir_projection(from_ui(raw)) == _ir_projection(convert_to_vibe_format(raw))


def test_from_api_matches_convert_on_api_from_ui_fixture() -> None:
    raw = json.loads(
        (Path(__file__).parent / "fixtures/reorganise/simple_text_to_image.json").read_text(
            encoding="utf-8"
        )
    )
    api = normalize_to_api(raw, use_comfy_converter=False)
    assert _ir_projection(from_api(api)) == _ir_projection(convert_to_vibe_format(api))
