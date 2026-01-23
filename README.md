# VibeComfy

CLI tools for understanding and editing ComfyUI workflow JSON files - built for use with [Claude Code](https://claude.ai/claude-code).

## Setup

1. Copy `.env.example` to `.env` and set your ComfyUI path:
   ```bash
   cp .env.example .env
   # Edit .env and set COMFY_PATH=/path/to/your/ComfyUI
   ```

2. Launch ComfyUI with logging enabled:
   ```bash
   cd /path/to/ComfyUI
   python main.py 2>&1 | tee comfyui.log
   ```

## Usage

1. Drop a workflow JSON into the `workflows/` folder
2. Launch Claude Code from the VibeComfy directory:
   ```bash
   cd VibeComfy
   claude --dangerously-skip-permissions
   ```
3. Tell it what you want to do - understand a workflow, adjust it, etc.

Claude can submit workflows to ComfyUI and read the logs to help debug issues.

The CLAUDE.md file contains instructions that Claude Code reads automatically. These can be used for other agents too. Its instructions encourage it to suggest changes based on issues it experiences, contributions are much appreciated!

## Example Prompts

- "Analyze the most recent workflow and explain what it does"
- "Find all the sampler nodes and show me their settings"
- "Duplicate the upscaling chain and wire it to a second output"
- "Trace the path from the video loader to the final output"

## Structure

```
VibeComfy/
├── we_vibin.py        # CLI entry point
├── cli_tools/         # Library modules
│   ├── workflow.py    # I/O, utilities
│   ├── analysis.py    # Analysis, path finding
│   ├── editing.py     # Copy, wire, delete, set
│   ├── batch.py       # Batch script execution
│   └── ...
└── workflows/         # Drop your workflows here
```

## Manual Usage

```bash
python we_vibin.py info workflows/my_workflow.json
python we_vibin.py trace workflows/my_workflow.json 577
python we_vibin.py --help
```

See [CLAUDE.md](CLAUDE.md) for the full command reference.
