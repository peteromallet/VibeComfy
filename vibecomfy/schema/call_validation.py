from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from vibecomfy.schema.provider import SchemaProvider, schema_for


@dataclass(frozen=True, slots=True)
class NodeCallValidationIssue:
    code: str
    message: str
    severity: str = "error"
    input: str | None = None
    detail: dict[str, Any] = field(default_factory=dict)

    def to_json(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "message": self.message,
            "severity": self.severity,
            "input": self.input,
            "detail": dict(self.detail),
        }


@dataclass(frozen=True, slots=True)
class NodeCallValidationReport:
    class_type: str
    ok: bool
    issues: list[NodeCallValidationIssue] = field(default_factory=list)

    def to_json(self) -> dict[str, Any]:
        return {
            "class_type": self.class_type,
            "ok": self.ok,
            "issues": [issue.to_json() for issue in self.issues],
        }


def validate_node_call(
    class_type: str,
    inputs: dict[str, Any],
    provider: SchemaProvider,
) -> NodeCallValidationReport:
    """Validate one schema-backed primitive node call without building a graph."""

    schema = schema_for(provider, class_type)
    if schema is None:
        issue = NodeCallValidationIssue(
            "unknown_class_type",
            f"Unknown class_type {class_type}.",
            detail={"class_type": class_type},
        )
        return NodeCallValidationReport(class_type=class_type, ok=False, issues=[issue])

    schema_inputs = getattr(schema, "inputs", {}) or {}
    issues: list[NodeCallValidationIssue] = []
    provided = set(inputs)
    declared = set(schema_inputs)

    for name, spec in schema_inputs.items():
        if getattr(spec, "required", False) and name not in provided and getattr(spec, "default", None) is None:
            issues.append(
                NodeCallValidationIssue(
                    "missing_required_input",
                    f"{class_type} is missing required input {name}.",
                    input=name,
                    detail={"class_type": class_type, "input": name},
                )
            )

    for name in sorted(provided - declared):
        issues.append(
            NodeCallValidationIssue(
                "unknown_input",
                f"{class_type} has unknown input {name}.",
                input=name,
                detail={"class_type": class_type, "input": name},
            )
        )

    for name in sorted(provided & declared):
        value = inputs[name]
        if _is_link(value):
            continue
        spec = schema_inputs[name]
        choices = getattr(spec, "choices", None) or []
        if choices and value not in choices:
            issues.append(
                NodeCallValidationIssue(
                    "value_not_in_enum",
                    f"{class_type} input {name} value {_truncate(value)} is not one of the declared choices.",
                    input=name,
                    detail={"class_type": class_type, "input": name, "value": value, "choices": choices},
                )
            )
        min_value = getattr(spec, "min", None)
        max_value = getattr(spec, "max", None)
        if min_value is not None or max_value is not None:
            numeric = _as_number(value)
            if numeric is not None and (
                (min_value is not None and numeric < float(min_value))
                or (max_value is not None and numeric > float(max_value))
            ):
                issues.append(
                    NodeCallValidationIssue(
                        "value_out_of_range",
                        f"{class_type} input {name} value {_truncate(value)} is outside the declared range.",
                        input=name,
                        detail={"class_type": class_type, "input": name, "value": value, "min": min_value, "max": max_value},
                    )
                )
        expected = _primitive_type(getattr(spec, "type", None))
        if expected is not None and not isinstance(value, expected):
            issues.append(
                NodeCallValidationIssue(
                    "primitive_type_mismatch",
                    f"{class_type} input {name} expected {_primitive_name(expected)}, got {type(value).__name__}.",
                    input=name,
                    detail={
                        "class_type": class_type,
                        "input": name,
                        "expected": _primitive_name(expected),
                        "actual": type(value).__name__,
                        "value": value,
                    },
                )
            )
    return NodeCallValidationReport(class_type=class_type, ok=not issues, issues=issues)


def _primitive_type(schema_type: Any) -> type | None:
    text = str(schema_type or "").strip().upper()
    if text == "INT":
        return int
    if text == "FLOAT":
        return int | float
    if text in {"STRING", "TEXT"}:
        return str
    if text in {"BOOLEAN", "BOOL"}:
        return bool
    return None


def _primitive_name(expected: type) -> str:
    if expected is bool:
        return "bool"
    if expected is int:
        return "int"
    if expected is str:
        return "str"
    return str(expected).replace(" | ", "|")


def _as_number(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _is_link(value: Any) -> bool:
    return isinstance(value, (list, tuple)) and len(value) == 2 and isinstance(value[0], str) and isinstance(value[1], int)


def _truncate(value: Any, n: int = 120) -> str:
    text = repr(value)
    return text if len(text) <= n else text[: max(0, n - 3)] + "..."


__all__ = ["NodeCallValidationIssue", "NodeCallValidationReport", "validate_node_call"]
