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
from .compact_resolver import (
    WidgetNameResolution,
    compact_widget_names_for_node,
    missing_widget_value_sentinel,
    widget_index_for_field,
    widget_value_for_field,
)
from .schema import (
    WIDGET_SCHEMA,
    WIDGET_SEMANTIC_NAMES,
    effective_widget_names_for_class,
)
from .settings_contract import (
    NodeFieldInfo,
    NodeSettingsInfo,
    compact_field_names_for_node,
    node_settings_for,
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
    "WidgetNameResolution",
    "compact_widget_names_for_node",
    "missing_widget_value_sentinel",
    "unresolved_widget_aliases",
    "widget_index_for_field",
    "widget_names_for_class",
    "widget_names_from_schema",
    "widget_value_for_field",
    # .schema
    "WIDGET_SCHEMA",
    "WIDGET_SEMANTIC_NAMES",
    "effective_widget_names_for_class",
    # .settings_contract
    "NodeFieldInfo",
    "NodeSettingsInfo",
    "compact_field_names_for_node",
    "node_settings_for",
]
