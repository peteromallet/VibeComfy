"""Static lowering: compile-time expansion of bounded vibecomfy.loop intent nodes.

This module provides the data model (LoweringResult, LoweringEvidence, etc.)
and loop extraction/discovery. Body-boundary discovery, cloning, and
multi-iteration substitution live in later steps of the lowering pipeline.

Design decisions (see plan_v2.md):
- Lowering is atomic: any unsupported loop fails the entire lower stage.
- Supported loops: bounded literal seed/prompt/text sweeps only.
- Unsupported: runtime-dependent counts, dynamic termination, unresolved
  variable expressions, and unsupported variable names.
"""

from __future__ import annotations

import copy
import hashlib
import json
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Mapping, Sequence

from vibecomfy.contracts.intent_nodes import (
    CLASS_TYPE_TO_KIND,
    INTENT_LOOP_MAX_ITERATIONS,
    intent_node_payload_from_metadata,
)
from vibecomfy.metadata import OUTPUT_NODE_NAMES
from vibecomfy.porting.canonical_coords import snap_pos
from vibecomfy.porting.uid import make_uid, parse_uid
from vibecomfy.workflow import ValidationIssue

if TYPE_CHECKING:
    from vibecomfy.schema.provider import SchemaProvider
    from vibecomfy.workflow import VibeNode, VibeWorkflow

# ---------------------------------------------------------------------------
# Supported variable names for this lowering slice
# ---------------------------------------------------------------------------

SUPPORTED_LOOP_VARIABLES: frozenset[str] = frozenset({"seed", "prompt", "text"})

# Fields where seed values are substituted during concretization (Step 6).
# Listed here so the extraction layer can validate them.
SEED_FIELDS: frozenset[str] = frozenset({"seed", "noise_seed"})

# Fields where prompt/text values are substituted during concretization.
TEXT_FIELDS: frozenset[str] = frozenset({"text", "prompt"})

# Horizontal stride (pixels) applied per iteration for clone layout positioning.
# Clones are placed to the right of the source node: pos_x + HORIZONTAL_STRIDE * iteration_index.
HORIZONTAL_STRIDE: int = 300

# Layout policy descriptor recorded in lowering evidence.
LAYOUT_POLICY_DESCRIPTOR: str = f"horizontal_stride_clone:offset={HORIZONTAL_STRIDE}"


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class LoweringDiagnostic:
    """A single diagnostic produced during lowering."""

    code: str
    message: str
    loop_node_id: str
    loop_uid: str | None = None
    detail: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class LoopLoweringPlan:
    """Normalized lowering plan for a single bounded loop."""

    loop_node_id: str
    loop_uid: str | None
    variable: str
    iterations: int
    over_values: tuple[Any, ...] = ()
    is_over: bool = False


@dataclass(frozen=True, slots=True)
class LoweringEvidence:
    """Per-loop evidence recorded into audit metadata."""

    loop_uid: str
    loop_node_id: str
    original_intent_hash: str
    variable: str
    iterations: int
    iteration_values: tuple[Any, ...] = ()
    lowered_node_count: int = 0
    source_to_lowered_node_map: dict[str, tuple[str, ...]] = field(default_factory=dict)
    lowered_fragment_hash: str | None = None
    layout_policy: str | None = None
    validation_result: dict[str, Any] | None = None


@dataclass(frozen=True, slots=True)
class LoweringResult:
    """Atomic outcome of the lowering stage.

    When ``ok`` is False the caller MUST NOT use the ``workflow`` or
    ``evidence`` fields — no partially lowered graph is emitted.
    """

    ok: bool
    workflow: "VibeWorkflow | None" = None
    evidence: tuple[LoweringEvidence, ...] = ()
    diagnostics: tuple[LoweringDiagnostic, ...] = ()
    lowered_count: int = 0

    @property
    def unsuccessful(self) -> bool:
        return not self.ok


@dataclass(frozen=True, slots=True)
class LoweringBoundaryInput:
    """An external edge that must be reconnected into each lowered clone."""

    source_node_id: str
    source_output: str
    target_node_id: str
    target_input: str


@dataclass(frozen=True, slots=True)
class LoweringBoundaryOutput:
    """An outgoing loop/body edge that crosses the lowered-body boundary."""

    source_node_id: str
    source_output: str
    consumer_node_id: str
    consumer_input: str
    consumer_class_type: str
    duplication_kind: str
    shared_inputs: tuple[LoweringBoundaryInput, ...] = ()


@dataclass(frozen=True, slots=True)
class LoopBodyBoundary:
    """Deterministic description of the nodes/edges affected by one loop."""

    loop_node_id: str
    loop_uid: str | None
    body_node_ids: tuple[str, ...]
    shared_inputs: tuple[LoweringBoundaryInput, ...]
    boundary_outputs: tuple[LoweringBoundaryOutput, ...]


@dataclass(frozen=True, slots=True)
class LoopTargetField:
    """A loop-driven field that must be concretized per iteration."""

    source_node_id: str
    target_field: str


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _intent_payload(node: "VibeNode") -> dict[str, Any] | None:
    """Extract the vibecomfy payload from a node's metadata."""
    return intent_node_payload_from_metadata(node.metadata)


def _hash_json(obj: Any) -> str:
    """Deterministic SHA-256 of a JSON-serializable object."""
    raw = json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(raw.encode()).hexdigest()


def _normalize_over_values(over: Sequence[Any]) -> tuple[Any, ...] | None:
    """Validate and normalize an ``intent.over`` sequence.

    Returns a tuple of values or None if any value is unsupported (non-literal).
    """
    if not isinstance(over, Sequence) or isinstance(over, (str, bytes)):
        return None
    values: list[Any] = []
    for item in over:
        if isinstance(item, (int, float, str, bool)):
            values.append(item)
        else:
            return None  # Non-literal value — unsupported
    return tuple(values)


def _validation_issue_to_dict(issue: ValidationIssue) -> dict[str, Any]:
    return {
        "code": issue.code,
        "message": issue.message,
        "severity": issue.severity,
        "detail": dict(issue.detail),
    }


def _validation_summary(issues: Sequence[ValidationIssue]) -> dict[str, Any]:
    return {
        "ok": not any(issue.severity == "error" for issue in issues),
        "issue_count": len(issues),
        "error_count": sum(1 for issue in issues if issue.severity == "error"),
        "warning_count": sum(1 for issue in issues if issue.severity != "error"),
        "issues": [_validation_issue_to_dict(issue) for issue in issues],
    }


def _validate_lowered_workflow(
    workflow: "VibeWorkflow",
    *,
    schema_provider: "SchemaProvider | None" = None,
) -> tuple[dict[str, Any], list[LoweringDiagnostic]]:
    issues = [
        issue
        for issue in workflow.validate(schema_provider=schema_provider).issues
        if issue.code != "empty_workflow"
    ]
    helper_issues = workflow.helper_diagnostics()
    if helper_issues:
        issues.extend(helper_issues)
    summary = _validation_summary(issues)
    if summary["ok"]:
        return summary, []
    diagnostics = [
        LoweringDiagnostic(
            code="lowered_copy_validation_failed",
            message=issue.message,
            loop_node_id=str(issue.detail.get("node_id") or "lowering"),
            detail={
                "validation_issue": _validation_issue_to_dict(issue),
            },
        )
        for issue in issues
        if issue.severity == "error"
    ]
    return summary, diagnostics


def _normalize_count(
    intent: Mapping[str, Any], loop_node_id: str
) -> tuple[int | None, list[LoweringDiagnostic]]:
    """Normalize count/iterations from loop intent.

    Returns (count_or_none, diagnostics). count_or_none is None when the
    bound is missing or invalid.
    """
    count = intent.get("count", intent.get("iterations"))
    if isinstance(count, bool):
        count = int(count)
    if isinstance(count, int):
        if 1 <= count <= INTENT_LOOP_MAX_ITERATIONS:
            return count, []
        return None, [
            LoweringDiagnostic(
                code="loop_bound_out_of_range",
                message=(
                    f"Loop count/iterations {count} out of range "
                    f"[1, {INTENT_LOOP_MAX_ITERATIONS}]."
                ),
                loop_node_id=loop_node_id,
                detail={"count": count, "max": INTENT_LOOP_MAX_ITERATIONS},
            )
        ]
    # count is missing or non-integer — check for "over"
    return None, []


def _node_sort_key(node_id: str) -> tuple[int, int | str, str]:
    if node_id.isdigit():
        return (0, int(node_id), node_id)
    return (1, node_id, node_id)


def _edge_sort_key(
    edge: tuple[str, str, str, str] | "LoweringBoundaryInput" | "LoweringBoundaryOutput",
) -> tuple[tuple[int, int | str, str], str, tuple[int, int | str, str], str]:
    if isinstance(edge, LoweringBoundaryOutput):
        return (
            _node_sort_key(edge.source_node_id),
            edge.source_output,
            _node_sort_key(edge.consumer_node_id),
            edge.consumer_input,
        )
    if isinstance(edge, LoweringBoundaryInput):
        return (
            _node_sort_key(edge.source_node_id),
            edge.source_output,
            _node_sort_key(edge.target_node_id),
            edge.target_input,
        )
    source_node, source_output, target_node, target_input = edge
    return (
        _node_sort_key(source_node),
        source_output,
        _node_sort_key(target_node),
        target_input,
    )


def _is_terminal_node(workflow: "VibeWorkflow", node_id: str) -> bool:
    return not any(edge.from_node == node_id for edge in workflow.edges)


def _is_duplicable_terminal_sink(workflow: "VibeWorkflow", node_id: str) -> bool:
    node = workflow.nodes[node_id]
    if node.class_type in OUTPUT_NODE_NAMES:
        return True
    return any(output.node_id == node_id for output in workflow.outputs)


def _clone_uid(loop_uid: str | None, source_uid: str, iteration_index: int) -> str:
    loop_scope, loop_local = parse_uid(loop_uid or "")
    _, source_local = parse_uid(source_uid)
    local_uid = f"{loop_local or 'loop'}:iter{iteration_index}:{source_local}"
    return make_uid(loop_scope, local_uid)


def _clone_node(
    workflow: "VibeWorkflow",
    source_node: "VibeNode",
    *,
    loop_node_id: str,
    loop_uid: str | None,
    iteration_index: int,
    clone_role: str,
    variable: str,
    iteration_value: Any,
    original_intent_hash: str,
) -> "VibeNode":
    new_id = workflow._next_node_id()
    source_uid = source_node.uid or source_node.id
    clone_uid = _clone_uid(loop_uid, source_uid, iteration_index)
    cloned_metadata = copy.deepcopy(source_node.metadata)
    cloned_metadata["vibecomfy.lowering"] = {
        "loop_node_id": loop_node_id,
        "loop_uid": loop_uid or loop_node_id,
        "source_node_id": source_node.id,
        "source_uid": source_uid,
        "iteration_index": iteration_index,
        "clone_role": clone_role,
        "variable": variable,
        "iteration_value": iteration_value,
        "original_intent_hash": original_intent_hash,
    }

    # --- Deterministic clone layout positioning ---
    # Read source node position from _ui metadata; default to (0, 0).
    source_ui = source_node.metadata.get("_ui")
    if isinstance(source_ui, dict):
        source_pos = source_ui.get("pos", [0, 0])
        source_size = source_ui.get("size")
    else:
        source_pos = [0, 0]
        source_size = None
    try:
        source_x = float(source_pos[0])
        source_y = float(source_pos[1])
    except (TypeError, IndexError, ValueError):
        source_x, source_y = 0.0, 0.0
    # Compute clone position: horizontal stride per iteration, same y.
    clone_pos = [source_x + HORIZONTAL_STRIDE * iteration_index, source_y]
    snapped_pos = snap_pos(clone_pos)
    # Ensure _ui sub-dict exists and store the snapped position.
    clone_ui: dict[str, Any] = cloned_metadata.setdefault("_ui", {})
    clone_ui["pos"] = snapped_pos
    if source_size is not None:
        try:
            clone_ui["size"] = source_size
        except (TypeError, IndexError):
            pass
    # --- End layout positioning ---

    cloned = source_node.__class__(
        id=new_id,
        class_type=source_node.class_type,
        pack=source_node.pack,
        inputs=copy.deepcopy(source_node.inputs),
        widgets=copy.deepcopy(source_node.widgets),
        metadata=cloned_metadata,
        uid=clone_uid,
        raw_widgets=copy.deepcopy(source_node.raw_widgets),
    )
    workflow.nodes[new_id] = cloned
    return cloned


def _matches_variable_target(variable: str, field: str) -> bool:
    if variable == "seed":
        return field in SEED_FIELDS
    return field in TEXT_FIELDS


def _collect_loop_target_fields(
    workflow: "VibeWorkflow",
    plan: LoopLoweringPlan,
) -> tuple[tuple[LoopTargetField, ...] | None, list[LoweringDiagnostic]]:
    diagnostics: list[LoweringDiagnostic] = []
    target_fields: list[LoopTargetField] = []
    for edge in sorted(
        (candidate for candidate in workflow.edges if candidate.from_node == plan.loop_node_id),
        key=lambda edge: _edge_sort_key((edge.from_node, edge.from_output, edge.to_node, edge.to_input)),
    ):
        if not _matches_variable_target(plan.variable, edge.to_input):
            diagnostics.append(
                LoweringDiagnostic(
                    code="unsupported_loop_target_field",
                    message=(
                        f"Loop variable {plan.variable!r} cannot be concretized into "
                        f"field {edge.to_input!r}."
                    ),
                    loop_node_id=plan.loop_node_id,
                    loop_uid=plan.loop_uid,
                    detail={"target_node_id": edge.to_node, "target_field": edge.to_input},
                )
            )
            continue
        target_fields.append(
            LoopTargetField(source_node_id=edge.to_node, target_field=edge.to_input)
        )
    if diagnostics:
        return None, diagnostics
    return tuple(target_fields), diagnostics


def _read_source_field_value(node: "VibeNode", field: str) -> Any:
    if field in node.inputs:
        return node.inputs[field]
    if field in node.widgets:
        return node.widgets[field]
    return None


def _coerce_iteration_values(
    workflow: "VibeWorkflow",
    plan: LoopLoweringPlan,
    target_fields: Sequence[LoopTargetField],
) -> tuple[tuple[Any, ...] | None, list[LoweringDiagnostic]]:
    diagnostics: list[LoweringDiagnostic] = []
    if plan.is_over:
        if plan.variable == "seed":
            if any(not isinstance(value, int) or isinstance(value, bool) for value in plan.over_values):
                diagnostics.append(
                    LoweringDiagnostic(
                        code="unsupported_seed_values",
                        message="Seed loops require integer literal iteration values.",
                        loop_node_id=plan.loop_node_id,
                        loop_uid=plan.loop_uid,
                        detail={"values": list(plan.over_values)},
                    )
                )
                return None, diagnostics
        elif any(not isinstance(value, str) for value in plan.over_values):
            diagnostics.append(
                LoweringDiagnostic(
                    code="unsupported_text_values",
                    message="Prompt/text loops require string literal iteration values.",
                    loop_node_id=plan.loop_node_id,
                    loop_uid=plan.loop_uid,
                    detail={"values": list(plan.over_values)},
                )
            )
            return None, diagnostics
        return tuple(plan.over_values), diagnostics

    if not target_fields:
        return tuple(range(plan.iterations)), diagnostics

    source_values = [
        _read_source_field_value(workflow.nodes[target.source_node_id], target.target_field)
        for target in target_fields
    ]
    exemplar = source_values[0]
    if plan.variable == "seed":
        if not isinstance(exemplar, int) or isinstance(exemplar, bool):
            diagnostics.append(
                LoweringDiagnostic(
                    code="unsupported_seed_source_value",
                    message="Seed loop lowering requires an integer source field value.",
                    loop_node_id=plan.loop_node_id,
                    loop_uid=plan.loop_uid,
                    detail={"value": exemplar},
                )
            )
            return None, diagnostics
        if any(value != exemplar for value in source_values[1:]):
            diagnostics.append(
                LoweringDiagnostic(
                    code="inconsistent_seed_source_values",
                    message="Seed loop lowering requires consistent seed source values across loop targets.",
                    loop_node_id=plan.loop_node_id,
                    loop_uid=plan.loop_uid,
                    detail={"values": source_values},
                )
            )
            return None, diagnostics
        return tuple(exemplar + offset for offset in range(plan.iterations)), diagnostics

    if not isinstance(exemplar, str):
        diagnostics.append(
            LoweringDiagnostic(
                code="unsupported_text_source_value",
                message="Prompt/text loop lowering requires a string source field value.",
                loop_node_id=plan.loop_node_id,
                loop_uid=plan.loop_uid,
                detail={"value": exemplar},
            )
        )
        return None, diagnostics
    if any(value != exemplar for value in source_values[1:]):
        diagnostics.append(
            LoweringDiagnostic(
                code="inconsistent_text_source_values",
                message=(
                    "Prompt/text loop lowering requires consistent source values "
                    "across loop targets when `intent.over` is not provided."
                ),
                loop_node_id=plan.loop_node_id,
                loop_uid=plan.loop_uid,
                detail={"values": source_values},
            )
        )
        return None, diagnostics
    return tuple(exemplar for _ in range(plan.iterations)), diagnostics


def _apply_iteration_substitutions(
    cloned: "VibeNode",
    *,
    source_node_id: str,
    target_fields: Sequence[LoopTargetField],
    iteration_value: Any,
) -> None:
    for target in target_fields:
        if target.source_node_id != source_node_id:
            continue
        if target.target_field in cloned.inputs:
            cloned.inputs[target.target_field] = iteration_value
        elif target.target_field in cloned.widgets:
            cloned.widgets[target.target_field] = iteration_value


def _emit_lowering_subgraph_definitions(
    workflow: "VibeWorkflow",
    *,
    plan: LoopLoweringPlan,
    iteration_clone_ids: list[list[str]],
    body_clone_ids_by_iteration: list[dict[str, str]],
    sink_clone_ids_by_iteration: list[dict[str, str]],
) -> None:
    """Build native subgraph definitions for lowered iteration groups.

    Each iteration becomes one subgraph entry in
    ``workflow.metadata['definitions']['subgraphs']``.  The subgraph carries
    a ``name`` like ``"Iteration 0"`` and a ``nodes`` list of minimal node
    dicts (``id``, ``type``, ``properties.vibecomfy_uid``) so that
    :func:`~vibecomfy.porting.layout.groups.build_subgraph_groups` can
    materialize visual groups in the emitted UI envelope.

    This is opt-in: the default lowering path keeps flat native emission.
    """
    subgraphs: list[dict[str, Any]] = []
    variable = plan.variable
    iteration_values = plan.over_values if plan.is_over else tuple(range(plan.iterations))

    for iter_idx, clone_ids in enumerate(iteration_clone_ids):
        iter_value = (
            iteration_values[iter_idx]
            if iter_idx < len(iteration_values)
            else iter_idx
        )
        title = f"Iteration {iter_idx}: {variable}={iter_value!r}"
        inner_nodes: list[dict[str, Any]] = []
        for clone_id in clone_ids:
            node = workflow.nodes.get(clone_id)
            if node is None:
                continue
            inner_nodes.append(
                {
                    "id": int(clone_id) if clone_id.isdigit() else clone_id,
                    "type": node.class_type,
                    "properties": {
                        "vibecomfy_uid": node.uid or clone_id,
                    },
                }
            )
        subgraphs.append(
            {
                "name": title,
                "nodes": inner_nodes,
            }
        )

    if not subgraphs:
        return

    metadata = workflow.metadata
    if not isinstance(metadata, dict):
        return
    definitions = metadata.setdefault("definitions", {})
    existing = definitions.get("subgraphs")
    if isinstance(existing, list):
        combined = list(existing) + subgraphs
    else:
        combined = subgraphs
    definitions["subgraphs"] = combined


def _lower_single_iteration(
    workflow: "VibeWorkflow",
    plan: LoopLoweringPlan,
    boundary: LoopBodyBoundary,
    *,
    iteration_values: Sequence[Any],
    original_intent_hash: str,
    target_fields: Sequence[LoopTargetField],
    emit_native_groups: bool = False,
) -> tuple[LoweringEvidence | None, list[LoweringDiagnostic]]:
    diagnostics: list[LoweringDiagnostic] = []
    body_clone_ids_by_iteration: list[dict[str, str]] = []
    sink_clone_ids_by_iteration: list[dict[str, str]] = []
    source_to_lowered: dict[str, list[str]] = {}
    iteration_clone_ids: list[list[str]] = []  # T9: per-iteration clone node ids

    sink_outputs_by_consumer: dict[str, list[LoweringBoundaryOutput]] = {}
    for boundary_output in boundary.boundary_outputs:
        sink_outputs_by_consumer.setdefault(boundary_output.consumer_node_id, []).append(
            boundary_output
        )

    internal_edges = sorted(
        (
            edge
            for edge in workflow.edges
            if edge.from_node in boundary.body_node_ids and edge.to_node in boundary.body_node_ids
        ),
        key=lambda edge: _edge_sort_key((edge.from_node, edge.from_output, edge.to_node, edge.to_input)),
    )
    lowered_node_ids: list[str] = []

    for iteration_index, iteration_value in enumerate(iteration_values):
        body_clone_ids: dict[str, str] = {}
        sink_clone_ids: dict[str, str] = {}

        for source_node_id in boundary.body_node_ids:
            source_node = workflow.nodes[source_node_id]
            cloned = _clone_node(
                workflow,
                source_node,
                loop_node_id=plan.loop_node_id,
                loop_uid=plan.loop_uid,
                iteration_index=iteration_index,
                clone_role="body",
                variable=plan.variable,
                iteration_value=iteration_value,
                original_intent_hash=original_intent_hash,
            )
            _apply_iteration_substitutions(
                cloned,
                source_node_id=source_node_id,
                target_fields=target_fields,
                iteration_value=iteration_value,
            )
            body_clone_ids[source_node_id] = cloned.id
            source_to_lowered.setdefault(source_node.uid or source_node.id, []).append(cloned.uid)
            lowered_node_ids.append(cloned.id)

        for consumer_node_id in sorted(sink_outputs_by_consumer, key=_node_sort_key):
            source_node = workflow.nodes[consumer_node_id]
            cloned = _clone_node(
                workflow,
                source_node,
                loop_node_id=plan.loop_node_id,
                loop_uid=plan.loop_uid,
                iteration_index=iteration_index,
                clone_role="terminal_sink",
                variable=plan.variable,
                iteration_value=iteration_value,
                original_intent_hash=original_intent_hash,
            )
            _apply_iteration_substitutions(
                cloned,
                source_node_id=consumer_node_id,
                target_fields=target_fields,
                iteration_value=iteration_value,
            )
            sink_clone_ids[consumer_node_id] = cloned.id
            source_to_lowered.setdefault(source_node.uid or source_node.id, []).append(cloned.uid)
            lowered_node_ids.append(cloned.id)

        body_clone_ids_by_iteration.append(body_clone_ids)
        sink_clone_ids_by_iteration.append(sink_clone_ids)

        # T9: track clone node ids for this iteration
        iter_ids: list[str] = []
        iter_ids.extend(body_clone_ids.values())
        iter_ids.extend(sink_clone_ids.values())
        iteration_clone_ids.append(iter_ids)

        for edge in internal_edges:
            workflow.connect(
                f"{body_clone_ids[edge.from_node]}.{edge.from_output}",
                f"{body_clone_ids[edge.to_node]}.{edge.to_input}",
            )

        for shared_input in boundary.shared_inputs:
            workflow.connect(
                f"{shared_input.source_node_id}.{shared_input.source_output}",
                f"{body_clone_ids[shared_input.target_node_id]}.{shared_input.target_input}",
            )

        for consumer_node_id in sorted(sink_outputs_by_consumer, key=_node_sort_key):
            sink_outputs = sink_outputs_by_consumer[consumer_node_id]
            sink_clone_id = sink_clone_ids[consumer_node_id]
            for boundary_output in sink_outputs:
                if boundary_output.source_node_id == plan.loop_node_id:
                    diagnostics.append(
                        LoweringDiagnostic(
                            code="unsupported_direct_loop_sink",
                            message=(
                                f"Loop {plan.loop_node_id!r} feeds terminal sink {consumer_node_id!r} "
                                "directly; lowering requires an explicit body node before the sink."
                            ),
                            loop_node_id=plan.loop_node_id,
                            loop_uid=plan.loop_uid,
                            detail={"consumer_node_id": consumer_node_id},
                        )
                    )
                    return None, diagnostics
                workflow.connect(
                    f"{body_clone_ids[boundary_output.source_node_id]}.{boundary_output.source_output}",
                    f"{sink_clone_id}.{boundary_output.consumer_input}",
                )
            for shared_input in sink_outputs[0].shared_inputs:
                workflow.connect(
                    f"{shared_input.source_node_id}.{shared_input.source_output}",
                    f"{sink_clone_id}.{shared_input.target_input}",
                )

    nodes_to_remove = {plan.loop_node_id, *boundary.body_node_ids, *sink_outputs_by_consumer.keys()}
    for node_id in sorted(nodes_to_remove, key=_node_sort_key):
        workflow.remove_node(node_id)
    workflow.finalize_metadata()

    # T9: Optionally build native subgraph grouping metadata for each iteration.
    if emit_native_groups:
        _emit_lowering_subgraph_definitions(
            workflow,
            plan=plan,
            iteration_clone_ids=iteration_clone_ids,
            body_clone_ids_by_iteration=body_clone_ids_by_iteration,
            sink_clone_ids_by_iteration=sink_clone_ids_by_iteration,
        )

    lowered_api = workflow.compile("api")
    lowered_fragment_hash = _hash_json(
        {
            node_id: lowered_api[node_id]
            for node_id in sorted(lowered_node_ids, key=_node_sort_key)
            if node_id in lowered_api
        }
    )
    return (
        LoweringEvidence(
            loop_uid=plan.loop_uid or plan.loop_node_id,
            loop_node_id=plan.loop_node_id,
            original_intent_hash=original_intent_hash,
            variable=plan.variable,
            iterations=plan.iterations,
            iteration_values=tuple(iteration_values),
            lowered_node_count=len(lowered_node_ids),
            source_to_lowered_node_map={
                key: tuple(values) for key, values in sorted(source_to_lowered.items())
            },
            lowered_fragment_hash=lowered_fragment_hash,
            layout_policy=LAYOUT_POLICY_DESCRIPTOR,
        ),
        diagnostics,
    )


# ---------------------------------------------------------------------------
# Loop discovery and extraction
# ---------------------------------------------------------------------------


def discover_loop_nodes(workflow: "VibeWorkflow") -> list[tuple[str, "VibeNode", dict[str, Any]]]:
    """Find all ``vibecomfy.loop`` intent nodes with valid loop payloads.

    Returns a list of ``(node_id, node, payload)`` tuples. Nodes that are
    ``vibecomfy.loop`` but have missing/invalid payloads are *not* returned
    here — they will be caught by contract validation earlier in the pipeline.
    Only nodes with ``class_type == "vibecomfy.loop"`` AND
    ``payload.kind == "loop"`` are returned.
    """
    result: list[tuple[str, "VibeNode", dict[str, Any]]] = []
    for node_id, node in workflow.nodes.items():
        if node.class_type != "vibecomfy.loop":
            continue
        payload = _intent_payload(node)
        if payload is None:
            continue
        if payload.get("kind") != CLASS_TYPE_TO_KIND.get("vibecomfy.loop", "loop"):
            continue
        result.append((node_id, node, payload))
    return result


def discover_body_boundary(
    workflow: "VibeWorkflow",
    plan: LoopLoweringPlan,
) -> tuple[LoopBodyBoundary | None, list[LoweringDiagnostic]]:
    """Discover the deterministic body/shared-input/output boundary for one loop.

    Body nodes are the non-terminal downstream nodes reached from the loop output.
    Terminal consumers are handled as boundary outputs: output/sink nodes may be
    duplicated per iteration, while all other terminal consumers are rejected.
    """

    outgoing_from_loop = sorted(
        (edge for edge in workflow.edges if edge.from_node == plan.loop_node_id),
        key=lambda edge: _edge_sort_key((edge.from_node, edge.from_output, edge.to_node, edge.to_input)),
    )
    if not outgoing_from_loop:
        return (
            LoopBodyBoundary(
                loop_node_id=plan.loop_node_id,
                loop_uid=plan.loop_uid,
                body_node_ids=(),
                shared_inputs=(),
                boundary_outputs=(),
            ),
            [],
        )

    diagnostics: list[LoweringDiagnostic] = []
    body_node_ids: set[str] = set()
    shared_inputs: dict[tuple[str, str, str, str], LoweringBoundaryInput] = {}
    boundary_outputs: dict[tuple[str, str, str, str], LoweringBoundaryOutput] = {}

    pending: list[str] = sorted({edge.to_node for edge in outgoing_from_loop}, key=_node_sort_key)

    while pending:
        node_id = pending.pop(0)
        if node_id in body_node_ids:
            continue

        incoming = sorted(
            (edge for edge in workflow.edges if edge.to_node == node_id),
            key=lambda edge: _edge_sort_key((edge.from_node, edge.from_output, edge.to_node, edge.to_input)),
        )
        varying_incoming = [
            edge
            for edge in incoming
            if edge.from_node == plan.loop_node_id or edge.from_node in body_node_ids
        ]
        if not varying_incoming:
            continue

        if _is_terminal_node(workflow, node_id):
            if not _is_duplicable_terminal_sink(workflow, node_id):
                diagnostics.append(
                    LoweringDiagnostic(
                        code="unsupported_scalar_fan_in",
                        message=(
                            f"Loop {plan.loop_node_id!r} feeds terminal non-sink node "
                            f"{node_id!r} ({workflow.nodes[node_id].class_type}); "
                            "only terminal output/sink consumers may be duplicated."
                        ),
                        loop_node_id=plan.loop_node_id,
                        loop_uid=plan.loop_uid,
                        detail={
                            "consumer_node_id": node_id,
                            "consumer_class_type": workflow.nodes[node_id].class_type,
                        },
                    )
                )
                return None, diagnostics

            sink_shared_inputs = tuple(
                LoweringBoundaryInput(
                    source_node_id=edge.from_node,
                    source_output=edge.from_output,
                    target_node_id=edge.to_node,
                    target_input=edge.to_input,
                )
                for edge in incoming
                if edge.from_node != plan.loop_node_id and edge.from_node not in body_node_ids
            )
            sink_shared_inputs = tuple(sorted(sink_shared_inputs, key=_edge_sort_key))
            for edge in varying_incoming:
                key = (edge.from_node, edge.from_output, edge.to_node, edge.to_input)
                boundary_outputs[key] = LoweringBoundaryOutput(
                    source_node_id=edge.from_node,
                    source_output=edge.from_output,
                    consumer_node_id=edge.to_node,
                    consumer_input=edge.to_input,
                    consumer_class_type=workflow.nodes[edge.to_node].class_type,
                    duplication_kind="duplicate_terminal_sink",
                    shared_inputs=sink_shared_inputs,
                )
            continue

        body_node_ids.add(node_id)

        for edge in incoming:
            if edge.from_node == plan.loop_node_id or edge.from_node in body_node_ids:
                continue
            key = (edge.from_node, edge.from_output, edge.to_node, edge.to_input)
            shared_inputs[key] = LoweringBoundaryInput(
                source_node_id=edge.from_node,
                source_output=edge.from_output,
                target_node_id=edge.to_node,
                target_input=edge.to_input,
            )

        outgoing = sorted(
            (edge for edge in workflow.edges if edge.from_node == node_id),
            key=lambda edge: _edge_sort_key((edge.from_node, edge.from_output, edge.to_node, edge.to_input)),
        )
        for edge in outgoing:
            if edge.to_node in body_node_ids:
                continue
            if edge.to_node not in pending:
                pending.append(edge.to_node)
        pending.sort(key=_node_sort_key)

    return (
        LoopBodyBoundary(
            loop_node_id=plan.loop_node_id,
            loop_uid=plan.loop_uid,
            body_node_ids=tuple(sorted(body_node_ids, key=_node_sort_key)),
            shared_inputs=tuple(sorted(shared_inputs.values(), key=_edge_sort_key)),
            boundary_outputs=tuple(sorted(boundary_outputs.values(), key=_edge_sort_key)),
        ),
        diagnostics,
    )


def extract_loop_plan(
    node_id: str,
    node: "VibeNode",
    payload: dict[str, Any],
) -> tuple[LoopLoweringPlan | None, list[LoweringDiagnostic]]:
    """Parse a single loop node into a normalized ``LoopLoweringPlan``.

    ``payload`` is the ``vibecomfy`` sub-dict (as returned by
    ``intent_node_payload_from_metadata``), which contains ``kind``,
    ``intent``, and ``io`` keys.

    Returns ``(plan, diagnostics)``. If ``plan`` is None, the loop cannot be
    lowered and ``diagnostics`` explains why.
    """
    diagnostics: list[LoweringDiagnostic] = []

    # --- Intent sub-dict ---
    intent = payload.get("intent")
    if not isinstance(intent, Mapping):
        return None, [
            LoweringDiagnostic(
                code="missing_loop_intent",
                message="Loop payload is missing `intent`.",
                loop_node_id=node_id,
                loop_uid=node.uid or None,
            )
        ]

    # --- Variable name ---
    var = intent.get("var")
    if not isinstance(var, str) or not var.strip():
        return None, [
            LoweringDiagnostic(
                code="missing_loop_var",
                message="Loop intent is missing a non-empty `var`.",
                loop_node_id=node_id,
                loop_uid=node.uid or None,
            )
        ]
    var = var.strip()

    if var not in SUPPORTED_LOOP_VARIABLES:
        return None, [
            LoweringDiagnostic(
                code="unsupported_loop_variable",
                message=(
                    f"Loop variable {var!r} is not supported for static lowering. "
                    f"Supported variables: {sorted(SUPPORTED_LOOP_VARIABLES)}."
                ),
                loop_node_id=node_id,
                loop_uid=node.uid or None,
                detail={
                    "variable": var,
                    "supported": sorted(SUPPORTED_LOOP_VARIABLES),
                },
            )
        ]

    # --- Determine iteration count / over values ---
    over = intent.get("over")

    if over is not None:
        # "over" takes precedence
        values = _normalize_over_values(over)
        if values is None:
            return None, [
                LoweringDiagnostic(
                    code="unsupported_over_values",
                    message=(
                        "Loop `intent.over` contains non-literal values that "
                        "cannot be statically lowered."
                    ),
                    loop_node_id=node_id,
                    loop_uid=node.uid or None,
                    detail={"over": list(over) if isinstance(over, (list, tuple)) else str(over)},
                )
            ]
        if len(values) < 1:
            return None, [
                LoweringDiagnostic(
                    code="empty_over_sequence",
                    message="Loop `intent.over` must contain at least one value.",
                    loop_node_id=node_id,
                    loop_uid=node.uid or None,
                )
            ]
        if len(values) > INTENT_LOOP_MAX_ITERATIONS:
            return None, [
                LoweringDiagnostic(
                    code="loop_bound_out_of_range",
                    message=(
                        f"Loop `intent.over` length {len(values)} exceeds "
                        f"max {INTENT_LOOP_MAX_ITERATIONS}."
                    ),
                    loop_node_id=node_id,
                    loop_uid=node.uid or None,
                    detail={
                        "count": len(values),
                        "max": INTENT_LOOP_MAX_ITERATIONS,
                    },
                )
            ]
        return LoopLoweringPlan(
            loop_node_id=node_id,
            loop_uid=node.uid or None,
            variable=var,
            iterations=len(values),
            over_values=values,
            is_over=True,
        ), diagnostics

    # "count" / "iterations" path
    count, count_diagnostics = _normalize_count(intent, node_id)
    diagnostics.extend(count_diagnostics)
    if count is None:
        if not count_diagnostics:
            diagnostics.append(
                LoweringDiagnostic(
                    code="missing_loop_bound",
                    message=(
                        "Loop intent must declare `intent.count`, "
                        "`intent.iterations`, or a bounded `intent.over` sequence."
                    ),
                    loop_node_id=node_id,
                    loop_uid=node.uid or None,
                )
            )
        return None, diagnostics

    return LoopLoweringPlan(
        loop_node_id=node_id,
        loop_uid=node.uid or None,
        variable=var,
        iterations=count,
        over_values=(),
        is_over=False,
    ), diagnostics


def lower_workflow(
    workflow: "VibeWorkflow",
    *,
    schema_provider: "SchemaProvider | None" = None,
    emit_native_groups: bool = False,
) -> LoweringResult:
    """Entry point: attempt to lower all loop nodes in a workflow.

    This is the atomic lowering entry point. If any loop node is unsupported,
    the entire result is unsuccessful and no workflow mutation is performed.

    Lowering expands each supported loop into repeated native graph structure on
    a cloned workflow. Any unsupported loop or concretization shape fails the
    entire lowering stage; partial lowered output is never emitted.

    When *emit_native_groups* is ``True``, the lowered workflow carries
    subgraph definitions in ``metadata['definitions']['subgraphs']`` so
    that :func:`~vibecomfy.porting.layout.groups.build_subgraph_groups`
    can materialize per-iteration visual groups.  Default (``False``) keeps
    flat native emission unchanged.

    The sole production caller is
    :mod:`vibecomfy.comfy_nodes.agent_edit` (``agent_edit.py:3147``).
    """
    loop_nodes = discover_loop_nodes(workflow)

    if not loop_nodes:
        return LoweringResult(
            ok=True,
            workflow=workflow,
            evidence=(),
            diagnostics=(),
            lowered_count=0,
        )

    plans: list[LoopLoweringPlan] = []
    plan_payloads: dict[str, dict[str, Any]] = {}
    all_diagnostics: list[LoweringDiagnostic] = []

    for node_id, node, payload in loop_nodes:
        plan, plan_diagnostics = extract_loop_plan(node_id, node, payload)
        all_diagnostics.extend(plan_diagnostics)
        if plan is not None:
            plans.append(plan)
            plan_payloads[node_id] = payload
        else:
            # Any failed plan makes the whole result unsuccessful
            return LoweringResult(
                ok=False,
                workflow=None,
                evidence=(),
                diagnostics=tuple(all_diagnostics),
                lowered_count=0,
            )

    lowered_workflow = workflow.clone()

    evidence: list[LoweringEvidence] = []
    for plan in plans:
        target_fields, target_field_diagnostics = _collect_loop_target_fields(lowered_workflow, plan)
        all_diagnostics.extend(target_field_diagnostics)
        if target_fields is None:
            return LoweringResult(
                ok=False,
                workflow=None,
                evidence=(),
                diagnostics=tuple(all_diagnostics),
                lowered_count=0,
            )
        iteration_values, iteration_value_diagnostics = _coerce_iteration_values(
            lowered_workflow, plan, target_fields
        )
        all_diagnostics.extend(iteration_value_diagnostics)
        if iteration_values is None:
            return LoweringResult(
                ok=False,
                workflow=None,
                evidence=(),
                diagnostics=tuple(all_diagnostics),
                lowered_count=0,
            )
        boundary, boundary_diagnostics = discover_body_boundary(lowered_workflow, plan)
        all_diagnostics.extend(boundary_diagnostics)
        if boundary is None:
            return LoweringResult(
                ok=False,
                workflow=None,
                evidence=(),
                diagnostics=tuple(all_diagnostics),
                lowered_count=0,
            )
        original_intent_hash = _hash_json(plan_payloads[plan.loop_node_id].get("intent"))
        loop_evidence, lowering_diagnostics = _lower_single_iteration(
            lowered_workflow,
            plan,
            boundary,
            iteration_values=iteration_values,
            original_intent_hash=original_intent_hash,
            target_fields=target_fields,
            emit_native_groups=emit_native_groups,
        )
        all_diagnostics.extend(lowering_diagnostics)
        if loop_evidence is None:
            return LoweringResult(
                ok=False,
                workflow=None,
                evidence=(),
                diagnostics=tuple(all_diagnostics),
                lowered_count=0,
            )
        evidence.append(loop_evidence)

    validation_result, validation_diagnostics = _validate_lowered_workflow(
        lowered_workflow,
        schema_provider=schema_provider,
    )
    evidence = [
        LoweringEvidence(
            loop_uid=item.loop_uid,
            loop_node_id=item.loop_node_id,
            original_intent_hash=item.original_intent_hash,
            variable=item.variable,
            iterations=item.iterations,
            iteration_values=item.iteration_values,
            lowered_node_count=item.lowered_node_count,
            source_to_lowered_node_map=dict(item.source_to_lowered_node_map),
            lowered_fragment_hash=item.lowered_fragment_hash,
            layout_policy=item.layout_policy,
            validation_result=copy.deepcopy(validation_result),
        )
        for item in evidence
    ]
    all_diagnostics.extend(validation_diagnostics)
    if validation_diagnostics:
        return LoweringResult(
            ok=False,
            workflow=None,
            evidence=(),
            diagnostics=tuple(all_diagnostics),
            lowered_count=0,
        )

    return LoweringResult(
        ok=True,
        workflow=lowered_workflow,
        evidence=tuple(evidence),
        diagnostics=tuple(all_diagnostics),
        lowered_count=len(plans),
    )


__all__ = [
    "HORIZONTAL_STRIDE",
    "INTENT_LOOP_MAX_ITERATIONS",
    "LAYOUT_POLICY_DESCRIPTOR",
    "LoopBodyBoundary",
    "LoweringBoundaryInput",
    "LoweringBoundaryOutput",
    "LoopLoweringPlan",
    "LoweringDiagnostic",
    "LoweringEvidence",
    "LoweringResult",
    "SEED_FIELDS",
    "SUPPORTED_LOOP_VARIABLES",
    "TEXT_FIELDS",
    "discover_body_boundary",
    "discover_loop_nodes",
    "extract_loop_plan",
    "lower_workflow",
]
