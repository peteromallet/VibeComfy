from __future__ import annotations

from typing import Any

from vibecomfy.porting.emit.emit_agent_edit import emit_agent_edit_python
from vibecomfy.porting.emit.emit_ready import (
    _emit_build_function,
    emit_ready_template_python as _render_canonical_python,
)
from vibecomfy.porting.emit.signatures import EmissionDiagnostic


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
    """Compatibility wrapper for the canonical executable emitter."""
    return emit_canonical_python(
        workflow,
        ready_metadata=ready_metadata,
        ready_requirements=ready_requirements,
        template_id=template_id,
        registered_inputs=registered_inputs,
        apply_overrides=apply_overrides,
    )


def emit_canonical_python(
    workflow,
    *,
    workflow_id: str | None = None,
    source_path: str | None = None,
    provenance: dict[str, Any] | None = None,
    ready_metadata: dict[str, Any] | None = None,
    ready_requirements: dict[str, Any] | None = None,
    template_id: str | None = None,
    registered_inputs: dict[str, tuple[str, str]] | None = None,
    apply_overrides: dict[str, Any] | None = None,
    diagnostics: list[EmissionDiagnostic] | None = None,
    object_info_identities: dict[str, Any] | None = None,
) -> str:
    """Emit the sole executable Python workflow source.

    Ready and scratchpad migration entry points delegate here, so one
    formatting/compiler contract owns every executable generated source while
    agent-edit remains an explicitly non-authoritative view.
    """
    from vibecomfy.workflow import VibeWorkflow

    if not isinstance(workflow, VibeWorkflow):
        raise TypeError(
            f"emit_canonical_python requires VibeWorkflow, got {type(workflow).__name__}"
        )
    source_id = str(workflow_id or workflow.id)
    if source_id != str(workflow.id):
        raise ValueError(
            f"canonical emitter workflow identity mismatch: declared {source_id!r} "
            f"must equal authored VibeWorkflow.id {workflow.id!r}"
        )
    identity_report = workflow.validate_identity()
    if not identity_report.ok:
        raise ValueError(identity_report.issues[0].message)
    if apply_overrides:
        raise ValueError(
            "canonical workflow variants must be declared in VibeWorkflow.variants; "
            "dynamic apply_overrides patches are not a semantic source"
        )
    metadata = dict(getattr(workflow, "metadata", {}) or {})
    metadata.update(dict(ready_metadata or {}))
    metadata["ready_template"] = source_id
    metadata.setdefault("workflow_template", source_id.rsplit("/", 1)[-1])
    if provenance is not None:
        metadata["provenance"] = dict(provenance)
    requirements = dict(ready_requirements or {})
    if not requirements:
        requirements = {
            "models": list(getattr(workflow.requirements, "models", ()) or ()),
            "custom_nodes": list(getattr(workflow.requirements, "custom_nodes", ()) or ()),
        }
    if registered_inputs is None:
        registered_inputs = {
            str(name): (str(item.node_id), str(item.field))
            for name, item in getattr(workflow, "inputs", {}).items()
        }
    return _render_canonical_python(
        workflow,
        ready_metadata=metadata,
        ready_requirements=requirements,
        template_id=str(template_id or source_id),
        registered_inputs=registered_inputs or None,
        apply_overrides=None,
        diagnostics=diagnostics,
        # Canonical sources never consult raw UI evidence for semantics.  The
        # ready renderer receives an empty raw source and restores
        # recursive/variant data from the detached IR below.
        raw_workflow={},
        object_info_identities=object_info_identities,
    )


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
    object_info_identities: dict[str, Any] | None = None,
) -> str:
    """One-way ready-template migration into canonical executable source."""
    migrated = workflow.copy()
    for node_id, node in migrated.nodes.items():
        if not str(node.uid or "").strip():
            node.uid = str(node_id)
    return emit_canonical_python(
        migrated,
        ready_metadata=ready_metadata,
        ready_requirements=ready_requirements,
        template_id=template_id,
        registered_inputs=registered_inputs,
        apply_overrides=apply_overrides,
        diagnostics=diagnostics,
        object_info_identities=object_info_identities,
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
    keep_virtual_wires: bool = True,
    prune_dead_branches: bool = False,
) -> str:
    if not keep_virtual_wires or prune_dead_branches:
        message = (
            "scratchpad projection options are migration-only and no longer select "
            "an alternate executable graph; canonical emission preserves virtual "
            "wires and authored branches"
        )
        if diagnostics is None:
            raise ValueError(
                f"{message}; use the canonical defaults keep_virtual_wires=True and "
                "prune_dead_branches=False, then migrate through `vibecomfy port convert`"
            )
        diagnostics.append(
            EmissionDiagnostic(
                code="deprecated_scratchpad_projection_options",
                message=message,
                severity="warning",
            )
        )
    # Scratchpads are a migration/import spelling for the same canonical
    # public-wrapper emitter. Compatibility options no longer select a second
    # executable representation.
    migrated = workflow.copy()
    for node_id, node in migrated.nodes.items():
        if not str(node.uid or "").strip():
            node.uid = str(node_id)
    return emit_canonical_python(
        migrated,
        workflow_id=getattr(migrated, "id", None),
        source_path=source_path,
        provenance=provenance,
        template_id=workflow_id or getattr(migrated, "id", "scratchpad"),
        registered_inputs=registered_inputs,
        apply_overrides=apply_overrides,
        diagnostics=diagnostics,
    )


__all__ = [
    "emit_ready_template_python",
    "emit_canonical_python",
    "format_as_python",
    "emit_scratchpad_python",
    "emit_agent_edit_python",
    "_emit_build_function",
]
