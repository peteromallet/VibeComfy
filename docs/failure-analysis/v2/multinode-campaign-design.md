# Multi-node additive campaign design

## Purpose and selection standard

This campaign makes additive editing test the product capability: reconstruct a
missing, cohesive function, not guess one deleted node. Every case below removes
at least five nodes, keeps the inquiry free of the golden node list and hidden
values, and grades a valid, role-correct, runnable restoration rather than byte
identity.

The ready-template cases were inspected in their generated Python/source graph
and exported through the same schema-aware `_export_ready_ui()` path used by
`_golden_for`. The two corpus cases were inspected in `compiled_api`; each
selected class resolves in the local object-info inventory and each artifact
reports no missing nodes. A schema export and baseline validation remain
mandatory registration gates for corpus cases.

| Case | Category | Family | Feature | Nodes |
|---|---|---|---|---:|
| M-01 | image | Qwen Image 2512 | four-step Lightning acceleration path | 5 |
| M-02 | image-edit | Flux.2 Klein 9B | second-reference conditioning | 5 |
| M-03 | image-edit | Qwen Image Edit 2506 | pose ControlNet branch | 5 |
| M-04 | t2v/control | Wan 2.2 5B | depth-video ControlNet branch | 7 |
| M-05 | i2v/t2v | LTX-2.3 | second-stage latent refinement | 10 |
| M-06 | speech-to-video | Wan 2.2 S2V | performance-video pose branch | 5 |
| M-07 | first/last-frame i2v | LTX-2.3 | last-frame target guide | 5 |
| M-08 | v2v | LTX-2.3 | continuation stitching and audio extension | 5 |
| M-09 | audio-driven video | LTX-2 | vocal-guidance and remix path | 6 |
| M-10 | audio | ACE-Step 1.5 | text-to-song generation head | 5 |

## M-01: Qwen Image 2512 four-step Lightning slice

**Source.** Ready template `image/qwen_image_2512`, sourced from
`ready_templates/sources/official/image/qwen_image_2512.json`. Modern family:
Qwen Image 2512. Category: text-to-image.

**The slice (5 nodes).**

- `63 LoraLoaderModelOnly`
- `71 ComfySwitchNode`
- `64 ModelSamplingAuraFlow`
- `72 ComfySwitchNode`
- `73 ComfySwitchNode`

This is one capability: select the optional Lightning-patched model, apply its
matching sampling shift, and supply the accelerated sampler's model/step/CFG
controls. The upstream boundary is `65 UNETLoader`; the downstream boundary is
`68 KSampler` at its `model`, `steps`, and `cfg` roles.

**Removal.** Delete the five nodes and every incident link atomically. Bridge
the retained base model from `65` to `68.model`; prune the two linked control
inputs so the broken graph visibly lacks the accelerated profile. If a runnable
fault requires materialized sampler controls, use ordinary schema defaults
declared by the fault policy, not hidden golden values.

**Realistic inquiry.**

> The fast Lightning path has disappeared. This Qwen workflow now behaves like the slow base model instead of the quick four-step setup I was using. Please restore the accelerated generation path without changing my prompt or output size.

**Correct reconstruction.** The sampler consumes a Qwen-compatible accelerated
model path and matching low-step sampling configuration, with valid inputs and a
runnable image output. A different compatible acceleration adapter or
equivalent control mechanism is acceptable; simply lowering the step count on
the unpatched base model is not.

**Verification note.** The schema-aware golden exported with 14 nodes and 15
links. Inspected type list:
`[LoraLoaderModelOnly, ComfySwitchNode, ModelSamplingAuraFlow, ComfySwitchNode, ComfySwitchNode]`
(5 nodes); all five sockets were materialized in the exported golden.

## M-02: Flux.2 Klein 9B second-reference conditioning slice

**Source.** Ready template `edit/flux2_klein_9b_image_edit_base`, sourced from
`ready_templates/sources/official/edit/flux2_klein_9b_image_edit_base.json`.
Modern family: Flux.2 Klein 9B. Category: multi-reference image edit.

**The slice (5 nodes).**

- `81 LoadImage`
- `18 ImageScaleToTotalPixels`
- `29 VAEEncode`
- `34 ReferenceLatent`
- `35 ReferenceLatent`

This is the complete second-reference branch: load and normalize the additional
image, encode it, and attach its latent to both positive and negative
conditioning streams. The retained VAE `22` enters the encoder; retained
first-reference conditionings `32` and `33` enter the two removed
`ReferenceLatent` nodes; their outputs feed `36 CFGGuider`.

**Removal.** Delete the five-node branch and its links. Bypass the missing
second reference by wiring `32` and `33` directly to the positive and negative
roles of `36`; the first reference and the rest of the edit sampler remain
runnable.

**Realistic inquiry.**

> This edit is only paying attention to the main reference now. The second reference image has no influence on the result, even though I need both images to guide the edit. Please add that second-reference conditioning back without changing the sampler.

**Correct reconstruction.** A second user image is normalized and VAE-encoded,
then contributes to both conditioning branches that reach the active guider and
sampler. A native multi-reference conditioner is acceptable instead of the
literal two-node reference chain if both images actually influence the runnable
edit.

**Verification note.** The schema-aware golden exported with 42 nodes and 57
links. Inspected type list:
`[LoadImage, ImageScaleToTotalPixels, VAEEncode, ReferenceLatent, ReferenceLatent]`
(5 nodes).

## M-03: Qwen Image Edit pose-ControlNet slice

**Source.**
`external_workflows/corpus/7952d606da990a99.json`, source filename
`Qwen-Image-Edit-2506-Lightning-Control-Net-Pose.json` (2025-11-05).
Modern family: Qwen Image Edit 2506 Lightning. Category: image edit.

**The slice (5 nodes).**

- `164 LoadImage`
- `172 Image Resize (rgthree)`
- `165 DWPreprocessor`
- `167 ControlNetLoader`
- `163 ControlNetApplyAdvanced`

This is one structural-guidance feature: ingest a second image, fit it to the
edit dimensions, extract body pose, load the control model, and apply it to both
conditioning branches. Retained `175 GetImageSize` supplies width/height;
retained Qwen conditionings `161`/`158` and VAE `148` enter the application
node; its positive/negative outputs feed retained `157 KSampler`.

**Removal.** Remove the five compiled node IDs and all incident edges. Bridge
the retained positive and negative Qwen conditioning directly to `157`, leaving
a runnable Qwen edit whose observable defect is that it ignores the pose
reference.

**Realistic inquiry.**

> The pose guidance has disappeared: edits no longer follow the body pose in my second reference image. Please restore structural pose ControlNet guidance while keeping the Qwen edit setup and output dimensions unchanged.

**Correct reconstruction.** A reference-pose image is preprocessed and applied
as ControlNet guidance to both conditioning branches that drive the active
sampler. An equivalent pose estimator or advanced ControlNet application is
acceptable if it is dimensionally compatible and runnable.

**Verification note.** I inspected the artifact's `compiled_api` and exact edge
references. Inspected type list:
`[LoadImage, Image Resize (rgthree), DWPreprocessor, ControlNetLoader, ControlNetApplyAdvanced]`
(5 nodes). All five classes resolve locally; the artifact declares
`requirements.missing_nodes = []`.

## M-04: Wan 2.2 5B depth-ControlNet slice

**Source.** Ready template
`video/wanvideo_wrapper_22_5b_t2v_controlnet`, sourced from
`ready_templates/sources/custom_nodes/wanvideo_wrapper/kijai/wan22_5b_t2v_controlnet.json`.
Modern family: Wan 2.2 5B. Category: text-to-video with control video.

**The slice (7 nodes).**

- `98 VHS_LoadVideo`
- `101 ImageResizeKJv2`
- `104 MiDaS-DepthMapPreprocessor`
- `109 ImageResizeKJv2`
- `103 WanVideoControlnetLoader`
- `105 WanVideoControlnet`
- `112 PreviewAnimation`

This is the whole depth-control branch: load and size the guide clip, derive and
refit its depth maps, load/apply the Wan ControlNet, and preview the actual
control sequence. Constants `113`/`114`/`115` enter the sizing path; base model
`22` enters `105`; the controlled model exits to `16 WanVideoTextEncode` and
`27 WanVideoSampler`.

**Removal.** Remove all seven nodes and incident links in one operation. Bridge
`22` directly to the model roles of `16` and `27`; prune the removed preview
branch. This produces a runnable ordinary Wan T2V path that no longer follows
the guide clip.

**Realistic inquiry.**

> The depth ControlNet guidance has disappeared: the video still renders, but it ignores the structure and camera layout from my guide clip. Please restore that control-video path so the generated motion follows the reference depth again.

**Correct reconstruction.** A dimension-matched depth/control-video path feeds
a compatible Wan ControlNet whose controlled model is the one used by the text
encoder and sampler. Equivalent depth preprocessors or compatible Wan control
implementations are acceptable; a disconnected preview-only branch is not.

**Verification note.** The schema-aware golden exported with 23 nodes and 27
links. Inspected type list:
`[VHS_LoadVideo, ImageResizeKJv2, MiDaS-DepthMapPreprocessor, ImageResizeKJv2, WanVideoControlnetLoader, WanVideoControlnet, PreviewAnimation]`
(7 nodes).

## M-05: LTX-2.3 second-stage latent-refinement slice

**Source.** Ready template `video/ltx2_3_lightricks_two_stage`, sourced from
`ready_templates/sources/custom_nodes/ltxvideo/lightricks_2_3/LTX-2.3_T2V_I2V_Two_Stage_Distilled.json`.
Modern family: LTX-2.3 distilled. Category: two-stage image/text-to-video.

**The slice (10 nodes).**

- `4967 RandomNoise`
- `4974 LatentUpscaleModelLoader`
- `4976 KSamplerSelect`
- `4985 ManualSigmas`
- `4964 CFGGuider`
- `4975 LTXVLatentUpsampler`
- `4970 LTXVImgToVideoConditionOnly`
- `4969 LTXVConcatAVLatent`
- `4971 SamplerCustomAdvanced`
- `4973 LTXVSeparateAVLatent`

These ten nodes are exactly the second pass: latent-upscale model and operation,
second-pass image conditioning and AV repack, independent noise/sampler/sigmas/
guider, sampling, and AV separation for decode. Stage-one split `4845`, model
`4922`, conditioning `1241`, VAE `3940`, and optional image `4990` form the
upstream boundary; `4973` feeds video decoder `4995` and audio decoder `4848`.

**Removal.** Delete the ten-node set and all internal/cut edges. For a valid
single-stage fault, bridge `4845.video` to `4995.latents` and `4845.audio` to
`4848.samples`. Do not run the existing per-node “first incoming source”
heuristic across this branch.

**Realistic inquiry.**

> Can you restore the second-stage LTX refinement? The video still generates, but it never gets the latent upscale and cleanup pass, so it looks softer and rougher than the two-stage result I had before.

**Correct reconstruction.** A true post-first-sampler latent upscale/refinement
stage occurs before decode and returns both video and audio latent streams.
Compatible alternative schedulers or samplers are allowed. Upscaling already
decoded frames does not restore this capability.

**Verification note.** The schema-aware golden exported with 35 nodes and 47
links. Inspected type list:
`[RandomNoise, LatentUpscaleModelLoader, KSamplerSelect, ManualSigmas, CFGGuider, LTXVLatentUpsampler, LTXVImgToVideoConditionOnly, LTXVConcatAVLatent, SamplerCustomAdvanced, LTXVSeparateAVLatent]`
(10 nodes).

## M-06: Wan 2.2 S2V performance-pose slice

**Source.** Ready template
`video/wanvideo_wrapper_22_s2v_framepack_pose`, sourced from
`ready_templates/sources/custom_nodes/wanvideo_wrapper/kijai/wan22_s2v_framepack_pose.json`.
Modern family: Wan 2.2 speech-to-video. Category: audio/portrait-to-video with a
performance guide.

**The slice (5 nodes).**

- `116 VHS_LoadVideo`
- `110 ImageResizeKJv2`
- `107 DWPreprocessor`
- `111 ImageResizeKJv2`
- `109 WanVideoEncode`

This is the complete performance-video pose input: load guide frames, normalize
them, extract facial/body pose, refit the pose maps, and VAE-encode the result as
the pose latent. Constants `131`/`132` and VAE `38` enter the branch; its output
feeds the `pose_latent` role of retained `117 WanVideoAddS2VEmbeds`.

**Removal.** Delete the five nodes and prune the single pose-latent cut edge.
The retained audio, portrait/reference latent, empty embeds, and VAE inputs of
`117` stay connected, so the broken S2V graph remains functional but lacks
performance motion.

**Realistic inquiry.**

> The speech-to-video clip still responds to the audio and portrait, but the character no longer follows the face performance from my guide video. Please restore that pose-guidance branch.

**Correct reconstruction.** Guide frames are pose-preprocessed, correctly
sized, encoded with the Wan VAE, and connected specifically to the existing
S2V pose role. An equivalent compatible pose extractor is acceptable; it must
not replace or disconnect the retained audio and reference-image inputs.

**Verification note.** The schema-aware golden exported with 34 nodes and 48
links. Inspected type list:
`[VHS_LoadVideo, ImageResizeKJv2, DWPreprocessor, ImageResizeKJv2, WanVideoEncode]`
(5 nodes).

## M-07: LTX-2.3 last-frame target-guide slice

**Source.** Ready template
`video/ltx2_3_lightricks_first_last_parity`. Modern family: LTX-2.3.
Category: first/last-frame image-to-video.

**The slice (5 nodes).**

- `2 LoadImage`
- `12 ResizeImageMaskNode`
- `14 LTXVPreprocess`
- `20 LTXVAddGuide`
- `25 LTXVCropGuides`

This branch loads and normalizes the end frame, appends it as final-frame
conditioning/latent guidance, and removes guide padding after sampling. Retained
first-frame guide `19` feeds the removed end guide; `20` feeds `21 CFGGuider`
and `22 LTXVConcatAVLatent`; sampled video `24` passes through `25` to decoder
`27`.

**Removal.** Remove the five nodes and their links. Bridge first-frame guide
`19` directly into `21` and `22`, and bridge `24.video` to `27.samples`. The
fault remains a runnable first-frame I2V workflow that no longer targets an end
image.

**Realistic inquiry.**

> The video still starts from my opening image, but it no longer lands on the ending image I supplied. Please restore the last-frame target so the motion transitions into that frame.

**Correct reconstruction.** An end image is normalized and applied at the
final-frame role; its conditioning and latent reach the active sampler, and
guide frames are handled before decode. Equivalent preprocessing and fresh IDs
are acceptable.

**Verification note.** The schema-aware golden exported with 28 nodes and 41
links. Inspected type list:
`[LoadImage, ResizeImageMaskNode, LTXVPreprocess, LTXVAddGuide, LTXVCropGuides]`
(5 nodes).

## M-08: LTX-2.3 video-continuation assembly slice

**Source.** Ready template
`video/ltx2_3_runexx_video_to_video_extend`, sourced from
`ready_templates/sources/custom_nodes/ltxvideo/runexx/LTX-2.3_V2V_Extend_Any_Video.json`.
Modern family: LTX-2.3. Category: video-to-video continuation.

**The slice (5 nodes).**

- `306 GetImageRangeFromBatch`
- `536 ImageBatchExtendWithOverlap`
- `394 TrimAudioDuration`
- `393 AudioConcat`
- `403 ImageBatchMulti`

This is one output-assembly function: select the generated continuation range,
crossfade/append it to the source frames, trim the new soundtrack to the
continuation, concatenate source and generated audio, and build the alternate
hard-concat view. Retained resized source frames `512` and generated decode
`527` enter the video side; retained source audio `443` and generated audio
decode `425` enter the audio side; the outputs feed retained video muxes `578`
and `627`.

**Removal.** Delete the five assembly nodes and cut edges. Rewire source frames
and source audio directly to the retained muxes as an explicit, socket-compatible
fault bypass. The output then contains only the original clip instead of an
appended continuation.

**Realistic inquiry.**

> The continuation is being generated, but it is no longer appended to the source video: there is no overlap blend, and the new audio is not joined to the original track. Please restore the finished video-extension assembly.

**Correct reconstruction.** Source and generated frames form one continuous
sequence with a sensible overlap transition, source/generated audio forms one
duration-aligned track, and those results reach the active output mux. A
different working crossfade/concat implementation is acceptable.

**Verification note.** The schema-aware golden exported with 76 nodes and 124
links. Inspected type list:
`[GetImageRangeFromBatch, ImageBatchExtendWithOverlap, TrimAudioDuration, AudioConcat, ImageBatchMulti]`
(5 nodes).

## M-09: LTX-2 vocal-guidance and generated-audio remix slice

**Source.**
`external_workflows/corpus/430a3f936f6235f5.json`, source filename
`LTX2_Sound2Video_v1.3_ABSYNTH_distilled.json` (2026-01-16).
Modern family: LTX-2 distilled. Category: audio-driven video.

**The slice (6 nodes).**

- `151 LTXVAudioVAEEncode`
- `148 SolidMask`
- `150 SetLatentNoiseMask`
- `156 Reroute`
- `126 LTXVAudioVAEDecode`
- `179 AudioMerge`

This is the functional bridge from an already isolated vocal/reference stem
into LTX audio-latent guidance and back into the finished soundtrack: encode,
mask, route into both AV sampling passes, decode generated audio, and mix it
with the preserved stem. Retained stem separator `153`, audio-VAE loader `127`,
dimensions `133`, and sampled AV split `124` enter the slice; `156` feeds AV
concat nodes `128`/`137`, and `179` feeds retained output mux `166`.

**Removal.** Remove the six nodes and all incident edges. For the degraded but
runnable fault, route the retained isolated/reference stem from `153` directly
to `166.audio`; the video still renders with the raw stem, but the audio no
longer guides generation and generated sound is not remixed.

**Realistic inquiry.**

> The clean vocal carry-through is broken. The reference stem is still available, but it no longer drives the LTX audio latent and the generated soundtrack is not mixed back with it. Please restore the guided audio and final remix.

**Correct reconstruction.** The reference stem is audio-VAE encoded into the
active AV latent path; generated audio is decoded and mixed with the preserved
stem before the video mux. Equivalent masking or merge nodes are acceptable.
Merely attaching the raw stem to the final video does not restore the
audio-guidance half of the feature.

**Verification note.** I inspected the artifact's `compiled_api`, including the
two outgoing `156` edges and the `179 -> 166.audio` boundary. Inspected type
list:
`[LTXVAudioVAEEncode, SolidMask, SetLatentNoiseMask, Reroute, LTXVAudioVAEDecode, AudioMerge]`
(6 nodes). All six classes resolve locally; the artifact declares
`requirements.missing_nodes = []`.

## M-10: ACE-Step 1.5 text-to-song generation head

**Source.** Ready template `audio/ace_step_1_5_t2a_song`, sourced from
`ready_templates/sources/official/audio/ace_step_1_5_t2a_song.json`.
Modern family: ACE-Step 1.5. Category: text-to-audio/song.

**The slice (5 nodes).**

- `122 EmptyAceStep1.5LatentAudio`
- `124 TextEncodeAceStepAudio1.5`
- `47 ConditioningZeroOut`
- `3 KSampler`
- `123 VAEDecodeAudio`

These nodes are the generation head: create the duration-shaped audio latent,
encode song/text conditioning, form the negative branch, sample the latent, and
decode it to audio. Retained UNet/model-sampling, text encoder, and VAE loaders
`125`/`78`/`105`/`106` enter the slice; decoded audio exits to retained
`59 SaveAudioMP3`.

**Removal.** Remove the five-node generation head and incident links. The
remaining graph deliberately contains the loaded ACE assets and output sink but
no song-producing path. This is the one case where a meaningful runnable bypass
would itself constitute a replacement generator, so the broken graph should be
accepted as a valid incomplete authoring graph rather than given a fake audio
source.

**Realistic inquiry.**

> The ACE-Step models still load, but the actual song-generation path is gone and nothing reaches the audio output. Please restore text-to-song generation so the prompt produces a finished, saveable track again.

**Correct reconstruction.** Prompt/audio conditioning and a duration-shaped
latent feed a compatible ACE-Step sampling path, the result is decoded with the
audio VAE, and runnable audio reaches the save node. Alternative compatible
guidance/sampling nodes are acceptable; a silent placeholder is not.

**Verification note.** The schema-aware golden exported with 10 nodes and 10
links. Inspected type list:
`[EmptyAceStep1.5LatentAudio, TextEncodeAceStepAudio1.5, ConditioningZeroOut, KSampler, VAEDecodeAudio]`
(5 nodes).

## M-11: Flux2 low-memory generation slice

**Source.** Ready template `image/flux2_klein_9b_gguf_t2i`. Modern family:
Flux2 Klein 9B GGUF. Category: text-to-image.

**The slice (8 nodes).** `4 UNETLoader`, `5 CLIPLoader`, `7 RandomNoise`,
`8 CLIPTextEncode`, `10 CFGGuider`, `11 SamplerCustomAdvanced`,
`12 VAEDecode`, and `14 CLIPTextEncode`. Together these nodes load the
quantized generation components, encode both prompt branches, guide and sample
the latent, and decode the result. The retained sampler selection, schedule,
canvas latent, VAE, and save node define the surviving boundary.

**Removal and inquiry.** Remove the eight nodes and incident links without a
bypass. The fault retains the canvas and output shell but no prompt-to-picture
generation head.

> I want to add the low-memory prompt-to-picture path back. The canvas and output are still present, but there is no complete generation stage between them. Please restore that path without changing my prompt or output size.

**Verification note.** The ready golden exported with 13 nodes and 13 links;
all eight IDs resolve and atomic removal leaves no dangling link endpoints.

## M-12: Qwen source-guided edit slice

**Source.** Ready template `edit/qwen_image_edit`. Modern family: Qwen Image
Edit. Category: image editing.

**The slice (6 nodes).** `78 LoadImage`, `6/7 TextEncodeQwenImageEdit`,
`8 VAEEncode`, `13 KSampler`, and `14 VAEDecode`. This is the source-picture
edit path: the source feeds positive and negative edit guidance plus the
starting latent, which are sampled and decoded into a new image. Model/VAE
loaders and the save node remain outside the slice.

**Removal and inquiry.** Delete the six-node edit path and all cut links. No
bypass is invented because the missing capability is deliberately authoring
critical.

> I want to restore image-guided editing. My source picture no longer becomes guidance for a new result, so the workflow cannot carry out the requested edit. Please add that source-conditioning and generation stage back without changing my instruction or output size.

**Verification note.** The ready golden exported with 16 nodes and 20 links;
the exact six nodes disappear atomically with no dangling endpoints.

## M-13: ACE-Step accelerated audio-conditioning slice

**Source.** Local Hivemind corpus
`external_workflows/corpus/8009c7ed72fd98a9.json`. Modern family: ACE-Step
1.5 Turbo. Category: text-to-audio.

**The slice (5 nodes).** `104 UNETLoader`, `78 ModelSamplingAuraFlow`,
`105 DualCLIPLoader`, `94 TextEncodeAceStepAudio1.5`, and
`47 ConditioningZeroOut`. This coherent front half loads the accelerated audio
generator, prepares its sampling behavior, and derives positive/negative song
conditioning. Duration controls, latent, sampler, decoder, VAE, and audio save
remain as the surviving shell.

**Removal and inquiry.** Remove the five-node accelerated conditioning path;
the primary sampling-model role at `78` keeps a boundary to the retained
sampler.

> I want to restore the fast song-generation setup. The duration and output pieces remain, but my description no longer drives a finished track at the speed I had. Please add the accelerated prompt-to-audio path back without changing the composition request.

**Verification note.** The corpus golden exported with 12 nodes and 14 links,
all selected classes resolve through local object info, and the full golden
passes the offline port check.

## M-14: Wan 2.2 synchronized-soundtrack slice

**Source.** Ready template
`video/wanvideo_wrapper_22_5b_ovi_audio_i2v`. Modern family: Wan 2.2 5B Ovi.
Category: audiovisual image-to-video.

**The slice (5 nodes).** `125 WanVideoEmptyMMAudioLatents`,
`89 OviMMAudioVAELoader`, `90 WanVideoDecodeOviAudio`, `108 PreviewAudio`,
and `88 VHS_VideoCombine`. This is the generated-soundtrack side of the shared
sampling result: supply audio latents, decode them, audition the audio, and
mux it with decoded frames.

**Removal and inquiry.** Delete the five nodes and their incident links. The
visual sampling and decode path remains, but synchronized sound and final
audiovisual packaging are absent.

> I want to add the generated soundtrack path back. The render should produce synchronized sound from the same generation, let me audition it, and package it with the frames in the finished clip.

**Verification note.** The ready golden exported with 22 nodes and 25 links;
the exact slice removes cleanly with no bypass or dangling endpoints.

## M-15: Wan 2.2 guided-transition slice

**Source.** Ready template
`video/wanvideo_wrapper_22_14b_vace_cocktail`. Modern family: Wan 2.2 14B
VACE. Category: guided video generation.

**The slice (5 nodes).** `4/7 LoadImage`, `8 VHS_LoadVideo`,
`12 WanVideoVACEStartToEndFrame`, and `13 WanVideoVACEEncode`. This branch
combines opening and ending images with a control clip, constructs the guide
and mask sequence, and encodes it for the retained multi-pass samplers.

**Removal and inquiry.** Remove the complete multi-reference guide branch.
The model and text-to-video sampling chain stays present, but it has no
reference transition conditioning.

> I want to restore the guided transition I had: it used my opening picture, ending picture, and control clip together. Now those references no longer shape the transition. Please add that multi-reference guidance path back without changing the text prompt or output dimensions.

**Verification note.** The ready golden exported with 22 nodes and 31 links;
all five selected IDs resolve and removal leaves zero dangling links.

## M-16: Wan speech-driven performance slice

**Source.** Ready template
`video/wanvideo_wrapper_21_14b_v2v_infinitetalk`. Modern family: Wan 2.1
InfiniteTalk. Category: speech-driven video-to-video.

**The slice (6 nodes).** `125 LoadAudio`,
`137 DownloadAndLoadWav2VecModel`, `194 MultiTalkWav2VecEmbeds`,
`270 INTConstant`, `303 MelBandRoFormerModelLoader`, and
`304 MelBandRoFormerSampler`. This branch loads the voice, separates the
performance-bearing stem, encodes speech motion over the intended duration,
and feeds the retained video sampler.

**Removal and inquiry.** Delete the six-node speech-performance branch. The
reference-video and visual-conditioning path remains, while mouth motion and
the exported voice track disappear.

> I want to add the speech-driven performance path back. The reference clip still loads, but the speaker's mouth no longer follows the supplied voice and the exported result has lost that voice track. Please restore the sound-to-performance guidance without changing the visual prompt.

**Verification note.** The ready golden exported with 28 nodes and 38 links;
atomic removal is exact and produces no dangling endpoints.

## M-17: Wan 2.2 subject-isolation slice

**Source.** Ready template `video/wan22_animate_native_first_stage`. Modern
family: Wan 2.2 Animate. Category: character animation preprocessing.

**The slice (6 nodes).** `6 DownloadAndLoadSAM2Model`, `19 PointsEditor`,
`20 Sam2Segmentation`, `21 GrowMask`, `22 BlockifyMask`, and
`23 DrawMaskOnImage`. This is one interactive subject-isolation capability:
select a person in guide footage, segment it consistently, stabilize the mask,
and preview that mask on the frames used by the retained animation path.

**Removal and inquiry.** Delete the six mask-authoring nodes and their links.
The guide footage remains available, but there is no subject selection or mask
preview to constrain animation.

> I want to restore the subject-isolation step for character animation. I need to mark the person in the guide footage, expand that selection into a stable mask, preview it over the frames, and use it to keep the animation confined to that subject.

**Verification note.** The ready golden exported with 30 nodes; the exact six
nodes remove without a bypass or dangling links.

## M-18: LTX-2.3 vocal segment-guidance slice

**Source.** Ready template `video/ltx2_3_runexx_music_video_low_ram`. Modern
family: LTX-2.3. Category: audio-guided music video.

**The slice (5 nodes).** `1594 LoadAudio`, `1598 TrimAudioDuration`,
`1600 MelBandRoFormerModelLoader`, `1599 MelBandRoFormerSampler`, and
`1616 ComfySwitchNode`. This branch loads and trims the song, optionally
isolates its lead vocal, and selects the timed guide track consumed by every
retained video segment.

**Removal and inquiry.** Delete the shared vocal-guide source and its incident
links. Segment generation remains, but none of the sections receives the
performance timing track.

> I want to add back the option that isolates the lead vocal from my song and uses that track to guide every generated segment. Right now the music-video sections receive no timed vocal guide, so the visuals no longer follow the performance.

**Verification note.** The ready golden exported with 202 nodes and 326 links;
the five-node slice removes exactly with zero dangling endpoints.

## M-19: LTX-2.3 visual-and-motion guidance slice

**Source.** Ready template `video/ltx2_3_lightricks_iclora_hdr`. Modern family:
LTX-2.3 ICLoRA HDR. Category: reference-guided video generation.

**The slice (5 nodes).** `5111 SimpleMath+`, `5112 ResizeImageMaskNode`,
`5029 GetImageSize`, `3059 EmptyLTXVLatentVideo`, and
`5012 LTXAddVideoICLoRAGuide`. The branch derives the guide dimensions,
normalizes the retained guide frames, creates the matching latent canvas, and
injects their appearance and timing into the retained conditioning/sampling
path.

**Removal and inquiry.** Delete the complete reference-guidance branch. The
prompt-driven sampler remains, giving a plausible prompt-only fault.

> I want to add the visual-and-motion guidance branch back. The workflow should prepare my guide footage at the generation size and use its look and timing to shape the result, instead of falling back to prompt-only motion.

**Verification note.** The ready golden exported with 24 nodes and 37 links;
the exact five-node slice removes without dangling links.

## M-20: Wan camera-reframing slice

**Source.** Ready template `video/wanvideo_wrapper_13b_recammaster`. Modern
family: Wan ReCamMaster. Category: camera-controlled video reframing.

**The slice (5 nodes).** `205 WanVideoReCamMasterDefaultCamera`,
`56 WanVideoReCamMasterCameraEmbed`, `138 ReCamMasterPoseVisualizer`,
`139 PreviewImage`, and `74 WidgetToString`. Together these nodes provide the
selected camera trajectory, embed it for the retained generator, visualize its
path, and expose a readable output label.

**Removal and inquiry.** Remove the five camera-control nodes and incident
links. Source video and text conditioning remain, but no trajectory reaches
generation and its preview/label are gone.

> I want to add the camera-motion controls back. The generated shot should follow my chosen camera trajectory again, and I also need the trajectory preview and readable label restored without changing the source clip or prompt.

**Verification note.** The ready golden exported with 23 nodes; all five IDs
resolve, remove atomically, and leave no dangling endpoints.

## Implementation spec

### 1. Represent cases explicitly

Add a campaign-only immutable `FeatureSubgraphSpec` (name illustrative) with:

- case ID, source kind (`ready` or `corpus`) and source locator;
- public `feature_key`, modality, family, and leak-safe inquiry;
- explicit verified removal node IDs plus expected types;
- primary semantic roles and surviving boundary roles;
- captured/expected inbound, internal, and outbound edge descriptions;
- an optional, explicit fault-bypass plan; and
- minimum node count, resolvability, golden-validation, and output checks.

Do not discover these slices by broadening `_FEATURE_RULES`. The explicit IDs
define the regression fixture; the public inquiry defines the product intent.

The campaign wiring should be a new list/mode, for example:

```python
MULTINODE_WORKFLOWS = [
    ("M-01", "ready", "image/qwen_image_2512", "lightning_acceleration"),
    ("M-02", "ready", "edit/flux2_klein_9b_image_edit_base", "second_reference"),
    ("M-03", "corpus", "external_workflows/corpus/7952d606da990a99.json", "pose_controlnet"),
    ("M-04", "ready", "video/wanvideo_wrapper_22_5b_t2v_controlnet", "depth_controlnet"),
    ("M-05", "ready", "video/ltx2_3_lightricks_two_stage", "latent_refinement"),
    ("M-06", "ready", "video/wanvideo_wrapper_22_s2v_framepack_pose", "performance_pose"),
    ("M-07", "ready", "video/ltx2_3_lightricks_first_last_parity", "last_frame_guide"),
    ("M-08", "ready", "video/ltx2_3_runexx_video_to_video_extend", "continuation_assembly"),
    ("M-09", "corpus", "external_workflows/corpus/430a3f936f6235f5.json", "audio_guidance_remix"),
    ("M-10", "ready", "audio/ace_step_1_5_t2a_song", "song_generation_head"),
    ("M-11", "ready", "image/flux2_klein_9b_gguf_t2i", "quantized_generation_head"),
    ("M-12", "ready", "edit/qwen_image_edit", "source_guided_editing"),
    ("M-13", "corpus", "external_workflows/corpus/8009c7ed72fd98a9.json", "accelerated_audio_conditioning"),
    ("M-14", "ready", "video/wanvideo_wrapper_22_5b_ovi_audio_i2v", "synchronized_soundtrack"),
    ("M-15", "ready", "video/wanvideo_wrapper_22_14b_vace_cocktail", "guided_transition"),
    ("M-16", "ready", "video/wanvideo_wrapper_21_14b_v2v_infinitetalk", "speech_performance"),
    ("M-17", "ready", "video/wan22_animate_native_first_stage", "subject_isolation"),
    ("M-18", "ready", "video/ltx2_3_runexx_music_video_low_ram", "vocal_segment_guidance"),
    ("M-19", "ready", "video/ltx2_3_lightricks_iclora_hdr", "reference_motion_guidance"),
    ("M-20", "ready", "video/wanvideo_wrapper_13b_recammaster", "camera_reframing"),
]
```

The actual node IDs/types and boundary plans should live in typed specs keyed by
case ID, not in the grader. Corpus registration must first export a schema'd UI
golden; skip with a fixture error if any selected class/edge does not resolve.

### 2. Replace sequential node removal with atomic subgraph removal

Generalize `_remove_feature_fault` with a
`remove_feature_subgraph(golden, spec)` path:

1. Preflight that the explicit ID set has at least five unique nodes and exact
   expected types, all classes resolve, and all declared boundary/internal
   edges exist.
2. Capture internal edges and cut edges before mutation.
3. Delete the complete node set and every incident link atomically. Do not call
   the existing one-node rerouter N times: an internal node chosen as “first
   incoming source” may itself be deleted, and that heuristic is not
   type/role-safe.
4. Rebuild every surviving `inputs[*].link` and `outputs[*].links` collection
   from the remaining global links, then run the existing orphan-reference
   scrub.
5. Apply only the case-declared bypasses, after verifying source/target socket
   compatibility. A missing bypass is allowed for a deliberately incomplete
   authoring graph such as M-10; an invented arbitrary bypass is not.
6. Prove fault locality: selected nodes are absent, no link has a missing
   endpoint, unrelated nodes/widgets/public I/O are unchanged, and the intended
   feature boundary is open or explicitly bypassed.

Return removal provenance (removed IDs/types, internal edges, cut edges, applied
bypasses) as harness evidence. Do not include it in the fixer prompt.

### 3. Derive a fresh-ID-tolerant subgraph repair contract

`derive_repair_delta` already emits multiple `AddNodeOp`s and missing links, but
its current `_additive_witness_locus` explicitly assumes the peer survives.
That cannot represent an edge between two freshly re-added nodes.

Add one grouped `additive_subgraph_witness` locus:

- assign each removed golden node an internal symbol;
- describe internal edges with symbol-to-symbol endpoints;
- describe boundary edges with a symbol on the new side and the surviving node
  ID plus named socket/type on the stable side;
- find one injective symbol-to-candidate-ID mapping, so repeated node types
  cannot be satisfied by one candidate or by inconsistent scattered witnesses;
- apply the complete mapping when checking paths to outputs; and
- keep canonical full-subgraph equality only as an exact-restore diagnostic or
  safe fallback, not as the practical product verdict.

For alternative implementations, mechanically derive generic evidence from
the candidate component and boundaries rather than requiring all golden
symbols/types. The repair delta is regression evidence; it is not a hidden
prescription sent to the fixer.

### 4. Grade functionality, not node identity

Extend `predicates.py` with a grouped hard floor. In practical mode it should
require:

- at least one intended primary feature role is present in the newly added
  connected component;
- that role is wired through the correct surviving boundary role and lies on
  an active path to the intended output;
- every added node on that component resolves, link/socket types are
  compatible, explicitly required inputs are satisfied, and no dangling/dead
  parallel branch is being offered as the “repair”;
- UI-to-API conversion/queue validation succeeds and an intended output is
  reachable; and
- the collateral fence shows unrelated graph regions were preserved.

“At least one intended feature node” is a floor, not a complete verdict. It
prevents a hard-coded golden topology from rejecting legitimate alternatives,
while the boundary/path checks prevent a token feature node or preview-only
branch from passing.

Pass candidate-only evidence to `additive_judge.py`: public inquiry/feature
intent, reconstructed component types/IDs/settings, named internal/boundary
wiring, conversion/output evidence, and runtime status. Never serialize the
golden node list or golden widget values. The LLM judge decides:

- `accepted`: functionality is restored and practically equivalent;
- `alternative_repair`: functionality works but makes a meaningful different
  implementation/settings choice; or
- `rejected`: the intended effect is absent, incorrectly placed, incomplete,
  or not runnable.

Ground the explanation in primary roles and boundary paths, not a demand to
recite every internal node. Offline conversion must be labeled
`runtime_unverified`; only a real bounded execution may be called executed. If
the LLM is unavailable, only a complete canonical grouped match may receive a
positive fallback; a minimal-floor-only candidate should remain undetermined or
rejected.

### 5. Required regression tests

- atomic removal with added-to-added internal edges and no dangling socket
  references;
- all reconstructed IDs changed;
- duplicate-type nodes require an injective mapping;
- partial reconstruction, split witnesses, wrong socket roles, and dead
  parallel feature branches reject;
- declared bypasses are type-compatible and unrelated branches are unchanged;
- an alternative topology that satisfies the same semantic boundary can reach
  `alternative_repair`;
- corpus cases fail fixture preflight when schema export or class resolution is
  unavailable; and
- judge outage cannot promote a merely minimal hard-floor pass.

### 6. Risks and anti-gaming constraints

The highest-risk area is grading: exact golden topology rejects valid
alternatives, while a loose “one feature type exists” check admits dead or
partial branches. The grouped component/boundary contract plus qualitative
judge is the recommended middle: deterministic structural/runnability floor,
semantic equivalence above it.

Other risks are duplicate class types, loader roots with no incoming boundary,
source/terminal slices that cannot be bypassed, and output reachability that
remaps only one fresh node. Treat fault-generation failure as a fixture failure,
not a fixer failure.

Do not expose removed node IDs/types, filenames, model names, schedules, widget
vectors, or hidden boundary answers in the inquiry/fixer prompt. Do not add
case-specific class-name checks to the generic grader, broaden substring
matchers to improve scores, or require exact values merely because the golden
contains them. Priors from ready templates/corpus may guide the fixer, but they
are evidence rather than prescriptions. The northstar remains: valid,
correctly wired, runnable functionality restored.
