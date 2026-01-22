"""Workflow visualization - layout and SVG generation."""

import re
from collections import deque
from typing import Dict, List, Tuple, Any, Optional
from . import workflow as wf_module


def parse_groups_file(path: str, wf: Dict) -> Dict:
    """Parse a groups config file for layout.

    Supports two formats:
    1. Grid format (section-based):
        ---  # section separator
        group_name : node_id node_id auto:TypePattern ...

    2. Legacy format (explicit positions):
        group_name @ x,y : node_id node_id auto:TypePattern ...
    """
    sections = []
    current_section = []
    node_types = {n['id']: n.get('type', '') for n in wf['nodes']}
    is_grid_format = False

    def parse_items(items_str):
        node_ids = []
        for item in items_str.split():
            if item.startswith('auto:'):
                pattern = item[5:].lower()
                for nid, ntype in node_types.items():
                    if pattern in ntype.lower():
                        node_ids.append(nid)
            else:
                try:
                    node_ids.append(int(item))
                except ValueError:
                    pass
        return node_ids

    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#'):
                continue

            if line == '---':
                is_grid_format = True
                if current_section:
                    sections.append(current_section)
                current_section = []
                continue

            # Grid format: group_name : items
            match = re.match(r'(\w+)\s*:\s*(.+)', line)
            if match and '@' not in line:
                name, items_str = match.groups()
                node_ids = parse_items(items_str)
                current_section.append((name, node_ids))
                continue

            # Legacy format: group_name @ x,y : items
            match = re.match(r'(\w+)\s*@\s*(\d+)\s*,\s*(\d+)\s*:\s*(.+)', line)
            if match:
                name, x, y, items_str = match.groups()
                node_ids = parse_items(items_str)
                current_section.append((name, node_ids, int(x), int(y)))

    if current_section:
        sections.append(current_section)

    return {'sections': sections, 'is_grid': is_grid_format}


def layout_group_nodes(wf: Dict, nodes_dict: Dict, group_nodes: List[int],
                       start_x: float, start_y: float,
                       max_width: float = 600,
                       spacing_x: float = 50, spacing_y: float = 80) -> None:
    """Layout nodes in a group in rows."""
    x, y = start_x, start_y
    row_height = 0
    row_start_x = start_x

    for node_id in group_nodes:
        node = nodes_dict.get(node_id)
        if not node:
            continue

        size = node.get('size', [200, 100])
        if isinstance(size, dict):
            w, h = float(size.get('0', 200)), float(size.get('1', 100))
        elif isinstance(size, list) and len(size) >= 2:
            w, h = float(size[0]), float(size[1])
        else:
            w, h = 200, 100

        if x + w - row_start_x > max_width and x != row_start_x:
            x = row_start_x
            y += row_height + spacing_y
            row_height = 0

        node['pos'] = [x, y]
        row_height = max(row_height, h)
        x += w + spacing_x


def auto_layout(wf: Dict) -> Dict:
    """Automatically layout nodes based on data flow.

    Returns dict with layout statistics.
    """
    nodes_dict = wf_module.get_nodes_dict(wf)
    forward, reverse = wf_module.build_adjacency(wf)

    # Find entry points
    all_dst = set()
    for dsts in forward.values():
        for dst, _ in dsts:
            all_dst.add(dst)
    entry_points = [n['id'] for n in wf['nodes'] if n['id'] not in all_dst]

    # BFS to assign depths
    depth = {}
    queue = deque()
    for entry in entry_points:
        depth[entry] = 0
        queue.append(entry)

    while queue:
        nid = queue.popleft()
        for dst, _ in forward.get(nid, []):
            if dst not in depth:
                depth[dst] = depth[nid] + 1
                queue.append(dst)

    # Assign depths to unvisited nodes
    for node in wf['nodes']:
        if node['id'] not in depth:
            depth[node['id']] = 0

    # Group by depth
    by_depth = {}
    for nid, d in depth.items():
        if d not in by_depth:
            by_depth[d] = []
        by_depth[d].append(nid)

    # Position nodes
    col_width = 350
    row_height = 120
    start_x = 50
    start_y = 50

    for d, node_ids in by_depth.items():
        x = start_x + d * col_width
        for i, nid in enumerate(sorted(node_ids)):
            y = start_y + i * row_height
            node = nodes_dict[nid]
            if isinstance(node.get('pos'), dict):
                node['pos'] = {'0': x, '1': y}
            else:
                node['pos'] = [x, y]

    max_depth = max(depth.values()) if depth else 0
    return {
        'max_depth': max_depth,
        'node_count': len(wf['nodes']),
    }


def generate_svg(wf: Dict, groups_file: str = None,
                 scale: float = None, width: int = None,
                 no_links: bool = False, local_links: bool = False) -> str:
    """Generate SVG visualization of workflow.

    Returns SVG string.
    """
    nodes_dict = wf_module.get_nodes_dict(wf)

    # Parse groups if provided
    parsed = None
    if groups_file:
        parsed = parse_groups_file(groups_file, wf)

    # Get node positions
    nodes = []
    for n in wf['nodes']:
        pos = n.get('pos', [0, 0])
        if isinstance(pos, dict):
            x, y = float(pos.get('0', 0)), float(pos.get('1', 0))
        else:
            x, y = float(pos[0]), float(pos[1])

        size = n.get('size', [200, 100])
        if isinstance(size, dict):
            w, h = float(size.get('0', 200)), float(size.get('1', 100))
        elif isinstance(size, list) and len(size) >= 2:
            w, h = float(size[0]), float(size[1])
        else:
            w, h = 200, 100

        nodes.append({
            'id': n['id'],
            'type': n['type'],
            'x': x, 'y': y, 'w': w, 'h': h,
        })

    # Get links
    links = []
    node_pos = {n['id']: (n['x'], n['y'], n['w'], n['h']) for n in nodes}
    for link in wf['links']:
        link_id, src_id, src_slot, dst_id, dst_slot, dtype = link
        if src_id in node_pos and dst_id in node_pos:
            links.append((src_id, dst_id))

    # Find bounds
    if not nodes:
        return '<svg></svg>'

    min_x = min(n['x'] for n in nodes)
    max_x = max(n['x'] + n['w'] for n in nodes)
    min_y = min(n['y'] for n in nodes)
    max_y = max(n['y'] + n['h'] for n in nodes)

    content_w = max_x - min_x + 100
    content_h = max_y - min_y + 100

    # Determine scale
    if width:
        actual_scale = width / content_w
    elif scale:
        actual_scale = scale
    else:
        actual_scale = min(1.0, 1920 / content_w)

    offset_x = -min_x + 50
    offset_y = -min_y + 50

    # Color mapping
    type_colors = {
        'VHS_LoadVideo': '#4CAF50', 'LoadImage': '#4CAF50',
        'VHS_VideoCombine': '#F44336', 'SaveImage': '#F44336',
        'VHS_SelectImages': '#2196F3',
        'WanVideoVACEEncode': '#9C27B0', 'WanVideoVACEStartToEndFrame': '#9C27B0',
        'WanVideoEncode': '#FF9800',
        'WanVideoSampler': '#00BCD4',
        'WanVideoDecode': '#FFEB3B',
        'ImageBatch': '#E91E63',
        'GetNode': '#607D8B', 'SetNode': '#607D8B',
    }

    def get_color(t):
        return type_colors.get(t, '#999999')

    svg_w = (max_x - min_x + 100) * actual_scale
    svg_h = (max_y - min_y + 100) * actual_scale

    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="{svg_w:.0f}" height="{svg_h:.0f}" style="background: #1a1a1a;">
<defs>
  <marker id="arrow" markerWidth="10" markerHeight="10" refX="9" refY="3" orient="auto">
    <path d="M0,0 L0,6 L9,3 z" fill="#666"/>
  </marker>
</defs>
'''

    # Draw links
    if not no_links:
        for src_id, dst_id in links:
            sx, sy, sw, sh = node_pos[src_id]
            dx, dy, dw, dh = node_pos[dst_id]

            if local_links:
                dist = abs(dy - sy)
                if dist > 300:
                    continue

            x1 = (sx + sw + offset_x) * actual_scale
            y1 = (sy + sh/2 + offset_y) * actual_scale
            x2 = (dx + offset_x) * actual_scale
            y2 = (dy + dh/2 + offset_y) * actual_scale
            svg += f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" stroke="#444" stroke-width="1" marker-end="url(#arrow)"/>\n'

    # Draw nodes
    for n in nodes:
        x = (n['x'] + offset_x) * actual_scale
        y = (n['y'] + offset_y) * actual_scale
        w = n['w'] * actual_scale
        h = n['h'] * actual_scale
        color = get_color(n['type'])

        svg += f'<rect x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{h:.1f}" fill="{color}" rx="5" opacity="0.8"/>\n'

        # Label
        label = f"[{n['id']}] {n['type'][:20]}"
        font_size = max(8, min(12, w / 15))
        svg += f'<text x="{x + 5:.1f}" y="{y + font_size + 3:.1f}" fill="white" font-size="{font_size}">{label}</text>\n'

    svg += '</svg>'
    return svg
