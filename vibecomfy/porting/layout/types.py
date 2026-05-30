"""Layout engine types — lightweight dataclasses with no dependencies."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class LayoutResult:
    """Immutable result from the fresh-layout engine.

    ``positions`` maps ``node.uid`` → ``{pos: [x, y], size: [w, h]}``.
    ``groups`` is a list of group dicts (may be empty).
    """

    positions: dict[str, dict]
    groups: list[dict]
