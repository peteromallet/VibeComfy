# Case 02 — ControlNet (SKIPPED): `video/ltx2_3_lightricks_iclora_union_control`

**TL;DR:** False skip — the golden DOES contain a functional controlnet pipeline (CannyEdgePreprocessor → ICLoRA Loader → ICLoRA Guide with a `union-control` LoRA), but the matcher misses it because the LTXVideo ecosystem uses ICLoRA node names that don't contain the substring `"control"`. **Root cause: PAIRING failure** — a workflow built around Lightricks IC-LoRA (Image-Conditioned LoRA with "union control") was paired with the `"controlnet"` feature tag. No standard ControlNet node types exist here, so the keyword matcher and category checker both come up empty. Additionally, a **SEARCH/INFRA secondary issue**: `CannyEdgePreprocessor` has category `"ControlNet Preprocessors/Line Extractors"` (would match `"controlnet"` substring) but it's absent from the object_info index, so its category is never consulted.

---

## 1. False-skip check — does the golden actually perform "controlnet"?

**YES.** The workflow at `ready_templates/video/ltx2_3_lightricks_iclora_union_control` implements a control-conditioned video generation pipeline. The conditioning is driven by an ICLoRA (Image-Conditioned LoRA) named `ltx-2.3-22b-ic-lora-union-control-ref0.5.safetensors`. The pipeline is:

1. **`CannyEdgePreprocessor`** (n18) — edge-detection preprocessor from `comfyui_controlnet_aux`. Generates the structural guide image.
2. **`LTXICLoRALoaderModelOnly`** (n15) — loads the `union-control` ICLoRA onto the diffusion model.
3. **`LTXAddVideoICLoRAGuide`** (n25) — applies the ICLoRA conditioning (the structural control signal) into the latent pipeline.

This is a genuine controlnet-equivalent mechanism. The term "union control" in the LoRA name makes the intent explicit.

## 2. Every node type — judgment

| Node Type | Contains `"control"`? | Category | In index? | Category matches? |
|---|---|---|---|---|
| CannyEdgePreprocessor | ❌ | ControlNet Preprocessors/Line Extractors | ❌ (stub file exists, not indexed) | Would match `"controlnet"` if indexed |
| LTXICLoRALoaderModelOnly | ❌ | Lightricks/IC-LoRA | ✅ | ❌ |
| LTXAddVideoICLoRAGuide | ❌ | Lightricks/IC-LoRA | ✅ | ❌ |
| All other nodes | ❌ | various | ✅/❌ | ❌ |

**Result: 0 nodes matched → `skipped_no_feature_node`.**

## 3. Why the matcher failed (`_node_matches_feature`)

The controlnet rules (`_FEATURE_RULES["controlnet"]`) are:

```python
{
    "categories": ["conditioning/controlnet", "controlnet"],
    "keywords": ["controlnet", "control", "applycontrolnet", "controlapply"],
}
```

For **CannyEdgePreprocessor**: keyword check `"control" in "cannyedgepreprocessor"` → ❌. Category check: `get_class("CannyEdgePreprocessor")` returns `None` because the class is **not in `index.json`** (the stub file `comfyui_controlnet_aux@stub.json` exists on disk but isn't registered in the index). So the category `"ControlNet Preprocessors/Line Extractors"` is never read.

For **LTXICLoRALoaderModelOnly**: keyword check `"control" in "ltxicloraloadermodelonly"` → ❌ (ICLoRA ≠ control as a substring). Category `"Lightricks/IC-LoRA"` → `"controlnet" not in "lightricks/ic-lora"` → ❌.

For **LTXAddVideoICLoRAGuide**: same analysis — no keyword match, category `"Lightricks/IC-LoRA"` doesn't contain `"controlnet"` or `"control"`.

## 4. Reference templates that DO match controlnet

Two reference workflows in `ready_templates/` contain proper ControlNet nodes:

- **`video/wanvideo_wrapper_22_5b_i2v_controlnet`** — uses `WanVideoControlnet` + `WanVideoControlnetLoader` (type names contain `"controlnet"` → keyword match ✅)
- **`video/wanvideo_wrapper_22_5b_t2v_controlnet`** — same pattern

These demonstrate what a canonical controlnet node looks like: `class_type` containing `"Controlnet"`/`"ControlNet"` (PascalCase), with a `"control_net"`/`"control_images"` input.

## 5. What a correct "controlnet" node looks like

A standard ComfyUI ControlNet node has:
- **class_type**: contains `"ControlNet"` (e.g., `ControlNetLoader`, `ControlNetApply`, `WanVideoControlnet`)
- **Key widgets/inputs**: `"control_net"` (the loaded controlnet model), `"strength"`, `"image"` (the preprocessor output)
- **Category**: typically `"conditioning/controlnet"` or similar

The LTXVideo ICLoRA nodes use different patterns but serve the same function:
- `LTXICLoRALoaderModelOnly` → analog to `ControlNetLoader`
- `LTXAddVideoICLoRAGuide` → analog to `ControlNetApply`
- `CannyEdgePreprocessor` → the preprocessor (same as standard ComfyUI)

## 6. Root cause: PAIRING failure (with SEARCH/INFRA secondary)

**Primary — PAIRING:** The workflow `video/ltx2_3_lightricks_iclora_union_control` was designed for Lightricks' IC-LoRA mechanism, not standard ComfyUI ControlNet. The campaign paired it with `feature_type="controlnet"`, but the node lexicon is entirely different (ICLoRA loader/guide vs. ControlNet loader/apply). The keywords `["controlnet", "control", "applycontrolnet", "controlapply"]` don't match `"LTXICLoRALoaderModelOnly"` or `"LTXAddVideoICLoRAGuide"`.

**Secondary — SEARCH/INFRA:** Even if the PAIRING were correct for the ICLoRA pipeline, the `CannyEdgePreprocessor` node (which DOES have a `"ControlNet Preprocessors/..."` category) is invisible to `get_class()` because its pack `comfyui_controlnet_aux` is not listed in `index.json`. The stub file exists at `porting/cache/object_info/comfyui_controlnet_aux@stub.json` but was never added to the index. This is an infrastructure gap.

### Recommended fixes

1. **PAIRING fix:** Either (a) re-pair this workflow with a new `feature_type="iclora"` and matching keywords `["iclora", "ic-lora", "ic_lora"]`, or (b) add `"iclora"` and `"ic-lora"` to the `controlnet` keywords since ICLoRA is an LTXVideo-specific control mechanism.

2. **INFRA fix:** Register `comfyui_controlnet_aux@stub.json` in `index.json` so `CannyEdgePreprocessor`'s category `"ControlNet Preprocessors/Line Extractors"` is resolvable. This alone would make the matcher detect it via the `"controlnet"` category substring match.

3. **Alternative workflow:** Swap to `video/wanvideo_wrapper_22_5b_i2v_controlnet` as the controlnet test case — it uses standard ControlNet node types that the matcher can find.
