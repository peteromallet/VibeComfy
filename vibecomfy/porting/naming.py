"""Node ordering and variable naming for ready-template emission."""

from __future__ import annotations

import keyword
import re

from vibecomfy._compile._graph import is_api_link, node_id_sort_key


def safe_var(class_type: str) -> str:
    """Lowercase + underscores form of a class type (no UUID prefixes)."""
    name = re.sub(r"[^a-zA-Z0-9_]", "_", class_type.lower())
    if not name or name[0].isdigit():
        name = f"n_{name}"
    if keyword.iskeyword(name):
        name = f"{name}_"
    return name


def connection_role_name(workflow_nodes: dict, edges_out: dict) -> dict[str, str]:
    """Apply role-from-connection heuristic: CLIPTextEncode -> positive/negative."""
    roles: dict[str, str] = {}
    for src_node_id, src_class in [(nid, n.class_type) for nid, n in workflow_nodes.items()]:
        if src_class != "CLIPTextEncode":
            continue
        for to_node, to_input in edges_out.get(src_node_id, []):
            target = workflow_nodes.get(to_node)
            if target is None:
                continue
            if target.class_type == "KSampler" and to_input in ("positive", "negative"):
                roles[src_node_id] = to_input
                break
            if target.class_type in ("CFGGuider", "MultimodalGuider") and to_input in ("positive", "negative"):
                roles[src_node_id] = to_input
                break
    return roles


def empty_text_role(workflow_nodes: dict) -> dict[str, str]:
    """Apply role-from-text heuristic: empty CLIPTextEncode prompt -> 'negative'."""
    roles: dict[str, str] = {}
    for nid, node in workflow_nodes.items():
        if node.class_type != "CLIPTextEncode":
            continue
        text_value = node.inputs.get("text", node.widgets.get("text", node.widgets.get("widget_0")))
        if isinstance(text_value, str) and text_value.strip() == "":
            roles.setdefault(nid, "negative")
    return roles


def topological_node_order(nodes: dict, edges_in: dict) -> list[str]:
    """Topologically sort node ids: producers before consumers.

    Resolves both edges-in-IR (`workflow.edges`) and link-shaped values still
    living in `node.inputs` so the emitted file can reference variables
    defined earlier in the function.
    """
    # Build incoming-deps map.
    deps: dict[str, set[str]] = {nid: set() for nid in nodes}
    for nid, node in nodes.items():
        # From workflow.edges via edges_in.
        for edge in edges_in.get(nid, []):
            if edge.from_node in nodes:
                deps[nid].add(edge.from_node)
        # From link-shaped values in node.inputs / widgets.
        for value in list(node.inputs.values()) + list(node.widgets.values()):
            # Tool-mode links are intentionally stricter than legacy graph links:
            # source ids must already be strings, though numeric compound ids are allowed.
            if is_api_link(
                value,
                allow_tuple=False,
                require_string_node_id=True,
                require_numeric_node_id=True,
                allow_compound_node_id=True,
                require_int_slot=True,
            ):
                src = str(value[0])
                if src in nodes:
                    deps[nid].add(src)

    pending = set(nodes.keys())
    out: list[str] = []
    while pending:
        # Pick the node with no remaining unsatisfied deps; tie-break by id.
        ready = sorted(
            (nid for nid in pending if not (deps[nid] - set(out))),
            key=lambda nid: node_id_sort_key(nid, allow_compound=True),
        )
        if not ready:
            # Cycle or unresolved dep -- flush remainder in id order.
            out.extend(sorted(pending, key=lambda nid: node_id_sort_key(nid, allow_compound=True)))
            break
        for nid in ready:
            out.append(nid)
            pending.discard(nid)
    return out


def compute_variable_names(workflow_nodes: dict, edges: list) -> dict[str, str]:
    """Assign a stable variable name to each node id."""
    edges_out: dict[str, list[tuple[str, str]]] = {}
    for edge in edges:
        edges_out.setdefault(edge.from_node, []).append((edge.to_node, edge.to_input))

    role_conn = connection_role_name(workflow_nodes, edges_out)
    role_empty = empty_text_role(workflow_nodes)

    sorted_ids = sorted(
        workflow_nodes.keys(),
        key=lambda nid: (
            tuple(int(p) if p.isdigit() else (1 << 30, p) for p in str(nid).split(":"))
            if all(p.isdigit() for p in str(nid).split(":"))
            else (1 << 30, str(nid))
        ),
    )

    used: dict[str, int] = {}
    var_names: dict[str, str] = {}

    for nid in sorted_ids:
        node = workflow_nodes[nid]
        if nid in role_conn:
            base = role_conn[nid]
        elif nid in role_empty:
            base = role_empty[nid]
        else:
            base = safe_var(node.class_type)

        used[base] = used.get(base, 0) + 1
        if used[base] == 1:
            var_names[nid] = base
        else:
            var_names[nid] = f"{base}_{used[base]}"

    # Second pass: if a base name was used only once, drop the suffix.
    # (Already correct above; nothing to do.)
    return var_names


__all__ = [
    "compute_variable_names",
    "connection_role_name",
    "empty_text_role",
    "safe_var",
    "topological_node_order",
]
