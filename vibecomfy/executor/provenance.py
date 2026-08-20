"""
Provenance read-side: load source workflows from breadcrumb metadata
and collect type instances from source workflows.

Reads ``extra.vibecomfy`` breadcrumbs (written by
``vibecomfy.porting.emit.ui._breadcrumb``) and resolves the originating
workflow.  Callers fall through to corpus search when this module returns
``None`` or ``[]`` — it never raises.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from vibecomfy.ingest.loader import load_workflow_json
from vibecomfy.registry.ready import _resolve_ready_path

from vibecomfy.ingest.normalize import door_get_links, door_get_nodes, door_get_widgets_values
_SOURCE_WORKFLOW_PATH_RE = re.compile(r"'source_workflow_path'\s*:\s*'([^']+)'")


def load_source_workflow(graph: dict[str, Any]) -> dict[str, Any] | None:
    """Resolve and load the **source** workflow dict from a graph carrying
    ``extra.vibecomfy`` breadcrumb metadata.

    * Prefers ``prior_path`` (a direct file path) when present.
    * Falls back to ``source_template`` (a ready-template id resolved via
      ``_resolve_ready_path`` + ``source_workflow_path`` extraction).
    * Returns ``None`` on *any* failure — missing breadcrumb, stale/invalid
      path, parse error, or missing loader.
    """
    breadcrumb = _breadcrumb_from_graph(graph)
    if breadcrumb is None:
        return None

    prior_path = breadcrumb.get("prior_path")
    if isinstance(prior_path, str) and prior_path:
        source_workflow = _load_and_normalize(prior_path)
        if source_workflow is not None:
            return source_workflow

    source_template = breadcrumb.get("source_template")
    if isinstance(source_template, str) and source_template:
        return _load_from_template(source_template)

    return None


def collect_type_instances(
    source_workflow: dict[str, Any] | None,
    class_type: str,
) -> list[dict[str, Any]]:
    """Return **all** nodes in *source_workflow* whose ``type`` matches
    *class_type*, each annotated with named widget values and incident
    edges.  Returns ``[]`` when *source_workflow* is ``None`` or no node
    matches.
    """
    if source_workflow is None:
        return []

    nodes = door_get_nodes(source_workflow, {})
    if not isinstance(nodes, dict):
        return []

    links = door_get_links(source_workflow)
    if not isinstance(links, list):
        links = []

    results: list[dict[str, Any]] = []
    for node_id, node in nodes.items():
        if not isinstance(node, dict):
            continue
        ct = node.get("type")
        if ct != class_type:
            continue

        results.append(
            {
                "node_id": str(node_id),
                "class_type": str(ct),
                "widget_values": _named_widget_values(node, ct),
                "incident_edges": _incident_edges(node_id, node, nodes, links),
            }
        )

    return results


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _breadcrumb_from_graph(graph: dict[str, Any]) -> dict[str, Any] | None:
    extra = graph.get("extra")
    if not isinstance(extra, dict):
        return None
    vibecomfy = extra.get("vibecomfy")
    if not isinstance(vibecomfy, dict):
        return None
    return vibecomfy


def _load_and_normalize(path: str | Path) -> dict[str, Any] | None:
    """Load a workflow JSON at *path* and return it with nodes keyed by id."""
    try:
        raw = load_workflow_json(path)
    except Exception:
        return None
    return _normalize_workflow(raw)


def _load_from_template(template_id: str) -> dict[str, Any] | None:
    """Resolve *template_id* to a path and load its source workflow JSON."""
    try:
        py_path = _resolve_ready_path(template_id)
    except Exception:
        return None

    try:
        source_text = py_path.read_text(encoding="utf-8")
    except Exception:
        return None

    match = _SOURCE_WORKFLOW_PATH_RE.search(source_text)
    if match is None:
        return None

    source_path = Path(match.group(1))
    if not source_path.is_absolute():
        source_path = Path(__file__).resolve().parents[2] / source_path
    return _load_and_normalize(source_path)


def _normalize_workflow(raw: dict[str, Any]) -> dict[str, Any]:
    """Return a copy of *raw* with ``nodes`` as a ``dict`` keyed by node id
    (string), and ``links`` left as a list.  The standard ComfyUI API shape
    is preserved; only the container structure changes."""
    nodes_raw = door_get_nodes(raw)
    nodes_dict: dict[str, Any] = {}
    if isinstance(nodes_raw, list):
        for node in nodes_raw:
            if isinstance(node, dict):
                nid = node.get("id")
                if nid is not None:
                    nodes_dict[str(nid)] = node
    return {**raw, "nodes": nodes_dict}


def _named_widget_values(
    node: dict[str, Any],
    class_type: str,
) -> list[dict[str, Any]]:
    """Return ``[{"name": str, "value": Any}, ...]`` for the widget values
    on *node*, using the compact widget name resolver when available."""
    widgets_values = door_get_widgets_values(node)
    if not isinstance(widgets_values, list):
        return []

    names = _resolve_widget_names(node, class_type)

    result: list[dict[str, Any]] = []
    for idx, value in enumerate(widgets_values):
        name = names[idx] if idx < len(names) else f"widget_{idx}"
        result.append({"name": name, "value": value})
    return result


def _resolve_widget_names(
    node: dict[str, Any],
    class_type: str,
) -> tuple[str | None, ...]:
    """Best-effort widget name resolution via the compact resolver."""
    try:
        from vibecomfy.porting.widgets.compact_resolver import (
            compact_widget_names_for_node,
        )

        resolution = compact_widget_names_for_node(
            node,
            class_type,
            value_count=len(door_get_widgets_values(node) or []),
        )
        return resolution.names
    except Exception:
        return ()


def _incident_edges(
    node_id: str,
    node: dict[str, Any],
    nodes: dict[str, Any],
    links: list[Any],
) -> list[dict[str, Any]]:
    """Build incident edge records for *node_id*.

    For each link into/out of this node, records the peer's ``class_type``,
    the socket name, and the direction (``"in"`` or ``"out"``).
    """
    edges: list[dict[str, Any]] = []
    for link in links:
        if isinstance(link, dict):
            origin = str(link.get("origin_id") or "")
            target = str(link.get("target_id") or "")
            origin_slot = link.get("origin_slot")
            target_slot = link.get("target_slot")
        elif isinstance(link, (list, tuple)) and len(link) >= 5:
            _link_id = link[0]
            origin = str(link[1])
            origin_slot = link[2]
            target = str(link[3])
            target_slot = link[4]
            _link_type = link[5] if len(link) > 5 else None
        else:
            continue

        if origin == node_id:
            peer_node = nodes.get(target)
            peer_class = (
                peer_node.get("type") if isinstance(peer_node, dict) else None
            )
            socket_name = _output_socket_name(node, origin_slot)
            edges.append(
                {
                    "peer_class": str(peer_class) if peer_class else "",
                    "socket": socket_name,
                    "direction": "out",
                }
            )
        elif target == node_id:
            peer_node = nodes.get(origin)
            peer_class = (
                peer_node.get("type") if isinstance(peer_node, dict) else None
            )
            socket_name = _input_socket_name(node, target_slot)
            edges.append(
                {
                    "peer_class": str(peer_class) if peer_class else "",
                    "socket": socket_name,
                    "direction": "in",
                }
            )

    return edges


def _output_socket_name(node: dict[str, Any], slot_index: Any) -> str:
    """Resolve an output slot index to a socket name."""
    outputs = node.get("outputs")
    if isinstance(outputs, list):
        try:
            idx = int(slot_index or 0)
            if 0 <= idx < len(outputs):
                entry = outputs[idx]
                if isinstance(entry, dict):
                    return str(entry.get("name") or idx)
        except (ValueError, TypeError):
            pass
    return str(slot_index)


def _input_socket_name(node: dict[str, Any], slot_index: Any) -> str:
    """Resolve an input slot index to a socket name."""
    inputs = node.get("inputs")
    if isinstance(inputs, list):
        try:
            idx = int(slot_index or 0)
            if 0 <= idx < len(inputs):
                entry = inputs[idx]
                if isinstance(entry, dict):
                    return str(entry.get("name") or idx)
        except (ValueError, TypeError):
            pass
    return str(slot_index)
