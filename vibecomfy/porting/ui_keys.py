"""Key helpers for emitted UI JSON node dicts."""
from __future__ import annotations


def node_lookup_key(node_dict: dict) -> str:
    """Return the canonical lookup key for an emitted litegraph node dict.

    Priority: ``properties['vibecomfy_uid']`` (stable, identity-preserving) if
    present and non-empty, else ``properties['vibecomfy_id']`` (class+order label).

    Use this instead of the former ``properties['ir_node_id']`` (demoted in M5).
    """
    props = node_dict.get("properties", {})
    uid = props.get("vibecomfy_uid")
    if uid:
        return uid
    return props.get("vibecomfy_id", "")
