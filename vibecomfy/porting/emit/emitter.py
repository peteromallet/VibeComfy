from __future__ import annotations

import ast
import contextlib
import contextvars
import hashlib
import importlib
import json
import keyword
import logging
import pprint
import re
from collections import Counter
from dataclasses import asdict, dataclass, field, replace
from pathlib import Path
from typing import Any, Literal, Mapping

from vibecomfy.errors import ArityDisagreementError, ConversionParityError
from vibecomfy.node_packs_lockfile import LockEntry, read_lockfile
from vibecomfy._workflow_helpers import RESOLVABLE_HELPER_CLASS_TYPES
from vibecomfy.porting.widgets.aliases import resolve_widget_key_with_provenance
from vibecomfy.porting.object_info import (
    check_output_arity_consensus,
    class_defaults,
    class_has_list_output,
    class_output_count,
    ObjectInfoIdentity,
    resolve_class_entry,
)
from vibecomfy.porting.object_info import output_names as class_output_names

# Re-exports from emit_kwargs.py (Step 4 of M2 structural decomposition).
# All these names remain importable from vibecomfy.porting.emitter so that
# existing callers (tests, commands, etc.) continue to work unchanged.
from vibecomfy.porting.emit_kwargs import (  # noqa: E402
    _is_link as _is_link,
    _is_any_link as _is_any_link,
    _ui_output_names as _ui_output_names,
    _UUID_RE as _UUID_RE,
    _safe_var as _safe_var,
    _connection_role_name as _connection_role_name,
    _empty_text_role as _empty_text_role,
    _id_sort_key as _id_sort_key,
    _topological_node_order as _topological_node_order,
    _compute_variable_names as _compute_variable_names,
    _locked_variable_uid_map as _locked_variable_uid_map,
    _apply_locked_variable_names as _apply_locked_variable_names,
    _is_valid_locked_variable_alias as _is_valid_locked_variable_alias,
    _compute_output_variable_names as _compute_output_variable_names,
    _SHADOWING_OUTPUT_NAMES as _SHADOWING_OUTPUT_NAMES,
    _SHADOWING_OUTPUT_ALIASES as _SHADOWING_OUTPUT_ALIASES,
    _shadowing_output_prefix as _shadowing_output_prefix,
    _safe_output_var_name as _safe_output_var_name,
    _schema_output_names_for_unpack as _schema_output_names_for_unpack,
    _declared_ui_output_names as _declared_ui_output_names,
    _has_out_of_range_edge as _has_out_of_range_edge,
    _class_collision_suffix as _class_collision_suffix,
    _live_output_slots_for_function as _live_output_slots_for_function,
    _edges_in_with_subgraph_external_refs as _edges_in_with_subgraph_external_refs,
    _assignment_target as _assignment_target,
    _first_output_var as _first_output_var,
    _format_value as _format_value,
    _is_schema_default as _is_schema_default,
    _format_metadata_dict as _format_metadata_dict,
    _node_output_names as _node_output_names,
    _declared_output_names_for_call_metadata as _declared_output_names_for_call_metadata,
    _safe_output_name as _safe_output_name,
    _output_fallback_diagnostic as _output_fallback_diagnostic,
    _is_schema_confirmed_single_output as _is_schema_confirmed_single_output,
    _is_single_output_ref as _is_single_output_ref,
    _node_binding_expr as _node_binding_expr,
    _edge_ref_expr as _edge_ref_expr,
    _wrapper_kwarg_name as _wrapper_kwarg_name,
    _translate_power_lora_loader_widget as _translate_power_lora_loader_widget,
    _power_lora_widget_index as _power_lora_widget_index,
    _is_power_lora_config as _is_power_lora_config,
    _collect_emission_diagnostics as _collect_emission_diagnostics,
    _node_kwargs as _node_kwargs,
)



# Re-exports from emit_subgraph.py (Step 5 of M2 structural decomposition).
from vibecomfy.porting.emit_subgraph import (  # noqa: E402
    _SubgraphPort as _SubgraphPort,
    _SubgraphDef as _SubgraphDef,
    slugify_subgraph_name as slugify_subgraph_name,
    _slugify_identifier as _slugify_identifier,
    _safe_kwarg_name as _safe_kwarg_name,
    _subgraph_input_kwarg_name as _subgraph_input_kwarg_name,
    _unique_port_name as _unique_port_name,
    _subgraph_definitions_from_raw as _subgraph_definitions_from_raw,
    _disambiguated_subgraph_slugs as _disambiguated_subgraph_slugs,
    _build_subgraph_def as _build_subgraph_def,
    subgraph_source_hash as subgraph_source_hash,
    _subgraph_default_args as _subgraph_default_args,
    _widget_default_for_target as _widget_default_for_target,
    _apply_subgraph_names_to_prepared as _apply_subgraph_names_to_prepared,
    _subgraph_result_base as _subgraph_result_base,
    _unique_var as _unique_var,
    READABILITY_WARNING_SUBGRAPH_INPUT_UNBOUND as READABILITY_WARNING_SUBGRAPH_INPUT_UNBOUND,
    _emit_subgraph_functions as _emit_subgraph_functions,
    _subgraph_topological_order as _subgraph_topological_order,
    _short_subgraph_id_prefix as _short_subgraph_id_prefix,
    _subgraph_emitted_node_id as _subgraph_emitted_node_id,
    _subgraph_node_id_required as _subgraph_node_id_required,
    _subgraph_signature as _subgraph_signature,
    _subgraph_docstring as _subgraph_docstring,
    _emit_subgraph_call_statement as _emit_subgraph_call_statement,
    _subgraph_call_kwargs as _subgraph_call_kwargs,
    _subgraph_instance_port_candidate_names as _subgraph_instance_port_candidate_names,
    _subgraph_instance_widget_values as _subgraph_instance_widget_values,
    _positional_ui_widget_names as _positional_ui_widget_names,
    _ui_widget_values_by_name as _ui_widget_values_by_name,
    _subgraph_return_expr as _subgraph_return_expr,
)

# Re-exports from emit_constants.py (Step 6 of M2 structural decomposition).
from vibecomfy.porting.emit_constants import (  # noqa: E402
    UI_ONLY_CLASS_TYPES as UI_ONLY_CLASS_TYPES,
    FALLBACK_CLASS_TYPES as FALLBACK_CLASS_TYPES,
    _STATIC_WRAPPER_MODULES as _STATIC_WRAPPER_MODULES,
    _WRAPPER_CLASS_TO_MODULE as _WRAPPER_CLASS_TO_MODULE,
    _WRAPPER_CLASS_TO_SYMBOL as _WRAPPER_CLASS_TO_SYMBOL,
    _wrapper_modules as _wrapper_modules,
    _wrapper_class_to_module as _wrapper_class_to_module,
    _wrapper_class_type_for_symbol as _wrapper_class_type_for_symbol,
    _wrapper_class_name_candidate as _wrapper_class_name_candidate,
    _wrapper_module_for_class as _wrapper_module_for_class,
    _wrapper_symbol_for_class as _wrapper_symbol_for_class,
    _wrapper_imports_for_nodes as _wrapper_imports_for_nodes,
    _classify_value_category as _classify_value_category,
    _classify_node_role as _classify_node_role,
    _constant_name_base_for_category as _constant_name_base_for_category,
    _constant_name_for_string_value as _constant_name_for_string_value,
    _literal_default_from_graph_get as _literal_default_from_graph_get,
    _resolve_graph_field_get_string as _resolve_graph_field_get_string,
    _model_path_parts as _model_path_parts,
    _model_basename as _model_basename,
    _model_family_constant_name as _model_family_constant_name,
    _canonical_prefixed_model_value as _canonical_prefixed_model_value,
    _model_constant_base_priority as _model_constant_base_priority,
    _canonical_model_values_by_base as _canonical_model_values_by_base,
    _constant_name_for_model_value as _constant_name_for_model_value,
    _build_section_groups as _build_section_groups,
    _hoist_constants as _hoist_constants,
    _translate_widget_for_key as _translate_widget_for_key,
    _drop_output_prefix_constants as _drop_output_prefix_constants,
    _ui_widget_aliases as _ui_widget_aliases,
    _format_models_block as _format_models_block,
    _filename_is_url_derived as _filename_is_url_derived,
    _apply_ready_template_metadata_defaults as _apply_ready_template_metadata_defaults,
    _metadata_extras_for_emit as _metadata_extras_for_emit,
    _is_derivable_provenance as _is_derivable_provenance,
    _normalize_model_path as _normalize_model_path,
    _model_assets_for_emit as _model_assets_for_emit,
    _model_key as _model_key,
    _model_role_key as _model_role_key,
    _requirements_expr_for_emit as _requirements_expr_for_emit,
    _looks_like_placeholder_filename as _looks_like_placeholder_filename,
    RESERVED_WRAPPER_INPUT_NAMES as RESERVED_WRAPPER_INPUT_NAMES,
    _ROLE_CLASSIFICATION as _ROLE_CLASSIFICATION,
    _SECTION_NODE_THRESHOLD as _SECTION_NODE_THRESHOLD,
    _CURATED_SCHEMA_DEFAULTS as _CURATED_SCHEMA_DEFAULTS,
    LTX2_3_TAIL_PATCHES as LTX2_3_TAIL_PATCHES,
    _AGENT_EDIT_STRING_ELIDE_THRESHOLD as _AGENT_EDIT_STRING_ELIDE_THRESHOLD,
    _SECTION_ORDER as _SECTION_ORDER,
    _LOAD_IMAGE_FAMILY as _LOAD_IMAGE_FAMILY,
    _MODEL_FAMILY_CONSTANTS as _MODEL_FAMILY_CONSTANTS,
    _MODEL_CONSTANT_BASE_PRIORITY as _MODEL_CONSTANT_BASE_PRIORITY,
)

# Re-exports from emit_prepare.py (Step 7 of M2 structural decomposition).
# _VIRTUAL_WIRE_EMITTER_CLASS_TYPES, _prepare_workflow_for_emit, and
# _emit_agent_edit_lines are defined there; re-exported here so existing
# callers (tests, commands, etc.) continue to work unchanged.
from vibecomfy.porting.emit_prepare import (  # noqa: E402
    _VIRTUAL_WIRE_EMITTER_CLASS_TYPES as _VIRTUAL_WIRE_EMITTER_CLASS_TYPES,
    _prepare_workflow_for_emit as _prepare_workflow_for_emit,
    _emit_agent_edit_lines as _emit_agent_edit_lines,
    _agent_edit_output_aliases as _agent_edit_output_aliases,
    _agent_edit_raw_output_names as _agent_edit_raw_output_names,
    _title_canonical as _title_canonical,
    _meaningful_title as _meaningful_title,
    _agent_edit_comment as _agent_edit_comment,
    _agent_edit_slot_alias_parts as _agent_edit_slot_alias_parts,
)

# Re-exports from emit_ready.py (Step 8 of M2 structural decomposition).
# All these names remain importable from vibecomfy.porting.emitter so that
# existing callers (tests, commands, etc.) continue to work unchanged.
from vibecomfy.porting.emit_ready import (  # noqa: E402
    _PublicInputBinding as _PublicInputBinding,
    _PublicInputSpec as _PublicInputSpec,
    GENERATED_HEADER as GENERATED_HEADER,
    _node_title as _node_title,
    _resolved_field_values as _resolved_field_values,
    _infer_public_input_bindings as _infer_public_input_bindings,
    _public_input_specs as _public_input_specs,
    _format_public_inputs_block as _format_public_inputs_block,
    _subgraph_port_index_for_instance_field as _subgraph_port_index_for_instance_field,
    _remap_public_inputs_for_materialized_subgraphs as _remap_public_inputs_for_materialized_subgraphs,
    _lock_entries_by_class as _lock_entries_by_class,
    _custom_node_packs_for_emit as _custom_node_packs_for_emit,
    _format_ready_metadata_build as _format_ready_metadata_build,
    _strip_unused_template_imports as _strip_unused_template_imports,
    _import_binding_name as _import_binding_name,
    emit_ready_template_python as emit_ready_template_python,
    _emit_ready_template_python_inner as _emit_ready_template_python_inner,
    _prune_dead_branches_for_emit as _prune_dead_branches_for_emit,
    _is_dead_optional_output_input as _is_dead_optional_output_input,
    _ltx_travel_template_omits_synthetic_audio as _ltx_travel_template_omits_synthetic_audio,
    _source_workflow_path as _source_workflow_path,
    _raw_workflow_from_metadata as _raw_workflow_from_metadata,
    _all_nodes_for_imports as _all_nodes_for_imports,
    _emit_build_function as _emit_build_function,
    _with_id_map_tail_line as _with_id_map_tail_line,
    _OUTPUT_CLASSES as _OUTPUT_CLASSES,
    _ready_template_tail_lines as _ready_template_tail_lines,
    _finalize_args as _finalize_args,
    _terminal_output_node_ids as _terminal_output_node_ids,
    _is_output_class as _is_output_class,
    _check_template_formatting as _check_template_formatting,
    _has_ltx_lowvram_tail as _has_ltx_lowvram_tail,
    _apply_overrides as _apply_overrides,
    _NODE_HELPER_SOURCE as _NODE_HELPER_SOURCE,
    _node_local_output_names as _node_local_output_names,
    _node_local_arity_check as _node_local_arity_check,
)

# Re-exports from emit_scratchpad.py (Step 9 of M2 structural decomposition).
# emit_scratchpad_python and _emit_scratchpad_python_inner are defined there;
# re-exported here so existing callers (convert.py, tests, etc.) continue
# to work unchanged.
from vibecomfy.porting.emit_scratchpad import (  # noqa: E402
    emit_scratchpad_python as emit_scratchpad_python,
    _emit_scratchpad_python_inner as _emit_scratchpad_python_inner,
)

# Re-exports from emit_agent_edit.py (Step 10 of M2 structural decomposition).
# emit_agent_edit_python is defined there; re-exported here so existing
# callers (edit_session.py, __init__.py, etc.) continue to work unchanged.
from vibecomfy.porting.emit_agent_edit import (  # noqa: E402
    emit_agent_edit_python as emit_agent_edit_python,
)

# --- Node-local object_info identity plumbing --------------------------------
#
# Conversion (T21) builds a ``node_id -> ObjectInfoIdentity`` map from
# provenance and threads it into the top-level emitter entry points. Internal
# helpers operate on ``VibeNode`` objects and don't take the map as a
# parameter, so we expose it via a contextvar and read it from node-local call
# sites that already have a node reference.
#
# When no identity map is active (legacy/unprovenanced flows, tests that call
# helpers directly), all lookups fall back to the historical class-only
# behavior, so this change is additive and non-breaking.

_NODE_OBJECT_INFO_IDENTITIES: contextvars.ContextVar[
    "dict[str, ObjectInfoIdentity] | None"
] = contextvars.ContextVar("_NODE_OBJECT_INFO_IDENTITIES", default=None)

# Recorder for identity-aware lookup warnings observed during emission. When a
# recorder list is bound, node-local helpers append (node_id, class_type, code,
# message) tuples so the top-level emit entry points can drain them into the
# caller's ``EmissionDiagnostic`` list.
_NODE_OBJECT_INFO_LOOKUP_WARNINGS: contextvars.ContextVar[
    "list[tuple[str | None, str, str, str]] | None"
] = contextvars.ContextVar("_NODE_OBJECT_INFO_LOOKUP_WARNINGS", default=None)


@contextlib.contextmanager
def _use_object_info_identities(
    identities: "dict[str, Any] | None",
):
    """Bind an optional ``node_id -> ObjectInfoIdentity`` map for this emit.

    Also opens a fresh warning recorder so identity-aware lookup helpers can
    report ``unprovenanced_class_fallback`` / ``provenance_identity_cache_miss``
    occurrences back to the top-level emit entry point.
    """
    normalized: "dict[str, ObjectInfoIdentity] | None" = None
    if identities:
        normalized = {}
        for raw_id, ident in identities.items():
            if ident is None:
                continue
            if isinstance(ident, ObjectInfoIdentity):
                normalized[str(raw_id)] = ident
            elif isinstance(ident, Mapping):
                try:
                    normalized[str(raw_id)] = ObjectInfoIdentity(
                        pack_slug=str(ident.get("pack_slug") or ident.get("pack") or ""),
                        git_commit=(str(ident["git_commit"]) if ident.get("git_commit") else None),
                        evidence_identity=(
                            str(ident["evidence_identity"]) if ident.get("evidence_identity") else None
                        ),
                    )
                except Exception:
                    continue
        if not normalized:
            normalized = None
    id_token = _NODE_OBJECT_INFO_IDENTITIES.set(normalized)
    warn_token = _NODE_OBJECT_INFO_LOOKUP_WARNINGS.set([])
    try:
        yield
    finally:
        _NODE_OBJECT_INFO_LOOKUP_WARNINGS.reset(warn_token)
        _NODE_OBJECT_INFO_IDENTITIES.reset(id_token)


# Mapping from consume-layer warning codes to emission diagnostic codes.
_LOOKUP_WARNING_CODE_TO_EMISSION: dict[str, str] = {
    "unprovenanced_cache_fallback": "unprovenanced_class_fallback",
    "provenanced_cache_miss_fallback": "provenance_identity_cache_miss",
    "identity_cache_miss": "provenance_identity_cache_miss",
}


def _record_lookup_warning(node: Any, class_type: str, warning: Any) -> None:
    """If a warning recorder is bound, append this identity-lookup warning."""
    if warning is None:
        return
    bucket = _NODE_OBJECT_INFO_LOOKUP_WARNINGS.get()
    if bucket is None:
        return
    node_id = str(getattr(node, "id", "")) if node is not None else ""
    bucket.append(
        (
            node_id or None,
            class_type,
            str(getattr(warning, "code", "") or ""),
            str(getattr(warning, "message", "") or ""),
        )
    )


def _drain_lookup_warning_diagnostics(
    diagnostics: "list[EmissionDiagnostic] | None",
) -> bool:
    """Drain the bound warning recorder into *diagnostics*. Returns True if any
    low-confidence warnings were emitted (so callers can flag low_confidence).

    Dedupes by (node_id, class_type, emission code) so a class touched on many
    code paths produces one diagnostic per node, not one per call site.
    """
    bucket = _NODE_OBJECT_INFO_LOOKUP_WARNINGS.get()
    if not bucket:
        return False
    low_conf = False
    seen: set[tuple[str | None, str, str]] = set()
    for node_id, class_type, code, message in bucket:
        emit_code = _LOOKUP_WARNING_CODE_TO_EMISSION.get(code)
        if not emit_code:
            continue
        key = (node_id, class_type, emit_code)
        if key in seen:
            continue
        seen.add(key)
        low_conf = True
        if diagnostics is not None:
            diagnostics.append(
                EmissionDiagnostic(
                    code=emit_code,
                    message=message,
                    severity="warning",
                    node_id=node_id,
                    class_type=class_type,
                    detail={"lookup_warning_code": code},
                )
            )
    return low_conf


def _identity_for_node(node: Any) -> "ObjectInfoIdentity | None":
    """Return the bound identity for *node* (by ``node.id``), if any."""
    table = _NODE_OBJECT_INFO_IDENTITIES.get()
    if not table or node is None:
        return None
    node_id = getattr(node, "id", None)
    if node_id is None:
        return None
    return table.get(str(node_id))


def _identity_for_node_id(node_id: Any) -> "ObjectInfoIdentity | None":
    table = _NODE_OBJECT_INFO_IDENTITIES.get()
    if not table or node_id is None:
        return None
    return table.get(str(node_id))


def _node_local_class_defaults(node: Any) -> dict[str, Any]:
    """Identity-aware schema defaults for *node*; class-only fallback."""
    class_type = str(node.class_type)
    identity = _identity_for_node(node)
    if identity is not None:
        try:
            result = resolve_class_entry(
                class_type, identity=identity, allow_class_fallback=True
            )
        except Exception:
            return dict(class_defaults(class_type))
        _record_lookup_warning(node, class_type, result.warning)
        entry = result.entry
        if entry is not None:
            defaults: dict[str, Any] = {}
            inputs = entry.get("inputs") or {}
            if isinstance(inputs, Mapping):
                for section in ("required", "optional"):
                    group = inputs.get(section)
                    if not isinstance(group, Mapping):
                        continue
                    for name, spec in group.items():
                        if (
                            isinstance(spec, (list, tuple))
                            and len(spec) > 1
                            and isinstance(spec[1], Mapping)
                            and "default" in spec[1]
                        ):
                            defaults[str(name)] = spec[1]["default"]
            return defaults
    return dict(class_defaults(class_type))
from vibecomfy.porting.widgets.schema import WIDGET_SCHEMA
# -- readability warning codes ------------------------------------------------
READABILITY_WARNING_AVOIDABLE_POSITIONAL_OUTPUT = "avoidable_positional_output"
READABILITY_WARNING_OUTPUT_NAME_AMBIGUITY = "output_name_ambiguity"
READABILITY_WARNING_SCHEMA_BACKED_WIDGET_ALIAS_NOT_RESOLVED = "schema_backed_widget_alias_not_resolved"
READABILITY_WARNING_HIDDEN_MODEL_FILENAME = "hidden_model_filename"
READABILITY_WARNING_LOCAL_HELPER_COPY_IN_STRICT_TEMPLATE = "local_helper_copy_in_strict_template"
READABILITY_WARNING_LONG_ONE_LINE_NODE_CALL = "long_one_line_node_call"
READABILITY_WARNING_GENERATED_TEMPLATE_NOT_FORMATTED = "generated_template_not_formatted"
READABILITY_WARNING_GENERATED_VARIABLE_NAME_TOO_LONG = "generated_variable_name_too_long"
READABILITY_WARNING_SCHEMA_UNKNOWN_KWARG_HIDDEN_BY_EXTRAS = "schema_unknown_kwarg_hidden_by_extras"
READABILITY_WARNING_LOCKED_VARIABLE_ALIAS_INVALID = "locked_variable_alias_invalid"
READABILITY_WARNING_LOCKED_VARIABLE_ALIAS_COLLISION = "locked_variable_alias_collision"
READABILITY_WARNING_LOCKED_VARIABLE_ALIAS_MISSING = "locked_variable_alias_missing"
READABILITY_WARNING_LOCKED_VARIABLE_UID_COLLISION = "locked_variable_uid_collision"

READABILITY_WARNING_CODES: frozenset[str] = frozenset(
    {
        READABILITY_WARNING_AVOIDABLE_POSITIONAL_OUTPUT,
        READABILITY_WARNING_OUTPUT_NAME_AMBIGUITY,
        READABILITY_WARNING_SCHEMA_BACKED_WIDGET_ALIAS_NOT_RESOLVED,
        READABILITY_WARNING_HIDDEN_MODEL_FILENAME,
        READABILITY_WARNING_LOCAL_HELPER_COPY_IN_STRICT_TEMPLATE,
        READABILITY_WARNING_LONG_ONE_LINE_NODE_CALL,
        READABILITY_WARNING_GENERATED_TEMPLATE_NOT_FORMATTED,
        READABILITY_WARNING_GENERATED_VARIABLE_NAME_TOO_LONG,
        READABILITY_WARNING_SUBGRAPH_INPUT_UNBOUND,
        READABILITY_WARNING_SCHEMA_UNKNOWN_KWARG_HIDDEN_BY_EXTRAS,
        READABILITY_WARNING_LOCKED_VARIABLE_ALIAS_INVALID,
        READABILITY_WARNING_LOCKED_VARIABLE_ALIAS_COLLISION,
        READABILITY_WARNING_LOCKED_VARIABLE_ALIAS_MISSING,
        READABILITY_WARNING_LOCKED_VARIABLE_UID_COLLISION,
    }
)

from vibecomfy.porting._provenance_utils import _normalize_provenance_paths

EmissionSeverity = Literal["error", "warning", "info"]
logger = logging.getLogger(__name__)


@dataclass(slots=True)
class EmissionDiagnostic:
    """A readability diagnostic recorded during emission.

    These are always *warnings* (or info) - hard errors are surfaced through
    `PortConvertValidation` parity / schema failures, not here.
    """

    code: str
    message: str
    severity: EmissionSeverity = "warning"
    node_id: str | None = None
    class_type: str | None = None
    detail: dict[str, Any] = field(default_factory=dict)

    def to_json(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class _PublicInputBinding:
    name: str
    node_id: str
    field: str
    type: str | None = None
    required: bool = False
    aliases: tuple[str, ...] = ()
    media_semantics: str | None = None


@dataclass(frozen=True, slots=True)
class _PublicInputSpec:
    name: str
    node_ref: str
    metadata_node_ref: str
    field: str
    default_expr: str
    type: str | None = None
    required: bool = False
    aliases: tuple[str, ...] = ()
    media_semantics: str | None = None




GENERATED_HEADER = (
    "# vibecomfy: generated\n"
    "# For hand-editing, run: python -m vibecomfy.cli copy-to-recipe <id>\n"
)












# _MODEL_FAMILY_CONSTANTS and _MODEL_CONSTANT_BASE_PRIORITY moved to emit_constants.py








def _public_input_specs(
    workflow_nodes: dict[str, Any],
    edges_in: dict[str, list[Any]],
    var_names: dict[str, str],
    output_var_names: dict[str, dict[int, str]],
    *,
    registered_inputs: dict[str, tuple[str, str]] | None,
    constant_map: dict[tuple[str, str], str],
) -> list[_PublicInputSpec]:
    specs: list[_PublicInputSpec] = []
    used_names: set[str] = set()

    def add(binding: _PublicInputBinding) -> None:
        if binding.name in used_names:
            return
        node = workflow_nodes.get(str(binding.node_id))
        if node is None:
            return
        field_values = _resolved_field_values(node)
        if binding.field not in field_values:
            return
        default_value = _resolve_graph_field_get_string(
            field_values[binding.field],
            workflow_nodes,
        )
        default_expr = constant_map.get((str(binding.node_id), binding.field))
        if default_expr is None:
            default_expr = _format_value(default_value)
        # Blank placeholder filenames for LoadImage-family public inputs
        # (e.g. 'image (6).png' — the upstream workflow author's local file).
        if (
            binding.required
            and binding.field == "image"
            and str(node.class_type) in _LOAD_IMAGE_FAMILY
            and isinstance(default_value, str)
            and _looks_like_placeholder_filename(default_value)
        ):
            default_expr = "''"
        node_var = _first_output_var(output_var_names.get(str(binding.node_id))) or var_names.get(str(binding.node_id))
        node_ref = node_var if node_var is not None else repr(str(binding.node_id))
        metadata_node_ref = repr(str(binding.node_id))
        specs.append(
            _PublicInputSpec(
                name=binding.name,
                node_ref=node_ref,
                metadata_node_ref=metadata_node_ref,
                field=binding.field,
                default_expr=default_expr,
                type=binding.type,
                required=binding.required,
                aliases=binding.aliases,
                media_semantics=binding.media_semantics,
            )
        )
        used_names.add(binding.name)
        used_names.update(binding.aliases)

    for input_name, (old_id, field) in dict(registered_inputs or {}).items():
        resolved_field = field
        if field.startswith("widget_") and old_id in workflow_nodes:
            cls = workflow_nodes[old_id].class_type
            node = workflow_nodes[old_id]
            aliases = getattr(node, "metadata", {}).get("input_aliases") or _ui_widget_aliases(node)
            resolved = resolve_widget_key_with_provenance(cls, field, input_aliases=aliases)
            if resolved.name is not None:
                resolved_field = resolved.name
        add(_PublicInputBinding(name=input_name, node_id=str(old_id), field=resolved_field))

    inferred = _infer_public_input_bindings(workflow_nodes, edges_in, reserved_names=used_names)
    for binding in inferred:
        add(binding)
    return specs


def _format_public_inputs_block(specs: list[_PublicInputSpec], *, metadata: bool = False) -> list[str]:
    if not specs:
        return []
    lines = ["PUBLIC_INPUT_METADATA = {" if metadata else "    return {"]
    # Dedup by (node_ref, field): aliases for the same underlying binding collapse
    # to one entry under the canonical name with the others recorded as
    # aliases=(...).  Without this, both 'negative' and 'negative_prompt' end up as
    # separate dict keys for the same node/field, which silently duplicates state.
    seen: dict[tuple[str, str], str] = {}
    for spec in specs:
        node_ref = spec.metadata_node_ref if metadata else spec.node_ref
        key = (node_ref, spec.field)
        if key in seen:
            continue
        seen[key] = spec.name
        # Fold any other specs that share (node_ref, field) into the aliases tuple.
        extra_aliases: list[str] = []
        for other in specs:
            other_node = other.metadata_node_ref if metadata else other.node_ref
            if (other_node, other.field) != key:
                continue
            if other.name != spec.name and other.name not in extra_aliases:
                extra_aliases.append(other.name)
        aliases = tuple(spec.aliases or ())
        for alias in extra_aliases:
            if alias not in aliases:
                aliases = aliases + (alias,)
        args = [
            f"node={node_ref}",
            f"field={spec.field!r}",
            f"default={spec.default_expr}",
        ]
        if spec.type is not None:
            args.append(f"type={spec.type!r}")
        if spec.required:
            args.append("required=True")
        if aliases:
            args.append(f"aliases={aliases!r}")
        if spec.media_semantics is not None:
            args.append(f"media_semantics={spec.media_semantics!r}")
        lines.append(f"    {spec.name!r}: InputSpec({', '.join(args)}),")
    lines.append("}" if metadata else "    }")
    return lines


def _remap_public_inputs_for_materialized_subgraphs(
    specs: list[_PublicInputSpec],
    workflow_nodes: dict[str, Any],
    subgraphs: dict[str, _SubgraphDef],
) -> list[_PublicInputSpec]:
    if not specs or not subgraphs:
        return specs
    remapped: list[_PublicInputSpec] = []
    for spec in specs:
        try:
            node_id = ast.literal_eval(spec.metadata_node_ref)
        except Exception:
            remapped.append(spec)
            continue
        node = workflow_nodes.get(str(node_id))
        subgraph = subgraphs.get(str(getattr(node, "class_type", ""))) if node is not None else None
        if subgraph is None:
            remapped.append(spec)
            continue
        port_index = _subgraph_port_index_for_instance_field(node, subgraph, spec.field)
        if port_index is None:
            remapped.append(spec)
            continue
        port = subgraph.inputs[port_index]
        consumer = next(
            (
                (internal_node_id, internal_field)
                for (internal_node_id, internal_field), port_name in subgraph.input_refs.items()
                if port_name == port.name
            ),
            None,
        )
        if consumer is None:
            remapped.append(spec)
            continue
        internal_node_id, internal_field = consumer
        remapped.append(
            replace(
                spec,
                metadata_node_ref=repr(_subgraph_emitted_node_id(subgraph.id, internal_node_id)),
                field=internal_field,
            )
        )
    return remapped


def _subgraph_port_index_for_instance_field(node: Any, subgraph: _SubgraphDef, field: str) -> int | None:
    candidates = _subgraph_instance_port_candidate_names(node, subgraph)
    for index, names in candidates.items():
        if field in names:
            return index
    return None






def _lock_entries_by_class(lockfile_path: Path = Path("custom_nodes.lock")) -> dict[str, LockEntry]:
    by_class: dict[str, LockEntry] = {}
    try:
        entries = read_lockfile(lockfile_path)
    except (OSError, ValueError):
        return {}
    for entry in entries:
        for class_type in entry.class_set:
            by_class.setdefault(str(class_type), entry)
    return by_class


def _custom_node_packs_for_emit(
    workflow_nodes: Mapping[str, Any],
    metadata: Mapping[str, Any],
    requirements: Mapping[str, Any],
) -> dict[str, dict[str, Any]]:
    explicit = metadata.get("custom_node_packs")
    if isinstance(explicit, Mapping):
        return {str(key): dict(value) for key, value in explicit.items() if isinstance(value, Mapping)}

    by_class = _lock_entries_by_class()
    if not by_class:
        return {}

    requirement_names = {
        str(item)
        for key in ("custom_nodes", "custom_node_refs")
        for item in (requirements.get(key) or [])
        if item
    }
    grouped: dict[str, dict[str, Any]] = {}
    for node in workflow_nodes.values():
        class_type = str(getattr(node, "class_type", ""))
        entry = by_class.get(class_type)
        if entry is None:
            continue
        commit = entry.commit or entry.git_commit_sha
        if not commit:
            continue
        row = grouped.setdefault(
            entry.name,
            {
                "commit": commit,
                "url": entry.url,
                "class_schema_sha256": entry.class_schema_sha256 or entry.schema_hash,
                "classes_used": [],
                "pip_packages": list(entry.pip_packages),
                "status": "pinned" if entry.name in requirement_names or entry.slug in requirement_names else "discovered",
            },
        )
        if class_type not in row["classes_used"]:
            row["classes_used"].append(class_type)

    for row in grouped.values():
        row["classes_used"] = sorted(row["classes_used"])
        row["pip_packages"] = sorted(row["pip_packages"])
        for key in ("url", "class_schema_sha256"):
            if row.get(key) is None:
                row.pop(key, None)
    return dict(sorted(grouped.items(), key=lambda item: item[0].lower()))


def _format_ready_metadata_build(
    metadata: Mapping[str, Any],
    requirements: Mapping[str, Any],
    *,
    has_models: bool,
    has_public_inputs: bool,
    custom_node_packs: Mapping[str, Any] | None = None,
    output_node_class_type: str | None = None,
) -> list[str]:
    template_id = str(metadata.get("ready_template") or metadata.get("workflow_template") or "ready_template")
    raw_capability = str(metadata.get("capability") or "unknown")
    if raw_capability == "unknown" and output_node_class_type:
        from vibecomfy.templates import _derive_output_kind  # local import to avoid circular import at module load
        derived = _derive_output_kind(output_node_class_type)
        if derived:
            raw_capability = derived
    capability = raw_capability
    output_prefix = str(metadata.get("output_prefix") or template_id)
    lines = [
        "READY_METADATA = ReadyMetadata.build(",
        f"    capability={capability!r},",
    ]
    if has_public_inputs:
        lines.append("    inputs=PUBLIC_INPUT_METADATA,")
    if has_models:
        lines.append("    models=MODELS,")
    if output_prefix != template_id:
        lines.append(f"    output_prefix={output_prefix!r},")
    requirements_expr = _requirements_expr_for_emit(requirements, has_models=has_models)
    if requirements_expr is not None:
        lines.append(f"    requirements={requirements_expr},")
    if custom_node_packs:
        lines.append(f"    custom_node_packs={_format_value(dict(custom_node_packs))},")
    for key, value in _metadata_extras_for_emit(metadata).items():
        lines.append(f"    {key}={_format_value(value)},")
    lines.append(")")
    return lines


def _strip_unused_template_imports(source: str) -> str:
    tree = ast.parse(source)
    used = {node.id for node in ast.walk(tree) if isinstance(node, ast.Name)}
    target = "from vibecomfy.templates import "
    lines = source.splitlines()
    rewritten: list[str] = []
    for line in lines:
        if not line.startswith(target):
            rewritten.append(line)
            continue
        names = [name.strip() for name in line[len(target) :].split(",")]
        kept = [name for name in names if _import_binding_name(name) in used]
        if kept:
            rewritten.append(target + ", ".join(kept))
    return "\n".join(rewritten) + ("\n" if source.endswith("\n") else "")


def _import_binding_name(import_name: str) -> str:
    if " as " in import_name:
        return import_name.rsplit(" as ", 1)[1].strip()
    return import_name


def emit_ready_template_python(
    workflow,
    *,
    ready_metadata: dict[str, Any],
    ready_requirements: dict[str, Any],
    template_id: str,
    registered_inputs: dict[str, tuple[str, str]] | None = None,
    apply_overrides: dict[str, Any] | None = None,
    diagnostics: list[EmissionDiagnostic] | None = None,
    raw_workflow: dict[str, Any] | None = None,
    variable_name_locks: Mapping[str, str] | None = None,
    strict_variable_name_locks: bool = False,
    object_info_identities: dict[str, Any] | None = None,
) -> str:
    with _use_object_info_identities(object_info_identities):
        result_text = _emit_ready_template_python_inner(
            workflow,
            ready_metadata=ready_metadata,
            ready_requirements=ready_requirements,
            template_id=template_id,
            registered_inputs=registered_inputs,
            apply_overrides=apply_overrides,
            diagnostics=diagnostics,
            raw_workflow=raw_workflow,
            variable_name_locks=variable_name_locks,
            strict_variable_name_locks=strict_variable_name_locks,
        )
        _drain_lookup_warning_diagnostics(diagnostics)
    return result_text


def format_as_python(
    workflow,
    *,
    ready_metadata: dict[str, Any],
    ready_requirements: dict[str, Any],
    template_id: str,
    registered_inputs: dict[str, tuple[str, str]] | None = None,
    apply_overrides: dict[str, Any] | None = None,
    raw_workflow: dict[str, Any] | None = None,
) -> str:
    """Compatibility wrapper for the package ready-template emitter.

    This is the canonical ``format_as_python`` entry point re-exported from
    ``vibecomfy.porting.emitter`` so that legacy callers (``loader.py``,
    etc.) that previously imported from ``tools.format_as_python`` continue
    to work through the emitter facade.
    """
    return emit_ready_template_python(
        workflow,
        ready_metadata=ready_metadata,
        ready_requirements=ready_requirements,
        template_id=template_id,
        registered_inputs=registered_inputs,
        apply_overrides=apply_overrides,
        raw_workflow=raw_workflow,
    )


def _emit_ready_template_python_inner(
    workflow,
    *,
    ready_metadata: dict[str, Any],
    ready_requirements: dict[str, Any],
    template_id: str,
    registered_inputs: dict[str, tuple[str, str]] | None = None,
    apply_overrides: dict[str, Any] | None = None,
    diagnostics: list[EmissionDiagnostic] | None = None,
    raw_workflow: dict[str, Any] | None = None,
    variable_name_locks: Mapping[str, str] | None = None,
    strict_variable_name_locks: bool = False,
) -> str:
    metadata = dict(ready_metadata)
    requirements = dict(ready_requirements)
    if apply_overrides:
        for key, value in (apply_overrides.get("metadata_overrides") or {}).items():
            metadata[key] = value
    _apply_ready_template_metadata_defaults(metadata, template_id)

    # Ensure sageattention is declared when SageAttention nodes are present.
    _sage_class_types = frozenset({
        "LTX2MemoryEfficientSageAttentionPatch",
        "PathchSageAttentionKJ",
    })
    if any(
        node.class_type in _sage_class_types
        for node in workflow.nodes.values()
    ):
        existing = metadata.get("runtime_packages")
        if not (
            isinstance(existing, list)
            and any(
                isinstance(pkg, dict) and pkg.get("name") == "sageattention"
                for pkg in existing
            )
        ):
            entry = {
                "name": "sageattention",
                "reason": (
                    "Required by LTX2MemoryEfficientSageAttentionPatch / "
                    "PathchSageAttentionKJ for memory-efficient attention on "
                    "compatible GPUs."
                ),
                "source": "SageAttention-ada",
            }
            if isinstance(existing, list):
                metadata["runtime_packages"] = [*existing, entry]
            else:
                metadata["runtime_packages"] = [entry]

    raw_workflow = raw_workflow or _raw_workflow_from_metadata(metadata)
    subgraph_definitions = _subgraph_definitions_from_raw(raw_workflow, source_path=_source_workflow_path(metadata))
    prepared = _prepare_workflow_for_emit(
        workflow,
        apply_overrides=apply_overrides,
        template_id=template_id,
        variable_name_locks=variable_name_locks,
        strict_variable_name_locks=strict_variable_name_locks,
        diagnostics=diagnostics,
    )
    prepared["subgraph_definitions"] = subgraph_definitions
    _apply_subgraph_names_to_prepared(prepared)
    has_ltx_tail = _has_ltx_lowvram_tail(template_id)

    workflow_nodes = prepared["nodes"]
    edges_in = prepared["edges_in"]
    ordering_edges_in = _edges_in_with_subgraph_external_refs(prepared, workflow_nodes, edges_in)
    var_names = prepared["var_names"]

    # Hoist constants and build section groups
    constant_lines, constant_map = _hoist_constants(workflow_nodes, edges_in, var_names)
    constant_lines, constant_map = _drop_output_prefix_constants(constant_lines, constant_map)
    section_groups = _build_section_groups(workflow_nodes, edges_in)
    wrapper_imports = _wrapper_imports_for_nodes(_all_nodes_for_imports(workflow_nodes, subgraph_definitions))
    output_var_names = prepared["output_var_names"]
    public_inputs = _public_input_specs(
        workflow_nodes,
        edges_in,
        var_names,
        output_var_names,
        registered_inputs=registered_inputs,
        constant_map=constant_map,
    )
    model_assets = _model_assets_for_emit(metadata, requirements)
    custom_node_packs = _custom_node_packs_for_emit(workflow_nodes, metadata, requirements)
    has_public_inputs = bool(public_inputs)
    metadata["_has_public_inputs_for_emit"] = has_public_inputs

    out_lines: list[str] = []
    out_lines.append(GENERATED_HEADER.rstrip("\n"))
    out_lines.append('"""Auto-generated ready_template — use python -m vibecomfy.cli copy-to-recipe <id> for hand-editing."""')
    out_lines.append("from __future__ import annotations")
    out_lines.append("")
    out_lines.append(
        "from vibecomfy.templates import InputSpec, ModelAsset, ReadyMetadata, finalize, new_workflow, node as raw_call, ref"
    )
    for module_name, names in sorted(wrapper_imports.items()):
        out_lines.append(f"from vibecomfy.nodes.{module_name} import {', '.join(names)}")
    if has_ltx_tail:
        out_lines.extend(LTX2_3_TAIL_PATCHES)
    out_lines.append("")
    # -- constants section ----------------------------------------------------
    if constant_lines:
        out_lines.append("")
        out_lines.extend(constant_lines)
        out_lines.append("")
    model_lines = _format_models_block(model_assets)
    if model_lines:
        out_lines.append("")
        out_lines.extend(model_lines)
        out_lines.append("")
    public_inputs_for_metadata = _remap_public_inputs_for_materialized_subgraphs(
        public_inputs,
        workflow_nodes,
        subgraph_definitions,
    )
    # Compute which subgraph node IDs are referenced by PUBLIC_INPUT_METADATA.
    # Only those nodes need explicit _id= kwargs in emitted subgraph functions.
    required_ids_by_subgraph: dict[str, set[str]] = {}
    for spec in public_inputs_for_metadata:
        try:
            ref_str = ast.literal_eval(spec.metadata_node_ref)
        except Exception:
            continue
        if ":" not in ref_str:
            continue
        prefix, inner_id = ref_str.split(":", 1)
        for subgraph_id in subgraph_definitions:
            if _short_subgraph_id_prefix(subgraph_id) == prefix:
                required_ids_by_subgraph.setdefault(subgraph_id, set()).add(inner_id)
                break
    public_input_metadata_lines = _format_public_inputs_block(public_inputs_for_metadata, metadata=True)
    if public_input_metadata_lines:
        out_lines.append("")
        out_lines.extend(public_input_metadata_lines)
        out_lines.append("")
    output_node_ids = _terminal_output_node_ids(workflow_nodes, edges_in)
    output_node_cls: str | None = (
        str(workflow_nodes[output_node_ids[0]].class_type) if output_node_ids and output_node_ids[0] in workflow_nodes else None
    )
    out_lines.extend(
        _format_ready_metadata_build(
            metadata,
            requirements,
            has_models=bool(model_assets),
            has_public_inputs=has_public_inputs,
            custom_node_packs=custom_node_packs,
            output_node_class_type=output_node_cls,
        )
    )
    out_lines.append("")
    subgraph_lines = _emit_subgraph_functions(
        prepared,
        diagnostics=diagnostics,
        constant_map=constant_map,
        required_ids_by_subgraph=required_ids_by_subgraph,
        variable_name_locks=variable_name_locks,
        strict_variable_name_locks=strict_variable_name_locks,
    )
    if subgraph_lines:
        out_lines.extend(subgraph_lines)
        out_lines.append("")
    out_lines.extend(
        _emit_build_function(
            prepared,
            workflow_id_expr="READY_METADATA",
            source_path_expr="__file__",
            source_type="ready_template",
            source_provenance=None,
            registered_inputs=registered_inputs,
            public_inputs=public_inputs,
            tail_lines=_ready_template_tail_lines(
                has_ltx_tail,
                workflow_nodes,
                edges_in,
                var_names,
                output_var_names,
                metadata,
            ),
            diagnostics=diagnostics,
            use_shared_helpers=True,
            constant_map=constant_map,
            section_groups=section_groups,
        )
    )
    out_lines.append("")

    combined = "\n".join(out_lines) + "\n"
    combined = _strip_unused_template_imports(combined)

    # -- readability diagnostic: generated_template_not_formatted -------------
    if diagnostics is not None:
        _check_template_formatting(combined, workflow_nodes, section_groups, diagnostics)

    # Validate syntax with ast.parse
    try:
        ast.parse(combined)
    except SyntaxError as exc:
        raise RuntimeError(f"Generated ready-template code failed syntax check: {exc}") from exc
    return combined


# emit_scratchpad_python and _emit_scratchpad_python_inner have been moved to
# emit_scratchpad.py (M2 structural decomposition, T9).
# They are re-exported above via the emit_scratchpad import block.
#
# emit_agent_edit_python has been moved to emit_agent_edit.py
# (M2 structural decomposition, T10).
# It is re-exported above via the emit_agent_edit import block.
#
# _VIRTUAL_WIRE_EMITTER_CLASS_TYPES, _prepare_workflow_for_emit,
# _emit_agent_edit_lines and their private helpers have been moved to
# emit_prepare.py (M2 structural decomposition, T7).
# They are re-exported above via the emit_prepare import block.


def _prune_dead_branches_for_emit(
    workflow_nodes: dict[str, Any],
    edges_in: dict[str, list[Any]],
    *,
    template_id: str | None,
) -> tuple[dict[str, Any], dict[str, list[Any]]]:
    output_node_ids = _terminal_output_node_ids(workflow_nodes, edges_in)
    if not output_node_ids:
        return workflow_nodes, edges_in

    live: set[str] = set(output_node_ids)
    pending = list(output_node_ids)
    while pending:
        node_id = pending.pop()
        node = workflow_nodes.get(node_id)
        if node is None:
            continue
        for edge in edges_in.get(node_id, []):
            if _is_dead_optional_output_input(node, str(getattr(edge, "to_input", "")), template_id):
                continue
            from_node = str(getattr(edge, "from_node", ""))
            if from_node in workflow_nodes and from_node not in live:
                live.add(from_node)
                pending.append(from_node)
        for key, value in {**getattr(node, "inputs", {}), **getattr(node, "widgets", {})}.items():
            if _is_dead_optional_output_input(node, str(key), template_id):
                continue
            if not _is_link(value):
                continue
            from_node = str(value[0])
            if from_node in workflow_nodes and from_node not in live:
                live.add(from_node)
                pending.append(from_node)

    pruned_nodes = {nid: node for nid, node in workflow_nodes.items() if nid in live}
    pruned_edges_in: dict[str, list[Any]] = {}
    for to_node, edges in edges_in.items():
        if str(to_node) not in pruned_nodes:
            continue
        kept = [
            edge
            for edge in edges
            if str(getattr(edge, "from_node", "")) in pruned_nodes
            and not _is_dead_optional_output_input(
                pruned_nodes[str(to_node)],
                str(getattr(edge, "to_input", "")),
                template_id,
            )
        ]
        if kept:
            pruned_edges_in[str(to_node)] = kept
    return pruned_nodes, pruned_edges_in


def _is_dead_optional_output_input(node: Any, input_name: str, template_id: str | None) -> bool:
    class_type = str(getattr(node, "class_type", ""))
    if not _ltx_travel_template_omits_synthetic_audio(template_id):
        return False
    return (
        (class_type == "VHS_VideoCombine" and input_name == "audio")
        or (class_type == "LTXVConcatAVLatent" and input_name == "audio_latent")
    )


def _ltx_travel_template_omits_synthetic_audio(template_id: str | None) -> bool:
    lowered = str(template_id or "").lower()
    if not lowered.startswith("video/ltx2_3"):
        return False
    if any(token in lowered for token in ("audio", "lipsync", "talk")):
        return False
    return "first_last" in lowered or "first_middle_last" in lowered or "travel" in lowered


def _source_workflow_path(metadata: Mapping[str, Any]) -> str | None:
    provenance = metadata.get("provenance")
    if isinstance(provenance, Mapping):
        source = provenance.get("source_workflow") or provenance.get("source_path")
        if isinstance(source, str) and source:
            return source
    source = metadata.get("source_workflow")
    return source if isinstance(source, str) and source else None


def _raw_workflow_from_metadata(metadata: Mapping[str, Any]) -> dict[str, Any] | None:
    source = _source_workflow_path(metadata)
    if not source:
        return None
    path = Path(source)
    if not path.is_absolute():
        path = Path.cwd() / path
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _all_nodes_for_imports(workflow_nodes: dict[str, Any], subgraphs: dict[str, _SubgraphDef]) -> dict[str, Any]:
    nodes = dict(workflow_nodes)
    for subgraph in subgraphs.values():
        for nid, node in subgraph.nodes.items():
            nodes.setdefault(_subgraph_emitted_node_id(subgraph.id, nid), node)
    return nodes




def _infer_public_input_bindings(
    workflow_nodes: dict[str, Any],
    edges_in: dict[str, list[Any]],
    *,
    reserved_names: set[str] | None = None,
) -> list[_PublicInputBinding]:
    bindings: list[_PublicInputBinding] = []
    used_names: set[str] = set(reserved_names or set())

    def add(
        name: str,
        node_id: str,
        field: str,
        *,
        type: str | None = None,
        required: bool = False,
        aliases: tuple[str, ...] = (),
        media_semantics: str | None = None,
    ) -> None:
        candidate_names = {name, *aliases}
        if candidate_names & used_names:
            return
        node = workflow_nodes.get(node_id)
        if node is None:
            return
        fields = _resolved_field_values(node)
        available = set(fields)
        incoming = {str(getattr(edge, "to_input", "")) for edge in edges_in.get(node_id, [])}
        if field not in available or field in incoming:
            return
        used_names.update(candidate_names)
        bindings.append(
            _PublicInputBinding(
                name=name,
                node_id=node_id,
                field=field,
                type=type,
                required=required,
                aliases=aliases,
                media_semantics=media_semantics,
            )
        )

    prompt_candidate: tuple[str, str] | None = None
    negative_candidate: tuple[str, str] | None = None
    for node_id, node in sorted(workflow_nodes.items(), key=lambda item: _id_sort_key(item[0])):
        fields = _resolved_field_values(node)
        class_type = str(getattr(node, "class_type", ""))
        title = _node_title(node).lower()

        if class_type in {"CLIPTextEncode", "CLIPTextEncodeFlux", "CLIPTextEncodeSD3", "CLIPTextEncodeSDXL", "TextEncodeQwenImageEdit"}:
            value = _resolve_graph_field_get_string(fields.get("text"), workflow_nodes)
            if isinstance(value, str):
                if "negative" in title:
                    negative_candidate = negative_candidate or (str(node_id), "text")
                elif value.strip():
                    prompt_candidate = prompt_candidate or (str(node_id), "text")
        primitive_value = _resolve_graph_field_get_string(fields.get("value"), workflow_nodes)
        if class_type in {"PrimitiveStringMultiline", "PrimitiveString"} and isinstance(
            primitive_value,
            str,
        ) and primitive_value.strip():
            prompt_candidate = prompt_candidate or (str(node_id), "value")
        if class_type == "LoadImage" and "image" in fields:
            add("image", str(node_id), "image", type="IMAGE", required=True, aliases=("input_image",), media_semantics="image")
        if "seed" in fields and isinstance(fields["seed"], int) and not isinstance(fields["seed"], bool):
            add("seed", str(node_id), "seed", type="INT")
        if "noise_seed" in fields and isinstance(fields["noise_seed"], int) and not isinstance(fields["noise_seed"], bool):
            add("seed", str(node_id), "noise_seed", type="INT")
        if "width" in fields and isinstance(fields["width"], int):
            add("width", str(node_id), "width", type="INT")
        if "height" in fields and isinstance(fields["height"], int):
            add("height", str(node_id), "height", type="INT")
        if "length" in fields and isinstance(fields["length"], int):
            add("frames", str(node_id), "length", type="INT")
        if "frames" in fields and isinstance(fields["frames"], int):
            add("frames", str(node_id), "frames", type="INT")
        if "fps" in fields and isinstance(fields["fps"], (int, float)):
            add("fps", str(node_id), "fps", type="FLOAT")

    if prompt_candidate is not None:
        add("prompt", prompt_candidate[0], prompt_candidate[1], type="STRING", required=True, media_semantics="text")
    if negative_candidate is not None:
        add("negative_prompt", negative_candidate[0], negative_candidate[1], type="STRING", aliases=("negative",), media_semantics="text")
    return bindings


def _node_title(node: Any) -> str:
    ui = getattr(node, "metadata", {}).get("_ui")
    if isinstance(ui, dict):
        title = ui.get("title")
        if isinstance(title, str):
            return title
    return ""


def _resolved_field_values(node: Any) -> dict[str, Any]:
    class_type = str(getattr(node, "class_type", ""))
    aliases = getattr(node, "metadata", {}).get("input_aliases") or _ui_widget_aliases(node)
    values: dict[str, Any] = {}
    for key, value in {**getattr(node, "inputs", {}), **getattr(node, "widgets", {})}.items():
        translated = _translate_widget_for_key(str(key), aliases, class_type)
        if translated is not None:
            values[translated] = value
    return values



def _emit_build_function(
    prepared: dict[str, Any],
    *,
    workflow_id_expr: str,
    source_path_expr: str,
    source_type: str,
    source_provenance: dict[str, Any] | None,
    registered_inputs: dict[str, tuple[str, str]] | None,
    public_inputs: list[_PublicInputSpec] | None,
    tail_lines: list[str],
    diagnostics: list[EmissionDiagnostic] | None = None,
    use_shared_helpers: bool = False,
    constant_map: dict[tuple[str, str], str] | None = None,
    section_groups: dict[str, list[str]] | None = None,
    function_name: str = "build",
    function_signature: str | None = None,
    function_docstring: list[str] | None = None,
    return_refs: tuple[tuple[str, int], ...] = (),
    external_refs: dict[tuple[str, str], str] | None = None,
    node_id_prefix: str | None = None,
    required_ids: set[str] | None = None,
) -> list[str]:
    workflow_nodes = prepared["nodes"]
    edges_in = prepared["edges_in"]
    ordering_edges_in = _edges_in_with_subgraph_external_refs(prepared, workflow_nodes, edges_in)
    var_names = prepared["var_names"]
    output_var_names = prepared.get("output_var_names", {}) if use_shared_helpers else {}

    if constant_map is None:
        constant_map = {}
    if section_groups is None:
        section_groups = {}
    var_to_nid = {var: nid for nid, var in var_names.items()}
    for output_nid, slot_vars in output_var_names.items():
        for output_var in slot_vars.values():
            var_to_nid[str(output_var)] = str(output_nid)
    live_output_slots = _live_output_slots_for_function(
        workflow_nodes,
        ordering_edges_in,
        output_var_names,
        return_refs=return_refs,
        tail_lines=tail_lines,
    )
    public_preserve_fields: dict[str, set[str]] = {}
    for spec in public_inputs or []:
        node_ref = spec.node_ref
        if node_ref.startswith("ref("):
            try:
                ref_name = ast.literal_eval(node_ref[4:-1])
            except Exception:
                continue
        else:
            ref_name = node_ref
        nid = var_to_nid.get(str(ref_name))
        if nid is not None:
            public_preserve_fields.setdefault(nid, set()).add(spec.field)

    # Build a set of node IDs covered by section groups for fast lookup
    section_nids: set[str] = set()
    for nids in section_groups.values():
        section_nids.update(nids)

    # Build ordered list of (section_name, nid) for topological-sorted nodes
    topo_order = _topological_node_order(workflow_nodes, ordering_edges_in)
    section_order_map: dict[str, str] = {}  # nid -> section_name
    for section_name in _SECTION_ORDER:
        for nid in section_groups.get(section_name, []):
            section_order_map[nid] = section_name

    is_subgraph_function = function_name != "build"
    out_lines: list[str] = []
    if function_signature is not None:
        out_lines.extend(function_signature.splitlines())
    else:
        out_lines.append("def build() -> VibeWorkflow:")
    if function_docstring is None:
        out_lines.append('    """Build the workflow (auto-generated)."""')
    elif function_docstring:
        out_lines.extend(function_docstring)
    provenance_part = ""
    if source_provenance is not None:
        provenance_part = f",\n            provenance={_format_value(source_provenance)}"

    if is_subgraph_function:
        body_indent = "    "
        continuation_indent = "        "
    elif use_shared_helpers:
        # new_workflow() eagerly binds the ContextVar, so emit a plain assignment
        # rather than wrapping the body in `with new_workflow(...) as wf:`.
        # finalize() releases the binding.
        if source_type != "ready_template":
            out_lines.append(
                f"    wf = new_workflow({workflow_id_expr}, source_path={source_path_expr}, source_type={source_type!r})"
            )
        else:
            out_lines.append(
                f"    wf = new_workflow({workflow_id_expr}, source_path={source_path_expr})"
            )
        body_indent = "    "
        continuation_indent = "        "
    else:
        out_lines.append(
            "    wf = VibeWorkflow(\n"
            f"        {workflow_id_expr},\n"
            "        WorkflowSource(\n"
            f"            id={workflow_id_expr},\n"
            f"            path={source_path_expr},\n"
            f"            source_type={source_type!r}"
            f"{provenance_part},\n"
            "        ),\n"
            "    )"
        )
        body_indent = "    "
        continuation_indent = "        "
    out_lines.append("")

    emitted_sections: set[str] = set()
    for nid in topo_order:
        node = workflow_nodes[nid]
        var = var_names[nid]

        # -- readability diagnostic: variable name too long -------------------
        if diagnostics is not None and len(var) > 40:
            diagnostics.append(
                EmissionDiagnostic(
                    code=READABILITY_WARNING_GENERATED_VARIABLE_NAME_TOO_LONG,
                    message=(
                        f"Variable name {var!r} ({len(var)} chars) exceeds 40-character threshold; "
                        f"consider a shorter semantic name."
                    ),
                    severity="warning",
                    node_id=str(nid),
                    class_type=node.class_type,
                    detail={"variable_name": var, "length": len(var)},
                )
            )

        # Emit section comment if entering a new section group
        section = section_order_map.get(nid)
        if section is not None and section not in emitted_sections:
            if out_lines and out_lines[-1] != "":
                out_lines.append("")
            out_lines.append(f"{body_indent}# {section}")
            emitted_sections.add(section)

        wrapper_module = _wrapper_module_for_class(str(node.class_type)) if use_shared_helpers else None
        preserve_fields = {
            field
            for old_id, field in (registered_inputs or {}).values()
            if old_id == nid
        }
        preserve_fields.update(public_preserve_fields.get(nid, set()))
        kwargs = _node_kwargs(
            node, edges_in, var_names,
            workflow_nodes=workflow_nodes,
            output_var_names=output_var_names,
            diagnostics=diagnostics,
            constant_map=constant_map,
            use_ui_widget_aliases=use_shared_helpers,
            strip_schema_defaults=use_shared_helpers,
            omit_single_output_metadata=use_shared_helpers,
            bare_single_output_refs=use_shared_helpers,
            emit_reserved_keyword_args=wrapper_module is not None,
            preserve_fields=preserve_fields,
            external_refs=external_refs,
        )

        if use_shared_helpers:
            subgraph = (prepared.get("subgraph_definitions") or {}).get(str(node.class_type))
            if subgraph is not None:
                stmt_lines = _emit_subgraph_call_statement(
                    node,
                    subgraph,
                    edges_in,
                    var_names,
                    output_var_names,
                    workflow_nodes,
                    body_indent=body_indent,
                    continuation_indent=continuation_indent,
                    diagnostics=diagnostics,
                )
                # Subgraph calls share the node-call blank-line rhythm: multi-line
                # statements are surrounded by blank lines, single-line ones pack.
                is_multiline = len(stmt_lines) > 1
                if is_multiline:
                    prev = out_lines[-1] if out_lines else ""
                    if out_lines and prev != "" and not prev.lstrip().startswith("# "):
                        out_lines.append("")
                out_lines.extend(stmt_lines)
                if is_multiline:
                    out_lines.append("")
                continue

            use_wrapper = wrapper_module is not None
            ready_kwargs: list[tuple[str, str]] = []
            outputs_expr: str | None = None
            extras_expr: str | None = None
            for key, expr in kwargs:
                if key == "_outputs":
                    outputs_expr = expr
                elif key == "_extras":
                    extras_expr = expr
                else:
                    ready_kwargs.append((key, expr))

            # Durable node identity (M2, T13): carry _uid= through the
            # ready-template emission paths (typed wrapper + raw_call), mirroring
            # the scratchpad _node() mechanism. node()/raw_call apply it verbatim.
            uid_arg = ("_uid", repr(node.uid)) if node.uid else None

            if use_wrapper:
                all_args = []
                if is_subgraph_function and node_id_prefix is not None:
                    if _subgraph_node_id_required(node_id_prefix, nid, required_ids):
                        all_args.append(("_id", repr(_subgraph_emitted_node_id(node_id_prefix, nid))))
                elif not is_subgraph_function:
                    all_args.append(("_id", repr(str(nid))))
                all_args.extend((_wrapper_kwarg_name(key), expr) for key, expr in ready_kwargs)
                if uid_arg is not None:
                    all_args.append(uid_arg)
                # v2.6.4 Fix 3: drop _outputs= for schema-known typed wrappers.
                # The wrapper class already knows its output names from the
                # generated schema (vibecomfy/nodes/_generated/<pack>.py). Only
                # raw_call (UUID fallback, no schema) needs explicit _outputs.
                if extras_expr is not None:
                    all_args.append(("**", extras_expr))
                call_name = _wrapper_symbol_for_class(str(node.class_type)) or str(node.class_type)
                assignment_target = _assignment_target(
                    var,
                    output_var_names.get(str(nid)),
                    live_slots=live_output_slots.get(str(nid)),
                )
            else:
                all_args = []
                if outputs_expr is not None:
                    all_args.append(("_outputs", outputs_expr))
                all_args.extend(ready_kwargs)
                if uid_arg is not None:
                    all_args.append(uid_arg)
                if extras_expr is not None:
                    all_args.append(("_extras", extras_expr))
                call_name = "node"
                assignment_target = var

            # Multi-line formatting: use multi-line when >3 kwargs or any line would exceed ~88 chars
            kwarg_lines = [f"**{expr}" if key == "**" else f"{key}={expr}" for key, expr in all_args]
            if use_wrapper:
                call_args = ", ".join(kwarg_lines)
                call_expr = f"{call_name}({call_args})"
            else:
                # v2.6.4 Fix 5: raw_call reads wf from ContextVar (set by
                # new_workflow context manager); no need to pass wf positional.
                raw_node_id = _subgraph_emitted_node_id(node_id_prefix, nid) if is_subgraph_function and node_id_prefix is not None else nid
                call_args = ", ".join([repr(node.class_type), repr(raw_node_id), *kwarg_lines])
                call_expr = f"raw_call({call_args})"
            single_line = (
                f"{body_indent}{assignment_target} = {call_expr}"
                if assignment_target is not None
                else f"{body_indent}{call_expr}"
            )

            # -- readability diagnostic: long one-line node call ----------
            if diagnostics is not None and len(single_line) > 120:
                diagnostics.append(
                    EmissionDiagnostic(
                        code=READABILITY_WARNING_LONG_ONE_LINE_NODE_CALL,
                        message=(
                            f"node call for {node.class_type!r} (node {nid}) would be a single "
                            f"line of {len(single_line)} chars (>120); multi-line formatting preferred."
                        ),
                        severity="warning",
                        node_id=str(nid),
                        class_type=node.class_type,
                        detail={"line_length": len(single_line)},
                    )
                )

            prefer_single_line_raw_call = not use_wrapper and len(all_args) <= 2 and len(single_line) <= 120
            if not prefer_single_line_raw_call and (len(all_args) > 3 or len(single_line) > 88):
                # v2.6.4 Fix 8 (refines Fix 2): multi-line statements are
                # SURROUNDED by blank lines (one before, one after) for
                # consistent vertical rhythm — including when followed by
                # single-line statements. Single-line statements still pack
                # together. Section comments stay attached to the first
                # multi-line that follows (no blank between).
                prev = out_lines[-1] if out_lines else ""
                is_section_comment = prev.lstrip().startswith("# ")
                if out_lines and prev != "" and not is_section_comment:
                    out_lines.append("")
                if use_wrapper:
                    head = f"{body_indent}{call_name}(" if assignment_target is None else f"{body_indent}{assignment_target} = {call_name}("
                    lines = [head]
                else:
                    # v2.6.4 Fix 5: drop wf positional from raw_call (ContextVar).
                    raw_node_id = _subgraph_emitted_node_id(node_id_prefix, nid) if is_subgraph_function and node_id_prefix is not None else nid
                    head = (
                        f"{body_indent}raw_call({node.class_type!r}, {raw_node_id!r},"
                        if assignment_target is None
                        else f"{body_indent}{assignment_target} = raw_call({node.class_type!r}, {raw_node_id!r},"
                    )
                    lines = [head]
                for key, expr in all_args:
                    if key == "**":
                        lines.append(f"{continuation_indent}**{expr},")
                    else:
                        lines.append(f"{continuation_indent}{key}={expr},")
                lines.append(f"{body_indent})")
                out_lines.extend(lines)
                out_lines.append("")
            else:
                out_lines.append(single_line)
        else:
            _uid_str = f", _uid={node.uid!r}" if node.uid else ""
            head = f"    {var} = _node(wf, {node.class_type!r}, {nid!r}{_uid_str}"
            if not kwargs:
                out_lines.append(f"{head})")
            else:
                out_lines.append(f"{head},")
                for key, expr in kwargs:
                    out_lines.append(f"        {key}={expr},")
                out_lines.append("    )")

    if use_shared_helpers:
        if out_lines and out_lines[-1] != "":
            out_lines.append("")
        if is_subgraph_function:
            out_lines.append(f"{body_indent}return {_subgraph_return_expr(return_refs, workflow_nodes, var_names, output_var_names, diagnostics)}")
        else:
            tail_lines = _with_id_map_tail_line(tail_lines, var_names)
            # tail_lines are pre-indented at 4 spaces ("    return wf.finalize(...)").
            # When use_shared_helpers emits a flat `wf = new_workflow(...)` form,
            # body_indent is 4, so emit tail lines verbatim.  When a `with`
            # wrapper is in use (body_indent == 8), prepend an extra 4 spaces.
            extra_indent = "    " if body_indent == "        " else ""
            out_lines.extend(extra_indent + line if line else line for line in tail_lines)
        return out_lines
    out_lines.append("")
    out_lines.extend(tail_lines)
    if registered_inputs:
        for input_name, (old_id, field) in registered_inputs.items():
            resolved_field = field
            if field.startswith("widget_") and old_id in workflow_nodes:
                cls = workflow_nodes[old_id].class_type
                node = workflow_nodes[old_id]
                aliases = getattr(node, "metadata", {}).get("input_aliases") or _ui_widget_aliases(node)
                resolved = resolve_widget_key_with_provenance(cls, field, input_aliases=aliases)
                if resolved.name is not None:
                    resolved_field = resolved.name
            descriptor_kwargs: list[str] = []
            if old_id in workflow_nodes:
                node = workflow_nodes[old_id]
                if resolved_field in node.inputs:
                    descriptor_kwargs.append(f"default={_format_value(node.inputs[resolved_field])}")
                elif resolved_field in node.widgets:
                    descriptor_kwargs.append(f"default={_format_value(node.widgets[resolved_field])}")
            if use_shared_helpers:
                suffix = ", " + ", ".join(descriptor_kwargs) if descriptor_kwargs else ""
                out_lines.append(f"    bind_input(wf, {input_name!r}, {_node_binding_expr(old_id, var_names)}, {resolved_field!r}{suffix})")
            else:
                suffix = ", " + ", ".join(descriptor_kwargs) if descriptor_kwargs else ""
                out_lines.append(
                    f"    wf.register_input({input_name!r}, {old_id!r}, {resolved_field!r}, "
                    f"wf.nodes[{old_id!r}].inputs.get({resolved_field!r}, wf.nodes[{old_id!r}].widgets.get({resolved_field!r})){suffix})"
                )

    out_lines.append("    return wf")
    return out_lines


def _with_id_map_tail_line(tail_lines: list[str], var_names: dict[str, str]) -> list[str]:
    # v2.6.4 fix: id_map is derived at runtime via wf.id_map() (returns
    # {ClassType#N: node_id}). The build() source is the authoritative
    # variable-name binding; storing it again at runtime via _set_id_map
    # was bloat that scaled linearly with node count (60+ entry one-line
    # dicts on LTX templates). Drop the emission entirely.
    return tail_lines
































_OUTPUT_CLASSES: dict[str, tuple[str, str]] = {
    "SaveImage": ("image", "image/png"),
    "PreviewImage": ("image", "image/png"),
    "SaveVideo": ("video", "video/mp4"),
    "VHS_VideoCombine": ("video", "video/mp4"),
    "SaveAudio": ("audio", "audio/wav"),
    "SaveAudioMP3": ("audio", "audio/mpeg"),
}


def _ready_template_tail_lines(
    has_ltx_tail: bool,
    workflow_nodes: dict[str, Any],
    edges_in: dict[str, list[Any]],
    var_names: dict[str, str],
    output_var_names: dict[str, dict[int, str]],
    metadata: Mapping[str, Any],
) -> list[str]:
    finalize_args = _finalize_args(workflow_nodes, edges_in, var_names, output_var_names, metadata)
    input_expr = "PUBLIC_INPUT_METADATA" if metadata.get("_has_public_inputs_for_emit") else "{}"
    call = f"    return wf.finalize({input_expr}{finalize_args})"
    if has_ltx_tail:
        return [
            "    apply_ltx_lowvram(wf)",
            "    resolution(384, 256, 9).apply(wf)",
            "    ensure_custom_nodes(wf, READY_METADATA.get(\"requirements\", {}).get(\"custom_nodes\", []))",
            call,
        ]
    return [call]


def _finalize_args(
    workflow_nodes: dict[str, Any],
    edges_in: dict[str, list[Any]],
    var_names: dict[str, str],
    output_var_names: dict[str, dict[int, str]],
    metadata: Mapping[str, Any],
) -> str:
    output_node_ids = _terminal_output_node_ids(workflow_nodes, edges_in)
    args: list[str] = []
    selected_id: str | None = output_node_ids[0] if output_node_ids else None
    if selected_id is not None:
        # Bind output_node to the specific node's emitter-assigned variable name
        # so the finalize call is self-documenting (and so downstream tooling can
        # introspect the chosen terminal node).
        output_var = _first_output_var(output_var_names.get(selected_id))
        args.append(f"output_node={output_var or var_names.get(selected_id, repr(selected_id))}")
    if selected_id is not None:
        node = workflow_nodes[selected_id]
        output_contract = _OUTPUT_CLASSES.get(str(node.class_type))
        if output_contract is not None:
            artifact_kind, mime_type = output_contract
            args.append(f"output_type={node.class_type!r}")
            args.append(f"name={artifact_kind!r}")
            args.append(f"artifact_kind={artifact_kind!r}")
            args.append(f"mime_type={mime_type!r}")
            args.append("expected_cardinality='one'")
        prefix_raw = node.inputs.get("filename_prefix", node.widgets.get("filename_prefix"))
        if prefix_raw is not None and prefix_raw != metadata.get("output_prefix"):
            args.append(f"filename_prefix={_format_value(prefix_raw)}")
    if not args:
        return ""
    return ", " + ", ".join(args)


def _terminal_output_node_ids(
    workflow_nodes: dict[str, Any],
    edges_in: dict[str, list[Any]],
) -> list[str]:
    outgoing = {
        str(edge.from_node)
        for edges in edges_in.values()
        for edge in edges
    }
    candidates = [
        nid
        for nid, node in workflow_nodes.items()
        if nid not in outgoing and _is_output_class(str(node.class_type))
    ]
    return sorted(candidates, key=_id_sort_key)


def _is_output_class(class_type: str) -> bool:
    if class_type in _OUTPUT_CLASSES:
        return True
    lowered = class_type.lower()
    return lowered.startswith(("save", "preview", "create")) or "save" in lowered or "preview" in lowered


def _check_template_formatting(
    combined: str,
    workflow_nodes: dict[str, Any],
    section_groups: dict[str, list[str]],
    diagnostics: list[EmissionDiagnostic],
) -> None:
    """Check generated template for section comments and indentation hygiene.

    Two checks:
    1. If the workflow has >=8 nodes and section_groups are non-empty but no
       section comment lines appear in the output.
    2. If any line in the tail (after the build function body) is un-indented
       (does not start with 4 spaces, '#', blank, or a string-like line).
    """
    lines = combined.split("\n")

    # Check 1: missing section comments for large workflows
    if len(workflow_nodes) >= _SECTION_NODE_THRESHOLD and section_groups:
        has_section_comment = any(
            line.strip().startswith("# ") and any(
                line.strip().endswith(f"# {sec}")
                or line.strip() == f"# {sec}"
                or line.strip().startswith(f"# {sec}")
                for sec in _SECTION_ORDER
            )
            for line in lines
        )
        if not has_section_comment:
            diagnostics.append(
                EmissionDiagnostic(
                    code=READABILITY_WARNING_GENERATED_TEMPLATE_NOT_FORMATTED,
                    message=(
                        f"Generated template has {len(workflow_nodes)} nodes but lacks section "
                        f"comments (e.g. # Inputs, # Loaders, # Conditioning). "
                        f"Section comments improve readability for large workflows."
                    ),
                    severity="warning",
                    detail={
                        "node_count": len(workflow_nodes),
                        "section_groups_present": bool(section_groups),
                    },
                )
            )

    # Check 2: un-indented tail lines (after build function)
    # Find the return wf line and check everything after it
    in_build = False
    past_return = False
    for line in lines:
        stripped = line.strip()
        if stripped == "def build() -> VibeWorkflow:":
            in_build = True
            continue
        if in_build and stripped.startswith("return wf"):
            past_return = True
            continue
        if past_return:
            # After return wf, lines should be empty or start with 4+ spaces
            # (internal to the build function) or be completely blank
            if stripped and not line.startswith("    ") and not stripped.startswith("#"):
                diagnostics.append(
                    EmissionDiagnostic(
                        code=READABILITY_WARNING_GENERATED_TEMPLATE_NOT_FORMATTED,
                        message=(
                            f"Generated template has un-indented tail line: {stripped!r}. "
                            f"Lines after return wf should be blank or properly indented."
                        ),
                        severity="warning",
                        detail={"unindented_line": stripped},
                    )
                )
                break  # One diagnostic is enough


def _has_ltx_lowvram_tail(category_id: str) -> bool:
    return category_id.startswith("video/ltx2_3_t2v") or category_id.startswith("video/ltx2_3_i2v")


def _apply_overrides(nodes: dict[str, Any], edges_in: dict[str, list[Any]], patches: list[dict[str, Any]]) -> None:
    for patch in patches:
        match = patch.get("match", {})
        target_ids: list[str] = []
        if "node_id" in match:
            target_ids = [str(match["node_id"])]
        elif "class_type" in match:
            class_target = match["class_type"]
            ordinal = match.get("node_index")
            matches = [nid for nid, node in nodes.items() if node.class_type == class_target]
            if ordinal is not None and 0 <= ordinal < len(matches):
                target_ids = [matches[ordinal]]
            else:
                target_ids = matches

        for tid in target_ids:
            node = nodes.get(tid)
            if node is None:
                continue
            for old, new in (patch.get("rename_inputs") or {}).items():
                if old in node.widgets:
                    node.widgets[new] = node.widgets.pop(old)
                if old in node.inputs:
                    node.inputs[new] = node.inputs.pop(old)
            for key, value in (patch.get("set_inputs") or {}).items():
                if key in node.widgets:
                    node.widgets[key] = value
                else:
                    node.inputs[key] = value
            for key in patch.get("remove_inputs") or []:
                node.widgets.pop(key, None)
                node.inputs.pop(key, None)


_NODE_HELPER_SOURCE = '''
def _node(
    wf: VibeWorkflow,
    class_type: str,
    _id: str,
    _extras: dict | None = None,
    _outputs: tuple[str, ...] | None = None,
    _uid: str | None = None,
    **kwargs,
):
    """Create a node, preserving the original node id from the source workflow.

    `_extras` carries kwargs whose names are not valid Python identifiers
    (e.g. "resize_type.multiple") which Python disallows as kwarg syntax.
    They are applied to the new node post-construction.
    """
    from vibecomfy.handles import Handle
    builder = wf.node(class_type, **kwargs)
    if _uid:
        builder.node.uid = _uid
    if _outputs is not None:
        builder.node.metadata["output_names"] = list(_outputs)
    if _extras:
        for key, value in _extras.items():
            if isinstance(value, Handle):
                wf.connect(value, f"{builder.node.id}.{key}")
            else:
                builder.node.inputs[key] = value
    if builder.node.id != _id:
        old_id = builder.node.id
        node = wf.nodes.pop(old_id)
        node.id = _id
        wf.nodes[_id] = node
        for edge in wf.edges:
            if edge.to_node == old_id:
                edge.to_node = _id
            if edge.from_node == old_id:
                edge.from_node = _id
    return builder
'''


# ---------------------------------------------------------------------------
# Node signature catalog for agent-edit surface
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class InputSignatureField:
    """A single input field described by a schema for agent-edit catalog display."""

    name: str
    type: str | None = None
    required: bool = False
    default: Any = None


@dataclass(frozen=True, slots=True)
class OutputSignatureField:
    """A single output slot described by a schema for agent-edit catalog display."""

    name: str | None = None
    type: str | None = None


@dataclass(frozen=True, slots=True)
class NodeSignatureRow:
    """A structured row describing one node type for the agent-edit catalog.

    Rows are produced by ``emit_available_node_signatures(...)`` from a
    ``SchemaProvider`` and may be filtered by socket-type compatibility.
    """

    class_type: str
    inputs: list[InputSignatureField]
    outputs: list[OutputSignatureField]
    source_confidence: float = 1.0
    pack: str | None = None


def emit_available_node_signatures(
    schema_provider: Any,
    *,
    focus_types: list[str] | None = None,
    compatible_input_type: str | None = None,
    compatible_output_type: str | None = None,
) -> list[NodeSignatureRow]:
    """Return structured rows for every known node type in *schema_provider*.

    Two query paths are supported:

    * **Enumeration** — when *focus_types* is ``None``, calls
      ``schema_provider.schemas()`` (or the protocol equivalent via
      ``schemas_for``) to enumerate every schema the provider knows.
    * **Focused / per-node** — when *focus_types* is a list of class-type
      strings, calls ``schema_provider.get_schema(...)`` for each entry.

    Optional compatibility filtering:

    * *compatible_input_type* — keep only rows that have at **least one
      output** socket type compatible with the given type (``MODEL`` →
      nodes whose output sockets can feed a ``MODEL`` input).
    * *compatible_output_type* — keep only rows that have at **least one
      input** socket type compatible with the given type (``MODEL`` →
      nodes that can consume a ``MODEL`` output).

    Both filters can be combined; when both are supplied a row must
    satisfy both.

    Unknown socket types (``None`` or ``\"*\"``) are treated as
    **compatible with everything** (the same contract as
    ``socket_types_compatible`` in ``vibecomfy.schema.validate``).

    Rows are always sorted by ``class_type`` for determinism.
    """
    from vibecomfy.schema import schema_for, schemas_for
    from vibecomfy.schema.validate import socket_types_compatible

    schemas_map: dict[str, Any] = {}

    if focus_types is not None:
        for class_type in focus_types:
            if not isinstance(class_type, str):
                continue
            schema = schema_for(schema_provider, class_type)
            if schema is not None:
                schemas_map[class_type] = schema
    else:
        raw = schemas_for(schema_provider)
        if raw is not None:
            schemas_map.update(
                {str(key): value for key, value in raw.items() if isinstance(key, str)}
            )

    rows: list[NodeSignatureRow] = []
    for class_type in sorted(schemas_map):
        schema = schemas_map[class_type]
        inputs = _build_input_signature_fields(schema)
        outputs = _build_output_signature_fields(schema)
        confidence = float(getattr(schema, "confidence", 1.0) or 1.0)
        pack = getattr(schema, "pack", None) or None

        # Compatibility filtering
        if compatible_input_type is not None:
            if not any(
                socket_types_compatible(output.type, compatible_input_type)
                for output in outputs
            ):
                continue

        if compatible_output_type is not None:
            if not any(
                socket_types_compatible(compatible_output_type, input_.type)
                for input_ in inputs
            ):
                continue

        rows.append(
            NodeSignatureRow(
                class_type=class_type,
                inputs=inputs,
                outputs=outputs,
                source_confidence=confidence,
                pack=pack,
            )
        )

    return rows


def _build_input_signature_fields(schema: Any) -> list[InputSignatureField]:
    inputs = getattr(schema, "inputs", None) or {}
    fields: list[InputSignatureField] = []
    for name, spec in inputs.items():
        if not isinstance(name, str):
            continue
        spec_type = getattr(spec, "type", None) if hasattr(spec, "type") else None
        spec_required = bool(getattr(spec, "required", False)) if hasattr(spec, "required") else False
        spec_default = getattr(spec, "default", None) if hasattr(spec, "default") else None
        fields.append(
            InputSignatureField(
                name=name,
                type=str(spec_type) if spec_type is not None else None,
                required=spec_required,
                default=spec_default,
            )
        )
    return fields


def _build_output_signature_fields(schema: Any) -> list[OutputSignatureField]:
    outputs = getattr(schema, "outputs", None) or []
    fields: list[OutputSignatureField] = []
    for output in outputs:
        out_type = getattr(output, "type", None) if hasattr(output, "type") else None
        out_name = getattr(output, "name", None) if hasattr(output, "name") else None
        fields.append(
            OutputSignatureField(
                name=str(out_name) if out_name is not None else None,
                type=str(out_type) if out_type is not None else None,
            )
        )
    return fields


def format_signature_rows(
    rows: list[NodeSignatureRow],
    *,
    show_pack: bool = False,
    show_confidence: bool = False,
) -> str:
    """Format a list of ``NodeSignatureRow`` as a deterministic text catalog.

    Each row is rendered as a Python-like function signature::

        def CheckpointLoaderSimple(ckpt_name: COMBO = ...) -> MODEL, CLIP, VAE:

    The output is sorted by ``class_type``.

    If *show_pack* is ``True``, a ``# pack: ...`` comment line precedes
    each signature.  If *show_confidence* is ``True``, a ``# confidence:
    0.XX`` suffix is appended.
    """
    from vibecomfy.porting.identity.codec import to_python_identifier

    lines: list[str] = []
    for row in sorted(rows, key=lambda r: r.class_type):
        prefix_parts: list[str] = []
        if show_pack and row.pack:
            prefix_parts.append(f"# pack: {row.pack}")
        suffix_parts: list[str] = []
        if show_confidence and row.source_confidence < 1.0:
            suffix_parts.append(f"confidence: {row.source_confidence:.2f}")

        param_parts: list[str] = []
        for field in row.inputs:
            has_default = field.default is not None
            default_str = " = ..." if has_default else ""
            type_str = f": {field.type}" if field.type else ""
            optional_marker = "" if field.required else ""
            name_ident = to_python_identifier(field.name)
            param_parts.append(f"{name_ident}{type_str}{default_str}")

        return_parts: list[str] = []
        for output in row.outputs:
            out_name = output.name
            out_type = output.type
            if out_type:
                return_parts.append(out_type)
            elif out_name:
                return_parts.append(out_name)
            else:
                return_parts.append("Any")

        params = ", ".join(param_parts)
        returns = ", ".join(return_parts) if return_parts else "None"
        sig = f"def {row.class_type}({params}) -> {returns}:"

        comment_parts = prefix_parts + suffix_parts
        if comment_parts:
            sig = "  ".join(comment_parts) + f"\n{sig}"

        lines.append(sig)

    return "\n".join(lines) + "\n"


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
