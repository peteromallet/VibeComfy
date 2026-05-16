"""Private stub `SchemaProviderLike` used by the dry-run runtime.

The stub wraps an `object_info` mapping (typically `tests/snapshots/`-style
JSON dumps cached under `out/cache/`) and returns the minimal
`NodeSchemaLike` record the dry-run code needs — `class_type` and nothing
else. The dry-run runtime never asks the stub for required-inputs, output
slots, or widget defaults.

This module MUST NOT import `vibecomfy.runtime.*`, `vibecomfy.schema.provider`,
or `vibecomfy.comfy_command` at module level. The single-line
`NodeSchemaLike`/`SchemaProviderLike` Protocols live in
`vibecomfy.testing._schema`.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from vibecomfy.testing._schema import NodeSchemaLike, SchemaProviderLike

__all__ = ["_StubNodeSchema", "_StubSchemaProvider"]


@dataclass(frozen=True, slots=True)
class _StubNodeSchema:
    """Minimal `NodeSchemaLike` record: only `class_type` is required."""

    class_type: str


class _StubSchemaProvider:
    """`SchemaProviderLike` backed by an `object_info` mapping.

    The mapping is the same shape as `tests/snapshots/object_info*.json` (a
    dict keyed by class_type). Lookups that miss the cache return a minimal
    `_StubNodeSchema(class_type)` so the dry-run runtime can keep going.
    """

    __slots__ = ("_object_info",)

    def __init__(self, object_info: dict[str, Any] | None = None) -> None:
        self._object_info = dict(object_info or {})

    def node_schema(self, class_type: str) -> NodeSchemaLike | None:
        # Returning a record (even on miss) keeps callers simple. The dry-run
        # runtime treats a hit and a synthesised stub interchangeably.
        return _StubNodeSchema(class_type=class_type)

    @property
    def object_info(self) -> dict[str, Any]:
        return dict(self._object_info)


# Runtime-checkable Protocol conformance is asserted lazily by the test suite
# (T5); we do not run `isinstance(_StubSchemaProvider(), SchemaProviderLike)`
# at import time to keep cost minimal.
assert SchemaProviderLike is not None  # noqa: S101 — module-level keep-alive
