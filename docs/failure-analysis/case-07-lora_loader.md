# Case 07 — lora_loader on `image/flux2_klein_4b_t2i`

**Verdict:** `skipped_no_feature_node`
**Root Classification:** PAIRING — true absence (not a false-skip/matcher miss)

---

## TL;DR

The golden workflow `flux2_klein_4b_t2i` is a bare FLUX2 t2i pipeline with **zero LoRA nodes**. The keyword matcher (`_FEATURE_RULES["lora_loader"]["keywords"] = ["lora"]`) correctly returned no matches. This is **not a false-skip** — there is simply no LoRA loader to remove. The campaign author erroneously paired a non-LoRA workflow with the `lora_loader` feature. The existing lora_loader pairing that DOES work is `video/wanvideo_wrapper_13b_control_lora` (index 6); the best re-pairing candidate in the image domain is `image/qwen_image_2512` (uses `LoraLoaderModelOnly`).

---

## 1. Golden Workflow Contents (All Node Types)

The layout.json (read from `ready_templates/image/flux2_klein_4b_t2i.layout.json`) contains **two identical parallel branches** (base pass + refinement pass) with these unique `Node name for S&R` values:

| Node Type | Count |
|---|---|
| `KSamplerSelect` | 2 |
| `Flux2Scheduler` | 2 |
| `EmptyFlux2LatentImage` | 2 |
| `UNETLoader` | 2 |
| `CLIPLoader` | 2 |
| `VAELoader` | 2 |
| `RandomNoise` | 2 |
| `CLIPTextEncode` | 3 |
| `CFGGuider` | 2 |
| `SamplerCustomAdvanced` | 2 |
| `VAEDecode` | 2 |
| `SaveImage` | 2 |
| `ConditioningZeroOut` | 1 |

**None of these 13 type names contain the substring "lora".** The matcher in `_node_matches_feature()` (creative.py:672-699) lowercases the type name and checks `_FEATURE_RULES["lora_loader"]["keywords"]` which is `["lora"]`. Every node correctly fails this check.

**Verdict: TRUE ABSENCE.** The golden simply has no LoRA node. The skip is correct behavior.

---

## 2. Matching Logic Confirmation

From `creative.py` lines 657-669:

```python
"lora_loader": {
    "categories": [],  # model/loaders is too broad (CLIPLoader etc.)
    "keywords": ["lora"],
},
```

No category match is attempted (empty list). The keyword match is the sole path. This is **intentionally conservative**: matching on "lora" substring correctly catches `LoraLoader`, `LoraLoaderModelOnly`, `WanVideoLoraSelect`, etc., while NOT matching `CLIPLoader`, `UNETLoader`, `VAELoader`. There is no matcher bug here.

---

## 3. Why This Workflow Was Paired with lora_loader

In `run_campaign.py` line 70:

```python
("image/flux2_klein_4b_t2i", "lora_loader"),  # case 7 (index 7, 0-indexed: 8)
```

This is a **campaign author assumption error**. The author likely assumed FLUX2 t2i pipelines include a LoRA loader by convention, but this particular workflow is a straightforward t2i without any style/character LoRA. The parallel branches are for a two-pass (base + refinement) sampler architecture, not for LoRA injection.

The same issue exists for `flux2_klein_9b_t2i` (used in REPAIR but could suffer the same absence if ever paired with lora_loader).

---

## 4. Candidate Workflows That DO Have LoRA Loaders

### In the Additive Campaign
- **`video/wanvideo_wrapper_13b_control_lora`** (index 6, paired with lora_loader — **works correctly**): contains `WanVideoLoraSelect` node. This is the only lora_loader case that correctly fires.

### In ready_templates/ (image domain candidates for re-pairing)
| Workflow | LoRA Node Class | Why Good |
|---|---|---|
| `image/qwen_image_2512` | `LoraLoaderModelOnly` | Image domain; uses standard comfy-core `LoraLoaderModelOnly` with `lora_name: str`, `strength_model: float` widgets. Direct precedent. |
| `edit/qwen_image_edit` | Indirect (imports lora constants) | Image-edit domain; may contain LoRA in subgraphs. |
| `video/ltx2_3_lightricks_iclora_union_control` | Custom LoRA | Domain-specific (iclora), not a general lora_loader target. |

### In structural_harness tests
- `wan22_stack_highlow_noise_lora.py`, `wan_t2v_splice_modelpatch_before_loras.py` — test-only, not ready_templates.

---

## 5. What a Correct "lora_loader" Node Looks Like

Per ComfyUI built-in node docs and corpus precedents:

| Class Type | Source | Key Widgets | Outputs |
|---|---|---|---|
| `LoraLoader` | comfy-core | `lora_name` (COMBO), `strength_model` (FLOAT), `strength_clip` (FLOAT) | `model`, `clip` |
| `LoraLoaderModelOnly` | comfy-core | `lora_name` (COMBO), `strength_model` (FLOAT) | `model` |
| `WanVideoLoraSelect` | wanvideo_wrapper custom | model-specific | domain-specific |

The canonical pattern (from `qwen_image_2512` precedent): a `LoraLoaderModelOnly` node takes a `model` input from the UNETLoader, a `lora_name` widget, and `strength_model`, then passes the patched model downstream to the sampler. For two-pass workflows, the LoRA loader typically sits between the model loader and the first sampler; sometimes both branches share one LoRA loader.

---

## 6. Recommendation

**True absence — skip is appropriate.** If a FLUX2 t2i workflow with LoRA is desired as an additive case, either:

1. Create a new ready_template `image/flux2_klein_4b_t2i_lora` (wrap the existing t2i with a `LoraLoaderModelOnly` node between UNETLoader and downstream).
2. Re-pair case 7 with `image/qwen_image_2512` → `lora_loader`, which has a proven LoRA loader node and is also in the image domain.
3. Or retire the case-7 slot and redistribute the 10 additive cases to only workflows that contain the target feature.
