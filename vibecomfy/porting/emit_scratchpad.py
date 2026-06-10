from __future__ import annotations

from typing import Any, Mapping, TYPE_CHECKING

from vibecomfy.porting.emit_prepare import _prepare_workflow_for_emit
from vibecomfy.porting.emit_ready import _emit_build_function, _NODE_HELPER_SOURCE

if TYPE_CHECKING:
    from vibecomfy.porting.emitter import EmissionDiagnostic


def emit_scratchpad_python(
    workflow,
    *,
    workflow_id: str | None = None,
    source_path: str | None = None,
    provenance: dict[str, Any] | None = None,
    registered_inputs: dict[str, tuple[str, str]] | None = None,
    apply_overrides: dict[str, Any] | None = None,
    diagnostics: list[EmissionDiagnostic] | None = None,
    keep_virtual_wires: bool = False,
    prune_dead_branches: bool = True,
    variable_name_locks: Mapping[str, str] | None = None,
    strict_variable_name_locks: bool = False,
    object_info_identities: dict[str, Any] | None = None,
) -> str:
    # Lazy import to avoid circular dependency with emitter.py
    # (emitter.py re-exports from this module).
    from vibecomfy.porting.emitter import _drain_lookup_warning_diagnostics, _use_object_info_identities

    with _use_object_info_identities(object_info_identities):
        result_text = _emit_scratchpad_python_inner(
            workflow,
            workflow_id=workflow_id,
            source_path=source_path,
            provenance=provenance,
            registered_inputs=registered_inputs,
            apply_overrides=apply_overrides,
            diagnostics=diagnostics,
            keep_virtual_wires=keep_virtual_wires,
            prune_dead_branches=prune_dead_branches,
            variable_name_locks=variable_name_locks,
            strict_variable_name_locks=strict_variable_name_locks,
        )
        _drain_lookup_warning_diagnostics(diagnostics)
    return result_text


def _emit_scratchpad_python_inner(
    workflow,
    *,
    workflow_id: str | None = None,
    source_path: str | None = None,
    provenance: dict[str, Any] | None = None,
    registered_inputs: dict[str, tuple[str, str]] | None = None,
    apply_overrides: dict[str, Any] | None = None,
    diagnostics: list[EmissionDiagnostic] | None = None,
    keep_virtual_wires: bool = False,
    prune_dead_branches: bool = True,
    variable_name_locks: Mapping[str, str] | None = None,
    strict_variable_name_locks: bool = False,
) -> str:
    workflow_id = workflow_id or getattr(workflow, "id", "scratchpad")
    prepared = _prepare_workflow_for_emit(
        workflow,
        apply_overrides=apply_overrides,
        keep_virtual_wires=keep_virtual_wires,
        prune_dead_branches=prune_dead_branches,
        variable_name_locks=variable_name_locks,
        strict_variable_name_locks=strict_variable_name_locks,
        diagnostics=diagnostics,
    )
    source_path_expr = repr(source_path) if source_path is not None else "__file__"

    out_lines: list[str] = []
    out_lines.append("# vibecomfy: generated scratchpad")
    out_lines.append('"""Auto-generated VibeComfy scratchpad."""')
    out_lines.append("from __future__ import annotations")
    out_lines.append("")
    out_lines.append("from vibecomfy.workflow import VibeWorkflow, WorkflowSource")
    out_lines.append("")
    out_lines.append("")
    out_lines.extend(
        _emit_build_function(
            prepared,
            workflow_id_expr=repr(workflow_id),
            source_path_expr=source_path_expr,
            source_type="scratchpad",
            source_provenance=provenance or {},
            registered_inputs=registered_inputs,
            public_inputs=None,
            tail_lines=["    wf.finalize_metadata()"],
            diagnostics=diagnostics,
        )
    )
    out_lines.append("")
    out_lines.append(_NODE_HELPER_SOURCE)
    return "\n".join(out_lines) + "\n"
