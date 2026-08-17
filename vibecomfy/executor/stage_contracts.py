"""Typed requests and packages for the agent-judgment stage pipeline."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Mapping

from .evidence_pack import (
    EvidenceArtifact,
    EvidenceLedger,
    _check_keys,
    _freeze_json,
    _required_text,
    _text_tuple,
    _thaw_json,
    normalize_artifacts,
)
from .tool_contracts import ToolStatus, normalize_tool_status

# Batch 14: typed ResearchAttempt vocabulary (mirrors
# ``agent_research_stage.RESEARCH_ATTEMPTS``; kept local so this low-level
# contract module never imports the research stage).  An unknown value fails
# safe to ``never``.
_RESEARCH_ATTEMPTS = frozenset({"never", "empty", "thin", "grounded"})


def _canonical_timestamp(value: Any) -> str:
    text = _required_text(value, "produced_at")
    candidate = text[:-1] + "+00:00" if text.endswith("Z") else text
    try:
        parsed = datetime.fromisoformat(candidate)
    except ValueError as exc:
        raise ValueError("`produced_at` must be an ISO-8601 timestamp.") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("`produced_at` must include a timezone offset.")
    utc = parsed.astimezone(timezone.utc)
    rendered = utc.isoformat(timespec="microseconds" if utc.microsecond else "seconds")
    return rendered.replace("+00:00", "Z")


@dataclass(frozen=True)
class StageDiagnostic:
    """Structured stage diagnostic; evidence references must resolve locally."""

    code: str
    message: str
    severity: str = "error"
    evidence_ids: tuple[str, ...] = ()
    details: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "code", _required_text(self.code, "code"))
        object.__setattr__(self, "message", _required_text(self.message, "message"))
        severity = _required_text(self.severity, "severity")
        if severity not in {"info", "warning", "error"}:
            raise ValueError("`severity` must be info, warning, or error.")
        object.__setattr__(self, "severity", severity)
        object.__setattr__(self, "evidence_ids", _text_tuple(self.evidence_ids, "evidence_ids"))
        if not isinstance(self.details, Mapping):
            raise ValueError("`details` must be an object.")
        object.__setattr__(self, "details", _freeze_json(self.details, "details"))

    def to_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "message": self.message,
            "severity": self.severity,
            "evidence_ids": list(self.evidence_ids),
            "details": _thaw_json(self.details),
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "StageDiagnostic":
        if not isinstance(payload, Mapping):
            raise ValueError("StageDiagnostic must be an object.")
        _check_keys(
            payload,
            required=frozenset({"code", "message", "severity", "evidence_ids", "details"}),
            contract="StageDiagnostic",
        )
        return cls(
            code=payload["code"],
            message=payload["message"],
            severity=payload["severity"],
            evidence_ids=payload["evidence_ids"],
            details=payload["details"],
        )


@dataclass(frozen=True)
class NeedsInput:
    """Decision-critical clarification authored by an agent stage."""

    decision: str
    question: str
    missing_information: tuple[str, ...]
    evidence_ids: tuple[str, ...] = ()
    options: tuple[str, ...] = ()
    bounded_assumption: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "decision", _required_text(self.decision, "decision"))
        object.__setattr__(self, "question", _required_text(self.question, "question"))
        missing = _text_tuple(self.missing_information, "missing_information")
        if not missing:
            missing = (self.question,)
        object.__setattr__(self, "missing_information", missing)
        object.__setattr__(self, "evidence_ids", _text_tuple(self.evidence_ids, "evidence_ids"))
        object.__setattr__(self, "options", _text_tuple(self.options, "options"))
        if self.bounded_assumption is not None:
            object.__setattr__(
                self,
                "bounded_assumption",
                _required_text(self.bounded_assumption, "bounded_assumption"),
            )

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "decision": self.decision,
            "question": self.question,
            "missing_information": list(self.missing_information),
            "evidence_ids": list(self.evidence_ids),
            "options": list(self.options),
        }
        if self.bounded_assumption is not None:
            payload["bounded_assumption"] = self.bounded_assumption
        return payload

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "NeedsInput":
        if not isinstance(payload, Mapping):
            raise ValueError("NeedsInput must be an object.")
        _check_keys(
            payload,
            required=frozenset({"question"}),
            optional=frozenset({
                "decision",
                "missing_information",
                "evidence_ids",
                "options",
                "bounded_assumption",
            }),
            contract="NeedsInput",
        )
        question = payload["question"]
        missing = payload.get("missing_information")
        if not missing:
            missing = (str(question),)
        return cls(
            decision=payload.get("decision") or "clarify",
            question=question,
            missing_information=missing,
            evidence_ids=payload.get("evidence_ids") or (),
            options=payload.get("options") or (),
            bounded_assumption=payload.get("bounded_assumption"),
        )


@dataclass(frozen=True)
class StagePackage:
    """Validated envelope handed from one stage to the next.

    ``research_attempt`` (research stage only) carries the batch-14 typed
    attempt semantics (never/empty/thin/grounded) derived from the research
    tool ledger — Python-derived, never model judgment.  It is optional and
    fails safe to ``never`` when absent (a package that does not declare
    evidence must not gate an implement on it).
    """

    stage_id: str
    produced_at: str
    artifacts: Mapping[str, EvidenceArtifact]
    diagnostics: tuple[StageDiagnostic, ...]
    status: ToolStatus
    next_stage_hints: tuple[str, ...]
    ledger: EvidenceLedger = field(default_factory=EvidenceLedger)
    needs_input: NeedsInput | None = None
    research_attempt: str = "never"

    def __post_init__(self) -> None:
        object.__setattr__(self, "stage_id", _required_text(self.stage_id, "stage_id"))
        object.__setattr__(self, "produced_at", _canonical_timestamp(self.produced_at))
        artifacts = normalize_artifacts(self.artifacts)
        object.__setattr__(self, "artifacts", artifacts)

        if not isinstance(self.diagnostics, (list, tuple)):
            raise ValueError("`diagnostics` must be a list.")
        diagnostics = tuple(
            item if isinstance(item, StageDiagnostic) else StageDiagnostic.from_dict(item)
            for item in self.diagnostics
        )
        object.__setattr__(self, "diagnostics", diagnostics)
        object.__setattr__(self, "status", normalize_tool_status(self.status))
        object.__setattr__(
            self,
            "next_stage_hints",
            _text_tuple(self.next_stage_hints, "next_stage_hints"),
        )
        ledger = (
            self.ledger
            if isinstance(self.ledger, EvidenceLedger)
            else EvidenceLedger.from_dict(self.ledger)
        )
        object.__setattr__(self, "ledger", ledger)
        needs_input = self.needs_input
        if needs_input is not None and not isinstance(needs_input, NeedsInput):
            needs_input = NeedsInput.from_dict(needs_input)
        object.__setattr__(self, "needs_input", needs_input)
        attempt = str(self.research_attempt or "").strip()
        if attempt not in _RESEARCH_ATTEMPTS:
            attempt = "never"
        object.__setattr__(self, "research_attempt", attempt)

        referenced_ids = set(ledger.evidence_ids)
        for diagnostic in diagnostics:
            referenced_ids.update(diagnostic.evidence_ids)
        if needs_input is not None:
            referenced_ids.update(needs_input.evidence_ids)
        unresolved = sorted(referenced_ids - set(artifacts))
        if unresolved:
            raise ValueError(
                "StagePackage contains unresolved evidence ID(s): "
                + ", ".join(unresolved)
                + "."
            )

    @property
    def evidence_ids(self) -> tuple[str, ...]:
        return tuple(self.artifacts)

    def to_dict(self) -> dict[str, Any]:
        return {
            "stage_id": self.stage_id,
            "produced_at": self.produced_at,
            "artifacts": {
                evidence_id: artifact.to_dict()
                for evidence_id, artifact in self.artifacts.items()
            },
            "diagnostics": [diagnostic.to_dict() for diagnostic in self.diagnostics],
            "status": self.status.value,
            "next_stage_hints": list(self.next_stage_hints),
            "ledger": self.ledger.to_dict(),
            "needs_input": self.needs_input.to_dict() if self.needs_input is not None else None,
            "research_attempt": self.research_attempt,
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "StagePackage":
        if not isinstance(payload, Mapping):
            raise ValueError("StagePackage must be an object.")
        _check_keys(
            payload,
            required=frozenset({
                "stage_id",
                "produced_at",
                "artifacts",
                "diagnostics",
                "status",
                "next_stage_hints",
                "ledger",
                "needs_input",
            }),
            optional=frozenset({"research_attempt"}),
            contract="StagePackage",
        )
        needs_input = payload["needs_input"]
        return cls(
            stage_id=payload["stage_id"],
            produced_at=payload["produced_at"],
            artifacts=payload["artifacts"],
            diagnostics=payload["diagnostics"],
            status=payload["status"],
            next_stage_hints=payload["next_stage_hints"],
            ledger=EvidenceLedger.from_dict(payload["ledger"]),
            needs_input=NeedsInput.from_dict(needs_input) if needs_input is not None else None,
            research_attempt=payload.get("research_attempt", "never"),
        )


__all__ = [
    "NeedsInput",
    "StageDiagnostic",
    "StagePackage",
]
