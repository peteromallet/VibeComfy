"""Subgraph function emission orchestration."""

from __future__ import annotations

from typing import Any, Mapping

from vibecomfy.porting.emit.build_function import _emit_build_function
from vibecomfy.porting.emit.diagnostics import EmissionDiagnostic
from vibecomfy.porting.emit.naming_codegen import (
    _apply_locked_variable_names,
    _compute_output_variable_names,
    _compute_variable_names,
)
from vibecomfy.porting.emit.subgraph_calls import (
    _apply_subgraph_names_to_prepared,
    _subgraph_docstring,
    _subgraph_signature,
)
from vibecomfy.porting.emit.subgraph_defs import (
    _SubgraphDef,
    _subgraph_topological_order,
)


def _emit_subgraph_functions(
    prepared: dict[str, Any],
    *,
    diagnostics: list[EmissionDiagnostic] | None,
    constant_map: dict[tuple[str, str], str] | None,
    required_ids_by_subgraph: dict[str, set[str]] | None = None,
    variable_name_locks: Mapping[str, str] | None = None,
    strict_variable_name_locks: bool = False,
) -> list[str]:
    subgraphs: dict[str, _SubgraphDef] = prepared.get("subgraph_definitions") or {}
    if not subgraphs:
        return []
    lines = ["# === Subgraph functions ===", ""]
    for subgraph_id in _subgraph_topological_order(subgraphs):
        subgraph = subgraphs[subgraph_id]
        inner_prepared = {
            "nodes": subgraph.nodes,
            "edges_in": subgraph.edges_in,
            "var_names": _compute_variable_names(subgraph.nodes, [edge for edges in subgraph.edges_in.values() for edge in edges]),
            "subgraph_definitions": subgraphs,
        }
        _apply_locked_variable_names(
            subgraph.nodes,
            inner_prepared["var_names"],
            variable_name_locks=variable_name_locks,
            strict=strict_variable_name_locks,
            diagnostics=diagnostics,
            scope_path=subgraph.id,
        )
        inner_prepared["output_var_names"] = _compute_output_variable_names(
            subgraph.nodes,
            inner_prepared["var_names"],
            [edge for edges in subgraph.edges_in.values() for edge in edges],
        )
        _apply_subgraph_names_to_prepared(inner_prepared)
        signature = _subgraph_signature(subgraph)
        docstring = _subgraph_docstring(subgraph)
        lines.extend(
            _emit_build_function(
                inner_prepared,
                workflow_id_expr="READY_METADATA",
                source_path_expr="__file__",
                source_type="ready_template",
                source_provenance=None,
                registered_inputs=None,
                public_inputs=None,
                tail_lines=[],
                diagnostics=diagnostics,
                use_shared_helpers=True,
                constant_map=constant_map,
                section_groups={},
                function_name=subgraph.slug,
                function_signature=signature,
                function_docstring=docstring,
                return_refs=subgraph.return_refs,
                external_refs=subgraph.input_refs,
                node_id_prefix=subgraph.id,
                required_ids=required_ids_by_subgraph.get(subgraph.id, set()) if required_ids_by_subgraph is not None else None,
            )
        )
        lines.append("")
        lines.append("")
    while lines and lines[-1] == "":
        lines.pop()
    return lines
