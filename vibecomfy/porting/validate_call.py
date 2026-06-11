from __future__ import annotations

import difflib
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from vibecomfy.schema import ConversionSchemaProvider, InputSpec, NodeSchema, OutputSpec
from vibecomfy.porting.object_info.consume import get_class


@dataclass(frozen=True)
class CallValidationError:
    kwarg: str
    type: str
    suggestion: str | None = None

    def to_json(self) -> dict[str, Any]:
        payload = {"kwarg": self.kwarg, "type": self.type}
        if self.suggestion:
            payload["suggestion"] = self.suggestion
        return payload


@dataclass(frozen=True)
class CallValidationResult:
    class_type: str
    valid: bool
    errors: list[CallValidationError] = field(default_factory=list)
    missing_required: list[str] = field(default_factory=list)
    schema_outputs: list[str] = field(default_factory=list)
    schema_source: str | None = None

    def to_json(self) -> dict[str, Any]:
        return {
            "class": self.class_type,
            "valid": self.valid,
            "errors": [error.to_json() for error in self.errors],
            "missing_required": list(self.missing_required),
            "schema_outputs": list(self.schema_outputs),
            "schema_source": self.schema_source,
        }


def validate_call(
    class_type: str,
    kwargs: dict[str, Any],
    *,
    workflow_path: str | None = None,
    schema_provider: Any | None = None,
) -> CallValidationResult:
    provider = schema_provider or ConversionSchemaProvider()
    schema = _subgraph_schema(class_type, workflow_path) if workflow_path else None
    if schema is None:
        schema = _cached_object_info_schema(class_type)
    if schema is None:
        schema = provider.get_schema(class_type)
    if schema is None:
        return CallValidationResult(
            class_type=class_type,
            valid=False,
            errors=[CallValidationError(kwarg=class_type, type="unknown_class")],
        )

    declared = set(schema.inputs)
    provided = set(kwargs)
    errors = [
        CallValidationError(
            kwarg=name,
            type="unknown_kwarg",
            suggestion=_suggestion(name, declared),
        )
        for name in sorted(provided - declared)
    ]
    missing = sorted(
        name
        for name, spec in schema.inputs.items()
        if getattr(spec, "required", False) and name not in provided
    )
    outputs = [
        output.type or output.name or f"output_{index}"
        for index, output in enumerate(schema.outputs)
    ]
    return CallValidationResult(
        class_type=class_type,
        valid=not errors,
        errors=errors,
        missing_required=missing,
        schema_outputs=outputs,
        schema_source=getattr(schema, "source_provider", None),
    )


def parse_kwargs_json(raw: str) -> dict[str, Any]:
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(f"--kwargs must be a JSON object: {exc}") from exc
    if not isinstance(parsed, dict):
        raise ValueError("--kwargs must be a JSON object")
    return parsed


def _suggestion(name: str, declared: set[str]) -> str | None:
    matches = difflib.get_close_matches(name, sorted(declared), n=1, cutoff=0.55)
    if not matches:
        return None
    return f"did you mean '{matches[0]}'?"


def _subgraph_schema(class_type: str, workflow_path: str | None) -> NodeSchema | None:
    if not workflow_path:
        return None
    path = Path(workflow_path)
    if not path.is_file():
        return None
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    definitions = raw.get("definitions") if isinstance(raw, dict) else None
    subgraphs = definitions.get("subgraphs") if isinstance(definitions, dict) else None
    entry = subgraphs.get(class_type) if isinstance(subgraphs, dict) else None
    if not isinstance(entry, dict):
        return None
    inputs: dict[str, InputSpec] = {}
    raw_inputs = entry.get("inputs") or entry.get("input") or {}
    if isinstance(raw_inputs, dict):
        for name, spec in raw_inputs.items():
            inputs[str(name)] = _input_spec(spec)
    elif isinstance(raw_inputs, list):
        for item in raw_inputs:
            if isinstance(item, str):
                inputs[item] = InputSpec(required=True)
            elif isinstance(item, dict) and isinstance(item.get("name"), str):
                inputs[item["name"]] = _input_spec(item)
    raw_outputs = entry.get("outputs") or entry.get("output") or []
    outputs = []
    if isinstance(raw_outputs, list):
        for item in raw_outputs:
            if isinstance(item, dict):
                outputs.append(OutputSpec(type=item.get("type"), name=item.get("name")))
            else:
                outputs.append(OutputSpec(type=str(item)))
    return NodeSchema(
        class_type=class_type,
        pack="subgraph",
        inputs=inputs,
        outputs=outputs,
        source_provider="workflow_subgraph",
    )


def _input_spec(raw: Any) -> InputSpec:
    if isinstance(raw, dict):
        return InputSpec(type=raw.get("type"), required=bool(raw.get("required", True)), default=raw.get("default"))
    if isinstance(raw, str):
        return InputSpec(type=raw, required=True)
    return InputSpec(required=True)


def _cached_object_info_schema(class_type: str) -> NodeSchema | None:
    entry = get_class(class_type)
    if not isinstance(entry, dict):
        return None
    inputs: dict[str, InputSpec] = {}
    raw_inputs = entry.get("inputs") or {}
    if isinstance(raw_inputs, dict):
        for group_name, group in raw_inputs.items():
            if not isinstance(group, dict):
                continue
            for name, spec in group.items():
                parsed = _input_spec(spec)
                inputs[str(name)] = InputSpec(
                    type=parsed.type,
                    required=group_name == "required",
                    default=parsed.default,
                    choices=parsed.choices,
                    min=parsed.min,
                    max=parsed.max,
                )
    outputs = []
    for item in entry.get("outputs") or []:
        if isinstance(item, dict):
            outputs.append(OutputSpec(type=item.get("type"), name=item.get("name")))
    return NodeSchema(
        class_type=class_type,
        pack=entry.get("pack"),
        inputs=inputs,
        outputs=outputs,
        source_provider="object_info_cache",
    )
