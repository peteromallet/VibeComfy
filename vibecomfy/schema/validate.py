from __future__ import annotations

import copy
import re
from typing import Any

from vibecomfy.schema.provider import SchemaProvider, schema_for, schema_registry_empty
from vibecomfy.workflow import ValidationIssue, VibeWorkflow


#: Known-lying custom-node schemas that may suppress only ``unknown_input`` and
#: ``value_*`` validation issues. Every entry must be cross-referenced from
#: ``docs/node_pack_reconciliation.md`` with its contract/root-cause note.
#:
#: Classes listed here have stub object_info cache entries that only define
#: category/description but lack full input schemas; they were added to satisfy
#: ``unknown_class_type`` gating without triggering ``unknown_input`` cascade
#: errors on every workflow input. When a real runpod snapshot is available for
#: the pack, remove the stub file and the entry here.
SCHEMA_VALIDATION_SKIP_CLASSES: dict[str, str] = {
    # ComfyUI-Florence2 — stub schema; real schema from runpod snapshot pending
    "DownloadAndLoadFlorence2Model": "stub schema - see docs/node_pack_reconciliation.md",
    "Florence2Run": "stub schema - see docs/node_pack_reconciliation.md",
    # ComfyUI-GIMM-VFI — stub schema; real schema from runpod snapshot pending
    "DownloadAndLoadGIMMVFIModel": "stub schema - see docs/node_pack_reconciliation.md",
    "GIMMVFI_interpolate": "stub schema - see docs/node_pack_reconciliation.md",
    # ComfyUI-MelBandRoformer — stub schema; real schema from runpod snapshot pending
    "MelBandRoFormerModelLoader": "stub schema - see docs/node_pack_reconciliation.md",
    "MelBandRoFormerSampler": "stub schema - see docs/node_pack_reconciliation.md",
    # ComfyUI-Custom-Scripts — stub schema; real schema from runpod snapshot pending
    "ShowText|pysssss": "stub schema - see docs/node_pack_reconciliation.md",
    "MathExpression|pysssss": "stub schema - see docs/node_pack_reconciliation.md",
    # comfyui_controlnet_aux — stub schema; real schema from runpod snapshot pending
    "DWPreprocessor": "stub schema - see docs/node_pack_reconciliation.md",
    "CannyEdgePreprocessor": "stub schema - see docs/node_pack_reconciliation.md",
    "DepthAnythingPreprocessor": "stub schema - see docs/node_pack_reconciliation.md",
    # ComfyUI-DepthAnythingV2 — stub entries added; real schema from runpod snapshot pending
    "VideoDepthAnythingProcess": "stub schema - see docs/node_pack_reconciliation.md",
    "LoadVideoDepthAnythingModel": "stub schema - see docs/node_pack_reconciliation.md",
    "VideoDepthAnythingOutput": "stub schema - see docs/node_pack_reconciliation.md",
    # ComfyUI-KJNodes — ImageConcatMulti has dynamic image_N inputs (inputcount drives them)
    # The schema only shows image_1/image_2; image_3+ are created at runtime by the node
    "ImageConcatMulti": "dynamic inputs (image_N count driven by inputcount widget) - see docs/node_pack_reconciliation.md",
    # ComfyUI-WanVideoWrapper — WanVideoModelLoader schema snapshot predates vace_model input
    # vace_model was added in a newer WanVideoWrapper version; snapshot needs refresh
    "WanVideoModelLoader": "snapshot predates vace_model input - see docs/node_pack_reconciliation.md",
    # ComfyUI-WanVideoWrapper — VACE model enum only captures one HiddenSwitch-local file
    # Templates use WanVideo 2.1 1.3B VACE variant not in snapshot enum
    "WanVideoVACEModelSelect": "model enum reflects HiddenSwitch local files only - see docs/node_pack_reconciliation.md",
    # ComfyUI-KJNodes — ImagePadKJ pad_mode accepts RGB strings like '255,255,255'
    # The snapshot enum only lists named modes; RGB string pass-through is valid at runtime
    "ImagePadKJ": "pad_mode accepts RGB strings not in static enum - see docs/node_pack_reconciliation.md",
    # ComfyUI-WanVideoWrapper — WanVideoSampler gained a new widget (position 14) in newer
    # versions not captured in the current widget_schema.py entry (14 items, 0-indexed)
    "WanVideoSampler": "widget schema incomplete for newer WanVideoWrapper versions - see docs/node_pack_reconciliation.md",
}


def validate_against_schema(workflow: VibeWorkflow, provider: SchemaProvider) -> list[ValidationIssue]:
    if schema_registry_empty(provider):
        return []

    issues: list[ValidationIssue] = []
    schema_by_node: dict[str, Any] = {}
    try:
        api_dict = workflow.compile(backend="api")
    except Exception as exc:
        return [ValidationIssue("api_compile_failed", str(exc), severity="warning")]

    return validate_api_against_schema(api_dict, provider)


def validate_api_against_schema(api_dict: dict[str, Any], provider: SchemaProvider) -> list[ValidationIssue]:
    if schema_registry_empty(provider):
        return []

    issues: list[ValidationIssue] = []
    schema_by_node: dict[str, Any] = {}

    for node_id, node in api_dict.items():
        if not isinstance(node, dict):
            continue
        class_type = node.get("class_type")
        if not isinstance(class_type, str):
            continue
        schema = schema_for(provider, class_type)
        if schema is None:
            issues.append(
                ValidationIssue(
                    "unknown_class_type",
                    f"Unknown class_type {class_type} on node {node_id}.",
                    detail={
                        "node_id": str(node_id),
                        "class_type": class_type,
                        "next_action": "vibecomfy schema refresh",
                    },
                )
            )
            continue

        schema_by_node[str(node_id)] = schema
        raw_schema_inputs = getattr(schema, "inputs", {}) or {}
        declared_inputs = set(raw_schema_inputs)
        payload_inputs = node.get("inputs") or {}
        if not isinstance(payload_inputs, dict):
            payload_inputs = {}
        provided_inputs = set(payload_inputs)

        if not raw_schema_inputs:
            continue

        for name, spec in raw_schema_inputs.items():
            if getattr(spec, "required", False) and name not in provided_inputs and getattr(spec, "default", None) is None:
                issues.append(
                    ValidationIssue(
                        "missing_required_input",
                        f"Node {node_id} ({class_type}) is missing required input {name}.",
                        detail={"node_id": str(node_id), "class_type": class_type, "input": name},
                    )
                )

        for name in sorted(provided_inputs - declared_inputs):
            value = payload_inputs.get(name)
            if (
                getattr(schema, "source_provider", None) == "widget_schema"
                and _is_api_link(value)
            ) or _preserve_linked_undeclared_input(name, value):
                continue
            if (
                not _issue_suppressed(class_type, "unknown_input")
                and not _is_dynamic_payload_input(class_type, name, payload_inputs)
            ):
                issues.append(
                    ValidationIssue(
                        "unknown_input",
                        f"Node {node_id} ({class_type}) has unknown input {name}.",
                        detail={"node_id": str(node_id), "class_type": class_type, "input": name},
                    )
                )

        issues.extend(_validate_dynamic_payload_inputs(node_id=str(node_id), class_type=class_type, inputs=payload_inputs))

        for name in sorted(provided_inputs & declared_inputs):
            value = payload_inputs[name]
            if _is_api_link(value):
                continue
            spec = raw_schema_inputs[name]
            choices = getattr(spec, "choices", None) or []
            if (
                choices
                and value not in choices
                and _coerce_choice_value(value, choices) is _NO_MATCH
                and not _issue_suppressed(class_type, "value_not_in_enum")
                and not _is_dynamic_file_choice(class_type, name)
            ):
                issues.append(
                    ValidationIssue(
                        "value_not_in_enum",
                        f"Node {node_id} ({class_type}) input {name} value {_truncate(value)} is not one of the declared choices.",
                        severity="error",
                        detail={
                            "node_id": str(node_id),
                            "class_type": class_type,
                            "input": name,
                            "value": _truncate(value),
                            "choices": choices,
                        },
                    )
                )

            min_value = getattr(spec, "min", None)
            max_value = getattr(spec, "max", None)
            if (min_value is not None or max_value is not None) and not _issue_suppressed(class_type, "value_out_of_range"):
                try:
                    numeric_value = float(value)
                except (TypeError, ValueError):
                    continue
                if (min_value is not None and numeric_value < float(min_value)) or (
                    max_value is not None and numeric_value > float(max_value)
                ):
                    issues.append(
                        ValidationIssue(
                            "value_out_of_range",
                            f"Node {node_id} ({class_type}) input {name} value {_truncate(value)} is outside the declared range.",
                            severity="error",
                            detail={
                                "node_id": str(node_id),
                                "class_type": class_type,
                                "input": name,
                                "value": _truncate(value),
                                "min": min_value,
                                "max": max_value,
                            },
                        )
                    )
            expected_type = _primitive_expected_type(getattr(spec, "type", None))
            if expected_type and not _issue_suppressed(class_type, "value_type_mismatch"):
                if not _matches_primitive_type(value, expected_type):
                    issues.append(
                        ValidationIssue(
                            "value_type_mismatch",
                            (
                                f"Node {node_id} ({class_type}) input {name} value {_truncate(value)} "
                                f"does not match declared type {expected_type}."
                            ),
                            severity="error",
                            detail={
                                "node_id": str(node_id),
                                "class_type": class_type,
                                "input": name,
                                "value": _truncate(value),
                                "expected_type": expected_type,
                                "actual_type": type(value).__name__,
                            },
                        )
                    )

    for to_node_id, node in api_dict.items():
        if not isinstance(node, dict):
            continue
        to_schema = schema_by_node.get(str(to_node_id))
        inputs = node.get("inputs") or {}
        if to_schema is None or not isinstance(inputs, dict):
            continue
        for input_name, value in inputs.items():
            if not _is_api_link(value):
                continue
            from_node, from_output = str(value[0]), str(value[1])
            from_schema = schema_by_node.get(from_node)
            if from_schema is None:
                continue
            outputs = getattr(from_schema, "outputs", None) or []
            if not outputs:
                continue
            try:
                output_index = int(from_output)
            except (TypeError, ValueError):
                output_index = None
            # Empty outputs list means the schema does not declare output info
            # (e.g. permissive index synthesized from API workflows). Treat as
            # unknown and skip the output-index bounds check rather than emit a
            # false-positive violation. A truly outputless node would be a
            # leaf sink that never appears as an edge source anyway.
            if output_index is not None and outputs and (output_index < 0 or output_index >= len(outputs)):
                issues.append(
                    ValidationIssue(
                        "invalid_output_index",
                        f"Edge {from_node}.{from_output} -> {to_node_id}.{input_name} references output "
                        f"{from_output}, but {from_schema.class_type} exposes {len(outputs)} output(s).",
                        severity="error",
                        detail={
                            "from_node": from_node,
                            "from_class_type": from_schema.class_type,
                            "from_output": from_output,
                            "output_count": len(outputs),
                            "to_node": str(to_node_id),
                            "to_input": input_name,
                        },
                    )
                )
                continue
            output_type = _edge_output_type(from_schema, from_output)
            input_type = _edge_input_type(to_schema, input_name)
            if output_type and input_type and not socket_types_compatible(output_type, input_type):
                issues.append(
                    ValidationIssue(
                        "type_mismatch",
                        f"Edge {from_node}.{from_output} -> {to_node_id}.{input_name} connects {output_type} to {input_type}.",
                        severity="warning",
                        detail={
                            "from_node": from_node,
                            "from_output": from_output,
                            "to_node": str(to_node_id),
                            "to_input": input_name,
                            "output_type": output_type,
                            "input_type": input_type,
                        },
                    )
                )

    return issues


def sanitize_api_against_schema(api_dict: dict[str, Any], provider: SchemaProvider | None) -> dict[str, Any]:
    """Drop schema-unknown payload keys and coerce equivalent choice strings.

    Ready templates often keep UI widget aliases as authoring hints. Runtime API
    prompts must match the live node schema exactly, so this strips fields the
    runtime will reject and normalizes portable model paths to the exact choice
    string exposed by Comfy.
    """
    if provider is None or schema_registry_empty(provider):
        return api_dict
    sanitized = copy.deepcopy(api_dict)
    for node in sanitized.values():
        if not isinstance(node, dict):
            continue
        class_type = node.get("class_type")
        inputs = node.get("inputs")
        if not isinstance(class_type, str) or not isinstance(inputs, dict):
            continue
        schema = schema_for(provider, class_type)
        schema_inputs = getattr(schema, "inputs", {}) if schema is not None else {}
        if not schema_inputs:
            continue
        for name in list(inputs):
            if (
                name not in schema_inputs
                and not _is_dynamic_payload_input(class_type, name, inputs)
                and not (
                    getattr(schema, "source_provider", None) == "widget_schema"
                    and _is_api_link(inputs.get(name))
                )
                and not _preserve_linked_undeclared_input(name, inputs.get(name))
            ):
                del inputs[name]
                continue
            value = inputs[name]
            if _is_api_link(value):
                continue
            if name not in schema_inputs:
                continue
            choices = getattr(schema_inputs[name], "choices", None) or []
            coerced = _coerce_choice_value(value, choices)
            if coerced is not _NO_MATCH:
                inputs[name] = coerced
    return sanitized


def validate_api_link_shapes(api_dict: dict[str, Any], provider: SchemaProvider) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    for node_id, node in api_dict.items():
        if not isinstance(node, dict):
            continue
        class_type = node.get("class_type")
        inputs = node.get("inputs", {})
        if not isinstance(class_type, str) or not isinstance(inputs, dict):
            continue
        schema = schema_for(provider, class_type)
        raw_schema_inputs = getattr(schema, "inputs", {}) or {}
        for name, value in inputs.items():
            if not isinstance(value, dict):
                continue
            spec = raw_schema_inputs.get(name)
            if _schema_accepts_dict(spec):
                continue
            issues.append(
                ValidationIssue(
                    "invalid_link_shape",
                    f"Node {node_id} ({class_type}) input {name} has dict-shaped link; expected [node_id, output_index].",
                    severity="error",
                    detail={
                        "node_id": str(node_id),
                        "class_type": class_type,
                        "input": name,
                        "value_repr": _truncate(value),
                    },
                )
            )
    return issues


def _incoming_inputs(workflow: VibeWorkflow) -> dict[str, set[str]]:
    incoming: dict[str, set[str]] = {}
    for edge in workflow.edges:
        incoming.setdefault(edge.to_node, set()).add(edge.to_input)
    return incoming


_LTX_IMAGE_SLOT_RE = re.compile(r"^num_images\.(?:image|index|strength)_(\d+)$")
_FIXED_SLOT_INPUT_RE = re.compile(r"^in_(\d+)$")


def _preserve_linked_undeclared_input(name: str, value: Any) -> bool:
    """Keep linked fixed-slot inputs even when the local schema omits them.

    Some Comfy-compatible nodes accept numbered wildcard sockets through the
    prompt payload path even when the best available local schema is narrower.
    Stripping a linked ``in_N`` here breaks delivery before runtime sees it.
    """

    return bool(_FIXED_SLOT_INPUT_RE.match(name)) and _is_api_link(value)


def _is_dynamic_payload_input(class_type: str, input_name: str, inputs: dict[str, Any] | None = None) -> bool:
    """Return whether an input is generated from a runtime payload count.

    Some custom nodes declare a compact controller input in object_info but
    validate expanded dotted inputs at queue time. These are not UI aliases:
    stripping them changes the executable prompt. Keep this list narrow and
    add class-specific validation below so dynamic inputs remain intentional.
    """

    if class_type == "LTXVImgToVideoInplaceKJ":
        return _LTX_IMAGE_SLOT_RE.match(input_name) is not None
    if class_type == "SimpleCalculator" and _has_numbered_prefix(input_name, "input_"):
        return True
    if class_type == "LTXVAddGuide" and _has_numbered_prefix(input_name, "guide_"):
        return True
    if class_type == "SimpleCalculatorKJ":
        return input_name in _simple_calculator_variables(inputs or {})
    return False


def _validate_dynamic_payload_inputs(
    *,
    node_id: str,
    class_type: str,
    inputs: dict[str, Any],
) -> list[ValidationIssue]:
    if class_type != "LTXVImgToVideoInplaceKJ":
        if class_type in {"SimpleCalculator", "SimpleCalculatorKJ"}:
            return _validate_simple_calculator_variables(node_id=node_id, class_type=class_type, inputs=inputs)
        return []
    raw_count = inputs.get("num_images")
    if raw_count is None or _is_api_link(raw_count):
        return []
    try:
        count = int(raw_count)
    except (TypeError, ValueError):
        return [
            ValidationIssue(
                "invalid_dynamic_input_count",
                f"Node {node_id} ({class_type}) input num_images must be an integer count.",
                severity="error",
                detail={"node_id": node_id, "class_type": class_type, "input": "num_images", "value": _truncate(raw_count)},
            )
        ]

    issues: list[ValidationIssue] = []
    for index in range(1, count + 1):
        for suffix in ("image", "index", "strength"):
            name = f"num_images.{suffix}_{index}"
            if name not in inputs:
                issues.append(
                    ValidationIssue(
                        "missing_dynamic_input",
                        f"Node {node_id} ({class_type}) is missing dynamic input {name}.",
                        severity="error",
                        detail={"node_id": node_id, "class_type": class_type, "input": name},
                    )
                )
    return issues


def _simple_calculator_variables(inputs: dict[str, Any]) -> set[str]:
    raw = inputs.get("variables")
    if not isinstance(raw, str):
        return set()
    return {part.strip() for part in raw.split(",") if part.strip()}


def _has_numbered_prefix(value: str, prefix: str) -> bool:
    suffix = value.removeprefix(prefix)
    return suffix != value and suffix.isdigit()


def _validate_simple_calculator_variables(
    *,
    node_id: str,
    class_type: str,
    inputs: dict[str, Any],
) -> list[ValidationIssue]:
    variables = _simple_calculator_variables(inputs)
    return [
        ValidationIssue(
            "missing_dynamic_input",
            f"Node {node_id} ({class_type}) is missing dynamic input {name}.",
            severity="error",
            detail={"node_id": node_id, "class_type": class_type, "input": name},
        )
        for name in sorted(variables)
        if name not in inputs
    ]


def _edge_output_type(schema, from_output: str) -> str | None:
    outputs = getattr(schema, "outputs", None) or []
    try:
        index = int(from_output)
    except (TypeError, ValueError):
        index = None
    if index is not None and 0 <= index < len(outputs):
        return _normalize_type(getattr(outputs[index], "type", None))
    for output in outputs:
        if getattr(output, "name", None) == from_output:
            return _normalize_type(getattr(output, "type", None))
    return None


def _edge_input_type(schema, to_input: str) -> str | None:
    spec = (getattr(schema, "inputs", {}) or {}).get(to_input)
    if spec is None:
        return None
    return _normalize_type(getattr(spec, "type", None))


def _normalize_type(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip().upper()
    if not text or text == "*":
        return None
    return text


def socket_types_compatible(output_type: Any, input_type: Any) -> bool:
    """Return whether a Comfy output socket type can connect to an input type."""

    normalized_output = _normalize_type(output_type)
    normalized_input = _normalize_type(input_type)
    if normalized_output is None or normalized_input is None:
        return True
    if normalized_output == normalized_input:
        return True
    if normalized_output in {"*", "ANY"} or normalized_input in {"*", "ANY"}:
        return True
    return False


def _primitive_expected_type(value: Any) -> str | None:
    normalized = _normalize_type(value)
    if normalized in {"INT", "INTEGER"}:
        return "INT"
    if normalized in {"FLOAT", "DOUBLE"}:
        return "FLOAT"
    if normalized in {"BOOL", "BOOLEAN"}:
        return "BOOLEAN"
    if normalized in {"STR", "STRING"}:
        return "STRING"
    return None


def _matches_primitive_type(value: Any, expected_type: str) -> bool:
    if expected_type == "INT":
        return _is_int_literal(value)
    if expected_type == "FLOAT":
        return _is_float_literal(value)
    if expected_type == "BOOLEAN":
        return _is_boolean_literal(value)
    if expected_type == "STRING":
        return isinstance(value, str)
    return True


def _is_int_literal(value: Any) -> bool:
    if isinstance(value, bool):
        return False
    if isinstance(value, int):
        return True
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return False
        try:
            int(text, 10)
        except ValueError:
            return False
        return True
    return False


def _is_float_literal(value: Any) -> bool:
    if isinstance(value, bool):
        return False
    if isinstance(value, (int, float)):
        return True
    if isinstance(value, str):
        try:
            float(value)
        except ValueError:
            return False
        return True
    return False


def _is_boolean_literal(value: Any) -> bool:
    if isinstance(value, bool):
        return True
    if isinstance(value, str):
        return value.strip().lower() in {"true", "false"}
    return False


def _is_api_link(value: Any) -> bool:
    return (
        isinstance(value, (list, tuple))
        and len(value) == 2
        and isinstance(value[0], str)
        and isinstance(value[1], int)
    )


def _truncate(value: Any, n: int = 120) -> str:
    text = repr(value)
    if len(text) <= n:
        return text
    return text[: max(0, n - 3)] + "..."


_NO_MATCH = object()


def _coerce_choice_value(value: Any, choices: list[Any]) -> Any:
    if value in choices:
        return _NO_MATCH
    if not isinstance(value, str):
        return _NO_MATCH
    normalized_value = _portable_choice_key(value)
    basename_value = normalized_value.rsplit("/", 1)[-1]
    matches = [
        choice
        for choice in choices
        if isinstance(choice, str)
        and (
            _portable_choice_key(choice) == normalized_value
            or _portable_choice_key(choice).rsplit("/", 1)[-1] == basename_value
        )
    ]
    return matches[0] if len(matches) == 1 else _NO_MATCH


def _portable_choice_key(value: str) -> str:
    return value.replace("\\", "/").strip()


def _issue_suppressed(class_type: str, code: str) -> bool:
    if class_type not in SCHEMA_VALIDATION_SKIP_CLASSES:
        return False
    return code == "unknown_input" or code.startswith("value_")


def _is_dynamic_file_choice(class_type: str, input_name: str) -> bool:
    """Return whether a Comfy enum is a runtime file picker, not a semantic enum.

    Object-info choices for these inputs reflect files present in the active
    input directory when object_info was fetched. Task scratchpads often copy
    images/videos immediately before queueing, so treating stale file-picker
    choices as hard schema errors rejects valid runs. Model/checkpoint enums are
    intentionally not listed here.
    """

    return (class_type, input_name) in {
        ("LoadImage", "image"),
        ("LoadVideo", "video"),
        ("LoadVideo", "file"),
        ("VHS_LoadVideo", "video"),
        ("VHS_LoadVideo", "file"),
    }


def _schema_accepts_dict(spec: Any) -> bool:
    typ = getattr(spec, "type", None)
    if typ is None:
        return False
    return str(typ).strip().upper() in {"DICT", "JSON", "*"}
