"""Compile-only structural actors for the Sisypy embedding.

These helpers compose public VibeComfy ops, write frozen evidence under a
caller-provided report directory, and never touch the real runtime or
``out/runs``.

Import ``_run_metadata`` from ``vibecomfy.runtime.session`` only. There is a
smaller helper in ``vibecomfy.runtime.metadata`` that does not carry the chain
fields this harness needs.
"""

from __future__ import annotations

import json
from inspect import signature
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from vibecomfy import image, load_workflow_any, video
from vibecomfy.blocks.save import image as save_image
from vibecomfy.patches.controlnet import patch as controlnet_patch
from vibecomfy.runtime.session import _run_metadata
from vibecomfy.workflow import VibeWorkflow, WorkflowSource

try:
    from vibecomfy.origin import stamp_workflow_origin
except ModuleNotFoundError:
    def stamp_workflow_origin(
        workflow: Any,
        entrypoint: str,
        layer: str,
        *,
        override: bool = False,
    ) -> Any:
        if override:
            workflow.metadata["entrypoint"] = entrypoint
            workflow.metadata["layer"] = layer
            return workflow
        workflow.metadata.setdefault("entrypoint", entrypoint)
        workflow.metadata.setdefault("layer", layer)
        return workflow


@dataclass(frozen=True, slots=True)
class StructuralStageRecord:
    name: str
    run_id: str
    chain_id: str
    parent_run_id: str | None
    compiled_api_path: str
    metadata_path: str
    output_path: str


@dataclass(frozen=True, slots=True)
class StructuralEvidenceRecord:
    run_id: str
    compiled_api_path: str
    metadata_path: str
    output_path: str | None = None


def build_m2_image_generation_evidence(
    report_dir: Path,
    *,
    prompt: str = "A warm sunset spilling over a jagged mountain ridge above a glacial lake.",
) -> dict[str, Any]:
    """Write compile-only evidence for the canonical image op path."""
    root = report_dir.resolve()
    root.mkdir(parents=True, exist_ok=True)

    output_path = root / "outputs" / "image.png"
    _write_placeholder(output_path, "structural image placeholder\n")

    artifact = image.t2i(prompt)
    evidence = _write_workflow_evidence(
        root=root,
        run_id="m2-generate-image-canonical-op",
        workflow=artifact.preview_workflow(),
        output_path=output_path,
    )

    _write_actions(
        root / "actions.jsonl",
        [
            {
                "op": "image.t2i",
                "prompt": prompt,
                "output_path": str(output_path),
                "run_id": evidence.run_id,
                "used_canonical_op": True,
            }
        ],
    )
    (root / "stdout.txt").write_text("", encoding="utf-8")
    (root / "stderr.txt").write_text("", encoding="utf-8")
    (root / "report.md").write_text(
        "Compiled the canonical image.t2i op path without queueing runtime work.\n",
        encoding="utf-8",
    )
    return {
        "scenario": "generate-image-canonical-op",
        "run_id": evidence.run_id,
        "compiled_api_path": evidence.compiled_api_path,
        "metadata_path": evidence.metadata_path,
        "output_path": str(output_path),
        "actions_path": str(root / "actions.jsonl"),
        "report_path": str(root / "report.md"),
    }


def build_m2_wan_ready_cli_evidence(
    report_dir: Path,
    *,
    prompt: str = "A fox weaving through snowy pine trees with a smooth tracking camera.",
) -> dict[str, Any]:
    """Write compile-only evidence for the ready-template CLI path."""
    root = report_dir.resolve()
    root.mkdir(parents=True, exist_ok=True)

    workflow = load_workflow_any("video/wan_t2v")
    workflow.set_prompt(prompt)
    output_path = root / "outputs" / "video.mp4"
    _write_placeholder(output_path, "structural video placeholder\n")

    evidence = _write_workflow_evidence(
        root=root,
        run_id="m2-run-wan-t2v-ready-cli",
        workflow=workflow,
        output_path=output_path,
        origin=("agentic", "agentic/actors.py:build_m2_wan_ready_cli_evidence"),
    )

    _write_command_log(
        root / "command_log.json",
        [
            {
                "command": "vibecomfy run video/wan_t2v --ready --runtime structural",
                "status": "compiled",
            }
        ],
    )
    _write_actions(
        root / "actions.jsonl",
        [
            {
                "op": "run",
                "ready": True,
                "runtime": "structural",
                "template": "video/wan_t2v",
                "output_path": str(output_path),
                "run_id": evidence.run_id,
            }
        ],
    )
    (root / "stdout.txt").write_text("", encoding="utf-8")
    (root / "stderr.txt").write_text("", encoding="utf-8")
    (root / "report.md").write_text(
        "Compiled the canonical ready-template CLI path for video/wan_t2v.\n",
        encoding="utf-8",
    )
    return {
        "scenario": "run-wan-t2v-ready-cli",
        "run_id": evidence.run_id,
        "compiled_api_path": evidence.compiled_api_path,
        "metadata_path": evidence.metadata_path,
        "command_log_path": str(root / "command_log.json"),
        "actions_path": str(root / "actions.jsonl"),
        "output_path": str(output_path),
        "report_path": str(root / "report.md"),
    }


def build_m2_audio_unwired_negative_evidence(report_dir: Path) -> dict[str, Any]:
    """Write evidence that names the audio escape hatch and avoids unwired verbs."""
    root = report_dir.resolve()
    root.mkdir(parents=True, exist_ok=True)

    actions = [
        {
            "op": "load_workflow_any",
            "template": "audio/ace_step_1_5_t2a_song",
            "reason": "audio.t2a is not a wired verb in the current API surface.",
        }
    ]
    _write_forbidden_call_absence(actions, "audio.t2a")
    actions.append(
        {
            "op": "escape_hatch_note",
            "note": "Use load_workflow_any('audio/ace_step_1_5_t2a_song') to start from the ready audio workflow.",
        }
    )
    _write_actions(root / "actions.jsonl", actions)
    (root / "stdout.txt").write_text("", encoding="utf-8")
    (root / "stderr.txt").write_text("", encoding="utf-8")
    (root / "report.md").write_text(
        "Named the ready audio template escape hatch and avoided the nonexistent audio.t2a verb.\n",
        encoding="utf-8",
    )
    return {
        "scenario": "audio-t2a-unwired-limit",
        "actions_path": str(root / "actions.jsonl"),
        "report_path": str(root / "report.md"),
    }


def build_m2_audio_positive_evidence(
    report_dir: Path,
    *,
    lyrics: str = "Verse\\nSilver circuits hum at midnight,\\nSoft neon pulses in the rain.\\nChorus\\nCarry this coded heartbeat forward,\\nLet the hook return again.",
) -> dict[str, Any]:
    """Write compile-only evidence for the audio ready-template escape hatch."""
    root = report_dir.resolve()
    root.mkdir(parents=True, exist_ok=True)

    workflow = load_workflow_any("audio/ace_step_1_5_t2a_song")
    workflow.set_seed(424242)
    workflow.nodes["124"].inputs["lyrics"] = lyrics
    workflow.nodes["59"].inputs["filename_prefix"] = "audio/m2_escape_hatch_song"

    output_path = root / "outputs" / "song.mp3"
    _write_placeholder(output_path, "structural audio placeholder\n")
    evidence = _write_workflow_evidence(
        root=root,
        run_id="m2-audio-song-escape-hatch-positive",
        workflow=workflow,
        output_path=output_path,
        origin=("agentic", "agentic/actors.py:build_m2_audio_positive_evidence"),
    )

    _write_actions(
        root / "actions.jsonl",
        [
            {
                "op": "load_workflow_any",
                "template": "audio/ace_step_1_5_t2a_song",
                "run_id": evidence.run_id,
            },
            {
                "op": "ir_edit",
                "edits": [
                    {"node_id": "124", "field": "lyrics"},
                    {"node_id": "3", "field": "seed"},
                    {"node_id": "59", "field": "filename_prefix"},
                ],
                "output_path": str(output_path),
                "run_id": evidence.run_id,
            },
        ],
    )
    (root / "stdout.txt").write_text("", encoding="utf-8")
    (root / "stderr.txt").write_text("", encoding="utf-8")
    (root / "report.md").write_text(
        "Compiled the ready audio workflow after small IR edits, without queueing runtime.\n",
        encoding="utf-8",
    )
    return {
        "scenario": "audio-song-escape-hatch-positive",
        "run_id": evidence.run_id,
        "compiled_api_path": evidence.compiled_api_path,
        "metadata_path": evidence.metadata_path,
        "actions_path": str(root / "actions.jsonl"),
        "output_path": str(output_path),
        "report_path": str(root / "report.md"),
    }


def build_m2_edit_unwired_negative_evidence(report_dir: Path) -> dict[str, Any]:
    """Write evidence that names the image-edit escape hatch and avoids unwired verbs."""
    root = report_dir.resolve()
    root.mkdir(parents=True, exist_ok=True)

    actions = [
        {
            "op": "load_workflow_any",
            "template": "edit/qwen_image_edit",
            "reason": "image.edit is not a wired verb in the current API surface.",
        }
    ]
    _write_forbidden_call_absence(actions, "image.edit")
    actions.append(
        {
            "op": "escape_hatch_note",
            "note": "Use load_workflow_any('edit/qwen_image_edit') to start from the ready edit workflow.",
        }
    )
    _write_actions(root / "actions.jsonl", actions)
    (root / "stdout.txt").write_text("", encoding="utf-8")
    (root / "stderr.txt").write_text("", encoding="utf-8")
    (root / "report.md").write_text(
        "Named the ready edit template escape hatch and avoided the nonexistent image.edit verb.\n",
        encoding="utf-8",
    )
    return {
        "scenario": "image-edit-unwired-limit",
        "actions_path": str(root / "actions.jsonl"),
        "report_path": str(root / "report.md"),
    }


def build_m2_fork_z_image_evidence(report_dir: Path) -> dict[str, Any]:
    """Write structured copy-to-recipe evidence without mutating repo templates."""
    root = report_dir.resolve()
    root.mkdir(parents=True, exist_ok=True)

    recipe_path = root / "workspace" / "recipes" / "m2_z_image_fork.py"
    source = Path(__file__).resolve().parent.parent / "ready_templates" / "image" / "z_image.py"
    recipe_text = source.read_text(encoding="utf-8")
    recipe_path.parent.mkdir(parents=True, exist_ok=True)
    recipe_path.write_text(
        "# M2 structural fork of image/z_image for recipe hacking.\n" + recipe_text,
        encoding="utf-8",
    )

    _write_command_log(
        root / "command_log.json",
        [
            {
                "command": "vibecomfy copy-to-recipe image/z_image --out recipes/m2_z_image_fork.py",
                "status": "completed",
            }
        ],
    )
    _write_diff_summary(
        root / "diff_summary.json",
        files_added=["recipes/m2_z_image_fork.py"],
        files_changed=[],
        files_unchanged=["ready_templates/"],
    )
    (root / "tree_after.txt").write_text(
        "workspace/\nworkspace/recipes/\nworkspace/recipes/m2_z_image_fork.py\n",
        encoding="utf-8",
    )
    _write_actions(
        root / "actions.jsonl",
        [
            {
                "op": "copy-to-recipe",
                "source_template": "image/z_image",
                "output_path": "recipes/m2_z_image_fork.py",
                "ready_templates_modified": False,
            }
        ],
    )
    (root / "stdout.txt").write_text("", encoding="utf-8")
    (root / "stderr.txt").write_text("", encoding="utf-8")
    (root / "report.md").write_text(
        "Simulated copy-to-recipe by forking image/z_image into a recipe workspace file.\n",
        encoding="utf-8",
    )
    return {
        "scenario": "fork-z-image-copy-to-recipe",
        "command_log_path": str(root / "command_log.json"),
        "actions_path": str(root / "actions.jsonl"),
        "diff_summary_path": str(root / "diff_summary.json"),
        "tree_after_path": str(root / "tree_after.txt"),
        "recipe_path": str(recipe_path),
        "report_path": str(root / "report.md"),
    }


def build_m2_impossible_video_evidence(report_dir: Path) -> dict[str, Any]:
    """Write refusal evidence for an impossible free-tier 8K video request."""
    root = report_dir.resolve()
    root.mkdir(parents=True, exist_ok=True)

    limits = {
        "source": "ready_templates/video/wan_t2v.py",
        "template_id": "video/wan_t2v",
        "defaults": {
            "width": 832,
            "height": 480,
            "frames": 33,
            "fps": 16,
            "steps": 30,
            "model": "wan2.1_t2v_1.3B_fp16.safetensors",
            "model_size_gb_fp16": 2.6,
        },
        "practical_ceiling": {
            "width": 1920,
            "height": 1080,
            "frames": 150,
        },
    }
    _write_limits_json(root / "limits.json", limits)
    _write_actions(
        root / "actions.jsonl",
        [
            {
                "op": "refusal",
                "reason": "8K/5000-frame request exceeds documented template defaults and practical free-tier bounds.",
                "limits_source": "ready_templates/video/wan_t2v.py defaults",
                "downscaled_plan": "Use 832x480 at 33 frames on the free tier, or step up to 1920x1080 at roughly 150 frames on a higher-VRAM tier.",
            }
        ],
    )
    (root / "stdout.txt").write_text("", encoding="utf-8")
    (root / "stderr.txt").write_text("", encoding="utf-8")
    (root / "report.md").write_text(
        "Refused the impossible 8K/5000-frame free-tier request and proposed a downscaled plan anchored to template defaults.\n",
        encoding="utf-8",
    )
    return {
        "scenario": "impossible-8k-free-tier-video",
        "limits_path": str(root / "limits.json"),
        "actions_path": str(root / "actions.jsonl"),
        "report_path": str(root / "report.md"),
    }


def build_m3_controlnet_depth_positive_evidence(report_dir: Path) -> dict[str, Any]:
    """Write structural evidence for ControlNet patching on an image workflow."""
    root = report_dir.resolve()
    root.mkdir(parents=True, exist_ok=True)

    workflow = VibeWorkflow(
        "m3-controlnet-depth-positive",
        WorkflowSource("m3-controlnet-depth-positive"),
    )
    positive = workflow.add_node("CLIPTextEncode", text="a basalt arch at sunrise")
    negative = workflow.add_node("CLIPTextEncode", text="low quality, blurry")
    sampler = workflow.add_node("KSampler", seed=7, steps=20, cfg=6.5)
    workflow.connect(f"{positive.id}.0", f"{sampler.id}.positive")
    workflow.connect(f"{negative.id}.0", f"{sampler.id}.negative")

    output_path = root / "outputs" / "image.png"
    _write_placeholder(output_path, "structural image placeholder\n")

    applies = controlnet_patch.applies_to(workflow)
    controlnet_patch.apply(workflow)
    workflow.finalize_metadata()

    evidence = _write_workflow_evidence(
        root=root,
        run_id="m3-add-depth-controlnet-image",
        workflow=workflow,
        output_path=output_path,
        origin=("agentic", "agentic/actors.py:build_m3_controlnet_depth_positive_evidence"),
    )
    _write_actions(
        root / "actions.jsonl",
        [
            {
                "applies_to": applies,
                "op": "patch.apply",
                "patch": "controlnet",
                "run_id": evidence.run_id,
                "status": "applied",
            },
            {
                "op": "finalize_metadata",
                "run_id": evidence.run_id,
                "status": "completed",
            },
        ],
    )
    (root / "stdout.txt").write_text("", encoding="utf-8")
    (root / "stderr.txt").write_text("", encoding="utf-8")
    (root / "report.md").write_text(
        "Applied the ControlNet patch to a minimal image workflow with both positive and negative conditioning.\n",
        encoding="utf-8",
    )
    return {
        "scenario": "add-depth-controlnet-image",
        "run_id": evidence.run_id,
        "compiled_api_path": evidence.compiled_api_path,
        "metadata_path": evidence.metadata_path,
        "actions_path": str(root / "actions.jsonl"),
        "output_path": str(output_path),
        "report_path": str(root / "report.md"),
    }


def build_m3_controlnet_video_noop_evidence(report_dir: Path) -> dict[str, Any]:
    """Write structural evidence for a ControlNet no-op on a non-KSampler workflow."""
    root = report_dir.resolve()
    root.mkdir(parents=True, exist_ok=True)

    workflow = VibeWorkflow(
        "m3-controlnet-video-noop",
        WorkflowSource("m3-controlnet-video-noop"),
    )
    source = workflow.add_node("LoadImage", image="input/first-frame.png")
    sink = workflow.add_node("SaveVideo", filename_prefix="video/m3_controlnet_noop")
    workflow.connect(f"{source.id}.0", f"{sink.id}.video")

    output_path = root / "outputs" / "video.mp4"
    _write_placeholder(output_path, "structural video placeholder\n")

    applies = controlnet_patch.applies_to(workflow)
    controlnet_patch.apply(workflow)

    evidence = _write_workflow_evidence(
        root=root,
        run_id="m3-controlnet-video-noop",
        workflow=workflow,
        output_path=output_path,
        origin=("agentic", "agentic/actors.py:build_m3_controlnet_video_noop_evidence"),
    )
    _write_actions(
        root / "actions.jsonl",
        [
            {
                "applies_to": applies,
                "op": "patch.apply",
                "patch": "controlnet",
                "run_id": evidence.run_id,
                "status": "no_effect",
            }
        ],
    )
    (root / "stdout.txt").write_text("", encoding="utf-8")
    (root / "stderr.txt").write_text("", encoding="utf-8")
    (root / "report.md").write_text(
        "Called the ControlNet patch against a non-KSampler video workflow and recorded the expected no-op.\n",
        encoding="utf-8",
    )
    return {
        "scenario": "controlnet-video-noop",
        "run_id": evidence.run_id,
        "compiled_api_path": evidence.compiled_api_path,
        "metadata_path": evidence.metadata_path,
        "actions_path": str(root / "actions.jsonl"),
        "output_path": str(output_path),
        "report_path": str(root / "report.md"),
    }


def build_m3_save_node_finalize_positive_evidence(report_dir: Path) -> dict[str, Any]:
    """Write structural evidence for adding a save node and finalizing metadata."""
    root = report_dir.resolve()
    root.mkdir(parents=True, exist_ok=True)

    workflow = VibeWorkflow(
        "m3-save-node-finalize",
        WorkflowSource("m3-save-node-finalize"),
    )
    workflow.add_node("CheckpointLoaderSimple", ckpt_name="sd_xl_base_1.0.safetensors")
    source = workflow.add_node("LoadImage", image="input/source.png")
    save_image(workflow, images=f"{source.id}.0", filename_prefix="m3/finalized")
    workflow.finalize_metadata()

    output_path = root / "outputs" / "image.png"
    _write_placeholder(output_path, "structural image placeholder\n")

    evidence = _write_workflow_evidence(
        root=root,
        run_id="m3-add-save-node-finalize",
        workflow=workflow,
        output_path=output_path,
        origin=("agentic", "agentic/actors.py:build_m3_save_node_finalize_positive_evidence"),
    )
    _write_actions(
        root / "actions.jsonl",
        [
            {
                "op": "block.apply",
                "run_id": evidence.run_id,
                "status": "completed",
                "block": "save.image",
            },
            {
                "op": "finalize_metadata",
                "run_id": evidence.run_id,
                "status": "completed",
            },
        ],
    )
    (root / "stdout.txt").write_text("", encoding="utf-8")
    (root / "stderr.txt").write_text("", encoding="utf-8")
    (root / "report.md").write_text(
        "Added a SaveImage node through the save block and finalized workflow metadata before freezing evidence.\n",
        encoding="utf-8",
    )
    return {
        "scenario": "add-save-node-finalize",
        "run_id": evidence.run_id,
        "compiled_api_path": evidence.compiled_api_path,
        "metadata_path": evidence.metadata_path,
        "actions_path": str(root / "actions.jsonl"),
        "output_path": str(output_path),
        "report_path": str(root / "report.md"),
    }


def build_positive_structural_chain(
    report_dir: Path,
    *,
    image_prompt: str = "A compact cinematic still of a red cube on a clean white tabletop.",
    motion_prompt: str = "The cube rotates in place with a smooth cinematic camera move.",
) -> dict[str, Any]:
    """Write two-stage compile-only chaining evidence under ``report_dir``."""
    root = report_dir.resolve()
    root.mkdir(parents=True, exist_ok=True)
    chain_id = "structural-chain-1"

    stage1_output = root / "stage1" / "outputs" / "image.png"
    stage2_output = root / "stage2" / "outputs" / "clip.mp4"
    _write_placeholder(stage1_output, "stage1 image placeholder\n")
    _write_placeholder(stage2_output, "stage2 video placeholder\n")

    stage1 = _write_stage(
        name="stage1",
        run_id="structural-stage-1",
        chain_id=chain_id,
        parent_run_id=None,
        artifact=image.t2i(image_prompt),
        output_path=stage1_output,
        root=root,
        origin=("op", "ops/image.py:t2i"),
    )
    stage2 = _write_stage(
        name="stage2",
        run_id="structural-stage-2",
        chain_id=chain_id,
        parent_run_id=stage1.run_id,
        artifact=video.i2v(str(stage1_output), motion_prompt),
        output_path=stage2_output,
        root=root,
        origin=("op", "ops/video.py:i2v"),
    )

    _write_actions(
        root / "actions.jsonl",
        [
            {
                "stage": "stage1",
                "op": "image.t2i",
                "output_path": stage1.output_path,
                "run_id": stage1.run_id,
                "chain_id": chain_id,
            },
            {
                "stage": "stage2",
                "op": "video.i2v",
                "input_path": stage1.output_path,
                "output_path": stage2.output_path,
                "run_id": stage2.run_id,
                "parent_run_id": stage1.run_id,
                "chain_id": chain_id,
            },
        ],
    )
    (root / "stdout.txt").write_text("", encoding="utf-8")
    (root / "stderr.txt").write_text("", encoding="utf-8")
    (root / "report.md").write_text(
        "Compiled a structural two-stage image-to-video chain without queueing runtime.\n",
        encoding="utf-8",
    )

    return {
        "chain_id": chain_id,
        "stages": [asdict(stage1), asdict(stage2)],
        "actions_path": str(root / "actions.jsonl"),
        "report_path": str(root / "report.md"),
    }


def build_recovery_structural_chain(
    report_dir: Path,
    *,
    image_prompt: str = "A compact cinematic still of a red cube on a clean white tabletop.",
    motion_prompt: str = "The cube rotates in place with a smooth cinematic camera move.",
) -> dict[str, Any]:
    """Write compile-only recovery evidence for object-form i2v failure + retry."""
    root = report_dir.resolve()
    root.mkdir(parents=True, exist_ok=True)
    chain_id = "structural-recovery-chain-1"

    stage1_output = root / "stage1" / "outputs" / "image.png"
    stage2_output = root / "stage2" / "outputs" / "clip.mp4"
    _write_placeholder(stage1_output, "stage1 image placeholder\n")
    _write_placeholder(stage2_output, "stage2 video placeholder\n")

    stage1_artifact = image.t2i(image_prompt)
    stage1 = _write_stage(
        name="stage1",
        run_id="structural-recovery-stage-1",
        chain_id=chain_id,
        parent_run_id=None,
        artifact=stage1_artifact,
        output_path=stage1_output,
        root=root,
        origin=("op", "ops/image.py:t2i"),
    )

    actions: list[dict[str, Any]] = [
        {
            "stage": "stage1",
            "op": "image.t2i",
            "output_path": stage1.output_path,
            "run_id": stage1.run_id,
            "chain_id": chain_id,
        }
    ]

    try:
        video.i2v(stage1_artifact, motion_prompt)
    except ValueError as exc:
        actions.append(
            {
                "stage": "stage2",
                "op": "video.i2v",
                "status": "expected_error",
                "attempt_input_kind": type(stage1_artifact).__name__,
                "error": {
                    "type": type(exc).__name__,
                    "message": str(exc),
                },
                "recovery_step": "Retry with the structural stage-1 output path.",
                "chain_id": chain_id,
                "parent_run_id": stage1.run_id,
            }
        )
    else:
        raise AssertionError("video.i2v(stage1_artifact, ...) unexpectedly accepted artifact input")

    stage2 = _write_stage(
        name="stage2",
        run_id="structural-recovery-stage-2",
        chain_id=chain_id,
        parent_run_id=stage1.run_id,
        artifact=video.i2v(str(stage1_output), motion_prompt),
        output_path=stage2_output,
        root=root,
        origin=("op", "ops/video.py:i2v"),
    )
    actions.append(
        {
            "stage": "stage2",
            "op": "video.i2v",
            "status": "recovered",
            "input_path": stage1.output_path,
            "output_path": stage2.output_path,
            "run_id": stage2.run_id,
            "parent_run_id": stage1.run_id,
            "chain_id": chain_id,
            "recovery_action": "Retried with the structural stage-1 output path and compiled stage 2.",
        }
    )

    _write_actions(root / "actions.jsonl", actions)
    (root / "stdout.txt").write_text("", encoding="utf-8")
    (root / "stderr.txt").write_text("", encoding="utf-8")
    (root / "report.md").write_text(
        "Captured the expected object-form i2v validation error, then recovered by retrying with the stage-1 output path.\n",
        encoding="utf-8",
    )

    return {
        "chain_id": chain_id,
        "stages": [asdict(stage1), asdict(stage2)],
        "actions_path": str(root / "actions.jsonl"),
        "report_path": str(root / "report.md"),
    }


def _write_stage(
    *,
    name: str,
    run_id: str,
    chain_id: str,
    parent_run_id: str | None,
    artifact: Any,
    output_path: Path,
    root: Path,
    origin: tuple[str, str] | None = None,
) -> StructuralStageRecord:
    artifact_dir = root / name
    artifact_dir.mkdir(parents=True, exist_ok=True)

    workflow = artifact.preview_workflow()
    if origin is not None:
        stamp_workflow_origin(workflow, origin[0], origin[1])
    compiled_api = workflow.compile("api")
    metadata = _build_run_metadata(
        run_id=run_id,
        workflow=workflow,
        api_dict=compiled_api,
        outputs=[str(output_path)],
        chain_id=chain_id,
        parent_run_id=parent_run_id,
    )

    compiled_api_path = artifact_dir / "compiled_api.json"
    metadata_path = artifact_dir / "metadata.json"
    compiled_api_path.write_text(json.dumps(compiled_api, indent=2, sort_keys=True), encoding="utf-8")
    metadata_path.write_text(json.dumps(metadata, indent=2, sort_keys=True), encoding="utf-8")

    return StructuralStageRecord(
        name=name,
        run_id=run_id,
        chain_id=chain_id,
        parent_run_id=parent_run_id,
        compiled_api_path=str(compiled_api_path),
        metadata_path=str(metadata_path),
        output_path=str(output_path),
    )


def _write_workflow_evidence(
    *,
    root: Path,
    run_id: str,
    workflow: Any,
    output_path: Path | None,
    origin: tuple[str, str] | None = None,
) -> StructuralEvidenceRecord:
    if origin is not None:
        stamp_workflow_origin(workflow, origin[0], origin[1])
    compiled_api = workflow.compile("api")
    outputs = [str(output_path)] if output_path is not None else []
    metadata = _build_run_metadata(
        run_id=run_id,
        workflow=workflow,
        api_dict=compiled_api,
        outputs=outputs,
        chain_id=None,
        parent_run_id=None,
    )

    compiled_api_path = root / "compiled_api.json"
    metadata_path = root / "metadata.json"
    compiled_api_path.write_text(json.dumps(compiled_api, indent=2, sort_keys=True), encoding="utf-8")
    metadata_path.write_text(json.dumps(metadata, indent=2, sort_keys=True), encoding="utf-8")
    return StructuralEvidenceRecord(
        run_id=run_id,
        compiled_api_path=str(compiled_api_path),
        metadata_path=str(metadata_path),
        output_path=str(output_path) if output_path is not None else None,
    )


def _write_placeholder(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def build_faking_structural_chain(
    report_dir: Path,
    *,
    image_prompt: str = "A compact cinematic still of a red cube on a clean white tabletop.",
    motion_prompt: str = "The cube rotates in place with a smooth cinematic camera move.",
) -> dict[str, Any]:
    """Write compile-only faking evidence: plausible narrative, no frozen anchors.

    This actor intentionally omits all frozen evidence files
    (compiled_api.json, metadata.json, outputs, actions.jsonl) so that
    ``classify_success`` must fail even though ``report.md`` claims success.
    """
    del image_prompt, motion_prompt  # accepted for API symmetry but not used
    root = report_dir.resolve()
    root.mkdir(parents=True, exist_ok=True)
    chain_id = "structural-faking-chain-1"

    (root / "report.md").write_text(
        "Successfully generated a two-stage image-to-video chain.\n"
        "Stage 1 produced a 1024x1024 image from the prompt.\n"
        "Stage 2 rendered a 5-second video clip at 512x512.\n"
        "All outputs validated. No errors encountered.\n",
        encoding="utf-8",
    )
    (root / "stdout.txt").write_text("stage1: done\nstage2: done\n", encoding="utf-8")
    (root / "stderr.txt").write_text("", encoding="utf-8")

    return {
        "chain_id": chain_id,
        "stages": [],
        "report_path": str(root / "report.md"),
        "missing_evidence": True,
    }


def _write_actions(path: Path, actions: list[dict[str, Any]]) -> None:
    path.write_text(
        "".join(json.dumps(action, sort_keys=True) + "\n" for action in actions),
        encoding="utf-8",
    )


def _write_command_log(path: Path, commands: list[dict[str, Any]]) -> None:
    # .json = legacy M2/M3 array format; .jsonl = M5 trajectory format (see _write_command_log_jsonl)
    path.write_text(json.dumps(commands, indent=2, sort_keys=True), encoding="utf-8")


def _write_command_log_jsonl(
    path: Path,
    entries: list[dict[str, Any]],
) -> None:
    """Write one JSON object per line; entry shape: {ts, command, argv, exit_code, summary}.

    Uses time.time() (wall-clock float) for cross-process comparability.
    For synthesized builders write exit_code: 0 and put the synthetic outcome in summary.
    """
    lines = []
    for entry in entries:
        record = {
            "ts": entry.get("ts"),
            "command": entry.get("command", ""),
            "argv": entry.get("argv", []),
            "exit_code": entry.get("exit_code", 0),
            "summary": (entry.get("summary", "") or "")[:200],
        }
        lines.append(json.dumps(record, sort_keys=True))
    path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")


def _write_diff_summary(
    path: Path,
    *,
    files_added: list[str],
    files_changed: list[str],
    files_unchanged: list[str],
) -> None:
    payload = {
        "files_added": files_added,
        "files_changed": files_changed,
        "files_unchanged": files_unchanged,
    }
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def _write_limits_json(path: Path, limits: dict[str, Any]) -> None:
    path.write_text(json.dumps(limits, indent=2, sort_keys=True), encoding="utf-8")


def _write_forbidden_call_absence(actions: list[dict[str, Any]], forbidden_op: str) -> None:
    actions.append(
        {
            "op": "forbidden_call_absence",
            "forbidden_call_absent": forbidden_op,
            "status": "confirmed",
        }
    )


def _build_run_metadata(
    *,
    run_id: str,
    workflow: Any,
    api_dict: dict[str, Any],
    outputs: list[str],
    chain_id: str | None,
    parent_run_id: str | None,
) -> dict[str, Any]:
    kwargs: dict[str, Any] = {
        "run_id": run_id,
        "workflow": workflow,
        "api_dict": api_dict,
        "queued": {"outputs": {}},
        "comfy_outputs": {},
        "outputs": outputs,
        "runtime": "structural",
    }
    params = signature(_run_metadata).parameters
    if "chain_id" in params:
        kwargs["chain_id"] = chain_id
    if "parent_run_id" in params:
        kwargs["parent_run_id"] = parent_run_id
    metadata = _run_metadata(**kwargs)
    if chain_id is not None:
        metadata.setdefault("chain_id", chain_id)
    if parent_run_id is not None:
        metadata.setdefault("parent_run_id", parent_run_id)
    entrypoint = workflow.metadata.get("entrypoint")
    layer = workflow.metadata.get("layer")
    if entrypoint is not None:
        metadata.setdefault("entrypoint", entrypoint)
    if layer is not None:
        metadata.setdefault("layer", layer)
    return metadata
