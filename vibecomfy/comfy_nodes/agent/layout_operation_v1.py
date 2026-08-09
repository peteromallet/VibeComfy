"""``layout_operation_v1`` — closed four-op layout grammar (Python owner).

Cross-language contract for root-scoped, stable-ID-only layout operations.
Identity is **never** title, native id, position, class, or array index: it is
the stable ``uid`` (nodes) / ``id`` (groups).  Duplicate titles are valid and
remain distinct.

Envelope (frozen, identical JS + Python)::

    {
      "contract_version": "layout_operation_v1",
      "wire_version": "1.0.0",
      "ops": [ <LayoutOp>, ... ],
      "digest": "<64-hex>"
    }

The four ops form a closed grammar:

  * ``set_node_geometry`` — ``{op, uid, pos}`` (``size`` optional).
  * ``add_group``         — ``{op, id, bounding, title, color}``.
  * ``set_group_geometry``— ``{op, id}`` plus >=1 changed value from the
    ``add_group`` field set (``bounding`` / ``title`` / ``color``).
  * ``remove_group``      — ``{op, id}``.

Every numeric component of ``pos`` / ``size`` / ``bounding`` is normalised
through ``canonicalize_contract_numeric`` (finite error code
``non_finite_geometry``) before any geometry check, so integer-valued floats
(``1.0``), ``-0.0``, and exponents (``1e2``) collapse to their JS-compatible
integer spelling rather than being rejected.  Non-finite values
(``NaN`` / ``±Infinity``) fail closed with ``non_finite_geometry``.

Hashing identity is the shared leaf (``_canonical_contract_primitives``): this
module imports ``ContractError``, ``canonical_json_bytes_v1`` / ``_hash`` and
``canonicalize_contract_numeric`` from the leaf — **not** from
``projection_registry_v1`` — to avoid the import cycle with the common
authority validator.  No second hash owner, no second canonicaliser.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from ._canonical_contract_primitives import (
    ContractError,
    _hash,
    canonicalize_contract_numeric,
)

LAYOUT_OPERATION_CONTRACT_V1 = "layout_operation_v1"
LAYOUT_OPERATION_WIRE_VERSION = "1.0.0"
LAYOUT_OPERATION_OP_NAMES = (
    "set_node_geometry",
    "add_group",
    "set_group_geometry",
    "remove_group",
)

_ENVELOPE_KEYS = frozenset(
    {"contract_version", "wire_version", "ops", "digest"}
)

# Closed per-op key sets.
_SET_NODE_GEOMETRY_KEYS = frozenset({"op", "uid", "pos", "size"})
_ADD_GROUP_KEYS = frozenset({"op", "id", "bounding", "title", "color"})
_SET_GROUP_GEOMETRY_KEYS = frozenset({"op", "id", "bounding", "title", "color"})
_REMOVE_GROUP_KEYS = frozenset({"op", "id"})
_GROUP_CHANGEABLE_KEYS = frozenset({"bounding", "title", "color"})


class LayoutOperationError(ContractError):
    """Typed contract violation for ``layout_operation_v1``."""


def _fail(message: str, code: str, **detail: Any) -> LayoutOperationError:
    error = LayoutOperationError(message, code)
    # Attach a detail mapping for parity with JS ``Error.detail``.
    object.__setattr__(error, "detail", dict(detail))
    return error


def _require_nonempty_str(value: Any, name: str) -> str:
    if not isinstance(value, str) or not value:
        raise _fail(f"Missing stable {name}", "missing_identity", field=name)
    return value


def _geometry_vector(value: Any, length: int, field: str) -> list[int | float]:
    """Normalise then structurally check a finite-number vector."""
    try:
        normalized = canonicalize_contract_numeric(
            value, finite_error_code="non_finite_geometry"
        )
    except ContractError as exc:
        # The shared normaliser is leaf-owned and raises the base ContractError;
        # surface it as this module's typed error with the same diagnostic code.
        raise _fail(str(exc), exc.code, field=field) from exc
    if not isinstance(normalized, list) or len(normalized) != length:
        raise _fail(
            f"{field} must be a list of {length} finite numbers",
            "malformed_layout_op",
            field=field,
        )
    for component in normalized:
        # canonicalize already rejected bool / non-finite; remaining
        # non-numbers (strings, None, nested) are structural errors.
        if isinstance(component, bool) or not isinstance(component, (int, float)):
            raise _fail(
                f"{field} must contain finite numbers",
                "malformed_layout_op",
                field=field,
            )
    return normalized


def _build_op(op_name: str, raw: Mapping[str, Any], *, keys: frozenset[str]) -> dict[str, Any]:
    """Copy only the closed key set, preserving order: op first, then sorted."""
    result: dict[str, Any] = {"op": op_name}
    for key in sorted(k for k in raw if k != "op"):
        result[key] = raw[key]
    return result


def _normalize_layout_op(raw: Any) -> dict[str, Any]:
    if not isinstance(raw, Mapping):
        raise _fail("layout op must be an object", "malformed_layout_op")
    op_name = raw.get("op")
    if not isinstance(op_name, str) or not op_name:
        raise _fail(
            "layout op must have a non-empty string \"op\"",
            "malformed_layout_op",
        )
    if op_name not in LAYOUT_OPERATION_OP_NAMES:
        raise _fail(
            f"Unsupported layout op \"{op_name}\"",
            "unsupported_layout_op",
            op=op_name,
        )

    if op_name == "set_node_geometry":
        extras = sorted(k for k in raw if k not in _SET_NODE_GEOMETRY_KEYS)
        if extras:
            raise _fail(
                f"Unknown layout op key(s): {', '.join(extras)}",
                "malformed_layout_op",
                keys=extras,
            )
        uid = _require_nonempty_str(raw.get("uid"), "node uid")
        pos = _geometry_vector(raw.get("pos"), 2, "pos")
        normalized: dict[str, Any] = {"op": op_name, "uid": uid, "pos": pos}
        if "size" in raw and raw.get("size") is not None:
            normalized["size"] = _geometry_vector(raw.get("size"), 2, "size")
        return normalized

    if op_name == "add_group":
        extras = sorted(k for k in raw if k not in _ADD_GROUP_KEYS)
        if extras:
            raise _fail(
                f"Unknown layout op key(s): {', '.join(extras)}",
                "malformed_layout_op",
                keys=extras,
            )
        group_id = _require_nonempty_str(raw.get("id"), "group id")
        bounding = _geometry_vector(raw.get("bounding"), 4, "bounding")
        title = raw.get("title")
        if not isinstance(title, str):
            raise _fail(
                "add_group title must be a string",
                "malformed_layout_op",
                field="title",
            )
        color = raw.get("color")
        if color is not None and not isinstance(color, str):
            raise _fail(
                "add_group color must be a string or null",
                "malformed_layout_op",
                field="color",
            )
        return {
            "op": op_name,
            "id": group_id,
            "bounding": bounding,
            "title": title,
            "color": color,
        }

    if op_name == "set_group_geometry":
        extras = sorted(k for k in raw if k not in _SET_GROUP_GEOMETRY_KEYS)
        if extras:
            raise _fail(
                f"Unknown layout op key(s): {', '.join(extras)}",
                "malformed_layout_op",
                keys=extras,
            )
        group_id = _require_nonempty_str(raw.get("id"), "group id")
        changed = sorted(k for k in _GROUP_CHANGEABLE_KEYS if k in raw)
        if not changed:
            raise _fail(
                "set_group_geometry must change at least one of bounding/title/color",
                "malformed_layout_op",
            )
        result: dict[str, Any] = {"op": op_name, "id": group_id}
        if "bounding" in raw:
            result["bounding"] = _geometry_vector(raw.get("bounding"), 4, "bounding")
        if "title" in raw:
            title = raw.get("title")
            if not isinstance(title, str):
                raise _fail(
                    "set_group_geometry title must be a string",
                    "malformed_layout_op",
                    field="title",
                )
            result["title"] = title
        if "color" in raw:
            color = raw.get("color")
            if color is not None and not isinstance(color, str):
                raise _fail(
                    "set_group_geometry color must be a string or null",
                    "malformed_layout_op",
                    field="color",
                )
            result["color"] = color
        return result

    # remove_group
    extras = sorted(k for k in raw if k not in _REMOVE_GROUP_KEYS)
    if extras:
        raise _fail(
            f"Unknown layout op key(s): {', '.join(extras)}",
            "malformed_layout_op",
            keys=extras,
        )
    group_id = _require_nonempty_str(raw.get("id"), "group id")
    return {"op": op_name, "id": group_id}


def _identity_for_op(normalized: Mapping[str, Any]) -> str:
    op_name = normalized["op"]
    if op_name == "set_node_geometry":
        return normalized["uid"]
    return normalized["id"]


def _normalize_ops(raw_ops: Any) -> list[dict[str, Any]]:
    if not isinstance(raw_ops, list):
        raise _fail("layout ops must be an array", "malformed_layout_operation")
    normalized_ops = [_normalize_layout_op(op) for op in raw_ops]
    # Within-class duplicate identity is a conflict (cross-class sequences such
    # as add_group -> set_group_geometry on the same id remain legal).
    seen: set[tuple[str, str]] = set()
    for op in normalized_ops:
        key = (op["op"], _identity_for_op(op))
        if key in seen:
            raise _fail(
                f"Duplicate layout identity for op {op['op']!r}",
                "duplicate_identity",
                op=op["op"],
                identity=_identity_for_op(op),
            )
        seen.add(key)
    return normalized_ops


def compute_layout_operation_digest(ops: Any) -> str:
    """Canonical SHA-256 of ``{contract_version, wire_version, ops}``.

    ``ops`` are validated and numerically normalised before hashing so the
    preimage is byte-identical to the JS mirror.
    """
    normalized_ops = _normalize_ops(ops)
    preimage = {
        "contract_version": LAYOUT_OPERATION_CONTRACT_V1,
        "wire_version": LAYOUT_OPERATION_WIRE_VERSION,
        "ops": normalized_ops,
    }
    return _hash(preimage)


def normalize_layout_operation_v1(envelope: Any) -> dict[str, Any]:
    """Validate shape + ops and return the canonical frozen envelope.

    The returned ``digest`` is always the *recomputed* canonical digest; the
    input ``digest`` (if any) is not trusted.  Use
    :func:`assert_layout_operation_envelope` to verify a claimed digest.
    """
    if not isinstance(envelope, Mapping):
        raise _fail(
            "layout operation envelope must be an object",
            "malformed_layout_operation",
        )
    extras = sorted(k for k in envelope if k not in _ENVELOPE_KEYS)
    if extras:
        raise _fail(
            f"Unknown layout operation envelope key(s): {', '.join(extras)}",
            "malformed_layout_operation",
            keys=extras,
        )
    if envelope.get("contract_version") != LAYOUT_OPERATION_CONTRACT_V1:
        raise _fail(
            "Unknown layout operation contract version",
            "unknown_contract",
        )
    if envelope.get("wire_version") != LAYOUT_OPERATION_WIRE_VERSION:
        raise _fail(
            "Unsupported layout operation wire version",
            "unsupported_wire_version",
        )
    normalized_ops = _normalize_ops(envelope.get("ops"))
    digest = _hash(
        {
            "contract_version": LAYOUT_OPERATION_CONTRACT_V1,
            "wire_version": LAYOUT_OPERATION_WIRE_VERSION,
            "ops": normalized_ops,
        }
    )
    return {
        "contract_version": LAYOUT_OPERATION_CONTRACT_V1,
        "wire_version": LAYOUT_OPERATION_WIRE_VERSION,
        "ops": normalized_ops,
        "digest": digest,
    }


def assert_layout_operation_envelope(value: Any) -> dict[str, Any]:
    """Validate the envelope *and* verify its claimed digest matches.

    Raises :class:`LayoutOperationError` with ``code="layout_operation_digest_mismatch"``
    when the envelope's ``digest`` does not equal the recomputed canonical
    digest.  Returns the canonical frozen envelope on success.
    """
    normalized = normalize_layout_operation_v1(value)
    if not isinstance(value, Mapping):
        # normalize already raised; defensive only.
        raise _fail("layout operation envelope must be an object", "malformed_layout_operation")
    claimed = value.get("digest")
    if claimed != normalized["digest"]:
        raise _fail(
            "Layout operation digest mismatch",
            "layout_operation_digest_mismatch",
        )
    return normalized


def _layout_node_uid(node: Mapping[str, Any]) -> str:
    """Stable node identity: ``vibecomfy_uid`` (or nested property) else ``id``."""
    properties = node.get("properties")
    nested = properties.get("vibecomfy_uid") if isinstance(properties, Mapping) else None
    value = node.get("vibecomfy_uid") if node.get("vibecomfy_uid") is not None else nested
    if value not in (None, ""):
        return str(value)
    return str(node.get("id", ""))


def _layout_group_id(group: Mapping[str, Any]) -> str:
    """Stable group identity: ``vibecomfy_group_id`` else ``id``."""
    value = group.get("vibecomfy_group_id")
    if value in (None, ""):
        value = group.get("id")
    return str(value) if value not in (None, "") else ""


def build_layout_operation_envelope(
    submit_ui: Mapping[str, Any] | None,
    candidate_ui: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """Derive the canonical layout operation envelope from a graph diff.

    Layout-family candidates (``layout_structural_noop``) carry no semantic
    delta; their forward mutation is the candidate layout itself.  This builds
    the operation envelope from the observable node/group geometry difference
    between the submit UI and the candidate UI, so the durable
    transaction binds reproducible layout evidence.

    Ops are emitted deterministically (nodes by stable uid, groups by stable
    id); geometry values are copied verbatim and normalised by the digest
    preimage, matching the JS mirror.
    """
    submit_nodes: dict[str, Mapping[str, Any]] = {}
    for node in submit_ui.get("nodes", ()) if isinstance(submit_ui, Mapping) else ():
        if isinstance(node, Mapping):
            submit_nodes[_layout_node_uid(node)] = node
    candidate_nodes: dict[str, Mapping[str, Any]] = {}
    for node in candidate_ui.get("nodes", ()) if isinstance(candidate_ui, Mapping) else ():
        if isinstance(node, Mapping):
            candidate_nodes[_layout_node_uid(node)] = node
    submit_groups: dict[str, Mapping[str, Any]] = {}
    for group in submit_ui.get("groups", ()) if isinstance(submit_ui, Mapping) else ():
        if isinstance(group, Mapping):
            submit_groups[_layout_group_id(group)] = group
    candidate_groups: dict[str, Mapping[str, Any]] = {}
    for group in candidate_ui.get("groups", ()) if isinstance(candidate_ui, Mapping) else ():
        if isinstance(group, Mapping):
            candidate_groups[_layout_group_id(group)] = group

    ops: list[dict[str, Any]] = []
    for uid in sorted(candidate_nodes):
        node = candidate_nodes[uid]
        prev = submit_nodes.get(uid)
        pos = node.get("pos")
        size = node.get("size")
        # No geometry on the candidate side: nothing representable as a
        # set_node_geometry op (normalize requires at least ``pos``).
        if pos is None and size is None:
            continue
        prev_pos = prev.get("pos") if prev is not None else None
        prev_size = prev.get("size") if prev is not None else None
        if pos == prev_pos and size == prev_size:
            continue
        op: dict[str, Any] = {"op": "set_node_geometry", "uid": uid}
        if pos is not None:
            op["pos"] = pos
        if size is not None:
            op["size"] = size
        ops.append(op)

    for gid in sorted(candidate_groups):
        group = candidate_groups[gid]
        prev = submit_groups.get(gid)
        if prev is None:
            # normalize requires ``bounding`` for add_group; skip groups that
            # carry no geometry at all.
            if group.get("bounding") is None:
                continue
            op: dict[str, Any] = {"op": "add_group", "id": gid}
            for key in ("bounding", "title", "color"):
                value = group.get(key)
                if value is not None:
                    op[key] = value
            ops.append(op)
        else:
            changed: dict[str, Any] = {}
            for key in ("bounding", "title", "color"):
                value = group.get(key)
                if value != prev.get(key) and value is not None:
                    changed[key] = value
            if changed:
                ops.append({"op": "set_group_geometry", "id": gid, **changed})

    for gid in sorted(submit_groups):
        if gid not in candidate_groups:
            ops.append({"op": "remove_group", "id": gid})

    return {
        "contract_version": LAYOUT_OPERATION_CONTRACT_V1,
        "wire_version": LAYOUT_OPERATION_WIRE_VERSION,
        "ops": ops,
        "digest": compute_layout_operation_digest(ops),
    }


__all__ = [
    "LAYOUT_OPERATION_CONTRACT_V1",
    "LAYOUT_OPERATION_WIRE_VERSION",
    "LAYOUT_OPERATION_OP_NAMES",
    "LayoutOperationError",
    "compute_layout_operation_digest",
    "normalize_layout_operation_v1",
    "assert_layout_operation_envelope",
    "build_layout_operation_envelope",
]
