"""T14a/T14c — compile('api') invariance and bypass-equivalence tests.

For graphs with NO bypassed/muted nodes (`_get_node_mode` returns 0 for every
node), `compile('api')` must be byte-identical regardless of whether
`vibecomfy_uid` is stamped on the `VibeNode` and regardless of whether
furniture (`pos`, `size`, `properties`) is present in `metadata['_ui']`. The
fast path in `_resolve_bypass_edges` (workflow.py:951) returns edges unchanged
when `dropped_ids` is empty, and `compile('api')` never reads `node.uid` or
`metadata['_ui']` — this test pins that contract.
"""

from __future__ import annotations

import copy
import json
import os
from pathlib import Path

import pytest

from vibecomfy import load_workflow_any
from vibecomfy.workflow import _compute_dropped_bypassed_ids


# ---------------------------------------------------------------------------
# T14c — known divergences between vibecomfy compile('api') and ComfyUI
# convert_ui_to_api for bypass/mute graphs.
#
# Each entry: (family_key, description)
# These are structural differences that are intentional or accepted debt.
# ---------------------------------------------------------------------------
_KNOWN_XFAIL_FAMILIES: dict[str, str] = {
    "_meta_field": (
        "ComfyUI convert_ui_to_api adds a '_meta': {'title': ...} field to every "
        "node in the output; vibecomfy compile('api') does not. This is a cosmetic "
        "metadata annotation (used by the ComfyUI frontend for display) and has no "
        "effect on execution semantics. Documented in docs/hiddenswitch_incompatibilities.md."
    ),
}


def _canonical(api: dict) -> str:
    return json.dumps(api, sort_keys=True, indent=None, separators=(",", ":"))


@pytest.mark.parametrize(
    "ready_id",
    [
        "image/z_image",
        "image/flux2_klein_4b_t2i",
    ],
)
def test_compile_byte_identical_with_or_without_uid_and_furniture(ready_id: str) -> None:
    wf = load_workflow_any(ready_id)

    # Precondition: no bypassed/muted nodes — the invariance only holds here.
    dropped, _bypassed = _compute_dropped_bypassed_ids(wf.nodes)
    assert dropped == frozenset(), (
        f"{ready_id} has dropped (muted/bypassed) nodes; invariance test requires none."
    )

    baseline = _canonical(wf.compile("api"))

    # Stamp synthetic uid + furniture on every node.
    for node_id, node in wf.nodes.items():
        node.uid = f"uid-{node_id}"
        ui = node.metadata.get("_ui")
        if not isinstance(ui, dict):
            ui = {}
            node.metadata["_ui"] = ui
        ui["pos"] = [100.0 + int(node_id) * 10, 200.0]
        ui["size"] = [220.0, 110.0]
        props = ui.get("properties")
        if not isinstance(props, dict):
            props = {}
            ui["properties"] = props
        props["vibecomfy_uid"] = node.uid
        props["vibecomfy_id"] = f"{node.class_type}_{node_id}"

    stamped = _canonical(wf.compile("api"))

    assert stamped == baseline, (
        f"compile('api') for {ready_id} changed after uid/furniture stamping "
        "(no bypassed/muted nodes present, so the output must be byte-identical)."
    )


# ---------------------------------------------------------------------------
# T14c — bypass-equivalence against convert_ui_to_api (gated: VIBECOMFY_COMFY_SMOKE=1)
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).resolve().parents[1]


def _strip_meta(api: dict) -> dict:
    """Remove the '_meta' annotation that ComfyUI adds but vibecomfy omits."""
    return {k: {ik: iv for ik, iv in v.items() if ik != "_meta"} for k, v in api.items()}


def _compare_api_dicts(vc_api: dict, comfy_api: dict) -> list[str]:
    """Return a list of divergence messages (excluding known _meta_field xfails)."""
    divergences = []

    vc_keys = set(vc_api.keys())
    comfy_keys_stripped = set(_strip_meta(comfy_api).keys())

    if vc_keys != comfy_keys_stripped:
        only_vc = vc_keys - comfy_keys_stripped
        only_comfy = comfy_keys_stripped - vc_keys
        if only_vc:
            divergences.append(f"Node(s) only in vibecomfy output: {sorted(only_vc)}")
        if only_comfy:
            divergences.append(f"Node(s) only in comfy output: {sorted(only_comfy)}")

    comfy_stripped = _strip_meta(comfy_api)
    for node_id in sorted(vc_keys & comfy_keys_stripped):
        vc_node = json.dumps(vc_api[node_id], sort_keys=True)
        comfy_node = json.dumps(comfy_stripped[node_id], sort_keys=True)
        if vc_node != comfy_node:
            divergences.append(
                f"Node {node_id!r} inputs differ:\n"
                f"  vibecomfy: {vc_node[:200]}\n"
                f"  comfy:     {comfy_node[:200]}"
            )

    return divergences


@pytest.mark.parametrize(
    "corpus_path,mode_label",
    [
        # mode 4 (bypass): flux2_klein_4b_t2i has 2 bypass nodes (ids 77, 78)
        (
            "workflow_corpus/official/image/flux2_klein_4b_t2i.json",
            "bypass_mode4",
        ),
        # mode 2 (mute): z_image with first non-note node set to mode 2
        (
            "workflow_corpus/official/image/z_image.json",
            "mute_mode2",
        ),
    ],
)
def test_bypass_equivalence_against_convert_ui_to_api(
    corpus_path: str, mode_label: str
) -> None:
    """T14c — vibecomfy compile('api') must be structurally equivalent to
    ComfyUI convert_ui_to_api for bypass (mode 4) and mute (mode 2) graphs.

    Gated on VIBECOMFY_COMFY_SMOKE=1. Known divergences are listed in
    _KNOWN_XFAIL_FAMILIES and documented in docs/hiddenswitch_incompatibilities.md.

    The comparison ignores the '_meta' annotation (see _KNOWN_XFAIL_FAMILIES).
    Any other divergence is a test failure that must be diagnosed and either
    fixed or added to _KNOWN_XFAIL_FAMILIES with a documented rationale.
    """
    import warnings

    if os.environ.get("VIBECOMFY_COMFY_SMOKE") != "1":
        pytest.skip("bypass-equivalence smoke gate is opt-in (set VIBECOMFY_COMFY_SMOKE=1)")

    from vibecomfy.comfy_backend import ensure_nodes
    if not ensure_nodes():
        pytest.skip("vendored ComfyUI not available (vendor/ComfyUI submodule uninitialized)")

    comfy_convert = pytest.importorskip(
        "comfy.component_model.workflow_convert"
    ).convert_ui_to_api

    from vibecomfy.ingest.normalize import convert_to_vibe_format

    raw_path = _REPO_ROOT / corpus_path
    raw = json.loads(raw_path.read_text(encoding="utf-8"))

    # For the mute (mode 2) fixture: set the first non-metadata node to mode 2
    if mode_label == "mute_mode2":
        raw = copy.deepcopy(raw)
        for node in raw["nodes"]:
            if node.get("type") not in ("MarkdownNote", "Note"):
                node["mode"] = 2
                break

    # vibecomfy path: UI JSON → IR → compile('api')
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        wf = convert_to_vibe_format(raw)
    vc_api = wf.compile("api")

    # ComfyUI path: UI JSON → convert_ui_to_api
    comfy_api = comfy_convert(raw)

    divergences = _compare_api_dicts(vc_api, comfy_api)

    assert not divergences, (
        f"[{mode_label}] {len(divergences)} divergence(s) between vibecomfy "
        f"compile('api') and ComfyUI convert_ui_to_api (after stripping known "
        f"_meta_field xfail):\n\n" + "\n\n".join(divergences) + "\n\n"
        "To accept a new divergence: add it to _KNOWN_XFAIL_FAMILIES in "
        "tests/test_compile_invariance.py and document it in "
        "docs/hiddenswitch_incompatibilities.md."
    )
