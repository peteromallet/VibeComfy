# ComfyUI Registry + MCP Server

Node discovery and workflow understanding for Claude Code. Helps agents work with ComfyUI by providing searchable access to 8,400+ nodes and converting workflow JSONs to readable format.

## What's Here

```
registry/
├── scraper.py      # Pulls nodes from api.comfy.org
├── knowledge.py    # Search/query API with task aliases + workflow reader
├── mcp_server.py   # MCP server for Claude Code (7 tools)
└── README.md
```

## Quick Start

### 1. Scrape Registry (one-time)

```bash
cd VibeComfy
python -m cli_tools.registry.scraper
# Scrapes 8000+ nodes to data/node_cache.json
```

### 2. Add MCP Server to Claude Code

```bash
# Create wrapper script
cat > run_mcp.sh << 'SCRIPT'
#!/bin/bash
cd /path/to/VibeComfy
python -m cli_tools.registry.mcp_server
SCRIPT
chmod +x run_mcp.sh

# Add to Claude Code (user scope recommended)
claude mcp add comfy-knowledge --scope user -- /path/to/VibeComfy/run_mcp.sh
```

### 3. Verify Connection

```bash
claude mcp list
# Should show: comfy-knowledge - ✓ Connected
```

## MCP Tools (10 total)

All tools use `comfy_` prefix for easy discovery.

### Node Discovery
| Tool | Description |
|------|-------------|
| `comfy_search` | Search 8,400+ nodes by keyword with smart aliases |
| `comfy_spec` | Get full node specification (inputs, outputs, types) |
| `comfy_author` | Find all nodes by author (kijai, Lightricks, filliptm) |
| `comfy_categories` | List all node categories with counts |
| `comfy_packs` | List all node packs with counts |
| `comfy_stats` | Cache statistics (total nodes, packs, authors) |

### Workflow Analysis
| Tool | Description |
|------|-------------|
| `comfy_read` | Convert workflow to readable format (pattern, params, variables, loops, flow) |
| `comfy_trace` | Trace a node's inputs/outputs with slot names |
| `comfy_upstream` | Find all nodes feeding into a target node |
| `comfy_downstream` | Find all nodes fed by a source node |

**Note:** Workflow tools accept either a JSON string or a file path.

---

## comfy_read - Workflow Reader

**The key tool for helping agents understand workflow JSONs.**

Converts complex JSON into readable format with:
- **Pattern detection**: txt2img, img2img, i2v, v2v, Flux, WAN, LTX, AnimateDiff
- **Modifier detection**: +ControlNet, +LoRA, +IPAdapter, +Upscale, +Inpaint
- **Key parameters**: model, steps, cfg, sampler, scheduler, size
- **Variables**: SetNode/GetNode pairs with their sources
- **Loops**: ForLoop/WhileLoop with iteration counts
- **Flow pipelines**: Categorized paths (VACE, Latent, Image, Video)

### Example

**Input**: 121-node WAN workflow JSON

**Output**:
```
## Pattern: WAN v2v +LoRA +Upscale

## Key Parameters
  model: wan2.1_i2v.safetensors
  steps: 20
  cfg: 7.5
  sampler: euler
  scheduler: normal

## Variables (12)
  $model <- Node 608 (WanVideoModelLoader)
  $vae <- Node 609 (WanVAELoader)
  ...

## Loops (1)
  ForLoop_1: 5 iterations

## Flow
  [VACE] 1140 -> 1183 -> 577 -> 595 -> 1220
  [Latent] 608 -> 577 -> 595

## Stats: 121 nodes, 104 connections, 42 unique types
```

---

## comfy_search - Smart Search

Search understands intent via 30+ task aliases:

| Query | Expands To |
|-------|------------|
| "beat detection" | onset, bpm, beat, drum detector, audio |
| "audio reactive" | amplitude, rms, sound reactive |
| "controlnet" | canny, depth, pose, lineart, openpose |
| "ltx" | ltx2, ltxv, stg, gemma, tiled sampler, looping |
| "wan" | wan2.1, wan2.2, vace, wanvideo |
| "i2v" | image2video, svd, stable video, img2vid |
| "v2v" | video2video, vid2vid |
| "flux" | bfl, schnell, dev, guidance |
| "klein" | deforum, flux2, temporal, warp, optical flow |
| "upscale" | esrgan, realesrgan, 4x, super resolution |
| "face" | insightface, faceid, portrait, reactor |
| "segmentation" | sam, sam2, clipseg, mask, cutout |

### Usage Examples

```
comfy_search("ltx sampler")
→ LTXV Base Sampler, LTXV Tiled Sampler, LTXV Looping Sampler...

comfy_search("audio reactive")
→ ROTI_AudioReactiveViz, FL_Audio_Reactive_*, KJ audio nodes...

comfy_search("mask blur")
→ GrowMaskWithBlur, MaskBlur, FeatherMask...

comfy_author("kijai")
→ All 47 KJNodes

comfy_author("Lightricks")
→ All 38 LTX-2 nodes
```

---

## Curated Content

Beyond the api.comfy.org registry, the cache includes curated nodes and workflows:

| Source | Count | Highlights |
|--------|-------|------------|
| api.comfy.org registry | 8,149 | Full registry scrape |
| LTX-2 (Lightricks) | 44 | 38 nodes + 6 workflows |
| Core ComfyUI | 48 | Essential built-in nodes |
| Workflow patterns | 20 | txt2img, img2img, ControlNet, etc. |
| Klein/Deforum | 15 | v2v pipeline mappings |
| KJNodes | 47 | Workflow utils, masks |
| Fill-Nodes | 56 | VFX, audio, glitch, dither |
| RyanOnTheInside | 34 | Audio/MIDI reactive, particles |
| Purz | 23 | Patterns, tutorials |
| Steerable-Motion | 15 | Image-to-video interpolation |
| Documentation | 10 | Official ComfyUI docs |

**Total: 8,456 searchable items**

---

## Integration with CLI

The MCP tools use the same analysis engine as the CLI (`cli_tools/analysis.py`):

| MCP Tool | CLI Equivalent |
|----------|---------------|
| `comfy_read` | `python we_vibin.py analyze workflow.json` |
| `comfy_trace` | `python we_vibin.py trace workflow.json NODE` |
| `comfy_upstream` | `python we_vibin.py upstream workflow.json NODE` |
| `comfy_downstream` | `python we_vibin.py downstream workflow.json NODE` |

The CLI `query` command uses simple substring matching for precision:
```bash
python we_vibin.py query workflow.json -t KSampler  # Exact type matching
```

Use `comfy_search` via MCP for smart alias expansion.

---

## Skill Integration

Four skills work with this MCP server:

| Skill | Purpose | Uses MCP for |
|-------|---------|--------------|
| `comfy-registry` | Node discovery | comfy_search, comfy_spec, comfy_author |
| `comfy-analyze` | Workflow understanding | comfy_read, comfy_trace, comfy_upstream |
| `comfy-edit` | Workflow editing | CLI tools + patterns |
| `comfy-nodes` | Custom node development | Finding similar nodes for reference |

Together they enable:
- "Find nodes for upscaling" → `comfy-registry` + MCP search
- "What does this workflow do?" → `comfy-analyze` + MCP read
- "Add ControlNet to this workflow" → `comfy-edit` + patterns + CLI
- "Convert my Python to a node" → `comfy-nodes` + MCP finds examples

---

## Updating the Cache

Registry updates weekly. To refresh:

```bash
python -m cli_tools.registry.scraper
```

## Requirements

- Python 3.8+
- `mcp` package: `pip install mcp`
