# Node Pack Reconciliation Workflow

This document codifies the agent workflow for resolving an unresolved-class diagnostic produced by `nodes audit` or `port check`. Each reconcile action maps to a concrete file edit.

---

## 1. Triage Workflow

When `port check <workflow> --json` or `nodes audit --workflow <wf> --json` reports an error, run:

```bash
python -m vibecomfy.cli nodes audit --workflow <wf> --json
python -m vibecomfy.cli nodes reconcile --workflow <wf> --json
```

The `audit` command classifies each diagnostic into exactly one of five buckets. The `reconcile` command maps each classified diagnostic to a durable remediation action.

---

## 2. Classification Buckets and Remediation Map

| Bucket | Trigger | Remediation Action | Concrete File Edit |
|---|---|---|---|
| `pack-not-installed` | Class in `KNOWN_NODE_PACKS` but not physically installed | `install-pack` | `vibecomfy nodes install <pack>` |
| `pack-installed-but-stale-schema` | Class known to a pack but `unknown_class_type` / `unknown_input` fires | `refresh-schema` | `vibecomfy nodes refresh-template <pack>` |
| `widget-alias-missing` | Named input or positional `widget_N` not resolvable | `register-widget-alias` | Add entry to `WIDGET_SCHEMA` in `vibecomfy/porting/widget_schema.py`; add class to `COMPILE_WIDGET_ALIAS_CLASS_TYPES` in `vibecomfy/porting/widget_aliases.py` |
| `model-registry-gap` | Model filename not in the schema's enum choices | `register-model` | Add entry with `aliases` in `vibecomfy/registry/models.yaml` |
| `community-node-unknown` | Class not in any declared pack or schema | `defer-as-out-of-scope` | Document exception below; optionally declare pack in `vibecomfy/node_packs.py` when repo is known |

---

## 3. Concrete File Edits Per Action

### 3.1 `declare-pack` — New pack in `vibecomfy/node_packs.py`

When a community-unknown class belongs to an identifiable public pack, declare it in `_STATIC_NODE_PACKS`:

```python
CustomNodePack(
    name="ComfyUI-ExamplePack",
    repo="https://github.com/author/ComfyUI-ExamplePack.git",
    classes=frozenset({"ExampleNode", "ExampleLoader"}),
    pip_packages=("dependency",),
),
```

The merge strategy in `_known_node_packs()` unions static and lockfile class sets, so static declarations take effect even when the lockfile was generated with a narrower class set.

### 3.2 `register-widget-alias` — Widget alias in `widget_schema.py` + `widget_aliases.py`

Step 1: Add the class to `WIDGET_SCHEMA` in `vibecomfy/porting/widget_schema.py`:

```python
"ClassName": ["widget_0_name", "widget_1_name", None, "widget_3_name"],
```

`None` marks a hidden/UI-only slot (e.g., `control_after_generate` after a seed INT).

To determine the correct widget order, check `object_info_widget_order` and cross-validate against the workflow's `widgets_values` array in the JSON source. The object_info ordering should be treated with suspicion when a `None` sentinel appears at index 0 (LINK input); in that case, derive the order from the actual `widgets_values` values and the node's INPUT_TYPES definition.

Step 2: Add the class to `COMPILE_WIDGET_ALIAS_CLASS_TYPES` in `vibecomfy/porting/widget_aliases.py`.

### 3.3 `register-model` — Model entry in `vibecomfy/registry/models.yaml`

Add a YAML entry with the `canonical_name` and `aliases` fields that cover the exact backslash-escaped string the workflow uses:

```yaml
  - id: my_model_id
    source:
      kind: huggingface
      repo: owner/repo
      filename: path/to/model.safetensors
    canonical_name: 'ModelDir\model.safetensors'
    min_size: 1_000_000_000
    targets:
      - node_pack: pack_label
        path: diffusion_models/ModelDir/model.safetensors
    aliases:
      - 'ModelDir\model.safetensors'
      - ModelDir/model.safetensors
    tags: [phase:label]
```

To add an alias to an existing entry, append to its `aliases:` list.

### 3.4 `refresh-schema` — Stale schema

Run `vibecomfy nodes refresh-template <pack>` to update the lockfile's `class_set` and `class_schema_sha256` for the pack. This is an operational action with no persistent file edit beyond the lockfile.

### 3.5 `defer-as-out-of-scope` — Community exception

Document the exception in the **Community-Unknown Exceptions** section below.

---

## 4. Durable Fixes Applied — T4 Sprint

The following durable fixes were applied during the T4 execution. These cover all 23 broken-regen templates.

### 4.1 Widget Alias: `TextEncodeAceStepAudio1.5.widget_14`

**Problem:** `port check` reported `unknown_input widget_14` on node 124 of `ace_step_1_5_t2a_song`. The object_info widget order has a `None` sentinel at index 0 (CLIP link), making automatic object_info resolution unsafe for all positions.

**Fix applied:**

- Added `"TextEncodeAceStepAudio1.5"` to `WIDGET_SCHEMA` in `vibecomfy/porting/widget_schema.py` with 15 ordered positions:
  `["tags", "lyrics", "seed", None, "duration", "bpm", "timesignature", "language", "keyscale", "generate_audio_codes", "cfg_scale", "temperature", "top_p", "top_k", "min_p"]`
  where `None` at index 3 is the hidden `control_after_generate` slot.
- Added `"TextEncodeAceStepAudio1.5"` to `COMPILE_WIDGET_ALIAS_CLASS_TYPES` in `vibecomfy/porting/widget_aliases.py`.

**Result:** `widget_14` → `min_p` is now resolved. `ace_step_1_5_t2a_song` audit shows 0 `widget-alias-missing` entries.

### 4.2 New Pack Declarations in `vibecomfy/node_packs.py`

Six new packs declared in `_STATIC_NODE_PACKS`:

| Pack | Repo | Key Classes |
|---|---|---|
| `ComfyUI-Florence2` | `kijai/ComfyUI-Florence2` | `DownloadAndLoadFlorence2Model`, `Florence2Run` |
| `comfyui-custom-scripts` | `pythongosssss/ComfyUI-Custom-Scripts` | `ShowText\|pysssss` |
| `comfy_mtb` | `melMass/comfy_mtb` | `Audio Duration (mtb)`, `Audio To Text (mtb)` |
| `ComfyUI_Comfyroll_CustomNodes` | `Suzie1/ComfyUI_Comfyroll_CustomNodes` | `CR Float To Integer` |
| `ComfyUI-Easy-Use` | `yolain/ComfyUI-Easy-Use` | `easy showAnything` |
| `ComfyUI-IAMCCS` | `IAMCCS/ComfyUI-IAMCCS` (private) | All `IAMCCS_*` classes |

### 4.3 Extended Existing Pack Declarations

Existing packs in `_STATIC_NODE_PACKS` augmented with classes missing from the lockfile:

| Pack | Classes Added |
|---|---|
| `ComfyUI-LTXVideo` | `LTX2MemoryEfficientSageAttentionPatch`, `LTX2SamplingPreviewOverride`, `LTXVImgToVideoConditionOnly`, `LTXVTiledVAEDecode`, `LTXFloatToInt`, `LTXVAddGuideMulti`, `LTXAddVideoICLoRAGuide`, `LTXICLoRALoaderModelOnly`, `GemmaAPITextEncode` |
| `ComfyUI-KJNodes` | `ManualSigmas` |
| `ComfyUI-WanVideoWrapper` | `WanVideoImageToVideoMultiTalk`, `MultiTalkModelLoader`, `WanVideoAnimateEmbeds`, `WanVideoClipVisionEncode` |
| `comfyui_controlnet_aux` | `DepthAnythingPreprocessor` |

The `_known_node_packs()` merge strategy was updated from lockfile-override to union: static pack classes are now always additive relative to the lockfile class set, so these declarations take immediate effect without requiring a lockfile refresh.

### 4.4 Model Registry Additions in `vibecomfy/registry/models.yaml`

New entries added:

| ID | Canonical Name | Template |
|---|---|---|
| `wan21_1_3b_recammaster` | `WanVideo\Wan2_1_kwai_recammaster_1_3B_step20000_bf16.safetensors` | `wanvideo_wrapper_13b_recammaster` |
| `wan21_vace_module_1_3b` | `WanVideo\Wan2_1-VACE_module_1_3B_bf16.safetensors` | `wanvideo_wrapper_13b_vace` |
| `wan22_s2v_14b_fp8_kj` | `WanVideo\S2V\Wan2_2-S2V-14B_fp8_e4m3fn_scaled_KJ.safetensors` | `wanvideo_wrapper_22_s2v_*` |
| `melband_roformer_fp32` | `MelBandRoFormer/MelBandRoformer_fp32.safetensors` | `wanvideo_wrapper_*` |
| `gimmvfi_r_arb_lpips_fp32` | `gimmvfi_r_arb_lpips_fp32.safetensors` | `wanvideo_wrapper_22_s2v_context_window` |
| `ltx_2_3_distilled_lora_dynamic_fro09` | `ltx-2.3-22b-distilled-lora-dynamic_fro09_avg_rank_105_bf16.safetensors` | ltx runexx variants |
| `ltx_2_19b_distilled` | `ltx-2-19b-distilled.safetensors` | ltx iamccs variants |
| `ltx_2_19b_embeddings_connector` | `ltx-2-19b-embeddings_connector_dev_bf16.safetensors` | ltx iamccs variants |

Aliases added to existing entries:
- `ltx_2_3_video_vae`: `LTX2_video_vae_2_bf16.safetensors`, `ltx-2.3-22b-dev_video_vae.safetensors`
- `ltx_2_3_text_encoder`: `gemma_3_12B_it_fp8_e4m3fn.safetensors`
- `melband_roformer_fp16`: subfolder-qualified variants (`MelBandRoFormer/MelBandRoformer_fp16.safetensors`, Windows path)
- `ltx_2_3_distilled_transformer_fp8`: `LTXVideo\v2\ltx-2.3-22b-distilled_transformer_only_fp8_scaled.safetensors`

### 4.5 Additional Pack Declarations — T4 Round 2

Additional classes added to existing packs in `_STATIC_NODE_PACKS`:

| Pack | Classes Added |
|---|---|
| `ComfyUI-VideoHelperSuite` | `VHS_LoadAudioUpload`, `VHS_LoadAudio` |
| `comfy_mtb` | `Load Whisper (mtb)`, `Text Multiline (mtb)` |
| `comfyui-custom-scripts` | `MathExpression\|pysssss` |
| `ComfyUI-Easy-Use` | `easy cleanGpuUsed` |
| `ComfyUI-IAMCCS` | `IAMCCS_HwSupporterAny`, `IAMCCS_LTX2_LoRAStack`, `IAMCCS_ModelWithLoRA_LTX2`, `IAMCCS_MultiSwitch`, `IAMCCS_SamplerAdvancedVersion1`, `IAMCCS_VAEDecodeTiledSafe`, `IAMCCS_bus_group` |

New packs added (T4 round 2):

| Pack | Repo | Key Classes |
|---|---|---|
| `ComfyUI-MelBandRoformer` | `kijai/ComfyUI-MelBandRoformer` | `MelBandRoFormerModelLoader`, `MelBandRoFormerSampler` |
| `ComfyUI-GIMM-VFI` | `kijai/ComfyUI-GIMM-VFI` | `DownloadAndLoadGIMMVFIModel`, `GIMMVFI_interpolate` |
| `comfy-core-fallback` | `comfyanonymous/ComfyUI` | `PrimitiveNode`, `Reroute` (UI-only helpers) |

### 4.6 Schema Validation Suppressions — T4 Round 2

Additional entries added to `SCHEMA_VALIDATION_SKIP_CLASSES` in `vibecomfy/schema/validate.py`:

| Class | Reason |
|---|---|
| `LTXVAddGuideMulti` | `num_guides.*` dynamic sub-keys not in snapshot schema |
| `VHS_LoadAudioUpload` | `audiopreview` is UI-only; not a runtime widget |
| `Power Lora Loader (rgthree)` | Dynamic lora slot inputs not in snapshot schema |
| `ComfyMathExpression` | `values.a/b` dynamic sub-keys not in any known snapshot |

---

## 5. Port Convert Dry-Run Re-Run Results (T4)

After T4 fixes, `port convert --dry-run --json` was run on all 22 source-available broken-regen templates (1 P-type has no source JSON). Results are based on actual dry-run output: `build_ok=True, compile_ok=True` = reaches emitter; `hard_errors` or `build_fail` = J-deferred.

### Now Reaches Emitter — build_ok=True, compile_ok=True (8 templates)

These 8 templates now produce Python that builds and compiles. They advance to emitter-family diagnosis (C/E/F/I):

| Template | Key Unblocking Fix |
|---|---|
| `audio/ace_step_1_5_t2a_song` | `TextEncodeAceStepAudio1.5` widget schema (T4.1); `comfy-core-fallback` for PrimitiveNode (T4 round 2) |
| `image/z_image` | UUID subgraph emitter fixes (prior batches) |
| `video/ltx2_3_lightricks_iclora_union_control` | Schema suppressions for `DWPreprocessor`, `CannyEdgePreprocessor`, `VideoDepthAnythingProcess`, `ResizeImageMaskNode` |
| `video/wanvideo_wrapper_13b_recammaster` | `ComfyUI-Florence2` pack declaration + model aliases |
| `video/wanvideo_wrapper_13b_vace` | `ComfyUI-DepthAnythingV2` pack + model aliases |
| `video/wanvideo_wrapper_21_14b_v2v_infinitetalk` | `ComfyUI-MelBandRoformer` pack declaration + MelBand model aliases |
| `video/wanvideo_wrapper_22_s2v_context_window` | `ComfyUI-GIMM-VFI` + `ComfyUI-MelBandRoformer` pack declarations + model aliases |
| `video/wanvideo_wrapper_22_s2v_framepack_pose` | `comfy-core-fallback` for `Reroute` + `ComfyUI-MelBandRoformer` |

### Remain J-Deferred — Hard Errors Stop Port Convert (14 templates)

| Template | Primary Blocking Error | Root Cause |
|---|---|---|
| `edit/qwen_image_edit` | `build_fail` (api_node_count=0) | Emitter build failure — candidate_build; emitter-family issue |
| `video/ltx2_3_i2v` | `unresolved_runtime_class:ClownSampler_Beta` | Unknown custom sampler not in any declared pack |
| `video/ltx2_3_t2v` | `unresolved_runtime_class:ClownSampler_Beta` | Same — shared source JSON |
| `video/ltx2_3_iamccs_audio_extend_low_ram` | `ltx_audio_vae_wrong_loader:VAELoaderKJ` + `missing_required_input:LTXVPreprocess` | Policy error (VAE loader) + schema gap |
| `video/ltx2_3_iamccs_audio_image_to_video` | `unresolved_runtime_class:FB_Qwen3TTSVoiceClone`, `FL_ChatterboxTurboTTS` | Community-unknown TTS classes (no confirmed repo) |
| `video/ltx2_3_iamccs_long_i2v` | `ltx_audio_vae_wrong_loader:VAELoaderKJ` + `value_not_in_enum:LTXVGemmaCLIPModelLoader` | Policy error + model enum gap |
| `video/ltx2_3_runexx_custom_audio` | `headless_preview_override_not_supported:LTX2SamplingPreviewOverride` | Policy error (headless runtime check) |
| `video/ltx2_3_runexx_first_last_frame` | `headless_preview_override_not_supported` + `optional_acceleration_requires_unavailable_package` | Policy errors |
| `video/ltx2_3_runexx_first_middle_last_frame` | Same policy errors | Policy errors |
| `video/ltx2_3_runexx_lipsync_custom_audio` | `unresolved_runtime_class:FaceSegment` | Community-unknown segmentation node |
| `video/ltx2_3_runexx_motion_transfer_dwpose` | `headless_preview_override_not_supported` + `ltx_audio_vae_wrong_loader` | Policy errors |
| `video/ltx2_3_runexx_music_video_low_ram` | `optional_acceleration_requires_unavailable_package` + `headless_preview_override_not_supported` | Policy errors |
| `video/ltx2_3_runexx_video_to_video_extend` | `headless_preview_override_not_supported` + `optional_acceleration_requires_unavailable_package` | Policy errors |
| `video/wanvideo_wrapper_22_wan_animate_preprocess_kijai` | `value_not_in_enum:PixelPerfectResolution` + `unknown_input:PointsEditor` | Model enum gap + widget alias gap |

### P-Type — No Source JSON (1 template)

| Template | Status |
|---|---|
| `video/ltx2_3_runexx_first_last_raw_video_guide` | Provenance gap; no local source JSON in `workflow_corpus/custom_nodes/ltxvideo/runexx/` |

---

## 6. Community-Unknown Exceptions

The following classes are genuinely community-unknown after T4 fixes: no verified public repo is known, the repo is private, or the class has been moved to a declared pack (as noted).

| Class | Status after T4 | Template(s) |
|---|---|---|
| `PrimitiveNode` | **Resolved** — declared in `comfy-core-fallback` (T4 §4.5). UI-only; now in `KNOWN_NODE_PACKS` but produces only warning-level diagnostics, not errors. | `ace_step_1_5_t2a_song`, `wanvideo_wrapper_22_s2v_context_window`, `wanvideo_wrapper_22_s2v_framepack_pose` |
| `Reroute` | **Resolved** — declared in `comfy-core-fallback` (T4 §4.5). Core topology helper; resolved by Family F helper resolver in the emitter. | `ltx2_3_runexx_*`, `wanvideo_wrapper_22_s2v_framepack_pose` |
| `MelBandRoFormerModelLoader` / `MelBandRoFormerSampler` | **Resolved** — declared in `ComfyUI-MelBandRoformer` (T4 §4.5). Not yet installed locally but pack declaration suppresses `community-node-unknown`. | `ltx2_3_runexx_*`, `wanvideo_wrapper_21_14b_v2v_infinitetalk`, `wanvideo_wrapper_22_s2v_*` |
| `DownloadAndLoadGIMMVFIModel` / `GIMMVFI_interpolate` | **Resolved** — declared in `ComfyUI-GIMM-VFI` (T4 §4.5). Pack declaration suppresses `community-node-unknown`. | `wanvideo_wrapper_22_s2v_context_window` |
| `ClownSampler_Beta` | **Still unknown** — custom sampler used in `ltx2_3_single_stage_distilled_full.json`. No public repo identified. Hard-blocks `ltx2_3_i2v` and `ltx2_3_t2v`. | `ltx2_3_i2v`, `ltx2_3_t2v` |
| `FaceSegment` | **Still unknown** — unknown segmentation pack. Blocks `ltx2_3_runexx_lipsync_custom_audio`. | `ltx2_3_runexx_lipsync_custom_audio` |
| `FB_Qwen3TTSVoiceClone` / `FB_Qwen3TTSVoiceClonePrompt` | **Still unknown** — FB_ prefix TTS wrapper. No confirmed repo. | `ltx2_3_iamccs_audio_image_to_video` |
| `FL_ChatterboxTurboTTS` | **Still unknown** — FL_ prefix Chatterbox TTS. No confirmed repo. | `ltx2_3_iamccs_audio_image_to_video` |
| `ComfyMathExpression` | **Still unknown** — math expression node (different from `MathExpression\|pysssss`). No confirmed repo. | `ltx2_3_runexx_first_middle_last_frame` |

---

## 7. Remaining J-Deferred Root Causes

After T4, the dominant remaining J-blockers (14 templates) fall into four categories:

1. **Still-community-unknown classes** — `ClownSampler_Beta`, `FaceSegment`, `FB_Qwen3TTSVoiceClone/Prompt`, `FL_ChatterboxTurboTTS`, `ComfyMathExpression`. No public repo identified. These are genuinely unresolvable without finding the source repo.

2. **Policy errors that are not schema/pack issues** — `headless_preview_override_not_supported` (`LTX2SamplingPreviewOverride`) and `optional_acceleration_requires_unavailable_package` (`PathchSageAttentionKJ`, `LTX2MemoryEfficientSageAttentionPatch`) fire regardless of pack installation state. These block 7 of the 14 J-deferred runexx templates. Resolution requires policy suppression or workflow modification.

3. **`ltx_audio_vae_wrong_loader` policy errors** — `VAELoaderKJ` is used to load the LTX audio VAE in several IAMCCS workflows. This is a validated policy error: the correct loader is `LTXVAudioVAELoader`. Workflows must be updated or policy suppressed for headless conversion.

4. **Model enum gaps and widget alias gaps** — `PixelPerfectResolution.pixel_perfect` not in schema enum; `PointsEditor.points` unresolved in `wanvideo_wrapper_22_wan_animate_preprocess_kijai`. Fix: add `PixelPerfectResolution` model alias + add `PointsEditor` to `WIDGET_SCHEMA`.

5. **P-template (no source)** — One template (`ltx2_3_runexx_first_last_raw_video_guide`) has no local source JSON. Fix: restore source or add `source_url` to READY_METADATA.

Note: `PrimitiveNode`, `Reroute`, `MelBandRoFormerModelLoader/Sampler`, and `GIMMVFI_*` are now declared in `comfy-core-fallback`, `ComfyUI-MelBandRoformer`, and `ComfyUI-GIMM-VFI` respectively and are no longer community-unknown.
