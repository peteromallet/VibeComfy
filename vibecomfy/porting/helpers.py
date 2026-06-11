"""Compatibility wrapper for workflow helper classification.

New code should import from :mod:`vibecomfy._workflow_helpers`. This module is
kept temporarily for existing porting callers and external imports.
"""

from __future__ import annotations

from vibecomfy._compile._helpers import (
    BROADCAST_HELPER_CLASS_TYPES,  # REMOVE-M4 compatibility export
    HELPER_CLASS_TYPES,  # REMOVE-M4 compatibility export
    PASSTHROUGH_HELPER_CLASS_TYPES,  # REMOVE-M4 compatibility export
    RESOLVABLE_HELPER_CLASS_TYPES,  # REMOVE-M4 compatibility export
    UI_ONLY_CLASS_TYPES,  # REMOVE-M4 compatibility export
    VALUE_HELPER_CLASS_TYPES,  # REMOVE-M4 compatibility export
    HelperDiagnostic,  # REMOVE-M4 compatibility export
    _compile_helper_inputs,  # REMOVE-M4 compatibility export
    _edge_attr,  # REMOVE-M4 compatibility export
    _node_class_type,  # REMOVE-M4 compatibility export
    _node_inputs,  # REMOVE-M4 compatibility export
    _node_sort_key,  # REMOVE-M4 compatibility export
    _node_widgets,  # REMOVE-M4 compatibility export
    _sorted_nodes,  # REMOVE-M4 compatibility export
    broadcast_name,  # REMOVE-M4 compatibility export
    collect_broadcast_sources,  # REMOVE-M4 compatibility export
    collect_helper_diagnostics,  # REMOVE-M4 compatibility export
    first_link_input,  # REMOVE-M4 compatibility export
    helper_stripped_class_types,  # REMOVE-M4 compatibility export
    helper_stripped_nodes,  # REMOVE-M4 compatibility export
    is_api_link,  # REMOVE-M4 compatibility export
    is_broadcast_helper_class_type,  # REMOVE-M4 compatibility export
    is_helper_class_type,  # REMOVE-M4 compatibility export
    is_passthrough_helper_class_type,  # REMOVE-M4 compatibility export
    is_ui_only_class_type,  # REMOVE-M4 compatibility export
    is_value_helper_class_type,  # REMOVE-M4 compatibility export
)

__all__ = [
    "BROADCAST_HELPER_CLASS_TYPES",
    "HELPER_CLASS_TYPES",
    "HelperDiagnostic",
    "PASSTHROUGH_HELPER_CLASS_TYPES",
    "RESOLVABLE_HELPER_CLASS_TYPES",
    "UI_ONLY_CLASS_TYPES",
    "VALUE_HELPER_CLASS_TYPES",
    "_compile_helper_inputs",
    "_edge_attr",
    "_node_class_type",
    "_node_inputs",
    "_node_sort_key",
    "_node_widgets",
    "_sorted_nodes",
    "broadcast_name",
    "collect_broadcast_sources",
    "collect_helper_diagnostics",
    "first_link_input",
    "helper_stripped_class_types",
    "helper_stripped_nodes",
    "is_api_link",
    "is_broadcast_helper_class_type",
    "is_helper_class_type",
    "is_passthrough_helper_class_type",
    "is_ui_only_class_type",
    "is_value_helper_class_type",
]
