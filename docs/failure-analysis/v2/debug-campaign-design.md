# Realistic debugging campaign design

## Purpose and selection standard

These ten cases test diagnosis of plausible single user mistakes in intact
workflows. They come from the local Hivemind-backed `ready_templates/` cache and
load through the campaign's schema-aware `_golden_for()` path. No case removes a
feature. Each complaint reports only a user-visible regression; exact nodes,
values, models, files, sockets, and repairs remain outside the fixer prompt.

| Case | Modality | Model family | Fault |
|---|---|---|---|
| D-01 | image | Qwen Image 2512 | one width value mistyped |
| D-02 | image | Flux.2 Klein 9B | guidance accidentally zeroed |
| D-03 | image edit | Qwen Image Edit | conditioning cables crossed |
| D-04 | multi-reference edit | Flux.2 Klein 9B | duplicate reference latent |
| D-05 | text-to-video | LTX-2.3 | first-pass steps reduced to one |
| D-06 | audiovisual video | LTX-2.3 | final sound link disconnected |
| D-07 | controlled i2v | Wan 2.2 5B | raw guide bypasses depth map |
| D-08 | speech-to-video | Wan 2.2 S2V | export frame rate mistyped |
| D-09 | music | ACE-Step 1.5 | duration shortened to a fragment |
| D-10 | speech | Qwen3 TTS | wrong language selected |

## D-01: Qwen Image narrow canvas

**Workflow locator.** Ready template `image/qwen_image_2512`, sourced from
`ready_templates/sources/official/image/qwen_image_2512.json`.

**Modality/model.** Text-to-image; Qwen Image 2512.

**Bug.** On node `70` (`EmptySD3LatentImage`), change
`widgets_values[0]` from `1328` to `256`; leave the height unchanged.

**Inquiry (verbatim).**

> Pictures still render, but they suddenly come out extremely narrow and lose horizontal detail while the vertical dimension looks normal.

**Expected fix.** Restore node `70` width to `1328`.

**Why realistic.** Width and height sit side by side, so editing the wrong field
or dropping a digit produces a valid but visibly distorted render.

## D-02: Flux.2 prompt guidance lost

**Workflow locator.** Ready template `image/flux2_klein_9b_t2i`, sourced
from `ready_templates/sources/official/image/flux2_klein_9b_t2i.json`.

**Modality/model.** Text-to-image; Flux.2 Klein 9B.

**Bug.** On node `10` (`CFGGuider`), change `widgets_values[0]` from `5`
to `0.0`.

**Inquiry (verbatim).**

> Strong prompt changes barely affect the result now. Every render looks flat and generic, as though the text has almost no influence.

**Expected fix.** Restore node `10` guidance to `5`.

**Why realistic.** A slider reset or typed zero preserves a runnable graph while
making prompt adherence collapse.

## D-03: Qwen edit conditioning polarity crossed

**Workflow locator.** Ready template `edit/qwen_image_edit`, sourced from
`ready_templates/sources/official/edit/qwen_image_edit.json`.

**Modality/model.** Instruction-driven image edit; Qwen Image Edit.

**Bug.** Swap the sources of the two connected inputs on node `13`
(`KSampler`): link `11` changes from `6:0 -> 13:5` to `7:0 -> 13:5`,
and link `12` changes from `7:0 -> 13:4` to `6:0 -> 13:4`. Targets and
link IDs remain intact.

**Inquiry (verbatim).**

> My edit has started doing the opposite of what I ask: unwanted elements stay prominent while protected parts of the source get disturbed.

**Expected fix.** Restore `6:0 -> 13.positive` and
`7:0 -> 13.negative`.

**Why realistic.** The adjacent same-typed conditioning sockets accept either
cable, so a drag-and-drop swap remains structurally valid.

## D-04: Flux.2 second reference duplicates the first

**Workflow locator.** Ready template
`edit/flux2_klein_9b_image_edit_base`, sourced from
`ready_templates/sources/official/edit/flux2_klein_9b_image_edit_base.json`.

**Modality/model.** Multi-reference image edit; Flux.2 Klein 9B.

**Bug.** Remove golden link `40` (`29:0 -> 34:0`) and create link `58`
from `28:0 -> 34:0`. This makes both reference-conditioning stages consume the
main reference latent.

**Inquiry (verbatim).**

> The extra reference stopped contributing to the edit. The result keeps echoing the main photo and misses the visual details supplied in the other reference.

**Expected fix.** Restore `29:0 -> 34.latent`.

**Why realistic.** Two same-typed, nearby encoded references are easy to confuse
during cable cleanup, and the graph still runs.

## D-05: LTX first pass reduced to one step

**Workflow locator.** Ready template `video/ltx2_3_t2v`, sourced from
`ready_templates/sources/custom_nodes/ltxvideo/ltx2_3_single_stage_distilled_full.json`.

**Modality/model.** Text-to-video with generated audio; LTX-2.3.

**Bug.** On node `4966` (`LTXVScheduler`), change `widgets_values[0]`
from `15` to `1`.

**Inquiry (verbatim).**

> Clips finish suspiciously fast, but the frames are mostly incoherent flicker and noise with no stable scene or motion.

**Expected fix.** Restore node `4966` steps to `15`.

**Why realistic.** A step-count typo makes the run unusually fast and visibly
under-sampled without damaging the graph.

## D-06: LTX final sound cable disconnected

**Workflow locator.** Ready template
`video/ltx2_3_lightricks_two_stage`, sourced from
`ready_templates/sources/custom_nodes/ltxvideo/lightricks_2_3/LTX-2.3_T2V_I2V_Two_Stage_Distilled.json`.

**Modality/model.** Two-stage audiovisual video; LTX-2.3.

**Bug.** Remove link `26`, `4848:0 -> 4849.audio`, clear that target
input's link reference, and prune the source output's link reference. All video
connections remain unchanged.

**Inquiry (verbatim).**

> The picture track saves normally, but the finished clip is silent even though sound is produced earlier in the workflow.

**Expected fix.** Reconnect `4848:0 -> 4849.audio`.

**Why realistic.** Optional sound inputs allow a clip to save successfully after
one cable is missed while rearranging the graph.

## D-07: Wan control path receives raw frames

**Workflow locator.** Ready template
`video/wanvideo_wrapper_22_5b_i2v_controlnet`, sourced from
`ready_templates/sources/custom_nodes/wanvideo_wrapper/kijai/wan22_5b_i2v_controlnet.json`.

**Modality/model.** Depth-controlled image-to-video; Wan 2.2 5B.

**Bug.** Remove golden link `21` (`109:0 -> 105:2`) and create link `33`
from resized raw source `101:0 -> 105:2`.

**Inquiry (verbatim).**

> The guide clip still affects colors and textures, but the generated motion no longer follows its depth or camera layout. Structure drifts badly from the reference.

**Expected fix.** Restore `109:0 -> 105.control_images`.

**Why realistic.** Raw and processed guide streams share the same socket type
and run in parallel, so selecting the visually nearby raw cable is plausible.

## D-08: Wan speech clip exported at the wrong rate

**Workflow locator.** Ready template
`video/wanvideo_wrapper_22_s2v_context_window`, sourced from
`ready_templates/sources/custom_nodes/wanvideo_wrapper/kijai/wan22_s2v_context_window.json`.

**Modality/model.** Speech-to-video; Wan 2.2 S2V.

**Bug.** On node `30` (`VHS_VideoCombine`), change
`widgets_values[0]` from `24` to `4`.

**Inquiry (verbatim).**

> The saved clip now plays in slow motion and drifts out of sync with its soundtrack, even though the generated frames themselves look normal.

**Expected fix.** Restore node `30` frame rate to `24`.

**Why realistic.** Export rate is an ordinary editable field; a single missing
digit changes playback timing without changing generated frames.

## D-09: ACE-Step duration shortened

**Workflow locator.** Ready template `audio/ace_step_1_5_t2a_song`,
sourced from
`ready_templates/sources/official/audio/ace_step_1_5_t2a_song.json`.

**Modality/model.** Text-to-music; ACE-Step 1.5.

**Bug.** On node `122` (`EmptyAceStep1.5LatentAudio`), change
`widgets_values[0]` from `2.0` to `0.1`.

**Inquiry (verbatim).**

> The song begins correctly and then cuts off almost immediately, leaving only a tiny fragment instead of a usable track.

**Expected fix.** Restore node `122` duration to `2.0`.

**Why realistic.** Duration is a decimal field where a misplaced decimal point
creates a valid, recognizable truncation.

## D-10: Qwen speech language mismatch

**Workflow locator.** Ready template `audio/qwen3_tts_voice_design`,
sourced from
`ready_templates/sources/custom_nodes/qwen_tts/1038lab/qwen3_tts_voice_design.json`.

**Modality/model.** Designed-voice text-to-speech; Qwen3 TTS.

**Bug.** On node `1` (`AILab_Qwen3TTSVoiceDesign`), change
`widgets_values[3]` from `English` to `Chinese`.

**Inquiry (verbatim).**

> The narrator suddenly uses the wrong phonetics for the script; familiar names sound as if they belong to a different language, while the voice character itself is unchanged.

**Expected fix.** Restore node `1` language to `English`.

**Why realistic.** An adjacent dropdown selection preserves synthesis and voice
character while producing an immediately recognizable pronunciation regression.

## Offline registration gates

All ten locators must export non-empty `nodes` and `links`, apply exactly the
registered mutation, retain every unrelated node/widget/link, and produce a
non-empty repaired oracle locus. Inquiries are scanned case-insensitively
against their golden node types, nontrivial widget strings, input filenames,
model filenames, and sigma strings. Any match is a fixture failure, not a fixer
failure.
