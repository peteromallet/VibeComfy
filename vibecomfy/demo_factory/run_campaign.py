#!/usr/bin/env python3
"""Demo-scenario-factory campaign runner module.

Produces 20 test cases:
- 10 REPAIR scenarios: subtle/nefarious defects via creative engine
- 10 ADDITIVE scenarios: remove a functional subgraph, then ask fixer to ADD it back

Uses diverse workflows across modalities, workflow types, and modern models.

Run:
    python -m vibecomfy.demo_factory.run_campaign
"""
from __future__ import annotations

import argparse
import copy
import json
import sys
import warnings
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from vibecomfy.demo_factory.case import run_creative_case, Case, CaseStage, _new_case_id, _cases_dir, _baseline_gate, _fixer_gate, _evaluate, check_leakage, write_leakage_check, _run_fixer
from vibecomfy.demo_factory.creative import BugProposal, _find_feature_nodes, _strip_orphan_references, apply_bug, find_feature_node_ids, _node_matches_feature
from vibecomfy.demo_factory.deltas import FaultInjection, derive_repair_delta
from vibecomfy.cli_loader import load_workflow_any
from vibecomfy.porting.object_info.consume import get_class
from vibecomfy.registry.ready import workflow_from_ready
from vibecomfy.porting.emit.ui import emit_ui_json
from vibecomfy.demo_factory.cli import _export_ready_ui
from vibecomfy.schema import get_schema_provider


# Default campaign directory
DEFAULT_CAMPAIGN_DIR = Path("/Users/peteromalley/Documents/reigh-workspace/vibecomfy/out/demo-candidate-factory/20260723-001")

# Workflows for REPAIR scenarios (creative engine)
REPAIR_WORKFLOWS = [
    # Basic upscale (3 nodes)
    "image/basic_image_upscale",
    # Text-to-image
    "image/flux2_klein_9b_t2i",
    "image/z_image",
    # Image-to-image
    "image/z_image_img2img",
    # Image edit
    "edit/flux2_klein_9b_image_edit_base",
    # Text-to-video
    "video/ltx2_3_t2v",
    "video/wan_t2v",
    # Image-to-video
    "video/ltx2_3_i2v",
    "video/wan_i2v",
    # Audio
    "audio/qwen3_tts_custom_voice",
    "audio/ace_step_1_5_t2a_song",
]

# Workflows for ADDITIVE scenarios (remove feature)
ADDITIVE_WORKFLOWS = [
    # Remove upscale
    ("image/basic_image_upscale", "upscale"),
    # Remove refinement
    ("video/ltx2_3_lightricks_two_stage", "refinement_pass"),
    # Remove ControlNet (replaces mis-paired iclora case; feature verified present)
    ("video/wanvideo_wrapper_21_14b_fun_control", "controlnet"),
    # Remove audio merge
    ("video/ltx2_3_iamccs_audio_extend_low_ram", "audio_merge"),
    # Remove upscale (replaces mis-paired face_detailer case; feature verified present)
    ("image/z_image_img2img", "upscale"),
    # Remove LoRA
    ("video/wanvideo_wrapper_13b_control_lora", "lora_loader"),
    # More diverse
    ("video/ltx2_3_runexx_first_last_frame", "upscale"),
    ("video/basic_video_enhance", "upscale"),  # replaces mis-paired lora_loader case; feature verified present
    ("video/wanvideo_wrapper_21_14b_i2v", "refinement_pass"),
    ("edit/flux2_klein_9b_image_edit_distilled", "upscale"),
]


@dataclass(frozen=True)
class MultinodeWorkflow:
    case_id: str
    kind: str
    locator: str
    feature_key: str
    slice_node_ids: tuple[str, ...]
    inquiry: str
    primary_node_id: str
    bypasses: tuple[tuple[str, int, str, int, str], ...] = ()


# Explicit regression fixtures. The node IDs are intentionally not discovered
# through the broad single-node feature matcher.
MULTINODE_WORKFLOWS = [
    MultinodeWorkflow(
        "M-01", "ready", "image/qwen_image_2512", "lightning_acceleration",
        ("63", "71", "64", "72", "73"),
        "The fast Lightning path has disappeared. This Qwen workflow now behaves like the slow base model instead of the quick four-step setup I was using. Please restore the accelerated generation path without changing my prompt or output size.",
        "64",
        (("65", 0, "68", 3, "MODEL"),),
    ),
    MultinodeWorkflow(
        "M-02", "ready", "edit/flux2_klein_9b_image_edit_base", "second_reference",
        ("81", "18", "29", "34", "35"),
        "This edit is only paying attention to the main reference now. The second reference image has no influence on the result, even though I need both images to guide the edit. Please add that second-reference conditioning back without changing the sampler.",
        "34",
        (
            ("32", 0, "36", 1, "CONDITIONING"),
            ("33", 0, "36", 2, "CONDITIONING"),
        ),
    ),
    MultinodeWorkflow(
        "M-03", "corpus", "external_workflows/corpus/7952d606da990a99.json", "pose_controlnet",
        ("164", "172", "165", "167", "163"),
        "The pose guidance has disappeared: edits no longer follow the body pose in my second reference image. Please restore structural pose ControlNet guidance while keeping the Qwen edit setup and output dimensions unchanged.",
        "163",
        (
            ("158", 0, "157", 3, ""),
            ("161", 0, "157", 2, ""),
        ),
    ),
    MultinodeWorkflow(
        "M-04", "ready", "video/wanvideo_wrapper_22_5b_t2v_controlnet", "depth_controlnet",
        ("98", "101", "104", "109", "103", "105", "112"),
        "The depth ControlNet guidance has disappeared: the video still renders, but it ignores the structure and camera layout from my guide clip. Please restore that control-video path so the generated motion follows the reference depth again.",
        "105",
        (
            ("22", 0, "16", 1, "WANVIDEOMODEL"),
            ("22", 0, "27", 0, "WANVIDEOMODEL"),
        ),
    ),
    MultinodeWorkflow(
        "M-05", "ready", "video/ltx2_3_lightricks_two_stage", "latent_refinement",
        ("4967", "4974", "4976", "4985", "4964", "4975", "4970", "4969", "4971", "4973"),
        "Can you restore the second-stage LTX refinement? The video still generates, but it never gets the latent upscale and cleanup pass, so it looks softer and rougher than the two-stage result I had before.",
        "4973",
        (
            ("4845", 0, "4995", 0, "LATENT"),
            ("4845", 1, "4848", 1, "LATENT"),
        ),
    ),
    MultinodeWorkflow(
        "M-06", "ready", "video/wanvideo_wrapper_22_s2v_framepack_pose", "performance_pose",
        ("116", "110", "107", "111", "109"),
        "The speech-to-video clip still responds to the audio and portrait, but the character no longer follows the face performance from my guide video. Please restore that pose-guidance branch.",
        "109",
    ),
    MultinodeWorkflow(
        "M-07", "ready", "video/ltx2_3_lightricks_first_last_parity", "last_frame_guide",
        ("2", "12", "14", "20", "25"),
        "The video still starts from my opening image, but it no longer lands on the ending image I supplied. Please restore the last-frame target so the motion transitions into that frame.",
        "20",
        (
            ("19", 0, "21", 2, "CONDITIONING"),
            ("19", 1, "21", 1, "CONDITIONING"),
            ("19", 2, "22", 0, "LATENT"),
            ("24", 0, "27", 0, "LATENT"),
        ),
    ),
    MultinodeWorkflow(
        "M-08", "ready", "video/ltx2_3_runexx_video_to_video_extend", "continuation_assembly",
        ("306", "536", "394", "393", "403"),
        "The continuation is being generated, but it is no longer appended to the source video: there is no overlap blend, and the new audio is not joined to the original track. Please restore the finished video-extension assembly.",
        "536",
        (
            ("443", 0, "578", 0, "AUDIO"),
            ("443", 0, "627", 0, "AUDIO"),
            ("512", 0, "578", 1, "IMAGE"),
            ("512", 0, "627", 1, "IMAGE"),
        ),
    ),
    MultinodeWorkflow(
        "M-09", "corpus", "external_workflows/corpus/430a3f936f6235f5.json", "audio_guidance_remix",
        ("151", "148", "150", "156", "126", "179"),
        "The clean vocal carry-through is broken. The reference stem is still available, but it no longer drives the LTX audio latent and the generated soundtrack is not mixed back with it. Please restore the guided audio and final remix.",
        "179",
        (("153", 1, "166", 0, ""),),
    ),
    MultinodeWorkflow(
        "M-10", "ready", "audio/ace_step_1_5_t2a_song", "song_generation_head",
        ("122", "124", "47", "3", "123"),
        "The ACE-Step models still load, but the actual song-generation path is gone and nothing reaches the audio output. Please restore text-to-song generation so the prompt produces a finished, saveable track again.",
        "123",
    ),
    MultinodeWorkflow(
        "M-11", "ready", "image/flux2_klein_9b_gguf_t2i", "quantized_generation_head",
        ("4", "5", "7", "8", "10", "11", "12", "14"),
        "I want to add the low-memory prompt-to-picture path back. The canvas and output are still present, but there is no complete generation stage between them. Please restore that path without changing my prompt or output size.",
        "12",
    ),
    MultinodeWorkflow(
        "M-12", "ready", "edit/qwen_image_edit", "source_guided_editing",
        ("78", "6", "7", "8", "13", "14"),
        "I want to restore image-guided editing. My source picture no longer becomes guidance for a new result, so the workflow cannot carry out the requested edit. Please add that source-conditioning and generation stage back without changing my instruction or output size.",
        "13",
    ),
    MultinodeWorkflow(
        "M-13", "corpus", "external_workflows/corpus/8009c7ed72fd98a9.json", "accelerated_audio_conditioning",
        ("104", "78", "105", "94", "47"),
        "I want to restore the fast song-generation setup. The duration and output pieces remain, but my description no longer drives a finished track at the speed I had. Please add the accelerated prompt-to-audio path back without changing the composition request.",
        "78",
    ),
    MultinodeWorkflow(
        "M-14", "ready", "video/wanvideo_wrapper_22_5b_ovi_audio_i2v", "synchronized_soundtrack",
        ("125", "89", "90", "108", "88"),
        "I want to add the generated soundtrack path back. The render should produce synchronized sound from the same generation, let me audition it, and package it with the frames in the finished clip.",
        "125",
    ),
    MultinodeWorkflow(
        "M-15", "ready", "video/wanvideo_wrapper_22_14b_vace_cocktail", "guided_transition",
        ("4", "7", "8", "12", "13"),
        "I want to restore the guided transition I had: it used my opening picture, ending picture, and control clip together. Now those references no longer shape the transition. Please add that multi-reference guidance path back without changing the text prompt or output dimensions.",
        "13",
    ),
    MultinodeWorkflow(
        "M-16", "ready", "video/wanvideo_wrapper_21_14b_v2v_infinitetalk", "speech_performance",
        ("125", "137", "194", "270", "303", "304"),
        "I want to add the speech-driven performance path back. The reference clip still loads, but the speaker's mouth no longer follows the supplied voice and the exported result has lost that voice track. Please restore the sound-to-performance guidance without changing the visual prompt.",
        "194",
    ),
    MultinodeWorkflow(
        "M-17", "ready", "video/wan22_animate_native_first_stage", "subject_isolation",
        ("6", "19", "20", "21", "22", "23"),
        "I want to restore the subject-isolation step for character animation. I need to mark the person in the guide footage, expand that selection into a stable mask, preview it over the frames, and use it to keep the animation confined to that subject.",
        "23",
    ),
    MultinodeWorkflow(
        "M-18", "ready", "video/ltx2_3_runexx_music_video_low_ram", "vocal_segment_guidance",
        ("1594", "1598", "1600", "1599", "1616"),
        "I want to add back the option that isolates the lead vocal from my song and uses that track to guide every generated segment. Right now the music-video sections receive no timed vocal guide, so the visuals no longer follow the performance.",
        "1616",
    ),
    MultinodeWorkflow(
        "M-19", "ready", "video/ltx2_3_lightricks_iclora_hdr", "reference_motion_guidance",
        ("5111", "5112", "5029", "3059", "5012"),
        "I want to add the visual-and-motion guidance branch back. The workflow should prepare my guide footage at the generation size and use its look and timing to shape the result, instead of falling back to prompt-only motion.",
        "5012",
    ),
    MultinodeWorkflow(
        "M-20", "ready", "video/wanvideo_wrapper_13b_recammaster", "camera_reframing",
        ("205", "56", "138", "139", "74"),
        "I want to add the camera-motion controls back. The generated shot should follow my chosen camera trajectory again, and I also need the trajectory preview and readable label restored without changing the source clip or prompt.",
        "56",
    ),
    MultinodeWorkflow(
        "M-21", "ready", "image/flux2_klein_4b_t2i", "distilled_preview_branch",
        ("13", "14", "15", "16", "17", "18", "19", "20", "21", "22", "23", "24"),
        "The regular-quality render still works, but I have lost the quick distilled preview I used for rapid prompt iteration. Please restore that fast alternate render without changing the prompt or canvas size.",
        "24",
    ),
    MultinodeWorkflow(
        "M-22", "ready", "edit/flux2_klein_4b_image_edit_base", "primary_subject_reference",
        ("76", "23", "28", "32", "33"),
        "The auxiliary room and style reference still influences the edit, but the original subject photo no longer anchors the person's identity, pose, or framing. Please restore the primary-reference guidance while keeping the second image and instruction intact.",
        "33",
        (
            ("18", 0, "26", 0, "IMAGE"),
            ("25", 0, "34", 1, "CONDITIONING"),
            ("27", 0, "35", 1, "CONDITIONING"),
        ),
    ),
    MultinodeWorkflow(
        "M-23", "ready", "edit/flux2_klein_9b_image_edit_distilled", "object_reference_insertion",
        ("121", "18", "28", "34", "35"),
        "The character edit still follows the main photo, but the specific object I supplied is no longer transferred into her hands. Please restore the object-reference branch while keeping the character, pose, and instruction unchanged.",
        "34",
        (
            ("33", 0, "36", 1, "CONDITIONING"),
            ("32", 0, "36", 2, "CONDITIONING"),
        ),
    ),
    MultinodeWorkflow(
        "M-24", "ready", "video/ltx2_3_runexx_talking_avatar_qwen_tts", "synthetic_voice_clone",
        ("1937", "1936", "1944", "1904", "1943"),
        "The talking avatar is using the reference recording itself again instead of speaking my new line in the cloned voice. Please restore the voice-copying and cleanup path, including an audio preview, without changing the portrait or script.",
        "1944",
        (
            ("1939", 0, "1916", 0, "AUDIO"),
            ("1916", 0, "1893", 0, "AUDIO"),
            ("1916", 0, "1945", 0, "AUDIO"),
        ),
    ),
    MultinodeWorkflow(
        "M-25", "ready", "video/ltx2_3_runexx_lipsync_custom_audio", "lip_region_masking",
        ("714", "717", "720", "761", "763", "775", "790", "791", "794"),
        "Lip-sync is affecting the whole frame instead of staying around the speaker's face and mouth. Please restore the stable face-region mask and its preview so the supplied speech only drives the intended area.",
        "761",
        (("565", 0, "178", 4, "LATENT"),),
    ),
    MultinodeWorkflow(
        "M-26", "ready", "video/ltx2_3_runexx_first_middle_last_frame", "midpoint_keyframe",
        ("47", "48", "49", "2174", "2216", "2221"),
        "The clip still starts and ends on my chosen images, but it no longer passes through the composition I supplied for the middle. Please restore that timed midpoint keyframe without changing the endpoints or duration.",
        "2221",
        (
            ("44", 1, "2171", 0, "INT"),
            ("44", 2, "2171", 1, "INT"),
            ("10", 0, "36", 2, "CONDITIONING"),
            ("10", 1, "36", 1, "CONDITIONING"),
            ("10", 0, "2222", 2, "CONDITIONING"),
            ("10", 1, "2222", 1, "CONDITIONING"),
            ("32", 0, "24", 0, "LATENT"),
        ),
    ),
    MultinodeWorkflow(
        "M-27", "ready", "video/ltx2_3_iamccs_audio_extend_low_ram", "third_segment_extension",
        ("46", "48", "49", "50", "51", "58", "47", "52", "53", "54", "55", "62", "57"),
        "My low-memory extension now stops after the second section, so the last part of the song never gets a matching continuation. Please restore the third timed segment and append it into the finished long video.",
        "57",
        (("43", 0, "59", 1, ""),),
    ),
    MultinodeWorkflow(
        "M-28", "ready", "video/wanvideo_wrapper_21_14b_wanmove_i2v", "object_trajectory_control",
        ("80", "88", "90", "91", "81"),
        "The image still animates, but the subject ignores the path I drew and neither preview nor output shows the motion track anymore. Please restore the trajectory-guided movement and track overlays.",
        "80",
        (
            ("63", 0, "27", 0, "WANVIDIMAGE_EMBEDS"),
            ("28", 0, "30", 0, "IMAGE"),
        ),
    ),
    MultinodeWorkflow(
        "M-29", "ready", "video/wanvideo_wrapper_22_s2v_context_window", "high_fps_motion_finish",
        ("80", "95", "96", "102", "30"),
        "I still get the basic speech video, but the polished version is gone: it should drop the startup frames, smooth the motion, and export at 24 fps. Please restore that finishing path while keeping the original audio.",
        "80",
        (("70", 0, "97", 1, "IMAGE"),),
    ),
    MultinodeWorkflow(
        "M-30", "ready", "video/wanvideo_wrapper_22_14b_i2v_kijai", "low_noise_handoff",
        ("8", "11", "17", "20", "24"),
        "The image-to-video render stops after the coarse first phase now, so fine detail and stability are noticeably worse. Please restore the dedicated low-noise finishing pass without changing my seed, prompt, or dimensions.",
        "24",
        (("23", 0, "25", 1, "LATENT"),),
    ),
    MultinodeWorkflow(
        "M-31", "corpus", "external_workflows/corpus/7cf357a55e5fab05.json", "style_reference_conditioning",
        ("12", "13", "14", "15", "16", "27", "29"),
        "My prompt still works, but the result no longer picks up the look of my style reference. Please restore the reference-style guidance without changing the base model or canvas.",
        "12",
        (("28", 0, "3", 3, ""),),
    ),
    MultinodeWorkflow(
        "M-32", "corpus", "external_workflows/corpus/02d7ea587fb70e40.json", "feathered_seam_cleanup",
        ("79", "80", "81", "82", "83", "84", "85", "86", "87", "88"),
        "The first outpaint still appears, but the border seam is no longer feathered and resampled into a clean final image. Please restore that edge-cleanup pass and its mask preview.",
        "84",
    ),
    MultinodeWorkflow(
        "M-33", "corpus", "external_workflows/corpus/e343e3b050e4c6a9.json", "background_replacement",
        ("100", "95", "99", "98", "96", "103"),
        "The subject cutout is still available, but it is no longer cleaned up, placed over a fresh background, or shown for review before generation. Please restore that background-replacement composition while keeping the source video unchanged.",
        "100",
        (("90", 0, "79", 0, "IMAGE"),),
    ),
    MultinodeWorkflow(
        "M-34", "corpus", "external_workflows/corpus/7567d20f91a2d6b5.json", "stacked_control_guidance",
        ("6", "7", "8", "10", "21", "23"),
        "My reference image still loads, but the render no longer combines the three structural guides I used to control its composition and detail. Please restore that layered guidance stack while keeping the prompt and sampler settings intact.",
        "21",
        (
            ("14", 0, "20", 3, "CONDITIONING"),
            ("15", 0, "20", 2, "CONDITIONING"),
        ),
    ),
    MultinodeWorkflow(
        "M-35", "corpus", "external_workflows/corpus/f0abffc2b525515c.json", "upscaler_comparison",
        ("18", "19", "20", "21", "22", "23", "24", "25", "26"),
        "Only my first enlarged image is being produced now. Please restore the other three model-based upscale alternatives and save each result so I can compare which one preserves the source best.",
        "19",
    ),
    MultinodeWorkflow(
        "M-36", "corpus", "external_workflows/corpus/2e93a5af34d6d96c.json", "second_speaker_turn",
        ("90", "116", "93", "130", "122", "123", "124", "126", "127", "128", "113"),
        "The first speaker still talks, but the second voice and its matching performance have vanished, and the finished clip no longer contains both turns. Please restore the second-speaker branch and join both voices into the output.",
        "130",
        (("115", 0, "30", 0, "AUDIO"),),
    ),
    MultinodeWorkflow(
        "M-37", "corpus", "external_workflows/corpus/c44e118d5940e1bc.json", "precision_face_mask",
        ("256", "257", "253", "254", "259", "238"),
        "The rough face region is still detected, but it no longer becomes a precise tracked mask with a visible overlay and stable block edges. Please restore that refined face masking so the animation stays confined to the intended face.",
        "253",
        (("242", 0, "263", 4, "MASK"),),
    ),
    MultinodeWorkflow(
        "M-38", "corpus", "external_workflows/corpus/dc3e44e987def366.json", "differential_inpaint",
        ("144", "149", "146", "142", "154", "156", "155"),
        "The prompt-only image path still works, but I can no longer load a picture, soften its mask, repaint just that area, and composite the patch back into the original. Please restore the localized inpainting path without changing my prompt.",
        "142",
        (
            ("122", 0, "150", 0, "LATENT"),
            ("138", 0, "145", 0, "IMAGE"),
        ),
    ),
    MultinodeWorkflow(
        "M-39", "corpus", "external_workflows/corpus/0b47c66d3fc67c4e.json", "lora_stack_export",
        ("414", "416", "417", "418", "419"),
        "The base video model still loads and can be saved, but the five style and motion adapters are no longer layered into it first. Please restore that ordered LoRA stack so the exported model includes the combined look.",
        "414",
        (("412", 0, "420", 0, "MODEL"),),
    ),
    MultinodeWorkflow(
        "M-40", "corpus", "external_workflows/corpus/c953dfc7fcf7520b.json", "automatic_audio_prompt_expansion",
        ("61", "64", "65", "66", "67", "69", "70", "71", "72", "77"),
        "My plain music description still works, but the option that expands it into a richer duration-aware generation prompt and shows me the cleaned result has disappeared. Please restore that assisted prompt path.",
        "67",
    ),
]


@dataclass(frozen=True)
class DebugWorkflow:
    case_id: str
    locator: str
    bug: dict[str, Any]
    inquiry: str


# Real user-mistake fixtures sourced from the local Hivemind ready-template
# cache. Inquiries intentionally describe only the observable failure.
DEBUG_WORKFLOWS = [
    DebugWorkflow(
        "D-01",
        "image/qwen_image_2512",
        {
            "edit_type": "set_widget",
            "target_node_id": 70,
            "widget_index": 0,
            "new_value": 256,
        },
        "Pictures still render, but they suddenly come out extremely narrow "
        "and lose horizontal detail while the vertical dimension looks normal.",
    ),
    DebugWorkflow(
        "D-02",
        "image/flux2_klein_9b_t2i",
        {
            "edit_type": "set_widget",
            "target_node_id": 10,
            "widget_index": 0,
            "new_value": 0.0,
        },
        "Strong prompt changes barely affect the result now. Every render looks "
        "flat and generic, as though the text has almost no influence.",
    ),
    DebugWorkflow(
        "D-03",
        "edit/qwen_image_edit",
        {
            "edit_type": "swap_links",
            "target_node_id": 13,
            "input_name": "positive",
            "other_target_node_id": 13,
            "other_input_name": "negative",
        },
        "My edit has started doing the opposite of what I ask: unwanted elements "
        "stay prominent while protected parts of the source get disturbed.",
    ),
    DebugWorkflow(
        "D-04",
        "edit/flux2_klein_9b_image_edit_base",
        {
            "edit_type": "rewire_input",
            "target_node_id": 34,
            "input_name": "latent",
            "new_source_node_id": 28,
            "new_source_output_slot": 0,
        },
        "The extra reference stopped contributing to the edit. The result keeps "
        "echoing the main photo and misses the visual details supplied in the other reference.",
    ),
    DebugWorkflow(
        "D-05",
        "video/ltx2_3_t2v",
        {
            "edit_type": "set_widget",
            "target_node_id": 4966,
            "widget_index": 0,
            "new_value": 1,
        },
        "Clips finish suspiciously fast, but the frames are mostly incoherent "
        "flicker and noise with no stable scene or motion.",
    ),
    DebugWorkflow(
        "D-06",
        "video/ltx2_3_lightricks_two_stage",
        {
            "edit_type": "disconnect_link",
            "target_node_id": 4849,
            "input_name": "audio",
        },
        "The picture track saves normally, but the finished clip is silent even "
        "though sound is produced earlier in the workflow.",
    ),
    DebugWorkflow(
        "D-07",
        "video/wanvideo_wrapper_22_5b_i2v_controlnet",
        {
            "edit_type": "rewire_input",
            "target_node_id": 105,
            "input_name": "control_images",
            "new_source_node_id": 101,
            "new_source_output_slot": 0,
        },
        "The guide clip still affects colors and textures, but the generated "
        "motion no longer follows its depth or camera layout. Structure drifts "
        "badly from the reference.",
    ),
    DebugWorkflow(
        "D-08",
        "video/wanvideo_wrapper_22_s2v_context_window",
        {
            "edit_type": "set_widget",
            "target_node_id": 30,
            "widget_index": 0,
            "new_value": 4,
        },
        "The saved clip now plays in slow motion and drifts out of sync with its "
        "soundtrack, even though the generated frames themselves look normal.",
    ),
    DebugWorkflow(
        "D-09",
        "audio/ace_step_1_5_t2a_song",
        {
            "edit_type": "set_widget",
            "target_node_id": 122,
            "widget_index": 0,
            "new_value": 0.1,
        },
        "The song begins correctly and then cuts off almost immediately, leaving "
        "only a tiny fragment instead of a usable track.",
    ),
    DebugWorkflow(
        "D-10",
        "audio/qwen3_tts_voice_design",
        {
            "edit_type": "set_widget",
            "target_node_id": 1,
            "widget_index": 3,
            "new_value": "Chinese",
        },
        "The narrator suddenly uses the wrong phonetics for the script; familiar "
        "names sound as if they belong to a different language, while the voice "
        "character itself is unchanged.",
    ),
]


def _multinode_spec(feature_key: str) -> MultinodeWorkflow:
    matches = [spec for spec in MULTINODE_WORKFLOWS if spec.feature_key == feature_key]
    if len(matches) != 1:
        raise ValueError(f"unknown or ambiguous multinode feature_key: {feature_key!r}")
    return matches[0]


def _add_bypass_link(
    graph: dict[str, Any],
    source_id: str,
    source_slot: int,
    target_id: str,
    target_slot: int,
    link_type: str,
) -> None:
    nodes = {str(node.get("id")): node for node in graph.get("nodes", [])}
    source = nodes.get(source_id)
    target = nodes.get(target_id)
    if source is None or target is None:
        raise ValueError(f"bypass endpoint missing: {source_id} -> {target_id}")

    link_id = max(
        (int(link[0]) for link in graph.get("links", []) if isinstance(link, list) and link),
        default=0,
    ) + 1
    graph.setdefault("links", []).append(
        [link_id, source.get("id"), source_slot, target.get("id"), target_slot, link_type]
    )
    outputs = source.get("outputs") or []
    if 0 <= source_slot < len(outputs) and isinstance(outputs[source_slot], dict):
        outputs[source_slot].setdefault("links", []).append(link_id)
    inputs = target.get("inputs") or []
    if 0 <= target_slot < len(inputs) and isinstance(inputs[target_slot], dict):
        inputs[target_slot]["link"] = link_id


def _primary_multinode_locus(
    golden: dict[str, Any],
    spec: MultinodeWorkflow,
) -> dict[str, Any]:
    removed_ids = set(spec.slice_node_ids)
    nodes = {str(node.get("id")): node for node in golden.get("nodes", [])}
    primary = nodes.get(spec.primary_node_id)
    if primary is None:
        raise ValueError(f"{spec.case_id} primary node {spec.primary_node_id} is absent")
    edges: list[dict[str, str]] = []
    for link in golden.get("links", []):
        if not isinstance(link, list) or len(link) < 6:
            continue
        _, from_node, from_slot, to_node, to_slot, _ = link[:6]
        if str(from_node) == spec.primary_node_id and str(to_node) not in removed_ids:
            edges.append({
                "direction": "out",
                "peer": str(to_node),
                "self_slot": str(from_slot),
                "peer_slot": str(to_slot),
            })
        elif str(to_node) == spec.primary_node_id and str(from_node) not in removed_ids:
            edges.append({
                "direction": "in",
                "peer": str(from_node),
                "self_slot": str(to_slot),
                "peer_slot": str(from_slot),
            })
    if not edges:
        raise ValueError(f"{spec.case_id} primary role has no surviving boundary")
    widgets = primary.get("widgets_values")
    return {
        "type": "additive_witness",
        "node_type": primary.get("type"),
        "edges": edges,
        "widgets_values": widgets if isinstance(widgets, list) else [],
        "feature_key": spec.feature_key,
    }


def _remove_subgraph_fault(
    golden: dict[str, Any],
    slice_node_ids: tuple[str, ...] | list[str],
    feature_key: str,
) -> FaultInjection:
    """Atomically remove one explicit feature slice and apply its safe bypass."""
    spec = _multinode_spec(feature_key)
    removed_ids = {str(node_id) for node_id in slice_node_ids}
    if tuple(str(node_id) for node_id in slice_node_ids) != spec.slice_node_ids:
        raise ValueError(f"{spec.case_id} slice IDs do not match the registered fixture")
    if len(removed_ids) < 5 or len(removed_ids) != len(slice_node_ids):
        raise ValueError("multinode slices require at least five unique node IDs")

    nodes = {str(node.get("id")): node for node in golden.get("nodes", [])}
    missing = sorted(removed_ids - nodes.keys())
    if missing:
        raise ValueError(f"{spec.case_id} slice node(s) absent: {', '.join(missing)}")

    broken = copy.deepcopy(golden)
    broken["nodes"] = [
        node for node in broken.get("nodes", [])
        if str(node.get("id")) not in removed_ids
    ]
    broken["links"] = [
        link for link in broken.get("links", [])
        if not (
            isinstance(link, list)
            and len(link) >= 4
            and (str(link[1]) in removed_ids or str(link[3]) in removed_ids)
        )
    ]
    _strip_orphan_references(broken, removed_ids)
    for bypass in spec.bypasses:
        _add_bypass_link(broken, *bypass)

    live_ids = {str(node.get("id")) for node in broken.get("nodes", [])}
    dangling = [
        link for link in broken.get("links", [])
        if isinstance(link, list)
        and len(link) >= 4
        and (str(link[1]) not in live_ids or str(link[3]) not in live_ids)
    ]
    if dangling:
        raise ValueError(f"{spec.case_id} fault contains dangling link endpoints")

    injection = derive_repair_delta(broken, golden)
    primary = _primary_multinode_locus(golden, spec)
    absence = dict(primary)
    absence["type"] = "additive_absence"
    fault_other = [
        item for item in injection.fault_predicate.get("locus", [])
        if item.get("type") not in {"additive_absence", "additive_witness"}
    ]
    repaired_other = [
        item for item in injection.repaired_predicate.get("locus", [])
        if item.get("type") not in {"additive_absence", "additive_witness"}
    ]
    injection.fault_predicate["locus"] = [absence, *fault_other]
    injection.repaired_predicate["locus"] = [primary, *repaired_other]
    injection.fault_predicate["additive_mode"] = "multinode"
    injection.repaired_predicate["additive_mode"] = "multinode"
    return FaultInjection(
        broken=injection.broken,
        golden=injection.golden,
        repair_delta=injection.repair_delta,
        fault_delta=injection.fault_delta,
        fault_predicate=injection.fault_predicate,
        repaired_predicate=injection.repaired_predicate,
        description=f"Removed explicit {spec.case_id} {feature_key} subgraph",
        user_effect=spec.inquiry,
    )


def _remove_feature_fault(
    golden: dict,
    feature_type: str,
) -> FaultInjection | None:
    """Create a fault by removing a feature subgraph.

    Returns ``None`` when no real feature node exists in ``golden`` — the
    caller should then SKIP the case. NEVER falls back to an unrelated node
    (the prior ``list(nodes_index.keys())[0]`` landmine removed LoadImage on
    ``image/basic_image_upscale`` because the real upscale node is
    ``ImageScaleBy``, which the old keyword matcher missed).
    """
    # Find real feature nodes via object_info category + keyword matching.
    feature_ids = find_feature_node_ids(golden, feature_type)
    if not feature_ids:
        print(f"  SKIP: no {feature_type} node found in golden (not removing a wrong node)")
        return None

    # For two-pass refinement, prefer the SECOND sampler (the refinement pass),
    # not the base pass — removing the base pass would be a different fault.
    if feature_type == "refinement_pass" and len(feature_ids) >= 2:
        target_id = feature_ids[-1]
    else:
        target_id = feature_ids[0]

    # Record the removed node type so the inquiry can name it exactly.
    target_type = None
    for n in golden.get("nodes", []):
        if str(n.get("id")) == str(target_id):
            target_type = n.get("type")
            break

    # Create a BugProposal for remove_feature
    proposal = BugProposal(
        edit_type="remove_feature",
        target_node_id=target_id,
        feature_type=feature_type,
        why_realistic=f"User accidentally removed the {feature_type} functionality",
        user_symptom=f"The {feature_type} feature is missing - the output doesn't have the expected quality/effect",
        summary=f"remove-{feature_type}",
    )

    # Apply the bug
    broken = apply_bug(golden, proposal)

    if broken is None:
        print(f"  SKIP: apply_bug returned None for {feature_type}")
        return None

    # Derive repair delta. deltas.py builds the repaired predicate with
    # type-tolerant link endpoints (``from_node_type``) for the removed
    # feature node, so the oracle accepts a sound re-add under a fresh id
    # (the fixer synthesizes a new node id rather than reusing the golden's).
    injection = derive_repair_delta(broken, golden)

    return FaultInjection(
        broken=injection.broken,
        golden=injection.golden,
        repair_delta=injection.repair_delta,
        fault_delta=injection.fault_delta,
        fault_predicate=injection.fault_predicate,
        repaired_predicate=injection.repaired_predicate,
        description=f"Removed {feature_type} ({target_type or 'node'}) feature from graph",
        user_effect=f"the {feature_type} functionality is missing - output lacks expected quality/effect",
    )


def _golden_for(workflow_id: str) -> dict:
    """Schema'd golden UI graph for a ready template.

    Uses the offline port-export path (object_info cache) so links/slots are
    properly typed — the schema-less ``emit_ui_json(..., schema_provider=None)``
    emission produced malformed slots the apply-validator misreads.
    """
    golden = _export_ready_ui(workflow_id)
    if golden is None:
        # Last-resort fallback so a single export failure does not abort the
        # whole campaign; the creative/repair path still tolerates best-effort
        # slots.
        template = workflow_from_ready(workflow_id)
        golden = emit_ui_json(template, schema_provider=None, strict=False)
    return golden


def _inject_debug_fault(
    golden: dict[str, Any],
    bug_spec: dict[str, Any],
) -> FaultInjection:
    """Apply one registered, exact debugging mutation to a ready golden."""
    edit_type = str(bug_spec.get("edit_type") or "")
    if edit_type not in {
        "set_widget",
        "rewire_input",
        "swap_links",
        "disconnect_link",
    }:
        raise ValueError(f"unsupported DEBUG fault family: {edit_type!r}")

    proposal = BugProposal(
        edit_type=edit_type,
        target_node_id=bug_spec.get("target_node_id"),
        widget_index=bug_spec.get("widget_index"),
        new_value=bug_spec.get("new_value"),
        input_name=bug_spec.get("input_name"),
        new_source_node_id=bug_spec.get("new_source_node_id"),
        new_source_output_slot=bug_spec.get("new_source_output_slot"),
        other_target_node_id=bug_spec.get("other_target_node_id"),
        other_input_name=bug_spec.get("other_input_name"),
        summary=f"debug-{edit_type}",
    )
    broken = apply_bug(golden, proposal)
    if broken is None:
        raise ValueError(f"DEBUG {edit_type} mutation is inapplicable")
    if broken == golden:
        raise ValueError(f"DEBUG {edit_type} mutation made no graph change")

    injection = derive_repair_delta(broken, golden)
    if not injection.repaired_predicate.get("locus"):
        raise ValueError(f"DEBUG {edit_type} mutation produced no oracle locus")
    return FaultInjection(
        broken=injection.broken,
        golden=injection.golden,
        repair_delta=injection.repair_delta,
        fault_delta=injection.fault_delta,
        fault_predicate=injection.fault_predicate,
        repaired_predicate=injection.repaired_predicate,
        description=f"Injected exact {edit_type} debugging fault",
        user_effect="observable workflow regression",
    )


def _author_additive_inquiry(
    golden: dict, broken: dict, feature_type: str, removed_node_type: str | None
) -> str:
    """Specific, leak-aware add-request naming the exact node type and symptom.

    The prior vague phrasing ("add the upscale back") made the fixer correctly
    report the feature was already present (because the wrong node had been
    removed) and ask for clarification. Naming the exact comfy-core class to
    re-add plus the user-observable effect makes the fixer resolve the class
    against object_info and act.
    """
    # Find the upstream/downstream neighbors of the gap so the request says
    # where to reconnect.
    golden_ids = {str(n.get("id")) for n in golden.get("nodes", [])}
    broken_ids = {str(n.get("id")) for n in broken.get("nodes", [])}
    removed = [
        n for n in golden.get("nodes", [])
        if str(n.get("id")) in (golden_ids - broken_ids)
    ]
    rtype = removed_node_type or (removed[0].get("type") if removed else None)

    # Symptoms keyed by feature family (generic, not node-name-specific).
    symptoms = {
        "upscale": "the output is lower resolution than it should be — it lost the detail the resize/upscale step used to add",
        "refinement_pass": "the refinement pass is gone — the output is rougher and less polished than the two-stage result used to be",
        "controlnet": "the structural/pose guidance from the ControlNet is completely absent — the output ignores the control reference",
        "audio_merge": "the audio merge/concat step is gone — only one audio source makes it through instead of the combined mix",
        "face_detailer": "the face-detailer pass is gone — faces come out lower quality than the rest of the image",
        "lora_loader": "the style/character LoRA is no longer applied — the output lost the look the LoRA used to provide",
    }
    symptom = symptoms.get(feature_type, "the step that used to refine the output is missing, so the result no longer matches what I expect")

    rtype_phrase = f" (the node type to re-add is `{rtype}`)" if rtype else ""
    return (
        f"I had removed the {feature_type.replace('_', ' ')} step from the workflow and now {symptom}. "
        f"Can you add that step back where it belongs so the output is restored?{rtype_phrase}"
    )


def run_repair_case(workflow_id: str, idx: int, output_base: Path) -> dict:
    """Run a REPAIR case using the creative engine."""
    print(f"[{idx}/20] Running REPAIR case: {workflow_id}")

    try:
        golden = _golden_for(workflow_id)

        case = run_creative_case(
            golden=golden,
            workflow_label=workflow_id,
            output_base=output_base,
        )

        return {
            "case_id": case.case_id,
            "workflow": workflow_id,
            "scenario_type": "REPAIR",
            "fault_family": case.fault_family,
            "verdict": case.verdict.value if case.verdict else "undetermined",
            "attempt": case.attempt,
            "inquiry": case.inquiry[:100] if case.inquiry else "",
        }
    except Exception as e:
        print(f"  ERROR: {e}")
        import traceback
        traceback.print_exc()
        return {
            "case_id": "failed",
            "workflow": workflow_id,
            "scenario_type": "REPAIR",
            "error": str(e),
        }


def run_additive_case(workflow_id: str, feature_type: str, idx: int, output_base: Path) -> dict:
    """Run an ADDITIVE case by removing a feature."""
    print(f"[{idx}/20] Running ADDITIVE case: {workflow_id} - remove {feature_type}")

    try:
        golden = _golden_for(workflow_id)

        # Create remove_feature fault. Returns None when no real feature node
        # exists — SKIP the case rather than removing a wrong node.
        injection = _remove_feature_fault(golden, feature_type)
        if injection is None:
            return {
                "case_id": "skipped",
                "workflow": workflow_id,
                "scenario_type": "ADDITIVE",
                "feature_type": feature_type,
                "verdict": "skipped_no_feature_node",
            }

        # Derive the removed node type from the ACTUAL fault (golden nodes absent
        # from broken), not the first feature-family match. ``_remove_feature_fault``
        # may pick a different target (e.g. ``ids[-1]`` for refinement_pass) than
        # ``ids[0]``; the inquiry must name the exact type the oracle's answer key
        # is built around, or the fixer re-adds a plausible-but-wrong class.
        golden_ids = {str(n.get("id")) for n in golden.get("nodes", [])}
        broken_ids = {str(n.get("id")) for n in injection.broken.get("nodes", [])}
        removed = [
            n for n in golden.get("nodes", [])
            if str(n.get("id")) in (golden_ids - broken_ids)
        ]
        removed_type = removed[0].get("type") if removed else None
        inquiry = _author_additive_inquiry(golden, injection.broken, feature_type, removed_type)

        case_id = _new_case_id()
        case_dir = _cases_dir(output_base) / case_id
        case_dir.mkdir(parents=True, exist_ok=True)

        case = Case(
            case_id=case_id,
            case_dir=case_dir,
            golden=golden,
            source="additive",
            fault_family=f"additive:{feature_type}",
        )
        case.advance_stage(CaseStage.SELECTED, {"source": "additive", "feature_type": feature_type})

        if not _baseline_gate(case, golden, case_dir):
            return {
                "case_id": case.case_id,
                "workflow": workflow_id,
                "scenario_type": "ADDITIVE",
                "feature_type": feature_type,
                "verdict": "baseline_rejected",
            }

        case.injection = injection
        case.broken = injection.broken
        case.inquiry = inquiry
        case.write_graph_artifacts()

        case.advance_stage(CaseStage.FAULT_PROVEN, {"repair_ops_count": len(injection.repair_delta)})

        # Try up to 3 attempts
        for attempt in range(1, 4):
            case.attempt = attempt
            attempts_dir = case_dir / "attempts"
            attempts_dir.mkdir(parents=True, exist_ok=True)
            attempt_dir = attempts_dir / f"{attempt:03d}"
            attempt_dir.mkdir(parents=True, exist_ok=True)

            case.advance_stage(CaseStage.FIXER_RUNNING)
            fixer_result = _run_fixer(case, injection.broken, inquiry, attempt_dir, additive=True)
            if not _fixer_gate(case, fixer_result):
                if attempt < 3:
                    continue
                return {
                    "case_id": case.case_id,
                    "workflow": workflow_id,
                    "scenario_type": "ADDITIVE",
                    "feature_type": feature_type,
                    "verdict": "fixer_failed",
                }

            leakage = check_leakage(inquiry)
            write_leakage_check(leakage, attempt_dir)
            evaluated_case = _evaluate(case, fixer_result.candidate)

            if evaluated_case.verdict.value in ("accepted", "alternative_repair"):
                return {
                    "case_id": case.case_id,
                    "workflow": workflow_id,
                    "scenario_type": "ADDITIVE",
                    "feature_type": feature_type,
                    "verdict": evaluated_case.verdict.value,
                    "attempt": attempt,
                }

            if attempt < 3:
                continue

            return {
                "case_id": case.case_id,
                "workflow": workflow_id,
                "scenario_type": "ADDITIVE",
                "feature_type": feature_type,
                "verdict": evaluated_case.verdict.value,
                "attempt": attempt,
            }

    except Exception as e:
        print(f"  ERROR: {e}")
        import traceback
        traceback.print_exc()
        return {
            "case_id": "failed",
            "workflow": workflow_id,
            "scenario_type": "ADDITIVE",
            "feature_type": feature_type,
            "error": str(e),
        }


class MultinodeFixtureError(RuntimeError):
    """A registered multinode source/slice is unavailable or stale."""


def _golden_for_multinode(spec: MultinodeWorkflow) -> dict[str, Any]:
    if spec.kind == "ready":
        golden = _golden_for(spec.locator)
    elif spec.kind == "corpus":
        path = Path(spec.locator)
        if not path.is_file():
            raise MultinodeFixtureError(f"corpus fixture is missing: {path}")
        workflow = load_workflow_any(str(path))
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)
            golden = emit_ui_json(
                workflow,
                schema_provider=get_schema_provider("auto"),
                strict=False,
            )
    else:
        raise MultinodeFixtureError(f"unsupported source kind: {spec.kind!r}")

    nodes = {str(node.get("id")): node for node in golden.get("nodes", [])}
    missing_ids = sorted(set(spec.slice_node_ids) - nodes.keys())
    if missing_ids:
        raise MultinodeFixtureError(
            f"{spec.case_id} exported golden is missing slice node(s): "
            + ", ".join(missing_ids)
        )
    if spec.kind == "corpus":
        unresolved = sorted({
            str(nodes[node_id].get("type"))
            for node_id in spec.slice_node_ids
            if not isinstance(get_class(str(nodes[node_id].get("type"))), dict)
        })
        if unresolved:
            raise MultinodeFixtureError(
                f"{spec.case_id} object_info cannot resolve: "
                + ", ".join(unresolved)
            )
    return golden


def run_multinode_case(
    spec: MultinodeWorkflow,
    idx: int,
    output_base: Path,
) -> dict[str, Any]:
    """Run one explicit multi-node additive case through the existing fixer."""
    print(
        f"[{idx}] Running MULTINODE case: {spec.case_id} - "
        f"{spec.locator} - remove {spec.feature_key}"
    )
    try:
        golden = _golden_for_multinode(spec)
        injection = _remove_subgraph_fault(
            golden,
            spec.slice_node_ids,
            spec.feature_key,
        )

        case_id = _new_case_id()
        case_dir = _cases_dir(output_base) / case_id
        case_dir.mkdir(parents=True, exist_ok=True)
        case = Case(
            case_id=case_id,
            case_dir=case_dir,
            golden=golden,
            source="multinode",
            fault_family=f"additive:multinode:{spec.feature_key}",
        )
        case.advance_stage(
            CaseStage.SELECTED,
            {
                "source": "multinode",
                "campaign_case_id": spec.case_id,
                "feature_type": spec.feature_key,
            },
        )
        if not _baseline_gate(case, golden, case_dir):
            return {
                "case_id": case.case_id,
                "campaign_case_id": spec.case_id,
                "workflow": spec.locator,
                "scenario_type": "MULTINODE",
                "feature_type": spec.feature_key,
                "verdict": "baseline_rejected",
            }

        case.injection = injection
        case.broken = injection.broken
        case.inquiry = spec.inquiry
        case.write_graph_artifacts()
        case.advance_stage(
            CaseStage.FAULT_PROVEN,
            {"repair_ops_count": len(injection.repair_delta)},
        )

        for attempt in range(1, 4):
            case.attempt = attempt
            attempt_dir = case_dir / "attempts" / f"{attempt:03d}"
            attempt_dir.mkdir(parents=True, exist_ok=True)
            case.advance_stage(CaseStage.FIXER_RUNNING)
            fixer_result = _run_fixer(
                case,
                injection.broken,
                spec.inquiry,
                attempt_dir,
                additive=True,
            )
            if not _fixer_gate(case, fixer_result):
                if attempt < 3:
                    continue
                return {
                    "case_id": case.case_id,
                    "campaign_case_id": spec.case_id,
                    "workflow": spec.locator,
                    "scenario_type": "MULTINODE",
                    "feature_type": spec.feature_key,
                    "verdict": (
                        case.verdict.value
                        if case.verdict is not None
                        else "fixer_failed"
                    ),
                }

            leakage = check_leakage(spec.inquiry)
            write_leakage_check(leakage, attempt_dir)
            evaluated_case = _evaluate(case, fixer_result.candidate)
            if evaluated_case.verdict.value in ("accepted", "alternative_repair"):
                return {
                    "case_id": case.case_id,
                    "campaign_case_id": spec.case_id,
                    "workflow": spec.locator,
                    "scenario_type": "MULTINODE",
                    "feature_type": spec.feature_key,
                    "verdict": evaluated_case.verdict.value,
                    "attempt": attempt,
                }
            if attempt < 3:
                continue
            return {
                "case_id": case.case_id,
                "campaign_case_id": spec.case_id,
                "workflow": spec.locator,
                "scenario_type": "MULTINODE",
                "feature_type": spec.feature_key,
                "verdict": evaluated_case.verdict.value,
                "attempt": attempt,
            }
    except MultinodeFixtureError as exc:
        print(f"  SKIP fixture error: {exc}")
        return {
            "case_id": "skipped",
            "campaign_case_id": spec.case_id,
            "workflow": spec.locator,
            "scenario_type": "MULTINODE",
            "feature_type": spec.feature_key,
            "verdict": "skipped_fixture_error",
            "fixture_error": str(exc),
        }
    except Exception as exc:
        print(f"  ERROR: {exc}")
        import traceback
        traceback.print_exc()
        return {
            "case_id": "failed",
            "campaign_case_id": spec.case_id,
            "workflow": spec.locator,
            "scenario_type": "MULTINODE",
            "feature_type": spec.feature_key,
            "error": str(exc),
        }


def run_debug_case(
    spec: DebugWorkflow,
    idx: int,
    output_base: Path,
) -> dict[str, Any]:
    """Run one exact realistic debugging fault through the existing fixer."""
    bug_type = str(spec.bug.get("edit_type") or "unknown")
    print(
        f"[{idx}] Running DEBUG case: {spec.case_id} - "
        f"{spec.locator} - {bug_type}"
    )
    try:
        golden = _golden_for(spec.locator)
        injection = _inject_debug_fault(golden, spec.bug)

        case_id = _new_case_id()
        case_dir = _cases_dir(output_base) / case_id
        case_dir.mkdir(parents=True, exist_ok=True)
        case = Case(
            case_id=case_id,
            case_dir=case_dir,
            golden=golden,
            source="debug",
            fault_family=f"debug:{bug_type}",
        )
        case.advance_stage(
            CaseStage.SELECTED,
            {
                "source": "debug",
                "campaign_case_id": spec.case_id,
                "bug_type": bug_type,
            },
        )
        if not _baseline_gate(case, golden, case_dir):
            return {
                "case_id": case.case_id,
                "campaign_case_id": spec.case_id,
                "workflow": spec.locator,
                "scenario_type": "DEBUG",
                "bug_type": bug_type,
                "verdict": "baseline_rejected",
            }

        case.injection = injection
        case.broken = injection.broken
        case.inquiry = spec.inquiry
        case.write_graph_artifacts()
        case.advance_stage(
            CaseStage.FAULT_PROVEN,
            {
                "repair_ops_count": len(injection.repair_delta),
                "fault_locus_count": len(
                    injection.fault_predicate.get("locus", [])
                ),
            },
        )

        for attempt in range(1, 4):
            case.attempt = attempt
            attempt_dir = case_dir / "attempts" / f"{attempt:03d}"
            attempt_dir.mkdir(parents=True, exist_ok=True)
            case.advance_stage(CaseStage.FIXER_RUNNING)
            fixer_result = _run_fixer(
                case,
                injection.broken,
                spec.inquiry,
                attempt_dir,
                additive=False,
            )
            if not _fixer_gate(case, fixer_result):
                if attempt < 3:
                    continue
                return {
                    "case_id": case.case_id,
                    "campaign_case_id": spec.case_id,
                    "workflow": spec.locator,
                    "scenario_type": "DEBUG",
                    "bug_type": bug_type,
                    "verdict": (
                        case.verdict.value
                        if case.verdict is not None
                        else "fixer_failed"
                    ),
                }

            leakage = check_leakage(spec.inquiry)
            write_leakage_check(leakage, attempt_dir)
            evaluated_case = _evaluate(case, fixer_result.candidate)
            if evaluated_case.verdict.value in ("accepted", "alternative_repair"):
                return {
                    "case_id": case.case_id,
                    "campaign_case_id": spec.case_id,
                    "workflow": spec.locator,
                    "scenario_type": "DEBUG",
                    "bug_type": bug_type,
                    "verdict": evaluated_case.verdict.value,
                    "attempt": attempt,
                }
            if attempt < 3:
                continue
            return {
                "case_id": case.case_id,
                "campaign_case_id": spec.case_id,
                "workflow": spec.locator,
                "scenario_type": "DEBUG",
                "bug_type": bug_type,
                "verdict": evaluated_case.verdict.value,
                "attempt": attempt,
            }
    except Exception as exc:
        print(f"  ERROR: {exc}")
        import traceback
        traceback.print_exc()
        return {
            "case_id": "failed",
            "campaign_case_id": spec.case_id,
            "workflow": spec.locator,
            "scenario_type": "DEBUG",
            "bug_type": bug_type,
            "error": str(exc),
        }


def main():
    """Run the full campaign."""
    parser = argparse.ArgumentParser(description="Run VibeComfy demo-scenario-factory campaign")
    parser.add_argument("--output", type=str, default=str(DEFAULT_CAMPAIGN_DIR), help="Output directory")
    parser.add_argument("--repair-count", type=int, default=10, help="Number of REPAIR cases")
    parser.add_argument("--additive-count", type=int, default=10, help="Number of ADDITIVE cases")
    parser.add_argument("--multinode-count", type=int, default=0, help="Number of MULTINODE additive cases")
    parser.add_argument("--debug-count", type=int, default=0, help="Number of DEBUG cases")
    args = parser.parse_args()

    campaign_dir = Path(args.output)
    campaign_dir.mkdir(parents=True, exist_ok=True)

    print("=" * 80)
    print("VibeComfy Demo-Scenario-Factory Campaign")
    print("=" * 80)
    print(f"Output: {campaign_dir}")
    print()

    results = []

    # Run REPAIR cases (1-10)
    print("Running REPAIR scenarios (creative engine)...")
    for i, workflow_id in enumerate(REPAIR_WORKFLOWS[:args.repair_count], 1):
        result = run_repair_case(workflow_id, i, campaign_dir)
        results.append(result)
        print(f"  Result: {result.get('verdict', 'unknown')}")
        print()

    # Run ADDITIVE cases (11-20)
    print("Running ADDITIVE scenarios (remove feature)...")
    for i, (workflow_id, feature_type) in enumerate(ADDITIVE_WORKFLOWS[:args.additive_count], args.repair_count + 1):
        result = run_additive_case(workflow_id, feature_type, i, campaign_dir)
        results.append(result)
        print(f"  Result: {result.get('verdict', 'unknown')}")
        print()

    # Run explicit multi-node additive cases without changing the legacy paths.
    print("Running MULTINODE ADDITIVE scenarios (remove explicit subgraph)...")
    start = args.repair_count + args.additive_count + 1
    for i, spec in enumerate(MULTINODE_WORKFLOWS[:args.multinode_count], start):
        result = run_multinode_case(spec, i, campaign_dir)
        results.append(result)
        print(f"  Result: {result.get('verdict', 'unknown')}")
        print()

    # Run exact realistic debugging cases without changing the legacy paths.
    print("Running DEBUG scenarios (exact user-mistake faults)...")
    start = (
        args.repair_count
        + args.additive_count
        + args.multinode_count
        + 1
    )
    for i, spec in enumerate(DEBUG_WORKFLOWS[:args.debug_count], start):
        result = run_debug_case(spec, i, campaign_dir)
        results.append(result)
        print(f"  Result: {result.get('verdict', 'unknown')}")
        print()

    # Write results
    results_file = campaign_dir / "campaign_results.json"
    results_file.write_text(json.dumps(results, indent=2), encoding="utf-8")

    # Print summary
    print("=" * 80)
    print("CAMPAIGN SUMMARY")
    print("=" * 80)

    repair_results = [r for r in results if r.get("scenario_type") == "REPAIR"]
    additive_results = [r for r in results if r.get("scenario_type") == "ADDITIVE"]
    multinode_results = [r for r in results if r.get("scenario_type") == "MULTINODE"]
    debug_results = [r for r in results if r.get("scenario_type") == "DEBUG"]

    repair_passed = sum(1 for r in repair_results if r.get("verdict") in ("accepted", "alternative_repair"))
    additive_passed = sum(1 for r in additive_results if r.get("verdict") in ("accepted", "alternative_repair"))
    multinode_passed = sum(1 for r in multinode_results if r.get("verdict") in ("accepted", "alternative_repair"))
    debug_passed = sum(1 for r in debug_results if r.get("verdict") in ("accepted", "alternative_repair"))

    total_cases = (
        len(repair_results)
        + len(additive_results)
        + len(multinode_results)
        + len(debug_results)
    )

    print(f"REPAIR: {repair_passed}/{len(repair_results)} passed")
    print(f"ADDITIVE: {additive_passed}/{len(additive_results)} passed")
    print(f"MULTINODE: {multinode_passed}/{len(multinode_results)} passed")
    print(f"DEBUG: {debug_passed}/{len(debug_results)} passed")
    total_passed = repair_passed + additive_passed + multinode_passed + debug_passed
    pass_rate = 100 * total_passed / total_cases if total_cases else 0.0
    print(f"Total: {total_passed}/{total_cases} passed ({pass_rate:.1f}%)")

    print()
    print("Results written to:", results_file)

    # Return exit code based on pass rate
    sys.exit(0 if total_cases and total_passed >= total_cases * 0.5 else 1)


if __name__ == "__main__":
    main()
