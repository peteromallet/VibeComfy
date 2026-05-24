from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from vibecomfy.cli_loader import load_workflow_any
from vibecomfy.porting.lint import lint_ready_template
from vibecomfy.porting.workbench import analyze_source
from vibecomfy.schema import get_schema_provider


@dataclass(frozen=True)
class SubcheckFinding:
    severity: str
    code: str
    message: str
    line: int | None = None
    detail: dict[str, Any] = field(default_factory=dict)

    def to_json(self) -> dict[str, Any]:
        payload = {
            "severity": self.severity,
            "code": self.code,
            "message": self.message,
            "detail": self.detail,
        }
        if self.line is not None:
            payload["line"] = self.line
        return payload


@dataclass(frozen=True)
class SubcheckResult:
    name: str
    ok: bool
    findings: list[SubcheckFinding] = field(default_factory=list)

    @property
    def error_count(self) -> int:
        return sum(1 for finding in self.findings if finding.severity == "error")

    @property
    def warning_count(self) -> int:
        return sum(1 for finding in self.findings if finding.severity == "warning")

    @property
    def info_count(self) -> int:
        return sum(1 for finding in self.findings if finding.severity == "info")

    def to_json(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "ok": self.ok,
            "error_count": self.error_count,
            "warning_count": self.warning_count,
            "info_count": self.info_count,
            "findings": [finding.to_json() for finding in self.findings],
        }


@dataclass(frozen=True)
class HealthReport:
    workflow: str
    ok: bool
    subchecks: list[SubcheckResult]

    def to_json(self) -> dict[str, Any]:
        return {
            "workflow": self.workflow,
            "ok": self.ok,
            "subchecks": [subcheck.to_json() for subcheck in self.subchecks],
        }


def run_port_check(workflow: str, *, schema_provider: Any | None = None) -> SubcheckResult:
    try:
        report = analyze_source(workflow, schema_provider=schema_provider or get_schema_provider("auto"))
    except Exception as exc:
        return _exception_result("port check", exc)
    findings = [
        SubcheckFinding(
            severity=issue.severity,
            code=issue.code,
            message=issue.message,
            detail=issue.detail or {},
        )
        for issue in report.diagnostics
    ]
    return SubcheckResult(name="port check", ok=not any(f.severity == "error" for f in findings), findings=findings)


def run_port_lint(workflow: str) -> SubcheckResult:
    path = _resolve_path(workflow)
    if path is None:
        return SubcheckResult(name="port lint", ok=True, findings=[])
    try:
        diagnostics = lint_ready_template(path.read_text(encoding="utf-8"), str(path))
    except Exception as exc:
        return _exception_result("port lint", exc)
    findings = [
        SubcheckFinding(
            severity=item.severity,
            code=item.code,
            message=item.message,
            line=item.line,
            detail=item.detail or {},
        )
        for item in diagnostics
    ]
    return SubcheckResult(name="port lint", ok=not any(f.severity == "error" for f in findings), findings=findings)


def run_validate(workflow: str, *, schema_provider: Any | None = None) -> SubcheckResult:
    try:
        wf = load_workflow_any(workflow)
        report = wf.validate(schema_provider=schema_provider or get_schema_provider("auto"))
    except Exception as exc:
        return _exception_result("validate", exc)
    findings = [
        SubcheckFinding(
            severity=issue.severity,
            code=issue.code,
            message=issue.message,
            detail=issue.detail or {},
        )
        for issue in report.issues
    ]
    return SubcheckResult(name="validate", ok=report.ok, findings=findings)


def run_doctor_readiness(workflow: str) -> SubcheckResult:
    try:
        wf = load_workflow_any(workflow)
    except Exception as exc:
        return _exception_result("doctor", exc)
    findings: list[SubcheckFinding] = []
    if wf.requirements.missing_nodes:
        findings.append(
            SubcheckFinding(
                severity="error",
                code="missing_nodes",
                message="Workflow has missing custom node requirements.",
                detail={"missing_nodes": list(wf.requirements.missing_nodes)},
            )
        )
    if wf.requirements.missing_models:
        findings.append(
            SubcheckFinding(
                severity="error",
                code="missing_models",
                message="Workflow has missing model requirements.",
                detail={"missing_models": list(wf.requirements.missing_models)},
            )
        )
    if not wf.outputs:
        findings.append(SubcheckFinding(severity="warning", code="no_outputs", message="Workflow has no public outputs."))
    return SubcheckResult(name="doctor", ok=not any(f.severity == "error" for f in findings), findings=findings)


def run_health_checks(workflow: str, *, schema_provider: Any | None = None) -> HealthReport:
    provider = schema_provider or get_schema_provider("auto")
    subchecks = [
        run_port_check(workflow, schema_provider=provider),
        run_port_lint(workflow),
        run_validate(workflow, schema_provider=provider),
        run_doctor_readiness(workflow),
    ]
    return HealthReport(workflow=workflow, ok=all(item.ok for item in subchecks), subchecks=subchecks)


def _exception_result(name: str, exc: Exception) -> SubcheckResult:
    return SubcheckResult(
        name=name,
        ok=False,
        findings=[
            SubcheckFinding(
                severity="error",
                code="exception",
                message=f"{type(exc).__name__}: {exc}",
                detail={"exception_type": type(exc).__name__},
            )
        ],
    )


def _resolve_path(workflow: str) -> Path | None:
    path = Path(workflow)
    if path.is_file():
        return path
    candidate = Path(__file__).resolve().parents[2] / "ready_templates" / f"{workflow}.py"
    return candidate if candidate.is_file() else None
