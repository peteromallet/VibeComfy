"""Compatibility exports for positional widget schema.

Static compile-time aliases live in :mod:`vibecomfy._widget_aliases`. Porting
keeps object-info fallback here for conversion/codemod callers.
"""

from __future__ import annotations

from vibecomfy._compile._widgets import WIDGET_SCHEMA, WIDGET_SEMANTIC_NAMES


def effective_widget_names_for_class(
    class_type: str,
    *,
    allow_object_info_fallback: bool = False,
) -> list[str | None]:
    """Return ordered widget names for *class_type*.

    Curated static aliases always win. When requested, conversion-only callers
    may fall back to the checked-in object-info index.
    """

    curated = WIDGET_SCHEMA.get(class_type)
    if curated is not None:
        return list(curated)

    if allow_object_info_fallback:
        from vibecomfy.porting.object_info.consume import object_info_widget_order  # noqa: PLC0415

        return list(object_info_widget_order(class_type))

    return []


__all__ = ["WIDGET_SCHEMA", "WIDGET_SEMANTIC_NAMES", "effective_widget_names_for_class"]
