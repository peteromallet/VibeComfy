from __future__ import annotations

from typing import Any, Mapping

from vibecomfy.porting.emit.build_function import _emit_build_function
from vibecomfy.porting.emit.diagnostics import EmissionDiagnostic
from vibecomfy.porting.emit.emit_ready import _NODE_HELPER_SOURCE
from vibecomfy.porting.emit.agent_edit_core import _prepare_workflow_for_emit


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
    from vibecomfy.porting.emit.emit_ready import emit_ready_template_python as _emit_ready_template_python  # noqa: PLC0415

    return _emit_ready_template_python(
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
        object_info_identities=object_info_identities,
    )


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
    """Compatibility wrapper for the package ready-template emitter."""
    return emit_ready_template_python(
        workflow,
        ready_metadata=ready_metadata,
        ready_requirements=ready_requirements,
        template_id=template_id,
        registered_inputs=registered_inputs,
        apply_overrides=apply_overrides,
        raw_workflow=raw_workflow,
    )


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


def emit_agent_edit_python(
    workflow,
    *,
    diagnostics: list[EmissionDiagnostic] | None = None,
    raw_workflow: dict[str, Any] | None = None,
    variable_name_locks: Mapping[str, str] | None = None,
    strict_variable_name_locks: bool = False,
) -> str:
    """Render a workflow as the Python assignment view used by EditSession.

    This is intentionally parallel to ``emit_scratchpad_python``.  It reuses the
    same lower-level workflow preparation and locked variable-name plumbing, but
    emits a compact edit surface rather than runnable scratchpad code.
    """
    from vibecomfy.porting.emit.emit_agent_edit import emit_agent_edit_python as _emit_agent_edit_python  # noqa: PLC0415

    return _emit_agent_edit_python(
        workflow,
        diagnostics=diagnostics,
        raw_workflow=raw_workflow,
        variable_name_locks=variable_name_locks,
        strict_variable_name_locks=strict_variable_name_locks,
    )
