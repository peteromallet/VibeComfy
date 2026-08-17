"""``mutation_materialization_v1`` — bound native-construction payload for add_node.

A materialization envelope accompanies **one** delta envelope — either the
forward ``operation.ops`` or an inverse ``restoration_strategy.payload.ops``.
Each entry binds exactly one ``add_node`` op **in that accompanying envelope**
and carries only the native construction data that is *not* already
authoritative in the op (the op already carries ``uid``, ``node_id``,
``class_type``, ``fields``, ``inputs``; these MUST NOT be duplicated here).

Envelope (frozen, identical JS + Python)::

    {
      "contract_version": "mutation_materialization_v1",
      "wire_version": "1.0.0",
      "entries": [ <MaterializationEntry>, ... ],
      "digest": "<64-hex>"
    }

Entry (closed keys; ``widgets_values``/``pos``/``size``/``opaque`` optional)::

    {
      "source_op_index": <int>,     # index into the accompanying delta ops
      "kind": "add_node",           # the ONLY permitted kind
      "widgets_values": [...],      # optional; native LiteGraph array, or object
                                    #   only when bound add_node.class_type == "vibecomfy.exec"
      "pos": [n, n],                # optional; finite construction geometry
      "size": [n, n],               # optional; finite construction geometry
      "opaque": { ... }             # optional; extension-owned, passed through
    }

No implicit links: the entry has NO ``links``/``inputs``/``fields``/``uid``/
``node_id``/``class_type`` key.  There is no ``remove_node_inverse`` kind and no
candidate-graph source.

Digest (folds in the accompanying ops, so re-binding is detectable)::

    digest = sha256Hex({
      contract_version, wire_version,
      entries: <normalised, ascending by source_op_index>,
      accompanying_ops_digest: sha256Hex(<accompanyingOps canonical form>)
    })

Hashing identity is the shared leaf (``_canonical_contract_primitives``).
"""

from __future__ import annotations

from vibecomfy.ingest.door_access import door_widgets_values
from collections import Counter
from collections.abc import Mapping, Sequence
from typing import Any

from ._canonical_contract_primitives import (
    ContractError,
    _hash,
    canonicalize_contract_numeric,
)

MUTATION_MATERIALIZATION_CONTRACT_V1 = "mutation_materialization_v1"
MUTATION_MATERIALIZATION_WIRE_VERSION = "1.0.0"
MATERIALIZATION_KINDS = ("add_node",)

_ENVELOPE_KEYS = frozenset(
    {"contract_version", "wire_version", "entries", "digest"}
)
_ENTRY_KEYS = frozenset(
    {"source_op_index", "kind", "widgets_values", "pos", "size", "opaque"}
)
# Op-authoritative fields that MUST NOT be duplicated on the entry.
_FORBIDDEN_ENTRY_KEYS = frozenset(
    {"links", "inputs", "fields", "uid", "node_id", "class_type"}
)


class MutationMaterializationError(ContractError):
    """Typed contract violation for ``mutation_materialization_v1``."""


def _fail(message: str, code: str, **detail: Any) -> MutationMaterializationError:
    error = MutationMaterializationError(message, code)
    object.__setattr__(error, "detail", dict(detail))
    return error


def _geo_vector(value: Any, length: int, field: str) -> list[int | float]:
    try:
        normalized = canonicalize_contract_numeric(
            value, finite_error_code="non_finite_materialization"
        )
    except ContractError as exc:
        raise _fail(str(exc), exc.code, field=field) from exc
    if not isinstance(normalized, list) or len(normalized) != length:
        raise _fail(
            f"{field} must be a list of {length} finite numbers",
            "malformed_materialization_entry",
            field=field,
        )
    for component in normalized:
        if isinstance(component, bool) or not isinstance(component, (int, float)):
            raise _fail(
                f"{field} must contain finite numbers",
                "malformed_materialization_entry",
                field=field,
            )
    return normalized


def _normalize_entry(raw: Any) -> dict[str, Any]:
    if not isinstance(raw, Mapping):
        raise _fail(
            "materialization entry must be an object",
            "malformed_materialization_entry",
        )
    keys = set(raw.keys())
    forbidden = sorted(keys & _FORBIDDEN_ENTRY_KEYS)
    if forbidden:
        raise _fail(
            f"materialization entry carries forbidden key(s): {', '.join(forbidden)}",
            "malformed_materialization_entry",
            keys=forbidden,
        )
    extras = sorted(keys - _ENTRY_KEYS)
    if extras:
        raise _fail(
            f"Unknown materialization entry key(s): {', '.join(extras)}",
            "malformed_materialization_entry",
            keys=extras,
        )
    if "source_op_index" not in raw:
        raise _fail(
            "materialization entry requires source_op_index",
            "malformed_materialization_entry",
            field="source_op_index",
        )
    if raw.get("kind") not in MATERIALIZATION_KINDS:
        raise _fail(
            f"Unsupported materialization kind {raw.get('kind')!r}",
            "unsupported_materialization_kind",
            kind=raw.get("kind"),
        )
    result: dict[str, Any] = {"source_op_index": raw["source_op_index"], "kind": "add_node"}
    if "widgets_values" in raw:
        wv = door_widgets_values(raw)
        if wv is None:
            raise _fail(
                "widgets_values may not be null (absent or a value)",
                "malformed_materialization_entry",
                field="widgets_values",
            )
        if not isinstance(wv, (list, dict)):
            raise _fail(
                "widgets_values must be an array (or object for vibecomfy.exec)",
                "malformed_materialization_entry",
                field="widgets_values",
            )
        result = {**result, "widgets_values": _clone_jsonish(wv)}
    if "pos" in raw and raw.get("pos") is not None:
        result["pos"] = _geo_vector(raw.get("pos"), 2, "pos")
    if "size" in raw and raw.get("size") is not None:
        result["size"] = _geo_vector(raw.get("size"), 2, "size")
    if "opaque" in raw and raw.get("opaque") is not None:
        opaque = raw.get("opaque")
        if not isinstance(opaque, Mapping):
            raise _fail(
                "opaque must be a JSON object",
                "malformed_materialization_entry",
                field="opaque",
            )
        result["opaque"] = _clone_jsonish(opaque)
    return result


def _clone_jsonish(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(k): _clone_jsonish(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_clone_jsonish(v) for v in value]
    return value


def _normalize_entries(raw_entries: Any) -> list[dict[str, Any]]:
    if not isinstance(raw_entries, list):
        raise _fail(
            "materialization entries must be an array",
            "malformed_materialization",
        )
    return [_normalize_entry(entry) for entry in raw_entries]


def _accompanying_ops_digest(accompanying_ops: Any) -> str:
    try:
        normalized_ops = canonicalize_contract_numeric(
            accompanying_ops,
            finite_error_code="non_finite_materialization",
            allow_bool=True,
        )
    except ContractError as exc:
        raise _fail(str(exc), exc.code) from exc
    return _hash(normalized_ops)


def compute_mutation_materialization_digest(
    entries: Any, accompanying_ops: Any
) -> str:
    """Canonical digest of ``{contract_version, wire_version, entries, accompanying_ops_digest}``.

    ``entries`` are structurally validated and numerically normalised, then
    sorted ascending by ``source_op_index``; ``accompanying_ops`` are
    numerically normalised and hashed.  The preimage is byte-identical to the
    JS mirror.
    """
    normalized_entries = _normalize_entries(entries)
    preimage = {
        "contract_version": MUTATION_MATERIALIZATION_CONTRACT_V1,
        "wire_version": MUTATION_MATERIALIZATION_WIRE_VERSION,
        "entries": sorted(normalized_entries, key=lambda e: e["source_op_index"]),
        "accompanying_ops_digest": _accompanying_ops_digest(accompanying_ops),
    }
    return _hash(preimage)


def build_mutation_materialization_v1(accompanying_ops: Any) -> dict[str, Any]:
    """Build the minimal canonical native-construction witness for add-node ops.

    The add-node delta already owns node identity, type, fields, and inputs.
    Optional LiteGraph-only construction details may be added by richer
    producers later; every add-node still needs a bound entry even when there
    are no such extras.
    """
    ops = _validate_accompanying_ops(accompanying_ops)
    entries = [
        {"source_op_index": index, "kind": "add_node"}
        for index, op in enumerate(ops)
        if op.get("op") == "add_node"
    ]
    envelope = {
        "contract_version": MUTATION_MATERIALIZATION_CONTRACT_V1,
        "wire_version": MUTATION_MATERIALIZATION_WIRE_VERSION,
        "entries": entries,
        "digest": compute_mutation_materialization_digest(entries, ops),
    }
    return assert_mutation_materialization_envelope(envelope, accompanying_ops=ops)


def normalize_mutation_materialization_v1(
    envelope: Any, *, accompanying_ops: Any
) -> dict[str, Any]:
    """Validate shape + entries and return the canonical envelope.

    The returned ``digest`` is always the recomputed canonical digest (which
    folds in ``accompanying_ops``); the input ``digest`` is not trusted.
    """
    if not isinstance(envelope, Mapping):
        raise _fail(
            "materialization envelope must be an object",
            "malformed_materialization",
        )
    extras = sorted(k for k in envelope if k not in _ENVELOPE_KEYS)
    if extras:
        raise _fail(
            f"Unknown materialization envelope key(s): {', '.join(extras)}",
            "malformed_materialization",
            keys=extras,
        )
    if envelope.get("contract_version") != MUTATION_MATERIALIZATION_CONTRACT_V1:
        raise _fail(
            "Unknown materialization contract version",
            "unknown_contract",
        )
    if envelope.get("wire_version") != MUTATION_MATERIALIZATION_WIRE_VERSION:
        raise _fail(
            "Unsupported materialization wire version",
            "unsupported_wire_version",
        )
    normalized_entries = _normalize_entries(envelope.get("entries"))
    preimage = {
        "contract_version": MUTATION_MATERIALIZATION_CONTRACT_V1,
        "wire_version": MUTATION_MATERIALIZATION_WIRE_VERSION,
        "entries": sorted(normalized_entries, key=lambda e: e["source_op_index"]),
        "accompanying_ops_digest": _accompanying_ops_digest(accompanying_ops),
    }
    return {
        "contract_version": MUTATION_MATERIALIZATION_CONTRACT_V1,
        "wire_version": MUTATION_MATERIALIZATION_WIRE_VERSION,
        "entries": preimage["entries"],
        "digest": _hash(preimage),
    }


def _validate_accompanying_ops(accompanying_ops: Any) -> list[Mapping[str, Any]]:
    if not isinstance(accompanying_ops, Sequence) or isinstance(
        accompanying_ops, (str, bytes)
    ):
        raise _fail(
            "accompanyingOps must be a non-empty array of canonical delta ops",
            "malformed_materialization",
        )
    if len(accompanying_ops) == 0:
        raise _fail(
            "accompanyingOps must be a non-empty array of canonical delta ops",
            "malformed_materialization",
        )
    ops: list[Mapping[str, Any]] = []
    for item in accompanying_ops:
        if not isinstance(item, Mapping) or not isinstance(item.get("op"), str):
            raise _fail(
                "accompanyingOps must be canonical delta ops",
                "malformed_materialization",
            )
        ops.append(item)
    return ops


def assert_mutation_materialization_envelope(
    envelope: Any, *, accompanying_ops: Any
) -> dict[str, Any]:
    """Validate envelope shape, every entry, the cross-binding against
    ``accompanying_ops``, and the digest.

    Raises :class:`MutationMaterializationError` on any §2.2–§2.4 violation;
    returns the canonical envelope on success.
    """
    ops = _validate_accompanying_ops(accompanying_ops)
    normalized = normalize_mutation_materialization_v1(
        envelope, accompanying_ops=accompanying_ops
    )
    entries = normalized["entries"]

    add_node_indices = {
        i for i, op in enumerate(ops) if op.get("op") == "add_node"
    }

    # Collision detection (Gate #2 / §2.4). Two entries sharing a
    # source_op_index that resolves to an add_node means a surplus entry is
    # piling onto an already-bound add_node (unreferenced_materialization_entry);
    # a collision over a non-binding index is a pure duplicate
    # (duplicate_materialization_source_op).
    index_counts = Counter(entry["source_op_index"] for entry in entries)
    for value, count in sorted(index_counts.items()):
        if count < 2:
            continue
        if value in add_node_indices:
            raise _fail(
                f"Surplus materialization entry for add_node at index {value}",
                "unreferenced_materialization_entry",
                source_op_index=value,
            )
        raise _fail(
            f"Duplicate materialization source_op_index {value}",
            "duplicate_materialization_source_op",
            source_op_index=value,
        )

    # Range + kind + widgets_values class-type pin per entry.
    for entry in entries:
        idx = entry["source_op_index"]
        if (
            isinstance(idx, bool)
            or not isinstance(idx, int)
            or idx < 0
            or idx >= len(ops)
        ):
            raise _fail(
                f"materialization source_op_index {idx!r} out of range",
                "materialization_source_op_index_out_of_range",
                source_op_index=idx,
            )
        op = ops[idx]
        if op.get("op") != "add_node":
            raise _fail(
                f"materialization source_op_index {idx} is not an add_node",
                "materialization_source_op_kind_mismatch",
                source_op_index=idx,
                op_kind=op.get("op"),
            )
        if "widgets_values" in entry:
            class_type = op.get("class_type")
            wv = door_widgets_values(entry)
            if class_type == "vibecomfy.exec":
                if not isinstance(wv, (list, dict)):
                    raise _fail(
                        "vibecomfy.exec widgets_values must be array or object",
                        "malformed_materialization_entry",
                        field="widgets_values",
                    )
            elif not isinstance(wv, list):
                raise _fail(
                    "widgets_values must be an array for non-vibecomfy.exec nodes",
                    "malformed_materialization_entry",
                    field="widgets_values",
                )

    # Coverage: every add_node needs exactly one entry.
    entry_indices = {entry["source_op_index"] for entry in entries}
    for index in sorted(add_node_indices):
        if index not in entry_indices:
            raise _fail(
                f"add_node at index {index} has no materialization entry",
                "missing_materialization_entry",
                source_op_index=index,
            )

    # Digest (folds in accompanying ops — rebind is detectable).
    claimed = envelope.get("digest") if isinstance(envelope, Mapping) else None
    if claimed != normalized["digest"]:
        raise _fail(
            "mutation materialization digest mismatch",
            "mutation_materialization_digest_mismatch",
            accompanying_ops_bound=True,
        )
    return normalized


__all__ = [
    "MUTATION_MATERIALIZATION_CONTRACT_V1",
    "MUTATION_MATERIALIZATION_WIRE_VERSION",
    "MATERIALIZATION_KINDS",
    "MutationMaterializationError",
    "compute_mutation_materialization_digest",
    "build_mutation_materialization_v1",
    "normalize_mutation_materialization_v1",
    "assert_mutation_materialization_envelope",
]
