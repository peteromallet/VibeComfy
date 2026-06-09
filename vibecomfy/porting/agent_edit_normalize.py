"""Agent-edit UI normalization.

Provides the normalize helper consumed by the preservation guard
(:func:`guard_full_ui` in ``vibecomfy/porting/edit_apply.py``) and the
narrow field-path allow-list used by the time-boxed fallback path.

Preferred path
--------------
The intended browser/LiteGraph mechanism::

    serialize -> configure -> serialize

When LiteGraph/browser utilities are available (i.e. the vendored ComfyUI
is importable), ``normalize_ui_json`` round-trips through the real
``LGraph.serialize()`` / ``LGraph.configure()`` cycle.  This is the only
path that is guaranteed to match the live browser's normal form.

Raw-dict fallback
-----------------
When LiteGraph is unavailable (unit tests, offline CI), a documented
raw-dict fallback approximates the normalization by:

1.  Round-tripping through :func:`json.dumps` / :func:`json.loads` with
    sorted keys to eliminate insertion-order variance.
2.  Normalizing float representation (``1.0`` → ``1`` when safe).
3.  Stripping empty ``flags`` objects and ``null`` link placeholders
    where LiteGraph omits them on re-serialize.

Any remaining cosmetic churn that the fallback cannot normalize must be
enumerated in the **allow-list** (see :data:`NORMALIZE_ALLOW_LIST`).

Allow-list contract
-------------------
Each entry is a dict with these keys:

``node_class``
    The ``type`` field value from the LiteGraph node (e.g. ``"KSampler"``).
``field_path``
    Exact dotted path from the node root (e.g. ``"widgets_values[0]"``,
    ``"properties.Node name for S&R"``).  Wildcards and regex are
    **not** allowed; broad node-level exemptions are forbidden.
``reason``
    Why the field churns under serialize→configure→serialize.
``fixture``
    Which fixture in ``tests/fixtures/agent_edit/`` demonstrated the churn.
``expiration``
    When this exemption should be re-evaluated (e.g. ``"2026-07-01"`` or
    ``"until LiteGraph configure is proven idempotent for this field"``).

The allow-list is consumed **only** on the time-boxed fallback path
(Step 7 of the preserve-core foundation).  When the preferred normalize
succeeds, no allow-list exemption is ever used.
"""

from __future__ import annotations

import copy
import json
import math
import time
from typing import Any

# ── allow-list ────────────────────────────────────────────────────────────

# Each entry: {node_class, field_path, reason, fixture, expiration}
# Field paths are dotted from the node root.  Index into arrays with [N].
# Broad node-class exemptions are forbidden — every entry must name the
# exact field path that churns.
#
# This list starts empty because the preferred normalize path has not yet
# been wired and no cosmetic churn has been measured on the available
# fixtures.  Entries are added by later tasks when the preservation
# guard encounters cosmetic churn that the raw-dict fallback cannot normalize.
NORMALIZE_ALLOW_LIST: list[dict[str, str]] = [
    # Example entry (commented out — no measured churn yet):
    # {
    #     "node_class": "KSampler",
    #     "field_path": "widgets_values[3]",
    #     "reason": "LiteGraph configure normalizes steps int to float "
    #               "when the widget config specifies a float step",
    #     "fixture": "flat.json",
    #     "expiration": "2026-07-01",
    # },
]

# ── helpers ────────────────────────────────────────────────────────────────

def _is_safe_int_float(value: float) -> bool:
    """Return True if *value* is a float that can be losslessly cast to int."""
    try:
        return value == int(value) and not math.isinf(value) and not math.isnan(value)
    except (OverflowError, ValueError):
        return False


def _normalize_value(value: Any) -> Any:
    """Normalize a single JSON value for comparison.

    - Integers represented as floats (e.g. ``1.0``) become ``int``.
    - Empty dicts (except ``{}`` that LiteGraph strips) are kept;
      specific empty-dict stripping is handled per-field by the allow-list.
    """
    if isinstance(value, float):
        if _is_safe_int_float(value):
            return int(value)
    if isinstance(value, dict):
        return {k: _normalize_value(v) for k, v in sorted(value.items())}
    if isinstance(value, list):
        return [_normalize_value(v) for v in value]
    return value


def _strip_null_link_placeholders(links: list | None) -> list | None:
    """Strip trailing null entries from output link arrays.

    LiteGraph sometimes serializes ``links: null`` for unused output slots
    and sometimes ``links: [null]``.  The round-trip normalizes both to
    ``links: null``.  This helper mirrors that behavior.
    """
    if links is None:
        return None
    if not links:
        return None
    # If ALL entries are None, return None
    if all(v is None for v in links):
        return None
    return links


def _normalize_node_outputs(outputs: list[dict] | None) -> list[dict] | None:
    """Normalize output slot link arrays within a node."""
    if outputs is None:
        return None
    result: list[dict] = []
    for out in outputs:
        out_copy = dict(out)
        if "links" in out_copy:
            out_copy["links"] = _strip_null_link_placeholders(out_copy["links"])
        # Normalize slot_index if it's a float-represented int
        if "slot_index" in out_copy and isinstance(out_copy["slot_index"], float):
            if _is_safe_int_float(out_copy["slot_index"]):
                out_copy["slot_index"] = int(out_copy["slot_index"])
        result.append(out_copy)
    return result


def _deep_sort_dict(d: dict[str, Any]) -> dict[str, Any]:
    """Recursively sort dictionary keys for stable comparison."""
    result: dict[str, Any] = {}
    for k in sorted(d.keys()):
        v = d[k]
        if isinstance(v, dict):
            result[k] = _deep_sort_dict(v)
        elif isinstance(v, list):
            result[k] = [
                _deep_sort_dict(item) if isinstance(item, dict) else item
                for item in v
            ]
        else:
            result[k] = v
    return result


def _normalize_node(node: dict[str, Any]) -> dict[str, Any]:
    """Normalize a single LiteGraph node dict for comparison.

    Applies:
    - Sorted keys for stable serialization
    - Float-to-int normalization for widget values
    - Null link placeholder stripping on outputs
    - Empty flags stripping (LiteGraph omits empty flags on re-serialize)
    """
    normalized: dict[str, Any] = {}

    for key in sorted(node.keys()):
        value = node[key]

        if key == "flags" and isinstance(value, dict) and not value:
            # LiteGraph strips empty flags on re-serialize
            continue

        if key == "outputs" and isinstance(value, list):
            normalized[key] = _normalize_node_outputs(value)
        elif key == "widgets_values" and isinstance(value, list):
            normalized[key] = [_normalize_value(v) for v in value]
        elif key == "properties" and isinstance(value, dict):
            normalized[key] = _deep_sort_dict(value)
        elif isinstance(value, dict):
            normalized[key] = _deep_sort_dict(value)
        elif isinstance(value, list):
            normalized[key] = [
                _deep_sort_dict(item) if isinstance(item, dict) else _normalize_value(item)
                for item in value
            ]
        else:
            normalized[key] = _normalize_value(value)

    return normalized


def _normalize_ui_json_raw(raw: dict[str, Any]) -> dict[str, Any]:
    """Normalize a UI JSON dict using the raw-dict fallback.

    This approximates ``serialize → configure → serialize`` by:
    1. Round-tripping through JSON with sorted keys.
    2. Normalizing each node.
    3. Normalizing root-level fields.
    """
    # JSON round-trip with sorted keys to eliminate insertion-order variance
    serialized = json.dumps(raw, sort_keys=True)
    round_tripped = json.loads(serialized)

    if not isinstance(round_tripped, dict):
        return raw  # defensive

    result: dict[str, Any] = {}

    for key in sorted(round_tripped.keys()):
        value = round_tripped[key]

        if key == "nodes" and isinstance(value, list):
            result[key] = [_normalize_node(n) for n in value if isinstance(n, dict)]
        elif key == "links" and isinstance(value, list):
            # Normalize link arrays: float-coerce link ids
            result[key] = [
                [_normalize_value(v) for v in link] if isinstance(link, list) else link
                for link in value
            ]
        elif key == "definitions" and isinstance(value, dict):
            result[key] = _normalize_definitions(value)
        elif key == "groups" and isinstance(value, list):
            result[key] = [
                _deep_sort_dict(g) if isinstance(g, dict) else g for g in value
            ]
        elif isinstance(value, dict):
            result[key] = _deep_sort_dict(value)
        else:
            result[key] = _normalize_value(value)

    return result


def _normalize_definitions(defs: dict[str, Any]) -> dict[str, Any]:
    """Normalize the ``definitions`` block including nested subgraphs."""
    result: dict[str, Any] = {}
    for key in sorted(defs.keys()):
        value = defs[key]
        if key == "subgraphs" and isinstance(value, list):
            # Each subgraph is itself a mini UI JSON with nodes/links
            result[key] = [
                _normalize_subgraph(sg) if isinstance(sg, dict) else sg
                for sg in value
            ]
        elif isinstance(value, dict):
            result[key] = _deep_sort_dict(value)
        else:
            result[key] = _normalize_value(value)
    return result


def _normalize_subgraph(subgraph: dict[str, Any]) -> dict[str, Any]:
    """Normalize a single subgraph definition dict."""
    result: dict[str, Any] = {}
    for key in sorted(subgraph.keys()):
        value = subgraph[key]
        if key == "nodes" and isinstance(value, list):
            result[key] = [_normalize_node(n) for n in value if isinstance(n, dict)]
        elif key == "links" and isinstance(value, list):
            # Subgraph links may be dict-format instead of array-format
            result[key] = [
                _deep_sort_dict(link) if isinstance(link, dict) else link
                for link in value
            ]
        elif isinstance(value, dict):
            result[key] = _deep_sort_dict(value)
        else:
            result[key] = _normalize_value(value)
    return result


# ── public API ─────────────────────────────────────────────────────────────

def normalize_ui_json(
    ui_json: dict[str, Any],
    *,
    timeout_ms: int = 200,
    _lgraph_available: bool = False,
) -> dict[str, Any]:
    """Normalize a browser UI JSON dict for byte-comparison.

    When the vendored ComfyUI/LiteGraph runtime is available
    (``_lgraph_available=True``), this round-trips through the real
    ``serialize → configure → serialize`` cycle.  The ``timeout_ms``
    parameter gates this path; if it times out, the raw-dict fallback
    is used instead.

    In test environments without LiteGraph, always uses the raw-dict
    fallback.

    Parameters
    ----------
    ui_json:
        The browser UI JSON dict to normalize.  Must have LiteGraph
        substrate shape (``nodes``, ``links``, etc.).
    timeout_ms:
        Maximum milliseconds to spend on the LiteGraph round-trip before
        falling back to raw-dict normalization.  Ignored when
        ``_lgraph_available`` is ``False``.
    _lgraph_available:
        Set to ``True`` when the vendored ComfyUI is importable and
        ``LGraph`` is available.  Test code should pass ``False``
        (the default) for deterministic offline behavior.

    Returns
    -------
    dict
        A normalized deep copy of *ui_json*.  The returned dict has
        sorted keys, normalized numeric types, and stripped cosmetic
        fields.
    """
    # Deep-copy to avoid mutating the input
    original = copy.deepcopy(ui_json)

    if _lgraph_available:
        # Preferred path: real LiteGraph round-trip
        start = time.monotonic()
        try:
            normalized = _normalize_via_litegraph(original, timeout_ms=timeout_ms, start_time=start)
            if normalized is not None:
                return normalized
        except Exception:
            pass
        # Fall through to raw-dict fallback on timeout or error

    return _normalize_ui_json_raw(original)


def _normalize_via_litegraph(
    ui_json: dict[str, Any],
    timeout_ms: int,
    start_time: float,
) -> dict[str, Any] | None:
    """Attempt to normalize through real LiteGraph serialize→configure→serialize.

    Returns None if LiteGraph is unavailable or the operation times out.
    """
    try:
        from vibecomfy.comfy_backend import ensure_nodes as _ensure_nodes
        _ensure_nodes()
        import comfy.litegraph as litegraph  # type: ignore[import-untyped]
    except Exception:
        return None

    try:
        graph = litegraph.LGraph()
        graph.configure(ui_json)

        elapsed = (time.monotonic() - start_time) * 1000
        if elapsed > timeout_ms:
            return None

        serialized = graph.serialize()
        if isinstance(serialized, str):
            serialized = json.loads(serialized)
        return dict(serialized) if isinstance(serialized, dict) else None
    except Exception:
        return None


def is_normalize_available() -> bool:
    """Return ``True`` if the vendored ComfyUI/LiteGraph is importable."""
    try:
        from vibecomfy.comfy_backend import ensure_nodes as _ensure_nodes
        _ensure_nodes()
        import comfy.litegraph  # type: ignore[import-untyped]  # noqa: F401
        return True
    except Exception:
        return False


def normalize_allow_list_matches(
    node_class: str,
    field_path: str,
) -> dict[str, str] | None:
    """Check if a (node_class, field_path) pair matches an allow-list entry.

    Returns the matching entry dict, or ``None`` if no match.
    """
    for entry in NORMALIZE_ALLOW_LIST:
        if entry["node_class"] == node_class and entry["field_path"] == field_path:
            return entry
    return None


def normalize_compare(
    original: dict[str, Any],
    candidate: dict[str, Any],
    *,
    normalize_fn: callable = normalize_ui_json,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Normalize both original and candidate, returning (norm_original, norm_candidate).

    This is the entry point used by the preservation guard when the
    preferred normalize path succeeds.  It normalizes both sides through
    the same mechanism before byte-comparison.
    """
    return normalize_fn(original), normalize_fn(candidate)
