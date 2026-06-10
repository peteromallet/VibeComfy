from __future__ import annotations

import ast
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
import re
from typing import Any, Final

from vibecomfy.security.agent_generated_loader import ScanFailure, ScanReport, scan_python_source_with_policy

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
MAX_DYNAMIC_PORTS: Final[int] = 16

INTENT_NODE_VALIDATION_PHASE: Final[str] = "intent_node_validate"
RUNTIME_CODE_CONTRACT_VERSION: Final[str] = "runtime_code_v1"
RUNTIME_CODE_EXECUTION_MODE: Final[str] = "expression_v1"
RUNTIME_CODE_POLICY_VERSION: Final[str] = "runtime_code_policy_v1"
RUNTIME_CODE_TIMEOUT_MS_MIN: Final[int] = 1
RUNTIME_CODE_TIMEOUT_MS_MAX: Final[int] = 10_000

EXECUTION_MODE_SANDBOXED_LOOSE: Final[str] = "sandboxed_loose"
EXECUTION_MODE_SANDBOXED_STRICT: Final[str] = "sandboxed_strict"
EXECUTION_MODE_UNRESTRICTED: Final[str] = "unrestricted"

_NEW_EXECUTION_MODES: Final[frozenset[str]] = frozenset(
    {
        EXECUTION_MODE_SANDBOXED_LOOSE,
        EXECUTION_MODE_SANDBOXED_STRICT,
        EXECUTION_MODE_UNRESTRICTED,
    }
)
_ALL_EXECUTION_MODES: Final[frozenset[str]] = _NEW_EXECUTION_MODES | {RUNTIME_CODE_EXECUTION_MODE}

RUNTIME_CODE_MAX_SOURCE_BYTES_NEW: Final[int] = 65_536
RUNTIME_CODE_UNRESTRICTED_ACK_ERROR: Final[str] = "runtime_unrestricted_requires_ack"
RUNTIME_CODE_ALLOWED_IO_TYPES: Final[frozenset[str]] = frozenset(
    {
        "BOOLEAN",
        "BOOL",
        "FLOAT",
        "INT",
        "INTEGER",
        "JSON",
        "NUMBER",
        "STRING",
    }
)
RUNTIME_CODE_SAFE_BUILTINS: Final[frozenset[str]] = frozenset(
    {
        "abs",
        "all",
        "any",
        "bool",
        "dict",
        "float",
        "int",
        "len",
        "list",
        "max",
        "min",
        "round",
        "sorted",
        "str",
        "sum",
        "tuple",
    }
)
RUNTIME_CODE_BROAD_BUILTINS: Final[frozenset[str]] = RUNTIME_CODE_SAFE_BUILTINS | frozenset(
    {
        "print",
        "range",
        "enumerate",
        "zip",
        "map",
        "filter",
        "set",
        "frozenset",
        "reversed",
        "divmod",
        "pow",
        "hex",
        "oct",
        "bin",
        "ord",
        "chr",
        "repr",
        "isinstance",
        "issubclass",
        "type",
        "hash",
        "id",
        "iter",
        "next",
    }
)
RUNTIME_CODE_LOOSE_ALLOWED_IMPORTS: Final[frozenset[str]] = frozenset(
    {
        "math",
        "statistics",
        "re",
        "json",
        "random",
        "itertools",
        "datetime",
    }
)

# Per-mode policy tables. `None` is a sentinel meaning "no filter" (unrestricted).
# Legacy ``expression_v1`` keeps its hardcoded behaviour and is intentionally absent
# from these tables — callers that need legacy semantics use the literal constants.
_BUILTINS_BY_MODE: Final[dict[str, frozenset[str] | None]] = {
    EXECUTION_MODE_SANDBOXED_LOOSE: RUNTIME_CODE_BROAD_BUILTINS,
    EXECUTION_MODE_SANDBOXED_STRICT: RUNTIME_CODE_BROAD_BUILTINS,
    EXECUTION_MODE_UNRESTRICTED: None,
}
_ALLOWED_IMPORTS_BY_MODE: Final[dict[str, frozenset[str] | None]] = {
    EXECUTION_MODE_SANDBOXED_LOOSE: RUNTIME_CODE_LOOSE_ALLOWED_IMPORTS,
    EXECUTION_MODE_SANDBOXED_STRICT: frozenset(),
    EXECUTION_MODE_UNRESTRICTED: None,
}
_TIMEOUT_MS_DEFAULT_BY_MODE: Final[dict[str, int]] = {
    EXECUTION_MODE_SANDBOXED_LOOSE: 10_000,
    EXECUTION_MODE_SANDBOXED_STRICT: 10_000,
    EXECUTION_MODE_UNRESTRICTED: 10_000,
}
_MAX_SOURCE_BYTES_BY_MODE: Final[dict[str, int]] = {
    EXECUTION_MODE_SANDBOXED_LOOSE: RUNTIME_CODE_MAX_SOURCE_BYTES_NEW,
    EXECUTION_MODE_SANDBOXED_STRICT: RUNTIME_CODE_MAX_SOURCE_BYTES_NEW,
    EXECUTION_MODE_UNRESTRICTED: RUNTIME_CODE_MAX_SOURCE_BYTES_NEW,
}
RUNTIME_CODE_FORBIDDEN_NAMES: Final[frozenset[str]] = frozenset(
    {
        "__builtins__",
        "__import__",
        "breakpoint",
        "compile",
        "delattr",
        "dir",
        "eval",
        "exec",
        "getattr",
        "globals",
        "locals",
        "open",
        "setattr",
        "vars",
        "os",
        "sys",
        "subprocess",
        "socket",
        "requests",
        "urllib",
        "http",
        "pathlib",
        "importlib",
        "inspect",
    }
)
RUNTIME_CODE_ALLOWED_EXPRESSION_NODES: Final[tuple[type[ast.AST], ...]] = (
    ast.Expression,
    ast.BoolOp,
    ast.BinOp,
    ast.UnaryOp,
    ast.IfExp,
    ast.Dict,
    ast.Set,
    ast.Compare,
    ast.Call,
    ast.FormattedValue,
    ast.JoinedStr,
    ast.Constant,
    ast.Attribute,
    ast.Subscript,
    ast.Name,
    ast.List,
    ast.Tuple,
    ast.Slice,
    ast.Load,
    ast.And,
    ast.Or,
    ast.Add,
    ast.Sub,
    ast.Mult,
    ast.Div,
    ast.FloorDiv,
    ast.Mod,
    ast.Pow,
    ast.LShift,
    ast.RShift,
    ast.BitOr,
    ast.BitXor,
    ast.BitAnd,
    ast.MatMult,
    ast.Invert,
    ast.Not,
    ast.UAdd,
    ast.USub,
    ast.Eq,
    ast.NotEq,
    ast.Lt,
    ast.LtE,
    ast.Gt,
    ast.GtE,
    ast.Is,
    ast.IsNot,
    ast.In,
    ast.NotIn,
    ast.comprehension,
)
RUNTIME_CODE_REJECTED_IO_TYPES: Final[frozenset[str]] = frozenset(
    {
        "*",
        "ANY",
        "CONDITIONING",
        "IMAGE",
        "LATENT",
        "MASK",
        "MODEL",
        "TENSOR",
        "VAE",
    }
)

KIND_TO_CLASS_TYPE: Final[dict[str, str]] = {
    "code": "vibecomfy.code",
    "loop": "vibecomfy.loop",
}
CLASS_TYPE_TO_KIND: Final[dict[str, str]] = {
    class_type: kind for kind, class_type in KIND_TO_CLASS_TYPE.items()
}
INTENT_CLASS_TYPES: Final[frozenset[str]] = frozenset(
    f"vibecomfy.{kind}" for kind in ALL_INTENT_KINDS
)


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


@dataclass(frozen=True, slots=True)
class NormalizedRuntimeCodeContract:
    runtime_backed: bool
    runtime_contract_version: str
    execution_mode: str
    timeout_ms: int
    max_source_bytes: int
    allowed_builtins: tuple[str, ...]
    redaction_policy: tuple[str, ...]
    policy_version: str
    passthrough_on_non_json: bool = False

    def as_dict(self) -> dict[str, Any]:
        return {
            "runtime_backed": self.runtime_backed,
            "runtime_contract_version": self.runtime_contract_version,
            "execution_mode": self.execution_mode,
            "timeout_ms": self.timeout_ms,
            "max_source_bytes": self.max_source_bytes,
            "allowed_builtins": list(self.allowed_builtins),
            "redaction_policy": list(self.redaction_policy),
            "policy_version": self.policy_version,
            "passthrough_on_non_json": self.passthrough_on_non_json,
        }


@dataclass(frozen=True, slots=True)
class RuntimeCodeContractValidationResult:
    normalized: NormalizedRuntimeCodeContract | None
    problems: tuple[IntentNodeProblem, ...] = ()

    @property
    def ok(self) -> bool:
        return not self.problems


def is_intent_class_type(class_type: str) -> bool:
    return class_type in INTENT_CLASS_TYPES


def resolve_execution_mode(runtime_block: Any) -> str:
    """Resolve the execution mode for a runtime block.

    Returns the explicit ``execution_mode`` when set; otherwise ``expression_v1``
    when the block looks legacy (no ``execution_mode`` and ``allowed_builtins``
    matches the legacy 16-name safe set); otherwise ``sandboxed_loose``.
    """

    if not isinstance(runtime_block, Mapping):
        return EXECUTION_MODE_SANDBOXED_LOOSE
    explicit = runtime_block.get("execution_mode")
    if isinstance(explicit, str) and explicit.strip():
        return explicit
    allowed = runtime_block.get("allowed_builtins")
    if isinstance(allowed, Sequence) and not isinstance(allowed, (str, bytes)):
        try:
            allowed_set = frozenset(item for item in allowed if isinstance(item, str))
        except TypeError:
            allowed_set = frozenset()
        if allowed_set == RUNTIME_CODE_SAFE_BUILTINS:
            return RUNTIME_CODE_EXECUTION_MODE
    return EXECUTION_MODE_SANDBOXED_LOOSE


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
        if len(value) > MAX_DYNAMIC_PORTS:
            problems.append(
                IntentNodeProblem(
                    "runtime_io_exceeds_max_ports",
                    f"properties.vibecomfy.io.{key} has {len(value)} entries; "
                    f"dynamic intent nodes support at most {MAX_DYNAMIC_PORTS} ports per side.",
                    detail={"field": key, "count": len(value), "max": MAX_DYNAMIC_PORTS},
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
            problems.extend(
                _validate_code_intent(
                    node_id=node_id,
                    class_type=class_type,
                    intent=intent,
                    runtime=payload.get("runtime") if isinstance(payload, Mapping) else None,
                )
            )
            runtime_result = validate_runtime_code_contract(
                class_type=class_type,
                payload=payload,
                require_runtime=False,
            )
            problems.extend(runtime_result.problems)
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


def validate_runtime_code_contract(
    *,
    class_type: str,
    payload: Mapping[str, Any] | None,
    require_runtime: bool = True,
) -> RuntimeCodeContractValidationResult:
    if payload is None:
        return RuntimeCodeContractValidationResult(
            normalized=None,
            problems=(IntentNodeProblem("missing_payload", "Runtime-backed code requires properties.vibecomfy metadata."),),
        )

    runtime = payload.get("runtime")
    if runtime is None:
        if require_runtime:
            return RuntimeCodeContractValidationResult(
                normalized=None,
                problems=(
                    IntentNodeProblem(
                        "missing_runtime_contract",
                        "Runtime-backed vibecomfy.code requires properties.vibecomfy.runtime.",
                    ),
                ),
            )
        return RuntimeCodeContractValidationResult(normalized=None)
    if not isinstance(runtime, Mapping):
        return RuntimeCodeContractValidationResult(
            normalized=None,
            problems=(
                IntentNodeProblem(
                    "runtime_contract_shape",
                    "properties.vibecomfy.runtime must be a mapping.",
                ),
            ),
        )

    runtime_backed = runtime.get("runtime_backed")
    if runtime_backed is not True:
        if runtime_backed is False and not require_runtime:
            return RuntimeCodeContractValidationResult(normalized=None)
        return RuntimeCodeContractValidationResult(
            normalized=None,
            problems=(
                IntentNodeProblem(
                    "runtime_backed_required",
                    "Runtime code contracts must set runtime_backed=true.",
                    detail={"runtime_backed": runtime_backed},
                ),
            ),
        )

    problems: list[IntentNodeProblem] = []
    if class_type != KIND_TO_CLASS_TYPE["code"]:
        problems.append(
            IntentNodeProblem(
                "runtime_kind_unsupported",
                "Only vibecomfy.code can declare a runtime-backed contract.",
                detail={"class_type": class_type, "supported_class_type": KIND_TO_CLASS_TYPE["code"]},
            )
        )

    intent = payload.get("intent")
    if not isinstance(intent, Mapping):
        problems.append(IntentNodeProblem("missing_intent", "Runtime-backed code requires properties.vibecomfy.intent."))
    else:
        if not isinstance(intent.get("source"), str) and not isinstance(intent.get("spec"), str):
            problems.append(
                IntentNodeProblem(
                    "missing_code_payload",
                    "Runtime-backed code requires queue-visible intent.source or intent.spec.",
                )
            )

    _, io_problems = validate_typed_io_spec(payload.get("io"))
    problems.extend(io_problems)
    if isinstance(payload.get("io"), Mapping):
        problems.extend(_validate_runtime_json_io(payload["io"]))

    runtime_contract_version = _required_string(runtime, "runtime_contract_version", problems)
    execution_mode = _required_string(runtime, "execution_mode", problems)
    policy_version = _required_string(runtime, "policy_version", problems)
    timeout_ms = _required_int(runtime, "timeout_ms", problems)
    max_source_bytes = _required_int(runtime, "max_source_bytes", problems)
    allowed_builtins = _required_string_sequence(runtime, "allowed_builtins", problems)
    redaction_policy = _required_string_sequence(runtime, "redaction_policy", problems)
    passthrough_on_non_json = runtime.get("passthrough_on_non_json", False)
    source = intent.get("source") if isinstance(intent, Mapping) else None

    if runtime_contract_version is not None and runtime_contract_version != RUNTIME_CODE_CONTRACT_VERSION:
        problems.append(
            IntentNodeProblem(
                "unsupported_runtime_contract_version",
                f"Unsupported runtime contract version {runtime_contract_version!r}.",
                detail={"supported": RUNTIME_CODE_CONTRACT_VERSION, "actual": runtime_contract_version},
            )
        )
    if execution_mode is not None and execution_mode not in _ALL_EXECUTION_MODES:
        problems.append(
            IntentNodeProblem(
                "unsupported_execution_mode",
                f"Unsupported runtime code execution mode {execution_mode!r}.",
                detail={"supported": sorted(_ALL_EXECUTION_MODES), "actual": execution_mode},
            )
        )
    if policy_version is not None and policy_version != RUNTIME_CODE_POLICY_VERSION:
        problems.append(
            IntentNodeProblem(
                "unsupported_policy_version",
                f"Unsupported runtime code policy version {policy_version!r}.",
                detail={"supported": RUNTIME_CODE_POLICY_VERSION, "actual": policy_version},
            )
        )
    # When ``execution_mode`` is explicit but invalid (already flagged at the
    # line-494 gate), fall back to the legacy ``expression_v1`` grammar for
    # downstream caps and scanner dispatch so we don't double-report a
    # ``runtime_mode_invalid`` from the scanner on top of
    # ``unsupported_execution_mode``.
    if execution_mode in _ALL_EXECUTION_MODES:
        resolved_mode = execution_mode
    elif execution_mode is None:
        resolved_mode = resolve_execution_mode(runtime)
    else:
        resolved_mode = RUNTIME_CODE_EXECUTION_MODE
    if allowed_builtins is not None:
        permitted_builtins = _BUILTINS_BY_MODE.get(resolved_mode, RUNTIME_CODE_SAFE_BUILTINS)
        if permitted_builtins is not None:
            unsupported_builtins = sorted(set(allowed_builtins) - permitted_builtins)
            if unsupported_builtins:
                problems.append(
                    IntentNodeProblem(
                        "runtime_allowed_builtin_unsupported",
                        (
                            f"runtime.allowed_builtins contains names outside the "
                            f"{resolved_mode} safe builtin allowlist."
                        ),
                        detail={"unsupported": unsupported_builtins, "mode": resolved_mode},
                    )
                )
    if timeout_ms is not None and not (RUNTIME_CODE_TIMEOUT_MS_MIN <= timeout_ms <= RUNTIME_CODE_TIMEOUT_MS_MAX):
        problems.append(
            IntentNodeProblem(
                "runtime_timeout_bounds",
                f"runtime.timeout_ms must be between {RUNTIME_CODE_TIMEOUT_MS_MIN} and {RUNTIME_CODE_TIMEOUT_MS_MAX}.",
                detail={"timeout_ms": timeout_ms},
            )
        )
    if resolved_mode in _NEW_EXECUTION_MODES:
        mode_source_cap = _MAX_SOURCE_BYTES_BY_MODE.get(resolved_mode, RUNTIME_CODE_MAX_SOURCE_BYTES_NEW)
    else:
        mode_source_cap = INTENT_CODE_MAX_BYTES
    if max_source_bytes is not None:
        if max_source_bytes < 1 or max_source_bytes > mode_source_cap:
            problems.append(
                IntentNodeProblem(
                    "runtime_source_bounds",
                    f"runtime.max_source_bytes must be between 1 and {mode_source_cap}.",
                    detail={"max_source_bytes": max_source_bytes, "mode": resolved_mode},
                )
            )
        if isinstance(source, str) and len(source.encode("utf-8")) > max_source_bytes:
            problems.append(
                IntentNodeProblem(
                    "runtime_source_too_large",
                    "intent.source exceeds runtime.max_source_bytes.",
                    detail={"max_source_bytes": max_source_bytes, "actual_bytes": len(source.encode("utf-8"))},
                )
            )
    if resolved_mode == EXECUTION_MODE_UNRESTRICTED and runtime.get("unrestricted_ack") is not True:
        problems.append(
            IntentNodeProblem(
                RUNTIME_CODE_UNRESTRICTED_ACK_ERROR,
                "Unrestricted execution mode requires runtime.unrestricted_ack=true.",
                detail={"mode": EXECUTION_MODE_UNRESTRICTED},
            )
        )
    source_within_runtime_limit = not (
        isinstance(source, str)
        and max_source_bytes is not None
        and len(source.encode("utf-8")) > max_source_bytes
    )
    if isinstance(source, str) and source_within_runtime_limit:
        scan_allowed_imports = _ALLOWED_IMPORTS_BY_MODE.get(resolved_mode, frozenset())
        runtime_policy_report = scan_runtime_code_source(
            source,
            mode=resolved_mode,
            input_names=_runtime_io_names(payload.get("io"), "inputs"),
            allowed_builtins=allowed_builtins or (),
            allowed_imports=scan_allowed_imports,
            max_source_bytes=max_source_bytes or mode_source_cap,
        )
        for failure in runtime_policy_report.failures:
            problems.append(
                IntentNodeProblem(
                    failure.code,
                    f"Runtime-backed code source failed policy ({resolved_mode}): {failure.message}",
                    detail={
                        "line": failure.line,
                        "column": failure.column,
                        "phase": failure.phase,
                        "mode": resolved_mode,
                    },
                )
            )
    if not isinstance(passthrough_on_non_json, bool):
        problems.append(
            IntentNodeProblem(
                "runtime_passthrough_shape",
                "runtime.passthrough_on_non_json must be a boolean when present.",
            )
        )
    elif passthrough_on_non_json:
        problems.append(
            IntentNodeProblem(
                "runtime_non_json_passthrough_unsupported",
                "Runtime-backed code must reject non-JSON outputs; passthrough_on_non_json must be false.",
            )
        )

    if problems:
        return RuntimeCodeContractValidationResult(normalized=None, problems=tuple(problems))

    return RuntimeCodeContractValidationResult(
        normalized=NormalizedRuntimeCodeContract(
            runtime_backed=True,
            runtime_contract_version=runtime_contract_version or RUNTIME_CODE_CONTRACT_VERSION,
            execution_mode=execution_mode or RUNTIME_CODE_EXECUTION_MODE,
            timeout_ms=timeout_ms if timeout_ms is not None else 0,
            max_source_bytes=max_source_bytes if max_source_bytes is not None else 0,
            allowed_builtins=tuple(allowed_builtins or ()),
            redaction_policy=tuple(redaction_policy or ()),
            policy_version=policy_version or RUNTIME_CODE_POLICY_VERSION,
            passthrough_on_non_json=False,
        )
    )


def scan_runtime_code_source(
    source: str,
    *,
    mode: str = RUNTIME_CODE_EXECUTION_MODE,
    input_names: Sequence[str] = (),
    allowed_builtins: Sequence[str] = (),
    allowed_imports: Sequence[str] | frozenset[str] = (),
    max_source_bytes: int = INTENT_CODE_MAX_BYTES,
) -> ScanReport:
    """Mode-aware static scan of runtime-backed code prior to execution.

    Mode dispatch:
    - ``expression_v1``: single-expression eval grammar + safe-builtin allowlist
      (byte-identical to the legacy scanner).
    - ``sandboxed_strict``: multi-line exec grammar; rejects any Import/ImportFrom,
      dunder attribute access, and forbidden names.
    - ``sandboxed_loose``: multi-line exec grammar; allows Import/ImportFrom only
      when the module is in ``allowed_imports``; rejects dunder access and forbidden
      names.
    - ``unrestricted``: syntax-only validation + the source-size cap.
    """

    if not isinstance(source, str):
        return ScanReport(
            ok=False,
            failures=(
                ScanFailure(
                    code="source_type",
                    message=f"source must be str, got {type(source).__name__}",
                    phase=INTENT_NODE_VALIDATION_PHASE,
                ),
            ),
        )
    if len(source.encode("utf-8")) > max_source_bytes:
        return ScanReport(
            ok=False,
            failures=(
                ScanFailure(
                    code="source_too_large",
                    message=f"Python source exceeds {max_source_bytes} bytes",
                    phase=INTENT_NODE_VALIDATION_PHASE,
                ),
            ),
        )

    if mode == RUNTIME_CODE_EXECUTION_MODE:
        return _scan_expression_v1(
            source,
            input_names=input_names,
            allowed_builtins=allowed_builtins,
        )
    if mode in (EXECUTION_MODE_SANDBOXED_STRICT, EXECUTION_MODE_SANDBOXED_LOOSE):
        return _scan_sandboxed(
            source,
            mode=mode,
            allowed_imports=frozenset(allowed_imports) if allowed_imports else frozenset(),
        )
    if mode == EXECUTION_MODE_UNRESTRICTED:
        return _scan_unrestricted(source)
    return ScanReport(
        ok=False,
        failures=(
            ScanFailure(
                code="runtime_mode_invalid",
                message=f"unknown execution mode {mode!r}",
                phase=INTENT_NODE_VALIDATION_PHASE,
            ),
        ),
    )


def scan_runtime_code_expression(
    source: str,
    *,
    input_names: Sequence[str],
    allowed_builtins: Sequence[str],
    max_source_bytes: int,
) -> ScanReport:
    """Back-compat wrapper around :func:`scan_runtime_code_source` for ``expression_v1``.

    External callers and tests imported this name historically; new code should call
    :func:`scan_runtime_code_source` directly.
    """

    return scan_runtime_code_source(
        source,
        mode=RUNTIME_CODE_EXECUTION_MODE,
        input_names=input_names,
        allowed_builtins=allowed_builtins,
        max_source_bytes=max_source_bytes,
    )


def _scan_expression_v1(
    source: str,
    *,
    input_names: Sequence[str],
    allowed_builtins: Sequence[str],
) -> ScanReport:
    try:
        tree = ast.parse(source, filename="<runtime_code_expression>", mode="eval")
    except SyntaxError as exc:
        try:
            ast.parse(source, filename="<runtime_code_expression>", mode="exec")
        except SyntaxError:
            code = "syntax_error"
            message = exc.msg
        else:
            code = "forbidden_statement"
            message = "runtime-backed code supports exactly one Python expression, not statements"
        return ScanReport(
            ok=False,
            failures=(
                ScanFailure(
                    code=code,
                    message=message,
                    phase=INTENT_NODE_VALIDATION_PHASE,
                    line=exc.lineno,
                    column=exc.offset,
                ),
            ),
        )

    allowed_call_names = frozenset(allowed_builtins) & RUNTIME_CODE_SAFE_BUILTINS
    visitor = _RuntimeCodeExpressionPolicy(
        input_names=frozenset(input_names),
        allowed_call_names=allowed_call_names,
    )
    visitor.visit(tree)
    return ScanReport(ok=not visitor.failures, failures=tuple(visitor.failures))


def _scan_sandboxed(
    source: str,
    *,
    mode: str,
    allowed_imports: frozenset[str],
) -> ScanReport:
    try:
        tree = ast.parse(source, filename="<runtime_code_source>", mode="exec")
    except SyntaxError as exc:
        return ScanReport(
            ok=False,
            failures=(
                ScanFailure(
                    code="syntax_error",
                    message=exc.msg or "syntax error",
                    phase=INTENT_NODE_VALIDATION_PHASE,
                    line=exc.lineno,
                    column=exc.offset,
                ),
            ),
        )
    visitor = _RuntimeCodeSandboxPolicy(
        mode=mode,
        allowed_imports=allowed_imports,
    )
    visitor.visit(tree)
    return ScanReport(ok=not visitor.failures, failures=tuple(visitor.failures))


def _scan_unrestricted(source: str) -> ScanReport:
    try:
        ast.parse(source, filename="<runtime_code_source>", mode="exec")
    except SyntaxError as exc:
        return ScanReport(
            ok=False,
            failures=(
                ScanFailure(
                    code="syntax_error",
                    message=exc.msg or "syntax error",
                    phase=INTENT_NODE_VALIDATION_PHASE,
                    line=exc.lineno,
                    column=exc.offset,
                ),
            ),
        )
    return ScanReport(ok=True, failures=())


class _RuntimeCodeSandboxPolicy(ast.NodeVisitor):
    """Static policy check for ``sandboxed_strict`` and ``sandboxed_loose`` modes.

    Forbidden-name checks apply to ``Name`` *loads* only — write targets (loop
    variables, ``outputs['k']=`` etc.) are allowed, otherwise legitimate code
    cannot bind locals named after dangerous builtins.
    """

    def __init__(self, *, mode: str, allowed_imports: frozenset[str]) -> None:
        self.mode = mode
        self.allowed_imports = allowed_imports
        self.failures: list[ScanFailure] = []

    def visit_Import(self, node: ast.Import) -> None:
        if self.mode == EXECUTION_MODE_SANDBOXED_STRICT:
            self._fail(
                node,
                "runtime_import_forbidden",
                "import statements are not allowed in sandboxed_strict mode",
            )
            return
        for alias in node.names:
            module_root = alias.name.split(".", 1)[0]
            if module_root not in self.allowed_imports:
                self._fail(
                    node,
                    "runtime_import_forbidden",
                    f"import of {alias.name!r} is not in the sandboxed_loose import allowlist",
                )

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        if self.mode == EXECUTION_MODE_SANDBOXED_STRICT:
            self._fail(
                node,
                "runtime_import_forbidden",
                "import statements are not allowed in sandboxed_strict mode",
            )
            return
        module_root = (node.module or "").split(".", 1)[0]
        if not module_root or module_root not in self.allowed_imports:
            self._fail(
                node,
                "runtime_import_forbidden",
                f"from-import of {node.module!r} is not in the sandboxed_loose import allowlist",
            )

    def visit_Attribute(self, node: ast.Attribute) -> None:
        if node.attr.startswith("__"):
            self._fail(node, "dunder_access", f"dunder attribute {node.attr!r} is not allowed")
        self.generic_visit(node)

    def visit_Name(self, node: ast.Name) -> None:
        if not isinstance(node.ctx, ast.Load):
            return
        if node.id.startswith("__"):
            self._fail(node, "dunder_access", f"{node.id!r} is not allowed")
            return
        if node.id in RUNTIME_CODE_FORBIDDEN_NAMES:
            self._fail(node, "forbidden_name", f"{node.id!r} is not allowed")

    def _fail(self, node: ast.AST, code: str, message: str) -> None:
        self.failures.append(
            ScanFailure(
                code=code,
                message=message,
                phase=INTENT_NODE_VALIDATION_PHASE,
                line=getattr(node, "lineno", None),
                column=getattr(node, "col_offset", None),
            )
        )


class _RuntimeCodeExpressionPolicy(ast.NodeVisitor):
    def __init__(self, *, input_names: frozenset[str], allowed_call_names: frozenset[str]) -> None:
        self.input_names = input_names
        self.allowed_call_names = allowed_call_names
        self.failures: list[ScanFailure] = []

    def visit(self, node: ast.AST) -> Any:
        if not isinstance(node, RUNTIME_CODE_ALLOWED_EXPRESSION_NODES):
            self._fail(
                node,
                "forbidden_node",
                f"{type(node).__name__} is not allowed in runtime-backed expression_v1 code",
            )
            return None
        return super().visit(node)

    def visit_Name(self, node: ast.Name) -> None:
        if node.id.startswith("__"):
            self._fail(node, "dunder_access", f"{node.id!r} is not allowed")
            return
        if node.id in RUNTIME_CODE_FORBIDDEN_NAMES:
            self._fail(node, "forbidden_name", f"{node.id!r} is not allowed")
            return
        if node.id in self.input_names or node.id in self.allowed_call_names:
            return
        self._fail(node, "forbidden_name", f"{node.id!r} is not a declared input or allowed builtin")

    def visit_Attribute(self, node: ast.Attribute) -> None:
        if node.attr.startswith("__"):
            self._fail(node, "dunder_access", f"dunder attribute {node.attr!r} is not allowed")
        else:
            self._fail(node, "forbidden_attribute", "attribute access is not allowed in expression_v1")

    def visit_Call(self, node: ast.Call) -> None:
        if not isinstance(node.func, ast.Name) or node.func.id not in self.allowed_call_names:
            self._fail(node, "forbidden_call", "only explicitly allowed builtin function calls are allowed")
            return
        self.generic_visit(node)

    def _fail(self, node: ast.AST, code: str, message: str) -> None:
        self.failures.append(
            ScanFailure(
                code=code,
                message=message,
                phase=INTENT_NODE_VALIDATION_PHASE,
                line=getattr(node, "lineno", None),
                column=getattr(node, "col_offset", None),
            )
        )


def _validate_code_intent(
    *,
    node_id: str,
    class_type: str,
    intent: Mapping[str, Any],
    runtime: Mapping[str, Any] | None = None,
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
    resolved_mode = resolve_execution_mode(runtime) if runtime is not None else RUNTIME_CODE_EXECUTION_MODE
    if resolved_mode in _NEW_EXECUTION_MODES:
        source_cap = _MAX_SOURCE_BYTES_BY_MODE.get(resolved_mode, RUNTIME_CODE_MAX_SOURCE_BYTES_NEW)
    else:
        source_cap = INTENT_CODE_MAX_BYTES
    if isinstance(source, str):
        problems.extend(
            _check_text_bound(
                field="intent.source",
                value=source,
                max_bytes=source_cap,
            )
        )
        # The legacy AST-safety scan is the only static defense for the legacy
        # ``expression_v1`` payload shape. New-mode payloads (sandboxed_* and
        # unrestricted) are scanned by the mode-aware
        # :func:`scan_runtime_code_source` inside
        # :func:`validate_runtime_code_contract`; the legacy scan rejects
        # ``import`` outright and would erroneously block valid sandboxed_loose
        # source.
        if resolved_mode not in _NEW_EXECUTION_MODES:
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


def _validate_runtime_json_io(io_payload: Mapping[str, Any]) -> list[IntentNodeProblem]:
    problems: list[IntentNodeProblem] = []
    for label in ("inputs", "outputs"):
        value = io_payload.get(label)
        if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
            continue
        entries, entry_problems = _validate_typed_io_entries(label, value)
        if entry_problems:
            continue
        for name, socket_type in entries:
            normalized = socket_type.strip().upper()
            if normalized in RUNTIME_CODE_ALLOWED_IO_TYPES:
                continue
            if normalized in RUNTIME_CODE_REJECTED_IO_TYPES or "TENSOR" in normalized:
                problems.append(
                    IntentNodeProblem(
                        "runtime_non_json_io",
                        "Runtime-backed code only supports JSON-compatible declared IO types.",
                        detail={"field": label, "name": name, "type": socket_type},
                    )
                )
            else:
                problems.append(
                    IntentNodeProblem(
                        "runtime_unknown_io_type",
                        "Runtime-backed code IO types must be explicitly JSON-compatible.",
                        detail={"field": label, "name": name, "type": socket_type},
                    )
                )
    return problems


def _runtime_io_names(io_payload: Any, label: str) -> tuple[str, ...]:
    if not isinstance(io_payload, Mapping):
        return ()
    value = io_payload.get(label)
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        return ()
    names: list[str] = []
    for entry in value:
        if (
            isinstance(entry, Sequence)
            and not isinstance(entry, (str, bytes))
            and len(entry) >= 2
            and isinstance(entry[0], str)
            and entry[0].strip()
        ):
            names.append(entry[0])
    return tuple(names)


def _required_string(
    runtime: Mapping[str, Any],
    field_name: str,
    problems: list[IntentNodeProblem],
) -> str | None:
    value = runtime.get(field_name)
    if isinstance(value, str) and value.strip():
        return value
    problems.append(
        IntentNodeProblem(
            "runtime_field_required",
            f"runtime.{field_name} must be a non-empty string.",
            detail={"field": field_name},
        )
    )
    return None


def _required_int(
    runtime: Mapping[str, Any],
    field_name: str,
    problems: list[IntentNodeProblem],
) -> int | None:
    value = runtime.get(field_name)
    if isinstance(value, bool) or not isinstance(value, int):
        problems.append(
            IntentNodeProblem(
                "runtime_field_required",
                f"runtime.{field_name} must be an integer.",
                detail={"field": field_name},
            )
        )
        return None
    return value


def _required_string_sequence(
    runtime: Mapping[str, Any],
    field_name: str,
    problems: list[IntentNodeProblem],
) -> tuple[str, ...] | None:
    value = runtime.get(field_name)
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        problems.append(
            IntentNodeProblem(
                "runtime_field_required",
                f"runtime.{field_name} must be a sequence of strings.",
                detail={"field": field_name},
            )
        )
        return None
    strings: list[str] = []
    for index, item in enumerate(value):
        if not isinstance(item, str) or not item.strip():
            problems.append(
                IntentNodeProblem(
                    "runtime_field_required",
                    f"runtime.{field_name}[{index}] must be a non-empty string.",
                    detail={"field": field_name, "index": index},
                )
            )
            return None
        strings.append(item)
    return tuple(strings)


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
    "EXECUTION_MODE_SANDBOXED_LOOSE",
    "EXECUTION_MODE_SANDBOXED_STRICT",
    "EXECUTION_MODE_UNRESTRICTED",
    "INTENT_CODE_MAX_BYTES",
    "INTENT_LOOP_MAX_ITERATIONS",
    "MAX_DYNAMIC_PORTS",
    "INTENT_NODE_CONTRACT_INVALID_CODE",
    "INTENT_NODE_EDITOR_ONLY_CODE",
    "INTENT_NODE_QUEUE_BLOCKER_CODE",
    "INTENT_CLASS_TYPES",
    "INTENT_SPEC_MAX_BYTES",
    "INTENT_NODE_VALIDATION_PHASE",
    "IntentNodeProblem",
    "IntentNodeValidationResult",
    "KIND_TO_CLASS_TYPE",
    "NormalizedRuntimeCodeContract",
    "RUNTIME_CODE_BROAD_BUILTINS",
    "RUNTIME_CODE_CONTRACT_VERSION",
    "RUNTIME_CODE_EXECUTION_MODE",
    "RUNTIME_CODE_LOOSE_ALLOWED_IMPORTS",
    "RUNTIME_CODE_MAX_SOURCE_BYTES_NEW",
    "RUNTIME_CODE_POLICY_VERSION",
    "RUNTIME_CODE_UNRESTRICTED_ACK_ERROR",
    "RuntimeCodeContractValidationResult",
    "SHIPPED_INTENT_KINDS",
    "VIBECOMFY_INTENT_CLASS_RE",
    "intent_node_payload_from_metadata",
    "intent_node_properties",
    "intent_node_properties_from_metadata",
    "is_intent_class_type",
    "resolve_execution_mode",
    "scan_runtime_code_expression",
    "scan_runtime_code_source",
    "validate_intent_node_contract",
    "validate_runtime_code_contract",
    "validate_typed_io_spec",
]
