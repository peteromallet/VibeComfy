"""Frozen uid helpers for M1.5. These signatures are frozen for M2.

Identity is extrinsic only — NOT a content/WL hash and NOT uuid4.
"""

from __future__ import annotations


def make_uid(scope_path: str, local_uid: str) -> str:
    """Compose a fully-qualified uid from a scope path and local uid.

    Returns local_uid when scope_path is empty, else f"{scope_path}:{local_uid}".
    """
    if scope_path == "":
        return local_uid
    return f"{scope_path}:{local_uid}"


def parse_uid(uid: str) -> tuple[str, str]:
    """Inverse of make_uid. Returns (scope_path, local_uid).

    Returns ("", uid) for a bare scalar with no scope separator.
    """
    if ":" not in uid:
        return ("", uid)
    scope_path, _, local_uid = uid.partition(":")
    return (scope_path, local_uid)


def mint_local_uid(raw_ui_node: dict | None, fallback_id: str) -> str:
    """Derive a local uid from a raw litegraph node dict.

    Precedence:
    1. str(properties["vibecomfy_uid"]) if present in raw node
    2. str(raw_ui_node["id"]) — the litegraph integer node id
    3. fallback_id
    """
    if raw_ui_node is None:
        return fallback_id
    properties = raw_ui_node.get("properties") or {}
    vibecomfy_uid = properties.get("vibecomfy_uid")
    if vibecomfy_uid is not None:
        return str(vibecomfy_uid)
    node_id = raw_ui_node.get("id")
    if node_id is not None:
        return str(node_id)
    return fallback_id
