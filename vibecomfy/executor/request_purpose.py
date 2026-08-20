"""Deterministic request-purpose policy shared by executor drivers.

This is host policy, not a classifier.  It only resolves purposes that are
already forced by the public request shape; staged deliberation remains free
to classify every other request, while threaded deliberation remains
classifier-free.
"""

from __future__ import annotations

from typing import Literal

from .contracts import ExecutorRequest

RequestPurpose = Literal["research", "inspect", "adapt"]


def deterministic_request_purpose(request: ExecutorRequest) -> RequestPurpose:
    """Return the capability purpose forced by *request*.

    A missing graph cannot support graph inspection or editing, so the only
    useful agent-owned action is research.  Conversely, an explicit
    ``answer_only`` interaction with an attached graph is inspection-only and
    must never enter the edit kernel.  All other attached-graph requests keep
    the normal edit-capable envelope.
    """
    if request.graph is None:
        return "research"
    if request.interaction_mode == "answer_only":
        return "inspect"
    return "adapt"


__all__ = ["RequestPurpose", "deterministic_request_purpose"]
