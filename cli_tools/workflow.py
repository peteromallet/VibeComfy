"""Workflow I/O and utility functions."""

import json
import re
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Tuple, Optional, Any

# Type aliases
NodeId = int
LinkId = int
Node = Dict[str, Any]
Link = List[Any]  # [link_id, src_node, src_slot, dst_node, dst_slot, type]
Workflow = Dict[str, Any]
AdjacencyList = Dict[NodeId, List[Tuple[NodeId, str]]]  # node_id -> [(connected_id, dtype), ...]


def load(path: str) -> Workflow:
    """Load a workflow from JSON file."""
    with open(path) as f:
        return json.load(f)


def save(workflow: Workflow, path: str) -> None:
    """Save a workflow to JSON file."""
    with open(path, 'w') as f:
        json.dump(workflow, f, indent=2)


def get_versioned_output(base_path: str) -> str:
    """Get next available version if file exists.

    If 'output.json' exists, returns 'output_v2.json'.
    If 'output_v5.json' exists, returns 'output_v6.json'.
    """
    path = Path(base_path)
    if not path.exists():
        return base_path

    stem = path.stem
    suffix = path.suffix
    parent = path.parent

    # Check for existing _vN suffix
    match = re.match(r'(.+)_v(\d+)$', stem)
    if match:
        base, version = match.groups()
        next_version = int(version) + 1
    else:
        base = stem
        next_version = 2

    while True:
        new_path = parent / f"{base}_v{next_version}{suffix}"
        if not new_path.exists():
            return str(new_path)
        next_version += 1


def log_change(input_file: str, output_file: str, operation: str, details: str) -> None:
    """Append change to changelog file.

    Creates/appends to a .changelog file alongside the output file.
    """
    output_path = Path(output_file)
    # Strip _vN suffix for changelog name
    stem = output_path.stem
    match = re.match(r'(.+)_v\d+$', stem)
    if match:
        base_stem = match.group(1)
    else:
        base_stem = stem
    changelog = output_path.parent / f"{base_stem}.changelog"

    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    input_name = Path(input_file).name
    output_name = output_path.name

    with open(changelog, 'a') as f:
        f.write(f"{timestamp} | {operation} | {input_name} → {output_name}\n")
        for line in details.strip().split('\n'):
            f.write(f"  {line}\n")
        f.write("\n")


def get_nodes_dict(workflow: Workflow) -> Dict[NodeId, Node]:
    """Return dict of node_id -> node."""
    return {n['id']: n for n in workflow['nodes']}


def get_links_dict(workflow: Workflow) -> Dict[LinkId, Link]:
    """Return dict of link_id -> link tuple.

    Link format: [link_id, src_node, src_slot, dst_node, dst_slot, type]
    """
    return {l[0]: l for l in workflow['links']}


def build_adjacency(workflow: Workflow) -> Tuple[AdjacencyList, AdjacencyList]:
    """Build forward and reverse adjacency lists from workflow links.

    Returns:
        (forward, reverse) where:
        - forward[src_id] = [(dst_id, dtype), ...] - what each node outputs to
        - reverse[dst_id] = [(src_id, dtype), ...] - what feeds into each node
    """
    forward: AdjacencyList = {}
    reverse: AdjacencyList = {}

    for link in workflow['links']:
        link_id, src_id, src_slot, dst_id, dst_slot, dtype = link

        if src_id not in forward:
            forward[src_id] = []
        forward[src_id].append((dst_id, dtype))

        if dst_id not in reverse:
            reverse[dst_id] = []
        reverse[dst_id].append((src_id, dtype))

    return forward, reverse


def resolve_slot(node: Node, slot_spec, is_output: bool = True) -> Tuple[Optional[int], Optional[str]]:
    """Resolve a slot specification (index or name) to an index.

    slot_spec can be:
      - An integer (slot index)
      - A string that's a number ("0")
      - A slot name ("IMAGE", "image")

    Returns (slot_index, error_message) - error_message is None on success.
    """
    slots = node.get('outputs' if is_output else 'inputs', [])

    # Try as integer first
    try:
        idx = int(slot_spec)
        if idx < len(slots):
            return idx, None
        return None, f"slot {idx} out of range (max {len(slots) - 1})"
    except (ValueError, TypeError):
        pass

    # Try as name (case-insensitive)
    if isinstance(slot_spec, str):
        slot_lower = slot_spec.lower()
        for i, slot in enumerate(slots):
            if slot.get('name', '').lower() == slot_lower:
                return i, None
            # Also try matching the type
            if slot.get('type', '').lower() == slot_lower:
                return i, None

        # List available slots for error message
        available = [f"{i}:{s.get('name', '?')}" for i, s in enumerate(slots)]
        return None, f"slot '{slot_spec}' not found (available: {', '.join(available)})"

    return None, f"invalid slot specification: {slot_spec}"


def get_node(workflow: Workflow, node_id: NodeId) -> Optional[Node]:
    """Get a single node by ID."""
    for node in workflow['nodes']:
        if node['id'] == node_id:
            return node
    return None


def find_nodes_by_type(workflow: Workflow, type_pattern: str) -> List[Node]:
    """Find nodes matching type pattern (case-insensitive partial match)."""
    pattern = type_pattern.lower()
    return [n for n in workflow['nodes'] if pattern in n['type'].lower()]


def get_widget_values(node: Node) -> Any:
    """Get node widget values."""
    return node.get('widgets_values')


def get_node_title(node: Node) -> str:
    """Get display title for a node (title if set, else type)."""
    title = node.get('title')
    ntype = node.get('type', '?')
    if title and title != ntype:
        return f"{ntype} \"{title}\""
    return ntype


def format_node(node_id: NodeId, nodes_dict: Dict[NodeId, Node]) -> str:
    """Format a node for display: [id] Type "title"."""
    node = nodes_dict.get(node_id, {})
    title = node.get('title')
    ntype = node.get('type', '?')
    if title and title != ntype:
        return f"[{node_id}] {ntype} \"{title}\""
    return f"[{node_id}] {ntype}"
