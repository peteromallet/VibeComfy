from __future__ import annotations

import ast
from typing import Any, Mapping, TYPE_CHECKING

from vibecomfy.porting.emit_prepare import _emit_agent_edit_lines, _prepare_workflow_for_emit
from vibecomfy.porting.emit_subgraph import (
    _apply_subgraph_names_to_prepared,
    _emit_subgraph_functions,
    _subgraph_definitions_from_raw,
)

if TYPE_CHECKING:
    from vibecomfy.porting.emitter import EmissionDiagnostic


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
    from vibecomfy.workflow import VibeWorkflow

    if not isinstance(workflow, VibeWorkflow):
        raise TypeError(
            f"emit_agent_edit_python requires VibeWorkflow, got {type(workflow).__name__}. "
            "Raw LiteGraph UI JSON must be converted before emitter calls."
        )

    prepared = _prepare_workflow_for_emit(
        workflow,
        apply_overrides=None,
        keep_virtual_wires=True,
        prune_dead_branches=False,
        variable_name_locks=variable_name_locks,
        strict_variable_name_locks=strict_variable_name_locks,
        diagnostics=diagnostics,
    )
    if raw_workflow is not None:
        subgraph_definitions = _subgraph_definitions_from_raw(raw_workflow, source_path=None)
        if subgraph_definitions:
            prepared["subgraph_definitions"] = subgraph_definitions
            _apply_subgraph_names_to_prepared(prepared)
    lines = _emit_agent_edit_lines(prepared)
    subgraph_lines = _emit_subgraph_functions(
        prepared,
        diagnostics=diagnostics,
        constant_map={},
        variable_name_locks=variable_name_locks,
        strict_variable_name_locks=strict_variable_name_locks,
    )
    if subgraph_lines:
        lines.extend(["", *subgraph_lines])
    source = "\n".join(lines) + "\n"
    try:
        ast.parse(source)
    except SyntaxError as exc:
        raise RuntimeError(f"Generated agent-edit Python failed syntax check: {exc}") from exc
    return source
