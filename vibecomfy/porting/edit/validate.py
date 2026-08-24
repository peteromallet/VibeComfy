"""Literal-value validation for the IR interpreter."""

from __future__ import annotations

import re
from typing import Any, Literal, Mapping

from vibecomfy.porting.report import PortIssue
from vibecomfy.porting.resolution import _normalize_type
from vibecomfy.schema import InputSpec


def _issue(
    code: str,
    message: str,
    *,
    severity: Literal["error", "warning", "info"] = "error",
    detail: Mapping[str, Any] | None = None,
) -> PortIssue:
    return PortIssue(code=code, message=message, severity=severity, detail=dict(detail or {}))


def validate_literal_value(
    *,
    value: Any,
    spec: InputSpec | None,
    class_type: str,
    input_name: str,
    context: str,
) -> list[PortIssue]:
    if spec is None:
        return []
    # Fail-closed against statically-unresolvable combo choices.
    if bool(getattr(spec, "unresolved_choices", False)):
        return [
            _issue(
                "unresolved_choices",
                f"{context} rejected {class_type}.{input_name}: literal value {value!r} cannot be validated against unresolved choices.",
                detail={
                    "class_type": class_type,
                    "input": input_name,
                    "value": value,
                },
            )
        ]
    issues: list[PortIssue] = []
    choices = getattr(spec, "choices", None) or []
    if choices and value not in choices and _coerce_choice_value(value, choices) is _NO_MATCH:
        detail = {
            "class_type": class_type,
            "input": input_name,
            "value": value,
            "choices": list(choices),
        }
        if _is_asset_enum(value=value, spec=spec, input_name=input_name, choices=choices):
            issues.append(
                _issue(
                    "asset_not_installed",
                    f"{context} accepted {class_type}.{input_name}: asset {value!r} is not in the declared local choices.",
                    severity="warning",
                    detail=detail,
                )
            )
        else:
            issues.append(
                _issue(
                    "value_not_in_enum",
                    f"{context} rejected {class_type}.{input_name}: value {value!r} is not in the declared enum.",
                    detail=detail,
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
                _issue(
                    "value_out_of_range",
                    f"{context} rejected {class_type}.{input_name}: value {value!r} is outside the declared range.",
                    detail={
                        "class_type": class_type,
                        "input": input_name,
                        "value": value,
                        "min": min_value,
                        "max": max_value,
                    },
                )
            )
    expected_type = _primitive_expected_type(getattr(spec, "type", None))
    if expected_type is not None and not _matches_primitive_type(value, expected_type):
        issues.append(
            _issue(
                "value_type_mismatch",
                f"{context} rejected {class_type}.{input_name}: expected {expected_type}, got {type(value).__name__}.",
                detail={
                    "class_type": class_type,
                    "input": input_name,
                    "value": value,
                    "expected_type": expected_type,
                    "actual_type": type(value).__name__,
                },
            )
        )
    return issues


def _primitive_expected_type(value: Any) -> str | None:
    normalized = _normalize_type(value)
    if normalized in {"INT", "INTEGER"}:
        return "INT"
    if normalized in {"FLOAT", "DOUBLE"}:
        return "FLOAT"
    if normalized in {"BOOL", "BOOLEAN"}:
        return "BOOLEAN"
    if normalized in {"STR", "STRING", "TEXT"}:
        return "STRING"
    return None


def _matches_primitive_type(value: Any, expected_type: str) -> bool:
    if expected_type == "INT":
        return isinstance(value, int) and not isinstance(value, bool)
    if expected_type == "FLOAT":
        return ((isinstance(value, int) and not isinstance(value, bool)) or isinstance(value, float))
    if expected_type == "BOOLEAN":
        return isinstance(value, bool)
    if expected_type == "STRING":
        return isinstance(value, str)
    return True


def _as_number(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


_NO_MATCH = object()

_ASSET_FIELD_WORDS = frozenset(
    {
        "checkpoint",
        "ckpt",
        "clip",
        "embedding",
        "gguf",
        "lora",
        "model",
        "unet",
        "vae",
    }
)
_ASSET_EXTENSIONS = (
    ".bin",
    ".ckpt",
    ".gguf",
    ".pt",
    ".safetensors",
    ".sft",
)
_CONSTRAINED_FIELD_SUFFIXES = frozenset({"format", "method", "mode", "option", "preset", "type"})


def _is_asset_enum(*, value: Any, spec: InputSpec, input_name: str, choices: list[Any]) -> bool:
    if not isinstance(value, str):
        return False
    field_identifier = _normalized_identifier(input_name)
    field_name_signals_asset = any(word in field_identifier for word in _ASSET_FIELD_WORDS) and not any(
        field_identifier.endswith(suffix) for suffix in _CONSTRAINED_FIELD_SUFFIXES
    )
    type_identifier = _normalized_identifier(str(getattr(spec, "type", "") or ""))
    if field_name_signals_asset or any(word in type_identifier for word in _ASSET_FIELD_WORDS):
        return True
    if any(isinstance(choice, str) and _looks_like_asset_reference(choice) for choice in choices):
        return True
    return _looks_like_asset_reference(value)


def _normalized_identifier(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", value.lower())


def _looks_like_asset_reference(value: str) -> bool:
    normalized = value.strip().replace("\\", "/").lower()
    path_without_query = normalized.split("?", 1)[0].split("#", 1)[0]
    return (
        "/" in normalized
        or normalized.startswith(("http://", "https://"))
        or path_without_query.endswith(_ASSET_EXTENSIONS)
    )


def _coerce_choice_value(value: Any, choices: list[Any]) -> Any:
    if isinstance(value, str):
        normalized = value.replace("\\", "/")
        for choice in choices:
            if isinstance(choice, str) and choice.replace("\\", "/") == normalized:
                return choice
    return _NO_MATCH
