"""Agent-edit Python emission — the ``surface`` lens (Law 4, batch 11).

This module produces the Python assignment view used by EditSession and is
the implementation of the renderer's ``surface`` lens
(``vibecomfy.porting.render``).  The renderer is the single entry point for
model-facing graph text: stages request ``render_text(wf, ("surface",
"topology"))`` and never consume ad-hoc per-stage projections.  The Python
view here is the lensed surface over the IR — node inventory with named
fields/sockets and explicit schema status — emitted from the retained
``VibeWorkflow`` only.
"""

from __future__ import annotations

import ast
from typing import Any, Mapping, TYPE_CHECKING

from vibecomfy.porting.emit.emit_prepare import _emit_agent_edit_lines, _prepare_workflow_for_emit
from vibecomfy.porting.emit.emit_subgraph import (
    _apply_subgraph_names_to_prepared,
    _subgraph_definitions_from_raw,
    _subgraph_topological_order,
)

if TYPE_CHECKING:
    from vibecomfy.porting.emitter import EmissionDiagnostic


def emit_agent_edit_python(
    workflow,
    *,
    diagnostics: list[EmissionDiagnostic] | None = None,
    raw_workflow: dict[str, Any] | None = None,
) -> str:
    """Render a workflow as the Python assignment view used by EditSession.

    This is the implementation of the renderer's ``surface`` lens
    (``vibecomfy.porting.render``): the model-facing graph text flows through
    the composable renderer, never through ad-hoc projections.  Bindings are
    a pure function of ``(class_type, uid-order)`` — the agent-edit surface
    does not accept locked aliases.
    """
    from vibecomfy.workflow import VibeWorkflow

    if not isinstance(workflow, VibeWorkflow):
        raise TypeError(
            f"emit_agent_edit_python requires VibeWorkflow, got {type(workflow).__name__}. "
            "Raw LiteGraph UI JSON must be converted before emitter calls."
        )

    # Prepare/subgraph naming stamp node.metadata.  Copy first so emit is
    # a pure function of the IR (Law 2: interpret(∅, emit(wf)) must not
    # mutate wf).
    workflow = workflow.copy()
    prepared = _prepare_workflow_for_emit(
        workflow,
        apply_overrides=None,
        keep_virtual_wires=True,
        prune_dead_branches=False,
        project_execution_edges=False,
        diagnostics=diagnostics,
    )
    definitions_source = raw_workflow
    if definitions_source is None:
        metadata_definitions = getattr(workflow, "metadata", None) or {}
        if isinstance(metadata_definitions, Mapping) and metadata_definitions.get("definitions"):
            definitions_source = {"definitions": metadata_definitions.get("definitions")}
    if definitions_source is not None:
        subgraph_definitions = _subgraph_definitions_from_raw(definitions_source, source_path=None)
        if subgraph_definitions:
            prepared["subgraph_definitions"] = subgraph_definitions
            _apply_subgraph_names_to_prepared(prepared)
    lines = _emit_agent_edit_lines(prepared)
    # FunctionDef is outside the editable grammar.  Emit the designed
    # subgraph_interface(...) form so interpret can reconstruct signatures
    # without executing subgraph bodies (bodies stay door-owned).
    interface_lines = _emit_subgraph_interface_calls(prepared)
    if interface_lines:
        lines.extend(["", *interface_lines])
    source = "\n".join(lines) + "\n"
    try:
        ast.parse(source)
    except SyntaxError as exc:
        raise RuntimeError(f"Generated agent-edit Python failed syntax check: {exc}") from exc
    return source


def _emit_subgraph_interface_calls(prepared: dict[str, Any]) -> list[str]:
    """Emit designed ``subgraph_interface(...)`` calls (not FunctionDef)."""
    subgraphs = prepared.get("subgraph_definitions") or {}
    if not subgraphs:
        return []
    lines = ["# subgraph interfaces — signatures only; bodies are door-owned"]
    for subgraph_id in _subgraph_topological_order(subgraphs):
        subgraph = subgraphs[subgraph_id]
        inputs = tuple((port.name, port.type) for port in subgraph.inputs)
        outputs = tuple((port.name, port.type) for port in subgraph.outputs)
        lines.append(
            "subgraph_interface("
            f"name={subgraph.slug!r}, "
            f"id={subgraph.id!r}, "
            f"inputs={inputs!r}, "
            f"outputs={outputs!r})"
        )
    return lines
