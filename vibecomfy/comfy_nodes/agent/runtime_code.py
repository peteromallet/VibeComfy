from __future__ import annotations

import json
import os
import resource
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from typing import Any, Final, Mapping

from vibecomfy.contracts.intent_nodes import (
    EXECUTION_MODE_UNRESTRICTED,
    KIND_TO_CLASS_TYPE,
    RUNTIME_CODE_EXECUTION_MODE,
    RUNTIME_CODE_SAFE_BUILTINS,
    RUNTIME_CODE_UNRESTRICTED_ACK_ERROR,
    _ALLOWED_IMPORTS_BY_MODE,
    _TIMEOUT_MS_DEFAULT_BY_MODE,
    intent_node_properties,
    resolve_execution_mode,
    validate_runtime_code_contract,
)

_WORKER_MAX_STDOUT_BYTES: Final[int] = 64 * 1024
_WORKER_MAX_STDERR_BYTES: Final[int] = 16 * 1024
_UNRESTRICTED_ENV_BLOCKLIST: Final[frozenset[str]] = frozenset(
    {
        "AWS_ACCESS_KEY_ID",
        "AWS_SECRET_ACCESS_KEY",
        "AWS_SESSION_TOKEN",
        "DATABASE_URL",
        "DATABASE_URI",
        "GOOGLE_APPLICATION_CREDENTIALS",
        "PGPASSWORD",
        "POSTGRES_URL",
        "SQLALCHEMY_DATABASE_URI",
    }
)
_UNRESTRICTED_ENV_BLOCK_PREFIXES: Final[tuple[str, ...]] = (
    "ANTHROPIC_",
    "ARNOLD_",
    "AWS_",
    "AZURE_",
    "CLAUDE_",
    "COHERE_",
    "DEEPSEEK_",
    "GCP_",
    "GEMINI_",
    "GOOGLE_",
    "GROQ_",
    "HF_",
    "HUGGINGFACE_",
    "HERMES_",
    "MISTRAL_",
    "OPENAI_",
    "OPENROUTER_",
    "PERPLEXITY_",
    "REPLICATE_",
    "RUNPOD_",
    "TOGETHER_",
    "VOYAGE_",
)
_UNRESTRICTED_ENV_BLOCK_SUFFIXES: Final[tuple[str, ...]] = (
    "_ACCESS_TOKEN",
    "_API_KEY",
    "_CONNECTION_STRING",
    "_DATABASE_URL",
    "_DSN",
    "_PASSWORD",
    "_PRIVATE_KEY",
    "_REFRESH_TOKEN",
    "_SECRET",
    "_SECRET_KEY",
    "_TOKEN",
)

# ComfyUI INPUT_TYPES traversal contract: ComfyUI discovers node ports exclusively by
# calling INPUT_TYPES as a @classmethod on the node class.  Per-instance state is not
# available during that call, so per-instance port counts (addInput/removeInput) cannot
# be driven from the Python side.  Instead, the architecture pre-declares a 16-slot
# wildcard pool in the static INPUT_TYPES dict and relies on the frontend to hide unused
# slots and relabel active ones at runtime.  This keeps the port surface minimal while
# respecting ComfyUI's classmethod-only discovery contract.


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
            "mode": contract.normalized.execution_mode or RUNTIME_CODE_EXECUTION_MODE,
            "source": source,
            "value": value,
            "inputs": _named_inputs_from_value(value, io),
            "allowed_builtins": allowed_builtin_names,
            "allowed_imports": [],
        },
        timeout_ms=contract.normalized.timeout_ms,
    )
    if not _is_json_compatible(worker_result):
        raise RuntimeCodeExecutionError(
            "runtime_output_not_json",
            "Runtime-backed code returned a non-JSON-compatible result.",
        )
    return worker_result


def execute_runtime_code_dynamic(
    *,
    named_inputs: dict[str, Any],
    vibecomfy_props: dict[str, Any],
) -> dict[str, Any]:
    """
    Execute a dynamic-IO runtime code node.

    Takes pre-remapped ``named_inputs`` (in_i keys already resolved to user
    names) and reads all configuration from ``vibecomfy_props``
    (``properties.vibecomfy`` extracted from the ComfyUI prompt by execute()).

    Always returns a dict so execute() can perform uniform 16-slot mapping:
    - io.outputs empty  → ``{"value": <worker_result>}`` (sentinel wrap)
    - io.outputs 1 entry → ``{out_name: <worker_result>}``
    - io.outputs N>1    → worker result must be a dict; raises
      ``RuntimeCodeExecutionError("runtime_output_shape_mismatch", ...)``
      when the worker returns a non-dict.
    """
    props = vibecomfy_props if isinstance(vibecomfy_props, dict) else {}
    io = props.get("io")
    io = io if isinstance(io, dict) else {}
    intent = props.get("intent")
    intent = intent if isinstance(intent, dict) else {}
    runtime = props.get("runtime")
    runtime = runtime if isinstance(runtime, dict) else {}

    source = intent.get("source")
    source = source if isinstance(source, str) else ""

    # Re-derive execution-mode caps from the resolved mode at execution time.
    # The widget mode is authoritative; an agent's snapshot of allowed_builtins /
    # allowed_imports / timeout_ms must never widen the runtime sandbox (SD3).
    resolved_mode = resolve_execution_mode(runtime)

    # Defense-in-depth ack: even if the contract validator was bypassed, never
    # execute unrestricted code without the explicit unrestricted_ack flag.
    if resolved_mode == EXECUTION_MODE_UNRESTRICTED and runtime.get("unrestricted_ack") is not True:
        raise RuntimeCodeExecutionError(
            RUNTIME_CODE_UNRESTRICTED_ACK_ERROR,
            "Unrestricted execution mode requires runtime.unrestricted_ack=true.",
            {"mode": resolved_mode},
        )

    if resolved_mode == RUNTIME_CODE_EXECUTION_MODE:
        # expression_v1: always the fixed 16-name SAFE_BUILTINS set (SD6 re-derive at execution time)
        allowed_builtins = sorted(RUNTIME_CODE_SAFE_BUILTINS)
    else:
        allowed_builtins_raw = runtime.get("allowed_builtins")
        if isinstance(allowed_builtins_raw, list) and all(isinstance(x, str) for x in allowed_builtins_raw):
            allowed_builtins = allowed_builtins_raw
        else:
            allowed_builtins = []

    mode_imports = _ALLOWED_IMPORTS_BY_MODE.get(resolved_mode)
    if mode_imports is None:
        allowed_imports: list[str] = []
    else:
        allowed_imports = sorted(mode_imports)

    if resolved_mode == RUNTIME_CODE_EXECUTION_MODE:
        timeout_default = 1000
    else:
        timeout_default = _TIMEOUT_MS_DEFAULT_BY_MODE.get(resolved_mode, 10_000)

    timeout_ms_val = runtime.get("timeout_ms")
    if not isinstance(timeout_ms_val, int) or isinstance(timeout_ms_val, bool):
        timeout_ms_val = timeout_default

    outputs_spec = io.get("outputs")
    outputs_spec = outputs_spec if isinstance(outputs_spec, list) else []

    worker_result = _run_worker(
        {
            "mode": resolved_mode,
            "source": source,
            "value": next(iter(named_inputs.values()), None) if named_inputs else None,
            "inputs": named_inputs,
            "allowed_builtins": allowed_builtins,
            "allowed_imports": allowed_imports,
        },
        timeout_ms=timeout_ms_val,
    )

    # In the new exec-based modes the worker writes results into an ``outputs`` dict
    # and returns it directly, so the dispatcher must key-map (not wrap) when the
    # worker returns a dict. Legacy expression_v1 returns the scalar eval result and
    # keeps the original wrap-by-position semantics. Tests that monkeypatch
    # ``_run_worker`` to return a scalar still hit the legacy branch.
    new_mode_dict_result = (
        resolved_mode != RUNTIME_CODE_EXECUTION_MODE and isinstance(worker_result, dict)
    )

    if not outputs_spec:
        # Empty io.outputs: sentinel-wrap so execute() always sees a dict.
        return {"value": worker_result}

    output_names: list[str] = []
    for entry in outputs_spec:
        if isinstance(entry, (list, tuple)) and entry and isinstance(entry[0], str):
            output_names.append(entry[0])

    if not output_names:
        return {"value": worker_result}

    if len(output_names) == 1:
        if new_mode_dict_result:
            return {output_names[0]: worker_result.get(output_names[0])}
        return {output_names[0]: worker_result}

    # Multiple declared outputs require the worker to return a dict.
    if not isinstance(worker_result, dict):
        raise RuntimeCodeExecutionError(
            "runtime_output_shape_mismatch",
            f"Runtime code with {len(output_names)} declared outputs must return a dict mapping "
            f"output names to values; got {type(worker_result).__name__}.",
            {"expected_keys": output_names, "actual_type": type(worker_result).__name__},
        )
    return {name: worker_result.get(name) for name in output_names}


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


def _is_sensitive_unrestricted_env_key(key: str) -> bool:
    normalized = key.strip().upper().replace("-", "_")
    if not normalized:
        return False
    if normalized in _UNRESTRICTED_ENV_BLOCKLIST:
        return True
    if normalized.startswith(_UNRESTRICTED_ENV_BLOCK_PREFIXES):
        return True
    return normalized.endswith(_UNRESTRICTED_ENV_BLOCK_SUFFIXES)


def _build_unrestricted_worker_env(parent_env: Mapping[str, str] | None = None) -> dict[str, str]:
    env_source = parent_env if parent_env is not None else os.environ
    return {
        key: value
        for key, value in env_source.items()
        if not _is_sensitive_unrestricted_env_key(key)
    }


def _run_worker(payload: dict[str, Any], *, timeout_ms: int) -> Any:
    timeout_seconds = max(timeout_ms, 1) / 1000
    mode = payload.get("mode") if isinstance(payload, dict) else None
    if not isinstance(mode, str) or not mode:
        mode = RUNTIME_CODE_EXECUTION_MODE
    try:
        encoded_payload = json.dumps(payload, allow_nan=False)
    except (TypeError, ValueError) as exc:
        raise RuntimeCodeExecutionError("runtime_protocol_input_invalid", str(exc)) from exc

    # Branch env + preexec on mode. Unrestricted mode is the explicit "no sandbox"
    # escape hatch (gated by unrestricted_ack upstream), but still strips common
    # parent credential variables before launching the worker. All other modes
    # (legacy expression_v1 and the two sandboxed modes) run with an empty env
    # and rlimits.
    if mode == EXECUTION_MODE_UNRESTRICTED:
        worker_env = _build_unrestricted_worker_env()
        preexec = None
    else:
        worker_env = {}
        preexec = _limit_worker_resources if os.name == "posix" else None

    with tempfile.TemporaryDirectory(prefix="vibecomfy-runtime-code-") as tmpdir:
        try:
            proc = subprocess.run(
                [sys.executable, "-I", "-c", _WORKER_SOURCE],
                input=encoded_payload,
                text=True,
                capture_output=True,
                timeout=timeout_seconds,
                cwd=tmpdir,
                env=worker_env,
                preexec_fn=preexec,
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
import builtins as _builtins
import json
import sys

# Legacy 16-name safe-builtin map. expression_v1 keeps this set byte-identical to
# the pre-mode-dispatch worker; do not extend without changing the contract.
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

# Broad builtins available to the new sandboxed_* modes. Mirrors
# RUNTIME_CODE_BROAD_BUILTINS in the contract.
_BROAD_BUILTIN_NAMES = (
    "abs", "all", "any", "bool", "dict", "float", "int", "len", "list",
    "max", "min", "round", "sorted", "str", "sum", "tuple",
    "print", "range", "enumerate", "zip", "map", "filter", "set",
    "frozenset", "reversed", "divmod", "pow", "hex", "oct", "bin",
    "ord", "chr", "repr", "isinstance", "issubclass", "type", "hash",
    "id", "iter", "next",
)


def _broad_builtins_map():
    return {
        name: getattr(_builtins, name)
        for name in _BROAD_BUILTIN_NAMES
        if hasattr(_builtins, name)
    }


def _strict_import(name, globals=None, locals=None, fromlist=(), level=0):
    raise ImportError("imports are forbidden in sandboxed_strict mode")


def _make_loose_import(allowed):
    allowed_roots = frozenset(allowed or ())

    def _loose_import(name, globals=None, locals=None, fromlist=(), level=0):
        root = (name or "").split(".", 1)[0]
        if root not in allowed_roots:
            raise ImportError(
                "import of " + repr(name) + " is not in the sandboxed_loose allowlist"
            )
        return _builtins.__import__(name, globals, locals, fromlist, level)

    return _loose_import


def _run_expression_v1(payload):
    # Byte-identical legacy branch: single-expression eval against the 16-name
    # SAFE_BUILTINS, scope = inputs + value, no outputs dict.
    allowed = {
        name: SAFE_BUILTINS[name]
        for name in payload.get("allowed_builtins", [])
        if name in SAFE_BUILTINS
    }
    scope = dict(payload.get("inputs") or {})
    scope.setdefault("value", payload.get("value"))
    return eval(
        compile(ast.parse(payload["source"], mode="eval"), "<runtime_code_expression>", "eval"),
        {"__builtins__": allowed},
        scope,
    )


def _run_sandboxed(payload, *, mode):
    inputs = dict(payload.get("inputs") or {})
    outputs = {}
    builtins_map = _broad_builtins_map()
    if mode == "sandboxed_strict":
        builtins_map["__import__"] = _strict_import
    else:
        builtins_map["__import__"] = _make_loose_import(payload.get("allowed_imports") or [])
    scope = {
        "__builtins__": builtins_map,
        "inputs": inputs,
        "outputs": outputs,
    }
    scope.update(inputs)
    compiled = compile(payload["source"], "<runtime_code_source>", "exec")
    exec(compiled, scope, scope)
    return outputs


def _run_unrestricted(payload):
    inputs = dict(payload.get("inputs") or {})
    outputs = {}
    scope = {
        "__builtins__": _builtins.__dict__,
        "inputs": inputs,
        "outputs": outputs,
    }
    scope.update(inputs)
    compiled = compile(payload["source"], "<runtime_code_source>", "exec")
    exec(compiled, scope, scope)
    return outputs


def main():
    try:
        payload = json.loads(sys.stdin.read())
        mode = payload.get("mode") or "expression_v1"
        if mode == "expression_v1":
            result = _run_expression_v1(payload)
        elif mode == "sandboxed_strict":
            result = _run_sandboxed(payload, mode="sandboxed_strict")
        elif mode == "sandboxed_loose":
            result = _run_sandboxed(payload, mode="sandboxed_loose")
        elif mode == "unrestricted":
            result = _run_unrestricted(payload)
        else:
            raise RuntimeError("unknown execution mode " + repr(mode))
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
