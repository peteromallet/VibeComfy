# Family Attribution Verified Checkpoint

T18 checkpoint status: review required before any E.x fixture authoring starts.

This document is the hard gate requested by Pre-E.2/3/4. It is based on the current worktree after T17 restored `workflow_corpus/custom_nodes` as a symlink, and on running this dry-run command shape for every `ready_templates/**/*.py` file that still inlines `SymbolicNodeRef`:

```bash
python -m vibecomfy.cli port convert <source>.json --ready-id <kind>/<name> --dry-run --json
```

## Decision Summary

The previous A/E counts do not reconcile with the live dry-run evidence. No current dry-run reaches a clean "Family A register_input id-map" failure; A remains a valid fixture family, but the 8/9 template attribution is not verified by this checkpoint.

Family E is verified by raw source topology, not by a clean candidate failure, for 8 source workflows with `properties.proxyWidgets`: `edit/qwen_image_edit`, `image/z_image`, `video/ltx2_3_iamccs_long_i2v`, `video/ltx2_3_runexx_first_last_frame`, `video/ltx2_3_runexx_first_middle_last_frame`, `video/ltx2_3_runexx_lipsync_custom_audio`, `video/ltx2_3_runexx_music_video_low_ram`, and `video/ltx2_3_runexx_video_to_video_extend`.

Opaque UUID components are a separate Family I, not a Family E variant. The decisive example is `image/z_image`: node `76` has class type `9b9009e4-2d3d-445f-9be5-6063f465757e`, one `proxyWidgets` list, unresolved `widget_0` through `widget_9`, and hidden model filenames in `widget_7`, `widget_8`, and `widget_9`. Family E can only map widget values correctly; it does not explain how a UUID class becomes first-class runnable Python/API nodes.

`audio/ace_step_1_5_t2a_song` is blocked by Family J, not by Family B yet. `port check` stops on `PrimitiveNode` and `TextEncodeAceStepAudio1.5.widget_14` before any register-input retargeting can be observed. `nodes spec TextEncodeAceStepAudio1.5` succeeds and shows 14 known inputs with no `widget_14`; `nodes spec PrimitiveNode` fails with "node schema not found". `nodes install-plan` returns no packs. This is a schema/node-pack coverage precondition, not an emitter-family fixture target yet.

Counting fixture families plus blockers now yields more than 8 buckets: A, B, C, D, E, F, I, J, and source-provenance gaps. Per the plan's own rule, E fixture authoring should be rescoped/reviewed before starting, not launched mechanically from the older counts.

## Family Legend

| Bucket | Meaning | T18 decision |
|---|---|---|
| A | `register_input` id-map preservation | Valid generic fixture family, but not observed as a primary live dry-run failure. |
| B | `register_input` retargets wrong runtime node after inlining | Not currently observable where J hard errors fire first. |
| C | Materialized subgraph function name collides with a local/build symbol | Verified for `edit/qwen_image_edit`. |
| D | Multi-output arity mismatch | Still likely for `video/wanvideo_wrapper_22_wan_animate_preprocess_kijai`, but its source is unavailable locally. |
| E | `proxyWidgets` ordering during subgraph materialization | Verified in raw topology for 8 source workflows. |
| F | Helper resolver for `SetNode`/`GetNode`/`Reroute` | Partially improved already for Set/Get in reports; `Reroute` still appears as hard runtime-class precondition in several templates. |
| I | Opaque UUID component handling | New separate family; frequently co-located with E but not reducible to widget ordering. |
| J | Missing/stale node-pack schema, model enum, or validation precondition | Dominant current blocker for most giant community workflows. |
| P | Source provenance gap | Template has no local `source_workflow` to dry-run. |

## Per-Template Verdicts

| Template | Dry-run result and exact blocking error | Primary | Secondary / blocked family signal | Blocking preconditions |
|---|---|---|---|---|
| `audio/ace_step_1_5_t2a_song` | `port convert stopped because port check found hard errors`; exact errors include `unresolved_runtime_class PrimitiveNode`, `unknown_input widget_14` on node `124` `TextEncodeAceStepAudio1.5`, and `unknown_class_type PrimitiveNode` on node `126`. | J | B unverified; do not write B fixture from this template yet. | Add/repair `PrimitiveNode` schema or provider; update `TextEncodeAceStepAudio1.5` widget aliases/schema for `widget_14` or prove the workflow is stale. |
| `edit/qwen_image_edit` | Candidate generation reaches strict-ready validation, then fails: `UnboundLocalError: cannot access local variable 'qwen_image_edit' where it is not associated with a value`. | C | E/I present: raw source has one proxyWidgets UUID component `74a8e1e2-9cb8-4112-978e-06ce1b5793f1`. | None before C fixture; I may still block full promotion after C. |
| `image/z_image` | Candidate builds/compiles, then validation fails: `missing_required_input UNETLoader.weight_dtype`, `missing_required_input KSampler.scheduler`, and `KSampler.steps value 770044821593082 is outside range`. | E | I present and separate: raw node `76` is UUID class `9b9009e4-2d3d-445f-9be5-6063f465757e` with proxyWidgets and hidden model filenames. | E fixture should cover proxyWidget mapping; I fixture/design must cover opaque UUID component replacement/inline policy. |
| `video/ltx2_3_i2v` | `port convert stopped because port check found hard errors`; exact errors include `unresolved_runtime_class ClownSampler_Beta`, two `GemmaAPITextEncode.ckpt_name value 'ltx-2.3-22b-dev.safetensors' is not one of the declared choices`, `unknown_class_type ClownSampler_Beta`, and `unknown_input LTXFloatToInt.rounding`. | J | No E/I source evidence; A/B not observable. | Refresh/install ClownSampler schema and LTX schema/model enum data. |
| `video/ltx2_3_iamccs_audio_extend_low_ram` | Hard `port check`; first errors include unresolved `IAMCCS_AudioExtender`, `IAMCCS_AudioExtensionMath`, `IAMCCS_AudioTimelineGate`, `IAMCCS_LTX2_ExtensionModule_Disk`, `IAMCCS_StartDirToVideoLatent`, `IAMCCS_VAEDecodeToDisk`, `IAMCCS_VideoCombineFromDir`, plus `ltx_audio_vae_wrong_loader`. | J | Prior B attribution is not currently observable. | IAMCCS custom-node schemas/packs, LTX audio VAE loader pairing, model enum coverage. |
| `video/ltx2_3_iamccs_audio_image_to_video` | Hard `port check`; errors include unresolved `Audio Duration (mtb)`, `Audio To Text (mtb)`, `CR Float To Integer`, `FB_Qwen3TTSVoiceClone`, `FL_ChatterboxTurboTTS`, multiple `IAMCCS_*`, plus invalid link shapes and missing sampler inputs. | J | No clean emitter-family signal yet. | Install/declare MTB, Comfyroll, Qwen TTS, Chatterbox, and IAMCCS schemas or reduce source before fixture use. |
| `video/ltx2_3_iamccs_long_i2v` | Hard `port check`; errors include unresolved `IAMCCS_AutoLinkArguments`, `IAMCCS_AutoLinkConverter`, `IAMCCS_GGUF_accelerator`, `IAMCCS_LTX2_ExtensionModule`, plus model enum errors and LTX audio VAE loader mismatch. | J | E/I present: 3 proxyWidgets nodes and UUID components `3eaa20c4-...`, `8b36a85a-...`. | IAMCCS schemas and model enum/loader coverage before using as E evidence. |
| `video/ltx2_3_lightricks_iclora_union_control` | Hard `port check`; errors include unknown classes `DWPreprocessor`, `VideoDepthAnythingProcess`, `LoadVideoDepthAnythingModel`, `VideoDepthAnythingOutput`, `CannyEdgePreprocessor`, plus `ResizeImageMaskNode.resize_type.multiple` and `LTXFloatToInt.rounding`. | J | No E/I source evidence; A not observed. | controlnet/depth preprocessors and current schema aliases. |
| `video/ltx2_3_runexx_custom_audio` | Hard `port check`; exact first errors include unresolved `MelBandRoFormerModelLoader`, `MelBandRoFormerSampler`, `Reroute`, `easy showAnything`, plus `headless_preview_override_not_supported LTX2SamplingPreviewOverride`. | J | F signal: 62 Set/Get broadcasts resolved, but `Reroute` still blocks; this resolves one of the four previously unassigned runexx templates as J/F, not E/A. | Install/update MelBand/easy-use/Reroute schema and decide preview override policy. |
| `video/ltx2_3_runexx_first_last_frame` | Hard `port check`; errors include preview override, sageattention package requirements, `ltx_audio_vae_wrong_loader`, `SimpleCalculatorKJ` missing inputs, and model enum failures. | J | E/I present: 1 proxyWidgets node and UUID classes `19e3f7e8-...`, `8fa4f93a-...`. | KJ/LTX schema drift, loader pairing, optional acceleration policy. |
| `video/ltx2_3_runexx_first_last_raw_video_guide` | No conversion run: template has no `source_workflow` metadata and no matching local source JSON was found under restored `workflow_corpus`. | P | Unknown; cannot attribute from current evidence. | Add `READY_METADATA.provenance.source_workflow` or restore the source JSON. |
| `video/ltx2_3_runexx_first_middle_last_frame` | Hard `port check`; first errors include preview override, sageattention package requirements, `ltx_audio_vae_wrong_loader`, `SimpleCalculatorKJ` missing inputs, and many `LTXVAddGuideMulti` unknown inputs. | J | E/I present: 1 proxyWidgets node and UUID classes `19e3f7e8-...`, `8fa4f93a-...`. | KJ/LTX schema drift and source simplification before using as E evidence. |
| `video/ltx2_3_runexx_lipsync_custom_audio` | Hard `port check`; first errors include unresolved `FaceSegment`, `MelBandRoFormerModelLoader`, `MelBandRoFormerSampler`, `Reroute`, and `easy showAnything`. | J | E/I present: 1 proxyWidgets node and UUID `e428c881-...`; F signal from 82 helper broadcasts. This resolves a previously unassigned runexx template as J with E/I/F secondary. | Install/update FaceSegment, MelBand, easy-use, Reroute schemas. |
| `video/ltx2_3_runexx_motion_transfer_dwpose` | Hard `port check`; first errors include unresolved `DepthAnythingPreprocessor`, `easy showAnything`, preview override, sageattention package requirement, and `ltx_audio_vae_wrong_loader`. | J | I present: UUID `94e8f3a0-...`; F signal from 103 helper broadcasts. | Depth/easy-use schema coverage and LTX runtime policy. |
| `video/ltx2_3_runexx_music_video_low_ram` | Hard `port check`; first errors include unresolved `MelBandRoFormerModelLoader`, `MelBandRoFormerSampler`, `easy showAnything`, preview override, sageattention package requirement, and many `VHS_VideoCombine` unknown inputs. | J | E/I present: 4 proxyWidgets nodes and 6 UUID classes; F signal from 91 helper broadcasts. This resolves a previously unassigned runexx template as J with strong E/I/F secondary. | MelBand/easy-use/VHS/KJ schema updates and preview/acceleration policy. |
| `video/ltx2_3_runexx_video_to_video_extend` | Hard `port check`; first errors include unresolved `Reroute`, preview override, sageattention package requirements, `ltx_audio_vae_wrong_loader`, and `DualCLIPLoaderGGUF` unknown class. | J | E/I present: 1 proxyWidgets UUID `6002fb3c-...`; F signal from 66 helper broadcasts. This resolves a previously unassigned runexx template as J with E/I/F secondary. | Reroute/DualCLIPLoaderGGUF schema coverage and LTX runtime policy. |
| `video/ltx2_3_t2v` | Same source and same hard errors as `video/ltx2_3_i2v`: unresolved `ClownSampler_Beta`, `GemmaAPITextEncode.ckpt_name` enum failures, and `LTXFloatToInt.rounding`. | J | No E/I source evidence; A/B not observable. | Refresh/install ClownSampler schema and LTX schema/model enum data. |
| `video/wanvideo_wrapper_13b_recammaster` | Hard `port check`; errors include unresolved `DownloadAndLoadFlorence2Model`, `Florence2Run`, `ShowText\|pysssss`, plus `WanVideoEncode.tile_stride_y` out of range and `VHS_*` unknown inputs. | J | Prior E attribution not verified by raw `proxyWidgets` count in this source; F signal from 10 helper broadcasts. | Florence/pysssss/VHS/WanVideo schema coverage. |
| `video/wanvideo_wrapper_13b_vace` | Hard `port check`; errors include `ImageConcatMulti.image_3`, repeated `VHS_VideoCombine` unknown inputs, `DownloadAndLoadDepthAnythingV2Model` unknown class, and Wan model enum failures. | J | Prior E attribution not verified by raw `proxyWidgets` count; F signal from 28 helper broadcasts. | DepthAnything/VHS/WanVideo schema coverage. |
| `video/wanvideo_wrapper_21_14b_v2v_infinitetalk` | Hard `port check`; errors include unresolved `MelBandRoFormerModelLoader`, `MelBandRoFormerSampler`, model enum failures for `MultiTalkModelLoader`/`WanVideoModelLoader`, `WanVideoImageToVideoMultiTalk` value errors, and `VHS_*` unknown inputs. | J | Prior E attribution not verified by raw `proxyWidgets` count; F signal from 17 helper broadcasts. | MelBand, MultiTalk, WanVideo, and VHS schema/model coverage. |
| `video/wanvideo_wrapper_22_s2v_context_window` | Hard `port check`; errors include unresolved `DownloadAndLoadGIMMVFIModel`, `GIMMVFI_interpolate`, `MelBandRoFormerModelLoader`, `MelBandRoFormerSampler`, and `PrimitiveNode`; plus Wan model enum failures. | J | No E proxyWidgets in source; PrimitiveNode makes this another J example. | GIMMVFI/MelBand/PrimitiveNode schemas and Wan model enum coverage. |
| `video/wanvideo_wrapper_22_s2v_framepack_pose` | Hard `port check`; errors include unresolved `MelBandRoFormerModelLoader`, `MelBandRoFormerSampler`, `PrimitiveNode`, and `Reroute`, plus Wan model enum/value range and `VHS_*` inputs. | J | F signal: `Reroute` still blocks while Set/Get are partly resolved. | MelBand/PrimitiveNode/Reroute schemas and Wan/VHS schema coverage. |
| `video/wanvideo_wrapper_22_wan_animate_preprocess_kijai` | No conversion run: template has no `source_workflow` metadata and no local source JSON found; it only records an upstream `source_url`. | P | D remains likely from prior attribution, but cannot be verified against a local source in this checkpoint. | Restore/cache the upstream JSON or add local `source_workflow` provenance before D fixture selection. |

## Implications For E Fixture Authoring

Do not start the E.x fixtures from the older family table. The verified fixture plan should be reviewed with these updates:

- Keep small synthetic fixtures for A, B, C, D, E, F. A/B/D should not be sourced directly from the blocked giant workflows until their preconditions are handled.
- Add a separate Family I fixture or design note for opaque UUID component handling. `z_image` is the minimal concrete trace for the decision: UUID node `76`, proxyWidgets mapping, and hidden model widgets.
- Treat Family J as a precondition bucket, not an emitter fixture family. It needs schema/install-plan/model-registry work before many community workflows can be used as evidence.
- Treat P as a data-restoration task. Two of the 23 cannot be dry-run locally today because source provenance is missing.

## Commands Run

```bash
python -m vibecomfy.cli port convert <source> --ready-id <ready_id> --dry-run --json
python -m vibecomfy.cli port check workflow_corpus/official/image/z_image.json --json
python -m vibecomfy.cli port check workflow_corpus/official/audio/ace_step_1_5_t2a_song.json --json
python -m vibecomfy.cli nodes install-plan workflow_corpus/official/audio/ace_step_1_5_t2a_song.json --json
python -m vibecomfy.cli nodes spec 'TextEncodeAceStepAudio1.5'
python -m vibecomfy.cli nodes spec PrimitiveNode
```
