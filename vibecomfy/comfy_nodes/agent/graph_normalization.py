"""Graph-shape adapter for the Agent Edit input boundary.

Agent Edit's mutation and authority contracts operate on canonical ComfyUI
LiteGraph JSON: ``nodes`` and ``links`` are lists.  Executor callers may carry
the serialized Vibe format instead, whose rich ``nodes`` collection is keyed by
node id.  The rich ``nodes`` mapping is the sole structural authority; the
executable API view is derived by compiling the IR (``compile(\"api\")``), never
read from stored data.  Normalize that representation once, before session
allocation persists or hashes it.

Batch 3 (one retained ingest authority): the door does NOT discard the IR it
constructs.  ``normalize_agent_edit_graph`` returns a typed
:class:`NormalizedAgentEditGraph` carrying BOTH the canonical LiteGraph dict
(``.graph``) and the retained ``VibeWorkflow`` (``.workflow``); the Agent Edit
entrypoint stores that IR in ``AgentEditState.workflow`` at allocation and no
downstream stage re-derives the IR from raw JSON.  For an existing UI graph the
canonical dict is the input itself (object identity preserved) and the retained
IR is built by the same named door (``from_ui``) — the door is the only shape
dispatcher.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from vibecomfy.workflow import VibeWorkflow


@dataclass(frozen=True, slots=True)
class NormalizedAgentEditGraph:
    """Typed door result: the canonical UI graph plus the retained ingest IR.

    ``graph`` is the canonical LiteGraph dict consumed by the Agent Edit
    pipeline (the input itself for existing UI graphs).  ``workflow`` is the
    single retained ``VibeWorkflow`` the door constructed — the IR authority
    stored on ``AgentEditState.workflow`` at allocation so it is never rebuilt
    downstream.
    """

    graph: dict[str, Any]
    workflow: VibeWorkflow


def normalize_agent_edit_graph(
    graph: dict[str, Any],
    *,
    schema_provider: Any = None,
) -> NormalizedAgentEditGraph:
    """Return the canonical UI graph consumed by the Agent Edit pipeline.

    Existing UI graphs keep the input dict as ``result.graph`` (object
    identity preserved) and build the retained IR through ``from_ui`` — the
    door is the ONLY shape dispatcher, so downstream stages never re-derive
    the IR from raw JSON.  All
    other supported workflow shapes are round-tripped through ``VibeWorkflow``
    and the canonical UI emitter; the returned :class:`NormalizedAgentEditGraph`
    carries both the canonical ``graph`` and the retained ``workflow`` (never
    discarded — batch 3).  For a serialized Vibe graph the
    rich ``nodes`` mapping is the sole structural authority (``compiled_api``
    is never used to decide which nodes exist): each rich node maps to a
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
    from vibecomfy.ingest.normalize import from_api, from_envelope, from_ui

    if isinstance(graph.get("nodes"), list):
        # Canonical LiteGraph UI graph: the input IS the canonical dict
        # (identity preserved); the retained IR is built by the same door.
        return NormalizedAgentEditGraph(
            graph=graph,
            workflow=from_ui(graph, schema_provider=schema_provider),
        )

    # The rich ``nodes`` mapping is the sole structural authority. ``compiled_api``
    # is execution evidence only and is deliberately NOT validated here — it must
    # never decide which rich nodes exist or gate the conversion.
    entries = graph.get("nodes")
    if isinstance(entries, Mapping) and any(
        not isinstance(entry, Mapping) for entry in entries.values()
    ):
        raise ValueError("nodes must contain only node objects")

    from vibecomfy.ingest.normalize import from_api, from_envelope
    from vibecomfy.porting.emit.ui import emit_ui_json

    # A rich ``nodes`` mapping is a serialized Vibe envelope; anything else
    # (no ``nodes`` key) is a ComfyUI API-format prompt dict (node id -> node),
    # which the API importer consumes directly.
    if isinstance(entries, Mapping):
        workflow = from_envelope(graph)
    else:
        workflow = from_api(graph, schema_provider=schema_provider)
    return NormalizedAgentEditGraph(
        graph=emit_ui_json(
            workflow,
            schema_provider=schema_provider,
            guard_original_ui=graph,
        ),
        workflow=workflow,
    )


__all__ = ["NormalizedAgentEditGraph", "normalize_agent_edit_graph"]
