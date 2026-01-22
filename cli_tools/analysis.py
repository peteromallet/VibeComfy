"""Workflow analysis functions - structure analysis, path finding, validation."""

from collections import deque
from typing import Dict, List, Set, Tuple, Optional, Any
from . import workflow as wf_module
from .descriptions import get_node_description


def get_node_role(node_id: int, forward: Dict, reverse: Dict,
                  nodes_dict: Dict, subgraph_nodes: Set[int]) -> str:
    """Determine a node's role based on what it connects to.

    Returns a category like 'UPSCALING', 'ENCODING', 'SAMPLING', etc.
    """
    node = nodes_dict.get(node_id, {})

    outputs_to = []
    for dst_id, dtype in forward.get(node_id, []):
        if dst_id in subgraph_nodes:
            outputs_to.append((dst_id, dtype))

    inputs_from = []
    for src_id, dtype in reverse.get(node_id, []):
        if src_id in subgraph_nodes:
            inputs_from.append((src_id, dtype))

    ntype = node.get('type', '').lower()

    # Check output types
    out_types = {dtype.upper() for _, dtype in outputs_to if dtype}
    in_types = {dtype.upper() for _, dtype in inputs_from if dtype}

    # Categorize by function
    if 'load' in ntype and ('video' in ntype or 'image' in ntype):
        return 'INPUT'
    if 'save' in ntype or 'combine' in ntype or 'output' in ntype:
        return 'OUTPUT'
    if 'upscale' in ntype or 'resize' in ntype:
        return 'UPSCALING'
    if 'sharpen' in ntype or 'blur' in ntype or 'enhance' in ntype:
        return 'ENHANCEMENT'
    if 'encode' in ntype and 'vace' in ntype:
        return 'ENCODING'
    if 'encode' in ntype:
        return 'ENCODING'
    if 'decode' in ntype:
        return 'DECODING'
    if 'sampler' in ntype or 'sample' in ntype:
        return 'SAMPLING'
    if 'math' in ntype or 'expression' in ntype or 'calc' in ntype:
        return 'MATH/LOGIC'
    if 'switch' in ntype or 'select' in ntype or 'mux' in ntype:
        return 'ROUTING'
    if 'getnode' in ntype or 'setnode' in ntype:
        return 'VARIABLES'
    if 'loop' in ntype:
        return 'CONTROL_FLOW'
    if 'context' in ntype or 'options' in ntype or 'config' in ntype:
        return 'CONFIGURATION'
    if 'get' in ntype and 'size' in ntype:
        return 'DATA_HANDLING'
    if 'loader' in ntype or 'load' in ntype:
        return 'MODEL_LOADING'

    # Check by data types
    if 'LATENT' in out_types or 'LATENT' in in_types:
        return 'LATENT_PROCESSING'
    if 'IMAGE' in out_types and 'IMAGE' in in_types:
        return 'IMAGE_PROCESSING'
    if 'MODEL' in out_types or 'VAE' in out_types or 'CLIP' in out_types:
        return 'MODEL_LOADING'

    return 'PROCESSING'


def categorize_pipeline(dtypes: List[str]) -> str:
    """Categorize a pipeline based on the data types it uses."""
    dtype_set = set(d.upper() for d in dtypes if d)

    if 'WANVIDEOVACE' in dtype_set or any('VACE' in d for d in dtype_set):
        return 'VACE'
    if 'LATENT' in dtype_set:
        return 'Latent'
    if 'IMAGE' in dtype_set:
        return 'Image'
    if 'VIDEO' in dtype_set:
        return 'Video'
    return 'Mixed'


def categorize_entry_points(entry_points: List[int], nodes_dict: Dict) -> Tuple[List[int], List[int]]:
    """Categorize entry points into primary inputs and model loaders.

    Returns (primary_inputs, model_loaders).
    """
    primary_inputs = []
    model_loaders = []

    for nid in entry_points:
        ntype = nodes_dict.get(nid, {}).get('type', '').lower()
        if any(k in ntype for k in ['loadvideo', 'loadimage', 'vhs_load']):
            primary_inputs.append(nid)
        elif any(k in ntype for k in ['loader', 'load', 'model', 'vae', 'lora']):
            model_loaders.append(nid)

    return primary_inputs, model_loaders


def categorize_exit_points(exit_points: List[int], nodes_dict: Dict) -> List[int]:
    """Categorize exit points to find primary outputs."""
    primary_outputs = []

    for nid in exit_points:
        ntype = nodes_dict.get(nid, {}).get('type', '').lower()
        if any(k in ntype for k in ['save', 'combine', 'output']):
            primary_outputs.append(nid)

    return primary_outputs


def detect_workflow_type(wf: Dict) -> str:
    """Detect the type of workflow (Video, Image, etc)."""
    all_types = ' '.join(n.get('type', '').lower() for n in wf['nodes'])
    if 'video' in all_types or 'vhs' in all_types:
        return 'Video'
    return 'General'


def analyze_workflow(wf: Dict) -> Dict:
    """
    Analyze workflow structure.

    Returns:
        {
            'entry_points': [node_ids...],   # Nodes with no connected inputs
            'exit_points': [node_ids...],    # Nodes with no connected outputs
            'primary_inputs': [node_ids...], # Video/image loaders
            'model_loaders': [node_ids...],  # Model/VAE/LoRA loaders
            'primary_outputs': [node_ids...],# Save/combine nodes
            'workflow_type': str,            # 'Video' or 'General'
            'pipelines': [...],              # Main data flow paths
            'variables': [...],              # SetNode/GetNode variable info
            'var_lookup': {...},             # get_node_id -> var info
            'loops': [...],                  # Detected loops
            'sections': {...},               # Grouped by Label nodes
        }
    """
    nodes_dict = wf_module.get_nodes_dict(wf)
    links_dict = wf_module.get_links_dict(wf)

    # Visual-only node types to exclude
    VISUAL_TYPES = {'Note', 'MarkdownNote', 'Label (rgthree)', 'PrimitiveNode'}

    # Resolve SetNode/GetNode pairs (variables)
    set_nodes = {}  # name -> node_id
    get_nodes_map = {}  # get_node_id -> set_node_id

    for node in wf['nodes']:
        if node['type'] == 'SetNode':
            name = node.get('title', '').replace('Set_', '')
            if name:
                set_nodes[name] = node['id']

    for node in wf['nodes']:
        if node['type'] == 'GetNode':
            name = node.get('title', '').replace('Get_', '')
            if name and name in set_nodes:
                get_nodes_map[node['id']] = set_nodes[name]

    # Build adjacency with resolved Get/Set connections
    backward = {}  # dst_id -> [(src_id, link_id, dtype), ...]
    for link in wf['links']:
        link_id, src_id, _, dst_id, _, dtype = link
        if dst_id not in backward:
            backward[dst_id] = []
        backward[dst_id].append((src_id, link_id, dtype))

    # Add implicit connections: GetNode <- SetNode's input
    for get_id, set_id in get_nodes_map.items():
        set_node = nodes_dict.get(set_id)
        if set_node:
            if get_id not in backward:
                backward[get_id] = []
            set_inputs = backward.get(set_id, [])
            for src_id, _, dtype in set_inputs:
                backward[get_id].append((src_id, -1, dtype))

    # Find entry points: nodes with no connected inputs
    entry_points = []
    for node in wf['nodes']:
        node_type = node['type']
        if node_type in VISUAL_TYPES or 'label' in node_type.lower():
            continue
        if node['id'] in get_nodes_map:
            continue

        inputs = node.get('inputs', [])
        if not inputs:
            entry_points.append(node['id'])
        else:
            all_unconnected = all(inp.get('link') is None for inp in inputs)
            if all_unconnected:
                entry_points.append(node['id'])

    # Find exit points: nodes with no connected outputs
    exit_points = []
    for node in wf['nodes']:
        node_type = node['type']
        if node_type in VISUAL_TYPES or 'label' in node_type.lower():
            continue

        if node_type == 'SetNode':
            name = node.get('title', '').replace('Set_', '')
            has_consumers = any(
                n['type'] == 'GetNode' and n.get('title', '').replace('Get_', '') == name
                for n in wf['nodes']
            )
            if has_consumers:
                continue

        outputs = node.get('outputs', [])
        if not outputs:
            exit_points.append(node['id'])
        else:
            all_unconnected = all(not out.get('links') for out in outputs)
            if all_unconnected:
                exit_points.append(node['id'])

    # Categorize entry/exit points
    primary_inputs, model_loaders = categorize_entry_points(entry_points, nodes_dict)
    primary_outputs = categorize_exit_points(exit_points, nodes_dict)
    workflow_type = detect_workflow_type(wf)

    # Trace pipelines backwards from each exit point
    def trace_pipeline(exit_id):
        paths = []

        def dfs(node_id, current_path, dtype):
            node = nodes_dict.get(node_id)
            if not node:
                return
            current_path = [(node_id, dtype)] + current_path
            upstream = backward.get(node_id, [])
            if not upstream:
                paths.append(current_path)
                return
            for src_id, _, src_dtype in upstream:
                dfs(src_id, current_path, src_dtype)

        dfs(exit_id, [], '')
        return paths

    pipelines = []
    for exit_id in exit_points:
        exit_node = nodes_dict.get(exit_id)
        if not exit_node:
            continue
        paths = trace_pipeline(exit_id)
        if not paths:
            continue
        main_path = max(paths, key=len) if paths else []
        if len(main_path) >= 2:
            dtypes = [dtype for _, dtype in main_path if dtype]
            primary_dtype = categorize_pipeline(dtypes)
            pipelines.append({
                'exit_id': exit_id,
                'exit_type': exit_node['type'],
                'path': main_path,
                'category': primary_dtype,
            })

    # Group by Label nodes (sections)
    sections = {}
    for node in wf['nodes']:
        if 'label' in node['type'].lower():
            title = node.get('title') or node.get('widgets_values', ['Unnamed'])[0]
            if isinstance(title, str) and len(title) > 2:
                sections[node['id']] = {
                    'title': title,
                    'pos': node.get('pos', [0, 0]),
                }

    # Build variable connections
    variables = []
    for name, set_id in set_nodes.items():
        set_node = nodes_dict.get(set_id)
        if not set_node:
            continue

        set_inputs = backward.get(set_id, [])
        source_id = set_inputs[0][0] if set_inputs else None
        source_node = nodes_dict.get(source_id) if source_id else None

        get_ids = [gid for gid, sid in get_nodes_map.items() if sid == set_id]

        consumers = []
        for get_id in get_ids:
            for link in wf['links']:
                link_id, src_id, src_slot, dst_id, dst_slot, dtype = link
                if src_id == get_id:
                    consumer = nodes_dict.get(dst_id)
                    if consumer:
                        consumers.append({
                            'node_id': dst_id,
                            'node_type': consumer['type'],
                            'input_slot': dst_slot,
                            'dtype': dtype,
                        })

        variables.append({
            'name': name,
            'set_id': set_id,
            'source_id': source_id,
            'source_type': source_node['type'] if source_node else None,
            'get_ids': get_ids,
            'consumers': consumers,
        })

    # Detect loops
    loops = []
    loop_starts = {}
    for node in wf['nodes']:
        ntype = node['type'].lower()
        if 'loopstart' in ntype or 'forstart' in ntype or 'whilestart' in ntype:
            name = node.get('title', node['type'])
            loop_info = {'start_id': node['id'], 'start_type': node['type'], 'name': name}

            for inp in node.get('inputs', []):
                inp_name = inp.get('name', '').lower()
                if 'total' in inp_name or 'iteration' in inp_name or 'count' in inp_name:
                    link_id = inp.get('link')
                    if link_id and link_id in links_dict:
                        src_id = links_dict[link_id][1]
                        src_node = nodes_dict.get(src_id, {})
                        src_type = src_node.get('type', '')

                        if 'constant' in src_type.lower() or 'primitive' in src_type.lower():
                            vals = src_node.get('widgets_values', [])
                            if vals and isinstance(vals[0], (int, float)):
                                loop_info['iterations'] = int(vals[0])
                                loop_info['iterations_source'] = 'constant'
                        else:
                            loop_info['iterations_source'] = src_type
                            loop_info['iterations_node'] = src_id
                    break

            loop_starts[node['id']] = loop_info

    for node in wf['nodes']:
        ntype = node['type'].lower()
        if 'loopend' in ntype or 'forend' in ntype or 'whileend' in ntype:
            for inp in node.get('inputs', []):
                link_id = inp.get('link')
                if link_id and link_id in links_dict:
                    src_id = links_dict[link_id][1]
                    if src_id in loop_starts:
                        loop_starts[src_id]['end_id'] = node['id']
                        loop_starts[src_id]['end_type'] = node['type']
                        loops.append(loop_starts[src_id])
                        break

    # Build variable lookup
    var_lookup = {}
    for var in variables:
        for get_id in var.get('get_ids', []):
            var_lookup[get_id] = {
                'name': var['name'],
                'source_id': var.get('source_id'),
                'source_type': var.get('source_type'),
            }

    return {
        'entry_points': sorted(entry_points),
        'exit_points': sorted(exit_points),
        'primary_inputs': primary_inputs,
        'model_loaders': model_loaders,
        'primary_outputs': primary_outputs,
        'workflow_type': workflow_type,
        'pipelines': pipelines,
        'variables': variables,
        'var_lookup': var_lookup,
        'loops': loops,
        'sections': sections,
    }


def get_workflow_info(wf: Dict) -> Dict:
    """Get basic workflow statistics."""
    nodes = wf['nodes']
    links = wf['links']

    type_counts = {}
    for n in nodes:
        t = n['type']
        type_counts[t] = type_counts.get(t, 0) + 1

    return {
        'node_count': len(nodes),
        'link_count': len(links),
        'last_node_id': wf.get('last_node_id'),
        'last_link_id': wf.get('last_link_id'),
        'type_counts': type_counts,
    }


def find_path(wf: Dict, from_node: int, to_node: int) -> Optional[List[int]]:
    """Find shortest path between two nodes using BFS.

    Returns list of node IDs from start to end, or None if no path exists.
    """
    forward, _ = wf_module.build_adjacency(wf)

    queue = deque([(from_node, [from_node])])
    visited = {from_node}

    while queue:
        current, path = queue.popleft()
        if current == to_node:
            return path

        for next_id, dtype in forward.get(current, []):
            if next_id not in visited:
                visited.add(next_id)
                queue.append((next_id, path + [next_id]))

    return None


def find_upstream(wf: Dict, target_id: int, max_depth: int = 999,
                  input_filter: str = None) -> Dict:
    """Find all nodes upstream of a target node.

    Returns:
        {
            'nodes': {node_id: depth, ...},
            'links': set of link_ids,
            'edges': [(src_id, src_type, src_slot_name, dst_id, dst_type, dst_slot_name, dtype), ...]
        }
    """
    nodes_dict = wf_module.get_nodes_dict(wf)
    links_dict = wf_module.get_links_dict(wf)

    # Build backward adjacency
    backward = {}
    for link in wf['links']:
        link_id, src_id, src_slot, dst_id, dst_slot, dtype = link
        if dst_id not in backward:
            backward[dst_id] = []
        backward[dst_id].append((src_id, link_id, src_slot, dst_slot, dtype))

    target_node = nodes_dict.get(target_id)
    if not target_node:
        return {'nodes': {}, 'links': set(), 'edges': [], 'error': f'Node {target_id} not found'}

    # Determine starting points
    start_nodes = []
    if input_filter:
        for inp in target_node.get('inputs', []):
            if input_filter.lower() in inp.get('name', '').lower():
                if inp.get('link'):
                    link = links_dict.get(inp['link'])
                    if link:
                        start_nodes.append((link[1], inp['link']))
                break
    else:
        for inp in target_node.get('inputs', []):
            link_id = inp.get('link')
            if link_id:
                link = links_dict.get(link_id)
                if link:
                    start_nodes.append((link[1], link_id))

    # BFS backward
    visited_nodes = {target_id: 0}
    visited_links = set()
    queue = deque()

    for src_id, link_id in start_nodes:
        visited_links.add(link_id)
        if src_id not in visited_nodes:
            visited_nodes[src_id] = 1
            if 1 < max_depth:
                queue.append((src_id, 1))

    while queue:
        node_id, depth = queue.popleft()
        if depth >= max_depth:
            continue

        for src_id, link_id, src_slot, dst_slot, dtype in backward.get(node_id, []):
            visited_links.add(link_id)
            if src_id not in visited_nodes:
                visited_nodes[src_id] = depth + 1
                queue.append((src_id, depth + 1))

    # Collect edges
    edges = []
    for link in wf['links']:
        link_id, src_id, src_slot, dst_id, dst_slot, dtype = link
        if link_id in visited_links:
            src_node = nodes_dict.get(src_id, {})
            dst_node = nodes_dict.get(dst_id, {})

            src_out_name = '?'
            for i, out in enumerate(src_node.get('outputs', [])):
                if i == src_slot:
                    src_out_name = out.get('name', '?')
                    break

            dst_in_name = '?'
            for i, inp in enumerate(dst_node.get('inputs', [])):
                if i == dst_slot:
                    dst_in_name = inp.get('name', '?')
                    break

            edges.append((
                src_id, src_node.get('type', '?'), src_out_name,
                dst_id, dst_node.get('type', '?'), dst_in_name, dtype
            ))

    return {
        'nodes': visited_nodes,
        'links': visited_links,
        'edges': edges,
        'target_id': target_id,
    }


def find_downstream(wf: Dict, source_id: int, max_depth: int = 999,
                    output_filter: str = None) -> Dict:
    """Find all nodes downstream of a source node.

    Returns same structure as find_upstream.
    """
    nodes_dict = wf_module.get_nodes_dict(wf)

    # Build forward adjacency
    forward = {}
    for link in wf['links']:
        link_id, src_id, src_slot, dst_id, dst_slot, dtype = link
        if src_id not in forward:
            forward[src_id] = []
        forward[src_id].append((dst_id, link_id, src_slot, dst_slot, dtype))

    source_node = nodes_dict.get(source_id)
    if not source_node:
        return {'nodes': {}, 'links': set(), 'edges': [], 'error': f'Node {source_id} not found'}

    # Determine starting points
    start_nodes = []
    if output_filter:
        for i, out in enumerate(source_node.get('outputs', [])):
            if output_filter.lower() in out.get('name', '').lower():
                for link_id in (out.get('links') or []):
                    for link in wf['links']:
                        if link[0] == link_id:
                            start_nodes.append((link[3], link_id))
                            break
                break
    else:
        for out in source_node.get('outputs', []):
            for link_id in (out.get('links') or []):
                for link in wf['links']:
                    if link[0] == link_id:
                        start_nodes.append((link[3], link_id))
                        break

    # BFS forward
    visited_nodes = {source_id: 0}
    visited_links = set()
    queue = deque()

    for dst_id, link_id in start_nodes:
        visited_links.add(link_id)
        if dst_id not in visited_nodes:
            visited_nodes[dst_id] = 1
            if 1 < max_depth:
                queue.append((dst_id, 1))

    while queue:
        node_id, depth = queue.popleft()
        if depth >= max_depth:
            continue

        for dst_id, link_id, src_slot, dst_slot, dtype in forward.get(node_id, []):
            visited_links.add(link_id)
            if dst_id not in visited_nodes:
                visited_nodes[dst_id] = depth + 1
                queue.append((dst_id, depth + 1))

    # Collect edges
    edges = []
    for link in wf['links']:
        link_id, src_id, src_slot, dst_id, dst_slot, dtype = link
        if link_id in visited_links:
            src_node = nodes_dict.get(src_id, {})
            dst_node = nodes_dict.get(dst_id, {})

            src_out_name = '?'
            for i, out in enumerate(src_node.get('outputs', [])):
                if i == src_slot:
                    src_out_name = out.get('name', '?')
                    break

            dst_in_name = '?'
            for i, inp in enumerate(dst_node.get('inputs', [])):
                if i == dst_slot:
                    dst_in_name = inp.get('name', '?')
                    break

            edges.append((
                src_id, src_node.get('type', '?'), src_out_name,
                dst_id, dst_node.get('type', '?'), dst_in_name, dtype
            ))

    return {
        'nodes': visited_nodes,
        'links': visited_links,
        'edges': edges,
        'source_id': source_id,
    }


def find_subgraph(wf: Dict, start_id: int, end_id: int) -> Dict:
    """Find all nodes between two nodes (subgraph extraction).

    Returns:
        {
            'nodes': set of node_ids between start and end,
            'edges': [(src_id, dst_id, dtype), ...],
            'sorted_nodes': topologically sorted node ids,
        }
    """
    nodes_dict = wf_module.get_nodes_dict(wf)

    if start_id not in nodes_dict:
        return {'error': f'Start node {start_id} not found'}
    if end_id not in nodes_dict:
        return {'error': f'End node {end_id} not found'}

    # Build adjacency
    forward = {}
    backward = {}
    for link in wf['links']:
        src_id, dst_id = link[1], link[3]
        dtype = link[5]
        if src_id not in forward:
            forward[src_id] = []
        forward[src_id].append((dst_id, dtype))
        if dst_id not in backward:
            backward[dst_id] = []
        backward[dst_id].append((src_id, dtype))

    # Forward BFS from start
    reachable_from_start = set()
    queue = deque([start_id])
    while queue:
        nid = queue.popleft()
        if nid in reachable_from_start:
            continue
        reachable_from_start.add(nid)
        for dst, _ in forward.get(nid, []):
            queue.append(dst)

    # Backward BFS from end
    can_reach_end = set()
    queue = deque([end_id])
    while queue:
        nid = queue.popleft()
        if nid in can_reach_end:
            continue
        can_reach_end.add(nid)
        for src, _ in backward.get(nid, []):
            queue.append(src)

    # Intersection
    between = reachable_from_start & can_reach_end

    if not between:
        return {'error': f'No path from [{start_id}] to [{end_id}]', 'nodes': set()}

    # Collect edges within subgraph
    edges = []
    for nid in between:
        for dst, dtype in forward.get(nid, []):
            if dst in between:
                edges.append((nid, dst, dtype))

    # Topological sort
    in_degree = {nid: 0 for nid in between}
    for src, dst, _ in edges:
        in_degree[dst] += 1

    sorted_nodes = []
    queue = deque([nid for nid in between if in_degree[nid] == 0])
    while queue:
        nid = queue.popleft()
        sorted_nodes.append(nid)
        for dst, _ in forward.get(nid, []):
            if dst in between:
                in_degree[dst] -= 1
                if in_degree[dst] == 0:
                    queue.append(dst)

    return {
        'nodes': between,
        'edges': edges,
        'sorted_nodes': sorted_nodes,
        'start_id': start_id,
        'end_id': end_id,
    }


def find_orphans(wf: Dict, primary_only: bool = False) -> List[Dict]:
    """Find nodes with unconnected inputs.

    Returns list of:
        {
            'node_id': int,
            'node_type': str,
            'input_slot': int,
            'input_name': str,
            'input_type': str,
            'likely_required': bool,
            'is_primary': bool,
            'broken_link': int or None
        }
    """
    nodes_dict = wf_module.get_nodes_dict(wf)
    links_dict = wf_module.get_links_dict(wf)

    optional_heavy_types = {
        'WanVideoSampler', 'WanVideoModelLoader', 'WanVideoVACEEncode',
        'VHS_LoadVideo', 'WanVideoEncode', 'WanVideoLoraSelect'
    }

    orphans = []
    for node in wf['nodes']:
        node_id = node['id']
        node_type = node['type']
        inputs = node.get('inputs', [])

        for i, inp in enumerate(inputs):
            link_id = inp.get('link')
            inp_name = inp.get('name', f'input_{i}')
            inp_type = inp.get('type', '?')

            if primary_only and i > 0:
                continue

            if link_id is None:
                is_likely_required = (
                    i == 0 or
                    'optional' not in inp_name.lower() and
                    node_type not in optional_heavy_types
                )

                orphans.append({
                    'node_id': node_id,
                    'node_type': node_type,
                    'input_slot': i,
                    'input_name': inp_name,
                    'input_type': inp_type,
                    'likely_required': is_likely_required,
                    'is_primary': i == 0
                })
            elif link_id not in links_dict:
                orphans.append({
                    'node_id': node_id,
                    'node_type': node_type,
                    'input_slot': i,
                    'input_name': inp_name,
                    'input_type': inp_type,
                    'likely_required': True,
                    'is_primary': i == 0,
                    'broken_link': link_id
                })

    return orphans


def find_dangling(wf: Dict) -> List[Dict]:
    """Find nodes with unconnected outputs.

    Returns list of:
        {
            'node_id': int,
            'node_type': str,
            'output_slot': int,
            'output_name': str,
            'output_type': str
        }
    """
    terminal_types = {
        'VHS_VideoCombine', 'SaveImage', 'PreviewImage', 'SetNode',
        'Display Any (rgthree)', 'Display Int (rgthree)', 'DisplayAny',
        'Note', 'Label (rgthree)', 'Reroute'
    }

    dangling = []
    for node in wf['nodes']:
        node_id = node['id']
        node_type = node['type']

        if node_type in terminal_types:
            continue

        outputs = node.get('outputs', [])
        if not outputs:
            continue

        for i, out in enumerate(outputs):
            links = out.get('links') or []
            if not links:
                dangling.append({
                    'node_id': node_id,
                    'node_type': node_type,
                    'output_slot': i,
                    'output_name': out.get('name', f'output_{i}'),
                    'output_type': out.get('type', '?')
                })

    return dangling


def format_values(vals) -> str:
    """Format widget values for display."""
    if isinstance(vals, list):
        if len(vals) <= 6:
            return str(vals)
        return f"[{vals[0]}, {vals[1]}, ... ({len(vals)} items)]"
    elif isinstance(vals, dict):
        keys = list(vals.keys())
        if len(keys) <= 4:
            return str(vals)
        return f"{{...}} ({len(keys)} keys)"
    return str(vals)
