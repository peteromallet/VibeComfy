---
name: comfy-nodes
description: This skill should be used when the user wants to "create a ComfyUI node", "make node from Python", "convert Python to node", "build a workflow", "create workflow JSON", "find nodes for upscaling", "add ControlNet", "make a txt2img workflow", or needs help with ComfyUI custom node development, workflow patterns, or node discovery using the 8400+ node registry.
version: 0.3.0
---

# ComfyUI Node & Workflow Development

This skill provides guidance for creating ComfyUI custom nodes and building workflows, with access to a registry of 8400+ nodes via MCP tools.

## MCP Tools Available

This skill integrates with the `comfy-knowledge` MCP server for live node registry access. See [MCP_SETUP.md](MCP_SETUP.md) for installation.

Available tools:
- `mcp__comfy-knowledge__comfy_search` - Search 8400+ nodes by keyword
- `mcp__comfy-knowledge__comfy_spec` - Get full node specification
- `mcp__comfy-knowledge__comfy_read` - Convert workflow JSON to readable format
- `mcp__comfy-knowledge__comfy_author` - Find nodes by author
- `mcp__comfy-knowledge__comfy_categories` - Browse node categories
- `mcp__comfy-knowledge__comfy_packs` - Browse node packs
- `mcp__comfy-knowledge__comfy_stats` - Registry statistics

To find nodes, call `comfy_search` first, then `comfy_spec` for promising results.
To understand a workflow, use `comfy_read` to convert JSON to readable format.

---

## Converting Python to ComfyUI Node

When user has Python code to convert:

### Step 1: Analyze the Python function
```python
# User's original function
def apply_blur(image, radius=5):
    from PIL import ImageFilter
    return image.filter(ImageFilter.GaussianBlur(radius))
```

### Step 2: Wrap in ComfyUI node structure
```python
import torch
import numpy as np
from PIL import Image, ImageFilter

class ApplyBlurNode:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "image": ("IMAGE",),
                "radius": ("FLOAT", {"default": 5.0, "min": 0.1, "max": 50.0, "step": 0.1}),
            }
        }

    RETURN_TYPES = ("IMAGE",)
    FUNCTION = "apply_blur"
    CATEGORY = "image/filters"

    def apply_blur(self, image, radius):
        # Convert ComfyUI tensor [B,H,W,C] to PIL
        batch_results = []
        for i in range(image.shape[0]):
            img_np = (image[i].cpu().numpy() * 255).astype(np.uint8)
            pil_img = Image.fromarray(img_np)

            # Apply the original function logic
            blurred = pil_img.filter(ImageFilter.GaussianBlur(radius))

            # Convert back to tensor
            result_np = np.array(blurred).astype(np.float32) / 255.0
            batch_results.append(torch.from_numpy(result_np))

        return (torch.stack(batch_results),)

NODE_CLASS_MAPPINGS = {"ApplyBlurNode": ApplyBlurNode}
NODE_DISPLAY_NAME_MAPPINGS = {"ApplyBlurNode": "Apply Blur"}
```

### Key Conversions

| Python Type | ComfyUI Type | Conversion |
|-------------|--------------|------------|
| PIL Image | IMAGE | `torch.from_numpy(np.array(pil) / 255.0)` |
| numpy array | IMAGE | `torch.from_numpy(arr.astype(np.float32))` |
| cv2 image (BGR) | IMAGE | `torch.from_numpy(cv2.cvtColor(img, cv2.COLOR_BGR2RGB) / 255.0)` |
| float 0-255 | IMAGE | Divide by 255.0 |
| Single image | Batch | `tensor.unsqueeze(0)` |

### Checklist for Python → Node
- [ ] Identify inputs and their types
- [ ] Map Python types to ComfyUI types (IMAGE, MASK, FLOAT, etc.)
- [ ] Handle batch dimension [B,H,W,C]
- [ ] Return tuple: `return (result,)`
- [ ] Add to NODE_CLASS_MAPPINGS

For comprehensive guide with V3 schema, see [references/NODE_TEMPLATE.md](references/NODE_TEMPLATE.md).

---

## Creating Custom Nodes

### Quick Template
```python
class MyNode:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "image": ("IMAGE",),
                "value": ("FLOAT", {"default": 1.0, "min": 0.0, "max": 1.0}),
            },
            "optional": {
                "mask": ("MASK",),
            }
        }

    RETURN_TYPES = ("IMAGE",)
    RETURN_NAMES = ("output",)
    FUNCTION = "execute"
    CATEGORY = "Custom/Category"

    def execute(self, image, value, mask=None):
        result = image * value
        return (result,)

NODE_CLASS_MAPPINGS = {"MyNode": MyNode}
NODE_DISPLAY_NAME_MAPPINGS = {"MyNode": "My Node"}
```

### Common Input Types

| Type | Shape/Format | Widget Options |
|------|--------------|----------------|
| IMAGE | [B,H,W,C] float 0-1 | - |
| MASK | [H,W] or [B,H,W] float 0-1 | - |
| LATENT | {"samples": [B,C,H,W]} | - |
| MODEL | ModelPatcher | - |
| CLIP | CLIP encoder | - |
| VAE | VAE model | - |
| CONDITIONING | [(cond, pooled), ...] | - |
| INT | integer | default, min, max, step |
| FLOAT | float | default, min, max, step, display |
| STRING | str | default, multiline |
| BOOLEAN | bool | default |
| COMBO | str | List of options as type |

---

## Building Workflow JSON

### Workflow Structure
```json
{
  "nodes": [
    {
      "id": 1,
      "type": "CheckpointLoaderSimple",
      "pos": [0, 0],
      "widgets_values": ["model.safetensors"]
    },
    {
      "id": 2,
      "type": "KSampler",
      "pos": [400, 0],
      "widgets_values": [42, "fixed", 20, 7.5, "euler", "normal", 1.0]
    }
  ],
  "links": [
    [1, 1, 0, 2, 0, "MODEL"]
  ]
}
```

### Link Format
`[link_id, from_node, from_slot, to_node, to_slot, type]`

### Core Patterns

**txt2img**: CheckpointLoader → CLIPTextEncode (×2) → EmptyLatentImage → KSampler → VAEDecode → SaveImage

**img2img**: LoadImage → VAEEncode → KSampler (denoise<1.0) → VAEDecode → SaveImage

**ControlNet**: LoadControlNet + Preprocessor → ControlNetApply → KSampler

**Upscale**: LoadUpscaleModel → ImageUpscaleWithModel → SaveImage

**LoRA**: CheckpointLoader → LoraLoader → KSampler

**Flux**: UNETLoader + DualCLIPLoader + VAELoader → FluxGuidance → KSampler

For detailed patterns, see [references/PATTERNS.md](references/PATTERNS.md).

---

## References

| File | Content |
|------|---------|
| [OFFICIAL_DOCS.md](references/OFFICIAL_DOCS.md) | Official ComfyUI docs - node structure, API, data types |
| [NODE_TEMPLATE.md](references/NODE_TEMPLATE.md) | Full node dev guide, V3 schema, examples |
| [PATTERNS.md](references/PATTERNS.md) | Workflow patterns (20+) |
| [PURZ_EXAMPLES.md](references/PURZ_EXAMPLES.md) | Official ComfyUI examples |
| [RECOMMENDED_PACKS.md](references/RECOMMENDED_PACKS.md) | KJNodes, Fill-Nodes, Purz, RyanOnTheInside, Steerable-Motion |

## Node Categories

Organize custom nodes:
- `image/` - Image processing
- `latent/` - Latent operations
- `conditioning/` - Prompt encoding
- `sampling/` - Sampler variants
- `loaders/` - Model loading
- `video/` - Animation/video
- `mask/` - Mask operations
- `utils/` - Utilities
