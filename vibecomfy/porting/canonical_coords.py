"""Canonical coordinate snapping for layout positions and sizes.

Uses round-half-even (banker's rounding) for idempotence and bit-stability
through json.dumps/json.loads cycles.  Python's built-in round() implements
banker's rounding per IEEE 754, so snap_coord is a one-liner.
"""

from __future__ import annotations

from typing import Sequence


def snap_coord(value: float | int) -> int:
    """Snap a single coordinate to a whole-pixel integer using round-half-even.

    Idempotent: snap_coord(snap_coord(x)) == snap_coord(x) for all finite x.
    Bit-stable: json.loads(json.dumps(snap_coord(x))) == snap_coord(x).
    """
    return round(value)


def snap_seq(seq: Sequence[float | int]) -> list[int]:
    """Snap a coordinate sequence to whole pixels."""
    return [snap_coord(v) for v in seq]


snap_pos = snap_seq


snap_size = snap_seq
