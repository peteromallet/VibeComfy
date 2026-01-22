"""Workflow editing operations - copy, wire, delete, set values."""

import copy as copy_module
from typing import Dict, List, Set, Tuple, Optional, Any, Union
from . import workflow as wf_module


def parse_set_value(val_str: str) -> Any:
    """Parse a string value into appropriate type."""
    # Boolean
    if val_str.lower() == 'true':
        return True
    if val_str.lower() == 'false':
        return False

    # None
    if val_str.lower() == 'none' or val_str.lower() == 'null':
        return None

    # Number
    try:
        if '.' in val_str:
            return float(val_str)
        return int(val_str)
    except ValueError:
        pass

    # String (remove quotes if present)
    if (val_str.startswith('"') and val_str.endswith('"')) or \
       (val_str.startswith("'") and val_str.endswith("'")):
        return val_str[1:-1]

    return val_str


def delete_nodes(wf: Dict, node_ids: List[int], dry_run: bool = False) -> Dict:
    """Delete nodes and their links from workflow.

    Args:
        wf: Workflow dict (modified in place unless dry_run)
        node_ids: List of node IDs to delete
        dry_run: If True, return impact analysis without modifying workflow

    Returns:
        {
            'deleted_nodes': set of node_ids deleted,
            'removed_links': set of link_ids removed,
            'orphaned_inputs': list of affected inputs,
            'lost_outputs': list of affected outputs,
            'warnings': list of warning messages,
        }
    """
    nodes_dict = wf_module.get_nodes_dict(wf)
    links_dict = wf_module.get_links_dict(wf)

    deleted_node_ids = set()
    removed_link_ids = set()
    warnings = []

    for node_id in node_ids:
        if node_id not in nodes_dict:
            warnings.append(f"Node {node_id} not found, skipping")
            continue
        deleted_node_ids.add(node_id)

    # Find all links connected to deleted nodes
    for link in wf['links']:
        link_id, src_id, src_slot, dst_id, dst_slot, dtype = link
        if src_id in deleted_node_ids or dst_id in deleted_node_ids:
            removed_link_ids.add(link_id)

    # Analyze impact: find nodes that will have orphaned inputs
    orphaned_inputs = []
    for node in wf['nodes']:
        if node['id'] in deleted_node_ids:
            continue
        for i, inp in enumerate(node.get('inputs', [])):
            link_id = inp.get('link')
            if link_id in removed_link_ids:
                link = links_dict.get(link_id)
                if link:
                    src_node = nodes_dict.get(link[1], {})
                    orphaned_inputs.append({
                        'node_id': node['id'],
                        'node_type': node['type'],
                        'input_name': inp.get('name', f'input_{i}'),
                        'was_connected_to': link[1],
                        'was_connected_type': src_node.get('type', '?')
                    })

    # Analyze impact: find nodes that will lose outputs
    lost_outputs = []
    for node in wf['nodes']:
        if node['id'] in deleted_node_ids:
            continue
        for i, out in enumerate(node.get('outputs', [])):
            links = out.get('links') or []
            for link_id in links:
                if link_id in removed_link_ids:
                    link = links_dict.get(link_id)
                    if link and link[3] in deleted_node_ids:
                        dst_node = nodes_dict.get(link[3], {})
                        lost_outputs.append({
                            'node_id': node['id'],
                            'node_type': node['type'],
                            'output_name': out.get('name', f'output_{i}'),
                            'was_connected_to': link[3],
                            'was_connected_type': dst_node.get('type', '?')
                        })

    result = {
        'deleted_nodes': deleted_node_ids,
        'removed_links': removed_link_ids,
        'orphaned_inputs': orphaned_inputs,
        'lost_outputs': lost_outputs,
        'warnings': warnings,
    }

    if dry_run:
        return result

    # Actually perform the deletion
    wf['nodes'] = [n for n in wf['nodes'] if n['id'] not in deleted_node_ids]
    wf['links'] = [l for l in wf['links'] if l[0] not in removed_link_ids]

    # Clear link references in remaining nodes
    for node in wf['nodes']:
        for inp in node.get('inputs', []):
            if inp.get('link') in removed_link_ids:
                inp['link'] = None
        for out in node.get('outputs', []):
            if out.get('links'):
                out['links'] = [l for l in out['links'] if l not in removed_link_ids]

    return result


def copy_node(wf: Dict, node_id: int, title: str = None,
              set_values: Dict[Union[int, str], Any] = None) -> Dict:
    """Copy a node as an unconnected template.

    Args:
        wf: Workflow dict (modified in place)
        node_id: ID of node to copy
        title: Optional title for new node
        set_values: Optional dict of {slot_index_or_name: value} to set

    Returns:
        {
            'new_node': the created node dict,
            'new_id': the new node's ID,
            'error': error message if failed,
        }
    """
    nodes_dict = wf_module.get_nodes_dict(wf)

    template = nodes_dict.get(node_id)
    if not template:
        return {'error': f'Node {node_id} not found'}

    new_node = copy_module.deepcopy(template)
    new_node['id'] = wf['last_node_id'] + 1
    wf['last_node_id'] = new_node['id']

    # Clear connections
    for inp in new_node.get('inputs', []):
        inp['link'] = None
    for out in new_node.get('outputs', []):
        out['links'] = []

    # Offset position
    pos = template.get('pos', [0, 0])
    if isinstance(pos, dict):
        new_node['pos'] = {'0': pos.get('0', 0) + 50, '1': pos.get('1', 0) + 50}
    else:
        new_node['pos'] = [pos[0] + 50, pos[1] + 50]

    # Apply title
    if title:
        new_node['title'] = title

    # Apply set values
    if set_values:
        widgets = new_node.get('widgets_values', [])
        warnings = []
        for key, val in set_values.items():
            if isinstance(widgets, list):
                try:
                    idx = int(key)
                    while len(widgets) <= idx:
                        widgets.append(None)
                    widgets[idx] = val
                except (ValueError, TypeError):
                    warnings.append(f"Cannot use key '{key}' on list-style widgets (use numeric index)")
            elif isinstance(widgets, dict):
                # Warn if using numeric key that doesn't exist (likely user error)
                try:
                    int(key)
                    if key not in widgets and str(key) not in widgets:
                        warnings.append(f"Numeric key '{key}' on dict-style widget - use key name (e.g., 'indexes')")
                except ValueError:
                    pass
                widgets[key] = val
        new_node['widgets_values'] = widgets
        if warnings:
            return {
                'new_node': new_node,
                'new_id': new_node['id'],
                'template_type': template['type'],
                'warnings': warnings,
            }

    wf['nodes'].append(new_node)

    return {
        'new_node': new_node,
        'new_id': new_node['id'],
        'template_type': template['type'],
    }


def wire_nodes(wf: Dict, src_id: int, src_slot: Union[int, str],
               dst_id: int, dst_slot: Union[int, str]) -> Dict:
    """Create a connection between two nodes.

    Args:
        wf: Workflow dict (modified in place)
        src_id: Source node ID
        src_slot: Source output slot (index or name)
        dst_id: Destination node ID
        dst_slot: Destination input slot (index or name)

    Returns:
        {
            'link_id': new link ID,
            'dtype': data type of connection,
            'replaced_link': ID of replaced link if any,
            'error': error message if failed,
        }
    """
    nodes_dict = wf_module.get_nodes_dict(wf)

    src_node = nodes_dict.get(src_id)
    dst_node = nodes_dict.get(dst_id)

    if not src_node:
        return {'error': f'Source node {src_id} not found'}
    if not dst_node:
        return {'error': f'Destination node {dst_id} not found'}

    # Resolve slot specifications
    src_slot_idx, err = wf_module.resolve_slot(src_node, src_slot, is_output=True)
    if err:
        return {'error': f'Source {err}'}

    dst_slot_idx, err = wf_module.resolve_slot(dst_node, dst_slot, is_output=False)
    if err:
        return {'error': f'Destination {err}'}

    # Get data type from source output
    outputs = src_node.get('outputs', [])
    dtype = outputs[src_slot_idx].get('type', '*')

    # Check if destination slot already has a connection
    inputs = dst_node.get('inputs', [])
    existing_link = inputs[dst_slot_idx].get('link')
    replaced_link = None

    if existing_link:
        replaced_link = existing_link
        # Remove the existing link
        wf['links'] = [l for l in wf['links'] if l[0] != existing_link]
        # Clear from source node's output
        for node in wf['nodes']:
            for out in node.get('outputs', []):
                if out.get('links') and existing_link in out['links']:
                    out['links'].remove(existing_link)

    # Create new link
    new_link_id = wf['last_link_id'] + 1
    wf['last_link_id'] = new_link_id

    new_link = [new_link_id, src_id, src_slot_idx, dst_id, dst_slot_idx, dtype]
    wf['links'].append(new_link)

    # Update node references
    dst_node['inputs'][dst_slot_idx]['link'] = new_link_id
    if src_node['outputs'][src_slot_idx].get('links') is None:
        src_node['outputs'][src_slot_idx]['links'] = []
    src_node['outputs'][src_slot_idx]['links'].append(new_link_id)

    return {
        'link_id': new_link_id,
        'dtype': dtype,
        'replaced_link': replaced_link,
        'src_slot': src_slot_idx,
        'dst_slot': dst_slot_idx,
    }


def disconnect_node(wf: Dict, node_id: int) -> Dict:
    """Remove all connections to/from a node.

    Args:
        wf: Workflow dict (modified in place)
        node_id: Node ID to disconnect

    Returns:
        {
            'removed_links': set of removed link IDs,
            'error': error message if failed,
        }
    """
    nodes_dict = wf_module.get_nodes_dict(wf)

    if node_id not in nodes_dict:
        return {'error': f'Node {node_id} not found'}

    removed_link_ids = set()
    for link in wf['links']:
        link_id, src_id, src_slot, dst_id, dst_slot, dtype = link
        if src_id == node_id or dst_id == node_id:
            removed_link_ids.add(link_id)

    # Remove links
    wf['links'] = [l for l in wf['links'] if l[0] not in removed_link_ids]

    # Clear link references in all nodes
    for node in wf['nodes']:
        for inp in node.get('inputs', []):
            if inp.get('link') in removed_link_ids:
                inp['link'] = None
        for out in node.get('outputs', []):
            if out.get('links'):
                out['links'] = [l for l in out['links'] if l not in removed_link_ids]

    return {'removed_links': removed_link_ids}


def set_widget_values(wf: Dict, node_id: int,
                      values: Dict[Union[int, str], Any]) -> Dict:
    """Set widget values on a node.

    Args:
        wf: Workflow dict (modified in place)
        node_id: Node ID to modify
        values: Dict of {slot_index_or_name: value}

    Returns:
        {
            'set_values': list of (key, value) pairs that were set,
            'error': error message if failed,
        }
    """
    nodes_dict = wf_module.get_nodes_dict(wf)

    node = nodes_dict.get(node_id)
    if not node:
        return {'error': f'Node {node_id} not found'}

    widgets = node.get('widgets_values', [])
    if widgets is None:
        widgets = []

    set_values = []
    warnings = []
    for key, val in values.items():
        if isinstance(widgets, list):
            try:
                idx = int(key)
                while len(widgets) <= idx:
                    widgets.append(None)
                widgets[idx] = val
                set_values.append((idx, val))
            except (ValueError, TypeError):
                warnings.append(f"Cannot use key '{key}' on list-style widgets (use numeric index)")
        elif isinstance(widgets, dict):
            # Warn if using numeric key that doesn't exist (likely user error)
            try:
                int(key)
                if key not in widgets and str(key) not in widgets:
                    warnings.append(f"Numeric key '{key}' on dict-style widget - use key name (e.g., 'indexes')")
            except ValueError:
                pass
            widgets[key] = val
            set_values.append((key, val))

    node['widgets_values'] = widgets
    result = {'set_values': set_values}
    if warnings:
        result['warnings'] = warnings
    return result


def create_node(wf: Dict, node_type: str, title: str = None,
                inputs: List[Tuple[str, str]] = None,
                outputs: List[Tuple[str, str]] = None) -> Dict:
    """Create a new node of the given type.

    Args:
        wf: Workflow dict (modified in place)
        node_type: Type of node to create
        title: Optional title
        inputs: Optional list of (name, type) tuples for inputs
        outputs: Optional list of (name, type) tuples for outputs

    Returns:
        {
            'new_node': the created node dict,
            'new_id': the new node's ID,
        }
    """
    new_id = wf['last_node_id'] + 1
    wf['last_node_id'] = new_id

    new_node = {
        'id': new_id,
        'type': node_type,
        'pos': [100, 100],
        'size': [200, 100],
        'flags': {},
        'order': len(wf['nodes']),
        'mode': 0,
        'inputs': [],
        'outputs': [],
        'properties': {},
        'widgets_values': [],
    }

    if title:
        new_node['title'] = title

    if inputs:
        for name, dtype in inputs:
            new_node['inputs'].append({
                'name': name,
                'type': dtype,
                'link': None,
            })

    if outputs:
        for name, dtype in outputs:
            new_node['outputs'].append({
                'name': name,
                'type': dtype,
                'links': [],
                'slot_index': len(new_node['outputs']),
            })

    wf['nodes'].append(new_node)

    return {
        'new_node': new_node,
        'new_id': new_id,
    }


def inline_variables(wf: Dict, dry_run: bool = False) -> Dict:
    """Replace GetNode/SetNode pairs with direct connections.

    Args:
        wf: Workflow dict (modified in place unless dry_run)
        dry_run: If True, return analysis without modifying

    Returns:
        {
            'pairs_found': list of (name, set_node, get_nodes),
            'nodes_to_delete': set of node IDs,
            'links_to_create': list of (src_id, src_slot, dst_id, dst_slot, dtype),
            'links_to_remove': set of link IDs,
        }
    """
    nodes_dict = wf_module.get_nodes_dict(wf)
    links_dict = wf_module.get_links_dict(wf)

    # Find all SetNode and GetNode nodes
    set_nodes = {}  # name -> node
    get_nodes = {}  # name -> [nodes]

    for node in wf['nodes']:
        if node['type'] == 'SetNode':
            name = node.get('widgets_values', [None])[0]
            if name:
                set_nodes[name] = node
        elif node['type'] == 'GetNode':
            name = node.get('widgets_values', [None])[0]
            if name:
                if name not in get_nodes:
                    get_nodes[name] = []
                get_nodes[name].append(node)

    # Find matching pairs
    pairs = []
    for name in set_nodes:
        if name in get_nodes:
            pairs.append((name, set_nodes[name], get_nodes[name]))

    nodes_to_delete = set()
    links_to_create = []
    links_to_remove = set()

    for name, set_node, get_node_list in pairs:
        set_id = set_node['id']

        # Find what feeds into the SetNode
        set_input = set_node.get('inputs', [{}])[0]
        set_link_id = set_input.get('link')

        if not set_link_id:
            continue

        set_link = links_dict.get(set_link_id)
        if not set_link:
            continue

        src_id = set_link[1]
        src_slot = set_link[2]
        dtype = set_link[5]

        nodes_to_delete.add(set_id)
        links_to_remove.add(set_link_id)

        for get_node in get_node_list:
            get_id = get_node['id']
            nodes_to_delete.add(get_id)

            get_outputs = get_node.get('outputs', [{}])
            if not get_outputs:
                continue

            get_output = get_outputs[0]
            get_links = get_output.get('links', [])

            for get_link_id in get_links:
                get_link = links_dict.get(get_link_id)
                if not get_link:
                    continue

                dst_id = get_link[3]
                dst_slot = get_link[4]

                links_to_remove.add(get_link_id)
                links_to_create.append((src_id, src_slot, dst_id, dst_slot, dtype))

    result = {
        'pairs_found': pairs,
        'nodes_to_delete': nodes_to_delete,
        'links_to_create': links_to_create,
        'links_to_remove': links_to_remove,
    }

    if dry_run:
        return result

    # Remove old links
    wf['links'] = [l for l in wf['links'] if l[0] not in links_to_remove]

    # Create new links
    for src_id, src_slot, dst_id, dst_slot, dtype in links_to_create:
        new_link_id = wf['last_link_id'] + 1
        wf['last_link_id'] = new_link_id

        new_link = [new_link_id, src_id, src_slot, dst_id, dst_slot, dtype]
        wf['links'].append(new_link)

        # Update node references
        dst_node = nodes_dict.get(dst_id)
        src_node = nodes_dict.get(src_id)

        if dst_node and dst_slot < len(dst_node.get('inputs', [])):
            dst_node['inputs'][dst_slot]['link'] = new_link_id

        if src_node and src_slot < len(src_node.get('outputs', [])):
            if src_node['outputs'][src_slot].get('links') is None:
                src_node['outputs'][src_slot]['links'] = []
            src_node['outputs'][src_slot]['links'].append(new_link_id)

    # Delete nodes
    wf['nodes'] = [n for n in wf['nodes'] if n['id'] not in nodes_to_delete]

    # Clear any remaining link references
    for node in wf['nodes']:
        for inp in node.get('inputs', []):
            if inp.get('link') in links_to_remove:
                inp['link'] = None
        for out in node.get('outputs', []):
            if out.get('links'):
                out['links'] = [l for l in out['links'] if l not in links_to_remove]

    return result
