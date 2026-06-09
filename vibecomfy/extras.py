from __future__ import annotations

import importlib.metadata
import importlib.util
from dataclasses import dataclass
from pathlib import Path
from collections.abc import Callable
from typing import Any


PLUGIN_GROUP = "vibecomfy.plugins"
PLUGIN_SUBDIRS = ("blocks", "patches", "ops", "recipes", "ready_templates")

_LOADED = False
_REGISTERED_READY_ROOTS: list[Path] = []


@dataclass(frozen=True)
class PluginAPI:
    def register_block(self, fn: Callable[..., Any]) -> Callable[..., Any]:
        from vibecomfy.blocks import block

        return block(fn)

    def register_patch(self, patch: Callable[..., Any]) -> Callable[..., Any]:
        from vibecomfy.patches.registry import register

        return register(patch)

    def register_op(self, verb_kind: str, verb_name: str, fn: Callable[..., Any]) -> Callable[..., Any]:
        from vibecomfy.ops.registry import register_op

        return register_op(verb_kind, verb_name, fn)

    def register_route(self, verb_kind: str, verb_name: str, predicate: Callable[..., Any], template_id: str, patches: Any = ()) -> Callable[..., Any]:
        from vibecomfy.router_rules import register_route

        return register_route(verb_kind, verb_name, predicate, template_id, patches)

    def register_ready_root(self, path: str | Path) -> Path:
        root = Path(path).expanduser().resolve()
        if root not in _REGISTERED_READY_ROOTS:
            _REGISTERED_READY_ROOTS.append(root)
        return root


_API = PluginAPI()


def plugin_api() -> PluginAPI:
    return _API


def registered_ready_roots() -> tuple[Path, ...]:
    return tuple(_REGISTERED_READY_ROOTS)


def ensure_plugins_loaded() -> PluginAPI:
    global _LOADED
    if not _LOADED:
        load_plugins()
        _LOADED = True
    return _API


def load_plugins() -> PluginAPI:
    for root in _discovery_roots():
        for subdir in PLUGIN_SUBDIRS:
            _load_plugin_files(root / subdir)
    for entry_point in _entry_points():
        register = entry_point.load()
        register(_API)
    return _API


def _discovery_roots() -> tuple[Path, Path]:
    return (Path.cwd() / "vibecomfy_extras", Path.home() / ".vibecomfy")


def _load_plugin_files(directory: Path) -> None:
    if not directory.is_dir():
        return
    for path in sorted(directory.glob("*.py")):
        if path.name.startswith("_"):
            continue
        spec = importlib.util.spec_from_file_location(f"vibecomfy_extra_{abs(hash(path))}", path)
        if spec is None or spec.loader is None:
            continue
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        register = getattr(module, "register", None)
        if callable(register):
            register(_API)


def _entry_points() -> list[Any]:
    eps = importlib.metadata.entry_points()
    if hasattr(eps, "select"):
        return list(eps.select(group=PLUGIN_GROUP))
    if hasattr(eps, "get"):
        return list(eps.get(PLUGIN_GROUP, []))
    return []


def _reset_for_tests() -> None:
    global _LOADED
    _LOADED = False
    _REGISTERED_READY_ROOTS.clear()


__all__ = [
    "PLUGIN_GROUP",
    "PluginAPI",
    "ensure_plugins_loaded",
    "load_plugins",
    "plugin_api",
    "registered_ready_roots",
]
