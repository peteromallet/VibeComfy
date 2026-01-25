# MCP Server Setup for comfy-nodes Skill

This skill works best with the `comfy-knowledge` MCP server providing live node registry access.

## Install MCP Dependency

```bash
pip install mcp
```

## Add MCP Server

```bash
# From VibeComfy directory
cat > run_mcp.sh << 'SCRIPT'
#!/bin/bash
cd "$(dirname "$0")"
python -m cli_tools.registry.mcp_server
SCRIPT
chmod +x run_mcp.sh

# Register with Claude Code
claude mcp add comfy-knowledge -- $(pwd)/run_mcp.sh
```

## Verify

```bash
claude mcp list
# comfy-knowledge: ... - ✓ Connected
```

## Available Tools

Once connected, these MCP tools are available:

- `mcp__comfy-knowledge__comfy_search` - Search 8400+ nodes
- `mcp__comfy-knowledge__comfy_spec` - Full node specification
- `mcp__comfy-knowledge__comfy_read` - Convert workflow JSON to readable format
- `mcp__comfy-knowledge__comfy_author` - Find nodes by author
- `mcp__comfy-knowledge__comfy_categories` - Browse node categories
- `mcp__comfy-knowledge__comfy_packs` - Browse node packs
- `mcp__comfy-knowledge__comfy_stats` - Registry statistics

## Without MCP

The skill still works without MCP but with reduced functionality:
- Pattern templates still available
- Node creation guidance still works
- No live registry search
