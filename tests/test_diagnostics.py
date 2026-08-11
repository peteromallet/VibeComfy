from __future__ import annotations

from typing import Any

import pytest

from vibecomfy.diagnostics import (
    DiagnosticFinding,
    PatchSuggestion,
    finding_messages,
    findings_payload,
    patch_suggestions_payload,
)
from vibecomfy.ir import __all__ as ir_all
from vibecomfy.ir import DiagnosticLike
from vibecomfy.ir.diagnostic import Diagnostic


def test_diagnostic_finding_payload_omits_empty_optional_fields() -> None:
    finding = DiagnosticFinding("missing_model", "model is missing", "error")

    assert finding.to_payload() == {
        "code": "missing_model",
        "message": "model is missing",
        "severity": "error",
    }


def test_diagnostic_finding_payload_preserves_doctor_aligned_fields() -> None:
    finding = DiagnosticFinding(
        "unknown_class_type",
        "Unknown node class",
        "warning",
        node_id="12",
        class_type="ExampleNode",
        detail={"class_type": "ExampleNode"},
    )

    assert finding.to_payload() == {
        "code": "unknown_class_type",
        "message": "Unknown node class",
        "severity": "warning",
        "node_id": "12",
        "class_type": "ExampleNode",
        "detail": {"class_type": "ExampleNode"},
    }


def test_diagnostic_helpers_convert_current_payload_shapes() -> None:
    findings = [
        DiagnosticFinding("a", "first", "warning"),
        DiagnosticFinding("b", "second", "error"),
    ]
    suggestions = [PatchSuggestion("seed", "set deterministic seed")]

    assert finding_messages(findings, severity="error") == ["second"]
    assert findings_payload(findings) == [finding.to_payload() for finding in findings]
    assert patch_suggestions_payload(suggestions) == [{"name": "seed", "rationale": "set deterministic seed"}]


# --- DiagnosticLike (vibecomfy.ir.diagnostic) ---


def _protocol_members(protocol: type) -> set[str]:
    return {name for name in protocol.__dict__ if not name.startswith("_")}


def test_diagnostic_like_declares_exactly_four_fields() -> None:
    members = _protocol_members(DiagnosticLike)
    assert members == {"code", "message", "severity", "detail"}
    # Every member is a read-only property (no setter).
    for name in members:
        assert isinstance(DiagnosticLike.__dict__[name], property)


def test_diagnostic_like_is_not_runtime_checkable() -> None:
    with pytest.raises(TypeError):
        isinstance(object(), DiagnosticLike)


def test_diagnostic_like_does_not_require_to_json() -> None:
    assert "to_json" not in _protocol_members(DiagnosticLike)
    assert not hasattr(DiagnosticLike, "to_json")


def test_diagnostic_like_matches_four_field_class_without_to_json() -> None:
    class FourFieldDiagnostic:
        def __init__(
            self,
            code: str,
            message: str,
            severity: str,
            detail: dict[str, Any],
        ) -> None:
            self.code = code
            self.message = message
            self.severity = severity
            self.detail = detail

    sample = FourFieldDiagnostic("c", "m", "error", {"k": "v"})
    # Every member the protocol requires must exist on the concrete object.
    for name in _protocol_members(DiagnosticLike):
        assert hasattr(sample, name)


def test_diagnostic_satisfies_diagnostic_like_surface() -> None:
    diagnostic = Diagnostic("code", "message")
    for name in _protocol_members(DiagnosticLike):
        assert hasattr(diagnostic, name)


def test_diagnostic_like_exported_from_ir_package() -> None:
    assert "DiagnosticLike" in ir_all
    assert DiagnosticLike.__module__ == "vibecomfy.ir.diagnostic"
