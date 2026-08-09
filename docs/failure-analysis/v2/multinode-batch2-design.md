# Additive-multinode campaign batch 2: M-21–M-40

## Method and evidence

This batch uses 10 ready templates and 10 normalized corpus workflows. Every slice was loaded through the campaign's real `_golden_for_multinode` path, checked for at least five unique string IDs, and exercised through `_remove_subgraph_fault`. Topology, IDs, and classes come only from the local workflow artifacts.

Hivemind was reachable and used for realism rather than wiring. Representative community evidence includes requests and workflows for [two-stage latent upscaling](https://discord.com/channels/1076117621407223829/1326228588088786996/1531870672752480267), [frame interpolation plus upscaling](https://discord.com/channels/1076117621407223829/1518909953245581322/1525127011352318023), [voice cloning](https://discord.com/channels/1076117621407223829/1145677539738665020/1530013526125711432), [motion transfer with additional image guidance](https://discord.com/channels/1076117621407223829/1309520535012638740/1523514923194253353), [masked differential inpainting](https://cdn.discordapp.com/attachments/1268951088078258350/1346889676157616221/flux_fill_inpaint_Auto_crop.json), [outpainting](https://cdn.discordapp.com/attachments/1145677539738665020/1436439922914365581/Qwen_Image_Inpaint_2025.11.03.json), [multi-speaker audio-driven video](https://cdn.discordapp.com/attachments/1342763350815277067/1410839279881687150/Nunchaku_InfiniteTalk.json), and [LoRA stacking](https://discord.com/channels/1076117621407223829/1342763350815277067/1389425412433772574).

### M-21 — `distilled_preview_branch`

- Locator: `image/flux2_klein_4b_t2i`
- Feature: A separate fast, distilled render for prompt iteration alongside the regular-quality result.
- Why realistic: Artists routinely keep a low-step preview branch before committing to slower renders; Hivemind discusses [four-step second passes](https://discord.com/channels/1076117621407223829/1309520535012638740/1531895781458706512).
- Slice: `13 KSamplerSelect`; `14 Flux2Scheduler`; `15 EmptyFlux2LatentImage`; `16 UNETLoader`; `17 CLIPLoader`; `18 VAELoader`; `19 RandomNoise`; `20 CLIPTextEncode`; `21 ConditioningZeroOut`; `22 CFGGuider`; `23 SamplerCustomAdvanced`; `24 VAEDecode`.
- Inquiry: “The regular-quality render still works, but I have lost the quick distilled preview I used for rapid prompt iteration. Please restore that fast alternate render without changing the prompt or canvas size.”

### M-22 — `primary_subject_reference`

- Locator: `edit/flux2_klein_4b_image_edit_base`
- Feature: Restore the main subject photograph as identity, pose, and framing guidance while retaining an auxiliary style/environment reference.
- Why realistic: Multi-reference edits often separate subject identity from scene or style; users explicitly seek working [reference-image workflows](https://discord.com/channels/1076117621407223829/1457981813120176138/1509239349961687160).
- Slice: `76 LoadImage`; `23 ImageScaleToTotalPixels`; `28 VAEEncode`; `32 ReferenceLatent`; `33 ReferenceLatent`.
- Inquiry: “The auxiliary room and style reference still influences the edit, but the original subject photo no longer anchors the person's identity, pose, or framing. Please restore the primary-reference guidance while keeping the second image and instruction intact.”

### M-23 — `object_reference_insertion`

- Locator: `edit/flux2_klein_9b_image_edit_distilled`
- Feature: Transfer a supplied object into a character edit without losing the primary subject.
- Why realistic: Product placement and prop transfer are common multi-reference editing tasks; the local template dedicates a complete independent reference-conditioning branch to the object.
- Slice: `121 LoadImage`; `18 ImageScaleToTotalPixels`; `28 VAEEncode`; `34 ReferenceLatent`; `35 ReferenceLatent`.
- Inquiry: “The character edit still follows the main photo, but the specific object I supplied is no longer transferred into her hands. Please restore the object-reference branch while keeping the character, pose, and instruction unchanged.”

### M-24 — `synthetic_voice_clone`

- Locator: `video/ltx2_3_runexx_talking_avatar_qwen_tts`
- Feature: Clone a reference voice, clean the synthesized speech, preview it, and drive the talking avatar with the new line.
- Why realistic: Voice-copying is an active user workflow, including direct discussion of [preferred voice cloners](https://discord.com/channels/1076117621407223829/1145677539738665020/1530013526125711432).
- Slice: `1937 MelBandRoFormerModelLoader`; `1936 MelBandRoFormerSampler`; `1944 AILab_Qwen3TTSVoiceClone`; `1904 AudioEnhancementNode`; `1943 PreviewAudio`.
- Inquiry: “The talking avatar is using the reference recording itself again instead of speaking my new line in the cloned voice. Please restore the voice-copying and cleanup path, including an audio preview, without changing the portrait or script.”

### M-25 — `lip_region_masking`

- Locator: `video/ltx2_3_runexx_lipsync_custom_audio`
- Feature: Build and preview a stable face-region mask so speech-driven changes stay around the mouth instead of affecting the whole frame.
- Why realistic: Localized lip-sync avoids collateral motion and identity drift; community practice similarly combines masks with audio/video conditioning.
- Slice: `714 GetImageRangeFromBatch`; `717 ResizeImageMaskNode`; `720 LTXVPreprocessMasks`; `761 FaceSegment`; `763 PreviewImage`; `775 GetImageRangeFromBatch`; `790 BlockifyMask`; `791 MaskToImage`; `794 LTXVSetVideoLatentNoiseMasks`.
- Inquiry: “Lip-sync is affecting the whole frame instead of staying around the speaker's face and mouth. Please restore the stable face-region mask and its preview so the supplied speech only drives the intended area.”

### M-26 — `midpoint_keyframe`

- Locator: `video/ltx2_3_runexx_first_middle_last_frame`
- Feature: Add a timed middle composition anchor between existing first and last frames.
- Why realistic: Users ask for first, middle, and last insertion to control motion between anchors; Hivemind records discussion of [multiple in-between frames](https://discord.com/channels/1076117621407223829/1309520535012638740/1531835406369423391).
- Slice: `47 LoadImage`; `48 ImageResizeKJv2`; `49 ResizeImagesByLongerEdge`; `2174 LTXVPreprocess`; `2216 SimpleCalculatorKJ`; `2221 LTXVAddGuideMulti`.
- Inquiry: “The clip still starts and ends on my chosen images, but it no longer passes through the composition I supplied for the middle. Please restore that timed midpoint keyframe without changing the endpoints or duration.”

### M-27 — `third_segment_extension`

- Locator: `video/ltx2_3_iamccs_audio_extend_low_ram`
- Feature: Generate the third timed continuation segment, decode it to disk, and append it to a low-memory long-form video.
- Why realistic: Long audio-driven videos must be chunked under memory limits; losing one continuation segment is a concrete production failure rather than an arbitrary node gap.
- Slice: `46 EmptyLTXVLatentVideo`; `48 IAMCCS_AudioExtensionMath`; `49 IAMCCS_AudioExtender`; `50 LTXVAudioVAEEncode`; `51 SetLatentNoiseMask`; `58 IAMCCS_AudioTimelineGate`; `47 IAMCCS_StartDirToVideoLatent`; `52 LTXVConcatAVLatent`; `53 RandomNoise`; `54 SamplerCustomAdvanced`; `55 LTXVSeparateAVLatent`; `62 IAMCCS_VAEDecodeToDisk`; `57 IAMCCS_LTX2_ExtensionModule_Disk`.
- Inquiry: “My low-memory extension now stops after the second section, so the last part of the song never gets a matching continuation. Please restore the third timed segment and append it into the finished long video.”

### M-28 — `object_trajectory_control`

- Locator: `video/wanvideo_wrapper_21_14b_wanmove_i2v`
- Feature: Apply a drawn path to the subject and overlay the path on preview and result.
- Why realistic: Motion transfer users want controllable subject-specific movement in addition to broad guide motion; Hivemind records this [combined-guidance need](https://discord.com/channels/1076117621407223829/1309520535012638740/1523514923194253353).
- Slice: `80 WanVideoAddWanMoveTracks`; `88 WanVideoWanDrawWanMoveTracks`; `90 VHS_VideoCombine`; `91 RepeatImageBatch`; `81 WanVideoWanDrawWanMoveTracks`.
- Inquiry: “The image still animates, but the subject ignores the path I drew and neither preview nor output shows the motion track anymore. Please restore the trajectory-guided movement and track overlays.”

### M-29 — `high_fps_motion_finish`

- Locator: `video/wanvideo_wrapper_22_s2v_context_window`
- Feature: Trim startup frames, interpolate motion, select the final cadence, and package a smooth 24-fps deliverable.
- Why realistic: A user specifically recommends [frame interpolation and upscaling for smoothness and detail](https://discord.com/channels/1076117621407223829/1518909953245581322/1525127011352318023).
- Slice: `80 VHS_SplitImages`; `95 DownloadAndLoadGIMMVFIModel`; `96 GIMMVFI_interpolate`; `102 VHS_SelectEveryNthImage`; `30 VHS_VideoCombine`.
- Inquiry: “I still get the basic speech video, but the polished version is gone: it should drop the startup frames, smooth the motion, and export at 24 fps. Please restore that finishing path while keeping the original audio.”

### M-30 — `low_noise_handoff`

- Locator: `video/wanvideo_wrapper_22_14b_i2v_kijai`
- Feature: Hand first-pass latents to a dedicated low-noise model and adapter for the fine-detail finishing phase.
- Why realistic: Two-stage generation is established practice; Hivemind describes generating high noise at low resolution, then [upscaling and completing the low-noise phase](https://discord.com/channels/1076117621407223829/1326228588088786996/1531870672752480267).
- Slice: `8 WanVideoModelLoader`; `11 WanVideoLoraSelect`; `17 WanVideoSetBlockSwap`; `20 WanVideoSetLoRAs`; `24 WanVideoSampler`.
- Inquiry: “The image-to-video render stops after the coarse first phase now, so fine detail and stability are noticeably worse. Please restore the dedicated low-noise finishing pass without changing my seed, prompt, or dimensions.”

### M-31 — `style_reference_conditioning`

- Locator: `external_workflows/corpus/7cf357a55e5fab05.json`
- Feature: Encode a reference image and combine its visual style with the normal text conditioning over a controlled timestep range.
- Why realistic: Reference styling is a common way to preserve a look without replacing the text prompt; the local graph retains a clean prompt-only bypass when the feature is removed.
- Slice: `12 StyleModelApply`; `13 StyleModelLoader`; `14 CLIPVisionLoader`; `15 CLIPVisionEncode`; `16 LoadImage`; `27 ConditioningSetTimestepRange`; `29 ConditioningCombine`.
- Inquiry: “My prompt still works, but the result no longer picks up the look of my style reference. Please restore the reference-style guidance without changing the base model or canvas.”

### M-32 — `feathered_seam_cleanup`

- Locator: `external_workflows/corpus/02d7ea587fb70e40.json`
- Feature: Feather the outpaint border, apply a masked resampling pass, preview the mask, and save the cleaned result.
- Why realistic: Outpaint borders commonly need a second cleanup pass; Hivemind contains a real [inpaint/outpaint workflow with latent noise masking and compositing](https://cdn.discordapp.com/attachments/1145677539738665020/1436439922914365581/Qwen_Image_Inpaint_2025.11.03.json).
- Slice: `79 SolidMask`; `80 SolidMask`; `81 MaskComposite`; `82 KSampler`; `83 VAEDecode`; `84 SetLatentNoiseMask`; `85 FeatherMask`; `86 SaveImage`; `87 MaskToImage`; `88 PreviewImage`.
- Inquiry: “The first outpaint still appears, but the border seam is no longer feathered and resampled into a clean final image. Please restore that edge-cleanup pass and its mask preview.”

### M-33 — `background_replacement`

- Locator: `external_workflows/corpus/e343e3b050e4c6a9.json`
- Feature: Grow and inspect an existing subject mask, composite the subject over a clean background, and preview the replacement.
- Why realistic: Cutout cleanup and recomposition is a standard post-segmentation feature, and keeping the raw input path as a bypass makes the broken workflow remain useful.
- Slice: `100 GrowMaskWithBlur`; `95 MaskToImage`; `99 MaskToImage`; `98 SolidMask`; `96 ImageCompositeMasked`; `103 PreviewImage`.
- Inquiry: “The subject cutout is still available, but it is no longer cleaned up, placed over a fresh background, or shown for review before generation. Please restore that background-replacement composition while keeping the source video unchanged.”

### M-34 — `stacked_control_guidance`

- Locator: `external_workflows/corpus/7567d20f91a2d6b5.json`
- Feature: Chain three independent structural guides before sampling while retaining prompt-only generation as a bypass.
- Why realistic: People combine static frames with structural guidance despite the tension between them; Hivemind explicitly discusses [that combined-control use case](https://discord.com/channels/1076117621407223829/1309520535012638740/1531839766411087933).
- Slice: `6 ControlNetLoader`; `7 ControlNetLoader`; `8 ControlNetLoader`; `10 ControlNetApplyAdvanced`; `21 ControlNetApplyAdvanced`; `23 ControlNetApplyAdvanced`.
- Inquiry: “My reference image still loads, but the render no longer combines the three structural guides I used to control its composition and detail. Please restore that layered guidance stack while keeping the prompt and sampler settings intact.”

### M-35 — `upscaler_comparison`

- Locator: `external_workflows/corpus/f0abffc2b525515c.json`
- Feature: Produce and save three additional model-upscaled alternatives next to the surviving baseline upscale.
- Why realistic: Upscalers trade prompt/detail fidelity differently, and Hivemind users describe switching to an [upscale step to preserve adherence](https://discord.com/channels/1076117621407223829/1518909953245581322/1531607167076012122).
- Slice: `18 UpscaleModelLoader`; `19 ImageUpscaleWithModel`; `20 SaveImage`; `21 UpscaleModelLoader`; `22 ImageUpscaleWithModel`; `23 SaveImage`; `24 UpscaleModelLoader`; `25 ImageUpscaleWithModel`; `26 SaveImage`.
- Inquiry: “Only my first enlarged image is being produced now. Please restore the other three model-based upscale alternatives and save each result so I can compare which one preserves the source best.”

### M-36 — `second_speaker_turn`

- Locator: `external_workflows/corpus/2e93a5af34d6d96c.json`
- Feature: Encode a second voice, generate its matching performance, concatenate both voice turns, and assemble the two video portions.
- Why realistic: Hivemind includes complete [multi-talk audio-driven video](https://cdn.discordapp.com/attachments/1342763350815277067/1410839279881687150/Nunchaku_InfiniteTalk.json) workflows rather than only single-speaker lip-sync.
- Slice: `90 LoadAudio`; `116 Reroute`; `93 AudioEncoderEncode`; `130 WanInfiniteTalkToVideo`; `122 CFGGuider`; `123 SamplerCustomAdvanced`; `124 VAEDecode`; `126 ImageFromBatch`; `127 ImageBatch`; `128 VHS_VideoCombine`; `113 AudioConcat`.
- Inquiry: “The first speaker still talks, but the second voice and its matching performance have vanished, and the finished clip no longer contains both turns. Please restore the second-speaker branch and join both voices into the output.”

### M-37 — `precision_face_mask`

- Locator: `external_workflows/corpus/c44e118d5940e1bc.json`
- Feature: Convert detected facial coordinates into a tracked segmentation, draw the overlay, grow the mask, and blockify it for stable animation.
- Why realistic: Precise face-only masking prevents edits from bleeding into hair, clothing, and background; this is a distinct refinement over the surviving rough pose-keypoint mask.
- Slice: `256 Florence2toCoordinates`; `257 DownloadAndLoadSAM2Model`; `253 Sam2Segmentation`; `254 DrawMaskOnImage`; `259 GrowMask`; `238 BlockifyMask`.
- Inquiry: “The rough face region is still detected, but it no longer becomes a precise tracked mask with a visible overlay and stable block edges. Please restore that refined face masking so the animation stays confined to the intended face.”

### M-38 — `differential_inpaint`

- Locator: `external_workflows/corpus/dc3e44e987def366.json`
- Feature: Load and resize a source, soften/remap its mask, encode the masked latent, and composite the regenerated patch back.
- Why realistic: This directly matches a Hivemind [Flux differential-diffusion inpainting workflow](https://cdn.discordapp.com/attachments/1268951088078258350/1346889676157616221/flux_fill_inpaint_Auto_crop.json).
- Slice: `144 LoadImage`; `149 RemapMaskRange`; `146 GrowMaskWithBlur`; `142 VAEEncodeForInpaint`; `154 ImageResizeKJ`; `156 GrowMaskWithBlur`; `155 ImageCompositeMasked`.
- Inquiry: “The prompt-only image path still works, but I can no longer load a picture, soften its mask, repaint just that area, and composite the patch back into the original. Please restore the localized inpainting path without changing my prompt.”

### M-39 — `lora_stack_export`

- Locator: `external_workflows/corpus/0b47c66d3fc67c4e.json`
- Feature: Apply five ordered style/motion LoRAs to a base video model before saving the merged result.
- Why realistic: A community user explicitly says they will keep using a [LoRA stack workflow](https://discord.com/channels/1076117621407223829/1342763350815277067/1389425412433772574).
- Slice: `414 LoraLoaderModelOnly`; `416 LoraLoaderModelOnly`; `417 LoraLoaderModelOnly`; `418 LoraLoaderModelOnly`; `419 LoraLoaderModelOnly`.
- Inquiry: “The base video model still loads and can be saved, but the five style and motion adapters are no longer layered into it first. Please restore that ordered LoRA stack so the exported model includes the combined look.”

### M-40 — `automatic_audio_prompt_expansion`

- Locator: `external_workflows/corpus/c953dfc7fcf7520b.json`
- Feature: Expand a plain music request into a richer duration-aware prompt, extract and clean the generated text, and preview it while retaining the manual prompt fallback.
- Why realistic: Assisted prompt expansion is a useful optional authoring branch for detailed song structure; the surviving manual path makes this a genuinely additive capability.
- Slice: `61 CLIPLoader`; `64 ComfyMathExpression`; `65 PreviewAny`; `66 StringReplace`; `67 TextGenerate`; `69 CustomCombo`; `70 JsonExtractString`; `71 StringReplace`; `72 StringReplace`; `77 PreviewAny`.
- Inquiry: “My plain music description still works, but the option that expands it into a richer duration-aware generation prompt and shows me the cleaned result has disappeared. Please restore that assisted prompt path.”
