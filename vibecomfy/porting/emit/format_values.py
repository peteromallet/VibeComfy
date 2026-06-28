"""Literal formatting helpers for generated Python emission."""

from __future__ import annotations

from typing import Any

_MODEL_FILE_SUFFIXES: tuple[str, ...] = (
    ".safetensors", ".ckpt", ".pt", ".bin", ".pth", ".gguf", ".onnx",
)


def _format_value(value: Any, *, elide_strings_over: int | None = None) -> str:
    # Normalize Windows-style backslash separators to forward slashes in model
    # file paths. ComfyUI model loaders accept either separator.
    if isinstance(value, str) and "\\" in value:
        if value.endswith(_MODEL_FILE_SUFFIXES) or any(
            f"\\{ext[1:]}" in value for ext in _MODEL_FILE_SUFFIXES
        ):
            value = value.replace("\\", "/")
    if elide_strings_over is not None and isinstance(value, str) and len(value) > elide_strings_over:
        head = repr(value[:240])
        tail = repr(value[-80:])
        n_elided = len(value) - 320
        return f"({head} + \"[...{n_elided} chars elided...]\" + {tail})"
    return repr(value)


__all__ = ["_MODEL_FILE_SUFFIXES", "_format_value"]
