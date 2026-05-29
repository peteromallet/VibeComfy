"""Unit tests for vibecomfy.porting.canonical_coords.

Proves:
1. snap_coord uses round-half-even (0.5→0, 1.5→2, 2.5→2).
2. Idempotence: snap_coord(snap_coord(x)) == snap_coord(x).
3. Bit-stability through json.dumps→json.loads cycle.
"""
from __future__ import annotations

import json

import pytest

from vibecomfy.porting.canonical_coords import snap_coord, snap_pos, snap_size


# ── Half-even rounding ────────────────────────────────────────────────────────

@pytest.mark.parametrize("value,expected", [
    (0.5, 0),   # half-even: 0 is even
    (1.5, 2),   # half-even: 2 is even
    (2.5, 2),   # half-even: 2 is even
    (3.5, 4),   # half-even: 4 is even
    (0.0, 0),
    (1.0, 1),
    (1.4, 1),
    (1.6, 2),
    (-0.5, 0),  # half-even: 0 is even
    (-1.5, -2), # half-even: -2 is even
])
def test_snap_coord_half_even(value: float, expected: int) -> None:
    assert snap_coord(value) == expected


# ── Idempotence ───────────────────────────────────────────────────────────────

@pytest.mark.parametrize("value", [0.5, 1.5, 2.5, 1.4, 99.9, -3.7, 0.0, 100.0])
def test_snap_coord_idempotent(value: float) -> None:
    once = snap_coord(value)
    assert snap_coord(once) == once


# ── Bit-stability through json round-trip ────────────────────────────────────

@pytest.mark.parametrize("value", [0.5, 1.5, 2.5, 100.0, -42.0, 0])
def test_snap_coord_bit_stable_json(value: float) -> None:
    snapped = snap_coord(value)
    # json.dumps produces an integer string for int; json.loads restores it as int
    recovered = json.loads(json.dumps(snapped))
    assert recovered == snapped
    assert type(recovered) is int


# ── snap_pos and snap_size wrappers ───────────────────────────────────────────

def test_snap_pos_rounds_sequence() -> None:
    assert snap_pos([10.5, 20.3]) == [10, 20]


def test_snap_size_rounds_sequence() -> None:
    assert snap_size([100.5, 200.5]) == [100, 200]  # both half-even → even


def test_snap_pos_empty() -> None:
    assert snap_pos([]) == []


def test_snap_size_already_int() -> None:
    assert snap_size([3, 7]) == [3, 7]
