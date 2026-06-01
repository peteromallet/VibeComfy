from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
import re
from typing import Any, Final

from vibecomfy.security.agent_generated_loader import scan_python_source_with_policy

VIBECOMFY_INTENT_CLASS_RE = re.compile(r"^vibecomfy\.[a-z]+$")

SHIPPED_INTENT_KINDS: Final[tuple[str, ...]] = ("code", "loop")
DEFERRED_INTENT_KINDS: Final[tuple[str, ...]] = ("branch", "workflowref")
ALL_INTENT_KINDS: Final[tuple[str, ...]] = SHIPPED_INTENT_KINDS + DEFERRED_INTENT_KINDS

INTENT_NODE_EDITOR_ONLY_CODE: Final[str] = "intent_node_editor_only"
INTENT_NODE_CONTRACT_INVALID_CODE: Final[str] = "intent_node_contract_invalid"
INTENT_NODE_QUEUE_BLOCKER_CODE: Final[str] = "intent_node_queue_blocker"

INTENT_CODE_MAX_BYTES: Final[int] = 16 * 1024
INTENT_SPEC_MAX_BYTES: Final[int] = 16 * 1024
INTENT_LOOP_MAX_ITERATIONS: Final[int] = 128

INTENT_NODE_VALIDATION_PHASE: Final[str] = "intent_node_validate"

KIND_TO_CLASS_TYPE: Final[dict[str, str]] = {
    "code": "vibecomfy.code",
    "loop": "vibecomfy.loop",
}
CLASS_TYPE_TO_KIND: Final[dict[str, str]] = {
    class_type: kind for kind, class_type in KIND_TO_CLASS_TYPE.items()
}


@dataclass(frozen=True, slots=True)
class IntentNodeProblem:
    code: str
    message: str
    detail: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class IntentNodeValidationResult:
    class_type: str
    vibecomfy_uid: str | None
    kind: str | None
    properties: dict[str, Any]
    payload: dict[str, Any] | None
    problems: tuple[IntentNodeProblem, ...] = ()

    @property
    def ok(self) -> bool:
        return not self.problems


def is_intent_class_type(class_type: str) -> bool:
    return bool(VIBECOMFY_INTENT_CLASS_RE.match(class_type))


def intent_node_properties(
    *,
    kind: str,
    uid: str,
    intent: Mapping[str, Any],
    inputs: Sequence[Sequence[str]] = (),
    outputs: Sequence[Sequence[str]] = (),
    extra_vibecomfy: Mapping[str, Any] | None = None,
    extra_properties: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    if kind not in ALL_INTENT_KINDS:
        raise ValueError(f"unknown intent node kind: {kind!r}")
    typed_inputs = _normalize_typed_io_entries("inputs", inputs)
    typed_outputs = _normalize_typed_io_entries("outputs", outputs)
    if not isinstance(uid, str) or not uid.strip():
        raise ValueError("intent node uid must be a non-empty string")
    if not isinstance(intent, Mapping):
        raise ValueError("intent node intent must be a mapping")
    properties = dict(extra_properties or {})
    vibecomfy = dict(extra_vibecomfy or {})
    vibecomfy["kind"] = kind
    vibecomfy["intent"] = dict(intent)
    vibecomfy["io"] = {
        "inputs": typed_inputs,
        "outputs": typed_outputs,
    }
    properties["vibecomfy_uid"] = uid
    properties["vibecomfy"] = vibecomfy
    return properties


def intent_node_properties_from_metadata(metadata: Mapping[str, Any] | None) -> dict[str, Any]:
    if not isinstance(metadata, Mapping):
        return {}
    ui = metadata.get("_ui")
    if isinstance(ui, Mapping):
        properties = ui.get("properties")
        if isinstance(properties, Mapping):
            return dict(properties)
    properties = metadata.get("properties")
    if isinstance(properties, Mapping):
        return dict(properties)
    return {}


def intent_node_payload_from_metadata(metadata: Mapping[str, Any] | None) -> dict[str, Any] | None:
    properties = intent_node_properties_from_metadata(metadata)
    payload = properties.get("vibecomfy")
    return dict(payload) if isinstance(payload, Mapping) else None


def validate_typed_io_spec(io_payload: Any) -> tuple[list[list[str]], list[IntentNodeProblem]]:
    problems: list[IntentNodeProblem] = []
    if not isinstance(io_payload, Mapping):
        return [], [IntentNodeProblem("missing_typed_io", "properties.vibecomfy.io must be a mapping")]
    normalized: list[list[str]] = []
    for key in ("inputs", "outputs"):
        value = io_payload.get(key)
        if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
            problems.append(
                IntentNodeProblem(
                    "typed_io_shape",
                    f"properties.vibecomfy.io.{key} must be a sequence of [name, type] pairs",
                    detail={"field": key},
                )
            )
            continue
        entries, entry_problems = _validate_typed_io_entries(key, value)
        normalized.extend(entries)
        problems.extend(entry_problems)
    return normalized, problems


def validate_intent_node_contract(
    *,
    node_id: str,
    class_type: str,
    metadata: Mapping[str, Any] | None,
) -> IntentNodeValidationResult:
    properties = intent_node_properties_from_metadata(metadata)
    payload = intent_node_payload_from_metadata(metadata)
    uid = properties.get("vibecomfy_uid")
    kind = payload.get("kind") if isinstance(payload, Mapping) else None
    problems: list[IntentNodeProblem] = []

    if not isinstance(uid, str) or not uid.strip():
        problems.append(
            IntentNodeProblem(
                "missing_uid",
                f"Node {node_id} ({class_type}) is missing properties.vibecomfy_uid.",
            )
        )

    expected_kind = CLASS_TYPE_TO_KIND.get(class_type)
    if payload is None:
        problems.append(
            IntentNodeProblem(
                "missing_payload",
                f"Node {node_id} ({class_type}) is missing properties.vibecomfy metadata.",
            )
        )
    else:
        if not isinstance(kind, str) or not kind:
            problems.append(
                IntentNodeProblem(
                    "missing_kind",
                    f"Node {node_id} ({class_type}) is missing properties.vibecomfy.kind.",
                )
            )
        elif kind not in SHIPPED_INTENT_KINDS:
            problems.append(
                IntentNodeProblem(
                    "unsupported_kind",
                    f"Node {node_id} ({class_type}) uses unsupported shipped kind {kind!r}.",
                    detail={"kind": kind, "shipped_kinds": list(SHIPPED_INTENT_KINDS)},
                )
            )
        elif expected_kind is not None and kind != expected_kind:
            problems.append(
                IntentNodeProblem(
                    "kind_class_mismatch",
                    (
                        f"Node {node_id} ({class_type}) declares kind {kind!r}; "
                        f"expected {expected_kind!r}."
                    ),
                    detail={"kind": kind, "expected_kind": expected_kind},
                )
            )

        _, io_problems = validate_typed_io_spec(payload.get("io"))
        problems.extend(io_problems)

        intent = payload.get("intent")
        if not isinstance(intent, Mapping):
            problems.append(
                IntentNodeProblem(
                    "missing_intent",
                    f"Node {node_id} ({class_type}) is missing properties.vibecomfy.intent.",
                )
            )
        elif kind == "code":
            problems.extend(_validate_code_intent(node_id=node_id, class_type=class_type, intent=intent))
        elif kind == "loop":
            problems.extend(_validate_loop_intent(node_id=node_id, class_type=class_type, intent=intent))

    return IntentNodeValidationResult(
        class_type=class_type,
        vibecomfy_uid=uid if isinstance(uid, str) and uid.strip() else None,
        kind=kind if isinstance(kind, str) else None,
        properties=properties,
        payload=payload,
        problems=tuple(problems),
    )


def _validate_code_intent(
    *,
    node_id: str,
    class_type: str,
    intent: Mapping[str, Any],
) -> list[IntentNodeProblem]:
    problems: list[IntentNodeProblem] = []
    source = intent.get("source")
    spec = intent.get("spec")
    if not isinstance(source, str) and not isinstance(spec, str):
        problems.append(
            IntentNodeProblem(
                "missing_code_payload",
                f"Node {node_id} ({class_type}) must declare intent.source or intent.spec.",
            )
        )
        return problems
    if isinstance(source, str):
        problems.extend(
            _check_text_bound(
                field="intent.source",
                value=source,
                max_bytes=INTENT_CODE_MAX_BYTES,
            )
        )
        report = scan_python_source_with_policy(
            source,
            phase=INTENT_NODE_VALIDATION_PHASE,
            max_source_bytes=INTENT_CODE_MAX_BYTES,
            max_ast_nodes=50_000,
        )
        for failure in report.failures:
            problems.append(
                IntentNodeProblem(
                    failure.code,
                    f"Node {node_id} ({class_type}) source failed AST safety scan: {failure.message}",
                    detail={
                        "line": failure.line,
                        "column": failure.column,
                        "phase": failure.phase,
                    },
                )
            )
    if isinstance(spec, str):
        problems.extend(
            _check_text_bound(
                field="intent.spec",
                value=spec,
                max_bytes=INTENT_SPEC_MAX_BYTES,
            )
        )
    return problems


def _validate_loop_intent(
    *,
    node_id: str,
    class_type: str,
    intent: Mapping[str, Any],
) -> list[IntentNodeProblem]:
    problems: list[IntentNodeProblem] = []
    var = intent.get("var")
    if not isinstance(var, str) or not var.strip():
        problems.append(
            IntentNodeProblem(
                "missing_loop_var",
                f"Node {node_id} ({class_type}) must declare a non-empty intent.var.",
            )
        )
    count = intent.get("count", intent.get("iterations"))
    over = intent.get("over")
    if isinstance(count, bool):
        count = int(count)
    if isinstance(count, int):
        if count < 1 or count > INTENT_LOOP_MAX_ITERATIONS:
            problems.append(
                IntentNodeProblem(
                    "loop_bound",
                    (
                        f"Node {node_id} ({class_type}) count/iterations must be between 1 and "
                        f"{INTENT_LOOP_MAX_ITERATIONS}."
                    ),
                    detail={"count": count, "max_iterations": INTENT_LOOP_MAX_ITERATIONS},
                )
            )
        return problems
    if isinstance(over, Sequence) and not isinstance(over, (str, bytes)):
        length = len(over)
        if length < 1 or length > INTENT_LOOP_MAX_ITERATIONS:
            problems.append(
                IntentNodeProblem(
                    "loop_bound",
                    (
                        f"Node {node_id} ({class_type}) over-list must contain between 1 and "
                        f"{INTENT_LOOP_MAX_ITERATIONS} items."
                    ),
                    detail={"count": length, "max_iterations": INTENT_LOOP_MAX_ITERATIONS},
                )
            )
        return problems
    problems.append(
        IntentNodeProblem(
            "missing_loop_bound",
            (
                f"Node {node_id} ({class_type}) must declare intent.count, intent.iterations, "
                "or a bounded intent.over sequence."
            ),
        )
    )
    return problems


def _check_text_bound(*, field: str, value: str, max_bytes: int) -> list[IntentNodeProblem]:
    encoded = value.encode("utf-8")
    if len(encoded) <= max_bytes:
        return []
    return [
        IntentNodeProblem(
            "text_too_large",
            f"{field} exceeds the {max_bytes}-byte limit.",
            detail={"field": field, "max_bytes": max_bytes, "actual_bytes": len(encoded)},
        )
    ]


def _normalize_typed_io_entries(label: str, entries: Sequence[Sequence[str]]) -> list[list[str]]:
    normalized, problems = _validate_typed_io_entries(label, entries)
    if problems:
        raise ValueError(problems[0].message)
    return normalized


def _validate_typed_io_entries(label: str, entries: Sequence[Sequence[str]]) -> tuple[list[list[str]], list[IntentNodeProblem]]:
    normalized: list[list[str]] = []
    problems: list[IntentNodeProblem] = []
    for index, entry in enumerate(entries):
        if not isinstance(entry, Sequence) or isinstance(entry, (str, bytes)) or len(entry) != 2:
            problems.append(
                IntentNodeProblem(
                    "typed_io_entry",
                    f"{label}[{index}] must be a [name, type] pair.",
                    detail={"field": label, "index": index},
                )
            )
            continue
        name, socket_type = entry
        if not isinstance(name, str) or not name.strip():
            problems.append(
                IntentNodeProblem(
                    "typed_io_entry",
                    f"{label}[{index}] name must be a non-empty string.",
                    detail={"field": label, "index": index},
                )
            )
            continue
        if not isinstance(socket_type, str) or not socket_type.strip():
            problems.append(
                IntentNodeProblem(
                    "typed_io_entry",
                    f"{label}[{index}] type must be a non-empty string.",
                    detail={"field": label, "index": index},
                )
            )
            continue
        normalized.append([name, socket_type])
    return normalized, problems


__all__ = [
    "ALL_INTENT_KINDS",
    "CLASS_TYPE_TO_KIND",
    "DEFERRED_INTENT_KINDS",
    "INTENT_CODE_MAX_BYTES",
    "INTENT_LOOP_MAX_ITERATIONS",
    "INTENT_NODE_CONTRACT_INVALID_CODE",
    "INTENT_NODE_EDITOR_ONLY_CODE",
    "INTENT_NODE_QUEUE_BLOCKER_CODE",
    "INTENT_SPEC_MAX_BYTES",
    "INTENT_NODE_VALIDATION_PHASE",
    "IntentNodeProblem",
    "IntentNodeValidationResult",
    "KIND_TO_CLASS_TYPE",
    "SHIPPED_INTENT_KINDS",
    "VIBECOMFY_INTENT_CLASS_RE",
    "intent_node_payload_from_metadata",
    "intent_node_properties",
    "intent_node_properties_from_metadata",
    "is_intent_class_type",
    "validate_intent_node_contract",
    "validate_typed_io_spec",
]
