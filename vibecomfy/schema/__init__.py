"""Schema package re-exports.

The eager re-exports below pulled `vibecomfy.schema.provider` into
`sys.modules` whenever `vibecomfy` was imported. Because
`vibecomfy/schema/provider.py` itself top-imports `vibecomfy.runtime.client`,
`vibecomfy.runtime.server`, and `vibecomfy.comfy_command`, this broke the
cheap-import contract for `vibecomfy.testing` (verified by T5's import-cost
subprocess test). To keep `import vibecomfy.testing` lightweight while
preserving the public `vibecomfy.schema.<name>` surface, every public name
is now loaded lazily via PEP 562 `__getattr__`.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

__all__ = [
    "InputSpec",
    "CompositeSchemaProvider",
    "ConversionSchemaProvider",
    "LocalSchemaProvider",
    "NodeSchema",
    "ObjectInfoSchemaProvider",
    "OutputSpec",
    "RuntimeSchemaProvider",
    "SchemaIndexError",
    "SchemaProvider",
    "SchemaSourceInfo",
    "SourceSchemaProvider",
    "get_schema_provider",
    "schema_for",
    "schema_registry_empty",
    "schemas_for",
]


if TYPE_CHECKING:  # pragma: no cover - typing only
    from .provider import (  # noqa: F401
        CompositeSchemaProvider,
        ConversionSchemaProvider,
        InputSpec,
        LocalSchemaProvider,
        NodeSchema,
        ObjectInfoSchemaProvider,
        OutputSpec,
        RuntimeSchemaProvider,
        SchemaIndexError,
        SchemaProvider,
        SchemaSourceInfo,
        SourceSchemaProvider,
        get_schema_provider,
        schema_for,
        schema_registry_empty,
        schemas_for,
    )


def __getattr__(name: str):
    if name in __all__:
        from . import provider as _provider  # local: defers runtime import chain

        value = getattr(_provider, name)
        globals()[name] = value
        return value
    raise AttributeError(f"module 'vibecomfy.schema' has no attribute {name!r}")
