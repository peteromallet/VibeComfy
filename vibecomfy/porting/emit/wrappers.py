"""Wrapper discovery and naming helpers for generated Python emission."""

from __future__ import annotations

import importlib
import keyword
from typing import Any

UI_ONLY_CLASS_TYPES: frozenset[str] = frozenset(
    {"Note", "MarkdownNote", "Label (rgthree)", "PreviewAny", "easy showAnything"}
)
FALLBACK_CLASS_TYPES: frozenset[str] = frozenset({
    "Note",
    "MarkdownNote",
})
RESERVED_WRAPPER_INPUT_NAMES: frozenset[str] = frozenset({"class", "from", "type"})

_STATIC_WRAPPER_MODULES: tuple[str, ...] = (
    "core",
    "kjnodes",
    "ltxvideo",
    "videohelpersuite",
    "controlnet_aux",
    "depthanythingv2",
    "wanvideowrapper",
    "qwentts",
    "qwen3tts",
    "gguf",
    "rgthree",
    "sam2",
    "wananimatepreprocess",
    "ailab_audioduration",
    "custom_scripts",
    "florence2",
    "gimm_vfi",
    "melbandroformer",
    "vibecomfy_internal",
)


_WRAPPER_CLASS_TO_MODULE: dict[str, str] | None = None
_WRAPPER_CLASS_TO_SYMBOL: dict[str, str] | None = None


def _wrapper_modules() -> tuple[str, ...]:
    try:
        nodes = importlib.import_module("vibecomfy.nodes")
    except ImportError:
        return _STATIC_WRAPPER_MODULES
    modules = getattr(nodes, "MODULES", None)
    if isinstance(modules, (list, tuple)):
        return tuple(str(module) for module in modules if isinstance(module, str) and module)
    return _STATIC_WRAPPER_MODULES


def _wrapper_class_to_module() -> dict[str, str]:
    global _WRAPPER_CLASS_TO_MODULE, _WRAPPER_CLASS_TO_SYMBOL
    if _WRAPPER_CLASS_TO_MODULE is not None:
        return _WRAPPER_CLASS_TO_MODULE
    module_mapping: dict[str, str] = {}
    symbol_mapping: dict[str, str] = {}
    for module_name in _wrapper_modules():
        try:
            module = importlib.import_module(f"vibecomfy.nodes.{module_name}")
        except ImportError:
            continue
        exported = getattr(module, "__all__", ())
        for name in exported:
            if isinstance(name, str):
                class_type = _wrapper_class_type_for_symbol(module, name)
                module_mapping.setdefault(class_type, module_name)
                symbol_mapping.setdefault(class_type, name)
    _WRAPPER_CLASS_TO_MODULE = module_mapping
    _WRAPPER_CLASS_TO_SYMBOL = symbol_mapping
    return module_mapping


def _wrapper_class_type_for_symbol(module: Any, symbol_name: str) -> str:
    class_types = getattr(module, "__vibecomfy_class_types__", None)
    if isinstance(class_types, dict):
        class_type = class_types.get(symbol_name)
        if isinstance(class_type, str) and class_type:
            return class_type
    func = getattr(module, symbol_name, None)
    if callable(func):
        code = getattr(func, "__code__", None)
        for value in getattr(code, "co_consts", ()):
            if isinstance(value, str) and value != symbol_name and _wrapper_class_name_candidate(value):
                return value
    return symbol_name


def _wrapper_class_name_candidate(value: str) -> bool:
    return (
        bool(value)
        and "\n" not in value
        and not value.endswith("() takes at most 1 positional argument, got ")
        and any(ch.isupper() or ch in " ()-" for ch in value)
    )


def _wrapper_module_for_class(class_type: str) -> str | None:
    if class_type in FALLBACK_CLASS_TYPES or class_type in UI_ONLY_CLASS_TYPES:
        return None
    return _wrapper_class_to_module().get(class_type)


def _wrapper_symbol_for_class(class_type: str) -> str | None:
    _wrapper_class_to_module()
    return (_WRAPPER_CLASS_TO_SYMBOL or {}).get(class_type)


def _wrapper_imports_for_nodes(workflow_nodes: dict[str, Any]) -> dict[str, list[str]]:
    imports: dict[str, set[str]] = {}
    for node in workflow_nodes.values():
        class_type = str(getattr(node, "class_type", ""))
        module_name = _wrapper_module_for_class(class_type)
        symbol_name = _wrapper_symbol_for_class(class_type)
        if module_name is not None:
            imports.setdefault(module_name, set()).add(symbol_name or class_type)
    return {module: sorted(names) for module, names in imports.items()}


def _wrapper_kwarg_name(name: str) -> str:
    return f"{name}_" if name in RESERVED_WRAPPER_INPUT_NAMES or keyword.iskeyword(name) else name


__all__ = [
    "UI_ONLY_CLASS_TYPES",
    "FALLBACK_CLASS_TYPES",
    "RESERVED_WRAPPER_INPUT_NAMES",
    "_STATIC_WRAPPER_MODULES",
    "_WRAPPER_CLASS_TO_MODULE",
    "_WRAPPER_CLASS_TO_SYMBOL",
    "_wrapper_modules",
    "_wrapper_class_to_module",
    "_wrapper_class_type_for_symbol",
    "_wrapper_class_name_candidate",
    "_wrapper_module_for_class",
    "_wrapper_symbol_for_class",
    "_wrapper_imports_for_nodes",
    "_wrapper_kwarg_name",
]
