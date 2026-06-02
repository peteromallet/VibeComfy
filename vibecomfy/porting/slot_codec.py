"""Deterministic codec for raw slot names ↔ Python identifiers.

Slot names in ComfyUI can contain any characters, including dots, spaces,
parentheses, leading digits, and even Python keywords like ``in``, ``not``,
``or``, ``and``.  This module provides a deterministic, reversible conversion
so that every slot name maps to a valid Python identifier and the original
name can be recovered when the set of candidate names (the "context") is known.

Usage
-----
    from vibecomfy.porting.slot_codec import to_python_identifier, to_raw_name

    encoded = to_python_identifier("in")            # "in_"
    decoded = to_raw_name("in_", context={"in": "in", "out": "out"})  # "in"

    # Batch encoding with collision avoidance:
    from vibecomfy.porting.slot_codec import encode_slot_names
    mapping = encode_slot_names(["in", "in_", "out"])
    # mapping == {"in": "in_", "in_": "in_2", "out": "out"}
"""

from __future__ import annotations

import builtins
import keyword
import re
from typing import Iterable, Mapping

# -- Builtin protection -------------------------------------------------------
# Names that shadow Python builtins get a trailing underscore, following the
# same PEP 8 convention used for Python keywords.

_BUILTIN_NAMES: frozenset[str] = frozenset(
    name for name in dir(builtins) if not name.startswith("_")
)


def to_python_identifier(raw_name: str, *, used: set[str] | None = None) -> str:
    """Convert a raw slot name to a deterministic, valid Python identifier.

    Rules applied in order:

    1. Empty names → ``"_"``
    2. Lowercase
    3. Replace non-alphanumeric characters (except ``_``) with ``_``
    4. Collapse consecutive underscores
    5. Strip leading underscores unconditionally
    6. Strip trailing underscores, but track whether the original name had one
    7. Leading digit → prepend ``_``
    8. Python keyword or builtin → trailing ``_`` (PEP 8)
    9. If a keyword-mapped name collides with a raw name that originally
       ended in ``_``, the latter gets ``_2`` instead
    10. If ``used`` is provided, append ``_2``, ``_3``, ... until unique

    The transformation is **deterministic** — the same input always produces
    the same output.  Collision avoidance via ``used`` only adds
    deduplication; it does not make the function stateful across calls.
    """
    if not raw_name:
        candidate = "_"
        if used is not None:
            return _deduplicate(candidate, used)
        return candidate

    original = raw_name
    candidate = original.lower()
    # Replace characters not allowed in Python identifiers
    candidate = re.sub(r"[^a-z0-9_]", "_", candidate)
    # Collapse runs of underscores
    candidate = re.sub(r"_+", "_", candidate)
    # Strip leading underscore unconditionally
    candidate = candidate.lstrip("_")
    # Remember trailing-underscore status for collision detection
    had_trailing_underscore = candidate.endswith("_")
    candidate = candidate.rstrip("_")

    if not candidate:
        candidate = "_"
    elif candidate[0].isdigit():
        candidate = "_" + candidate

    # Keyword or builtin → trailing underscore (PEP 8 convention)
    if keyword.iskeyword(candidate) or candidate in _BUILTIN_NAMES:
        if had_trailing_underscore:
            # The raw name already ended in underscore so the trailing-underscore
            # encoding would collide with the keyword-suffixed form of the base
            # name.  Use _2 instead to avoid the collision.
            candidate = candidate + "_2"
        else:
            candidate = candidate + "_"

    if used is not None:
        candidate = _deduplicate(candidate, used)

    return candidate


def _deduplicate(candidate: str, used: set[str]) -> str:
    """Append ``_2``, ``_3``, ... until ``candidate`` is not in ``used``,
    then add it to ``used`` and return."""
    base = candidate
    index = 2
    while candidate in used:
        candidate = f"{base}_{index}"
        index += 1
    used.add(candidate)
    return candidate


def to_raw_name(encoded: str, context: Mapping[str, str]) -> str:
    """Recover the original raw slot name from an encoded Python identifier.

    ``context`` maps every possible raw slot name to itself (e.g.
    ``{"in": "in", "out": "out"}``).  The function encodes each key and
    returns the key whose encoding matches ``encoded``.

    Raises ``KeyError`` if no match is found and ``ValueError`` if the match
    is ambiguous.
    """
    reverse: dict[str, str] = {}
    for raw in context:
        encoded_key = to_python_identifier(raw)
        if encoded_key in reverse:
            existing = reverse[encoded_key]
            if existing != raw:
                raise ValueError(
                    f"Ambiguous encoding: both {existing!r} and "
                    f"{raw!r} encode to {encoded_key!r}"
                )
        reverse[encoded_key] = raw
    return reverse[encoded]


def build_reverse_map(raw_names: Iterable[str]) -> dict[str, str]:
    """Build a reverse map from encoded Python identifiers to raw slot names.

    Useful when you need many reverse lookups.  Raises ``ValueError`` on
    encoding collisions.

    Returns a dict mapping each unique encoded identifier to its original
    raw name.
    """
    reverse: dict[str, str] = {}
    for raw in raw_names:
        encoded = to_python_identifier(raw)
        if encoded in reverse:
            existing = reverse[encoded]
            if existing != raw:
                raise ValueError(
                    f"Encoding collision: {existing!r} and {raw!r} both "
                    f"encode to {encoded!r}"
                )
        reverse[encoded] = raw
    return reverse


def encode_slot_names(raw_names: Iterable[str]) -> dict[str, str]:
    """Build a deterministic mapping from raw slot names to Python identifiers.

    Uses collision avoidance: if two raw names would encode to the same
    identifier, the second one gets a ``_2`` suffix (or ``_3``, etc.).

    Returns a dict in the original iteration order mapping each raw name
    to its unique encoded identifier.
    """
    used: set[str] = set()
    mapping: dict[str, str] = {}
    for raw in raw_names:
        encoded = to_python_identifier(raw, used=used)
        mapping[raw] = encoded
    return mapping
