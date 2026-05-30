"""Refusal-spine for re-emit (M5 Step 16).

``guard_emit(original_ui, candidate_ui, snapshot_delta)`` is the safety gate
applied on APPLIED re-emit: it runs both UI JSONs through the vendored
ComfyUI ``convert_ui_to_api`` and refuses the emit whenever the *candidate*
diverges from the *original* on a uid-matched, snapshot-present node in any
field NOT named in ``snapshot_delta``.

A *hard import check* runs at module load — if the vendored ComfyUI is not
importable (e.g. ``vendor/ComfyUI`` submodule uninitialized), the failure is
captured and re-raised from the first ``guard_emit`` call with a clear
diagnostic, rather than silently degrading to a no-op gate.

Spec: ``vibecomfy/porting/refuse.py`` is torch-free, no Node, no HTTP. All
schema needs are served from the vendored ComfyUI on ``sys.path`` (via
``vibecomfy.comfy_backend.ensure_nodes``).
"""
from __future__ import annotations

from typing import Any, Mapping

# ─── Hard import check (module init) ──────────────────────────────────────
# Fail loudly at first use rather than silently degrading: importing this
# module always attempts to bring the vendored ComfyUI onto sys.path and
# import ``convert_ui_to_api``.  On failure, ``_IMPORT_ERROR`` is set and the
# first ``guard_emit`` call re-raises it as ImportError.
from vibecomfy.comfy_backend import ensure_nodes as _ensure_nodes

_ensure_nodes()
try:  # noqa: SIM105
    from comfy.component_model.workflow_convert import (
        convert_ui_to_api as _convert_ui_to_api,
    )
except Exception as _imp_err:  # pragma: no cover - exercised when vendor absent
    _convert_ui_to_api = None  # type: ignore[assignment]
    _IMPORT_ERROR: BaseException | None = _imp_err
else:
    _IMPORT_ERROR = None


class RefusedEmit(Exception):
    """Raised when ``guard_emit`` detects an unauthorized re-emit divergence.

    Attributes
    ----------
    reason:
        Short human-readable summary of why the emit was refused.
    diff:
        ``{uid: {axis: ...}}`` — per-uid breakdown of the offending differences
        between ``convert_ui_to_api(original)`` and ``convert_ui_to_api(candidate)``.
    """

    def __init__(self, reason: str, diff: Mapping[str, Any]):
        super().__init__(reason)
        self.reason = reason
        self.diff = dict(diff)


class EditorAheadError(Exception):
    """Raised when ``emit_ui_json`` detects editor-only uids in the prior store.

    An editor-only uid is one that exists in the prior store but is absent from
    the IR and was not authored by a prior VibeComfy emit (i.e. the node was
    added directly in the ComfyUI editor after the last VibeComfy export).

    Attributes
    ----------
    editor_only_uids:
        List of ``{uid, class_type}`` dicts for each editor-only uid detected,
        sorted by uid for deterministic output.
    """

    def __init__(self, editor_only_uids: list[dict[str, str]]):
        super().__init__(
            f"editor_ahead: {len(editor_only_uids)} uid(s) in the prior store "
            "were not authored by VibeComfy — use --force-drop to allow dropping them"
        )
        self.editor_only_uids = list(editor_only_uids)


def _uid_to_litegraph_id(ui_json: Mapping[str, Any]) -> dict[str, str]:
    """Build a ``{vibecomfy_uid: str(litegraph_id)}`` map from a UI JSON."""
    out: dict[str, str] = {}
    for node in ui_json.get("nodes", []) or []:
        if not isinstance(node, dict):
            continue
        props = node.get("properties") or {}
        uid = props.get("vibecomfy_uid")
        if uid:
            out[str(uid)] = str(node.get("id"))
    return out


def _api_node(api: Mapping[str, Any], node_id: str) -> Any:
    """Look up an api-node by id, tolerating int/str key drift."""
    if node_id in api:
        return api[node_id]
    if node_id.isdigit():
        as_int = int(node_id)
        if as_int in api:  # type: ignore[operator]
            return api[as_int]  # type: ignore[index]
    return None


# Snapshot field names whose changes flow into the API ``inputs`` axis.
_INPUT_AXIS_FIELDS = frozenset(
    {
        "widget_values_sig",
        "incoming_edge_sig",
        "outgoing_edge_sig",
        "public_input_binding",
    }
)


def guard_emit(
    original_ui: Mapping[str, Any],
    candidate_ui: Mapping[str, Any],
    snapshot_delta: Mapping[str, Mapping[str, tuple]] | None,
) -> None:
    """Refusal-spine on APPLIED re-emit.

    Compares ``convert_ui_to_api(candidate_ui)`` against
    ``convert_ui_to_api(original_ui)`` over the *scope set* — nodes that are
    (a) uid-matched in both ``original_ui`` and ``candidate_ui`` AND (b) present
    in the original ingest snapshot.  Because the original UI IS the snapshot
    source by construction in the M5 preserve flow, condition (b) reduces to
    uid-presence in ``original_ui``.

    Inside the scope set, any change *outside* the fields enumerated by
    ``snapshot_delta[uid]`` raises :class:`RefusedEmit` with the offending
    per-uid diff.  Nodes outside the scope set are always allowed.

    Parameters
    ----------
    original_ui:
        UI JSON dict for the pre-edit state (what was on disk before re-emit).
    candidate_ui:
        UI JSON dict for the post-edit emit candidate (about to be written).
    snapshot_delta:
        ``{uid: {field_name: (old, new)}}`` from
        :func:`vibecomfy.porting.layout.delta.compute_field_delta`.  Names the
        fields the user is intentionally changing.  ``None`` is treated as the
        empty dict.

    Raises
    ------
    RefusedEmit
        When a uid in the scope set differs on a field not in ``snapshot_delta``.
    ImportError
        When the vendored ComfyUI ``convert_ui_to_api`` is unavailable.
    """
    if _convert_ui_to_api is None:  # pragma: no cover - exercised when vendor absent
        raise ImportError(
            "vibecomfy.porting.refuse: vendored ComfyUI convert_ui_to_api is "
            f"unavailable ({_IMPORT_ERROR!r}). Ensure the vendor/ComfyUI "
            "submodule is initialized and importable."
        )

    delta: Mapping[str, Mapping[str, tuple]] = snapshot_delta or {}

    orig_uid_to_id = _uid_to_litegraph_id(original_ui)
    cand_uid_to_id = _uid_to_litegraph_id(candidate_ui)
    scope_uids = set(orig_uid_to_id) & set(cand_uid_to_id)
    if not scope_uids:
        return

    orig_api = _convert_ui_to_api(dict(original_ui))
    cand_api = _convert_ui_to_api(dict(candidate_ui))

    diff: dict[str, dict[str, Any]] = {}
    for uid in scope_uids:
        orig_node = _api_node(orig_api, orig_uid_to_id[uid])
        cand_node = _api_node(cand_api, cand_uid_to_id[uid])

        if orig_node is None and cand_node is None:
            continue
        if orig_node is None or cand_node is None:
            diff[uid] = {
                "presence": (orig_node is not None, cand_node is not None)
            }
            continue

        # Strip the slim ``_ui`` merge (litegraph furniture only — no graph
        # semantics).  Compare ``class_type`` and ``inputs`` axes.
        orig_class = orig_node.get("class_type")
        cand_class = cand_node.get("class_type")
        orig_inputs = dict(orig_node.get("inputs") or {})
        cand_inputs = dict(cand_node.get("inputs") or {})

        allowed = set(delta.get(uid, {}).keys())
        class_axis_allowed = "class_type" in allowed
        inputs_axis_allowed = bool(allowed & _INPUT_AXIS_FIELDS)

        node_diff: dict[str, Any] = {}
        if orig_class != cand_class and not class_axis_allowed:
            node_diff["class_type"] = (orig_class, cand_class)
        if orig_inputs != cand_inputs and not inputs_axis_allowed:
            differing: dict[str, tuple] = {}
            for k in set(orig_inputs) | set(cand_inputs):
                if orig_inputs.get(k) != cand_inputs.get(k):
                    differing[k] = (orig_inputs.get(k), cand_inputs.get(k))
            if differing:
                node_diff["inputs"] = differing
        if node_diff:
            diff[uid] = node_diff

    if diff:
        raise RefusedEmit(
            "guard_emit refused re-emit: "
            f"{len(diff)} uid-matched node(s) changed outside snapshot_delta",
            diff,
        )


__all__ = ["EditorAheadError", "RefusedEmit", "guard_emit"]
