"""Subgraph scope identity for durable node uids (M2, Step 6).

A subgraph *definition* (one entry of ``metadata['definitions']``) is reduced to
a stable ``sg_key`` derived ONLY from its structural skeleton — inner
``class_type``s, topology, and wiring — EXCLUDING ``pos``, ``properties``,
widget values, and the volatile ``graphUuid`` (SD2/SD5). Two clones of the same
definition therefore share an ``sg_key`` (and thus a ``scope_path``); their
inner nodes are kept distinct by minting local uids off a never-reused monotonic
counter (T2), so colliding inner integer ids do not collide as uids.

Pure-Python derivation (blake2b) keeps M2 offline and deterministic — no
dependency on the ComfyUI submodule.
"""

from __future__ import annotations

import hashlib
import json
import re
from typing import Any, Callable, Mapping, Sequence

from .uid import SCOPE_CHAIN_JOIN, SCOPE_LOCAL_SEP, make_uid

# Characters that must never appear inside a sanitized subgraph name, because
# they are the uid structural separators. ':' is allowed inside an sg_key.
_FORBIDDEN_NAME_CHARS = (SCOPE_LOCAL_SEP, SCOPE_CHAIN_JOIN)


def _canonical_local_node_id(value: Any) -> Any:
    """Match native integer and canonical string spellings of one local id."""
    if isinstance(value, str) or type(value) is int:
        return str(value)
    return value


def sanitize_subgraph_name(name: str) -> str:
    """Replace uid separators in a subgraph name so it cannot break scope parsing."""
    cleaned = str(name)
    for ch in _FORBIDDEN_NAME_CHARS:
        cleaned = cleaned.replace(ch, "_")
    return cleaned


def _inner_skeleton(sg_def: Mapping[str, Any]) -> dict[str, Any]:
    """Structural skeleton of a subgraph definition.

    Includes inner node ids + class_types and the input/output wiring; excludes
    pos, properties, widget values, and graphUuid so the key is invariant to
    cosmetic / value-only edits but changes on topology or class_type edits.
    """
    from vibecomfy.ingest.normalize import door_get_links, door_get_nodes

    skel_nodes: list[dict[str, Any]] = []
    for node in door_get_nodes(sg_def) or []:
        if not isinstance(node, Mapping):
            continue
        inputs = [
            {"name": i.get("name"), "type": i.get("type")}
            for i in (node.get("inputs") or [])
            if isinstance(i, Mapping)
        ]
        outputs = [
            {"name": o.get("name"), "type": o.get("type")}
            for o in (node.get("outputs") or [])
            if isinstance(o, Mapping)
        ]
        skel_nodes.append(
            {
                "id": _canonical_local_node_id(node.get("id")),
                "type": node.get("type") or node.get("class_type"),
                "inputs": inputs,
                "outputs": outputs,
            }
        )
    skel_nodes.sort(key=lambda n: json.dumps(n.get("id"), sort_keys=True, default=str))

    skel_links: list[Any] = []
    for link in door_get_links(sg_def) or []:
        # litegraph link form: [link_id, origin_id, origin_slot, target_id, target_slot, type]
        if isinstance(link, Sequence) and not isinstance(link, (str, bytes)):
            values = list(link)
            if len(values) >= 6:
                # Array and object links are two serializations of the same
                # LiteGraph edge.  Emission converts the former to the latter,
                # so structural identity must encode both with the same named
                # endpoint record or a presentation round-trip changes the
                # canonical recursive scope path.
                skel_links.append(
                    {
                        "origin_id": _canonical_local_node_id(values[1]),
                        "origin_slot": values[2],
                        "target_id": _canonical_local_node_id(values[3]),
                        "target_slot": values[4],
                        "type": values[5],
                    }
                )
            else:
                # Preserve deterministic identity for malformed legacy rows;
                # validation owns their eventual refusal.
                skel_links.append(values[1:])  # drop the volatile link id
        elif isinstance(link, Mapping):
            skel_links.append(
                {
                    "origin_id": _canonical_local_node_id(link.get("origin_id")),
                    "origin_slot": link.get("origin_slot"),
                    "target_id": _canonical_local_node_id(link.get("target_id")),
                    "target_slot": link.get("target_slot"),
                    "type": link.get("type"),
                }
            )
    skel_links.sort(key=lambda l: json.dumps(l, sort_keys=True, default=str))

    return {"nodes": skel_nodes, "links": skel_links}


def sg_key(sg_def: Mapping[str, Any]) -> str:
    """Stable scope key for one subgraph definition.

    Nameless definitions fall back to a hash-only key (never raises,
    prerequisite_ordering-2). Named definitions prefix a sanitized name for
    readability. The key may contain ':' but never the uid separators.
    """
    skeleton = _inner_skeleton(sg_def)
    payload = json.dumps(skeleton, sort_keys=True, default=str).encode("utf-8")
    digest = hashlib.blake2b(payload, digest_size=8).hexdigest()
    name = sg_def.get("name")
    if isinstance(name, str) and name.strip():
        return f"{sanitize_subgraph_name(name.strip())}:{digest}"
    return digest


def compose_scope_path(sg_keys: Sequence[str]) -> str:
    """Compose a scope_path from a chain of sg_keys (outermost first).

    Returns "" for an empty chain (top level → degrades to the M1.5 scalar uid).
    """
    if isinstance(sg_keys, str):
        raise ValueError("scope keys must be supplied as a sequence, not one string")
    normalized: list[str] = []
    for key in sg_keys:
        if not isinstance(key, str) or not key.strip():
            raise ValueError("scope keys must be nonblank strings")
        if SCOPE_CHAIN_JOIN in key or SCOPE_LOCAL_SEP in key:
            raise ValueError(f"scope key {key!r} contains a reserved UID separator")
        if re.fullmatch(r"sg\d+", key):
            raise ValueError(f"ordinal scope key {key!r} is not a stable sg_key")
        normalized.append(key)
    return SCOPE_CHAIN_JOIN.join(normalized)


def mint_inner_uid(scope_path: str, mint_local: Callable[[], str]) -> str:
    """Mint a scoped uid for an inner node.

    ``mint_local`` must return a fresh, never-reused local uid (e.g. wired to the
    T2 monotonic counter). Two clones sharing ``scope_path`` thus receive
    distinct uids despite colliding inner integer ids.
    """
    return make_uid(scope_path, mint_local())


__all__ = [
    "compose_scope_path",
    "mint_inner_uid",
    "sanitize_subgraph_name",
    "sg_key",
]
