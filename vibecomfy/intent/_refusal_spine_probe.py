"""Refusal-spine probe: detect whether a workflow edit is within the intended delta.

Lifted from scripts/roundtrip_fidelity_spike.py T4 detector.

``convert_ui_to_api`` is imported lazily when available. Offline test runs use
VibeComfy's pure-Python UI normalizer fallback instead.
"""

from __future__ import annotations

import copy
from typing import Literal, Any


from vibecomfy.ingest.door_access import door_get_nodes
def probe_refusal_spine(
    orig: Any,
    edited: Any,
    intended_delta: set[tuple[str, str]],
) -> Literal["ALLOW", "REFUSE"]:
    """Return 'ALLOW' if the edit is contained within intended_delta, 'REFUSE' otherwise.

    Parameters
    ----------
    orig:
        Pre-edit workflow.  Either UI-format (dict with a ``nodes`` list) or
        API-format (dict whose keys are node IDs).
    edited:
        Post-edit workflow in the same format as *orig*.
    intended_delta:
        Set of ``(node_id, field)`` pairs the editor intended to change.
    """
    a, b = _to_api(orig), _to_api(edited)

    changed: set[tuple[str, str]] = set()
    for nid in set(a) | set(b):
        a_inputs = a.get(nid, {}).get("inputs", {})
        b_inputs = b.get(nid, {}).get("inputs", {})
        for k in set(a_inputs) | set(b_inputs):
            if a_inputs.get(k) != b_inputs.get(k):
                changed.add((nid, k))

    unexpected = changed - intended_delta
    return "ALLOW" if not unexpected else "REFUSE"


def _to_api(wf: Any) -> dict:
    """Convert *wf* to API format (no-op if already in API format)."""
    if isinstance(wf, dict) and isinstance(door_get_nodes(wf), list):
        try:
            from comfy.component_model.workflow_convert import convert_ui_to_api  # lazy
        except ImportError:
            from vibecomfy.ingest.normalize import normalize_to_api

            return normalize_to_api(
                copy.deepcopy(wf),
                use_comfy_converter=False,
            )
        else:
            result = convert_ui_to_api(copy.deepcopy(wf))
            return result[0] if isinstance(result, tuple) else result
    # Already API-format
    return wf
