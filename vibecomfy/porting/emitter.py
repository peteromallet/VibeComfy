from __future__ import annotations

from vibecomfy.porting.emit.entrypoints import (
    _NODE_HELPER_SOURCE,
    _emit_build_function,
    emit_agent_edit_python as _emit_agent_edit_python,
    emit_ready_template_python as _emit_ready_template_python,
    emit_scratchpad_python as _emit_scratchpad_python,
    format_as_python as _format_as_python,
)
from vibecomfy.porting.emit.identity import (
    _drain_lookup_warning_diagnostics,
    _identity_for_node,
    _identity_for_node_id,
    _node_local_arity_check,
    _node_local_class_defaults,
    _node_local_output_names,
    _record_lookup_warning,
    _use_object_info_identities,
)
from vibecomfy.porting.emit.models import *  # noqa: F403
from vibecomfy.porting.emit.public_inputs import *  # noqa: F403
from vibecomfy.porting.emit.signatures import (
    EmissionDiagnostic,
    EmissionSeverity,
    InputSignatureField,
    NodeSignatureRow,
    OutputSignatureField,
    READABILITY_WARNING_AVOIDABLE_POSITIONAL_OUTPUT,
    READABILITY_WARNING_CODES,
    READABILITY_WARNING_GENERATED_TEMPLATE_NOT_FORMATTED,
    READABILITY_WARNING_GENERATED_VARIABLE_NAME_TOO_LONG,
    READABILITY_WARNING_HIDDEN_MODEL_FILENAME,
    READABILITY_WARNING_LOCAL_HELPER_COPY_IN_STRICT_TEMPLATE,
    READABILITY_WARNING_LOCKED_VARIABLE_ALIAS_COLLISION,
    READABILITY_WARNING_LOCKED_VARIABLE_ALIAS_INVALID,
    READABILITY_WARNING_LOCKED_VARIABLE_ALIAS_MISSING,
    READABILITY_WARNING_LOCKED_VARIABLE_UID_COLLISION,
    READABILITY_WARNING_LONG_ONE_LINE_NODE_CALL,
    READABILITY_WARNING_OUTPUT_NAME_AMBIGUITY,
    READABILITY_WARNING_SCHEMA_BACKED_WIDGET_ALIAS_NOT_RESOLVED,
    READABILITY_WARNING_SCHEMA_UNKNOWN_KWARG_HIDDEN_BY_EXTRAS,
    READABILITY_WARNING_SUBGRAPH_INPUT_UNBOUND,
    emit_available_node_signatures,
    filter_signature_rows_to_in_graph_nodes,
    format_signature_rows,
)
from vibecomfy.porting.emit.subgraph import *  # noqa: F403
from vibecomfy.porting.emit.valueclassify import *  # noqa: F403
from vibecomfy.porting.emit.wrappers import *  # noqa: F403
from vibecomfy.porting.emit.emit_constants import (
    _CURATED_SCHEMA_DEFAULTS,
    _apply_ready_template_metadata_defaults,
    _drop_output_prefix_constants,
    _filename_is_url_derived,
    _is_derivable_provenance,
    _metadata_extras_for_emit,
    _translate_widget_for_key,
    _ui_widget_aliases,
)
from vibecomfy.porting.emit.emit_kwargs import *  # noqa: F403
from vibecomfy.porting.emit.emit_kwargs import _node_kwargs
from vibecomfy.porting.emit.emit_subgraph import _safe_kwarg_name
from vibecomfy.porting.emit.emit_subgraph import _ui_widget_values_by_name
from vibecomfy.porting.widgets.schema import WIDGET_SCHEMA
from vibecomfy.porting.emit.emit_prepare import (
    _VIRTUAL_WIRE_EMITTER_CLASS_TYPES,
    _agent_edit_comment,
    _agent_edit_output_aliases,
    _agent_edit_raw_output_names,
    _agent_edit_slot_alias_parts,
    _emit_agent_edit_lines,
    _meaningful_title,
    _prepare_workflow_for_emit,
    _title_canonical,
)
from vibecomfy.porting.emit.emit_ready import (
    GENERATED_HEADER,
    LTX2_3_TAIL_PATCHES,
    _all_nodes_for_imports,
    _apply_overrides,
    _custom_node_packs_for_emit,
    _declared_exec_outputs,
    _finalize_args,
    _format_ready_metadata_build,
    _has_ltx_lowvram_tail,
    _ltx_travel_template_omits_synthetic_audio,
    _import_binding_name,
    _lock_entries_by_class,
    _raw_workflow_from_metadata,
    _prune_dead_branches_for_emit,
    _ready_template_tail_lines,
    _source_workflow_path,
    _strip_unused_template_imports,
    _terminal_output_node_ids,
)


def format_as_python(*args, **kwargs):
    return _format_as_python(*args, **kwargs)


def emit_ready_template_python(*args, **kwargs):
    return _emit_ready_template_python(*args, **kwargs)


def emit_agent_edit_python(*args, **kwargs):
    return _emit_agent_edit_python(*args, **kwargs)


def emit_scratchpad_python(*args, **kwargs):
    return _emit_scratchpad_python(*args, **kwargs)


__all__ = [
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
    "_safe_kwarg_name",
]
