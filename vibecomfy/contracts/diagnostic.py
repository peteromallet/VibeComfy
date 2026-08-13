from __future__ import annotations

from typing import Any, Protocol


class DiagnosticLike(Protocol):
    """Structural protocol for the four shared diagnostic fields.

    Any object exposing read-only ``code``, ``message``, ``severity``, and
    ``detail`` members is compatible, regardless of its concrete type — it does
    not need to inherit from :class:`Diagnostic`.  ``to_json`` is deliberately
    NOT part of this surface: serialization is a concrete-type concern.

    Intentionally not ``@runtime_checkable``: ``isinstance`` checks are
    meaningless for a duck-typed surface, so consumers should rely on static
    typing (or explicit field access) instead.
    """

    @property
    def code(self) -> str: ...

    @property
    def message(self) -> str: ...

    @property
    def severity(self) -> str: ...

    @property
    def detail(self) -> dict[str, Any]: ...


class Diagnostic:
    """Shared base for diagnostic/issue types across the codebase.

    ``Diagnostic`` is the canonical four-field diagnostic carrier (``code``,
    ``message``, ``severity``, ``detail``) with a ``to_json()`` serializer.

    Concrete diagnostic types elsewhere (e.g. ``ContractIssue`` in
    ``contracts/validation.py``, ``NodeCallValidationIssue`` in
    ``schema/call_validation.py``) may subclass it so downstream tooling can
    treat them polymorphically, or may stay standalone dataclasses that merely
    satisfy the structural :class:`DiagnosticLike` surface.

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
