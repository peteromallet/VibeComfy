"""Widgets sub-package: widget-aliases and widget-schema primitives."""

from .aliases import (
    COMPILE_WIDGET_ALIAS_CLASS_TYPES,
    LINK_ONLY_TYPES,
    WidgetResolution,
    apply_positional_widget_aliases,
    resolve_widget_key,
    resolve_widget_key_with_provenance,
    resolve_widget_name,
    resolve_widget_name_with_provenance,
    unresolved_widget_aliases,
    widget_alias_analysis,
    widget_names_for_class,
    widget_names_from_schema,
)
from .schema import (
    WIDGET_SCHEMA,
    WIDGET_SEMANTIC_NAMES,
    effective_widget_names_for_class,
)

__all__ = [
    # .aliases
    "COMPILE_WIDGET_ALIAS_CLASS_TYPES",
    "LINK_ONLY_TYPES",
    "apply_positional_widget_aliases",
    "resolve_widget_key",
    "resolve_widget_key_with_provenance",
    "resolve_widget_name",
    "resolve_widget_name_with_provenance",
    "widget_alias_analysis",
    "WidgetResolution",
    "unresolved_widget_aliases",
    "widget_names_for_class",
    "widget_names_from_schema",
    # .schema
    "WIDGET_SCHEMA",
    "WIDGET_SEMANTIC_NAMES",
    "effective_widget_names_for_class",
]
