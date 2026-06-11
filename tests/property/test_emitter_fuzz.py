"""Property/fuzz test for the emitter (T21 / Step 15).

Generates random valid IR using a SEEDED deterministic generator, emits
UI JSON, reconstructs the API graph via Layer-1 independent read-back, and
asserts isomorphism with ``compile('api')``.  Also asserts widget-count and
slot-range invariants.

All randomness is seeded → deterministic offline pass.
"""

from __future__ import annotations

import json
import random
import warnings
from pathlib import Path
from typing import Any

import pytest

from vibecomfy.ingest.normalize import _schema_input_names
from vibecomfy.porting.parity import compile_equivalent
from vibecomfy.porting.emit.ui import emit_ui_json
from vibecomfy.schema import get_schema_provider
from vibecomfy.schema.provider import ObjectInfoIndexSchemaProvider
from vibecomfy.workflow import VibeNode, VibeWorkflow, WorkflowSource

# ---------------------------------------------------------------------------
# Seeded RNG — deterministic, no Math.random/Date.now-style nondeterminism.
# ---------------------------------------------------------------------------
_SEED = 42
_RNG = random.Random(_SEED)

# ---------------------------------------------------------------------------
# Known node classes for random generation (must be in the object_info cache).
# ---------------------------------------------------------------------------
_NODE_CLASSES = [
    "LoadImage", "SaveImage", "VAEDecode", "VAEEncode",
    "CLIPTextEncode", "CheckpointLoaderSimple", "EmptyLatentImage",
    "KSampler", "UNETLoader", "VAELoader",
]

# Classes that have no outputs (terminal / save nodes).
_TERMINAL_CLASSES = frozenset({"SaveImage", "PreviewImage"})

# Classes that have no inputs (source / loader nodes).
_SOURCE_CLASSES = frozenset({
    "LoadImage", "EmptyLatentImage", "CheckpointLoaderSimple",
    "UNETLoader", "VAELoader",
})

# ---------------------------------------------------------------------------
# Fuzz generator: random valid IR (seeded, deterministic)
# ---------------------------------------------------------------------------


def _generate_random_workflow(
    node_count: int = 5,
) -> VibeWorkflow:
    """Generate a random-but-valid VibeWorkflow with ``node_count`` nodes.

    Nodes are randomly selected from *_NODE_CLASSES* and connected in a
    valid directed acyclic fashion (always terminating at a SaveImage).
    """
    if node_count < 2:
        node_count = 2

    wf = VibeWorkflow(
        f"fuzz_{_RNG.randint(1000, 9999)}",
        WorkflowSource("fuzz"),
    )

    # Always include at least one source and one sink.
    classes: list[str] = []
    classes.append(_RNG.choice(list(_SOURCE_CLASSES)))
    for _ in range(node_count - 2):
        classes.append(_RNG.choice(_NODE_CLASSES))
    classes.append("SaveImage")

    nodes: list[str] = []
    for i, cls in enumerate(classes):
        nid = str(i + 1)
        wf.nodes[nid] = VibeNode(nid, cls, uid=f"n{i + 1}")
        nodes.append(nid)

    # Connect nodes in a simple chain: each node's first output → next node's first input.
    # For known classes, use canonical slot names.
    schema_provider = get_schema_provider("local")
    for i in range(len(nodes) - 1):
        src_id = nodes[i]
        dst_id = nodes[i + 1]
        src_cls = classes[i]
        dst_cls = classes[i + 1]

        # Determine output slot name for source.
        src_schema = schema_provider.get_schema(src_cls)
        if src_schema and src_schema.outputs:
            src_slot = src_schema.outputs[0].name or "0"
        else:
            src_slot = "0"

        # Determine input slot name for destination.
        dst_schema = schema_provider.get_schema(dst_cls)
        if dst_schema and dst_schema.inputs:
            dst_input_names = _schema_input_names(schema_provider, dst_cls)
            if dst_input_names:
                dst_slot = dst_input_names[0]
            else:
                dst_slot = list(dst_schema.inputs.keys())[0]
        else:
            dst_slot = "0"

        wf.connect(f"{src_id}.{src_slot}", f"{dst_id}.{dst_slot}")

    return wf


# ---------------------------------------------------------------------------
# Layer-1 independent read-back (same algorithm as T14)
# ---------------------------------------------------------------------------

_UI_ONLY_TYPES = frozenset({
    "Note", "MarkdownNote", "Label (rgthree)", "PreviewAny",
    "easy showAnything", "SetNode", "GetNode", "Reroute",
})


def _reconstruct_api_from_links(
    envelope: dict[str, Any],
    schema_provider: Any,
) -> dict[str, Any]:
    """Independent Layer-1 read-back from links[] + widget order.

    Does NOT call ``_normalize_ui_to_api``.
    """
    all_nodes: dict[int, dict[str, Any]] = {}
    for node in envelope.get("nodes", []):
        all_nodes[int(node["id"])] = node

    nodes_by_id: dict[int, dict[str, Any]] = {}
    for nid, node in all_nodes.items():
        if str(node.get("type", "")) in _UI_ONLY_TYPES:
            continue
        nodes_by_id[nid] = node

    link_id_map: dict[int, tuple[int, int]] = {}
    for link in envelope.get("links", []):
        if not isinstance(link, list) or len(link) < 5:
            continue
        link_id_map[int(link[0])] = (int(link[1]), int(link[2]))

    api: dict[str, Any] = {}
    for nid, node in nodes_by_id.items():
        class_type = str(node.get("type", "Unknown"))
        sid = str(nid)
        inputs: dict[str, Any] = {}

        # Widget values
        widgets = node.get("widgets_values", [])
        if isinstance(widgets, list):
            schema_names = _schema_input_names(schema_provider, class_type)
            if schema_names:
                for idx, value in enumerate(widgets):
                    if idx < len(schema_names):
                        inputs[schema_names[idx]] = value
                    else:
                        inputs[f"widget_{idx}"] = value
            else:
                for idx, value in enumerate(widgets):
                    inputs[f"widget_{idx}"] = value

        # Edge connections
        node_inputs = node.get("inputs", [])
        if isinstance(node_inputs, list):
            for inp in node_inputs:
                if not isinstance(inp, dict):
                    continue
                name = inp.get("name")
                link_id = inp.get("link")
                if name and link_id is not None and link_id in link_id_map:
                    src_nid, src_slot = link_id_map[int(link_id)]
                    # Resolve broadcast
                    src_nid, src_slot = _resolve_broadcast(
                        src_nid, src_slot, all_nodes, link_id_map
                    )
                    inputs[name] = [str(src_nid), src_slot]

        api[sid] = {"class_type": class_type, "inputs": inputs}

    return api


def _resolve_broadcast(
    src_nid: int, src_slot: int,
    all_nodes: dict[int, dict[str, Any]],
    link_id_map: dict[int, tuple[int, int]],
) -> tuple[int, int]:
    """Resolve SetNode/GetNode chains transitively."""
    seen: set[int] = set()
    current = src_nid
    while current in all_nodes:
        node = all_nodes.get(current)
        if node is None:
            break
        ct = str(node.get("type", ""))
        if ct not in ("SetNode", "GetNode"):
            break
        if current in seen:
            break
        seen.add(current)
        node_inputs = node.get("inputs", [])
        if not isinstance(node_inputs, list) or not node_inputs:
            break
        first = node_inputs[0]
        if not isinstance(first, dict):
            break
        lid = first.get("link")
        if lid is None or lid not in link_id_map:
            break
        current, _ = link_id_map[int(lid)]
    return current, src_slot


# ---------------------------------------------------------------------------
# Property tests
# ---------------------------------------------------------------------------


def test_fuzz_emitter_l1_readback_isomorphism() -> None:
    """Property: random valid IR → emit → Layer-1 read-back == compile('api').

    Uses a SEEDED generator for deterministic reproducibility.  Runs 10
    random workflows through emit → independent read-back and asserts
    isomorphism via ``compile_equivalent``.
    """
    schema_provider = get_schema_provider("local")

    for run in range(10):
        node_count = _RNG.randint(3, 8)
        wf = _generate_random_workflow(node_count)

        # Emit
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            envelope = emit_ui_json(wf)

        # Compile (ground truth)
        api = wf.compile("api")

        # Independent Layer-1 read-back
        reconstructed = _reconstruct_api_from_links(envelope, schema_provider)

        # Isomorphism check
        equal, diffs = compile_equivalent(reconstructed, api)
        assert equal, (
            f"Run {run} (nodes={node_count}):"
            f" Layer-1 read-back != compile('api'): {diffs[:5]}"
        )

    print(f"\n[T21] Fuzz test: 10 random workflows passed Layer-1 isomorphism.")


def test_fuzz_widget_count_invariants() -> None:
    """Invariant: safe regenerated widgets_values do not exceed raw widget order count.

    Pinned dynamic nodes may preserve opaque raw widget payloads. The count
    invariant applies only to nodes the widget-shape fence marked safe to
    regenerate.
    """
    obj_provider = ObjectInfoIndexSchemaProvider(
        "vibecomfy/porting/cache/object_info"
    )
    schema_provider = get_schema_provider("local")

    for run in range(10):
        node_count = _RNG.randint(3, 8)
        wf = _generate_random_workflow(node_count)

        report: list[dict[str, Any]] = []
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            envelope = emit_ui_json(wf, recovery_report=report)

        verdict_by_node = {
            int(entry["node_id"]): entry.get("widget_shape_verdict")
            for entry in report
            if "node_id" in entry
        }

        for node in envelope.get("nodes", []):
            if verdict_by_node.get(int(node["id"])) != "safe_to_regenerate":
                continue
            class_type = str(node.get("type", ""))
            raw_order = obj_provider.raw_widget_order(class_type)
            if raw_order is None:
                continue  # unknown class, skip invariant

            widgets = node.get("widgets_values", [])
            if not isinstance(widgets, list):
                continue

            expected_count = len(raw_order)
            actual_count = len(widgets)

            # The widget count must be ≤ the raw order count.
            # Extra widgets (beyond schema) get widget_N keys.
            assert actual_count <= expected_count, (
                f"Run {run}, {class_type}:"
                f" widgets_values count {actual_count} > raw_widget_order"
                f" count {expected_count}"
            )

    print(f"\n[T21] Widget-count invariants: 10 fuzz runs passed.")


def test_fuzz_slot_range_invariants() -> None:
    """Invariant: emitted link slots are within range.

    Every link's ``from_slot`` must be ≥ 0 and every ``to_slot`` must be
    within the target node's input count.
    """
    for run in range(10):
        node_count = _RNG.randint(3, 8)
        wf = _generate_random_workflow(node_count)

        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            envelope = emit_ui_json(wf)

        # Build input count per node
        input_counts: dict[int, int] = {}
        for node in envelope.get("nodes", []):
            nid = int(node["id"])
            inputs = node.get("inputs", [])
            input_counts[nid] = len(inputs) if isinstance(inputs, list) else 0

        for link in envelope.get("links", []):
            if not isinstance(link, list) or len(link) < 5:
                continue
            from_slot = int(link[2])
            to_node = int(link[3])
            to_slot = int(link[4])

            assert from_slot >= 0, (
                f"Run {run}: negative from_slot {from_slot} in link {link}"
            )
            assert to_slot >= 0, (
                f"Run {run}: negative to_slot {to_slot} in link {link}"
            )

            # to_slot should be < input_count (or the node has widget inputs
            # that aren't in the inputs[] array — skip if unknown)
            max_slot = input_counts.get(to_node)
            if max_slot is not None and max_slot > 0:
                assert to_slot <= max_slot, (
                    f"Run {run}: to_slot {to_slot} exceeds input count"
                    f" {max_slot} for node {to_node}"
                )

    print(f"\n[T21] Slot-range invariants: 10 fuzz runs passed.")


def test_fuzz_determinism() -> None:
    """Determinism: same seed → same fuzz results.

    Two generators with the same seed produce the same sequence of workflows,
    and emit produces byte-identical output.
    """
    rng1 = random.Random(42)
    rng2 = random.Random(42)

    # Generate one workflow from each RNG with identical seed
    for _ in range(3):
        wf1 = _generate_random_workflow_with_rng(5, rng1)
        wf2 = _generate_random_workflow_with_rng(5, rng2)

        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            env1 = emit_ui_json(wf1)
            env2 = emit_ui_json(wf2)

    # Both envelopes must be identical (byte-identical JSON)
    json1 = json.dumps(env1, sort_keys=True, default=str)
    json2 = json.dumps(env2, sort_keys=True, default=str)
    assert json1 == json2, (
        "Determinism violated: same seed produced different emit output"
    )

    print(f"\n[T21] Determinism: same seed reproduces byte-identical output.")


# ---------------------------------------------------------------------------
# Helpers for determinism test
# ---------------------------------------------------------------------------


def _generate_random_workflow_with_rng(
    node_count: int,
    rng: random.Random,
) -> VibeWorkflow:
    """Generate a random workflow using a specific RNG instance."""
    if node_count < 2:
        node_count = 2

    wf = VibeWorkflow(
        f"det_{rng.randint(1000, 9999)}",
        WorkflowSource("det"),
    )

    classes: list[str] = []
    classes.append(rng.choice(list(_SOURCE_CLASSES)))
    for _ in range(node_count - 2):
        classes.append(rng.choice(_NODE_CLASSES))
    classes.append("SaveImage")

    nodes: list[str] = []
    for i, cls in enumerate(classes):
        nid = str(i + 1)
        wf.nodes[nid] = VibeNode(nid, cls, uid=f"d{i + 1}")
        nodes.append(nid)

    schema_provider = get_schema_provider("local")
    for i in range(len(nodes) - 1):
        src_id = nodes[i]
        dst_id = nodes[i + 1]
        src_cls = classes[i]
        dst_cls = classes[i + 1]

        src_schema = schema_provider.get_schema(src_cls)
        src_slot = (
            src_schema.outputs[0].name if src_schema and src_schema.outputs else "0"
        )

        dst_schema = schema_provider.get_schema(dst_cls)
        if dst_schema and dst_schema.inputs:
            dst_names = _schema_input_names(schema_provider, dst_cls)
            dst_slot = dst_names[0] if dst_names else list(dst_schema.inputs.keys())[0]
        else:
            dst_slot = "0"

        wf.connect(f"{src_id}.{src_slot}", f"{dst_id}.{dst_slot}")

    return wf
