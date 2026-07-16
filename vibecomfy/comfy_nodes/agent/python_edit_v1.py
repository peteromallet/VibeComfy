"""Browser-free canonical Agent Edit application for Python callers."""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any

from vibecomfy.porting.edit.apply_core import apply_delta
from vibecomfy.porting.edit.ops import normalize_delta_v1, op_to_dict

from .projection_registry_v1 import (
    ROOT_SCOPE,
    projection_reference_v1,
    workflow_identity_v1,
)


PYTHON_EDIT_RESULT_V1 = "python_edit_result_v1"


def apply_delta_v1_python(
    *,
    workflow_id: str,
    graph: Mapping[str, Any],
    delta: Mapping[str, Any],
    schema_provider: Any = None,
) -> dict[str, Any]:
    """Apply explicit ``delta_v1`` to canonical UI JSON without browser globals.

    The returned value is JSON-serializable durable evidence: it binds the
    caller-supplied stable workflow UUID, root scope, the exact normalized
    operation contract, and typed structural pre/postcondition projections.
    """
    workflow_identity_v1(workflow_id)
    normalized = normalize_delta_v1(delta)
    precondition = projection_reference_v1(graph, "structural_v1")
    applied = apply_delta(
        graph,
        normalized.ops,
        schema_provider=schema_provider,
    )
    if not applied.ok or not isinstance(applied.candidate, Mapping):
        messages = [
            str(getattr(diagnostic, "message", diagnostic))
            for diagnostic in applied.diagnostics
        ]
        raise ValueError(f"delta_v1 Python apply failed: {messages[:8]!r}")
    candidate = dict(applied.candidate)
    postcondition = projection_reference_v1(candidate, "structural_v1")
    result = {
        "contract_version": PYTHON_EDIT_RESULT_V1,
        "workflow_id": workflow_id,
        "scope": dict(ROOT_SCOPE),
        "operation": {
            "delta_contract": "delta_v1",
            "wire_version": normalized.schema_version,
            "ops": [op_to_dict(op) for op in normalized.ops],
        },
        "precondition": precondition,
        "postcondition": postcondition,
        "graph": candidate,
    }
    # Enforce the public promise at the boundary rather than leaving callers to
    # discover a nested non-JSON runtime object during persistence.
    return json.loads(json.dumps(result, sort_keys=True, separators=(",", ":")))


__all__ = ["PYTHON_EDIT_RESULT_V1", "apply_delta_v1_python"]
