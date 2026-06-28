from __future__ import annotations

import contextlib
import contextvars
from typing import Any, Mapping

from vibecomfy.porting.emit.diagnostics import EmissionDiagnostic
from vibecomfy.porting.object_info import (
    ObjectInfoIdentity,
    class_defaults,
    resolve_class_entry,
)

# --- Node-local object_info identity plumbing --------------------------------

_NODE_OBJECT_INFO_IDENTITIES: contextvars.ContextVar[
    "dict[str, ObjectInfoIdentity] | None"
] = contextvars.ContextVar("_NODE_OBJECT_INFO_IDENTITIES", default=None)

_NODE_OBJECT_INFO_LOOKUP_WARNINGS: contextvars.ContextVar[
    "list[tuple[str | None, str, str, str]] | None"
] = contextvars.ContextVar("_NODE_OBJECT_INFO_LOOKUP_WARNINGS", default=None)


@contextlib.contextmanager
def _use_object_info_identities(
    identities: "dict[str, Any] | None",
):
    """Bind an optional ``node_id -> ObjectInfoIdentity`` map for this emit."""
    normalized: "dict[str, ObjectInfoIdentity] | None" = None
    if identities:
        normalized = {}
        for raw_id, ident in identities.items():
            if ident is None:
                continue
            if isinstance(ident, ObjectInfoIdentity):
                normalized[str(raw_id)] = ident
            elif isinstance(ident, Mapping):
                try:
                    normalized[str(raw_id)] = ObjectInfoIdentity(
                        pack_slug=str(ident.get("pack_slug") or ident.get("pack") or ""),
                        git_commit=(str(ident["git_commit"]) if ident.get("git_commit") else None),
                        evidence_identity=(
                            str(ident["evidence_identity"]) if ident.get("evidence_identity") else None
                        ),
                    )
                except Exception:
                    continue
        if not normalized:
            normalized = None
    id_token = _NODE_OBJECT_INFO_IDENTITIES.set(normalized)
    warn_token = _NODE_OBJECT_INFO_LOOKUP_WARNINGS.set([])
    try:
        yield
    finally:
        _NODE_OBJECT_INFO_LOOKUP_WARNINGS.reset(warn_token)
        _NODE_OBJECT_INFO_IDENTITIES.reset(id_token)


_LOOKUP_WARNING_CODE_TO_EMISSION: dict[str, str] = {
    "unprovenanced_cache_fallback": "unprovenanced_class_fallback",
    "provenanced_cache_miss_fallback": "provenance_identity_cache_miss",
    "identity_cache_miss": "provenance_identity_cache_miss",
}


def _record_lookup_warning(node: Any, class_type: str, warning: Any) -> None:
    """If a warning recorder is bound, append this identity-lookup warning."""
    if warning is None:
        return
    bucket = _NODE_OBJECT_INFO_LOOKUP_WARNINGS.get()
    if bucket is None:
        return
    node_id = str(getattr(node, "id", "")) if node is not None else ""
    bucket.append(
        (
            node_id or None,
            class_type,
            str(getattr(warning, "code", "") or ""),
            str(getattr(warning, "message", "") or ""),
        )
    )


def _drain_lookup_warning_diagnostics(
    diagnostics: "list[EmissionDiagnostic] | None",
) -> bool:
    """Drain the bound warning recorder into *diagnostics*."""
    bucket = _NODE_OBJECT_INFO_LOOKUP_WARNINGS.get()
    if not bucket:
        return False
    low_conf = False
    seen: set[tuple[str | None, str, str]] = set()
    for node_id, class_type, code, message in bucket:
        emit_code = _LOOKUP_WARNING_CODE_TO_EMISSION.get(code)
        if not emit_code:
            continue
        key = (node_id, class_type, emit_code)
        if key in seen:
            continue
        seen.add(key)
        low_conf = True
        if diagnostics is not None:
            diagnostics.append(
                EmissionDiagnostic(
                    code=emit_code,
                    message=message,
                    severity="warning",
                    node_id=node_id,
                    class_type=class_type,
                    detail={"lookup_warning_code": code},
                )
            )
    return low_conf


def _identity_for_node(node: Any) -> "ObjectInfoIdentity | None":
    """Return the bound identity for *node* (by ``node.id``), if any."""
    table = _NODE_OBJECT_INFO_IDENTITIES.get()
    if not table or node is None:
        return None
    node_id = getattr(node, "id", None)
    if node_id is None:
        return None
    return table.get(str(node_id))


def _identity_for_node_id(node_id: Any) -> "ObjectInfoIdentity | None":
    table = _NODE_OBJECT_INFO_IDENTITIES.get()
    if not table or node_id is None:
        return None
    return table.get(str(node_id))


def _node_local_class_defaults(node: Any) -> dict[str, Any]:
    """Identity-aware schema defaults for *node*; class-only fallback."""
    class_type = str(node.class_type)
    identity = _identity_for_node(node)
    if identity is not None:
        try:
            result = resolve_class_entry(
                class_type, identity=identity, allow_class_fallback=True
            )
        except Exception:
            return dict(class_defaults(class_type))
        _record_lookup_warning(node, class_type, result.warning)
        entry = result.entry
        if entry is not None:
            defaults: dict[str, Any] = {}
            inputs = entry.get("inputs") or {}
            if isinstance(inputs, Mapping):
                for section in ("required", "optional"):
                    group = inputs.get(section)
                    if not isinstance(group, Mapping):
                        continue
                    for name, spec in group.items():
                        if (
                            isinstance(spec, (list, tuple))
                            and len(spec) > 1
                            and isinstance(spec[1], Mapping)
                            and "default" in spec[1]
                        ):
                            defaults[str(name)] = spec[1]["default"]
            return defaults
    return dict(class_defaults(class_type))


