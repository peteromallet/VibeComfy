"""Private helpers for `vibecomfy.testing.assertions`.

These helpers are intentionally trivial and side-effect-free so the public
assertion surface stays focused on the *contract* and not on parsing.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from vibecomfy.handles import Handle

if TYPE_CHECKING:
    from vibecomfy.workflow import VibeWorkflow

__all__ = [
    "FAILURE_HINT_USE_ASSERT_EDGE",
    "format_failure",
    "is_api_link",
    "is_ir_edge_ref",
    "resolve_wf_id",
]

FAILURE_HINT_USE_ASSERT_EDGE = "use assert_edge for edge/link values"


def resolve_wf_id(wf_or_api: Any) -> str:
    """Return a best-effort workflow id for failure messages.

    For a `VibeWorkflow` the precedence is `wf.id` then `wf.source.id`. For an
    API dict, look at a top-level `"metadata"` mapping (compile output may carry
    one) and fall back to `"<unknown>"`.
    """
    from vibecomfy.workflow import VibeWorkflow  # lazy: avoid testing↔workflow import cycle

    if isinstance(wf_or_api, VibeWorkflow):
        wid = getattr(wf_or_api, "id", None)
        if wid:
            return str(wid)
        source = getattr(wf_or_api, "source", None)
        if source is not None:
            sid = getattr(source, "id", None)
            if sid:
                return str(sid)
        return "<unknown>"
    if isinstance(wf_or_api, dict):
        meta = wf_or_api.get("metadata")
        if isinstance(meta, dict):
            mid = meta.get("workflow_id") or meta.get("id")
            if mid:
                return str(mid)
        return "<api-dict>"
    return "<unknown>"


def is_api_link(value: Any) -> bool:
    """Return True for a compiled API-dict link ref: `[node_id_str, slot_int]`."""
    return (
        isinstance(value, list)
        and len(value) == 2
        and isinstance(value[0], str)
        and isinstance(value[1], int)
    )


def is_ir_edge_ref(value: Any) -> bool:
    """Return True for an IR-level edge ref: a `Handle` or 2-tuple."""
    if isinstance(value, Handle):
        return True
    if isinstance(value, tuple) and len(value) == 2:
        return True
    return False


def format_failure(
    wf_id: str,
    name: str,
    what: str,
    *,
    node_id: Any = None,
    field: Any = None,
    expected: Any = ...,
    got: Any = ...,
    hint: str | None = None,
) -> str:
    """Standard failure message used by every assertion."""
    expected_part = f"expected={expected!r}" if expected is not ... else "expected=<n/a>"
    got_part = f"got={got!r}" if got is not ... else "got=<n/a>"
    parts = [
        f"node={node_id!r}",
        f"input={field!r}",
        expected_part,
        got_part,
    ]
    suffix = "(" + ", ".join(parts) + ")"
    base = f"[{wf_id}] {name}: {what} {suffix}"
    if hint:
        base = f"{base} | hint: {hint}"
    return base
