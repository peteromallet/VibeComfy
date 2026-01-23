#!/usr/bin/env python3
"""
ComfyUI Workflow CLI Tool - see CLAUDE.md for full command reference.
"""

import argparse
import sys
import os
import json
import urllib.request
import urllib.error
from pathlib import Path

# Load .env if it exists
_env_path = Path(__file__).parent / '.env'
if _env_path.exists():
    for line in _env_path.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith('#') and '=' in line:
            key, val = line.split('=', 1)
            os.environ.setdefault(key.strip(), val.strip())

from cli_tools import workflow as wf_mod
from cli_tools import analysis
from cli_tools import editing
from cli_tools import batch as batch_mod
from cli_tools import visualization as viz
from cli_tools import fetch as fetch_mod
from cli_tools.descriptions import get_node_description
from cli_tools.analysis import get_node_role


def cmd_info(args):
    wf = wf_mod.load(args.workflow)
    info = analysis.get_workflow_info(wf)
    print(f"Workflow: {args.workflow}")
    print(f"  Nodes: {info['node_count']}")
    print(f"  Links: {info['link_count']}")
    print(f"  Last node ID: {info['last_node_id'] or 'N/A'}")
    print(f"  Last link ID: {info['last_link_id'] or 'N/A'}")
    print(f"\nNode types ({len(info['type_counts'])} unique):")
    for t, count in sorted(info['type_counts'].items(), key=lambda x: -x[1])[:20]:
        print(f"  {t}: {count}")
    if len(info['type_counts']) > 20:
        print(f"  ... and {len(info['type_counts']) - 20} more")


def cmd_analyze(args):
    wf = wf_mod.load(args.workflow)
    nodes_dict = wf_mod.get_nodes_dict(wf)
    result = analysis.analyze_workflow(wf)

    primary_inputs = result['primary_inputs']
    model_loaders = result['model_loaders']
    primary_outputs = result['primary_outputs']

    print("=" * 60)
    print(f"WORKFLOW ANALYSIS: {result['workflow_type']} Pipeline")
    print("=" * 60)

    if primary_inputs:
        print(f"\nPRIMARY INPUTS ({len(primary_inputs)})")
        for nid in primary_inputs:
            print(f"   {wf_mod.format_node(nid, nodes_dict)}")

    if primary_outputs:
        print(f"\nPRIMARY OUTPUTS ({len(primary_outputs)})")
        for nid in primary_outputs:
            print(f"   {wf_mod.format_node(nid, nodes_dict)}")

    if result['pipelines']:
        main = max(result['pipelines'], key=lambda p: len(p['path']))
        print(f"\nMAIN PIPELINE ({len(main['path'])} nodes)")
        for nid, _ in main['path'][:10]:
            print(f"   {wf_mod.format_node(nid, nodes_dict)}")
        if len(main['path']) > 10:
            print(f"   ... ({len(main['path']) - 10} more)")

    if model_loaders:
        print(f"\nMODEL LOADERS ({len(model_loaders)})")
        for nid in model_loaders[:5]:
            print(f"   {wf_mod.format_node(nid, nodes_dict)}")


def cmd_query(args):
    wf = wf_mod.load(args.workflow)

    if not args.type:
        print("Error: -t/--type required (use 'trace' to inspect a specific node)")
        return

    results = [n for n in wf['nodes'] if args.type.lower() in n['type'].lower()]

    if not results:
        print("No nodes found")
        return

    for n in results:
        print(f"[{n['id']}] {n['type']}" + (f" \"{n['title']}\"" if n.get('title') else ""))


def cmd_trace(args):
    wf = wf_mod.load(args.workflow)
    nodes_dict = wf_mod.get_nodes_dict(wf)
    links_dict = wf_mod.get_links_dict(wf)

    node = nodes_dict.get(args.node_id)
    if not node:
        print(f"Node {args.node_id} not found")
        return

    print(f"[Node {args.node_id}] {node['type']}")
    print("\n  INPUTS (what feeds into this node):")
    for i, inp in enumerate(node.get('inputs', [])):
        link_id = inp.get('link')
        if link_id and link_id in links_dict:
            link = links_dict[link_id]
            src_node = nodes_dict.get(link[1], {})
            print(f"    [{i}] {inp.get('name', '?')} <- [Node {link[1]}] {src_node.get('type', '?')} (slot {link[2]})")
        else:
            print(f"    [{i}] {inp.get('name', '?')} <- (unconnected)")

    print("\n  OUTPUTS (what this node feeds into):")
    for i, out in enumerate(node.get('outputs', [])):
        for link_id in (out.get('links') or []):
            if link_id in links_dict:
                link = links_dict[link_id]
                dst_node = nodes_dict.get(link[3], {})
                print(f"    [{i}] {out.get('name', '?')} -> [Node {link[3]}] {dst_node.get('type', '?')} (slot {link[4]})")
        if not out.get('links'):
            print(f"    [{i}] {out.get('name', '?')} -> (unconnected)")


def cmd_graph(args):
    wf = wf_mod.load(args.workflow)
    nodes_dict = wf_mod.get_nodes_dict(wf)
    filter_type = args.filter.lower() if args.filter else None

    print("Workflow Graph:\n" + "=" * 60)
    for link in wf['links']:
        link_id, src_id, src_slot, dst_id, dst_slot, dtype = link
        src_type = nodes_dict.get(src_id, {}).get('type', '?')
        dst_type = nodes_dict.get(dst_id, {}).get('type', '?')
        if filter_type and filter_type not in src_type.lower() and filter_type not in dst_type.lower():
            continue
        print(f"[{src_id}] {src_type}:{src_slot} --({dtype})--> [{dst_id}] {dst_type}:{dst_slot}")


def cmd_path(args):
    wf = wf_mod.load(args.workflow)
    nodes_dict = wf_mod.get_nodes_dict(wf)
    path = analysis.find_path(wf, args.from_node, args.to_node)
    if path:
        print(f"Path from {args.from_node} to {args.to_node}:")
        for i, nid in enumerate(path):
            print(f"{'  ' * i}[{nid}] {nodes_dict.get(nid, {}).get('type', '?')}")
    else:
        print(f"No path found from {args.from_node} to {args.to_node}")


def cmd_subgraph(args):
    wf = wf_mod.load(args.workflow)
    nodes_dict = wf_mod.get_nodes_dict(wf)
    result = analysis.find_subgraph(wf, args.start, args.end)

    if result.get('error'):
        print(result['error'])
        return

    print(f"Subgraph: [{args.start}] -> [{args.end}]")
    print(f"Nodes: {len(result['nodes'])}\n" + "=" * 60)

    forward, _ = wf_mod.build_adjacency(wf)
    by_role = {}
    for nid in result['sorted_nodes']:
        role = get_node_role(nid, forward, {}, nodes_dict, result['nodes'])
        by_role.setdefault(role, []).append(nid)

    for role, nids in sorted(by_role.items()):
        print(f"\n  {role}:")
        for nid in nids:
            node = nodes_dict.get(nid, {})
            desc = get_node_description(node.get('type', ''))
            print(f"    [{nid}] {node.get('type', '?')} - {desc}")


def cmd_upstream(args):
    wf = wf_mod.load(args.workflow)
    nodes_dict = wf_mod.get_nodes_dict(wf)
    result = analysis.find_upstream(wf, args.node_id, max_depth=args.depth or 999, input_filter=args.input)

    if result.get('error'):
        print(result['error'])
        return

    print(f"\nUpstream of [{args.node_id}] {nodes_dict.get(args.node_id, {}).get('type', '?')}:")
    print("=" * 60)
    for edge in result['edges']:
        src_id, src_type, src_out, dst_id, dst_type, dst_in, dtype = edge
        marker = " <<<" if dst_id == args.node_id else ""
        print(f"[{src_id}] {src_type}.{src_out} --({dtype})--> [{dst_id}] {dst_type}.{dst_in}{marker}")
    print(f"\nTotal: {len(result['nodes'])} nodes, {len(result['links'])} links")


def cmd_downstream(args):
    wf = wf_mod.load(args.workflow)
    nodes_dict = wf_mod.get_nodes_dict(wf)
    result = analysis.find_downstream(wf, args.node_id, max_depth=args.depth or 999, output_filter=args.output)

    if result.get('error'):
        print(result['error'])
        return

    print(f"\nDownstream of [{args.node_id}] {nodes_dict.get(args.node_id, {}).get('type', '?')}:")
    print("=" * 60)
    for edge in result['edges']:
        src_id, src_type, src_out, dst_id, dst_type, dst_in, dtype = edge
        marker = " <<<" if src_id == args.node_id else ""
        print(f"[{src_id}] {src_type}.{src_out}{marker} --({dtype})--> [{dst_id}] {dst_type}.{dst_in}")
    print(f"\nTotal: {len(result['nodes'])} nodes, {len(result['links'])} links")


def cmd_values(args):
    wf = wf_mod.load(args.workflow)
    node = wf_mod.get_nodes_dict(wf).get(args.node_id)
    if not node:
        print(f"Node {args.node_id} not found")
        return

    print(f"[{node['id']}] {node['type']}")
    if node.get('title'):
        print(f"Title: {node['title']}")

    vals = node.get('widgets_values')
    if not vals:
        print("\nNo widget values")
        return

    print(f"\nWidget values ({type(vals).__name__}):")
    if isinstance(vals, list):
        for i, v in enumerate(vals):
            v_repr = repr(v)[:80] + "..." if len(repr(v)) > 80 else repr(v)
            print(f"  [{i}] {v_repr}")
    elif isinstance(vals, dict):
        for k, v in vals.items():
            v_repr = repr(v)[:80] + "..." if len(repr(v)) > 80 else repr(v)
            print(f"  {k}: {v_repr}")


def cmd_unconnected(args):
    wf = wf_mod.load(args.workflow)

    # Default to both if neither specified
    show_inputs = args.inputs or (not args.inputs and not args.outputs)
    show_outputs = args.outputs or (not args.inputs and not args.outputs)

    if show_inputs:
        orphans = analysis.find_orphans(wf, primary_only=args.primary)
        if orphans:
            by_node = {}
            for o in orphans:
                by_node.setdefault(o['node_id'], {'type': o['node_type'], 'inputs': []})['inputs'].append(o)
            print(f"Unconnected inputs ({len(orphans)} across {len(by_node)} nodes):\n")
            for nid, data in sorted(by_node.items()):
                print(f"[{nid}] {data['type']}")
                for inp in data['inputs']:
                    marker = "!" if inp.get('is_primary') or inp.get('broken_link') else "?"
                    print(f"  {marker} [{inp['input_slot']}] {inp['input_name']}: {inp['input_type']}")
                print()
        elif show_inputs and not show_outputs:
            print("No unconnected inputs found.")

    if show_outputs:
        dangling = analysis.find_dangling(wf)
        if dangling:
            by_node = {}
            for d in dangling:
                by_node.setdefault(d['node_id'], {'type': d['node_type'], 'outputs': []})['outputs'].append(d)
            print(f"Unconnected outputs ({len(dangling)} across {len(by_node)} nodes):\n")
            for nid, data in sorted(by_node.items()):
                print(f"[{nid}] {data['type']}")
                for out in data['outputs']:
                    print(f"  -> [{out['output_slot']}] {out['output_name']}: {out['output_type']}")
                print()
        elif show_outputs and not show_inputs:
            print("No unconnected outputs found.")


def cmd_delete(args):
    wf = wf_mod.load(args.workflow)
    nodes_dict = wf_mod.get_nodes_dict(wf)
    result = editing.delete_nodes(wf, args.node_ids, dry_run=args.dry_run)

    for w in result['warnings']:
        print(f"Warning: {w}")

    if args.dry_run:
        print(f"DRY RUN - Would delete {len(result['deleted_nodes'])} nodes:\n")
        for nid in sorted(result['deleted_nodes']):
            print(f"  [{nid}] {nodes_dict.get(nid, {}).get('type', '?')}")
        print(f"\nWould remove {len(result['removed_links'])} links")
        if result['orphaned_inputs']:
            print(f"\nWARNING: {len(result['orphaned_inputs'])} inputs will become orphaned")
        print("\n(No changes made)")
        return

    if not args.output:
        print("Error: -o/--output is required")
        return

    output_path = wf_mod.get_versioned_output(args.output)
    wf_mod.log_change(args.workflow, output_path, 'delete', f"Deleted {len(result['deleted_nodes'])} nodes")
    wf_mod.save(wf, output_path)
    print(f"Deleted {len(result['deleted_nodes'])} nodes, {len(result['removed_links'])} links -> {output_path}")


def cmd_copy(args):
    wf = wf_mod.load(args.workflow)
    set_values = {}
    if args.set:
        for s in args.set:
            if '=' in s:
                k, v = s.split('=', 1)
                set_values[k] = editing.parse_set_value(v)

    result = editing.copy_node(wf, args.node_id, title=args.title, set_values=set_values or None)
    if result.get('error'):
        print(f"Error: {result['error']}")
        return

    if not args.output:
        print("Error: -o/--output is required")
        return

    output_path = wf_mod.get_versioned_output(args.output)
    wf_mod.log_change(args.workflow, output_path, 'copy', f"Copied {args.node_id} -> {result['new_id']}")
    wf_mod.save(wf, output_path)
    print(f"Created node {result['new_id']} from {args.node_id} ({result['template_type']}) -> {output_path}")
    for warning in result.get('warnings', []):
        print(f"  Warning: {warning}")


def cmd_wire(args):
    wf = wf_mod.load(args.workflow)

    if args.disconnect:
        result = editing.disconnect_node(wf, args.disconnect)
        if result.get('error'):
            print(f"Error: {result['error']}")
            return
        print(f"Disconnected {len(result['removed_links'])} links from node {args.disconnect}")
    else:
        result = editing.wire_nodes(wf, args.src_id, args.src_slot, args.dst_id, args.dst_slot)
        if result.get('error'):
            print(f"Error: {result['error']}")
            return
        print(f"Created link {result['link_id']}: [{args.src_id}]:{result['src_slot']} --({result['dtype']})--> [{args.dst_id}]:{result['dst_slot']}")

    if not args.output:
        print("Error: -o/--output is required")
        return

    output_path = wf_mod.get_versioned_output(args.output)
    wf_mod.log_change(args.workflow, output_path, 'wire', 'Connection modified')
    wf_mod.save(wf, output_path)
    print(f"Saved to {output_path}")


def cmd_set(args):
    wf = wf_mod.load(args.workflow)
    values = {}
    for s in args.values:
        if '=' in s:
            k, v = s.split('=', 1)
            values[k] = editing.parse_set_value(v)

    result = editing.set_widget_values(wf, args.node_id, values)
    if result.get('error'):
        print(f"Error: {result['error']}")
        return

    if not args.output:
        print("Error: -o/--output is required")
        return

    output_path = wf_mod.get_versioned_output(args.output)
    wf_mod.log_change(args.workflow, output_path, 'set', f"Set {len(result['set_values'])} values on {args.node_id}")
    wf_mod.save(wf, output_path)
    print(f"Set {len(result['set_values'])} values on node {args.node_id} -> {output_path}")
    for warning in result.get('warnings', []):
        print(f"  Warning: {warning}")


def cmd_inline(args):
    wf = wf_mod.load(args.workflow)
    result = editing.inline_variables(wf, dry_run=args.dry_run)

    if not result['pairs_found']:
        print("No SetNode/GetNode pairs found")
        return

    print(f"Found {len(result['pairs_found'])} pairs")
    if args.dry_run:
        print(f"Would delete {len(result['nodes_to_delete'])} nodes, create {len(result['links_to_create'])} links")
        print("(No changes made)")
        return

    if not args.output:
        print("Error: -o/--output is required")
        return

    output_path = wf_mod.get_versioned_output(args.output)
    wf_mod.log_change(args.workflow, output_path, 'inline', f"Inlined {len(result['pairs_found'])} pairs")
    wf_mod.save(wf, output_path)
    print(f"Inlined {len(result['pairs_found'])} pairs -> {output_path}")


def cmd_batch(args):
    wf = wf_mod.load(args.workflow)
    operations = batch_mod.parse_batch_script(args.script)

    if not operations:
        print("No operations found in script")
        return

    dry_run = getattr(args, 'dry_run', False)
    print(f"{'DRY RUN - Simulating' if dry_run else 'Executing'} {len(operations)} operations...")

    result = batch_mod.execute_batch(wf, operations, dry_run=dry_run)

    for detail in result['details']:
        print(f"  {detail}")
    for error in result['errors']:
        print(f"ERROR: {error}")

    if dry_run:
        print("\n(No changes made)")
        return

    if not args.output:
        print("Error: -o/--output is required")
        return

    output_path = wf_mod.get_versioned_output(args.output)
    wf_mod.log_change(args.workflow, output_path, 'batch', '\n'.join(result['details']))
    wf_mod.save(wf, output_path)
    print(f"\nSaved to {output_path}")


def cmd_layout(args):
    wf = wf_mod.load(args.workflow)
    nodes_dict = wf_mod.get_nodes_dict(wf)

    if args.groups:
        parsed = viz.parse_groups_file(args.groups, wf)
        current_y = 50
        for section in parsed['sections']:
            for item in section:
                name, node_ids = item[0], item[1]
                viz.layout_group_nodes(wf, nodes_dict, node_ids, 50, current_y)
                current_y += 300
    else:
        result = viz.auto_layout(wf)
        print(f"Auto-layout: {result['max_depth'] + 1} columns")

    if not args.output:
        print("Error: -o/--output is required")
        return

    output_path = wf_mod.get_versioned_output(args.output)
    wf_mod.save(wf, output_path)
    print(f"Laid out {len(wf['nodes'])} nodes -> {output_path}")


def cmd_visualize(args):
    wf = wf_mod.load(args.workflow)
    svg = viz.generate_svg(wf, groups_file=args.groups, scale=args.scale, width=args.width,
                           no_links=args.no_links, local_links=args.local_links)

    if not args.output:
        print("Error: -o/--output is required")
        return

    with open(args.output, 'w') as f:
        f.write(svg)
    print(f"Generated SVG: {args.output}")


def cmd_fetch(args):
    wf = wf_mod.load(args.workflow)
    node = wf_mod.get_nodes_dict(wf).get(args.node_id)
    if not node:
        print(f"Node {args.node_id} not found")
        return

    info = fetch_mod.get_node_repo_info(node)
    if not info['repo']:
        print(f"No repository info for [{args.node_id}] {node['type']}")
        return

    print(f"Fetching {info['node_name']} from {info['repo']}...")
    source, url = fetch_mod.fetch_node_source(info['repo'], info['commit'], info['node_name'])

    if not source:
        print(f"Could not fetch source")
        return

    print(f"Source: {url}\n")

    if getattr(args, 'search', None):
        matches = fetch_mod.search_source(source, args.search)
        if not matches:
            print(f"No matches for '{args.search}'")
            return
        for m in matches[:10]:
            print(f"Line {m['line_num']}: {m['line']}")
        return

    if getattr(args, 'source', None):
        code = fetch_mod.extract_class_code(source, info['node_name'])
        if code:
            if not args.full and len(code) > 3000:
                print(code[:3000] + f"\n... ({len(code) - 3000} chars truncated)")
            else:
                print(code)
        return

    inputs, widgets = fetch_mod.parse_input_types(source, info['node_name'])
    if inputs:
        print("INPUTS (connections):")
        for name, dtype in inputs:
            print(f"  {name}: {dtype}")
    if widgets:
        print("\nWIDGETS (parameters):")
        for name, dtype in widgets:
            print(f"  {name}: {dtype}")


def cmd_verify(args):
    wf = wf_mod.load(args.workflow)
    nodes_dict = wf_mod.get_nodes_dict(wf)
    links_dict = wf_mod.get_links_dict(wf)
    issues = []

    for node in wf['nodes']:
        for inp in node.get('inputs', []):
            if inp.get('link') and inp['link'] not in links_dict:
                issues.append(f"Node {node['id']}: input refs missing link {inp['link']}")
        for out in node.get('outputs', []):
            for link_id in (out.get('links') or []):
                if link_id not in links_dict:
                    issues.append(f"Node {node['id']}: output refs missing link {link_id}")

    for link_id, link in links_dict.items():
        if link[1] not in nodes_dict:
            issues.append(f"Link {link_id}: source node {link[1]} not found")
        if link[3] not in nodes_dict:
            issues.append(f"Link {link_id}: dest node {link[3]} not found")

    if issues:
        print(f"Found {len(issues)} issues:\n")
        for i in issues:
            print(f"  - {i}")
    else:
        print("Workflow integrity OK")


def cmd_diff(args):
    wf1, wf2 = wf_mod.load(args.workflow1), wf_mod.load(args.workflow2)
    nodes1 = {n['id']: n for n in wf1['nodes']}
    nodes2 = {n['id']: n for n in wf2['nodes']}

    added = set(nodes2) - set(nodes1)
    removed = set(nodes1) - set(nodes2)

    print(f"Comparing: {args.workflow1} -> {args.workflow2}\n")
    if added:
        print(f"ADDED ({len(added)}):")
        for nid in sorted(added):
            print(f"  + [{nid}] {nodes2[nid]['type']}")
    if removed:
        print(f"REMOVED ({len(removed)}):")
        for nid in sorted(removed):
            print(f"  - [{nid}] {nodes1[nid]['type']}")

    modified = [nid for nid in set(nodes1) & set(nodes2)
                if nodes1[nid].get('widgets_values') != nodes2[nid].get('widgets_values')]
    if modified:
        print(f"MODIFIED ({len(modified)}):")
        for nid in sorted(modified):
            print(f"  ~ [{nid}] {nodes1[nid]['type']}")


def cmd_create(args):
    wf = wf_mod.load(args.workflow)
    inputs = [(s.split(':')[0], s.split(':')[1]) for s in (args.input or []) if ':' in s]
    outputs = [(s.split(':')[0], s.split(':')[1]) for s in (args.output_slot or []) if ':' in s]

    result = editing.create_node(wf, args.node_type, title=args.title,
                                 inputs=inputs or None, outputs=outputs or None)

    if not args.output_file:
        print("Error: -o/--output is required")
        return

    output_path = wf_mod.get_versioned_output(args.output_file)
    wf_mod.log_change(args.workflow, output_path, 'create', f"Created {args.node_type} -> {result['new_id']}")
    wf_mod.save(wf, output_path)
    print(f"Created node {result['new_id']} of type {args.node_type} -> {output_path}")


# ============================================================================
# ComfyUI Integration
# ============================================================================

def fetch_object_info():
    """Fetch node schemas from ComfyUI's /object_info endpoint."""
    comfy_url = os.environ.get('COMFY_URL', 'http://127.0.0.1:8188')
    url = f"{comfy_url.rstrip('/')}/object_info"
    try:
        with urllib.request.urlopen(url, timeout=5) as resp:
            return json.loads(resp.read().decode('utf-8'))
    except:
        return None


def convert_to_api_format(workflow, object_info=None):
    """Convert UI workflow format to API format.

    Args:
        workflow: UI format workflow (with 'nodes' array)
        object_info: Optional node schema from /object_info. If not provided,
                     will attempt to fetch from ComfyUI.
    """
    # If already API format (no 'nodes' array), return as-is
    if 'nodes' not in workflow:
        return workflow

    # Try to get object_info for proper widget name mapping
    if object_info is None:
        object_info = fetch_object_info()

    # Build link map: link_id -> (src_node, src_slot)
    link_map = {}
    for link in workflow.get('links', []):
        link_id, src_node, src_slot, dst_node, dst_slot, dtype = link
        link_map[link_id] = (str(src_node), src_slot)

    api_workflow = {}
    for node in workflow['nodes']:
        node_id = str(node['id'])
        node_type = node['type']
        inputs = {}

        # Map connected inputs
        for inp in node.get('inputs', []):
            link_id = inp.get('link')
            if link_id and link_id in link_map:
                src_node, src_slot = link_map[link_id]
                inputs[inp['name']] = [src_node, src_slot]

        # Map widget values to inputs
        widget_values = node.get('widgets_values', [])
        if isinstance(widget_values, list) and widget_values:
            # Get widget names from object_info if available
            widget_names = []
            if object_info and node_type in object_info:
                node_info = object_info[node_type]
                required = node_info.get('input', {}).get('required', {})
                optional = node_info.get('input', {}).get('optional', {})
                # Widget inputs are those that aren't connection types
                for name, spec in {**required, **optional}.items():
                    if isinstance(spec, list) and len(spec) > 0:
                        dtype = spec[0]
                        # Skip connection types
                        if dtype not in ['MODEL', 'CLIP', 'VAE', 'CONDITIONING',
                                        'LATENT', 'IMAGE', 'MASK', 'CONTROL_NET', '*']:
                            widget_names.append(name)

            # Map values to names (or fall back to position-based)
            for i, val in enumerate(widget_values):
                if val is not None:
                    if i < len(widget_names):
                        name = widget_names[i]
                        if name not in inputs:  # Don't override connections
                            inputs[name] = val
                    # Skip values we can't map - they may be UI-only state
        elif isinstance(widget_values, dict):
            for k, v in widget_values.items():
                if k not in inputs:
                    inputs[k] = v

        api_workflow[node_id] = {
            'class_type': node['type'],
            'inputs': inputs
        }

    return api_workflow


def cmd_submit(args):
    """Submit a workflow to ComfyUI for execution."""
    # Load the workflow
    with open(args.workflow, 'r') as f:
        workflow = json.load(f)

    # Convert to API format if needed
    if 'nodes' in workflow:
        object_info = fetch_object_info()
        workflow = convert_to_api_format(workflow, object_info)

    # Wrap in prompt format
    prompt = {'prompt': workflow}

    comfy_url = os.environ.get('COMFY_URL', 'http://127.0.0.1:8188')
    url = f"{comfy_url.rstrip('/')}/prompt"

    data = json.dumps(prompt).encode('utf-8')
    req = urllib.request.Request(url, data=data, headers={'Content-Type': 'application/json'})

    try:
        with urllib.request.urlopen(req) as resp:
            result = json.loads(resp.read().decode('utf-8'))
            print(f"Queued: prompt_id={result.get('prompt_id')}, number={result.get('number')}")
    except urllib.error.URLError as e:
        print(f"Error connecting to ComfyUI at {comfy_url}: {e}")
        print("Is ComfyUI running?")
    except urllib.error.HTTPError as e:
        error_body = e.read().decode('utf-8')
        print(f"Error from ComfyUI: {e.code}")
        try:
            err = json.loads(error_body)
            if 'node_errors' in err:
                for node_id, errors in err['node_errors'].items():
                    print(f"  Node {node_id}: {errors}")
        except:
            print(error_body)


def cmd_logs(args):
    """Read ComfyUI logs."""
    comfy_path = os.environ.get('COMFY_PATH')
    if not comfy_path:
        print("Error: COMFY_PATH not set in .env")
        print("Add COMFY_PATH=/path/to/ComfyUI to your .env file")
        return

    log_path = Path(comfy_path) / 'comfyui.log'
    if not log_path.exists():
        print(f"No log file found at {log_path}")
        print(f"\nTo create logs, launch ComfyUI with:")
        print(f"  cd {comfy_path}")
        print(f"  python main.py 2>&1 | tee comfyui.log")
        return

    # Read last N lines or tail
    lines = args.lines or 50
    with open(log_path, 'r') as f:
        all_lines = f.readlines()
        for line in all_lines[-lines:]:
            print(line, end='')


# ============================================================================
# Argument parsing
# ============================================================================

def main():
    parser = argparse.ArgumentParser(description='ComfyUI Workflow CLI Tool')
    subs = parser.add_subparsers(dest='command')

    # Analysis commands
    p = subs.add_parser('info'); p.add_argument('workflow')
    p = subs.add_parser('analyze'); p.add_argument('workflow')

    p = subs.add_parser('query'); p.add_argument('workflow')
    p.add_argument('--type', '-t')

    p = subs.add_parser('trace'); p.add_argument('workflow'); p.add_argument('node_id', type=int)
    p = subs.add_parser('graph'); p.add_argument('workflow'); p.add_argument('--filter', '-f')

    p = subs.add_parser('path'); p.add_argument('workflow')
    p.add_argument('from_node', type=int); p.add_argument('to_node', type=int)

    p = subs.add_parser('subgraph'); p.add_argument('workflow')
    p.add_argument('start', type=int); p.add_argument('end', type=int)

    p = subs.add_parser('upstream'); p.add_argument('workflow'); p.add_argument('node_id', type=int)
    p.add_argument('--input', '-i'); p.add_argument('--depth', '-d', type=int); p.add_argument('--verbose', '-v', action='store_true')

    p = subs.add_parser('downstream'); p.add_argument('workflow'); p.add_argument('node_id', type=int)
    p.add_argument('--output', '-O', dest='output'); p.add_argument('--depth', '-d', type=int)

    p = subs.add_parser('values'); p.add_argument('workflow'); p.add_argument('node_id', type=int)
    p = subs.add_parser('unconnected'); p.add_argument('workflow')
    p.add_argument('--inputs', '-i', action='store_true'); p.add_argument('--outputs', '-o', action='store_true')
    p.add_argument('--primary', '-p', action='store_true')
    p = subs.add_parser('verify'); p.add_argument('workflow')

    p = subs.add_parser('diff'); p.add_argument('workflow1'); p.add_argument('workflow2')

    # Editing commands
    p = subs.add_parser('delete'); p.add_argument('workflow'); p.add_argument('node_ids', type=int, nargs='+')
    p.add_argument('--output', '-o'); p.add_argument('--dry-run', action='store_true'); p.add_argument('--cascade', action='store_true')

    p = subs.add_parser('copy'); p.add_argument('workflow'); p.add_argument('node_id', type=int)
    p.add_argument('--output', '-o'); p.add_argument('--title', '-t'); p.add_argument('--set', '-s', action='append')

    p = subs.add_parser('wire'); p.add_argument('workflow')
    p.add_argument('src_id', type=int, nargs='?'); p.add_argument('src_slot', nargs='?')
    p.add_argument('dst_id', type=int, nargs='?'); p.add_argument('dst_slot', nargs='?')
    p.add_argument('--disconnect', type=int); p.add_argument('--output', '-o')

    p = subs.add_parser('set'); p.add_argument('workflow'); p.add_argument('node_id', type=int)
    p.add_argument('values', nargs='+'); p.add_argument('--output', '-o')

    p = subs.add_parser('inline'); p.add_argument('workflow')
    p.add_argument('--output', '-o'); p.add_argument('--dry-run', action='store_true')

    p = subs.add_parser('batch'); p.add_argument('workflow'); p.add_argument('script')
    p.add_argument('--output', '-o'); p.add_argument('--dry-run', action='store_true')

    p = subs.add_parser('create'); p.add_argument('workflow'); p.add_argument('node_type')
    p.add_argument('--title', '-t'); p.add_argument('--input', '-i', action='append')
    p.add_argument('--output-slot', '-O', action='append'); p.add_argument('--output', '-o', dest='output_file')

    # Visualization commands
    p = subs.add_parser('layout'); p.add_argument('workflow')
    p.add_argument('--groups', '-g'); p.add_argument('--output', '-o'); p.add_argument('--nodes', '-n', nargs='+')

    p = subs.add_parser('visualize'); p.add_argument('workflow')
    p.add_argument('--output', '-o'); p.add_argument('--groups', '-g')
    p.add_argument('--scale', type=float); p.add_argument('--width', type=int)
    p.add_argument('--no-links', action='store_true'); p.add_argument('--local-links', action='store_true')

    # Fetch command
    p = subs.add_parser('fetch'); p.add_argument('workflow'); p.add_argument('node_id', type=int)
    p.add_argument('--source', '-s', action='store_true'); p.add_argument('--search', '-S')
    p.add_argument('--full', '-f', action='store_true')

    # ComfyUI integration
    p = subs.add_parser('submit'); p.add_argument('workflow')
    p = subs.add_parser('logs'); p.add_argument('--lines', '-n', type=int, default=50)

    args = parser.parse_args()

    commands = {
        'info': cmd_info, 'analyze': cmd_analyze, 'query': cmd_query, 'trace': cmd_trace,
        'graph': cmd_graph, 'path': cmd_path, 'subgraph': cmd_subgraph,
        'upstream': cmd_upstream, 'downstream': cmd_downstream, 'values': cmd_values,
        'unconnected': cmd_unconnected, 'verify': cmd_verify, 'diff': cmd_diff,
        'delete': cmd_delete, 'copy': cmd_copy, 'wire': cmd_wire, 'set': cmd_set,
        'inline': cmd_inline, 'batch': cmd_batch, 'create': cmd_create,
        'layout': cmd_layout, 'visualize': cmd_visualize, 'fetch': cmd_fetch,
        'submit': cmd_submit, 'logs': cmd_logs,
    }

    if args.command in commands:
        commands[args.command](args)
    else:
        parser.print_help()


if __name__ == '__main__':
    main()
