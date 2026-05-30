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

import pytest


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


pytestmark = pytest.mark.skipif(
    not _comfy_available(),
    reason="vendored ComfyUI nodes not available for guard_emit oracle",
)


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
