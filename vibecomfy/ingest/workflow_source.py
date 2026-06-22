from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

from vibecomfy.ingest.normalize import detect_workflow_shape, normalize_to_api

WorkflowSourceStatus = Literal["loaded", "unsupported", "error"]
WorkflowSourceShape = Literal["api", "litegraph", "unknown"]

_WRAPPER_KEYS = ("workflow", "prompt", "graph")


@dataclass(frozen=True)
class WorkflowLoadWarning:
    code: str
    message: str
    path: tuple[str, ...] = ()
    severity: Literal["warning", "error"] = "warning"

    def to_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "message": self.message,
            "path": list(self.path),
            "severity": self.severity,
        }


@dataclass(frozen=True)
class WorkflowNodeRecord:
    node_id: str
    class_type: str
    inputs: dict[str, Any] = field(default_factory=dict)
    raw_node: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "node_id": self.node_id,
            "class_type": self.class_type,
            "inputs": dict(self.inputs),
            "raw_node": dict(self.raw_node),
        }


@dataclass(frozen=True)
class WorkflowLoadResult:
    status: WorkflowSourceStatus
    shape: WorkflowSourceShape
    raw: dict[str, Any] | None = None
    api: dict[str, Any] | None = None
    nodes: tuple[WorkflowNodeRecord, ...] = ()
    warnings: tuple[WorkflowLoadWarning, ...] = ()
    source_path: str | None = None

    @property
    def ok(self) -> bool:
        return self.status == "loaded"

    @property
    def blocks_candidate_output(self) -> bool:
        return self.status != "loaded"

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "shape": self.shape,
            "source_path": self.source_path,
            "node_count": len(self.nodes),
            "nodes": [node.to_dict() for node in self.nodes],
            "warnings": [warning.to_dict() for warning in self.warnings],
            "blocks_candidate_output": self.blocks_candidate_output,
        }


def load_workflow_source(path: str | Path) -> WorkflowLoadResult:
    source_path = Path(path)
    try:
        with source_path.open("r", encoding="utf-8") as handle:
            raw = json.load(handle)
    except json.JSONDecodeError as exc:
        return _unsupported(
            source_path=str(source_path),
            code="invalid_json",
            message=f"Workflow source JSON could not be decoded: {exc}",
            severity="error",
        )
    except OSError as exc:
        return _unsupported(
            source_path=str(source_path),
            code="read_error",
            message=f"Workflow source could not be read: {exc}",
            severity="error",
        )
    return normalize_workflow_source(raw, source_path=str(source_path))


def normalize_workflow_source(raw: Any, *, source_path: str | None = None) -> WorkflowLoadResult:
    if not isinstance(raw, dict):
        return _unsupported(
            source_path=source_path,
            code="not_object",
            message="Workflow source must decode to a JSON object.",
            severity="error",
        )

    unwrapped, wrapper_path, unwrap_warnings = _unwrap_workflow(raw)
    shape = _detect_source_shape(unwrapped)
    if shape == "unknown":
        return WorkflowLoadResult(
            status="unsupported",
            shape="unknown",
            raw=unwrapped,
            warnings=(
                *unwrap_warnings,
                WorkflowLoadWarning(
                    code="unsupported_workflow_format",
                    message=(
                        "Workflow source is not a ComfyUI API prompt dict or "
                        "LiteGraph nodes/links export."
                    ),
                    path=wrapper_path,
                    severity="warning",
                ),
            ),
            source_path=source_path,
        )

    try:
        api = normalize_to_api(unwrapped, use_comfy_converter=False)
    except Exception as exc:
        return WorkflowLoadResult(
            status="error",
            shape=shape,
            raw=unwrapped,
            warnings=(
                *unwrap_warnings,
                WorkflowLoadWarning(
                    code="normalization_error",
                    message=f"Workflow source normalization failed: {type(exc).__name__}: {exc}",
                    path=wrapper_path,
                    severity="error",
                ),
            ),
            source_path=source_path,
        )

    nodes = _node_records_from_api(api)
    if not nodes:
        return WorkflowLoadResult(
            status="unsupported",
            shape=shape,
            raw=unwrapped,
            api=api,
            warnings=(
                *unwrap_warnings,
                WorkflowLoadWarning(
                    code="no_node_records",
                    message="Workflow source normalized but did not contain any node records.",
                    path=wrapper_path,
                    severity="warning",
                ),
            ),
            source_path=source_path,
        )

    return WorkflowLoadResult(
        status="loaded",
        shape=shape,
        raw=unwrapped,
        api=api,
        nodes=nodes,
        warnings=unwrap_warnings,
        source_path=source_path,
    )


def _unwrap_workflow(raw: dict[str, Any]) -> tuple[dict[str, Any], tuple[str, ...], tuple[WorkflowLoadWarning, ...]]:
    current = raw
    path: list[str] = []
    warnings: list[WorkflowLoadWarning] = []
    seen: set[int] = set()

    while isinstance(current, dict) and id(current) not in seen:
        seen.add(id(current))
        next_key: str | None = None
        for key in _WRAPPER_KEYS:
            if isinstance(current.get(key), dict):
                next_key = key
                break
        if next_key is None:
            extra = current.get("extra")
            if isinstance(extra, dict) and isinstance(extra.get("workflow"), dict):
                path.extend(["extra", "workflow"])
                current = extra["workflow"]
                warnings.append(
                    WorkflowLoadWarning(
                        code="workflow_unwrapped",
                        message="Unwrapped workflow source from extra.workflow.",
                        path=tuple(path),
                    )
                )
                continue
            break
        path.append(next_key)
        current = current[next_key]
        if next_key != "prompt":
            warnings.append(
                WorkflowLoadWarning(
                    code="workflow_unwrapped",
                    message=f"Unwrapped workflow source from {'.'.join(path)}.",
                    path=tuple(path),
                )
            )

    return current, tuple(path), tuple(warnings)


def _detect_source_shape(raw: dict[str, Any]) -> WorkflowSourceShape:
    shape = detect_workflow_shape(raw)
    if shape == "api":
        return "api"
    if shape == "ui":
        return "litegraph"
    return "unknown"


def _node_records_from_api(api: dict[str, Any]) -> tuple[WorkflowNodeRecord, ...]:
    records: list[WorkflowNodeRecord] = []
    for node_id in sorted(api, key=_stable_node_sort_key):
        node = api[node_id]
        if not isinstance(node, dict):
            continue
        class_type = node.get("class_type")
        if not isinstance(class_type, str) or not class_type:
            continue
        inputs = node.get("inputs")
        records.append(
            WorkflowNodeRecord(
                node_id=str(node_id),
                class_type=class_type,
                inputs=dict(inputs) if isinstance(inputs, dict) else {},
                raw_node=dict(node),
            )
        )
    return tuple(records)


def _stable_node_sort_key(node_id: Any) -> tuple[int, int | str]:
    text = str(node_id)
    if text.isdigit():
        return (0, int(text))
    return (1, text)


def _unsupported(
    *,
    source_path: str | None,
    code: str,
    message: str,
    severity: Literal["warning", "error"],
) -> WorkflowLoadResult:
    return WorkflowLoadResult(
        status="error" if severity == "error" else "unsupported",
        shape="unknown",
        warnings=(
            WorkflowLoadWarning(
                code=code,
                message=message,
                severity=severity,
            ),
        ),
        source_path=source_path,
    )


__all__ = [
    "WorkflowLoadResult",
    "WorkflowLoadWarning",
    "WorkflowNodeRecord",
    "load_workflow_source",
    "normalize_workflow_source",
]
