from __future__ import annotations

import ast
import json
import logging
import pprint
from pathlib import Path
from typing import Any, Mapping

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
from vibecomfy.porting.emit.format_values import _MODEL_FILE_SUFFIXES, _format_value
from vibecomfy.porting.emit.constants_hoist import (
    _SECTION_NODE_THRESHOLD,
    _SECTION_ORDER,
    _classify_node_role,
    _classify_value_category,
    _constant_name_base_for_category,
    _constant_name_for_model_value,
    _constant_name_for_string_value,
    _drop_output_prefix_constants,
    _model_basename,
    _resolve_graph_field_get_string,
    _translate_widget_for_key,
)
from vibecomfy.porting.emit.constants_hoist import _build_section_groups as _build_section_groups_impl
from vibecomfy.porting.emit.constants_hoist import _hoist_constants as _hoist_constants_impl
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
    _ui_widget_aliases,
)
from vibecomfy.porting.emit.build_function import (
    _emit_build_function,
    _with_id_map_tail_line,
)
from vibecomfy.porting.emit.public_inputs import (
    _PublicInputBinding,
    _PublicInputSpec,
    _format_public_inputs_block,
    _looks_like_placeholder_filename,
)
from vibecomfy.porting.emit.public_inputs import _public_input_specs as _public_input_specs_impl
from vibecomfy.porting.emit.public_inputs import _remap_public_inputs_for_materialized_subgraphs as _remap_public_inputs_for_materialized_subgraphs_impl
from vibecomfy.porting.emit.subgraph_defs import (
    _SubgraphDef,
    _SubgraphPort,
    _build_subgraph_def,
    _disambiguated_subgraph_slugs,
    _slugify_identifier,
    _safe_kwarg_name,
    _short_subgraph_id_prefix,
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
from vibecomfy.porting.emit.subgraph_functions import _emit_subgraph_functions
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
from vibecomfy.porting.emit import wrappers as _wrappers
from vibecomfy.porting.widgets.schema import WIDGET_SCHEMA

logger = logging.getLogger(__name__)
def __getattr__(name: str) -> Any:
    if name in {"_WRAPPER_CLASS_TO_MODULE", "_WRAPPER_CLASS_TO_SYMBOL"}:
        return getattr(_wrappers, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


GENERATED_HEADER = (
    "# vibecomfy: generated\n"
    "# For hand-editing, run: python -m vibecomfy.cli copy-to-recipe <id>\n"
)

LTX2_3_TAIL_PATCHES: tuple[str, ...] = (
    "from vibecomfy.patches.ltx_lowvram import apply as apply_ltx_lowvram",
    "from vibecomfy.patches.requirements import ensure_custom_nodes",
    "from vibecomfy.patches.resolution import resolution",
)

_AGENT_EDIT_STRING_ELIDE_THRESHOLD = 400


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
            nodes, incoming, reserved_names=reserved
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


def _subgraph_port_index_for_instance_field(node: Any, subgraph: _SubgraphDef, field: str) -> int | None:
    candidates = _subgraph_instance_port_candidate_names(node, subgraph)
    for index, names in candidates.items():
        if field in names:
            return index
    return None


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


def _node_local_output_names(node: Any) -> list[str]:
    from vibecomfy.porting.emit.emit_ready import _node_local_output_names as _impl  # noqa: PLC0415

    return _impl(node)


def _node_local_arity_check(node: Any, ui_output_count: int | None) -> int:
    from vibecomfy.porting.emit.emit_ready import _node_local_arity_check as _impl  # noqa: PLC0415

    return _impl(node, ui_output_count)


from vibecomfy.porting.emit.entrypoints import (
    emit_agent_edit_python,
    emit_ready_template_python,
    emit_scratchpad_python,
    format_as_python,
)
from vibecomfy.porting.emit.agent_edit_core import (
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

for _public_entrypoint in (
    emit_agent_edit_python,
    emit_ready_template_python,
    emit_scratchpad_python,
    format_as_python,
):
    _public_entrypoint.__module__ = __name__
del _public_entrypoint


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


def _node_binding_expr(node_id: str, var_names: dict[str, str]) -> str:
    var = var_names.get(str(node_id))
    if var is not None and _wrapper_module_for_class(var.split("_", 1)[0]) is not None:
        return f"{var}.node.id"
    if var is not None:
        return f"{var}.node.id"
    return repr(str(node_id))


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


def _edges_in_with_subgraph_external_refs(
    prepared: dict[str, Any],
    workflow_nodes: dict[str, Any],
    edges_in: dict[str, list[Any]],
) -> dict[str, list[Any]]:
    subgraphs: dict[str, _SubgraphDef] = prepared.get("subgraph_definitions") or {}
    if not subgraphs:
        return edges_in

    from vibecomfy.workflow import VibeEdge

    out = {str(node_id): list(edges) for node_id, edges in edges_in.items()}
    for node_id, node in workflow_nodes.items():
        subgraph = subgraphs.get(str(getattr(node, "class_type", "")))
        if subgraph is None:
            continue
        for port in subgraph.inputs:
            if port.external_ref is None:
                continue
            source_id, source_slot = port.external_ref
            if str(source_id) not in workflow_nodes:
                continue
            out.setdefault(str(node_id), []).append(
                VibeEdge(str(source_id), str(source_slot), str(node_id), port.name)
            )
    return out


def _format_metadata_dict(name: str, value: dict[str, Any]) -> str:
    formatted = pprint.pformat(value, width=110, sort_dicts=False)
    return f"{name} = {formatted}"


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
