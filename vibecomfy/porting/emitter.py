from __future__ import annotations

import logging
from typing import Any

from vibecomfy.porting.emit import wrappers as _wrappers
from vibecomfy.porting.emit.agent_edit_core import (
    _AGENT_EDIT_STRING_ELIDE_THRESHOLD,
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
from vibecomfy.porting.emit.build_function import (
    _emit_build_function,
    _with_id_map_tail_line,
)
from vibecomfy.porting.emit.constants_hoist import (
    _SECTION_NODE_THRESHOLD,
    _SECTION_ORDER,
    _build_section_groups as _build_section_groups_impl,
    _classify_node_role,
    _classify_value_category,
    _constant_name_base_for_category,
    _constant_name_for_model_value,
    _constant_name_for_string_value,
    _drop_output_prefix_constants,
    _hoist_constants as _hoist_constants_impl,
    _model_basename,
    _resolve_graph_field_get_string,
    _translate_widget_for_key,
)
from vibecomfy.porting.emit.diagnostics import (
    EmissionDiagnostic,
    EmissionSeverity,
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
)
from vibecomfy.porting.emit.emit_kwargs import (
    _edges_in_with_subgraph_external_refs,
    _format_metadata_dict,
    _node_binding_expr,
)
from vibecomfy.porting.emit.emit_ready import (
    GENERATED_HEADER,
    LTX2_3_TAIL_PATCHES,
    _NODE_HELPER_SOURCE,
    _OUTPUT_CLASSES,
    _all_nodes_for_imports,
    _apply_overrides,
    _check_template_formatting,
    _finalize_args,
    _has_ltx_lowvram_tail,
    _import_binding_name,
    _infer_public_input_bindings,
    _is_output_class,
    _node_local_arity_check,
    _node_local_output_names,
    _node_title,
    _raw_workflow_from_metadata,
    _ready_template_tail_lines,
    _resolved_field_values,
    _source_workflow_path,
    _strip_unused_template_imports,
    _subgraph_port_index_for_instance_field,
    _terminal_output_node_ids,
)
from vibecomfy.porting.emit.entrypoints import (
    emit_agent_edit_python,
    emit_ready_template_python,
    emit_scratchpad_python,
    format_as_python,
)
from vibecomfy.porting.emit.format_values import _MODEL_FILE_SUFFIXES, _format_value
from vibecomfy.porting.emit.identity_context import (
    _drain_lookup_warning_diagnostics,
    _identity_for_node,
    _identity_for_node_id,
    _node_local_class_defaults,
    _record_lookup_warning,
    _use_object_info_identities,
)
from vibecomfy.porting.emit.metadata_blocks import (
    _apply_ready_template_metadata_defaults,
    _custom_node_packs_for_emit,
    _format_models_block,
    _format_ready_metadata_build,
    _metadata_extras_for_emit,
    _model_assets_for_emit,
    _requirements_expr_for_emit,
)
from vibecomfy.porting.emit.naming_codegen import (
    _SHADOWING_OUTPUT_ALIASES,
    _SHADOWING_OUTPUT_NAMES,
    _UUID_RE,
    _apply_locked_variable_names,
    _assignment_target,
    _class_collision_suffix,
    _compute_output_variable_names,
    _compute_variable_names,
    _connection_role_name,
    _edge_ref_expr,
    _empty_text_role,
    _first_output_var,
    _has_out_of_range_edge,
    _id_sort_key,
    _is_schema_confirmed_single_output,
    _is_single_output_ref,
    _is_valid_locked_variable_alias,
    _live_output_slots_for_function,
    _locked_variable_uid_map,
    _node_output_names,
    _output_fallback_diagnostic,
    _safe_output_name,
    _safe_output_var_name,
    _safe_var,
    _schema_output_names_for_unpack,
    _shadowing_output_prefix,
    _topological_node_order,
)
from vibecomfy.porting.emit.node_kwargs_core import (
    _CURATED_SCHEMA_DEFAULTS,
    _collect_emission_diagnostics,
    _is_any_link,
    _is_link,
    _is_power_lora_config,
    _is_schema_default,
    _node_kwargs,
    _positional_ui_widget_names,
    _power_lora_widget_index,
    _translate_power_lora_loader_widget,
    _ui_widget_values_by_name,
    _ui_widget_aliases,
)
from vibecomfy.porting.emit.public_inputs import (
    _PublicInputBinding,
    _PublicInputSpec,
    _format_public_inputs_block,
    _looks_like_placeholder_filename,
    _public_input_specs as _public_input_specs_impl,
    _remap_public_inputs_for_materialized_subgraphs as _remap_public_inputs_for_materialized_subgraphs_impl,
)
from vibecomfy.porting.emit.signatures import (
    InputSignatureField,
    NodeSignatureRow,
    OutputSignatureField,
    _build_input_signature_fields,
    _build_output_signature_fields,
    _compatible_output_signature_rank,
    emit_available_node_signatures,
    format_signature_rows,
)
from vibecomfy.porting.emit.subgraph_calls import (
    COMFY_TYPE_TO_PY_HINT,
    _apply_subgraph_names_to_prepared,
    _emit_subgraph_call_statement,
    _subgraph_call_kwargs,
    _subgraph_docstring,
    _subgraph_instance_port_candidate_names,
    _subgraph_instance_widget_values,
    _subgraph_node_id_required,
    _subgraph_result_base,
    _subgraph_return_expr,
    _subgraph_signature,
    _unique_var,
)
from vibecomfy.porting.emit.subgraph_defs import (
    _SubgraphDef,
    _SubgraphPort,
    _build_subgraph_def,
    _disambiguated_subgraph_slugs,
    _safe_kwarg_name,
    _short_subgraph_id_prefix,
    _slugify_identifier,
    _subgraph_default_args,
    _subgraph_definitions_from_raw,
    _subgraph_emitted_node_id,
    _subgraph_input_kwarg_name,
    _subgraph_topological_order,
    _unique_port_name,
    _widget_default_for_target,
    slugify_subgraph_name,
    subgraph_source_hash,
)
from vibecomfy.porting.emit.subgraph_functions import _emit_subgraph_functions
from vibecomfy.porting.emit.wrappers import (
    FALLBACK_CLASS_TYPES,
    RESERVED_WRAPPER_INPUT_NAMES,
    UI_ONLY_CLASS_TYPES,
    _STATIC_WRAPPER_MODULES,
    _wrapper_class_name_candidate,
    _wrapper_class_to_module,
    _wrapper_class_type_for_symbol,
    _wrapper_imports_for_nodes,
    _wrapper_kwarg_name,
    _wrapper_module_for_class,
    _wrapper_modules,
    _wrapper_symbol_for_class,
)
from vibecomfy.porting.widgets.schema import WIDGET_SCHEMA

logger = logging.getLogger(__name__)

for _public_entrypoint in (
    emit_agent_edit_python,
    emit_ready_template_python,
    emit_scratchpad_python,
    format_as_python,
):
    _public_entrypoint.__module__ = __name__
del _public_entrypoint


def __getattr__(name: str) -> Any:
    if name in {"_WRAPPER_CLASS_TO_MODULE", "_WRAPPER_CLASS_TO_SYMBOL"}:
        return getattr(_wrappers, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def _build_section_groups(
    workflow_nodes: dict[str, Any],
    edges_in: dict[str, list[Any]],
) -> dict[str, list[str]]:
    return _build_section_groups_impl(
        workflow_nodes,
        edges_in,
        topological_node_order=_topological_node_order,
    )


def _hoist_constants(
    workflow_nodes: dict[str, Any],
    edges_in: dict[str, list[Any]],
    var_names: dict[str, str],
) -> tuple[list[str], dict[tuple[str, str], str]]:
    return _hoist_constants_impl(
        workflow_nodes,
        edges_in,
        var_names,
        is_link=_is_link,
        ui_widget_aliases=_ui_widget_aliases,
        is_schema_default=_is_schema_default,
    )


def _public_input_specs(
    workflow_nodes: dict[str, Any],
    edges_in: dict[str, list[Any]],
    var_names: dict[str, str],
    output_var_names: dict[str, dict[int, str]],
    *,
    registered_inputs: dict[str, tuple[str, str]] | None,
    constant_map: dict[tuple[str, str], str],
) -> list[_PublicInputSpec]:
    return _public_input_specs_impl(
        workflow_nodes,
        edges_in,
        var_names,
        output_var_names,
        registered_inputs=registered_inputs,
        constant_map=constant_map,
        resolve_graph_field_get_string=_resolve_graph_field_get_string,
        resolved_field_values=_resolved_field_values,
        first_output_var=_first_output_var,
        ui_widget_aliases=_ui_widget_aliases,
        infer_public_input_bindings=lambda nodes, incoming, reserved: _infer_public_input_bindings(
            nodes,
            incoming,
            reserved_names=reserved,
        ),
    )


def _remap_public_inputs_for_materialized_subgraphs(
    specs: list[_PublicInputSpec],
    workflow_nodes: dict[str, Any],
    subgraphs: dict[str, _SubgraphDef],
) -> list[_PublicInputSpec]:
    return _remap_public_inputs_for_materialized_subgraphs_impl(
        specs,
        workflow_nodes,
        subgraphs,
        subgraph_port_index_for_instance_field=_subgraph_port_index_for_instance_field,
        subgraph_emitted_node_id=_subgraph_emitted_node_id,
    )


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
]
