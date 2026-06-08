from __future__ import annotations

import json
import keyword
import textwrap
import traceback
from typing import Any

from vibecomfy.comfy_nodes.exec_examples import EXEC_EXAMPLES, EXEC_HELP_TEXT

try:
    import numpy as np
except Exception:  # pragma: no cover - optional dependency
    np = None  # type: ignore[assignment]

try:
    from PIL import Image
except Exception:  # pragma: no cover - optional dependency
    Image = None  # type: ignore[assignment]

try:
    import torch
except Exception:  # pragma: no cover - optional dependency
    torch = None  # type: ignore[assignment]

EXEC_CLASS_TYPE: str = "vibecomfy.exec"
EXEC_SLOT_COUNT: int = 16  # in_0..in_15 and out_0..out_15

_PREINJECT_GLOBALS: dict[str, Any] = {
    "__builtins__": __builtins__,
    "__name__": EXEC_CLASS_TYPE,
    "torch": torch,
    "np": np,
    "Image": Image,
}


class ExecNodeContractError(RuntimeError):
    """Raised when `vibecomfy.exec` inputs or outputs violate the node contract."""


def _normalize_io_entries(io_value: Any, *, field: str) -> tuple[tuple[str, str | None], ...]:
    if io_value is None:
        return ()
    if not isinstance(io_value, list):
        raise ExecNodeContractError(f"`io.{field}` must be a list of [name, type] entries")
    normalized: list[tuple[str, str | None]] = []
    for index, entry in enumerate(io_value):
        if not isinstance(entry, (list, tuple)) or not (1 <= len(entry) <= 2):
            raise ExecNodeContractError(
                f"`io.{field}[{index}]` must be a [name, type] pair"
            )
        name = entry[0]
        type_name = entry[1] if len(entry) == 2 else None
        if not isinstance(name, str) or not name:
            raise ExecNodeContractError(f"`io.{field}[{index}][0]` must be a non-empty string")
        if type_name is not None and not isinstance(type_name, str):
            raise ExecNodeContractError(f"`io.{field}[{index}][1]` must be a string when provided")
        normalized.append((name, type_name))
    return tuple(normalized)


def parse_io(io: Any) -> dict[str, tuple[tuple[str, str | None], ...]]:
    if isinstance(io, str):
        try:
            payload = json.loads(io)
        except json.JSONDecodeError as exc:
            raise ExecNodeContractError(f"`io` must be valid JSON: {exc.msg}") from exc
    elif io is None:
        payload = {}
    elif isinstance(io, dict):
        payload = io
    else:
        raise ExecNodeContractError("`io` must be a dict, JSON string, or null")

    if not isinstance(payload, dict):
        raise ExecNodeContractError("`io` must decode to a dict")

    inputs = _normalize_io_entries(payload.get("inputs"), field="inputs")
    outputs = _normalize_io_entries(payload.get("outputs"), field="outputs")
    if len(inputs) > EXEC_SLOT_COUNT:
        raise ExecNodeContractError(f"`io.inputs` supports at most {EXEC_SLOT_COUNT} entries")
    if len(outputs) > EXEC_SLOT_COUNT:
        raise ExecNodeContractError(f"`io.outputs` supports at most {EXEC_SLOT_COUNT} entries")

    input_names = [name for name, _ in inputs]
    output_names = [name for name, _ in outputs]
    if len(set(input_names)) != len(input_names):
        raise ExecNodeContractError("`io.inputs` contains duplicate names")
    if len(set(output_names)) != len(output_names):
        raise ExecNodeContractError("`io.outputs` contains duplicate names")

    return {"inputs": inputs, "outputs": outputs}


def semantic_inputs_from_slots(
    io_spec: dict[str, tuple[tuple[str, str | None], ...]],
    slots: dict[str, Any],
) -> dict[str, Any]:
    values: dict[str, Any] = {}
    for index, (name, _type_name) in enumerate(io_spec.get("inputs", ())):
        values[name] = clone_exec_input(slots.get(f"in_{index}"))
    return values


def clone_exec_input(value: Any) -> Any:
    if torch is not None and isinstance(value, torch.Tensor):
        return value.clone()
    if np is not None and isinstance(value, np.ndarray):
        return value.copy()
    if Image is not None and isinstance(value, Image.Image):
        return value.copy()
    if isinstance(value, dict):
        return {key: clone_exec_input(item) for key, item in value.items()}
    if isinstance(value, list):
        return [clone_exec_input(item) for item in value]
    if isinstance(value, tuple):
        return tuple(clone_exec_input(item) for item in value)
    return value


def _validate_identifier(name: str) -> None:
    if not name.isidentifier() or keyword.iskeyword(name):
        raise ExecNodeContractError(
            f"`io` input name {name!r} is not a valid Python identifier for `vibecomfy.exec`"
        )


def compile_source_body(
    source: str,
    input_names: list[str] | tuple[str, ...],
    *,
    filename: str = "<vibecomfy.exec>",
) -> Any:
    if not isinstance(source, str):
        raise ExecNodeContractError("`source` must be a string")

    for name in input_names:
        _validate_identifier(name)

    body = textwrap.dedent(source).strip("\n")
    if not body:
        body = "return {}"
    signature = ", ".join(input_names)
    function_source = f"def __vibecomfy_exec_body({signature}):\n{textwrap.indent(body, '    ')}\n"
    namespace: dict[str, Any] = {}
    exec(compile(function_source, filename, "exec"), dict(_PREINJECT_GLOBALS), namespace)
    return namespace["__vibecomfy_exec_body"]


def _format_exec_exception(exc: BaseException, *, filename: str) -> str:
    for frame in reversed(traceback.extract_tb(exc.__traceback__)):
        if frame.filename == filename:
            body_line = max(frame.lineno - 1, 1)
            return f"`vibecomfy.exec` body failed at {filename}:{body_line}: {exc}"
    return f"`vibecomfy.exec` body failed: {exc}"


def run_source_body(runner: Any, semantic_inputs: dict[str, Any]) -> Any:
    try:
        return runner(**semantic_inputs)
    except Exception as exc:  # noqa: BLE001 - bubble user-code failures with node context
        raise RuntimeError(_format_exec_exception(exc, filename=runner.__code__.co_filename)) from exc


def validate_exec_result(
    result: Any,
    io_spec: dict[str, tuple[tuple[str, str | None], ...]],
) -> tuple[Any, ...]:
    if not isinstance(result, dict):
        raise ExecNodeContractError("`vibecomfy.exec` body must return a dict keyed by `io.outputs` names")

    output_names = [name for name, _ in io_spec.get("outputs", ())]
    missing = [name for name in output_names if name not in result]
    extra = sorted(key for key in result if key not in output_names)
    if missing or extra:
        problems: list[str] = []
        if missing:
            problems.append(f"missing {missing}")
        if extra:
            problems.append(f"unexpected {extra}")
        raise ExecNodeContractError(
            "`vibecomfy.exec` body must return exactly the declared `io.outputs` keys: "
            + ", ".join(problems)
        )

    outputs = [result[name] for name in output_names]
    outputs.extend([None] * (EXEC_SLOT_COUNT - len(outputs)))
    return tuple(outputs[:EXEC_SLOT_COUNT])


class VibeComfyExec:
    """In-graph code execution node with fixed wildcard I/O slots.

    ``source`` holds the Python expression/script body.
    ``io`` is a JSON widget that declares typed input/output schemas
    (the single authoritative source of truth per SD2).

    Up to 16 wildcard inputs (``in_0`` … ``in_15``) can be linked
    by the graph.  The node always produces 16 wildcard outputs
    (``out_0`` … ``out_15``), padding unset slots with ``None``.
    """

    CATEGORY: str = "vibecomfy/exec"
    RETURN_TYPES: tuple[str, ...] = tuple(["*"] * EXEC_SLOT_COUNT)
    RETURN_NAMES: tuple[str, ...] = tuple(f"out_{i}" for i in range(EXEC_SLOT_COUNT))
    FUNCTION: str = "execute"
    DESCRIPTION: str = EXEC_HELP_TEXT
    HELP: str = EXEC_HELP_TEXT
    EXAMPLES: dict[str, dict[str, object]] = EXEC_EXAMPLES

    VIBECOMFY_INTENT_NODE: bool = False
    VIBECOMFY_EDITOR_ONLY: bool = False
    VIBECOMFY_RUNTIME_BACKED: bool = False
    VIBECOMFY_LOWERED: bool = False

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, Any]:
        optional: dict[str, tuple[str, ...]] = {}
        for i in range(EXEC_SLOT_COUNT):
            optional[f"in_{i}"] = ("*",)
        return {
            "required": {
                "source": ("STRING", {"default": "", "multiline": True}),
                "io": ("JSON",),
            },
            "optional": optional,
        }

    def execute(self, source: str = "", io: Any = None, **kwargs: Any) -> tuple[Any, ...]:
        io_spec = parse_io(io)
        semantic_inputs = semantic_inputs_from_slots(io_spec, kwargs)
        runner = compile_source_body(
            source,
            [name for name, _type_name in io_spec["inputs"]],
            filename=f"<{EXEC_CLASS_TYPE}>",
        )
        result = run_source_body(runner, semantic_inputs)
        return validate_exec_result(result, io_spec)
