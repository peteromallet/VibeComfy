"""Graph-shape adapter for the Agent Edit input boundary.

Agent Edit's mutation and authority contracts operate on canonical ComfyUI
LiteGraph JSON: ``nodes`` and ``links`` are lists.  Executor callers may carry
the serialized Vibe format instead, whose rich ``nodes`` collection is keyed by
node id.  The rich ``nodes`` mapping is the sole structural authority; the
executable API view is derived by compiling the IR (``compile("api")``), never
read from stored data.  Normalize that representation once, before session
allocation persists or hashes it.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any


def normalize_agent_edit_graph(
    graph: dict[str, Any],
    *,
    schema_provider: Any = None,
) -> dict[str, Any]:
    """Return the canonical UI graph consumed by the Agent Edit pipeline.

    Existing UI graphs are returned unchanged, including object identity.  All
    other supported workflow shapes are round-tripped through ``VibeWorkflow``
    and the canonical UI emitter.  For a serialized Vibe graph the rich
    ``nodes`` mapping is the sole structural authority (``compiled_api`` is
    never used to decide which nodes exist): each rich node maps to a
    LiteGraph node ``id`` (numeric keys become integers) and carries its stable
    string identity in ``properties.vibecomfy_uid``; rich edges become
    canonical ``links``.  Graph-level ``groups`` ride on the IR
    (``VibeWorkflow.groups``, populated by the envelope/UI importers) and are
    emitted as the canonical envelope's top-level ``groups``; a non-list
    ``groups`` is rejected at ingest.

    The conversion is whole-graph and fail-closed: malformed or mixed mapping
    entries are never partially appended to an otherwise canonical node list.
    An empty mapping normalizes to an empty list.
    """
    if isinstance(graph.get("nodes"), list):
        return graph

    # The rich ``nodes`` mapping is the sole structural authority. ``compiled_api``
    # is execution evidence only and is deliberately NOT validated here — it must
    # never decide which rich nodes exist or gate the conversion.
    entries = graph.get("nodes")
    if isinstance(entries, Mapping) and any(
        not isinstance(entry, Mapping) for entry in entries.values()
    ):
        raise ValueError("nodes must contain only node objects")

    from vibecomfy.ingest.normalize import from_envelope
    from vibecomfy.porting.emit.ui import emit_ui_json

    workflow = from_envelope(graph)
    return emit_ui_json(
        workflow,
        schema_provider=schema_provider,
        guard_original_ui=graph,
    )


__all__ = ["normalize_agent_edit_graph"]
