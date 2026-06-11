from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

Severity = Literal["error", "warning", "info"]


@dataclass(frozen=True, slots=True)
class DiagnosticFinding:
    code: str
    message: str
    severity: Severity
    node_id: str | None = None
    class_type: str | None = None
    detail: dict[str, Any] | None = None

    def to_payload(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "code": self.code,
            "message": self.message,
            "severity": self.severity,
        }
        if self.node_id is not None:
            payload["node_id"] = self.node_id
        if self.class_type is not None:
            payload["class_type"] = self.class_type
        if self.detail is not None:
            payload["detail"] = self.detail
        return payload


@dataclass(frozen=True, slots=True)
class PatchSuggestion:
    name: str
    rationale: str

    def to_payload(self) -> dict[str, str]:
        return {"name": self.name, "rationale": self.rationale}


def finding_messages(findings: list[DiagnosticFinding], *, severity: Severity | None = None) -> list[str]:
    return [finding.message for finding in findings if severity is None or finding.severity == severity]


def findings_payload(findings: list[DiagnosticFinding]) -> list[dict[str, Any]]:
    return [finding.to_payload() for finding in findings]


def patch_suggestions_payload(suggestions: list[PatchSuggestion]) -> list[dict[str, str]]:
    return [suggestion.to_payload() for suggestion in suggestions]
