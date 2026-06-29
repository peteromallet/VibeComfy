from __future__ import annotations

from typing import Any, Mapping

from vibecomfy.porting.report import PortIssue
from vibecomfy.porting.resolution import ResolutionContext, to_port_issues


def _issue(
    code: str,
    message: str,
    *,
    severity: str = "error",
    detail: Mapping[str, Any] | None = None,
) -> PortIssue:
    return PortIssue(code=code, message=message, severity=severity, detail=dict(detail or {}))


_ctx = ResolutionContext()

# "unknown_target" is the generic ResolutionContext uid-not-found code; the apply
# surface has always exposed it as "unknown_node_target" to callers.
_RESOLUTION_CODE_REMAP: dict[str, str] = {"unknown_target": "unknown_node_target"}


def _endpoint_port_issues(result: Any) -> list[PortIssue]:
    """Convert ResolveResult issues for endpoint resolvers, remapping uid error codes."""
    issues = to_port_issues(result)
    return [
        _issue(
            _RESOLUTION_CODE_REMAP.get(i.code, i.code),
            i.message,
            severity=i.severity,
            detail=i.detail,
        )
        for i in issues
    ]
