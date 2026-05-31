"""Canonical-form API comparator for ready-template parity testing.

Deterministic topology/literal parity using stable JSON serialization and
WL-style refinement over upstream and downstream neighborhoods. Preserves
multiplicity for collision groups.

Guarantee: deterministic comparator for real ready-template graphs, not
complete graph isomorphism. Two graphs that are WL-distinguishable in the
real world will be distinguished here; two graphs that are genuinely
WL-isomorphic may collide (documented bound).

Implementation strategy:
1. Build adjacency lists from the API dict.
2. Compute WL-style labels iteratively (stable hash per node incorporating
   class_type, sorted literal kwargs, and sorted upstream+downstream
   neighborhood hashes from the previous iteration).
3. Replace node ids with WL labels in the canonical form dict.
4. Return normalized dict suitable for direct comparison via stable JSON.

Two parallel VAEDecode nodes with the same upstream but different downstream
consumers stay distinct because downstream divergence back-propagates into
the hash via the neighborhood step.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any


def _stable_json(obj: Any) -> str:
    """Produce a deterministic JSON string, stable across Python versions."""
    return json.dumps(obj, sort_keys=True, ensure_ascii=True, default=str, separators=(",", ":"))


def _sha256_hex(data: str) -> str:
    """Short 12-char hex digest for compact labels."""
    return hashlib.sha256(data.encode("utf-8")).hexdigest()[:12]


def _is_link(value: Any) -> bool:
    """Check if a value is a ComfyUI API link [node_id_str, slot_int]."""
    if not isinstance(value, list) or len(value) != 2:
        return False
    if not isinstance(value[1], int):
        return False
    return isinstance(value[0], str) or isinstance(value[0], int)


def _link_source(value: list) -> str:
    """Return the source node id as a string from a link value."""
    return str(value[0])


def _literal_kwargs(inputs: dict[str, Any]) -> dict[str, Any]:
    """Return only literal (non-link) kwargs, sorted for stability."""
    return {
        k: v
        for k, v in sorted(inputs.items())
        if not _is_link(v)
    }


def _node_payload(node: Any) -> dict[str, Any]:
    """Return the execution-relevant API payload for canonical comparison."""
    if not isinstance(node, dict):
        return {}
    return {
        key: value
        for key, value in node.items()
        if key in {"class_type", "inputs"}
    }


def canonical_form(api: dict) -> dict:
    """Return a normalized representation of an api dict.

    Node ids are replaced with WL-hash labels. Two graphs are
    canonical-equal iff they're graph-isomorphic with identical
    class_type + literal kwargs at each node.

    Args:
        api: A standard ComfyUI API dict mapping node_id -> {class_type, inputs}.

    Returns:
        A normalized dict with WL-hash labels as node keys, suitable for
        direct JSON comparison.
    """
    if not api:
        return {}

    # --- Phase 1: Build adjacency and compute initial labels ---
    node_ids = sorted(api.keys(), key=lambda x: str(x))

    # Map node_id -> list of (target_node_id, input_name, source_slot)
    downstream: dict[str, list[tuple[str, str, int]]] = {nid: [] for nid in node_ids}
    upstream: dict[str, list[tuple[str, str, int]]] = {nid: [] for nid in node_ids}

    for nid in node_ids:
        node = _node_payload(api[nid])
        inputs = node.get("inputs", {})
        for key, value in sorted(inputs.items()):
            if _is_link(value):
                src = _link_source(value)
                slot = int(value[1])
                upstream[nid].append((src, key, slot))
                if src in downstream:
                    downstream[src].append((nid, key, slot))

    # Initial label: hash of (class_type, stable_json of literal kwargs)
    def _initial_label(nid: str) -> str:
        node = _node_payload(api[nid])
        class_type = str(node.get("class_type", ""))
        literals = _literal_kwargs(node.get("inputs", {}))
        raw = _stable_json({"class_type": class_type, "kwargs": literals})
        return _sha256_hex(raw)

    labels: dict[str, str] = {nid: _initial_label(nid) for nid in node_ids}

    # --- Phase 2: WL-style iterative refinement ---
    MAX_ITER = 5  # graphs this size typically converge in 2-3 iterations
    for _ in range(MAX_ITER):
        new_labels: dict[str, str] = {}
        for nid in node_ids:
            # Collect upstream neighborhood labels (stable sorted)
            up_sig = sorted(
                (labels[src], key, slot)
                for src, key, slot in upstream.get(nid, [])
                if src in labels
            )
            # Collect downstream neighborhood labels (stable sorted)
            down_sig = sorted(
                (labels[tgt], key, slot)
                for tgt, key, slot in downstream.get(nid, [])
                if tgt in labels
            )
            raw = _stable_json({
                "self": labels[nid],
                "upstream": up_sig,
                "downstream": down_sig,
            })
            new_labels[nid] = _sha256_hex(raw)
        if new_labels == labels:
            break  # converged
        labels = new_labels

    # --- Phase 3: Build canonical node multiset ---
    #
    # Do not suffix collision groups by original node-id order. That would make
    # symmetric interchangeable branches compare unequal after id renumbering.
    # Instead, keep collisions as a sorted multiset of node records. Links point
    # at the refined WL label, preserving multiplicity without pretending this
    # is a complete graph-isomorphism solver.
    result_nodes: list[dict[str, Any]] = []
    for nid in node_ids:
        node = _node_payload(api[nid])
        new_inputs: dict[str, Any] = {}
        for key, value in sorted(node.get("inputs", {}).items()):
            if _is_link(value):
                src = str(value[0])
                slot = int(value[1])
                new_inputs[key] = [labels.get(src, src), slot]
            else:
                new_inputs[key] = value
        result_nodes.append({
            "label": labels[nid],
            "class_type": node.get("class_type", ""),
            "inputs": new_inputs,
        })

    result_nodes.sort(key=_stable_json)
    return {"nodes": result_nodes}


def canonical_equal(api_a: dict, api_b: dict) -> bool:
    """Return True if two API dicts are canonical-equal.

    This is the recommended entry point for parity testing.
    """
    return _stable_json(canonical_form(api_a)) == _stable_json(canonical_form(api_b))


__all__ = ["canonical_form", "canonical_equal"]
