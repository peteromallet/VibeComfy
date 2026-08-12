"""Graph-shape adapter for the Agent Edit input boundary.

Agent Edit's mutation and authority contracts operate on canonical ComfyUI
LiteGraph JSON: ``nodes`` and ``links`` are lists.  Executor callers may carry
the serialized Vibe format instead, whose rich ``nodes`` collection is keyed by
node id and whose executable graph lives under ``compiled_api``.  Normalize
that representation once, before session allocation persists or hashes it.
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
    and the canonical UI emitter.  For a serialized Vibe graph this maps each
    ``nodes`` mapping key to a LiteGraph node ``id`` (numeric keys become
    integers) and carries its stable string identity in
    ``properties.vibecomfy_uid``; compiled edges become canonical ``links``.

    The conversion is whole-graph and fail-closed: malformed or mixed mapping
    entries are never partially appended to an otherwise canonical node list.
    An empty mapping normalizes to an empty list.
    """
    if isinstance(graph.get("nodes"), list):
        return graph

    for field in ("nodes", "compiled_api"):
        entries = graph.get(field)
        if isinstance(entries, Mapping) and any(
            not isinstance(entry, Mapping) for entry in entries.values()
        ):
            raise ValueError(f"{field} must contain only node objects")

    from vibecomfy.ingest.normalize import convert_to_vibe_format
    from vibecomfy.porting.emit.ui import emit_ui_json

    workflow = convert_to_vibe_format(graph, schema_provider=schema_provider)
    return emit_ui_json(
        workflow,
        schema_provider=schema_provider,
        guard_original_ui=graph,
    )


__all__ = ["normalize_agent_edit_graph"]
