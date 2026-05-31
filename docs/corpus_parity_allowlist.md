# Corpus Compatibility Audit and Parity Gate Allowlist

**Date:** 2026-05-26  
**Milestone:** M1 — Foundation (T12), updated 2026-05-31 for S2 dynamic-widget fence taxonomy  
**Purpose:** Classify every `ready_templates/**/*.py` (64 files) and `workflow_corpus/**/*.json` (16 files) by their compatibility with the M1 offline parity gate (`offline_emitter_normalizer_self_consistency_check`). Produce the documented allowlist of entries the gate is permitted to skip, with per-entry reasons. All 80 entries are enumerated.

---

## Classification buckets

| Bucket | Description |
|---|---|
| `clean` | `emit_ui_json` succeeds; `offline_emitter_normalizer_self_consistency_check` returns `(True, [])`. Gate runs and passes. |
| `subgraph_uuid` | Contains one or more UUID-typed opaque subgraph nodes. Gate runs and passes — UUID class types emit as-is and parity holds offline. |
| `control_after_generate_default` | No schema-less nodes; CAG value absent from IR metadata (Python-authored or not captured at ingest) — emitter defaults to `fixed` and flags it, but CAG is UI-only so it does not enter `compile('api')`. Gate runs and passes. |
| `schema_less` | One or more nodes have no schema entry in `widget_schema.py` or the object-info cache. Best-effort emission; parity may fail. |
| `widget_shape_fence` | A dynamic or otherwise opaque widget surface has more raw/candidate `widgets_values` than schema-derived regeneration can prove. The S2 fence accepts only typed pin/refusal outcomes. |
| `not_a_workflow` | File is not a workflow; `workflow_from_file` raises "Unsupported workflow shape". |

---

## Summary

| Bucket | Ready templates | Corpus JSONs | Total | On allowlist |
|---|---|---|---|---|
| `clean` | 12 | 13 | 25 | No — gate passes |
| `subgraph_uuid` | — | — | — | No — gate passes (see §Gate-passable bucket notes) |
| `control_after_generate_default` | — | — | — | No — gate passes |
| `schema_less` | 32 | 1 | 33 | Yes — parity unreliable |
| `widget_shape_fence` | 10 | 0 | 10 | Yes — dynamic widgets pin or refuse before unsafe regeneration |
| `not_a_workflow` | 0 | 2 | 2 | Yes — not a workflow |
| **Total** | **64** | **16** | **80** | **45** |

### Gate-passable bucket notes

After running the full corpus:

- All `subgraph_uuid` entries that successfully emit have `parity=(True, [])`. The UUID type is treated as opaque and passes through the gate without issue. **Not on allowlist.**
- All `control_after_generate_default` entries that successfully emit have `parity=(True, [])`. CAG is UI-only and does not affect `compile('api')` output. **Not on allowlist.**

---

## Entries NOT on allowlist (gate runs and passes)

These 25 entries use the parity gate without a skip.

### Ready templates — gate passes

| Path | Bucket | Notes |
|---|---|---|
| `ready_templates/edit/flux2_klein_4b_image_edit_base.py` | `subgraph_uuid` | UUID nodes emit as-is; parity True |
| `ready_templates/edit/flux2_klein_4b_image_edit_distilled.py` | `schema_less` | ReferenceLatent/ConditioningZeroOut schema-less but parity True |
| `ready_templates/edit/flux2_klein_9b_image_edit_base.py` | `subgraph_uuid` | UUID nodes emit as-is; parity True |
| `ready_templates/edit/flux2_klein_9b_image_edit_distilled.py` | `subgraph_uuid` | UUID nodes emit as-is; parity True |
| `ready_templates/image/basic_image_upscale.py` | `control_after_generate_default` | CAG defaulted; UI-only; parity True |
| `ready_templates/image/flux2_klein_4b_t2i.py` | `control_after_generate_default` | CAG defaulted; UI-only; parity True |
| `ready_templates/image/flux2_klein_9b_gguf_t2i.py` | `control_after_generate_default` | CAG defaulted; UI-only; parity True |
| `ready_templates/image/flux2_klein_9b_t2i.py` | `subgraph_uuid` | UUID nodes emit as-is; parity True |
| `ready_templates/image/qwen_image_2512.py` | `schema_less` | ComfySwitchNode schema-less but parity True for Python IR |
| `ready_templates/image/z_image.py` | `control_after_generate_default` | CAG defaulted; UI-only; parity True |
| `ready_templates/image/z_image_img2img.py` | `control_after_generate_default` | CAG defaulted; UI-only; parity True |
| `ready_templates/video/wan_t2v.py` | `control_after_generate_default` | CAG defaulted; UI-only; parity True |

### Corpus JSONs — gate passes

| Path | Bucket | Parity |
|---|---|---|
| `workflow_corpus/official/edit/flux2_klein_4b_image_edit_base.json` | `subgraph_uuid` | `(True, [])` |
| `workflow_corpus/official/edit/flux2_klein_4b_image_edit_distilled.json` | `subgraph_uuid` | `(True, [])` |
| `workflow_corpus/official/edit/flux2_klein_9b_image_edit_base.json` | `subgraph_uuid` | `(True, [])` |
| `workflow_corpus/official/edit/flux2_klein_9b_image_edit_distilled.json` | `subgraph_uuid` | `(True, [])` |
| `workflow_corpus/official/edit/qwen_image_edit.json` | `subgraph_uuid` | `(True, [])` |
| `workflow_corpus/official/image/flux2_klein_4b_t2i.json` | `subgraph_uuid` | `(True, [])` |
| `workflow_corpus/official/image/flux2_klein_9b_t2i.json` | `subgraph_uuid` | `(True, [])` |
| `workflow_corpus/official/image/z_image.json` | `subgraph_uuid` | `(True, [])` |
| `workflow_corpus/official/video/ltx2_3_i2v.json` | `subgraph_uuid` | `(True, [])` |
| `workflow_corpus/official/video/ltx2_3_t2v.json` | `subgraph_uuid` | `(True, [])` |
| `workflow_corpus/official/video/wan_i2v.json` | `schema_less` | `(True, [])` |
| `workflow_corpus/official/video/wan_t2v.json` | `control_after_generate_default` | `(True, [])` |
| `workflow_corpus/official/audio/ace_step_1_5_t2a_song.json` | `schema_less` | `(True, [])` |

---

## Allowlist — entries the parity gate is permitted to skip

The gate MUST be skipped for these entries. Automated test harnesses asserting `offline_emitter_normalizer_self_consistency_check` passes should exclude them using this list.

### Reason codes

| Code | Meaning |
|---|---|
| `PIN_OPAQUE_WIDGET_SHAPE` | `emit_ui_json` detected dynamic widget-shape divergence and preserved the unchanged full raw LiteGraph node payload instead of regenerating `widgets_values`. |
| `REFUSED_WIDGET_SHAPE` | `emit_ui_json` detected dynamic widget-shape divergence but could not safely pin the node, usually because no full raw UI payload exists or the widget/link surface was edited. |
| `NAMED_CAG_DIVERGENCE` | Named `control_after_generate` (or adjacent None-slot widget like `WanVideoSampler.force_offload`) survives `_normalize_ui_to_api` but is stripped by `compile('api')` via `_is_ui_only_prompt_input`. M1 offline oracle diverges from compile here; emitted UI JSON is correct for ComfyUI. |
| `SCHEMA_LESS_WIDGET` | One or more schema-less nodes have widgets the emitter cannot reconstruct; round-trip widget values diverge from `compile('api')` output. |
| `PARITY_FAIL_TOPOLOGY` | `offline_emitter_normalizer_self_consistency_check` returns `(False, [...])` with topology diffs (not just widget values); schema-less nodes cause API graph shape divergence. |
| `NOT_A_WORKFLOW` | File is not a workflow (manifest/config); `workflow_from_file` raises. |

---

### A. Manifest files (2)

| Entry | Bucket | Reason code | Per-entry reason |
|---|---|---|---|
| `workflow_corpus/manifests/coverage.json` | `not_a_workflow` | `NOT_A_WORKFLOW` | Coverage manifest, not a workflow. `workflow_from_file` raises "Unsupported workflow shape: unknown". |
| `workflow_corpus/manifests/ready_regeneration.json` | `not_a_workflow` | `NOT_A_WORKFLOW` | Regeneration manifest, not a workflow. `workflow_from_file` raises "Unsupported workflow shape: unknown". |

---

### B. Corpus JSON with confirmed parity failure (1)

| Entry | Bucket | Reason code | Parity | Per-entry reason |
|---|---|---|---|---|
| `workflow_corpus/official/image/qwen_image_2512.json` | `schema_less` | `PARITY_FAIL_TOPOLOGY` | `(False, [...])` | `ComfySwitchNode` is schema-less. On round-trip, topology diverges: `KSampler` loses its `model`, `cfg`, `latent_image`, `steps`, and conditioning connections that flow through `ComfySwitchNode`. Best-effort slot emission produces an incorrect topology; parity=False confirmed at audit time. |

---

### C. Ready templates — widget-shape fence (10)

These entries were previously classified as overflow `EMIT_ERROR`. Under the S2 dynamic-widget fence, schema-count overflow is not a schema-maintenance-only condition. It is a per-node widget-shape decision:

- unchanged full raw UI payload available: `PIN_OPAQUE_WIDGET_SHAPE`
- no full payload, widget edit, class edit, or touched link surface: `REFUSED_WIDGET_SHAPE`

The parity gate is still skipped for these entries, but a returned envelope may not contain an overflow recovery entry with `widget_shape_verdict == "safe_to_regenerate"`.

| Entry | Offending node | Schema count | Raw/candidate count | Accepted reason code(s) |
|---|---|---:|---:|---|
| `ready_templates/video/ltx2_3_iamccs_audio_extend_low_ram.py` | `ResizeImageMaskNode` | 3 | 5 | `PIN_OPAQUE_WIDGET_SHAPE` or `REFUSED_WIDGET_SHAPE` |
| `ready_templates/video/ltx2_3_lightricks_iclora_motion_track.py` | `PrimitiveInt` | 1 | 2 | `PIN_OPAQUE_WIDGET_SHAPE` or `REFUSED_WIDGET_SHAPE` |
| `ready_templates/video/ltx2_3_lightricks_two_stage.py` | `PrimitiveInt` | 1 | 2 | `PIN_OPAQUE_WIDGET_SHAPE` or `REFUSED_WIDGET_SHAPE` |
| `ready_templates/video/ltx2_3_runexx_lipsync_custom_audio.py` | `BlockifyMask` | 1 | 2 | `PIN_OPAQUE_WIDGET_SHAPE` or `REFUSED_WIDGET_SHAPE` |
| `ready_templates/video/ltx2_3_runexx_music_video_low_ram.py` | `Power Lora Loader (rgthree)` | 4 | 8 | `PIN_OPAQUE_WIDGET_SHAPE` or `REFUSED_WIDGET_SHAPE` |
| `ready_templates/video/ltx2_3_runexx_talking_avatar_qwen_tts.py` | `Power Lora Loader (rgthree)` | 4 | 5 | `PIN_OPAQUE_WIDGET_SHAPE` or `REFUSED_WIDGET_SHAPE` |
| `ready_templates/video/wanvideo_wrapper_21_14b_fun_control.py` | `LoadImage` | 2 | 3 | `PIN_OPAQUE_WIDGET_SHAPE` or `REFUSED_WIDGET_SHAPE` |
| `ready_templates/video/wanvideo_wrapper_21_14b_t2v.py` | `WanVideoSampler` | 14 | 15 | `PIN_OPAQUE_WIDGET_SHAPE` or `REFUSED_WIDGET_SHAPE` |
| `ready_templates/video/wanvideo_wrapper_21_14b_wanmove_i2v.py` | `WanVideoVAELoader` | 2 | 3 | `PIN_OPAQUE_WIDGET_SHAPE` or `REFUSED_WIDGET_SHAPE` |
| `ready_templates/video/wanvideo_wrapper_wan_animate.py` | `PointsEditor` | 9 | 10 | `PIN_OPAQUE_WIDGET_SHAPE` or `REFUSED_WIDGET_SHAPE` |

---

### D. Ready templates — named CAG divergence (10)

Root cause: `RandomNoise` carries `control_after_generate` as a **named** widget slot in `widget_schema.py` (position 1). The M1 emitter correctly includes it in `widgets_values`; `_normalize_ui_to_api` retains the named slot in the API dict. However, `compile('api')` strips it via `_is_ui_only_prompt_input` (which applies to all nodes, not just KSampler). The offline oracle diverges from `compile('api')` for this node class. The emitted UI JSON is correct for ComfyUI — the divergence exists only in the M1 offline gate.

| Entry | Offending node(s) | Diverging widget | Reason code |
|---|---|---|---|
| `ready_templates/video/ltx2_3_first_last_frame_travel_iclora_control.py` | `RandomNoise` ×2 | `control_after_generate` | `NAMED_CAG_DIVERGENCE` |
| `ready_templates/video/ltx2_3_iamccs_audio_image_to_video.py` | `RandomNoise` ×1 | `control_after_generate` | `NAMED_CAG_DIVERGENCE` |
| `ready_templates/video/ltx2_3_lightricks_iclora_hdr.py` | `RandomNoise` ×1 | `control_after_generate` | `NAMED_CAG_DIVERGENCE` |
| `ready_templates/video/ltx2_3_lightricks_iclora_union_control.py` | `RandomNoise` ×1 | `control_after_generate` | `NAMED_CAG_DIVERGENCE` |
| `ready_templates/video/ltx2_3_runexx_custom_audio.py` | `RandomNoise` ×2 | `control_after_generate` | `NAMED_CAG_DIVERGENCE` |
| `ready_templates/video/ltx2_3_runexx_first_last_frame.py` | `RandomNoise` ×2 | `control_after_generate` | `NAMED_CAG_DIVERGENCE` |
| `ready_templates/video/ltx2_3_runexx_first_last_raw_video_guide.py` | `RandomNoise` ×2 | `control_after_generate` | `NAMED_CAG_DIVERGENCE` |
| `ready_templates/video/ltx2_3_runexx_first_middle_last_frame.py` | `RandomNoise` ×2 | `control_after_generate` | `NAMED_CAG_DIVERGENCE` |
| `ready_templates/video/ltx2_3_runexx_motion_transfer_dwpose.py` | `RandomNoise` ×2 | `control_after_generate` | `NAMED_CAG_DIVERGENCE` |
| `ready_templates/video/ltx2_3_runexx_video_to_video_extend.py` | `RandomNoise` ×2 | `control_after_generate` | `NAMED_CAG_DIVERGENCE` |

---

### E. Ready templates — WanVideoSampler force_offload divergence (11)

Root cause: `WanVideoSampler` has a `None`-slot (CAG position) at index 4 in `widget_schema.py`, followed by `force_offload` at index 5. After `_schema_input_names` strips the None slot, `force_offload` occupies the compacted position 4. The M1 emitter's CAG-default reconstruction places `'fixed'` at the original None-slot position before compaction, shifting `force_offload` out of its expected slot and causing the round-trip to produce `force_offload='fixed'` (string) instead of `force_offload=True` (bool). The emitted UI JSON's widget ordering is incorrect for this node but the semantic content is partially preserved.

| Entry | Offending node | Diverging widget | Reason code |
|---|---|---|---|
| `ready_templates/video/wanvideo_wrapper_13b_control_lora.py` | `WanVideoSampler` ×1 | `force_offload` | `NAMED_CAG_DIVERGENCE` |
| `ready_templates/video/wanvideo_wrapper_13b_recammaster.py` | `WanVideoSampler` ×1 | `force_offload` | `NAMED_CAG_DIVERGENCE` |
| `ready_templates/video/wanvideo_wrapper_13b_vace.py` | `WanVideoSampler` ×3 | `force_offload` | `NAMED_CAG_DIVERGENCE` |
| `ready_templates/video/wanvideo_wrapper_21_14b_flf2v.py` | `WanVideoSampler` ×1 | `force_offload` | `NAMED_CAG_DIVERGENCE` |
| `ready_templates/video/wanvideo_wrapper_21_14b_fun_control_camera.py` | `WanVideoSampler` ×1 | `force_offload` | `NAMED_CAG_DIVERGENCE` |
| `ready_templates/video/wanvideo_wrapper_21_14b_i2v.py` | `WanVideoSampler` ×1 | `force_offload` | `NAMED_CAG_DIVERGENCE` |
| `ready_templates/video/wanvideo_wrapper_21_14b_v2v_infinitetalk.py` | `WanVideoSampler` ×1 | `force_offload` | `NAMED_CAG_DIVERGENCE` |
| `ready_templates/video/wanvideo_wrapper_22_14b_t2i.py` | `WanVideoSampler` ×2 | `force_offload` | `NAMED_CAG_DIVERGENCE` |
| `ready_templates/video/wanvideo_wrapper_22_5b_i2v.py` | `WanVideoSampler` ×1 | `force_offload` | `NAMED_CAG_DIVERGENCE` |
| `ready_templates/video/wanvideo_wrapper_22_5b_i2v_controlnet.py` | `WanVideoSampler` ×1 | `force_offload` | `NAMED_CAG_DIVERGENCE` |
| `ready_templates/video/wanvideo_wrapper_22_5b_ovi_audio_i2v.py` | `WanVideoSampler` ×1 | `force_offload` | `NAMED_CAG_DIVERGENCE` |
| `ready_templates/video/wanvideo_wrapper_22_5b_t2v_controlnet.py` | `WanVideoSampler` ×1 | `force_offload` | `NAMED_CAG_DIVERGENCE` |
| `ready_templates/video/wanvideo_wrapper_22_s2v_context_window.py` | `WanVideoSampler` ×1 | `force_offload` | `NAMED_CAG_DIVERGENCE` |
| `ready_templates/video/wanvideo_wrapper_22_s2v_framepack_pose.py` | `WanVideoSampler` ×1 | `force_offload` | `NAMED_CAG_DIVERGENCE` |

---

### F. Ready templates — schema-less widget mismatch (21)

Root cause: one or more nodes have no schema in `widget_schema.py` or the object-info cache. The emitter does best-effort emission (copies IR widget carriers in order) but cannot know the full widget list or their correct positions. Round-trip widget values diverge from `compile('api')`.

#### Audio (4)

| Entry | Schema-less node(s) | Diverging widget | Reason code |
|---|---|---|---|
| `ready_templates/audio/ace_step_1_5_t2a_song.py` | `EmptyAceStep1.5LatentAudio`, `ConditioningZeroOut`, `VAEDecodeAudio`, `TextEncodeAceStepAudio1.5` | `batch_size` (EmptyAceStep…) | `SCHEMA_LESS_WIDGET` |
| `ready_templates/audio/qwen3_tts_custom_voice.py` | `AILab_Qwen3TTSCustomVoice` | `instruct` | `SCHEMA_LESS_WIDGET` |
| `ready_templates/audio/qwen3_tts_voice_clone.py` | `AILab_Qwen3TTSVoiceClone` | `language` | `SCHEMA_LESS_WIDGET` |
| `ready_templates/audio/qwen3_tts_voice_design.py` | `AILab_Qwen3TTSVoiceDesign` | `instruct` | `SCHEMA_LESS_WIDGET` |

#### Edit (1)

| Entry | Schema-less node(s) | Diverging widget | Reason code |
|---|---|---|---|
| `ready_templates/edit/qwen_image_edit.py` | `ComfySwitchNode`, `CFGNorm` | `strength` (CFGNorm) | `SCHEMA_LESS_WIDGET` |

#### Smoke (1)

| Entry | Schema-less node(s) | Diverging widget | Reason code |
|---|---|---|---|
| `ready_templates/smoke/empty_image_red.py` | `EmptyImage` | `width` | `SCHEMA_LESS_WIDGET` |

#### Video (15)

| Entry | Schema-less node(s) | Diverging widget | Reason code |
|---|---|---|---|
| `ready_templates/video/basic_video_enhance.py` | `VHS_LoadVideo`, `VHS_VideoCombine` | `video` (VHS_LoadVideo) | `SCHEMA_LESS_WIDGET` |
| `ready_templates/video/ltx2_3_i2v.py` | `LowVRAMCheckpointLoader`, `LowVRAMAudioVAELoader`, etc. | `ckpt_name` | `SCHEMA_LESS_WIDGET` |
| `ready_templates/video/ltx2_3_iamccs_audio_image_to_video.py` (partial) | `LTXVConcatAVLatent`, `LTXVImgToVideoInplace`, etc. | multiple | `SCHEMA_LESS_WIDGET` |
| `ready_templates/video/ltx2_3_iamccs_long_i2v.py` | `LowVRAMAudioVAELoader`, `LTXVGemmaCLIPModelLoader`, etc. | `ckpt_name` | `SCHEMA_LESS_WIDGET` |
| `ready_templates/video/ltx2_3_lightricks_first_last_parity.py` | `LTXVAudioVAELoader`, `LTXVCropGuides`, etc. | `ckpt_name` | `SCHEMA_LESS_WIDGET` |
| `ready_templates/video/ltx2_3_lightricks_first_last_two_stage_lowvram.py` | `LTXVAudioVAELoader`, `LowVRAMCheckpointLoader`, etc. | `ckpt_name` | `SCHEMA_LESS_WIDGET` |
| `ready_templates/video/ltx2_3_t2v.py` | `LowVRAMCheckpointLoader`, `LowVRAMAudioVAELoader`, etc. | `ckpt_name` | `SCHEMA_LESS_WIDGET` |
| `ready_templates/video/wan22_animate_native_first_stage.py` | `WanAnimateToVideo` | `batch_size` | `SCHEMA_LESS_WIDGET` |
| `ready_templates/video/wan22_i2v_comfy_lightx2v.py` | `WanImageToVideo` | `batch_size` | `SCHEMA_LESS_WIDGET` |
| `ready_templates/video/wan_i2v.py` | `WanImageToVideo` | `batch_size` | `SCHEMA_LESS_WIDGET` |
| `ready_templates/video/wanvideo_wrapper_22_14b_i2v_kijai.py` | `VHS_VideoCombine` (schema-less crf slot) | `crf` | `SCHEMA_LESS_WIDGET` |
| `ready_templates/video/wanvideo_wrapper_22_14b_vace_cocktail.py` | `VHS_LoadVideo` | `video` | `SCHEMA_LESS_WIDGET` |
| `ready_templates/video/wanvideo_wrapper_22_wan_animate_preprocess_kijai.py` | `VHS_LoadVideo` | `force_rate` | `SCHEMA_LESS_WIDGET` |
| `ready_templates/video/wanvideo_wrapper_22_14b_t2i.py` (partial — also WanVideoSampler) | mixed schema-less + named-CAG | multiple | `SCHEMA_LESS_WIDGET` + `NAMED_CAG_DIVERGENCE` |
| `ready_templates/video/wanvideo_wrapper_22_s2v_context_window.py` (partial) | `WanVideoSampler` (primarily CAG) + `VHS_VideoCombine` | `force_offload` | listed under §E |

> Note: some entries appear in both §E and §F because they have both `NAMED_CAG_DIVERGENCE` and `SCHEMA_LESS_WIDGET` failures. All are on the allowlist regardless of which code applies.

---

## Complete allowlist index

The following 45 paths are on the parity gate allowlist. A test asserting `offline_emitter_normalizer_self_consistency_check(wf) == (True, [])` MUST skip these.

```
# Manifests — NOT_A_WORKFLOW
workflow_corpus/manifests/coverage.json
workflow_corpus/manifests/ready_regeneration.json

# Corpus JSON — PARITY_FAIL_TOPOLOGY
workflow_corpus/official/image/qwen_image_2512.json

# Ready templates — PIN_OPAQUE_WIDGET_SHAPE / REFUSED_WIDGET_SHAPE
ready_templates/video/ltx2_3_iamccs_audio_extend_low_ram.py
ready_templates/video/ltx2_3_lightricks_iclora_motion_track.py
ready_templates/video/ltx2_3_lightricks_two_stage.py
ready_templates/video/ltx2_3_runexx_lipsync_custom_audio.py
ready_templates/video/ltx2_3_runexx_music_video_low_ram.py
ready_templates/video/ltx2_3_runexx_talking_avatar_qwen_tts.py
ready_templates/video/wanvideo_wrapper_21_14b_fun_control.py
ready_templates/video/wanvideo_wrapper_21_14b_t2v.py
ready_templates/video/wanvideo_wrapper_21_14b_wanmove_i2v.py
ready_templates/video/wanvideo_wrapper_wan_animate.py

# Ready templates — NAMED_CAG_DIVERGENCE (RandomNoise)
ready_templates/video/ltx2_3_first_last_frame_travel_iclora_control.py
ready_templates/video/ltx2_3_iamccs_audio_image_to_video.py
ready_templates/video/ltx2_3_lightricks_iclora_hdr.py
ready_templates/video/ltx2_3_lightricks_iclora_union_control.py
ready_templates/video/ltx2_3_runexx_custom_audio.py
ready_templates/video/ltx2_3_runexx_first_last_frame.py
ready_templates/video/ltx2_3_runexx_first_last_raw_video_guide.py
ready_templates/video/ltx2_3_runexx_first_middle_last_frame.py
ready_templates/video/ltx2_3_runexx_motion_transfer_dwpose.py
ready_templates/video/ltx2_3_runexx_video_to_video_extend.py

# Ready templates — NAMED_CAG_DIVERGENCE (WanVideoSampler.force_offload)
ready_templates/video/wanvideo_wrapper_13b_control_lora.py
ready_templates/video/wanvideo_wrapper_13b_recammaster.py
ready_templates/video/wanvideo_wrapper_13b_vace.py
ready_templates/video/wanvideo_wrapper_21_14b_flf2v.py
ready_templates/video/wanvideo_wrapper_21_14b_fun_control_camera.py
ready_templates/video/wanvideo_wrapper_21_14b_i2v.py
ready_templates/video/wanvideo_wrapper_21_14b_v2v_infinitetalk.py
ready_templates/video/wanvideo_wrapper_22_14b_t2i.py
ready_templates/video/wanvideo_wrapper_22_5b_i2v.py
ready_templates/video/wanvideo_wrapper_22_5b_i2v_controlnet.py
ready_templates/video/wanvideo_wrapper_22_5b_ovi_audio_i2v.py
ready_templates/video/wanvideo_wrapper_22_5b_t2v_controlnet.py
ready_templates/video/wanvideo_wrapper_22_s2v_context_window.py
ready_templates/video/wanvideo_wrapper_22_s2v_framepack_pose.py

# Ready templates — SCHEMA_LESS_WIDGET
ready_templates/audio/ace_step_1_5_t2a_song.py
ready_templates/audio/qwen3_tts_custom_voice.py
ready_templates/audio/qwen3_tts_voice_clone.py
ready_templates/audio/qwen3_tts_voice_design.py
ready_templates/edit/qwen_image_edit.py
ready_templates/smoke/empty_image_red.py
ready_templates/video/basic_video_enhance.py
ready_templates/video/ltx2_3_i2v.py
ready_templates/video/ltx2_3_iamccs_long_i2v.py
ready_templates/video/ltx2_3_lightricks_first_last_parity.py
ready_templates/video/ltx2_3_lightricks_first_last_two_stage_lowvram.py
ready_templates/video/ltx2_3_t2v.py
ready_templates/video/wan22_animate_native_first_stage.py
ready_templates/video/wan22_i2v_comfy_lightx2v.py
ready_templates/video/wan_i2v.py
ready_templates/video/wanvideo_wrapper_22_14b_i2v_kijai.py
ready_templates/video/wanvideo_wrapper_22_14b_vace_cocktail.py
ready_templates/video/wanvideo_wrapper_22_wan_animate_preprocess_kijai.py
```

---

## M2 fix targets

The allowlist is not permanent. The following issues are fixable in M2:

| Issue | Affected entries | Fix |
|---|---|---|
| `PIN_OPAQUE_WIDGET_SHAPE` / `REFUSED_WIDGET_SHAPE` — dynamic widget-shape overflow | 10 ready templates | Keep the S2 fence active. Add row-aware schema/object-info coverage only when regeneration can be proven; otherwise preserve unchanged raw UI payloads or refuse with typed node details. |
| `NAMED_CAG_DIVERGENCE` — named CAG slots in offline oracle | 24 ready templates | Extend `_normalize_ui_to_api` (or the parity comparator) to apply `_is_ui_only_prompt_input` stripping on named CAG/force_offload slots, OR teach the emitter not to emit CAG in `widgets_values` for nodes where it survives the normalizer. |
| `SCHEMA_LESS_WIDGET` | 18 ready templates + 1 corpus JSON | Add schema entries for missing custom node classes (LowVRAMCheckpointLoader, LTXVAudioVAELoader, WanImageToVideo, WanAnimateToVideo, EmptyAceStep1.5LatentAudio, AILab_Qwen3TTS*, CFGNorm, EmptyImage, VHS_LoadVideo, VHS_VideoCombine). Dynamic row widgets such as Power Lora remain under the widget-shape fence until row-aware regeneration is proven. |
