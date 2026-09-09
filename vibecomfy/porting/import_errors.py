"""Small, source-only diagnostics for workflow import failures.

These diagnostics deliberately do not attempt to repair a ComfyUI UI graph.
In particular, native recursive subgraph boundary markers are meaningful only
after ComfyUI (or an author supplied Python boundary contract) has resolved
them.  Keeping this classification separate lets CLI callers report a useful
next step without turning an unsupported source into a runnable candidate.
"""
from __future__ import annotations

from typing import Any


NATIVE_BOUNDARY_CODE = "unsupported_boundary_encoding"


def native_boundary_recovery(exc: BaseException, source: str) -> dict[str, Any] | None:
    """Return structured recovery guidance for the native boundary failure."""
    message = str(exc)
    if not message.startswith(f"{NATIVE_BOUNDARY_CODE}:"):
        return None
    return {
        "code": NATIVE_BOUNDARY_CODE,
        "source": source,
        "message": message,
        "recovery": {
            "inspect_source": (
                "Open the graph in ComfyUI and export a graph with its recursive "
                "component boundaries resolved, or author explicit Python-owned "
                "interfaces and boundary_ports."
            ),
            "port_after_resolution": f"vibecomfy port check {source} --json",
            "materialize_after_resolution": (
                f"vibecomfy port convert {source} --out out/scratchpads/<name>.py --json"
            ),
            "validate_candidate": "vibecomfy validate out/scratchpads/<name>.py",
        },
        "candidate_status": "not_materialized",
    }
