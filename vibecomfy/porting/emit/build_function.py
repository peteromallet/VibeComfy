"""Build-function code-generation helpers."""

from __future__ import annotations

import ast
from typing import Any

from vibecomfy.porting.emit.constants_hoist import _SECTION_ORDER
from vibecomfy.porting.emit.diagnostics import (
    EmissionDiagnostic,
    READABILITY_WARNING_GENERATED_VARIABLE_NAME_TOO_LONG,
    READABILITY_WARNING_LONG_ONE_LINE_NODE_CALL,
)
from vibecomfy.porting.emit.emit_kwargs import (
    _edges_in_with_subgraph_external_refs,
    _node_binding_expr,
)
from vibecomfy.porting.emit.format_values import _format_value
from vibecomfy.porting.emit.naming_codegen import (
    _assignment_target,
    _live_output_slots_for_function,
    _topological_node_order,
)
from vibecomfy.porting.emit.node_kwargs_core import _node_kwargs, _ui_widget_aliases
from vibecomfy.porting.emit.public_inputs import _PublicInputSpec
from vibecomfy.porting.emit.subgraph_calls import (
    _emit_subgraph_call_statement,
    _subgraph_node_id_required,
    _subgraph_return_expr,
)
from vibecomfy.porting.emit.subgraph_defs import _subgraph_emitted_node_id
from vibecomfy.porting.emit.wrappers import (
    _wrapper_kwarg_name,
    _wrapper_module_for_class,
    _wrapper_symbol_for_class,
)
from vibecomfy.porting.widgets.aliases import resolve_widget_key_with_provenance


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
                # generated schema (vibecomfy/nodes/<pack>.py). Only
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
