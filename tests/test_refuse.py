"""Tests for the M5 Step 16 refusal-spine ``guard_emit``.

The spike T4 reproduction (``test_refuses_control_after_generate_slot_drop``)
asserts that dropping the ``control_after_generate`` slot from a KSampler
``widgets_values`` array — producing a 6-element list that left-shifts every
following widget — is detected and refused.

These tests need the vendored ComfyUI node mappings to drive
``convert_ui_to_api``.  When the vendored backend is not available, the suite
skips rather than fails — matching the existing convention used by the M3
``test_layer3_corpus_wide`` gate.
"""
from __future__ import annotations

import builtins
import importlib
import json
import sys
from enum import Enum
from types import SimpleNamespace

import pytest


def _drop_vibecomfy_modules() -> dict[str, object]:
    removed: dict[str, object] = {}
    for module_name in list(sys.modules):
        if module_name == "vibecomfy" or module_name.startswith("vibecomfy."):
            module = sys.modules.pop(module_name, None)
            if module is not None:
                removed[module_name] = module
    return removed


def _restore_vibecomfy_modules(removed: dict[str, object]) -> None:
    for module_name in list(sys.modules):
        if module_name == "vibecomfy" or module_name.startswith("vibecomfy."):
            sys.modules.pop(module_name, None)
    sys.modules.update(removed)


def _comfy_available() -> bool:
    try:
        from vibecomfy.comfy_backend import ensure_nodes

        if not ensure_nodes():
            return False
        from comfy.component_model.workflow_convert import convert_ui_to_api  # noqa: F401
        from comfy.nodes_context import get_nodes

        nodes = get_nodes()
        return "KSampler" in nodes.NODE_CLASS_MAPPINGS
    except Exception:
        return False


def _require_comfy() -> None:
    if not _comfy_available():
        pytest.skip("vendored ComfyUI nodes not available for guard_emit oracle")


def test_refused_emit_import_and_construction_are_side_effect_light(monkeypatch) -> None:
    """Importing/constructing RefusedEmit must not adopt ComfyUI or load converter."""
    repo_root = str(__file__).split("/tests/test_refuse.py", maxsplit=1)[0]
    monkeypatch.syspath_prepend(repo_root)
    removed_modules = _drop_vibecomfy_modules()

    real_import = builtins.__import__

    def guarded_import(name, globals=None, locals=None, fromlist=(), level=0):
        if name == "vibecomfy.comfy_backend" or name.startswith("comfy."):
            raise AssertionError(f"unexpected refusal import side effect: {name}")
        return real_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", guarded_import)

    try:
        module = importlib.import_module("vibecomfy.porting.refuse")
        exc = module.RefusedEmit("widget-shape refusal", {"uid": {"axis": "diff"}})

        assert exc.reason == "widget-shape refusal"
        assert exc.diff == {"uid": {"axis": "diff"}}
        assert "vibecomfy.comfy_backend" not in sys.modules
    finally:
        _restore_vibecomfy_modules(removed_modules)


def test_widget_shape_refusal_diff_is_node_keyed_and_json_tolerant(monkeypatch) -> None:
    """Widget-shape refusal details are machine-readable without ComfyUI imports."""
    repo_root = str(__file__).split("/tests/test_refuse.py", maxsplit=1)[0]
    monkeypatch.syspath_prepend(repo_root)
    removed_modules = _drop_vibecomfy_modules()

    real_import = builtins.__import__

    def guarded_import(name, globals=None, locals=None, fromlist=(), level=0):
        if name == "vibecomfy.comfy_backend" or name.startswith("comfy."):
            raise AssertionError(f"unexpected widget-shape refusal import side effect: {name}")
        return real_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", guarded_import)

    class _Decision(str, Enum):
        REFUSE = "refuse"

    class _Reason(str, Enum):
        OVERFLOW = "overflow"
        WIDGET_DELTA = "widget_delta"

    evidence = SimpleNamespace(
        node_id="7",
        class_type="DynamicRows",
        schema_less=False,
        confidence=1.0,
        raw_widget_count=4,
        candidate_widget_count=4,
        schema_widget_count=2,
        raw_widget_shape="list",
        has_dict_rows=False,
        overflow=True,
        provider="test_provider",
    )
    verdict = SimpleNamespace(
        node_id="7",
        class_type="DynamicRows",
        decision=_Decision.REFUSE,
        reasons=(_Reason.OVERFLOW, _Reason.WIDGET_DELTA),
        safe_to_regenerate=False,
        pin_opaque=False,
        refuse=True,
        evidence=evidence,
        field_delta={"widget_1": ("old", "new")},
        link_delta={},
    )

    try:
        module = importlib.import_module("vibecomfy.porting.refuse")
        exc = module.refused_widget_shape([verdict])

        assert exc.reason == "widget shape refused: 1 node(s) cannot be emitted safely"
        assert exc.diff["7"]["axis"] == "widget_shape"
        assert exc.diff["7"]["node_id"] == "7"
        assert exc.diff["7"]["class_type"] == "DynamicRows"
        assert exc.diff["7"]["reason"] == "overflow"
        assert exc.diff["7"]["reasons"] == ["overflow", "widget_delta"]
        assert exc.diff["7"]["details"]["decision"] == "refuse"
        assert exc.diff["7"]["details"]["evidence"]["schema_widget_count"] == 2
        assert exc.diff["7"]["details"]["field_delta"]["widget_1"] == ["old", "new"]
        assert json.loads(json.dumps({"refused_emit": exc.diff}))["refused_emit"]["7"][
            "reason"
        ] == "overflow"
        assert str(exc) == exc.reason
        assert "vibecomfy.comfy_backend" not in sys.modules
    finally:
        _restore_vibecomfy_modules(removed_modules)


def _ksampler_ui(widgets_values: list) -> dict:
    """Minimal UI graph: CheckpointLoader + EmptyLatent + 2x CLIPTextEncode + KSampler."""
    return {
        "version": 0.4,
        "nodes": [
            {
                "id": 1,
                "type": "CheckpointLoaderSimple",
                "pos": [0, 0],
                "size": [200, 100],
                "mode": 0,
                "order": 0,
                "outputs": [
                    {"name": "MODEL", "type": "MODEL", "links": [1]},
                    {"name": "CLIP", "type": "CLIP", "links": None},
                    {"name": "VAE", "type": "VAE", "links": None},
                ],
                "widgets_values": ["v1-5-pruned-emaonly.safetensors"],
                "properties": {
                    "vibecomfy_uid": "uid-loader",
                    "vibecomfy_id": "loader_0",
                },
            },
            {
                "id": 2,
                "type": "EmptyLatentImage",
                "pos": [0, 200],
                "size": [200, 100],
                "mode": 0,
                "order": 1,
                "outputs": [{"name": "LATENT", "type": "LATENT", "links": [2]}],
                "widgets_values": [512, 512, 1],
                "properties": {
                    "vibecomfy_uid": "uid-latent",
                    "vibecomfy_id": "latent_0",
                },
            },
            {
                "id": 3,
                "type": "CLIPTextEncode",
                "pos": [0, 400],
                "size": [200, 100],
                "mode": 0,
                "order": 2,
                "inputs": [{"name": "clip", "type": "CLIP", "link": None}],
                "outputs": [
                    {"name": "CONDITIONING", "type": "CONDITIONING", "links": [3]}
                ],
                "widgets_values": ["a cat"],
                "properties": {"vibecomfy_uid": "uid-pos", "vibecomfy_id": "pos_0"},
            },
            {
                "id": 4,
                "type": "CLIPTextEncode",
                "pos": [0, 600],
                "size": [200, 100],
                "mode": 0,
                "order": 3,
                "inputs": [{"name": "clip", "type": "CLIP", "link": None}],
                "outputs": [
                    {"name": "CONDITIONING", "type": "CONDITIONING", "links": [4]}
                ],
                "widgets_values": [""],
                "properties": {"vibecomfy_uid": "uid-neg", "vibecomfy_id": "neg_0"},
            },
            {
                "id": 5,
                "type": "KSampler",
                "pos": [400, 0],
                "size": [300, 200],
                "mode": 0,
                "order": 4,
                "inputs": [
                    {"name": "model", "type": "MODEL", "link": 1},
                    {"name": "positive", "type": "CONDITIONING", "link": 3},
                    {"name": "negative", "type": "CONDITIONING", "link": 4},
                    {"name": "latent_image", "type": "LATENT", "link": 2},
                ],
                "outputs": [
                    {"name": "LATENT", "type": "LATENT", "links": None}
                ],
                "widgets_values": widgets_values,
                "properties": {
                    "vibecomfy_uid": "uid-ksampler",
                    "vibecomfy_id": "ksampler_0",
                },
            },
        ],
        "links": [
            [1, 1, 0, 5, 0, "MODEL"],
            [2, 2, 0, 5, 3, "LATENT"],
            [3, 3, 0, 5, 1, "CONDITIONING"],
            [4, 4, 0, 5, 2, "CONDITIONING"],
        ],
        "groups": [],
        "config": {},
        "extra": {},
    }


def test_refuses_control_after_generate_slot_drop() -> None:
    """Spike T4 reproduction: dropping ``control_after_generate`` from the
    KSampler widgets_values shifts every following widget by one position,
    corrupting steps/cfg/sampler/scheduler/denoise. guard_emit must refuse.
    """
    _require_comfy()

    from vibecomfy.porting.refuse import RefusedEmit, guard_emit

    # 7-slot UI form: [seed, control_after_generate, steps, cfg, sampler, scheduler, denoise]
    original = _ksampler_ui([42, "fixed", 20, 8.0, "euler", "normal", 1.0])
    # Drop ``control_after_generate`` → 6 elements; widgets shift left.
    candidate = _ksampler_ui([42, 20, 8.0, "euler", "normal", 1.0])

    with pytest.raises(RefusedEmit) as exc_info:
        guard_emit(original, candidate, snapshot_delta={})

    assert "uid-ksampler" in exc_info.value.diff, (
        f"expected uid-ksampler in refusal diff, got {exc_info.value.diff!r}"
    )
    # The corruption is in the inputs axis (positional widget shift).
    assert "inputs" in exc_info.value.diff["uid-ksampler"]


def test_allows_clean_widget_edit_inside_delta() -> None:
    """A widget edit named in snapshot_delta is allowed through."""
    _require_comfy()

    from vibecomfy.porting.refuse import guard_emit

    original = _ksampler_ui([42, "fixed", 20, 8.0, "euler", "normal", 1.0])
    # Caller intentionally edits seed.
    candidate = _ksampler_ui([99, "fixed", 20, 8.0, "euler", "normal", 1.0])

    # widget_values_sig is in delta → inputs-axis change is allowed.
    guard_emit(
        original,
        candidate,
        snapshot_delta={
            "uid-ksampler": {
                "widget_values_sig": (
                    (("seed", "42"),),
                    (("seed", "99"),),
                )
            }
        },
    )


def test_allows_change_on_snapshot_absent_node() -> None:
    """Nodes uid-mismatched between original and candidate (i.e. not in the
    intersection scope set) are always allowed — the equivalent of being
    snapshot-absent from the guard's perspective.
    """
    _require_comfy()

    from vibecomfy.porting.refuse import guard_emit

    original = _ksampler_ui([42, "fixed", 20, 8.0, "euler", "normal", 1.0])
    candidate = _ksampler_ui([42, "fixed", 20, 8.0, "euler", "normal", 1.0])
    # Rename the KSampler uid in candidate → uid-mismatched (out of scope).
    for n in candidate["nodes"]:
        if n["id"] == 5:
            n["properties"]["vibecomfy_uid"] = "uid-different"
            # Edit a widget too — must NOT raise: original uid not in candidate
            # scope set.
            n["widgets_values"][0] = 999

    guard_emit(original, candidate, snapshot_delta={})
