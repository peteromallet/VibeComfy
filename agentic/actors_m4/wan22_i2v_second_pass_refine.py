"""Builder for the Wan 2.2 i2v two-pass high-resolution refine scenario.

Loads the real ``video/wan22_i2v_comfy_lightx2v`` ready template, then adds a
genuine second high-resolution refinement pass on top of the existing base
generation: take the base pipeline's final LATENT, upscale it, run a NEW refine
sampler at low denoise seeded from that upscaled latent, and rewire the decoder
to consume the refine sampler's output.

The deepest "compiles-but-wrong" trap is feeding the refine sampler a fresh /
original empty latent (so the refinement ignores the base generation) or
leaving the decoder pointed at the base sampler (so the refined latent is never
decoded). The canonical edit below threads the latent correctly:

    base sampler 14  ->  LatentUpscale  ->  refine sampler  ->  VAEDecode

so the enforced compiled_api.json edge-reference checks pass.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from agentic.actors import (
    _write_actions,
    _write_placeholder,
    _write_workflow_evidence,
)
from vibecomfy import load_workflow_any


def build_m4_wan22_i2v_second_pass_refine_evidence(report_dir: Path) -> dict[str, Any]:
    """Compile-only evidence for the Wan 2.2 i2v two-pass refine edit."""
    root = report_dir.resolve()
    root.mkdir(parents=True, exist_ok=True)

    # Load the REAL Wan 2.2 i2v ready template and edit it in place.
    workflow = load_workflow_any("video/wan22_i2v_comfy_lightx2v")

    # The base template ends in: KSamplerAdvanced('14') -> VAEDecode('15').
    # Add a true high-res refine pass that consumes the base sampler's LATENT.
    base_sampler_id = "14"
    decode_id = "15"

    upscale = workflow.add_node(
        "LatentUpscale",
        upscale_method="nearest-exact",
        width=1280,
        height=1280,
        crop="disabled",
    )
    # Upscale the FIRST pass's LATENT output (not a fresh empty latent).
    workflow.connect(f"{base_sampler_id}.0", f"{upscale.id}.samples")

    refine = workflow.add_node(
        "KSamplerAdvanced",
        add_noise="enable",
        noise_seed=987654,
        steps=8,
        cfg=1.0,
        sampler_name="euler",
        scheduler="simple",
        start_at_step=4,
        end_at_step=8,
        return_with_leftover_noise="disable",
    )
    # Refine sampler reads the UPSCALED base latent, plus model/conditioning.
    workflow.connect(f"{upscale.id}.0", f"{refine.id}.latent_image")
    workflow.connect("11.0", f"{refine.id}.model")
    workflow.connect("12.0", f"{refine.id}.positive")
    workflow.connect("12.1", f"{refine.id}.negative")

    # Decode the REFINED latent, not the base sampler's latent.
    workflow.replace_edge(f"{decode_id}.samples", f"{refine.id}.0")

    workflow.finalize_metadata()

    output_path = root / "outputs" / "video.mp4"
    _write_placeholder(output_path, "structural wan22 refine video placeholder\n")

    evidence = _write_workflow_evidence(
        root=root,
        run_id="m4-wan22-i2v-second-pass-refine",
        workflow=workflow,
        output_path=output_path,
        origin=(
            "agentic",
            "agentic/actors_m4/wan22_i2v_second_pass_refine.py:"
            "build_m4_wan22_i2v_second_pass_refine_evidence",
        ),
    )

    _write_actions(
        root / "actions.jsonl",
        [
            {
                "op": "load_workflow_any",
                "template": "video/wan22_i2v_comfy_lightx2v",
                "run_id": evidence.run_id,
            },
            {
                "op": "ir_edit",
                "edits": [
                    {"node": "LatentUpscale", "from": f"{base_sampler_id}.0", "to": "samples"},
                    {"node": "KSamplerAdvanced", "field": "latent_image", "from": f"{upscale.id}.0"},
                    {"node": "VAEDecode", "field": "samples", "from": f"{refine.id}.0"},
                ],
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
        "Added a high-res second refine pass to the Wan 2.2 i2v template: "
        "base latent -> LatentUpscale -> low-denoise refine sampler -> decode.\n",
        encoding="utf-8",
    )
    return {
        "scenario": "wan22-i2v-second-pass-refine",
        "run_id": evidence.run_id,
        "compiled_api_path": evidence.compiled_api_path,
        "metadata_path": evidence.metadata_path,
        "actions_path": str(root / "actions.jsonl"),
        "output_path": str(output_path),
        "report_path": str(root / "report.md"),
    }
