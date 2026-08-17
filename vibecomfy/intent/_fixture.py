"""Fixture loader for the intent-oracle corpus.

Each fixture JSON describes a *wrong-but-faithful* workflow edit: the editor
changed the right place but the edit does not actually achieve the nl_intent.
"""

from __future__ import annotations

from vibecomfy.ingest.door_access import door_get_nodes, door_get_widgets_values
import copy
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from vibecomfy.intent._ledger import (  # noqa: F401 — one ledger, re-exported
    CLASS_D_HARD_FLOOR_IDS,
    EXIT_FAILURE_LEDGER,
    FailureLedgerRow,
    LEDGER_ID_COUNT,
    LEDGER_RECONSTRUCTION_SOURCE,
    LEDGER_UNRECOVERABLE_COUNT,
    assert_ledger_integrity,
    ledger_scenario_ids,
)


@dataclass
class Fixture:
    id: str
    family: str
    pre_ui: Any
    post_ui: Any
    intended_delta: set[tuple[str, str]]
    nl_intent: str
    expected_text_judge_verdict: str
    wrongness_description: str


def load_fixture(path: str | Path) -> Fixture:
    """Load a fixture JSON and return a populated :class:`Fixture`.

    The fixture's ``pre_workflow_path`` is resolved relative to the fixture
    file.  ``post_edit_ir_patch`` ops are applied to a deep-copy of the loaded
    workflow to produce ``post_ui``.
    """
    path = Path(path)
    raw = json.loads(path.read_text())

    pre_path = (path.parent / raw["pre_workflow_path"]).resolve()
    pre_ui = json.loads(pre_path.read_text())
    post_ui = copy.deepcopy(pre_ui)

    patch = raw["post_edit_ir_patch"]
    ops = patch if isinstance(patch, list) else [patch]
    for op in ops:
        _apply_op(post_ui, op)

    intended_delta: set[tuple[str, str]] = {
        (str(node_id), str(field))
        for node_id, field in raw["intended_delta"]["changed"]
    }

    return Fixture(
        id=raw["id"],
        family=raw["family"],
        pre_ui=pre_ui,
        post_ui=post_ui,
        intended_delta=intended_delta,
        nl_intent=raw["nl_intent"],
        expected_text_judge_verdict=raw["expected_text_judge_verdict"],
        wrongness_description=raw["wrongness_description"],
    )


def _apply_op(wf: Any, op: dict) -> None:
    """Apply a single patch op to *wf* in place."""
    node_id = str(op["node_id"])
    field = str(op["field"])
    new_val = op["new"]
    old_val = op.get("old")

    if isinstance(wf, dict) and isinstance(door_get_nodes(wf), list):
        # UI-format: search top-level nodes and subgraph definitions
        node = _find_ui_node(wf, node_id)
        if node is None:
            raise KeyError(f"Node {node_id!r} not found in UI workflow")
        wv = door_get_widgets_values(node)
        if wv is not None and len(wv) > 0:
            # Find widget slot by exact old value first
            if old_val is not None and old_val in wv:
                idx = wv.index(old_val)
            elif len(wv) == 1:
                # Single widget — must be the right one
                idx = 0
            else:
                # Try prefix match for truncated string values
                idx = _find_widget_idx_fuzzy(wv, old_val)
                if idx is None:
                    # Cannot safely locate widget; skip rather than corrupt
                    return
            wv[idx] = new_val
        else:
            # Widget stored as named input (widget-input with link=null).
            # Find the input entry and insert new value into widgets_values.
            inputs = node.get("inputs", [])
            widget_inputs = [i for i in inputs if i.get("widget") and i.get("link") is None]
            target = next((i for i in widget_inputs if i.get("name") == field), None)
            if target is not None and isinstance(wv, list):
                wv.append(new_val)
            # Missing widgets_values is left unchanged: assigning that graph
            # key belongs in the ingest/emit doors, not the fixture loader.
    else:
        # API-format: keys are node IDs
        if node_id in wf:
            wf[node_id]["inputs"][field] = new_val
        else:
            raise KeyError(f"Node {node_id!r} not found in API workflow")


def _find_widget_idx_fuzzy(wv: list, old_val: Any) -> int | None:
    """Return the index of *old_val* in *wv* using prefix-match for strings."""
    if not isinstance(old_val, str):
        return None
    for i, v in enumerate(wv):
        if isinstance(v, str) and v.startswith(old_val):
            return i
    return None


def _find_ui_node(wf: dict, node_id: str) -> dict | None:
    """Return the UI node dict with the given *node_id* (str or int match)."""
    int_id: int | None = None
    try:
        int_id = int(node_id)
    except (ValueError, TypeError):
        pass

    # Search top-level nodes
    for n in door_get_nodes(wf, []):
        if str(n.get("id")) == node_id or n.get("id") == int_id:
            return n

    # Search inside subgraph definitions (ComfyUI UI format with definitions.subgraphs)
    for sg in wf.get("definitions", {}).get("subgraphs", []):
        for n in door_get_nodes(sg, []):
            if str(n.get("id")) == node_id or n.get("id") == int_id:
                return n

    return None
