# VibeComfy

CLI + MCP server for working with ComfyUI workflows via [Claude Code](https://claude.ai/claude-code).

## Example Prompts

- **Discovery**: "What nodes exist for audio-reactive effects?"
- **Analysis**: "What's happening with the loop in this workflow"
- **Editing**: "Apply the Controlnet for Qwen before the Ksampler"
- **Submission**: "Run this workflow with a prompt about horses"
- **Node Dev**: "Convert my Python blur function to a ComfyUI node"

## Setup

```bash
git clone https://github.com/peteromallet/VibeComfy
cd VibeComfy
pip install -r requirements.txt
```

Then just run `claude` - the MCP server auto-configures via `.mcp.json`.

## ComfyUI Integration

To submit workflows, set your ComfyUI path in `.env`:

```bash
cp .env.example .env
# Edit: COMFY_PATH=/path/to/ComfyUI
```

Run ComfyUI with logging: `python main.py 2>&1 | tee comfyui.log`

## Documentation

- [CLAUDE.md](CLAUDE.md) - CLI command reference
- [cli_tools/registry/README.md](cli_tools/registry/README.md) - MCP server details
