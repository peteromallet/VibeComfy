"""Local structural Protocols for the dry-run runtime.

This module exists so `vibecomfy.testing` never has to import
`vibecomfy.schema.provider.SchemaProvider` (which would transitively
load `vibecomfy.runtime.client`, `vibecomfy.runtime.server`, and
`vibecomfy.comfy_command`). The dry-run code uses only the tiny
`node_schema(class_type)` surface defined here.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    pass

__all__ = ["NodeSchemaLike", "SchemaProviderLike"]


@runtime_checkable
class NodeSchemaLike(Protocol):
    """Minimal node-schema surface the dry-run runtime relies on."""

    class_type: str


@runtime_checkable
class SchemaProviderLike(Protocol):
    """Minimal schema-provider surface the dry-run runtime relies on."""

    def node_schema(self, class_type: str) -> NodeSchemaLike | None: ...
