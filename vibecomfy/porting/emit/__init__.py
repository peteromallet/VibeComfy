"""emit/ — ready-template Python emission cluster.

Sub-package of :mod:`vibecomfy.porting`.  Contains the core emitter,
UI (litegraph) emitter, and supporting helpers for formatting, naming,
and node-kwarg extraction.
"""

from .emitter import (  # noqa: F401
    EmissionDiagnostic,
    EmissionSeverity,
    READABILITY_WARNING_AVOIDABLE_POSITIONAL_OUTPUT,
    READABILITY_WARNING_OUTPUT_NAME_AMBIGUITY,
    READABILITY_WARNING_SCHEMA_BACKED_WIDGET_ALIAS_NOT_RESOLVED,
    READABILITY_WARNING_HIDDEN_MODEL_FILENAME,
    READABILITY_WARNING_LOCAL_HELPER_COPY_IN_STRICT_TEMPLATE,
    READABILITY_WARNING_LONG_ONE_LINE_NODE_CALL,
    READABILITY_WARNING_GENERATED_TEMPLATE_NOT_FORMATTED,
    READABILITY_WARNING_GENERATED_VARIABLE_NAME_TOO_LONG,
    READABILITY_WARNING_LOCKED_VARIABLE_ALIAS_INVALID,
    READABILITY_WARNING_LOCKED_VARIABLE_ALIAS_COLLISION,
    READABILITY_WARNING_LOCKED_VARIABLE_ALIAS_MISSING,
    READABILITY_WARNING_LOCKED_VARIABLE_UID_COLLISION,
    READABILITY_WARNING_CODES,
    NodeSignatureRow,
    InputSignatureField,
    OutputSignatureField,
    emit_available_node_signatures,
    format_signature_rows,
    format_as_python,
    emit_ready_template_python,
    emit_agent_edit_python,
    emit_scratchpad_python,
)

from .node_kwargs import (  # noqa: F401
    apply_overrides,
    node_kwargs,
)

from .formatting import (  # noqa: F401
    format_kwargs_block,
    format_metadata_dict,
    format_value,
)

from .naming import (  # noqa: F401
    compute_variable_names,
    connection_role_name,
    empty_text_role,
    safe_var,
    topological_node_order,
)

from .ui import (  # noqa: F401
    WidgetShapeEvidence,
    derive_widget_shape_evidence,
    extract_raw_ui_node_map,
    materialize_litegraph_node,
    _normalize_pinned_node_link_refs,
    _raw_ui_payload_for_pin,
    emit_ui_json,
    offline_emitter_normalizer_self_consistency_check,
    structural_validate,
    default_output_path,
)

__all__ = [
    # emitter.py (24 names)
    "EmissionDiagnostic",
    "EmissionSeverity",
    "READABILITY_WARNING_AVOIDABLE_POSITIONAL_OUTPUT",
    "READABILITY_WARNING_OUTPUT_NAME_AMBIGUITY",
    "READABILITY_WARNING_SCHEMA_BACKED_WIDGET_ALIAS_NOT_RESOLVED",
    "READABILITY_WARNING_HIDDEN_MODEL_FILENAME",
    "READABILITY_WARNING_LOCAL_HELPER_COPY_IN_STRICT_TEMPLATE",
    "READABILITY_WARNING_LONG_ONE_LINE_NODE_CALL",
    "READABILITY_WARNING_GENERATED_TEMPLATE_NOT_FORMATTED",
    "READABILITY_WARNING_GENERATED_VARIABLE_NAME_TOO_LONG",
    "READABILITY_WARNING_LOCKED_VARIABLE_ALIAS_INVALID",
    "READABILITY_WARNING_LOCKED_VARIABLE_ALIAS_COLLISION",
    "READABILITY_WARNING_LOCKED_VARIABLE_ALIAS_MISSING",
    "READABILITY_WARNING_LOCKED_VARIABLE_UID_COLLISION",
    "READABILITY_WARNING_CODES",
    "NodeSignatureRow",
    "InputSignatureField",
    "OutputSignatureField",
    "emit_available_node_signatures",
    "format_signature_rows",
    "format_as_python",
    "emit_ready_template_python",
    "emit_agent_edit_python",
    "emit_scratchpad_python",
    # node_kwargs.py (2 names)
    "apply_overrides",
    "node_kwargs",
    # formatting.py (3 names)
    "format_kwargs_block",
    "format_metadata_dict",
    "format_value",
    # naming.py (5 names)
    "compute_variable_names",
    "connection_role_name",
    "empty_text_role",
    "safe_var",
    "topological_node_order",
    # ui.py (10 names)
    "WidgetShapeEvidence",
    "derive_widget_shape_evidence",
    "extract_raw_ui_node_map",
    "materialize_litegraph_node",
    "_normalize_pinned_node_link_refs",
    "_raw_ui_payload_for_pin",
    "emit_ui_json",
    "offline_emitter_normalizer_self_consistency_check",
    "structural_validate",
    "default_output_path",
]
