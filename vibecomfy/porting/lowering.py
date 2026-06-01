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

import hashlib
import json
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Mapping, Sequence

from vibecomfy.contracts.intent_nodes import (
    CLASS_TYPE_TO_KIND,
    INTENT_LOOP_MAX_ITERATIONS,
    intent_node_payload_from_metadata,
)

if TYPE_CHECKING:
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
    lowered_node_count: int = 0
    source_to_lowered_node_map: dict[str, str] = field(default_factory=dict)
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


def lower_workflow(workflow: "VibeWorkflow") -> LoweringResult:
    """Entry point: attempt to lower all loop nodes in a workflow.

    This is the atomic lowering entry point. If any loop node is unsupported,
    the entire result is unsuccessful and no workflow mutation is performed.

    For the T3 slice this only discovers loop nodes and plans their lowering.
    Actual graph mutation (cloning, body-boundary, substitution) happens in
    T4–T6.
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
    all_diagnostics: list[LoweringDiagnostic] = []

    for node_id, node, payload in loop_nodes:
        plan, plan_diagnostics = extract_loop_plan(node_id, node, payload)
        all_diagnostics.extend(plan_diagnostics)
        if plan is not None:
            plans.append(plan)
        else:
            # Any failed plan makes the whole result unsuccessful
            return LoweringResult(
                ok=False,
                workflow=None,
                evidence=(),
                diagnostics=tuple(all_diagnostics),
                lowered_count=0,
            )

    # For T3, we only produce the plans and evidence without mutating the graph.
    # Full lowering with graph mutation is deferred to T4–T6.
    evidence: list[LoweringEvidence] = []
    for plan in plans:
        intent_hash = _hash_json(
            {
                "loop_node_id": plan.loop_node_id,
                "variable": plan.variable,
                "iterations": plan.iterations,
                "over_values": list(plan.over_values) if plan.is_over else None,
            }
        )
        evidence.append(
            LoweringEvidence(
                loop_uid=plan.loop_uid or plan.loop_node_id,
                loop_node_id=plan.loop_node_id,
                original_intent_hash=intent_hash,
                variable=plan.variable,
                iterations=plan.iterations,
                lowered_node_count=0,  # Filled in T5/T6
            )
        )

    return LoweringResult(
        ok=True,
        workflow=workflow,
        evidence=tuple(evidence),
        diagnostics=tuple(all_diagnostics),
        lowered_count=len(plans),
    )


__all__ = [
    "INTENT_LOOP_MAX_ITERATIONS",
    "LoopLoweringPlan",
    "LoweringDiagnostic",
    "LoweringEvidence",
    "LoweringResult",
    "SEED_FIELDS",
    "SUPPORTED_LOOP_VARIABLES",
    "TEXT_FIELDS",
    "discover_loop_nodes",
    "extract_loop_plan",
    "lower_workflow",
]
