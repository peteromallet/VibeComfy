# MCP Server Setup

The `comfy-knowledge` MCP server provides node discovery and workflow analysis tools.

## Install

```bash
# Clone VibeComfy
git clone https://github.com/peteromallet/VibeComfy
cd VibeComfy

# Install MCP dependency
pip install mcp

# Create run script
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
# comfy-knowledge: ... - Connected
```

## Available Tools

Once connected, these tools are available in any Claude session:

| Tool | Purpose |
|------|---------|
| `comfy_search` | Search 8400+ nodes by keyword |
| `comfy_spec` | Get full node specification |
| `comfy_trace` | Trace node connections in workflow |
| `comfy_upstream` | Find nodes feeding into target |
| `comfy_downstream` | Find nodes fed by source |
| `comfy_read` | Convert workflow to readable summary |
| `comfy_author` | Find nodes by author |
| `comfy_categories` | Browse node categories |
| `comfy_packs` | Browse node packs |
| `comfy_stats` | Registry statistics |

## Global Skill (Optional)

To have Claude automatically know about these tools in any project:

```bash
# Copy skill to global location
cp -r .claude/skills/comfy-workflows ~/.claude/skills/
```

Now when you ask about ComfyUI workflows in any project, Claude will know the tools exist.
