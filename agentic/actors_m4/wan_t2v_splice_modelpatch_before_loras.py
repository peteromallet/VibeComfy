"""Structural actor: splice a model-optimization node UPSTREAM of the LoRA loader.

Base template: ``video/wanvideo_wrapper_21_14b_t2v``. The real model chain is

    WanVideoModelLoader(22) -> WanVideoSetLoRAs(58) -> WanVideoSetBlockSwap(56) -> WanVideoSampler(27)

The user wants a model-optimization node (a torch-compile / model-modifier) spliced
onto the BASE model, BEFORE the LoRA loader, so the optimization wraps the full
model+lora stack rather than sitting between the loras and the sampler.

The canonical correct edit inserts ``WanVideoTorchCompileSettings`` between the base
``WanVideoModelLoader`` and ``WanVideoSetLoRAs``: the new node consumes node 22's
model output, and the LoRA loader is rewired to consume the new node's output. The
downstream block-swap + sampler chain is left intact, so the sampler still receives
the post-lora model.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from agentic.actors import _write_actions, _write_placeholder, _write_workflow_evidence
from vibecomfy import load_workflow_any


def build_m4_wan_t2v_splice_modelpatch_before_loras_evidence(
    report_dir: Path,
) -> dict[str, Any]:
    """Compile-only evidence for splicing a model-patch upstream of the loras."""
    root = report_dir.resolve()
    root.mkdir(parents=True, exist_ok=True)

    workflow = load_workflow_any("video/wanvideo_wrapper_21_14b_t2v")

    # Insert the model-optimization node and rewire it onto the BASE model,
    # UPSTREAM of the LoRA loader (node 58).
    optimization = workflow.add_node("WanVideoTorchCompileSettings")
    # LoRA loader's model input used to reference the base loader (node 22);
    # rewire it to the optimization node instead.
    workflow.replace_edge("58.model", f"{optimization.id}.0")
    # The optimization node consumes the base WanVideoModelLoader output (node 22).
    workflow.connect("22.0", f"{optimization.id}.model")
    workflow.finalize_metadata()

    output_path = root / "outputs" / "video.mp4"
    _write_placeholder(output_path, "structural video placeholder\n")

    evidence = _write_workflow_evidence(
        root=root,
        run_id="m4-wan-t2v-splice-modelpatch-before-loras",
        workflow=workflow,
        output_path=output_path,
        origin=(
            "agentic",
            "agentic/actors_m4/wan_t2v_splice_modelpatch_before_loras.py:"
            "build_m4_wan_t2v_splice_modelpatch_before_loras_evidence",
        ),
    )
    _write_actions(
        root / "actions.jsonl",
        [
            {
                "op": "add_node",
                "class_type": "WanVideoTorchCompileSettings",
                "node_id": optimization.id,
                "run_id": evidence.run_id,
                "status": "completed",
            },
            {
                "op": "splice",
                "position": "upstream_of_loras",
                "base_model_node": "22",
                "lora_loader_node": "58",
                "optimization_node": optimization.id,
                "run_id": evidence.run_id,
                "status": "completed",
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
        "Spliced WanVideoTorchCompileSettings onto the base WanVideoModelLoader, "
        "upstream of the LoRA loader, so the optimization wraps the full model+lora "
        "stack while the sampler still receives the post-lora model.\n",
        encoding="utf-8",
    )
    return {
        "scenario": "wan-t2v-splice-modelpatch-before-loras",
        "run_id": evidence.run_id,
        "compiled_api_path": evidence.compiled_api_path,
        "metadata_path": evidence.metadata_path,
        "actions_path": str(root / "actions.jsonl"),
        "output_path": str(output_path),
        "report_path": str(root / "report.md"),
    }
