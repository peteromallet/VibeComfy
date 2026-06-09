from __future__ import annotations

from vibecomfy.workflow import VibeWorkflow


def stamp_workflow_origin(
    workflow: VibeWorkflow,
    entrypoint: str,
    layer: str,
    *,
    override: bool = False,
) -> VibeWorkflow:
    """Record authoring-boundary provenance on ``workflow.metadata``.

    The default mode is first-writer-wins: preserve any existing marker and
    only fill missing fields. ``override=True`` is reserved for explicit
    backfills or migration code that intends to replace existing markers.
    """

    if override:
        workflow.metadata["entrypoint"] = entrypoint
        workflow.metadata["layer"] = layer
        return workflow
    workflow.metadata.setdefault("entrypoint", entrypoint)
    workflow.metadata.setdefault("layer", layer)
    return workflow


__all__ = ["stamp_workflow_origin"]
