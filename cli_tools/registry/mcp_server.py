#!/usr/bin/env python3
"""MCP Server for ComfyUI Knowledge - enables Claude Code to search nodes and analyze workflows."""

import asyncio
import json
import sys
from pathlib import Path
from .knowledge import ComfyKnowledge


def load_workflow(source: str) -> dict:
    """Load workflow from JSON string or file path."""
    # If it looks like JSON (starts with {), parse it directly
    source_stripped = source.strip()
    if source_stripped.startswith('{'):
        return json.loads(source)

    # Otherwise try as file path
    path = Path(source)
    if path.exists() and path.suffix == '.json':
        with open(path) as f:
            return json.load(f)

    # Last resort: try parsing as JSON anyway
    return json.loads(source)


def format_trace_result(result: dict) -> str:
    """Format trace_node result for display."""
    if 'error' in result:
        return result['error']

    lines = [f"[Node {result['node_id']}] {result['node_type']}"]
    if result.get('title'):
        lines[0] += f' "{result["title"]}"'

    lines.append("\n  INPUTS:")
    for inp in result['inputs']:
        if inp['source_node']:
            lines.append(f"    [{inp['slot']}] {inp['name']} <- Node {inp['source_node']} ({inp['source_type']}, slot {inp['source_slot']})")
        else:
            lines.append(f"    [{inp['slot']}] {inp['name']} (unconnected)")

    lines.append("\n  OUTPUTS:")
    for out in result['outputs']:
        if out['targets']:
            for t in out['targets']:
                lines.append(f"    [{out['slot']}] {out['name']} -> Node {t['node']} ({t['type']}, slot {t['slot']})")
        else:
            lines.append(f"    [{out['slot']}] {out['name']} (unconnected)")

    return "\n".join(lines)


def main():
    try:
        from mcp.server import Server
        from mcp.server.stdio import stdio_server
        from mcp.types import Tool, TextContent
    except ImportError:
        print("Install MCP: pip install mcp", file=sys.stderr)
        sys.exit(1)

    kb = ComfyKnowledge()
    server = Server("comfy-knowledge")

    @server.list_tools()
    async def list_tools():
        return [
            Tool(name="comfy_search", description="Search 8400+ ComfyUI nodes by keyword. Start here to find nodes for a task. Supports aliases (e.g. 'v2v' finds video2video nodes).",
                 inputSchema={"type": "object", "properties": {"query": {"type": "string", "description": "Search terms (e.g. 'audio reactive', 'ltx sampler', 'controlnet')"}, "limit": {"type": "integer", "default": 10}}, "required": ["query"]}),
            Tool(name="comfy_spec", description="Get full node specification (inputs, outputs, types). Use after comfy_search to inspect a specific node before using it.",
                 inputSchema={"type": "object", "properties": {"node_name": {"type": "string", "description": "Exact node name from search results"}}, "required": ["node_name"]}),
            Tool(name="comfy_author", description="Find all nodes by a specific author (e.g. kijai, filliptm, Lightricks, Kosinkadink).",
                 inputSchema={"type": "object", "properties": {"author": {"type": "string"}, "limit": {"type": "integer", "default": 20}}, "required": ["author"]}),
            Tool(name="comfy_categories", description="List all node categories with counts. Use to explore what's available.",
                 inputSchema={"type": "object", "properties": {}}),
            Tool(name="comfy_packs", description="List all node packs with counts. Use to explore what's available.",
                 inputSchema={"type": "object", "properties": {}}),
            Tool(name="comfy_read", description="Convert workflow JSON to readable summary: pattern (txt2img, v2v), key params (model, steps, cfg), variables, loops, flow. Use first to understand any workflow.",
                 inputSchema={"type": "object", "properties": {"workflow": {"type": "string", "description": "ComfyUI workflow JSON string or file path"}}, "required": ["workflow"]}),
            Tool(name="comfy_trace", description="Trace a node's inputs and outputs with slot names. Use to find slot numbers before wiring nodes together.",
                 inputSchema={"type": "object", "properties": {"workflow": {"type": "string", "description": "ComfyUI workflow JSON string or file path"}, "node_id": {"type": "integer", "description": "Node ID to trace"}}, "required": ["workflow", "node_id"]}),
            Tool(name="comfy_upstream", description="Find all nodes feeding into a target node. Use to understand what affects a node's output.",
                 inputSchema={"type": "object", "properties": {"workflow": {"type": "string", "description": "ComfyUI workflow JSON string or file path"}, "node_id": {"type": "integer", "description": "Target node ID"}, "depth": {"type": "integer", "default": 5, "description": "Max depth to traverse"}}, "required": ["workflow", "node_id"]}),
            Tool(name="comfy_downstream", description="Find all nodes fed by a source node. Use to understand what a node's output affects.",
                 inputSchema={"type": "object", "properties": {"workflow": {"type": "string", "description": "ComfyUI workflow JSON string or file path"}, "node_id": {"type": "integer", "description": "Source node ID"}, "depth": {"type": "integer", "default": 5, "description": "Max depth to traverse"}}, "required": ["workflow", "node_id"]}),
            Tool(name="comfy_stats", description="Node cache statistics. Use to verify the registry is loaded.",
                 inputSchema={"type": "object", "properties": {}}),
        ]

    @server.call_tool()
    async def call_tool(name, args):
        if name == "comfy_search":
            results = kb.search_nodes(args["query"], args.get("limit", 10))
            if results:
                lines = []
                for r in results:
                    desc = r.get('description', '')[:80]
                    desc_str = f" - {desc}..." if desc else ""
                    pack = r.get('pack', '')
                    pack_str = f" [{pack}]" if pack else ""
                    lines.append(f"**{r['name']}** ({r.get('category', '?')}){pack_str}{desc_str}")
                text = "\n".join(lines)
            else:
                text = "No matching nodes found."

        elif name == "comfy_spec":
            spec = kb.get_node_spec(args["node_name"])
            text = json.dumps(spec, indent=2) if spec else f"Node '{args['node_name']}' not found."

        elif name == "comfy_author":
            results = kb.search_by_author(args["author"], args.get("limit", 20))
            if results:
                lines = [f"- **{r['name']}** ({r.get('category', '?')})" for r in results]
                text = f"Found {len(results)} nodes:\n" + "\n".join(lines)
            else:
                text = f"No nodes found by author '{args['author']}'."

        elif name == "comfy_categories":
            cats = kb.list_categories()[:30]
            if cats:
                lines = [f"- {cat}: {count}" for cat, count in cats]
                text = f"Top {len(cats)} categories:\n" + "\n".join(lines)
            else:
                text = "No categories found. Run scraper to populate cache."

        elif name == "comfy_packs":
            packs = kb.list_packs()[:30]
            if packs:
                lines = [f"- {pack}: {count}" for pack, count in packs]
                text = f"Top {len(packs)} packs:\n" + "\n".join(lines)
            else:
                text = "No packs found. Run scraper to populate cache."

        elif name == "comfy_read":
            try:
                wf = load_workflow(args["workflow"])
                text = kb.simplify_workflow(wf)
            except json.JSONDecodeError:
                text = "Invalid JSON"
            except FileNotFoundError:
                text = f"File not found: {args['workflow']}"

        elif name == "comfy_trace":
            try:
                from cli_tools.analysis import trace_node
                wf = load_workflow(args["workflow"])
                result = trace_node(wf, args["node_id"])
                text = format_trace_result(result)
            except json.JSONDecodeError:
                text = "Invalid JSON"
            except FileNotFoundError:
                text = f"File not found: {args['workflow']}"

        elif name == "comfy_upstream":
            try:
                from cli_tools.analysis import find_upstream
                from cli_tools import workflow as wf_mod
                wf = load_workflow(args["workflow"])
                result = find_upstream(wf, args["node_id"], max_depth=args.get("depth", 5))

                if 'error' in result:
                    text = result['error']
                else:
                    nodes_dict = wf_mod.get_nodes_dict(wf)
                    lines = [f"Upstream of Node {args['node_id']} (depth {args.get('depth', 5)}):"]
                    for nid, depth in sorted(result['nodes'].items(), key=lambda x: x[1]):
                        if nid != args['node_id']:
                            node = nodes_dict.get(nid, {})
                            lines.append(f"  [depth {depth}] Node {nid} ({node.get('type', '?')})")
                    text = "\n".join(lines)
            except json.JSONDecodeError:
                text = "Invalid JSON"
            except FileNotFoundError:
                text = f"File not found: {args['workflow']}"

        elif name == "comfy_downstream":
            try:
                from cli_tools.analysis import find_downstream
                from cli_tools import workflow as wf_mod
                wf = load_workflow(args["workflow"])
                result = find_downstream(wf, args["node_id"], max_depth=args.get("depth", 5))

                if 'error' in result:
                    text = result['error']
                else:
                    nodes_dict = wf_mod.get_nodes_dict(wf)
                    lines = [f"Downstream of Node {args['node_id']} (depth {args.get('depth', 5)}):"]
                    for nid, depth in sorted(result['nodes'].items(), key=lambda x: x[1]):
                        if nid != args['node_id']:
                            node = nodes_dict.get(nid, {})
                            lines.append(f"  [depth {depth}] Node {nid} ({node.get('type', '?')})")
                    text = "\n".join(lines)
            except json.JSONDecodeError:
                text = "Invalid JSON"
            except FileNotFoundError:
                text = f"File not found: {args['workflow']}"

        elif name == "comfy_stats":
            stats = kb.stats()
            text = "\n".join(f"{k}: {v}" for k, v in stats.items())

        else:
            text = f"Unknown tool: {name}"

        return [TextContent(type="text", text=text)]

    async def run():
        async with stdio_server() as streams:
            await server.run(
                streams[0],
                streams[1],
                server.create_initialization_options()
            )
    asyncio.run(run())


if __name__ == "__main__":
    main()
