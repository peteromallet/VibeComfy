#!/usr/bin/env python3
"""MCP Server for ComfyUI Knowledge - enables Claude Code to search nodes."""

import asyncio
import json
import sys
from .knowledge import ComfyKnowledge


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
            Tool(name="comfy_search", description="Search ComfyUI nodes by keyword (supports multi-word queries, 8400+ nodes)",
                 inputSchema={"type": "object", "properties": {"query": {"type": "string", "description": "Search terms (e.g. 'audio reactive', 'ltx sampler', 'controlnet')"}, "limit": {"type": "integer", "default": 10}}, "required": ["query"]}),
            Tool(name="comfy_spec", description="Get full node specification with inputs/outputs",
                 inputSchema={"type": "object", "properties": {"node_name": {"type": "string"}}, "required": ["node_name"]}),
            Tool(name="comfy_author", description="Find nodes by author (e.g. kijai, filliptm, Lightricks)",
                 inputSchema={"type": "object", "properties": {"author": {"type": "string"}, "limit": {"type": "integer", "default": 20}}, "required": ["author"]}),
            Tool(name="comfy_categories", description="List all node categories with counts",
                 inputSchema={"type": "object", "properties": {}}),
            Tool(name="comfy_packs", description="List all node packs with counts",
                 inputSchema={"type": "object", "properties": {}}),
            Tool(name="comfy_read", description="Read workflow JSON as human-readable: pattern (txt2img, v2v), key params (model, steps, cfg), flow (NodeA -> NodeB -> NodeC)",
                 inputSchema={"type": "object", "properties": {"workflow_json": {"type": "string", "description": "ComfyUI workflow JSON"}}, "required": ["workflow_json"]}),
            Tool(name="comfy_stats", description="Node cache statistics (total nodes, packs, authors)",
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
                wf = json.loads(args["workflow_json"])
                text = kb.simplify_workflow(wf)
            except json.JSONDecodeError:
                text = "Invalid JSON"
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
