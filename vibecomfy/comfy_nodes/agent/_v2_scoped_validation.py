"""V2 scoped validation: submit/candidate graph loading, delta normalisation, graph
indexing, scoped expected_old resolution, and the scoped validation plan builder (T-045).

Extracted from ``vibecomfy.comfy_nodes.agent.session`` (T-045, ORACLE-7, WP-6.2): the
V2 scoped-validation helper ranges (session.py :4143-5383) -- submit/candidate graph
loading, delta normalisation, graph indexing, scoped expected_old resolution, the
scoped validation plan builder, V2 accept-evidence loading, and the V2 turn-state
transition validator.  ``session`` re-exports this module via ``from
._v2_scoped_validation import *`` (façade seam added at T-043); ``__all__`` below is
exactly the name set these ranges contributed to the session namespace, so the
re-export reproduces the identical top-level attributes -- the same contract
``edit`` uses for its ``_frag_*`` fragments (including ``_``-prefixed helpers that
stay importable by name for the T-048 monkeypatch/importer compatibility).

Dependency style (S6 ground truth): non-cyclic deps (``contracts``,
``vibecomfy.porting.edit.ops``) are imported ordinarily at module level; every name
that lives in the host ``session`` façade (``payload_hash``,
``_V1_HISTORICAL_STATES``, ``_V2_TERMINAL_STATES``) is resolved with the standard
T-045 late import (function-local, host namespace lookup, resolved at call time) so
the ``session`` -> ``_v2_scoped_validation`` re-export cycle never bites and
module-attr patching on ``session`` stays visible.
"""

from __future__ import annotations

import json
import re
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterator, Literal

from .contracts import FailureEnvelope, FailureKind, TurnContext, failure_envelope
from vibecomfy.porting.edit.ops import parse_edit_delta
# T-045 module-level host import: ``TurnState`` is referenced only in annotations
# (PEP 563 strings -- never evaluated at runtime), imported here so those
# annotations stay resolvable for type checkers; ``session`` is fully defined
# before its end-of-file ``from ._v2_scoped_validation import *`` re-export, so
# the cycle never bites when ``session`` is the entry point.
from .session import TurnState


# ---------------------------------------------------------------------------
# V2 accept evidence loading -- load persisted turn/session artifacts so
# scoped validation can derive expected_old from the submit-time graph.
# These are consumed by _mutate_turn_state (V2 branch) but do not change
# the accept gate themselves; that is done in later tasks.
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class _ScopedValueSentinel:
    code: str


_SENTINEL_NO_VALUE = _ScopedValueSentinel("missing_value")
_SENTINEL_LINK_ABSENT = _ScopedValueSentinel("link_absent")
_SENTINEL_NODE_ABSENT = _ScopedValueSentinel("node_absent")


@dataclass(frozen=True)
class _GraphIndex:
    graph: Mapping[str, Any]
    nodes_by_uid: dict[str, Mapping[str, Any]]
    nodes_by_id: dict[int | str, Mapping[str, Any]]
    nodes_by_str_id: dict[str, Mapping[str, Any]]
    links_by_id: dict[int | str, Any]


def _load_turn_request_graph(
    *, session_dir: Path, turn_id: str
) -> dict[str, Any] | None:
    """Load the submit-time graph from the turn's ``request.json``."""
    path = session_dir / "turns" / turn_id / "request.json"
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(payload, Mapping):
        return None
    graph = payload.get("graph")
    if isinstance(graph, Mapping):
        return dict(graph)
    return None


def _load_turn_response_payload(
    *, session_dir: Path, turn_id: str
) -> dict[str, Any] | None:
    """Load the turn's ``response.json``."""
    path = session_dir / "turns" / turn_id / "response.json"
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, Mapping) else None


def _load_turn_candidate_graph(
    *, session_dir: Path, turn_id: str
) -> dict[str, Any] | None:
    """Load the candidate graph from the persisted turn response."""
    payload = _load_turn_response_payload(session_dir=session_dir, turn_id=turn_id)
    if payload is None:
        return None
    graph = payload.get("graph")
    if isinstance(graph, Mapping):
        return dict(graph)
    return None


def _load_turn_delta_ops(
    *, session_dir: Path, turn_id: str
) -> tuple[dict[str, Any], ...] | None:
    """Load canonical ``delta_ops`` from the persisted turn response.

    Prefers the ``delta_ops_envelope`` (``{schema_version: "2.0.0", ops: [...]}``)
    over the legacy flat ``delta_ops`` list.  Returns None if the response does
    not contain a valid ops list.
    """
    response = _load_turn_response_payload(session_dir=session_dir, turn_id=turn_id)
    if response is None:
        return None

    # Canonical path: delta_ops_envelope with {schema_version, ops}
    envelope = response.get("delta_ops_envelope")
    if isinstance(envelope, Mapping):
        ops = envelope.get("ops")
        if isinstance(ops, list) and all(isinstance(op, Mapping) for op in ops):
            # Validate each op through the backend normaliser so that
            # malformed ops (unknown op kind, missing required fields,
            # etc.) inside a syntactically-valid envelope are rejected
            # before downstream accept verification consumes them.
            try:
                parse_edit_delta(ops)
            except ValueError:
                return None
            return tuple(dict(op) for op in ops)
        # Envelope present but ops is malformed — fall through to delta_ops.
        # We record the shape for diagnostics in _build_v2_accept_evidence.

    # Legacy bridge: flat delta_ops list
    delta_ops = response.get("delta_ops")
    if isinstance(delta_ops, list) and all(isinstance(op, Mapping) for op in delta_ops):
        return tuple(dict(op) for op in delta_ops)

    # Legacy wrapped shape: a dict under delta_ops that is NOT a list
    # (e.g. {"delta_ops": {...}, "diagnostics": [...]}) — reject.
    if isinstance(delta_ops, Mapping):
        return None

    return _infer_delta_ops_from_legacy_field_changes(response)


def _iter_legacy_field_changes(payload: Mapping[str, Any]) -> Iterator[Mapping[str, Any]]:
    seen_ids: set[int] = set()

    def emit_items(items: Any) -> Iterator[Mapping[str, Any]]:
        if not isinstance(items, list):
            return
        for item in items:
            if not isinstance(item, Mapping):
                continue
            identity = id(item)
            if identity in seen_ids:
                continue
            seen_ids.add(identity)
            yield item

    yield from emit_items(payload.get("field_changes"))
    outcome = payload.get("outcome")
    if isinstance(outcome, Mapping):
        yield from emit_items(outcome.get("changes"))
    batch_turns = payload.get("batch_turns")
    for turn in batch_turns if isinstance(batch_turns, list) else ():
        if isinstance(turn, Mapping):
            yield from emit_items(turn.get("field_changes"))
    change_details = payload.get("change_details")
    if isinstance(change_details, Mapping):
        detail_turns = change_details.get("batch_turns")
        for turn in detail_turns if isinstance(detail_turns, list) else ():
            if isinstance(turn, Mapping):
                yield from emit_items(turn.get("field_changes"))


def _infer_delta_ops_from_legacy_field_changes(
    response: Mapping[str, Any],
) -> tuple[dict[str, Any], ...] | None:
    """Recover scoped link intent from pre-delta response artifacts.

    Only explicit link field changes are promoted. Literal/widget changes remain
    V1 because field changes do not faithfully encode every edit operation kind.
    """
    ops: list[dict[str, Any]] = []
    seen: set[str] = set()
    unsupported_change_seen = False
    for change in _iter_legacy_field_changes(response):
        target_uid = change.get("uid")
        field_path = change.get("field_path")
        new_value = change.get("new")
        if target_uid is None or not isinstance(field_path, str) or not field_path:
            unsupported_change_seen = True
            continue
        if not isinstance(new_value, Mapping):
            unsupported_change_seen = True
            continue
        source_uid = new_value.get("uid")
        output_slot = new_value.get("output_slot")
        if source_uid is None or output_slot is None:
            unsupported_change_seen = True
            continue
        source_scope = new_value.get("scope_path", "")
        target_scope = change.get("scope_path", "")
        if not isinstance(source_scope, str) or not isinstance(target_scope, str):
            unsupported_change_seen = True
            continue
        op = {
            "op": "upsert_link",
            "from": [source_scope, str(source_uid), output_slot],
            "to": [target_scope, str(target_uid), field_path],
        }
        key = json.dumps(op, sort_keys=True, separators=(",", ":"))
        if key in seen:
            continue
        seen.add(key)
        ops.append(op)
    if unsupported_change_seen:
        return None
    return tuple(ops) if ops else None


def _load_turn_delta_ops_diagnostic(
    *, session_dir: Path, turn_id: str
) -> dict[str, Any]:
    """Inspect the persisted turn response and return a diagnostic classifying
    the delta shape, without attempting to normalise.

    Returns a dict with:
      * ``shape`` — one of ``canonical``, ``legacy_flat``, ``legacy_wrapped``,
        ``missing``
      * ``code`` — stable diagnostic code
      * ``detail`` — shape-specific evidence
    """
    response = _load_turn_response_payload(session_dir=session_dir, turn_id=turn_id)
    if response is None:
        return {
            "shape": "missing",
            "code": "missing_turn_response",
            "detail": {},
        }

    envelope = response.get("delta_ops_envelope")
    if isinstance(envelope, Mapping):
        ops = envelope.get("ops")
        if isinstance(ops, list):
            # Validate each op through the backend normaliser so that
            # malformed entries (unknown op kind, missing required fields,
            # etc.) are classified as malformed rather than canonical.
            try:
                parse_edit_delta(ops)
            except ValueError:
                return {
                    "shape": "canonical",
                    "code": "canonical_envelope_malformed_ops",
                    "detail": {
                        "schema_version": envelope.get("schema_version"),
                        "reason": "ops list present but entries failed parse_edit_delta validation",
                    },
                }
            return {
                "shape": "canonical",
                "code": "canonical_delta_ops",
                "detail": {"schema_version": envelope.get("schema_version")},
            }
        return {
            "shape": "canonical",
            "code": "canonical_envelope_malformed_ops",
            "detail": {"ops_type": type(ops).__name__},
        }

    delta_ops = response.get("delta_ops")
    if isinstance(delta_ops, list):
        return {
            "shape": "legacy_flat",
            "code": "legacy_delta_ops_flat",
            "detail": {},
        }
    if isinstance(delta_ops, Mapping):
        legacy_keys = sorted(
            k for k in delta_ops
            if k in (
                "delta", "delta_ops", "diagnostics", "guard_result",
                "automatic_link_removals", "re_stitches", "normalize",
                "ops",
            )
        )
        return {
            "shape": "legacy_wrapped",
            "code": "legacy_delta_shape",
            "detail": {"keys": legacy_keys},
        }

    return {
        "shape": "missing",
        "code": "missing_delta_ops",
        "detail": {},
    }


def _scoped_sentinel_payload(value: Any) -> Any:
    if value is _SENTINEL_NO_VALUE:
        return {"sentinel": _SENTINEL_NO_VALUE.code}
    if value is _SENTINEL_LINK_ABSENT:
        return {"sentinel": _SENTINEL_LINK_ABSENT.code}
    if value is _SENTINEL_NODE_ABSENT:
        return {"sentinel": _SENTINEL_NODE_ABSENT.code}
    return value


def _build_graph_index(graph: Mapping[str, Any]) -> _GraphIndex:
    nodes_by_uid: dict[str, Mapping[str, Any]] = {}
    nodes_by_id: dict[int | str, Mapping[str, Any]] = {}
    nodes_by_str_id: dict[str, Mapping[str, Any]] = {}
    for node in graph.get("nodes") if isinstance(graph.get("nodes"), list) else []:
        if not isinstance(node, Mapping):
            continue
        node_id = node.get("id")
        if isinstance(node_id, (int, str)):
            nodes_by_id[node_id] = node
            nodes_by_str_id[str(node_id)] = node
        props = node.get("properties")
        if isinstance(props, Mapping):
            uid = props.get("vibecomfy_uid")
            if isinstance(uid, str) and uid:
                nodes_by_uid[uid] = node
    links_by_id: dict[int | str, Any] = {}
    for link in graph.get("links") if isinstance(graph.get("links"), list) else []:
        if isinstance(link, list) and link:
            link_id = link[0]
        elif isinstance(link, Mapping):
            link_id = link.get("id")
        else:
            continue
        if isinstance(link_id, (int, str)):
            links_by_id[link_id] = link
            links_by_id[str(link_id)] = link
    return _GraphIndex(
        graph=graph,
        nodes_by_uid=nodes_by_uid,
        nodes_by_id=nodes_by_id,
        nodes_by_str_id=nodes_by_str_id,
        links_by_id=links_by_id,
    )


def _canonical_node_uid(node: Mapping[str, Any]) -> str | None:
    props = node.get("properties")
    if isinstance(props, Mapping):
        uid = props.get("vibecomfy_uid")
        if isinstance(uid, str) and uid:
            return uid
    node_id = node.get("id")
    if isinstance(node_id, (int, str)):
        return str(node_id)
    return None


def _normalize_target_uid(target: Any) -> str | None:
    if isinstance(target, Mapping):
        for key in ("uid", "node_uid", "id", "node_id", "scope_path"):
            value = target.get(key)
            if isinstance(value, (int, str)) and str(value):
                return str(value)
        return None
    if isinstance(target, list) and len(target) >= 2:
        value = target[1]
        if isinstance(value, (int, str)) and str(value):
            return str(value)
    return None


def _find_node_in_index(index: _GraphIndex, alias: Any) -> Mapping[str, Any] | None:
    if isinstance(alias, str) and alias in index.nodes_by_uid:
        return index.nodes_by_uid[alias]
    if isinstance(alias, (int, str)) and alias in index.nodes_by_id:
        return index.nodes_by_id[alias]
    if isinstance(alias, (int, str)):
        return index.nodes_by_str_id.get(str(alias))
    return None


def _find_node_in_graph(graph: Mapping[str, Any], uid: str) -> Mapping[str, Any] | None:
    return _find_node_in_index(_build_graph_index(graph), uid)


def _split_field_path(field_path: str) -> list[str]:
    normalized = re.sub(r"\[(\d+)\]", r".\1", field_path)
    return [segment for segment in normalized.split(".") if segment]


def _read_named_socket(
    entries: Any,
    key: str,
) -> Mapping[str, Any] | Any:
    if not isinstance(entries, list):
        return _SENTINEL_NO_VALUE
    if key.isdigit():
        index = int(key)
        return entries[index] if 0 <= index < len(entries) else _SENTINEL_NO_VALUE
    for entry in entries:
        if isinstance(entry, Mapping) and entry.get("name") == key:
            return entry
    return _SENTINEL_NO_VALUE


def _descend_field_value(root: Any, segments: list[str]) -> Any:
    current = root
    for segment in segments:
        if isinstance(current, Mapping):
            if segment not in current:
                return _SENTINEL_NO_VALUE
            current = current[segment]
            continue
        if isinstance(current, list):
            if not segment.isdigit():
                return _SENTINEL_NO_VALUE
            index = int(segment)
            if not 0 <= index < len(current):
                return _SENTINEL_NO_VALUE
            current = current[index]
            continue
        return _SENTINEL_NO_VALUE
    return current


def _read_widget_value(node: Mapping[str, Any], widget_name: str) -> Any:
    widgets = node.get("widgets")
    widgets_values = node.get("widgets_values")
    if isinstance(widgets, list) and isinstance(widgets_values, list):
        for index, widget in enumerate(widgets):
            if (
                isinstance(widget, Mapping)
                and widget.get("name") == widget_name
                and index < len(widgets_values)
            ):
                return widgets_values[index]
    if isinstance(widgets_values, Mapping) and widget_name in widgets_values:
        return widgets_values[widget_name]
    return _SENTINEL_NO_VALUE


def _read_field_value_from_node(
    node: Mapping[str, Any], field_path: str
) -> Any:
    """Read a field from widgets, widgets_values, inputs, outputs, or top-level keys."""
    if not isinstance(field_path, str) or not field_path:
        return _SENTINEL_NO_VALUE
    if field_path == "mode":
        return node["mode"] if "mode" in node else _SENTINEL_NO_VALUE

    segments = _split_field_path(field_path)
    if not segments:
        return _SENTINEL_NO_VALUE

    simple_widget_value = _read_widget_value(node, field_path)
    if simple_widget_value is not _SENTINEL_NO_VALUE:
        return simple_widget_value

    head = segments[0]
    tail = segments[1:]
    if head == "widgets":
        root = _read_named_socket(node.get("widgets"), tail[0]) if tail else node.get("widgets")
        return _descend_field_value(root, tail[1:]) if tail else root
    if head == "widgets_values":
        return _descend_field_value(node.get("widgets_values"), tail)
    if head == "inputs":
        root = _read_named_socket(node.get("inputs"), tail[0]) if tail else node.get("inputs")
        return _descend_field_value(root, tail[1:]) if tail else root
    if head == "outputs":
        root = _read_named_socket(node.get("outputs"), tail[0]) if tail else node.get("outputs")
        return _descend_field_value(root, tail[1:]) if tail else root
    if head in node:
        return _descend_field_value(node, segments)
    return _SENTINEL_NO_VALUE


def _normalize_link_endpoint(node_alias: Any, output_slot: Any) -> Any:
    if not isinstance(node_alias, (int, str)) or output_slot is None:
        return _SENTINEL_NO_VALUE
    return {"uid": str(node_alias), "output_slot": output_slot}


def _link_target_ref(op: Mapping[str, Any]) -> tuple[str | None, str | int | None]:
    target = op.get("to") if "to" in op else op.get("target")
    if isinstance(target, Mapping):
        uid = _normalize_target_uid(target)
        field = target.get("input_field")
        if not isinstance(field, (str, int)):
            field = target.get("field")
        return uid, field if isinstance(field, (str, int)) else None
    if isinstance(target, list) and len(target) >= 3:
        uid = _normalize_target_uid(target)
        field = target[2]
        return uid, field if isinstance(field, (str, int)) else None
    return None, None


def _read_link_source_endpoint(
    index: _GraphIndex,
    *,
    target_uid: str,
    input_field: str | int,
) -> Any:
    node = _find_node_in_index(index, target_uid)
    if node is None:
        return _SENTINEL_NODE_ABSENT
    inputs = node.get("inputs")
    input_entry = _read_named_socket(inputs, str(input_field))
    if input_entry is _SENTINEL_NO_VALUE:
        return _SENTINEL_NO_VALUE
    if not isinstance(input_entry, Mapping):
        return _SENTINEL_NO_VALUE
    link_id = input_entry.get("link")
    if link_id is None:
        return _SENTINEL_LINK_ABSENT
    link = index.links_by_id.get(link_id)
    if link is None:
        link = index.links_by_id.get(str(link_id))
    if isinstance(link, list) and len(link) >= 3:
        origin_id = link[1]
        origin_slot = link[2]
    elif isinstance(link, Mapping):
        origin_id = link.get("origin_id")
        origin_slot = link.get("origin_slot")
    else:
        return _SENTINEL_NO_VALUE
    origin_node = _find_node_in_index(index, origin_id)
    if origin_node is None:
        return _SENTINEL_NO_VALUE
    origin_uid = _canonical_node_uid(origin_node)
    return _normalize_link_endpoint(origin_uid, origin_slot)


def _resolve_candidate_value_for_op(
    candidate_graph: Mapping[str, Any] | None,
    op: Mapping[str, Any],
) -> tuple[Any, str | None]:
    op_kind = op.get("op")
    if not isinstance(op_kind, str):
        return (None, f"Missing or invalid op kind: {op_kind!r}")
    candidate_index = _build_graph_index(candidate_graph) if isinstance(candidate_graph, Mapping) else None
    if op_kind == "set_node_field":
        if "value" in op:
            return (op.get("value"), None)
        target = op.get("target")
        uid = _normalize_target_uid(target)
        field_path = target[2] if isinstance(target, list) and len(target) >= 3 else None
        if candidate_index is None or uid is None or not isinstance(field_path, str):
            return (_SENTINEL_NO_VALUE, "Could not resolve candidate field value.")
        node = _find_node_in_index(candidate_index, uid)
        if node is None:
            return (_SENTINEL_NODE_ABSENT, None)
        return (_read_field_value_from_node(node, field_path), None)
    if op_kind == "set_mode":
        if "mode" in op:
            return (op.get("mode"), None)
        uid = _normalize_target_uid(op.get("target"))
        if candidate_index is None or uid is None:
            return (_SENTINEL_NO_VALUE, "Could not resolve candidate mode.")
        node = _find_node_in_index(candidate_index, uid)
        if node is None:
            return (_SENTINEL_NODE_ABSENT, None)
        return (_read_field_value_from_node(node, "mode"), None)
    if op_kind == "reorder":
        order = op.get("order")
        if isinstance(order, list):
            return (tuple(order), None)
        return (_SENTINEL_NO_VALUE, "Reorder op missing order.")
    if op_kind == "upsert_link":
        source = op.get("from")
        if isinstance(source, list) and len(source) >= 3:
            source_uid = _normalize_target_uid(source)
            output_slot = source[2]
            return (_normalize_link_endpoint(source_uid, output_slot), None)
        target_uid, input_field = _link_target_ref(op)
        if candidate_index is None or target_uid is None or input_field is None:
            return (_SENTINEL_NO_VALUE, "Could not resolve candidate link target.")
        return (
            _read_link_source_endpoint(
                candidate_index, target_uid=target_uid, input_field=input_field
            ),
            None,
        )
    if op_kind == "remove_link":
        return (_SENTINEL_LINK_ABSENT, None)
    if op_kind == "add_node":
        # Canonical: prefer explicit uid, then node_id, then scope_path
        uid = op.get("uid")
        if not (isinstance(uid, str) and uid):
            node_id = op.get("node_id")
            if isinstance(node_id, (int, str)) and str(node_id):
                uid = str(node_id)
            else:
                scope_path = op.get("scope_path")
                if isinstance(scope_path, (str, int)) and str(scope_path):
                    uid = str(scope_path)
                else:
                    uid = None
        if candidate_index is not None and isinstance(uid, str) and uid:
            node = _find_node_in_index(candidate_index, uid)
            if node is not None:
                return (
                    {
                        "uid": _canonical_node_uid(node),
                        "id": node.get("id"),
                        "type": node.get("type"),
                    },
                    None,
                )
        return (
            {
                "uid": uid,
                "class_type": op.get("class_type"),
                "fields": op.get("fields"),
                "inputs": op.get("inputs"),
            },
            None,
        )
    if op_kind == "remove_node":
        return (_SENTINEL_NODE_ABSENT, None)
    return (None, f"Unsupported delta op kind: {op_kind!r}")


def _resolve_submit_value_for_set_node_field(
    submit_graph: Mapping[str, Any],
    op: Mapping[str, Any],
) -> tuple[Any, str | None]:
    """Derive expected_old for a ``set_node_field`` op."""
    target = op.get("target")
    if not isinstance(target, list) or len(target) < 3:
        return (None, "Invalid target for set_node_field op")
    uid = _normalize_target_uid(target)
    field_path = target[2] if len(target) > 2 else None
    if not isinstance(uid, str):
        return (None, f"Invalid uid in target: {uid!r}")
    if not isinstance(field_path, str):
        return (None, f"Invalid field_path in target: {field_path!r}")
    node = _find_node_in_graph(submit_graph, uid)
    if node is None:
        return (_SENTINEL_NODE_ABSENT, None)
    value = _read_field_value_from_node(node, field_path)
    return (value, None)


def _resolve_submit_value_for_set_mode(
    submit_graph: Mapping[str, Any],
    op: Mapping[str, Any],
) -> tuple[Any, str | None]:
    """Derive expected_old for a ``set_mode`` op."""
    target = op.get("target")
    uid = _normalize_target_uid(target)
    if uid is None:
        return (None, "Invalid target for set_mode op")
    node = _find_node_in_graph(submit_graph, uid)
    if node is None:
        return (_SENTINEL_NODE_ABSENT, None)
    return (_read_field_value_from_node(node, "mode"), None)


def _resolve_submit_value_for_reorder(
    submit_graph: Mapping[str, Any],
    op: Mapping[str, Any],
) -> tuple[Any, str | None]:
    """Derive expected_old for a ``reorder`` op (current widget/slot order)."""
    target = op.get("target")
    uid = _normalize_target_uid(target)
    if uid is None:
        return (None, "Invalid target for reorder op")
    node = _find_node_in_graph(submit_graph, uid)
    if node is None:
        return (_SENTINEL_NODE_ABSENT, None)
    axis = op.get("axis")
    if axis == "widgets":
        widgets = node.get("widgets")
        if isinstance(widgets, list):
            return (
                tuple(w.get("name") for w in widgets if isinstance(w, Mapping)),
                None,
            )
        return (_SENTINEL_NO_VALUE, "Could not resolve widget reorder from serialized graph.")
    if axis == "inputs":
        inputs = node.get("inputs")
        if isinstance(inputs, list):
            return (
                tuple(
                    entry.get("name")
                    for entry in inputs
                    if isinstance(entry, Mapping) and entry.get("name") is not None
                ),
                None,
            )
        return (_SENTINEL_NO_VALUE, "Could not resolve input reorder from serialized graph.")
    if axis == "outputs":
        outputs = node.get("outputs")
        if isinstance(outputs, list):
            return (
                tuple(
                    entry.get("name")
                    for entry in outputs
                    if isinstance(entry, Mapping) and entry.get("name") is not None
                ),
                None,
            )
        return (_SENTINEL_NO_VALUE, "Could not resolve output reorder from serialized graph.")
    return (_SENTINEL_NO_VALUE, f"Unsupported reorder axis: {axis!r}")


def _resolve_submit_value_for_upsert_link(
    submit_graph: Mapping[str, Any],
    op: Mapping[str, Any],
) -> tuple[Any, str | None]:
    """Derive expected_old for an ``upsert_link`` op.

    Returns the current link source endpoint ``(origin_uid, origin_slot)``
    connected to the target input, or ``_SENTINEL_NO_VALUE`` if unwired.
    """
    target_uid, input_field = _link_target_ref(op)
    if target_uid is None or input_field is None:
        return (None, "Invalid 'to' ref for upsert_link op")
    value = _read_link_source_endpoint(
        _build_graph_index(submit_graph),
        target_uid=target_uid,
        input_field=input_field,
    )
    return (value, None)


def _resolve_submit_value_for_remove_link(
    submit_graph: Mapping[str, Any],
    op: Mapping[str, Any],
) -> tuple[Any, str | None]:
    """Derive expected_old for a ``remove_link`` op (same as upsert_link --
    what link currently feeds the target input)."""
    return _resolve_submit_value_for_upsert_link(submit_graph, op)


def _resolve_submit_value_for_add_node(
    submit_graph: Mapping[str, Any],
    op: Mapping[str, Any],
) -> tuple[Any, str | None]:
    """Derive expected_old for an ``add_node`` op -- expected absence.

    Checks whether any node in the submit graph already claims the UID or
    LiteGraph id carried by the op payload.  Prefers the canonical ``uid``
    and ``node_id`` fields; only falls back to ``scope_path`` when neither
    explicit identity field is present (legacy flat bridge).

    Returns ``_SENTINEL_NODE_ABSENT`` (absent) on success, or
    ``(existing_node_summary, None)`` if a collision is detected (callers
    treat a non-sentinel value as a conflict signal).
    """
    # Canonical path: explicit uid and node_id take priority over scope_path
    explicit_uid = op.get("uid")
    explicit_node_id = op.get("node_id")

    if isinstance(explicit_uid, str) and explicit_uid:
        existing = _find_node_in_graph(submit_graph, explicit_uid)
        if existing is not None:
            return (
                {
                    "uid": _canonical_node_uid(existing),
                    "id": existing.get("id"),
                    "type": existing.get("type"),
                },
                None,
            )
        # Explicit uid was supplied and no collision was found — expected
        # absence for add_node.
        return (_SENTINEL_NODE_ABSENT, None)

    if isinstance(explicit_node_id, (int, str)) and str(explicit_node_id):
        existing = _find_node_in_graph(submit_graph, str(explicit_node_id))
        if existing is not None:
            return (
                {
                    "uid": _canonical_node_uid(existing),
                    "id": existing.get("id"),
                    "type": existing.get("type"),
                },
                None,
            )
        # Explicit node_id was supplied and no collision was found — expected
        # absence for add_node.
        return (_SENTINEL_NODE_ABSENT, None)

    # Legacy fallback: infer identity from scope_path when neither uid nor
    # node_id is present.  This path exists only for pre-canonical flat
    # delta_ops that have not been re-persisted with explicit identity.
    scope_path = op.get("scope_path")
    if isinstance(scope_path, (str, int)) and str(scope_path):
        uid = str(scope_path)
        existing = _find_node_in_graph(submit_graph, uid)
        if existing is not None:
            return (
                {
                    "uid": _canonical_node_uid(existing),
                    "id": existing.get("id"),
                    "type": existing.get("type"),
                },
                None,
            )
        # Valid scope_path, node not found — expected absence for add_node.
        return (_SENTINEL_NODE_ABSENT, None)

    # A canonical add_node must carry at least one of uid, node_id, or
    # scope_path.  If none are present the op is malformed.
    return (
        None,
        "Missing add_node identity: need uid, node_id, or scope_path.",
    )


def _resolve_submit_value_for_remove_node(
    submit_graph: Mapping[str, Any],
    op: Mapping[str, Any],
) -> tuple[Any, str | None]:
    """Derive expected_old for a ``remove_node`` op -- expected presence.

    Returns a summary of the existing node on success, or
    ``_SENTINEL_NO_VALUE`` if already absent.
    """
    target = op.get("target")
    uid = _normalize_target_uid(target)
    if uid is None:
        return (None, "Invalid target for remove_node op")
    node = _find_node_in_graph(submit_graph, uid)
    if node is None:
        return (_SENTINEL_NODE_ABSENT, None)
    return (
        {
            "uid": _canonical_node_uid(node),
            "id": node.get("id"),
            "type": node.get("type"),
        },
        None,
    )


def _resolve_submit_value_for_op(
    *,
    submit_graph: Mapping[str, Any],
    op: Mapping[str, Any],
) -> tuple[Any, str | None]:
    """Derive ``expected_old`` for a single delta op from the submit-time graph.

    Returns ``(expected_old_value, error_message)``.
    ``error_message`` is ``None`` on success.
    """
    op_kind = op.get("op")
    if not isinstance(op_kind, str):
        return (None, f"Missing or invalid op kind: {op_kind!r}")
    if op_kind == "set_node_field":
        return _resolve_submit_value_for_set_node_field(submit_graph, op)
    if op_kind == "set_mode":
        return _resolve_submit_value_for_set_mode(submit_graph, op)
    if op_kind == "reorder":
        return _resolve_submit_value_for_reorder(submit_graph, op)
    if op_kind == "upsert_link":
        return _resolve_submit_value_for_upsert_link(submit_graph, op)
    if op_kind == "remove_link":
        return _resolve_submit_value_for_remove_link(submit_graph, op)
    if op_kind == "add_node":
        return _resolve_submit_value_for_add_node(submit_graph, op)
    if op_kind == "remove_node":
        return _resolve_submit_value_for_remove_node(submit_graph, op)
    return (None, f"Unsupported delta op kind: {op_kind!r}")


def _status_for_scoped_validation_entry(
    *,
    op_kind: str,
    expected_old: Any,
    actual_before: Any,
    desired_new: Any,
    error: str | None,
) -> str:
    if error is not None:
        return "unscopable"
    if expected_old is _SENTINEL_NO_VALUE or actual_before is _SENTINEL_NO_VALUE:
        return "unscopable"
    if desired_new is _SENTINEL_NO_VALUE:
        return "unscopable"
    if op_kind == "remove_node" and actual_before is _SENTINEL_NODE_ABSENT:
        return "already_absent"
    if op_kind == "add_node":
        return "ok" if actual_before is _SENTINEL_NODE_ABSENT else "conflict"
    if op_kind == "remove_link" and actual_before is _SENTINEL_LINK_ABSENT:
        return "already_absent"
    if expected_old == desired_new:
        return "noop"
    if actual_before == expected_old:
        return "ok"
    if actual_before == desired_new:
        return "already_applied"
    return "conflict"


def _scoped_validation_diagnostic_code(entry: Mapping[str, Any]) -> str:
    error = entry.get("error")
    if isinstance(error, str) and (
        "Unsupported delta op kind" in error or "Missing or invalid op kind" in error
    ):
        return "unsupported_delta_op"
    return "unscopable_delta_op"


def _build_scoped_validation_plan_entry(
    *,
    submit_graph: Mapping[str, Any],
    live_graph: Mapping[str, Any],
    candidate_graph: Mapping[str, Any] | None,
    op: Mapping[str, Any],
) -> dict[str, Any]:
    expected_old, expected_error = _resolve_submit_value_for_op(
        submit_graph=submit_graph,
        op=op,
    )
    actual_before, actual_error = _resolve_submit_value_for_op(
        submit_graph=live_graph,
        op=op,
    )
    desired_new, desired_error = _resolve_candidate_value_for_op(candidate_graph, op)
    op_kind = op.get("op")
    errors = [error for error in (expected_error, actual_error, desired_error) if error]
    error = "; ".join(errors) if errors else None
    return {
        "op": op_kind,
        "target": op.get("target") if "target" in op else op.get("to"),
        "expected_old": _scoped_sentinel_payload(expected_old),
        "actual_before": _scoped_sentinel_payload(actual_before),
        "desired_new": _scoped_sentinel_payload(desired_new),
        "status": _status_for_scoped_validation_entry(
            op_kind=op_kind if isinstance(op_kind, str) else "",
            expected_old=expected_old,
            actual_before=actual_before,
            desired_new=desired_new,
            error=error,
        ),
        "error": error,
    }


def _build_scoped_validation_plan(
    *,
    submit_graph: Mapping[str, Any],
    live_graph: Mapping[str, Any],
    candidate_graph: Mapping[str, Any] | None,
    delta_ops: tuple[dict[str, Any], ...] | list[dict[str, Any]],
) -> dict[str, Any]:
    entries = [
        _build_scoped_validation_plan_entry(
            submit_graph=submit_graph,
            live_graph=live_graph,
            candidate_graph=candidate_graph,
            op=op,
        )
        for op in delta_ops
    ]
    diagnostics = [
        {
            "code": _scoped_validation_diagnostic_code(entry),
            "severity": "error",
            "op": entry.get("op"),
            "target": entry.get("target"),
            "message": entry.get("error") or "Scoped validation could not resolve this op.",
        }
        for entry in entries
        if entry.get("status") == "unscopable"
    ]
    return {
        "entries": entries,
        "diagnostics": diagnostics,
        "ok": not diagnostics,
    }


def _scoped_accept_recovery_payload(
    *,
    turn_id: str,
    submit_graph_hash: str,
    candidate_graph_hash: str,
) -> dict[str, Any]:
    return {
        "action": "rebaseline",
        "endpoint": "/vibecomfy/agent-edit/rebaseline",
        "reason": "scoped_accept_conflict",
        "turn_id": turn_id,
        "submit_graph_hash": submit_graph_hash,
        "candidate_graph_hash": candidate_graph_hash,
    }


def _scoped_issue_node_uid(op: Mapping[str, Any]) -> str | None:
    op_kind = op.get("op")
    if op_kind == "add_node":
        # Canonical: explicit uid takes priority; fall back to scope_path
        # only for legacy flat delta_ops that lack explicit identity.
        uid = op.get("uid")
        if isinstance(uid, str) and uid:
            return uid
        node_id = op.get("node_id")
        if isinstance(node_id, (int, str)) and str(node_id):
            return str(node_id)
        scope_path = op.get("scope_path")
        if isinstance(scope_path, (int, str)) and str(scope_path):
            return str(scope_path)
        return None
    target = op.get("target") if "target" in op else op.get("to")
    return _normalize_target_uid(target)


def _scoped_issue_field_path(op: Mapping[str, Any]) -> str | None:
    op_kind = op.get("op")
    if op_kind == "set_node_field":
        target = op.get("target")
        if isinstance(target, list) and len(target) >= 3:
            field_path = target[2]
            return str(field_path) if isinstance(field_path, (int, str)) else None
        return None
    if op_kind == "set_mode":
        return "mode"
    if op_kind == "reorder":
        axis = op.get("axis")
        return str(axis) if isinstance(axis, str) and axis else None
    return None


def _scoped_issue_link_target(op: Mapping[str, Any]) -> dict[str, Any] | None:
    op_kind = op.get("op")
    if op_kind not in {"upsert_link", "remove_link"}:
        return None
    target_uid, input_field = _link_target_ref(op)
    if target_uid is None or input_field is None:
        return None
    return {"node_uid": target_uid, "input_field": input_field}


def _whole_graph_hash_diagnostic(cas_evidence: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "code": "whole_graph_hash_mismatch",
        "severity": "info",
        "message": "Whole-graph structural CAS mismatched at accept time; v2 used scoped validation instead.",
        "detail": dict(cas_evidence),
    }


def _scoped_accept_issue(
    *,
    op: Mapping[str, Any],
    entry: Mapping[str, Any] | None,
    code: str,
    message: str,
    rebaseline_recovery: Mapping[str, Any],
) -> dict[str, Any]:
    issue = {
        "code": code,
        "op": op.get("op"),
        "node_uid": _scoped_issue_node_uid(op),
        "field_path": _scoped_issue_field_path(op),
        "link_target": _scoped_issue_link_target(op),
        "expected_old": entry.get("expected_old") if isinstance(entry, Mapping) else None,
        "actual_before": entry.get("actual_before") if isinstance(entry, Mapping) else None,
        "desired_new": entry.get("desired_new") if isinstance(entry, Mapping) else None,
        "status": entry.get("status") if isinstance(entry, Mapping) else None,
        "message": message,
        "detail": message,
        "rebaseline_recovery": dict(rebaseline_recovery),
    }
    return {key: value for key, value in issue.items() if value is not None}


def _fail_v2_scoped_accept(
    *,
    scope: Literal["accept"],
    context: TurnContext,
    explanation: str,
    issues: list[dict[str, Any]],
    diagnostics: list[dict[str, Any]] | None = None,
) -> FailureEnvelope:
    agent_failure_context: dict[str, Any] = {
        "explanation": explanation,
        "issues": issues,
    }
    if diagnostics:
        agent_failure_context["diagnostics"] = diagnostics
    return failure_envelope(
        FailureKind.STALE_STATE_MISMATCH,
        scope,
        context,
        agent_failure_context=agent_failure_context,
        queue_allowed=False,
    )


def _build_v2_accept_evidence(
    *,
    session_dir: Path,
    turn_id: str,
    turn_record: Mapping[str, Any],
) -> dict[str, Any]:
    """Load V2 accept evidence from persisted turn/session artifacts.

    Returns a dict with keys:
      * ``submit_graph`` -- the submit-time graph loaded from ``request.json``
      * ``candidate_graph`` -- the candidate graph loaded from ``response.json``
      * ``delta_ops`` -- authoritative mutation-intent list from the canonical
        envelope (preferred) or legacy flat bridge
      * ``delta_shape_diagnostic`` -- classification of the delta payload shape
      * ``submit_graph_hash`` -- hash of the loaded submit graph
      * ``candidate_graph_hash`` -- from the turn record
      * ``protocol`` -- ``"v2_delta"``
      * ``loaded_ok`` -- ``True`` iff required evidence was loaded
      * ``diagnostics`` -- list of evidence-loading issues, classified into
        distinct buckets: *malformed_delta*, *legacy_delta_shape*,
        *unsupported_scoped_apply*, *missing_submit_graph*,
        *missing_candidate_graph*
    """
    from vibecomfy.comfy_nodes.agent.session import payload_hash  # T-045 late import: host namespace lookup; resolved at call time

    evidence: dict[str, Any] = {
        "submit_graph": None,
        "candidate_graph": None,
        "delta_ops": None,
        "delta_shape_diagnostic": None,
        "submit_graph_hash": None,
        "candidate_graph_hash": None,
        "protocol": "v2_delta",
        "loaded_ok": True,
        "diagnostics": [],
    }

    submit_graph = _load_turn_request_graph(session_dir=session_dir, turn_id=turn_id)
    if submit_graph is not None:
        evidence["submit_graph"] = submit_graph
        evidence["submit_graph_hash"] = payload_hash(submit_graph)
    else:
        evidence["loaded_ok"] = False
        evidence["diagnostics"].append(
            {
                "code": "missing_submit_graph",
                "severity": "error",
                "message": "Could not load submit-time graph from turn artifacts.",
            }
        )

    # Classify the delta shape before loading so we can surface legacy /
    # malformed shapes in distinct evidence buckets.
    shape_diag = _load_turn_delta_ops_diagnostic(
        session_dir=session_dir, turn_id=turn_id
    )
    evidence["delta_shape_diagnostic"] = shape_diag

    delta_ops = _load_turn_delta_ops(session_dir=session_dir, turn_id=turn_id)
    if delta_ops is not None:
        evidence["delta_ops"] = delta_ops
        # Optional: surface legacy flat bridge use as an info diagnostic.
        if shape_diag.get("code") == "legacy_delta_ops_flat":
            evidence["diagnostics"].append(
                {
                    "code": "legacy_delta_shape",
                    "severity": "info",
                    "message": (
                        "Delta loaded from legacy flat delta_ops list; "
                        "canonical consumers should migrate to "
                        "delta_ops_envelope."
                    ),
                    "detail": shape_diag.get("detail", {}),
                }
            )
    else:
        evidence["loaded_ok"] = False
        diag_code = shape_diag.get("code", "missing_delta_ops")
        diag_message: str
        if diag_code == "legacy_delta_shape":
            diag_message = (
                "Persisted delta uses a legacy wrapped shape that is not a "
                "canonical V2 envelope; re-persist the turn with a canonical "
                "delta_ops_envelope."
            )
            evidence["delta_ops"] = ()
        elif diag_code == "canonical_envelope_malformed_ops":
            diag_code = "malformed_delta"
            diag_message = (
                "Canonical delta_ops_envelope is present but its `ops` field "
                "is malformed."
            )
        elif diag_code == "missing_turn_response":
            diag_message = "Could not load the persisted turn response."
        else:
            diag_message = (
                "Could not load delta_ops from persisted turn response."
            )
        evidence["diagnostics"].append(
            {
                "code": diag_code,
                "severity": "error",
                "message": diag_message,
                "detail": shape_diag.get("detail", {}),
            }
        )

    candidate_graph_hash = turn_record.get("candidate_graph_hash")
    if isinstance(candidate_graph_hash, str):
        evidence["candidate_graph_hash"] = candidate_graph_hash
    candidate_graph = _load_turn_candidate_graph(session_dir=session_dir, turn_id=turn_id)
    if candidate_graph is not None:
        evidence["candidate_graph"] = candidate_graph
    else:
        evidence["loaded_ok"] = False
        evidence["diagnostics"].append(
            {
                "code": "missing_candidate_graph",
                "severity": "error",
                "message": "Could not load candidate graph from persisted turn response.",
            }
        )

    return evidence


# ── V2 turn-state transition validation ────────────────────────────────────
# This map defines every valid forward transition for V2 lifecycle states.
# It is used by prepare / finalize / rollback routes to reject out-of-order
# requests.  Unknown (superseded) transitions are handled separately in
# allocate_turn and _mutate_turn_state.
_V2_VALID_TRANSITIONS: dict[TurnState, frozenset[TurnState]] = {
    "submitted": frozenset({"candidate_ready"}),
    "candidate_ready": frozenset({"review_bound", "discarded"}),
    "review_bound": frozenset({"prepared", "discarded"}),
    "prepared": frozenset({"canvas_verified", "rollback_complete", "recoverable_error"}),
    "canvas_verified": frozenset({"finalized", "rollback_complete", "recoverable_error"}),
    "recoverable_error": frozenset({"prepared", "canvas_verified", "rollback_complete"}),
    "finalized": frozenset(),  # terminal
    "rollback_complete": frozenset(),  # terminal
    "discarded": frozenset(),  # terminal
    "superseded": frozenset(),  # terminal
}


def _validate_v2_transition(
    *,
    current_state: TurnState,
    target_state: TurnState,
    turn_id: str,
) -> str | None:
    """Return ``None`` if *target_state* is a valid transition from *current_state*.

    Otherwise return a human-readable explanation of why the transition is invalid.
    V1 historical states always produce an error — they must be migrated before
    they can participate in V2 flows.
    """
    from vibecomfy.comfy_nodes.agent.session import (_V1_HISTORICAL_STATES, _V2_TERMINAL_STATES)  # T-045 late import: host namespace lookup; resolved at call time

    if current_state in _V1_HISTORICAL_STATES:
        return (
            f"Turn {turn_id} is in V1 historical state {current_state!r}. "
            f"V2 transitions require a turn allocated under agent_edit_protocol v2_delta."
        )
    if current_state in _V2_TERMINAL_STATES:
        return (
            f"Turn {turn_id} is in V2 terminal state {current_state!r} "
            f"and cannot transition to {target_state!r}."
        )
    valid_targets = _V2_VALID_TRANSITIONS.get(current_state)
    if valid_targets is None:
        return (
            f"Turn {turn_id} has unknown V2 state {current_state!r}."
        )
    if target_state not in valid_targets:
        return (
            f"Turn {turn_id} cannot transition from "
            f"{current_state!r} to {target_state!r}. "
            f"Valid next states: {sorted(valid_targets)}."
        )
    return None


__all__ = (
    "_ScopedValueSentinel",
    "_SENTINEL_NO_VALUE",
    "_SENTINEL_LINK_ABSENT",
    "_SENTINEL_NODE_ABSENT",
    "_GraphIndex",
    "_load_turn_request_graph",
    "_load_turn_response_payload",
    "_load_turn_candidate_graph",
    "_load_turn_delta_ops",
    "_iter_legacy_field_changes",
    "_infer_delta_ops_from_legacy_field_changes",
    "_load_turn_delta_ops_diagnostic",
    "_scoped_sentinel_payload",
    "_build_graph_index",
    "_canonical_node_uid",
    "_normalize_target_uid",
    "_find_node_in_index",
    "_find_node_in_graph",
    "_split_field_path",
    "_read_named_socket",
    "_descend_field_value",
    "_read_widget_value",
    "_read_field_value_from_node",
    "_normalize_link_endpoint",
    "_link_target_ref",
    "_read_link_source_endpoint",
    "_resolve_candidate_value_for_op",
    "_resolve_submit_value_for_set_node_field",
    "_resolve_submit_value_for_set_mode",
    "_resolve_submit_value_for_reorder",
    "_resolve_submit_value_for_upsert_link",
    "_resolve_submit_value_for_remove_link",
    "_resolve_submit_value_for_add_node",
    "_resolve_submit_value_for_remove_node",
    "_resolve_submit_value_for_op",
    "_status_for_scoped_validation_entry",
    "_scoped_validation_diagnostic_code",
    "_build_scoped_validation_plan_entry",
    "_build_scoped_validation_plan",
    "_scoped_accept_recovery_payload",
    "_scoped_issue_node_uid",
    "_scoped_issue_field_path",
    "_scoped_issue_link_target",
    "_whole_graph_hash_diagnostic",
    "_scoped_accept_issue",
    "_fail_v2_scoped_accept",
    "_build_v2_accept_evidence",
    "_V2_VALID_TRANSITIONS",
    "_validate_v2_transition",
)
