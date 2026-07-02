from __future__ import annotations

from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any, Literal, Mapping

DiagnosticSeverity = Literal["error", "warning", "info"]

DIAGNOSTIC_SEVERITY_ERROR: DiagnosticSeverity = "error"
DIAGNOSTIC_SEVERITY_WARNING: DiagnosticSeverity = "warning"
DIAGNOSTIC_SEVERITY_INFO: DiagnosticSeverity = "info"
DIAGNOSTIC_SEVERITIES: frozenset[DiagnosticSeverity] = frozenset(
    {
        DIAGNOSTIC_SEVERITY_ERROR,
        DIAGNOSTIC_SEVERITY_WARNING,
        DIAGNOSTIC_SEVERITY_INFO,
    }
)


def _freeze_detail(detail: Mapping[str, Any] | None) -> Mapping[str, Any]:
    if detail is None:
        return MappingProxyType({})
    return MappingProxyType({str(key): value for key, value in detail.items()})


@dataclass(frozen=True, slots=True)
class ReorganiseDiagnostic:
    """Machine-assertable diagnostic emitted by reorganise foundation modules."""

    code: str
    message: str
    severity: DiagnosticSeverity = DIAGNOSTIC_SEVERITY_ERROR
    path: tuple[str | int, ...] = ()
    detail: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.severity not in DIAGNOSTIC_SEVERITIES:
            raise ValueError(f"unknown diagnostic severity: {self.severity!r}")
        object.__setattr__(self, "path", tuple(self.path))
        object.__setattr__(self, "detail", _freeze_detail(self.detail))

    def to_json(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "code": self.code,
            "message": self.message,
            "severity": self.severity,
        }
        if self.path:
            payload["path"] = list(self.path)
        if self.detail:
            payload["detail"] = dict(self.detail)
        return payload


@dataclass(frozen=True, slots=True)
class ReorganiseDiagnosticReport:
    """Deterministically ordered collection of reorganise diagnostics."""

    ok: bool
    diagnostics: tuple[ReorganiseDiagnostic, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "diagnostics", tuple(self.diagnostics))

    @property
    def errors(self) -> tuple[ReorganiseDiagnostic, ...]:
        return tuple(
            diagnostic
            for diagnostic in self.diagnostics
            if diagnostic.severity == DIAGNOSTIC_SEVERITY_ERROR
        )

    def to_json(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "diagnostics": [diagnostic.to_json() for diagnostic in self.diagnostics],
        }


__all__ = [
    "DIAGNOSTIC_SEVERITIES",
    "DIAGNOSTIC_SEVERITY_ERROR",
    "DIAGNOSTIC_SEVERITY_INFO",
    "DIAGNOSTIC_SEVERITY_WARNING",
    "DiagnosticSeverity",
    "ReorganiseDiagnostic",
    "ReorganiseDiagnosticReport",
]
