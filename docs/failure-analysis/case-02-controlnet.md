# Case 02: ControlNet — video/ltx2_3_lightricks_iclora_union_control

**Verdict:** `skipped_no_feature_node`  
**Root classification:** TRUE ABSENCE (not a matcher miss)  
**TL;DR:** The golden workflow uses Lightricks' proprietary **ICLoRA union control** mechanism, not a standard ControlNet node. No conventional `ControlNetApply`/`ControlNetLoader` or category-tagged controlnet node exists. The matcher correctly returned `[]`. Best re-pair candidate: `video/wanvideo_wrapper_22_5b_i2v_controlnet`.

---

## 1. False-Skip Check — Every Node in the Golden

The layout JSON and auto-generated `.py` recipe expose these class types:

| Node | Class Type | Matches `controlnet` rules? |
|---|---|---|
| n14 | `LTXVConditioning` | No |
| n1 | `LoadImage` | No |
| n9, n10 | `CLIPTextEncode` | No |
| n22 | `EmptyLTXVLatentVideo` | No |
| n24 | `LTXVImgToVideoConditionOnly` | No |
| n2 | `CheckpointLoaderSimple` | No |
| n23 | `LTXVEmptyLatentAudio` | No |
| n3 | `LTXVAudioVAELoader` | No |
| n26 | `LTXVConcatAVLatent` | No |
| n27 | `CFGGuider` | No |
| n28 | `SamplerCustomAdvanced` | No |
| n4 | `KSamplerSelect` | No |
| n5 | `RandomNoise` | No |
| n29 | `LTXVSeparateAVLatent` | No |
| n30 | `LTXVAudioVAEDecode` | No |
| n33 | `CreateVideo` | No |
| n34 | `SaveVideo` | No |
| n11 | `LoraLoaderModelOnly` | No |
| **n18** | **`CannyEdgePreprocessor`** | **No** ⚠️ |
| n12 | `GetVideoComponents` | No |
| n6 | `LoadVideo` | No |
| n15 | `LTXICLoRALoaderModelOnly` | No |
| n25 | `LTXAddVideoICLoRAGuide` | No |
| n31 | `LTXVCropGuides` | No |
| n7 | `LTXAVTextEncoderLoader` | No |
| n8 | `ManualSigmas` | No |
| n16, n20, n13 | `ResizeImageMaskNode` | No |
| n21 | `GetImageSize` | No |
| n19 | `SimpleMath+` | No |
| n17 | `LTXFloatToInt` | No |
| n32 | `LTXVTiledVAEDecode` | No |

**CannyEdgePreprocessor** (n18) is the closest-looking node, but the matcher's keyword list is `["controlnet", "control", "applycontrolnet", "controlapply"]` — none of which appear in `"cannyedgepreprocessor"`. Even if `get_class()` returned a category like `"controlnet preprocessors"` (which does contain `"controlnet"` as a substring), this is a *preprocessor*, not the controlnet *application node* that applies a control model to condition the latents. The true control function in this workflow is the **ICLoRA union control** pipeline (`LTXICLoRALoaderModelOnly` → `LTXAddVideoICLoRAGuide`), which is an LTX-specific approach with no conventional ControlNet node.

**Bottom line:** This is NOT a false-skip. The matcher is correct.

## 2. Valid Re-Pairing Candidates in ready_templates/

Two workflows contain proper controlnet nodes:

| Workflow | Controlnet Class(es) | Notes |
|---|---|---|
| `video/wanvideo_wrapper_22_5b_t2v_controlnet` | `WanVideoControlnet`, `WanVideoControlnetLoader` | Text-to-video with depth controlnet |
| `video/wanvideo_wrapper_22_5b_i2v_controlnet` | `WanVideoControlnet`, `WanVideoControlnetLoader` | Image-to-video; closest domain match to the LTX case (both are video workflows that condition on a control image) |

**Recommendation:** Re-pair to `video/wanvideo_wrapper_22_5b_i2v_controlnet` — it's the same modality (video I2V) and uses a genuine `WanVideoControlnet` + `WanVideoControlnetLoader` pair that the matcher will find and the fixer can restore.

## 3. What a Correct "ControlNet" Node Looks Like

Per `_FEATURE_RULES`, controlnet nodes are identified by:

- **Keywords:** `controlnet`, `control`, `applycontrolnet`, `controlapply`
- **Categories:** `conditioning/controlnet`, `controlnet`

In standard ComfyUI: `ControlNetLoader` (loads `.safetensors` control models), `ControlNetApply` (applies control to conditioning).  
In WanVideo wrapper: `WanVideoControlnet` + `WanVideoControlnetLoader`.  
In the corpus/hivemind semantics: `hivemind_workflow_semantics.py` maps `"controlnet"` → `("controlnet", "control net")`.

## 4. Process Break Analysis

The break occurs at **PAIRING** — but it's not a matcher defect. The campaign definition (run_campaign.py line 61) pairs `controlnet` with a workflow that uses Lightricks' proprietary ICLoRA union control rather than a standard ControlNet. The golden simply does not contain a node of the feature type requested. For the re-paired case (`wanvideo_wrapper_22_5b_i2v_controlnet`), we would next assess whether SEARCH/REFERENCE/FIXER succeeds.
