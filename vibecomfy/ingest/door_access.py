"""Door-owned LiteGraph / envelope accessors.

Product files must call these instead of reading ``nodes`` / ``links`` /
``widgets_values`` directly.  Defined in a leaf module so identity and
other ingest dependencies can import them without cycling through
``normalize``.
"""

from __future__ import annotations

from typing import Any

_DOOR_MISSING = object()


def door_get_nodes(graph: Any, default: Any = None) -> Any:
    getter = getattr(graph, "get", None)
    if callable(getter):
        return getter("nodes", default)
    return default


def door_nodes(graph: Any) -> Any:
    return graph["nodes"]


def door_pop_nodes(graph: Any, default: Any = _DOOR_MISSING) -> Any:
    if default is _DOOR_MISSING:
        return graph.pop("nodes")
    return graph.pop("nodes", default)


def door_setdefault_nodes(graph: Any, default: Any = None) -> Any:
    return graph.setdefault("nodes", default)


def door_get_links(graph: Any, default: Any = None) -> Any:
    getter = getattr(graph, "get", None)
    if callable(getter):
        return getter("links", default)
    return default


def door_links(graph: Any) -> Any:
    return graph["links"]


def door_pop_links(graph: Any, default: Any = _DOOR_MISSING) -> Any:
    if default is _DOOR_MISSING:
        return graph.pop("links")
    return graph.pop("links", default)


def door_setdefault_links(graph: Any, default: Any = None) -> Any:
    return graph.setdefault("links", default)


def door_get_widgets_values(node: Any, default: Any = None) -> Any:
    getter = getattr(node, "get", None)
    if callable(getter):
        return getter("widgets_values", default)
    return default


def door_widgets_values(node: Any) -> Any:
    return node["widgets_values"]


def door_pop_widgets_values(node: Any, default: Any = _DOOR_MISSING) -> Any:
    if default is _DOOR_MISSING:
        return node.pop("widgets_values")
    return node.pop("widgets_values", default)


def door_setdefault_widgets_values(node: Any, default: Any = None) -> Any:
    return node.setdefault("widgets_values", default)
