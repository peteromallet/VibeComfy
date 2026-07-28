# Case 07 — lora_loader on image/flux2_klein_4b_t2i

**TL;DR:** This is a TRUE ABSENCE (not a false-skip). The golden workflow `image/flux2_klein_4b_t2i` genuinely contains zero LoRA nodes — it is a pure Flux.2 Klein text-to-image pipeline with no LoRA patching. The skip is correct. **Root cause: PAIRING.** The campaign runner paired a `lora_loader` feature with a workflow that doesn't use LoRA. The fix is in the pairing layer: either add a LoRA workflow to the image ready_template corpus, or remove `lora_loader` from the set of features tested against LoRA-free workflows.

---

## 1. False-Skip Audit: Does the Golden Actually Contain a LoRA Node?

I enumerated every node type in the source workflow and the resolved ready template.

**Source nodes** (`ready_templates/sources/official/image/flux2_klein_4b_t2i.json`):

| Node | Type |
|------|------|
| 76   | `PrimitiveStringMultiline` |
| 79   | `MarkdownNote` |
| 9, 78 | `SaveImage` |
| 75   | `7b34ab90-36f9-45ba-a665-71d418f0df18` (subgraph ref) |
| 77   | `a67caa28-5f85-4917-8396-36004960dd30` (subgraph ref) |

**Resolved inner nodes** (from the ready template `ready_templates/image/flux2_klein_4b_t2i.py`):

Subgraph `text_to_image_flux2_klein_4b`: `KSamplerSelect`, `Flux2Scheduler`, `EmptyFlux2LatentImage`, `UNETLoader`, `CLIPLoader`, `VAELoader`, `RandomNoise`, `CLIPTextEncode`×2, `CFGGuider`, `SamplerCustomAdvanced`, `VAEDecode`.

Subgraph `text_to_image_flux2_klein_4b_distilled`: same set plus `ConditioningZeroOut`.

**No type name contains "lora"** (case-insensitive). The matcher `_node_matches_feature` for `lora_loader` uses keyword `"lora"` and an empty categories list (because `"model/loaders"` would false-positive on CLIPLoader, UNETLoader, VAELoader). This correctly returns `[]`. **The skip is legitimate.**

## 2. Other Ready Templates That DO Contain LoRA Nodes

Two image-domain ready templates contain `LoraLoaderModelOnly` (class_type `"LoraLoaderModelOnly"`):

| Template | Path |
|----------|------|
| `image/qwen_image_2512` | `ready_templates/image/qwen_image_2512.py` — uses `LoraLoaderModelOnly(lora_name=..., model=unetloader)` on a Qwen-Image 2512 workflow |
| `edit/qwen_image_edit` | `ready_templates/edit/qwen_image_edit.py` — uses `LoraLoaderModelOnly(lora_name=..., model=unetloader)` on a Qwen-Image-Edit workflow |

Additionally, ~20 video templates (LTX Video, WanVideo, Lightricks ICLoRA) use `LoraLoader`, `LoraLoaderModelOnly`, or custom LoRA loader nodes — but those are in the `video/` domain.

**Key observation:** The Flux2 Klein family (`flux2_klein_4b_t2i`, `flux2_klein_9b_t2i`, `flux2_klein_9b_gguf_t2i`) has **zero** LoRA support in any of its ready templates. The Qwen image family adopted LoRA; the Flux Klein family did not.

## 3. What a Correct "lora_loader" Node Looks Like

The canonical ComfyUI node is **`LoraLoaderModelOnly`** (`class_type: "LoraLoaderModelOnly"`, pack: `comfy`). Key widgets/inputs:

| Input | Type | Description |
|-------|------|-------------|
| `model` | MODEL | UNet model to patch |
| `lora_name` | STRING (enum) | LoRA file from the model directory |
| `strength_model` | FLOAT (default: 1.0) | LoRA weight strength |

A second variant is `LoraLoader` (`class_type: "LoraLoader"`) which additionally accepts a `clip` input and a `strength_clip` parameter, used when the LoRA also patches the CLIP text encoder.

The matcher keyword `"lora"` correctly matches both `"LoraLoaderModelOnly"` and `"LoraLoader"` (and any vendor-specific variant like `"ICLoRALoader"`).

## 4. Root Cause: PAIRING Failure

The campaign's pairing logic (in `run_campaign.py` / `case.py`) selected `lora_loader` as the feature to test against the `image/flux2_klein_4b_t2i` golden workflow. This workflow is a **pure Flux.2 Klein T2I pipeline** with no LoRA patching — it loads a UNET directly and runs sampling. There is no LoRA node to remove.

**The pairing layer should have excluded this workflow for `lora_loader`**, or better, should have selected a workflow that actually contains a LoRA node (e.g., `image/qwen_image_2512` or `edit/qwen_image_edit`). This is a coverage gap in the campaign's workflow–feature matrix: only 2/14 image ready templates contain LoRA nodes, and neither is a Flux2 Klein variant.

**Recommended fix (pairing layer):** Either (a) add `image/flux2_klein_4b_t2i` to a blocklist for `lora_loader`, or (b) refactor pairing to only propose a feature for a workflow when `find_feature_node_ids(golden, feature)` returns ≥1 hit **at pairing time** (pre-screening, not at execution time). Option (b) is more robust and would have caught this before the campaign ran.
