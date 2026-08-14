"""Typed results returned by agent-invoked stage tools."""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Mapping

from .evidence_pack import _check_keys, _freeze_json, _required_text, _text_tuple, _thaw_json


class ToolStatus(StrEnum):
    OK = "ok"
    NO_RESULTS = "no_results"
    RATE_LIMITED = "rate_limited"
    TIMEOUT = "timeout"
    UNAVAILABLE = "unavailable"
    INVALID_REQUEST = "invalid_request"
    REFUSED = "refused"


TOOL_STATUSES = frozenset(status.value for status in ToolStatus)


def normalize_tool_status(value: Any) -> ToolStatus:
    if isinstance(value, ToolStatus):
        return value
    try:
        return ToolStatus(value)
    except (TypeError, ValueError) as exc:
        allowed = ", ".join(sorted(TOOL_STATUSES))
        raise ValueError(f"`status` must be one of: {allowed}.") from exc


@dataclass(frozen=True)
class ToolDiagnostic:
    code: str
    message: str
    details: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "code", _required_text(self.code, "code"))
        object.__setattr__(self, "message", _required_text(self.message, "message"))
        if not isinstance(self.details, Mapping):
            raise ValueError("`details` must be an object.")
        object.__setattr__(self, "details", _freeze_json(self.details, "details"))

    def to_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "message": self.message,
            "details": _thaw_json(self.details),
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "ToolDiagnostic":
        if not isinstance(payload, Mapping):
            raise ValueError("ToolDiagnostic must be an object.")
        _check_keys(
            payload,
            required=frozenset({"code", "message", "details"}),
            contract="ToolDiagnostic",
        )
        return cls(
            code=payload["code"],
            message=payload["message"],
            details=payload["details"],
        )


@dataclass(frozen=True)
class ToolResult:
    """One tool call result with transport/existence states kept distinct."""

    tool_name: str
    status: ToolStatus
    result: Any = None
    evidence_ids: tuple[str, ...] = ()
    diagnostics: tuple[ToolDiagnostic, ...] = ()
    retry_after_seconds: float | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "tool_name", _required_text(self.tool_name, "tool_name"))
        object.__setattr__(self, "status", normalize_tool_status(self.status))
        object.__setattr__(self, "result", _freeze_json(self.result, "result"))
        object.__setattr__(self, "evidence_ids", _text_tuple(self.evidence_ids, "evidence_ids"))

        if not isinstance(self.diagnostics, (list, tuple)):
            raise ValueError("`diagnostics` must be a list.")
        diagnostics = tuple(
            item if isinstance(item, ToolDiagnostic) else ToolDiagnostic.from_dict(item)
            for item in self.diagnostics
        )
        object.__setattr__(self, "diagnostics", diagnostics)

        retry_after = self.retry_after_seconds
        if retry_after is not None:
            if isinstance(retry_after, bool) or not isinstance(retry_after, (int, float)):
                raise ValueError("`retry_after_seconds` must be a non-negative number or null.")
            retry_after = float(retry_after)
            if not math.isfinite(retry_after) or retry_after < 0:
                raise ValueError("`retry_after_seconds` must be finite and non-negative.")
            if self.status is not ToolStatus.RATE_LIMITED:
                raise ValueError("`retry_after_seconds` is valid only for rate_limited results.")
        object.__setattr__(self, "retry_after_seconds", retry_after)

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "tool_name": self.tool_name,
            "status": self.status.value,
            "result": _thaw_json(self.result),
            "evidence_ids": list(self.evidence_ids),
            "diagnostics": [item.to_dict() for item in self.diagnostics],
        }
        if self.retry_after_seconds is not None:
            payload["retry_after_seconds"] = self.retry_after_seconds
        return payload

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "ToolResult":
        if not isinstance(payload, Mapping):
            raise ValueError("ToolResult must be an object.")
        _check_keys(
            payload,
            required=frozenset({"tool_name", "status", "result", "evidence_ids", "diagnostics"}),
            optional=frozenset({"retry_after_seconds"}),
            contract="ToolResult",
        )
        return cls(
            tool_name=payload["tool_name"],
            status=payload["status"],
            result=payload["result"],
            evidence_ids=payload["evidence_ids"],
            diagnostics=payload["diagnostics"],
            retry_after_seconds=payload.get("retry_after_seconds"),
        )


__all__ = [
    "TOOL_STATUSES",
    "ToolDiagnostic",
    "ToolResult",
    "ToolStatus",
    "normalize_tool_status",
]
