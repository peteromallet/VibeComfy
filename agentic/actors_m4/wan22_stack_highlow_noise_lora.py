from __future__ import annotations

from pathlib import Path
from typing import Any

from agentic.actors import _write_actions, _write_placeholder, _write_workflow_evidence
from vibecomfy import load_workflow_any

# The user's 2-stage LoRA. The real Kijai Wan 2.2 wrapper template already drives
# the high-noise and low-noise model paths through separate WanVideoLoraSelect ->
# WanVideoSetLoRAs chains, so the canonical "stack a LoRA on BOTH stages" edit is
# to splice one additional WanVideoLoraSelect into the prev_lora head of each path.
STACK_LORA = (
    "WanVideo/Lightx2v/lightx2v_I2V_14B_480p_cfg_step_distill_rank64_bf16.safetensors"
)

# Strengths differ per stage: the high-noise stage carries the structural pass,
# the low-noise stage refines, so it gets a slightly lower strength.
HIGH_STRENGTH = 1.0
LOW_STRENGTH = 0.8

# Stable explicit ids so enforced checks can anchor on the compiled graph.
HIGH_LORA_ID = "stack_lora_high"
LOW_LORA_ID = "stack_lora_low"

# Existing per-path LoRA-select heads in the real template:
#   '6'  -> WanVideoLoraSelect feeding the HIGH-noise SetLoRAs ('21') -> sampler '23'
#   '11' -> WanVideoLoraSelect feeding the LOW-noise  SetLoRAs ('20') -> sampler '24'
EXISTING_HIGH_LORA_HEAD = "6"
EXISTING_LOW_LORA_HEAD = "11"


def build_m4_wan22_stack_highlow_noise_lora_evidence(report_dir: Path) -> dict[str, Any]:
    """Stack a 2-stage LoRA onto BOTH the high-noise and low-noise Wan 2.2 paths."""
    root = report_dir.resolve()
    root.mkdir(parents=True, exist_ok=True)

    workflow = load_workflow_any("video/wanvideo_wrapper_22_14b_i2v_kijai")

    # HIGH-noise path: splice the user's LoRA into the prev_lora head feeding the
    # high-noise sampler's model chain.
    high_lora = workflow.add_node(
        "WanVideoLoraSelect",
        _id=HIGH_LORA_ID,
        lora=STACK_LORA,
        strength=HIGH_STRENGTH,
        merge_loras=False,
    )
    workflow.connect(f"{high_lora.id}.0", f"{EXISTING_HIGH_LORA_HEAD}.prev_lora")

    # LOW-noise path: same splice, independent node, into the low-noise head.
    low_lora = workflow.add_node(
        "WanVideoLoraSelect",
        _id=LOW_LORA_ID,
        lora=STACK_LORA,
        strength=LOW_STRENGTH,
        merge_loras=False,
    )
    workflow.connect(f"{low_lora.id}.0", f"{EXISTING_LOW_LORA_HEAD}.prev_lora")

    workflow.finalize_metadata()

    output_path = root / "outputs" / "video.mp4"
    _write_placeholder(output_path, "structural video placeholder\n")

    evidence = _write_workflow_evidence(
        root=root,
        run_id="m4-wan22-stack-highlow-noise-lora",
        workflow=workflow,
        output_path=output_path,
        origin=(
            "agentic",
            "agentic/actors_m4/wan22_stack_highlow_noise_lora.py:build_m4_wan22_stack_highlow_noise_lora_evidence",
        ),
    )
    _write_actions(
        root / "actions.jsonl",
        [
            {
                "op": "finalize_metadata",
                "run_id": evidence.run_id,
                "status": "completed",
            }
        ],
    )
    (root / "stdout.txt").write_text("", encoding="utf-8")
    (root / "stderr.txt").write_text("", encoding="utf-8")
    (root / "report.md").write_text(
        "Stacked the 2-stage LoRA onto both the high-noise and low-noise Wan 2.2 "
        "model chains via per-path WanVideoLoraSelect splices.\n",
        encoding="utf-8",
    )
    return {
        "scenario": "wan22-stack-highlow-noise-lora",
        "run_id": evidence.run_id,
        "compiled_api_path": evidence.compiled_api_path,
        "metadata_path": evidence.metadata_path,
        "actions_path": str(root / "actions.jsonl"),
        "output_path": str(output_path),
        "report_path": str(root / "report.md"),
    }
