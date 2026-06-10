from __future__ import annotations

from typing import Any


class Diagnostic:
    """Shared base for all diagnostic/issue types across the codebase.

    ``ValidationIssue`` (ir/types.py), ``ContractIssue`` (contracts/validation.py),
    and ``NodeCallValidationIssue`` (schema/call_validation.py) all inherit from
    this base so that downstream tooling can treat them polymorphically.

    This is intentionally a plain class (not a dataclass) so that children can
    independently choose ``frozen`` and ``slots`` without hitting the dataclass
    inheritance constraint that requires all classes in the hierarchy to agree
    on these flags.
    """

    __slots__ = ("code", "message", "severity", "detail")

    def __init__(
        self,
        code: str,
        message: str,
        severity: str = "error",
        detail: dict[str, Any] | None = None,
    ) -> None:
        self.code = code
        self.message = message
        self.severity = severity
        self.detail = detail if detail is not None else {}

    def to_json(self) -> dict[str, Any]:
        """Project shared fields to a JSON-safe dict.

        Subclasses that add extra fields (e.g. ``input``) should call this via
        ``Diagnostic.to_json(self)`` and merge their own additions.

        We call the base explicitly (``Diagnostic.to_json(self)``) rather than
        via ``super()`` because ``@dataclass(slots=True)`` replaces the class
        dict in a way that can break ``super()`` resolution in Python 3.11/3.12.
        """
        return {
            "code": self.code,
            "message": self.message,
            "severity": self.severity,
            "detail": dict(self.detail),
        }
