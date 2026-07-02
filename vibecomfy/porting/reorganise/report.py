from __future__ import annotations

from typing import Iterable, Sequence

from .diagnostics import ReorganiseDiagnostic, ReorganiseDiagnosticReport
from .plan_types import AssessmentIssue, AssessmentMetric, AssessmentReport

ASSESSMENT_VERDICT_OK = "ok"
ASSESSMENT_VERDICT_NEEDS_REORGANISE = "needs_reorganise"
ASSESSMENT_VERDICT_BLOCKED = "blocked"

_SEVERITY_ORDER = {"error": 0, "warning": 1, "info": 2}


def issue_to_diagnostic(issue: AssessmentIssue) -> ReorganiseDiagnostic:
    return ReorganiseDiagnostic(
        code=issue.code,
        message=issue.message,
        severity=issue.severity,
        detail=issue.detail,
    )


def ordered_assessment_metrics(
    metrics: Iterable[AssessmentMetric],
    *,
    preferred_order: Sequence[str] = (),
) -> tuple[AssessmentMetric, ...]:
    order = {name: index for index, name in enumerate(preferred_order)}
    return tuple(
        sorted(
            metrics,
            key=lambda metric: (
                order.get(metric.name, len(order)),
                metric.name,
                str(metric.value),
            ),
        )
    )


def ordered_assessment_issues(
    issues: Iterable[AssessmentIssue],
    *,
    preferred_order: Sequence[str] = (),
) -> tuple[AssessmentIssue, ...]:
    order = {code: index for index, code in enumerate(preferred_order)}
    return tuple(
        sorted(
            issues,
            key=lambda issue: (
                order.get(issue.code, len(order)),
                _SEVERITY_ORDER.get(issue.severity, 99),
                tuple(ref.to_json() for ref in issue.refs),
                issue.code,
                issue.message,
            ),
        )
    )


def build_assessment_report(
    *,
    metrics: Iterable[AssessmentMetric],
    issues: Iterable[AssessmentIssue],
    diagnostics: Iterable[ReorganiseDiagnostic] = (),
    metric_order: Sequence[str] = (),
    issue_order: Sequence[str] = (),
) -> AssessmentReport:
    ordered_metrics = ordered_assessment_metrics(metrics, preferred_order=metric_order)
    ordered_issues = ordered_assessment_issues(issues, preferred_order=issue_order)
    issue_diagnostics = tuple(issue_to_diagnostic(issue) for issue in ordered_issues)
    ordered_diagnostics = tuple(
        sorted(
            (*tuple(diagnostics), *issue_diagnostics),
            key=lambda diagnostic: (
                _SEVERITY_ORDER.get(diagnostic.severity, 99),
                diagnostic.code,
                tuple(diagnostic.path),
                str(dict(diagnostic.detail)),
            ),
        )
    )
    verdict = (
        ASSESSMENT_VERDICT_BLOCKED
        if any(diagnostic.severity == "error" for diagnostic in ordered_diagnostics)
        else ASSESSMENT_VERDICT_NEEDS_REORGANISE
        if ordered_issues
        else ASSESSMENT_VERDICT_OK
    )
    return AssessmentReport(
        verdict=verdict,
        metrics=ordered_metrics,
        issues=ordered_issues,
        diagnostics=ordered_diagnostics,
    )


def diagnostic_report_from_assessment(report: AssessmentReport) -> ReorganiseDiagnosticReport:
    return ReorganiseDiagnosticReport(
        ok=report.verdict == ASSESSMENT_VERDICT_OK,
        diagnostics=report.diagnostics,
    )


__all__ = [
    "ASSESSMENT_VERDICT_BLOCKED",
    "ASSESSMENT_VERDICT_NEEDS_REORGANISE",
    "ASSESSMENT_VERDICT_OK",
    "build_assessment_report",
    "diagnostic_report_from_assessment",
    "issue_to_diagnostic",
    "ordered_assessment_issues",
    "ordered_assessment_metrics",
]
