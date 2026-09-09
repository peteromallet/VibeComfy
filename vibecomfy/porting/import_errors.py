"""Structured diagnostics for source workflow import barriers."""
from __future__ import annotations

from typing import Any

NATIVE_BOUNDARY_CODE = "unsupported_boundary_encoding"


def native_boundary_recovery(exc: BaseException, source: str) -> dict[str, Any] | None:
    """Describe the supported recovery path without rewriting native boundaries."""
    message = str(exc)
    if not message.startswith(f"{NATIVE_BOUNDARY_CODE}:"):
        return None
    return {
        "code": NATIVE_BOUNDARY_CODE,
        "source": source,
        "message": message,
        "recovery": {
            "inspect_source": (
                "Open the graph in ComfyUI and export it with recursive component boundaries resolved, "
                "or author explicit Python-owned interfaces and boundary_ports."
            ),
            "port_after_resolution": f"vibecomfy port check {source} --json",
            "materialize_after_resolution": (
                f"vibecomfy port convert {source} --out out/scratchpads/<name>.py --json"
            ),
            "validate_candidate": "vibecomfy validate out/scratchpads/<name>.py",
        },
        "candidate_status": "not_materialized",
    }
