from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from vibecomfy.workflow import VibeWorkflow


@dataclass(frozen=True, slots=True)
class Patch:
    """A targeted, idempotent decoration of an existing workflow graph.

    A patch adjusts policy or topology on a graph the caller already has: set
    widget/input values, swap compatible node classes, add support nodes, or
    splice into an existing edge. Construction APIs that create a new reusable
    stage and return public handles belong in blocks or ready workflows, not in
    patches. A patch's public result is always the same
    :class:`VibeWorkflow`; it must not introduce a new handle-producing API.

    ``applies_to`` must be a conservative, side-effect-free predicate that is
    safe to call on any workflow and returns true only when ``apply`` can make
    its supported change. ``apply`` must be idempotent for the same workflow:
    repeated calls should not duplicate support nodes, metadata, requirements,
    or edges. Unsupported direct ``apply`` calls should fail clearly rather
    than silently leaving the graph unchanged.
    """

    name: str
    applies_to: Callable[[VibeWorkflow], bool]
    apply: Callable[[VibeWorkflow], VibeWorkflow]
    rationale: Callable[[VibeWorkflow], str]
