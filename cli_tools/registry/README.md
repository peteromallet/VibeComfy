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

## MCP Tools (7 total)

All tools use `comfy_` prefix for easy discovery.

| Tool | Description |
|------|-------------|
| `comfy_search` | Search 8,400+ nodes by keyword with smart aliases |
| `comfy_spec` | Get full node specification (inputs, outputs, types) |
| `comfy_author` | Find all nodes by author (kijai, Lightricks, filliptm) |
| `comfy_categories` | List all node categories with counts |
| `comfy_packs` | List all node packs with counts |
| `comfy_read` | Convert workflow JSON to human-readable format |
| `comfy_stats` | Cache statistics (total nodes, packs, authors) |

---

## comfy_read - Workflow Reader

**The key tool for helping agents understand workflow JSONs.**

Converts complex JSON into readable format with:
- **Pattern detection**: txt2img, img2img, i2v, v2v, Flux, WAN, LTX, AnimateDiff
- **Modifier detection**: +ControlNet, +LoRA, +IPAdapter, +Upscale, +Inpaint
- **Key parameters**: model, steps, cfg, sampler, scheduler, size
- **Flow visualization**: NodeA -> NodeB -> NodeC

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

## Flow
  Checkpoint -> KSampler -> VAEDecode -> SaveImage
  LoadImage -> ControlNetApply -> KSampler

## Stats: 121 nodes, 104 connections
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

## Skill Integration

The `comfy-nodes` skill (`.claude/skills/comfy-nodes/`) works with this MCP:

| Component | Provides |
|-----------|----------|
| **Skill** | Node templates, Python→Node conversion, workflow patterns |
| **MCP** | Live registry search, node specs, workflow reading |

Together they enable:
- "Create a node for image blending" → skill templates + MCP finds similar nodes
- "Build txt2img with LoRA" → skill workflow pattern + MCP finds specific nodes
- "Convert my Python to ComfyUI node" → skill guides structure, MCP finds examples
- "What does this workflow do?" → MCP reads JSON into understandable format

---

## Updating the Cache

Registry updates weekly. To refresh:

```bash
python -m cli_tools.registry.scraper
```

## Requirements

- Python 3.8+
- `mcp` package: `pip install mcp`
