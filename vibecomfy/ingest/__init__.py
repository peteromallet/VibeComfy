from __future__ import annotations

from typing import Any

__all__ = [
    "load_workflow_json",
    "from_envelope",
    "from_ui",
    "from_api",
    "normalize_to_api",
    "index_workflows",
    "write_index",
    "WorkflowLoadResult",
    "WorkflowLoadWarning",
    "WorkflowNodeRecord",
    "load_workflow_source",
    "normalize_workflow_source",
]

_LAZY_ATTRS: dict[str, tuple[str, str]] = {
    "index_workflows": (".index", "index_workflows"),
    "write_index": (".index", "write_index"),
    "load_workflow_json": (".loader", "load_workflow_json"),
    "from_api": (".normalize", "from_api"),
    "from_envelope": (".normalize", "from_envelope"),
    "from_ui": (".normalize", "from_ui"),
    "normalize_to_api": (".normalize", "normalize_to_api"),
    "WorkflowLoadResult": (".workflow_source", "WorkflowLoadResult"),
    "WorkflowLoadWarning": (".workflow_source", "WorkflowLoadWarning"),
    "WorkflowNodeRecord": (".workflow_source", "WorkflowNodeRecord"),
    "load_workflow_source": (".workflow_source", "load_workflow_source"),
    "normalize_workflow_source": (".workflow_source", "normalize_workflow_source"),
}


def __getattr__(name: str) -> Any:
    target = _LAZY_ATTRS.get(name)
    if target is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    module_name, attr = target
    from importlib import import_module

    value = getattr(import_module(module_name, __name__), attr)
    globals()[name] = value
    return value
