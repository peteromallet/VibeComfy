"""Zero-dependency leaf for canonical contract hashing primitives.

This module is the single owner of the shared canonical-hash identity used by
the agent-edit authority contracts.  It is intentionally a *leaf*: it imports
nothing else inside ``vibecomfy.comfy_nodes.agent`` so the cross-language
contract modules (``layout_operation_v1``, ``mutation_materialization_v1``)
can import it without forming an import cycle with
``projection_registry_v1`` (which must, in turn, call those modules'
``assert_*`` validators from inside the common authority validator).

Dependency direction is one-way::

    _canonical_contract_primitives.py   (leaf; imports nothing in agent/)
            ^                ^                ^
            |                |                |
    projection_registry_v1   layout_operation_v1   mutation_materialization_v1

The hash/JSON/error code below was relocated **verbatim** from
``projection_registry_v1.py``; ``projection_registry_v1.py`` re-exports these
symbols unchanged so every existing caller resolves to the *same* objects
(identity-preserving, behavior-preserving).  No second hash owner, no second
canonicalizer, no second error class.

The sole *addition* here versus the historical registry body is
``canonicalize_contract_numeric`` (see §0.3.1 of the M2 checkpoint spec): a
value preprocessor that normalises Python numeric spellings to match the
canonical form ``JSON.stringify`` already produces in JavaScript.  It is a
*value* transform run before the shared hash; it does not sort keys, emit JSON
text, or call ``hashlib``.  Existing entry points do not call it, so every
existing m1/m0 digest is unchanged.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping
from functools import cmp_to_key
from typing import Any

# Maximum exactly-representable integer in IEEE-754 double (2**53 - 1).  Integer
# values whose magnitude exceeds this cannot round-trip through JavaScript's
# ``Number`` type, so they are rejected as non-canonical rather than silently
# truncated.
_JS_SAFE_INTEGER_MAX = 9007199254740991

_NON_CANONICAL_NUMBER = "non_canonical_number"


class ContractError(ValueError):
    def __init__(self, message: str, code: str) -> None:
        super().__init__(message)
        self.code = code


def _compare_utf16_keys(left: str, right: str) -> int:
    """Match JavaScript's UTF-16 code-unit object-key ordering exactly."""
    left_units = left.encode("utf-16-be", errors="surrogatepass")
    right_units = right.encode("utf-16-be", errors="surrogatepass")
    return (left_units > right_units) - (left_units < right_units)


def _order_json_objects_utf16(value: Any) -> Any:
    if isinstance(value, Mapping):
        ordered: dict[str, Any] = {}
        entries = sorted(
            ((str(key), entry) for key, entry in value.items()),
            key=cmp_to_key(lambda left, right: _compare_utf16_keys(left[0], right[0])),
        )
        for key, entry in entries:
            ordered[key] = _order_json_objects_utf16(entry)
        return ordered
    if isinstance(value, (list, tuple)):
        return [_order_json_objects_utf16(entry) for entry in value]
    return value


def canonical_json(value: Any, *, ensure_ascii: bool = True) -> str:
    """Canonical JSON with browser-equivalent UTF-16 object-key ordering."""
    return json.dumps(
        _order_json_objects_utf16(value),
        sort_keys=False,
        separators=(",", ":"),
        ensure_ascii=ensure_ascii,
    )


def canonical_json_bytes_v1(value: Any, *, ensure_ascii: bool = False) -> bytes:
    return canonical_json(value, ensure_ascii=ensure_ascii).encode("utf-8")


def _hash(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode()).hexdigest()


def canonicalize_contract_numeric(
    value: Any,
    *,
    finite_error_code: str,
    allow_bool: bool = False,
) -> Any:
    """Normalise numeric values to the JavaScript-compatible spelling.

    Recursively walks mappings (by value) and lists/tuples (by element).  For
    every numeric leaf:

    * ``int`` whose magnitude is within ``±(2**53 - 1)`` -> returned unchanged.
    * ``int`` whose magnitude exceeds ``2**53 - 1`` -> rejected with
      ``non_canonical_number`` (Python's arbitrary-precision ``int`` serialises
      to an exact decimal that JS ``Number`` cannot represent identically, so
      the two sides would emit divergent bytes — e.g. ``2**60``).
    * ``bool`` -> rejected with ``non_canonical_number`` (a boolean in a
      numeric position has no JS-compatible numeric spelling).
    * finite ``float`` whose value is integral with ``abs(x) <= 2**53 - 1`` ->
      coerced to ``int`` (so ``1.0``, ``-0.0``, and ``1e2`` all normalise to
      ``1``, ``0``, ``100`` — the spelling ``JSON.stringify`` already emits).
    * finite ``float`` whose magnitude exceeds ``2**53 - 1`` -> rejected with
      ``non_canonical_number`` (cannot be represented exactly as a JS Number).
    * genuine fractional ``float`` -> returned unchanged (``1.5`` stays
      ``1.5`` in both languages).
    * ``NaN`` / ``Infinity`` / ``-Infinity`` -> rejected with
      ``finite_error_code`` (caller-selectable: ``non_finite_geometry`` for
      layout, ``non_finite_materialization`` for materialization).

    This is a *value* preprocessor: it does not sort keys, emit JSON text, or
    call ``hashlib``.  The hashing identity remains ``_hash`` /
    ``canonical_json_bytes_v1``; this function only prepares the value so the
    shared hash produces a byte-identical preimage on both sides.
    """
    return _normalize_numeric(
        value,
        finite_error_code=finite_error_code,
        allow_bool=allow_bool,
    )


def _normalize_numeric(
    value: Any,
    *,
    finite_error_code: str,
    allow_bool: bool,
) -> Any:
    if isinstance(value, bool):
        if allow_bool:
            return value
        # bool is a subclass of int in Python but has no numeric spelling in
        # the JS canonical contract; reject it explicitly.
        raise ContractError(
            "Boolean is not a canonical numeric value", _NON_CANONICAL_NUMBER
        )
    if isinstance(value, int):
        # Native Python ``int`` is arbitrary-precision.  A value whose
        # magnitude exceeds the JS safe integer range (±(2**53 - 1)) cannot be
        # represented identically by JS ``Number``: ``json.dumps`` emits the
        # exact decimal (e.g. ``2**60`` -> ``"...476"``) while JS
        # ``JSON.stringify`` emits the shortest round-trippable spelling
        # (``"...500"``).  Reject so both sides agree on bytes.
        if abs(value) > _JS_SAFE_INTEGER_MAX:
            raise ContractError(
                "Integer value exceeds the JS safe integer range",
                _NON_CANONICAL_NUMBER,
            )
        return value
    if isinstance(value, float):
        if value != value or value in (float("inf"), float("-inf")):
            raise ContractError(
                "Non-finite numeric value is not canonical", finite_error_code
            )
        if value.is_integer():
            if abs(value) > _JS_SAFE_INTEGER_MAX:
                raise ContractError(
                    "Integer value exceeds the JS safe integer range",
                    _NON_CANONICAL_NUMBER,
                )
            return int(value)
        return value
    if isinstance(value, Mapping):
        return {
            str(key): _normalize_numeric(
                entry,
                finite_error_code=finite_error_code,
                allow_bool=allow_bool,
            )
            for key, entry in value.items()
        }
    if isinstance(value, (list, tuple)):
        return [
            _normalize_numeric(
                entry,
                finite_error_code=finite_error_code,
                allow_bool=allow_bool,
            )
            for entry in value
        ]
    return value


__all__ = [
    "ContractError",
    "canonical_json",
    "canonical_json_bytes_v1",
    "_hash",
    "_order_json_objects_utf16",
    "_compare_utf16_keys",
    "canonicalize_contract_numeric",
]
