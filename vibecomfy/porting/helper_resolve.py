"""Conversion adapter for IR-neutral helper-edge resolution."""

from __future__ import annotations

from typing import Any

from vibecomfy._compile._resolve import (  # REMOVE-M4 compatibility exports
    HelperResolveErrorSpec,
    ResolveDiagnostics,
    resolve_helpers as _resolve_helpers,
)
from vibecomfy._compile._helpers import HelperDiagnostic
from vibecomfy.errors import ConversionParityError
from vibecomfy.porting.object_info import get_class
from vibecomfy.workflow import VibeNode, VibeWorkflow


def resolve_helpers(
    workflow: VibeWorkflow,
    registered_inputs: dict[str, tuple[str, str]],
) -> ResolveDiagnostics:
    """Eliminate conversion-resolvable helper nodes from *workflow*.

    The graph traversal and rewrite semantics live in ``vibecomfy._helper_resolve``.
    This wrapper keeps conversion-specific primitive coercion and
    ``ConversionParityError`` behavior in the porting layer.
    """
    return _resolve_helpers(
        workflow,
        registered_inputs,
        primitive_value_extractor=_extract_primitive_value,
        error_factory=_conversion_error,
    )


def _conversion_error(spec: HelperResolveErrorSpec) -> ConversionParityError:
    return ConversionParityError(spec.message, next_action=spec.next_action)


_TYPE_TOKEN_MAP: dict[str, type] = {
    "BOOLEAN": bool,
    "INT": int,
    "FLOAT": float,
    "STRING": str,
}


def _extract_primitive_value(node: VibeNode, diagnostics: list[HelperDiagnostic]) -> Any:
    """Extract a typed literal from a Primitive* node via object_info."""
    raw = node.inputs.get("value", node.widgets.get("widget_0"))

    entry = get_class(node.class_type)
    if entry is None:
        diagnostics.append(
            HelperDiagnostic(
                code="primitive_no_schema",
                message=(
                    f"No object_info schema entry for {node.class_type} "
                    f"({node.id}); keeping raw widget value"
                ),
                severity="info",
                node_id=node.id,
                class_type=node.class_type,
            )
        )
        return raw

    inputs = entry.get("inputs", {})
    required = inputs.get("required", {})
    value_spec = required.get("value")

    if not isinstance(value_spec, list) or len(value_spec) < 1:
        diagnostics.append(
            HelperDiagnostic(
                code="primitive_no_value_spec",
                message=(
                    f"Object_info for {node.class_type} ({node.id}) has "
                    "unexpected inputs.required.value structure; keeping raw widget value"
                ),
                severity="info",
                node_id=node.id,
                class_type=node.class_type,
            )
        )
        return raw

    type_token = value_spec[0]
    coerce_fn = _TYPE_TOKEN_MAP.get(type_token)
    if coerce_fn is None:
        diagnostics.append(
            HelperDiagnostic(
                code="primitive_unknown_type_token",
                message=(
                    f"Unknown type token {type_token!r} for {node.class_type} "
                    f"({node.id}); keeping raw widget value"
                ),
                severity="info",
                node_id=node.id,
                class_type=node.class_type,
            )
        )
        return raw

    if raw is None:
        if coerce_fn is bool:
            return False
        if coerce_fn is int:
            return 0
        if coerce_fn is float:
            return 0.0
        if coerce_fn is str:
            return ""
        return raw

    return coerce_fn(raw)


__all__ = [
    "ResolveDiagnostics",
    "resolve_helpers",
]
