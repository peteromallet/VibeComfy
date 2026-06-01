from __future__ import annotations

import json
import os
import resource
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from typing import Any, Final

from vibecomfy.contracts.intent_nodes import (
    KIND_TO_CLASS_TYPE,
    intent_node_properties,
    validate_runtime_code_contract,
)

_WORKER_MAX_STDOUT_BYTES: Final[int] = 64 * 1024
_WORKER_MAX_STDERR_BYTES: Final[int] = 16 * 1024


@dataclass(frozen=True, slots=True)
class RuntimeCodeExecutionError(RuntimeError):
    code: str
    message: str
    detail: dict[str, Any] | None = None

    def __str__(self) -> str:
        return f"{self.code}: {self.message}"


def execute_runtime_code(
    *,
    value: Any,
    source: str = "",
    io: Any = None,
    runtime_backed: bool = False,
    runtime_contract_version: str = "",
    execution_mode: str = "",
    timeout_ms: int = 1000,
    max_source_bytes: int = 16 * 1024,
    allowed_builtins: Any = None,
    redaction_policy: Any = None,
    policy_version: str = "",
    passthrough_on_non_json: bool = False,
    spec: str = "",
    vibecomfy_uid: str = "",
    kind: str = "code",
) -> Any:
    allowed_builtin_names = _coerce_string_list(allowed_builtins, "allowed_builtins")
    redaction_policy_names = _coerce_string_list(redaction_policy, "redaction_policy")
    payload = {
        "kind": kind,
        "intent": {"source": source},
        "io": io,
        "runtime": {
            "runtime_backed": runtime_backed,
            "runtime_contract_version": runtime_contract_version,
            "execution_mode": execution_mode,
            "timeout_ms": timeout_ms,
            "max_source_bytes": max_source_bytes,
            "allowed_builtins": allowed_builtin_names,
            "redaction_policy": redaction_policy_names,
            "policy_version": policy_version,
            "passthrough_on_non_json": passthrough_on_non_json,
        },
    }
    if spec:
        payload["intent"]["spec"] = spec
    properties = intent_node_properties(
        kind=kind,
        uid=vibecomfy_uid or "runtime-code",
        intent=payload["intent"],
        inputs=_typed_io_entries(io, "inputs"),
        outputs=_typed_io_entries(io, "outputs"),
        extra_vibecomfy={"runtime": payload["runtime"], "io": payload["io"]},
    )
    contract = validate_runtime_code_contract(
        class_type=KIND_TO_CLASS_TYPE["code"],
        payload=properties["vibecomfy"],
        require_runtime=True,
    )
    if not contract.ok or contract.normalized is None:
        raise RuntimeCodeExecutionError(
            "runtime_contract_invalid",
            "Runtime-backed code contract failed validation before execution.",
            {"issues": [problem.code for problem in contract.problems]},
        )
    if not _is_json_compatible(value):
        raise RuntimeCodeExecutionError(
            "runtime_input_not_json",
            "Runtime-backed code inputs must be JSON-compatible.",
        )
    worker_result = _run_worker(
        {
            "source": source,
            "value": value,
            "inputs": _named_inputs_from_value(value, io),
            "allowed_builtins": allowed_builtin_names,
        },
        timeout_ms=contract.normalized.timeout_ms,
    )
    if not _is_json_compatible(worker_result):
        raise RuntimeCodeExecutionError(
            "runtime_output_not_json",
            "Runtime-backed code returned a non-JSON-compatible result.",
        )
    return worker_result


def _coerce_string_list(value: Any, field: str) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise RuntimeCodeExecutionError(
            "runtime_contract_invalid",
            f"{field} must be a JSON array of strings.",
        )
    return value


def _named_inputs_from_value(value: Any, io: Any) -> dict[str, Any]:
    names: list[str] = []
    if isinstance(io, dict) and isinstance(io.get("inputs"), list):
        for entry in io["inputs"]:
            if isinstance(entry, (list, tuple)) and entry and isinstance(entry[0], str):
                names.append(entry[0])
    if not names:
        return {"value": value}
    return {name: value for name in names}


def _typed_io_entries(io: Any, field: str) -> list[list[str]]:
    entries: list[list[str]] = []
    if not isinstance(io, dict) or not isinstance(io.get(field), list):
        return entries
    for entry in io[field]:
        if (
            isinstance(entry, (list, tuple))
            and len(entry) == 2
            and isinstance(entry[0], str)
            and isinstance(entry[1], str)
        ):
            entries.append([entry[0], entry[1]])
    return entries


def _is_json_compatible(value: Any) -> bool:
    try:
        json.dumps(value, allow_nan=False)
    except (TypeError, ValueError):
        return False
    return True


def _run_worker(payload: dict[str, Any], *, timeout_ms: int) -> Any:
    timeout_seconds = max(timeout_ms, 1) / 1000
    try:
        encoded_payload = json.dumps(payload, allow_nan=False)
    except (TypeError, ValueError) as exc:
        raise RuntimeCodeExecutionError("runtime_protocol_input_invalid", str(exc)) from exc
    with tempfile.TemporaryDirectory(prefix="vibecomfy-runtime-code-") as tmpdir:
        try:
            proc = subprocess.run(
                [sys.executable, "-I", "-c", _WORKER_SOURCE],
                input=encoded_payload,
                text=True,
                capture_output=True,
                timeout=timeout_seconds,
                cwd=tmpdir,
                env={},
                preexec_fn=_limit_worker_resources if os.name == "posix" else None,
            )
        except subprocess.TimeoutExpired as exc:
            raise RuntimeCodeExecutionError(
                "runtime_timeout",
                f"Runtime code exceeded timeout_ms={timeout_ms}.",
            ) from exc
    stdout = proc.stdout[: _WORKER_MAX_STDOUT_BYTES + 1]
    stderr = proc.stderr[: _WORKER_MAX_STDERR_BYTES + 1]
    if len(proc.stdout) > _WORKER_MAX_STDOUT_BYTES:
        raise RuntimeCodeExecutionError("runtime_protocol_output_too_large", "Worker stdout exceeded the protocol limit.")
    if proc.returncode != 0:
        detail = {"stderr": stderr} if stderr else None
        raise RuntimeCodeExecutionError("runtime_worker_failed", "Runtime code worker exited unsuccessfully.", detail)
    try:
        message = json.loads(stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeCodeExecutionError("runtime_protocol_non_json", "Runtime code worker emitted non-JSON output.") from exc
    if not isinstance(message, dict) or "ok" not in message:
        raise RuntimeCodeExecutionError("runtime_protocol_shape", "Runtime code worker emitted an invalid protocol message.")
    if not message["ok"]:
        raise RuntimeCodeExecutionError(
            str(message.get("code") or "runtime_worker_error"),
            str(message.get("message") or "Runtime code failed."),
        )
    return message.get("result")


def _limit_worker_resources() -> None:
    try:
        resource.setrlimit(resource.RLIMIT_CPU, (1, 1))
    except (OSError, ValueError):
        pass
    try:
        memory_bytes = 256 * 1024 * 1024
        resource.setrlimit(resource.RLIMIT_AS, (memory_bytes, memory_bytes))
    except (OSError, ValueError):
        pass


_WORKER_SOURCE: Final[str] = r'''
import ast
import json
import sys

SAFE_BUILTINS = {
    "abs": abs,
    "all": all,
    "any": any,
    "bool": bool,
    "dict": dict,
    "float": float,
    "int": int,
    "len": len,
    "list": list,
    "max": max,
    "min": min,
    "round": round,
    "sorted": sorted,
    "str": str,
    "sum": sum,
    "tuple": tuple,
}


def main():
    try:
        payload = json.loads(sys.stdin.read())
        allowed = {
            name: SAFE_BUILTINS[name]
            for name in payload.get("allowed_builtins", [])
            if name in SAFE_BUILTINS
        }
        scope = dict(payload.get("inputs") or {})
        scope.setdefault("value", payload.get("value"))
        result = eval(
            compile(ast.parse(payload["source"], mode="eval"), "<runtime_code_expression>", "eval"),
            {"__builtins__": allowed},
            scope,
        )
        print(json.dumps({"ok": True, "result": result}, allow_nan=False), end="")
    except BaseException as exc:
        print(
            json.dumps(
                {
                    "ok": False,
                    "code": "runtime_exception",
                    "message": f"{type(exc).__name__}: {exc}",
                }
            ),
            end="",
        )


main()
'''
