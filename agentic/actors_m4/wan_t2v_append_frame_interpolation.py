from __future__ import annotations

from pathlib import Path
from typing import Any

from agentic.actors import (
    _write_actions,
    _write_placeholder,
    _write_workflow_evidence,
)
from vibecomfy import load_workflow_any

# Recognizable interpolation class shared between this builder and the rubric.
# Opaque placeholder so the scenario stays offline-compilable while still
# modelling a real RIFE/FILM/GIMM-style VFI node that operates on IMAGES.
INTERP_CLASS = "vibecomfy.placeholder.frame_interpolation"

# Real wan_t2v node ids the edit must hang off of.
VAEDECODE_ID = "8"      # VAEDecode -> decoded IMAGES
CREATEVIDEO_ID = "49"   # CreateVideo -> takes images, feeds SaveVideo


def build_m4_wan_t2v_append_frame_interpolation_evidence(
    report_dir: Path,
) -> dict[str, Any]:
    """Append frame interpolation AFTER the VAE decode on the wan_t2v graph.

    Canonical correct edit:

    * Insert an interpolation node that consumes the VAEDecode IMAGE output.
    * Rewire CreateVideo's ``images`` input from the raw decode to the
      interpolation node's output, so the saved video uses the smoothed frames.

    The two traps a naive agent falls into -- interpolating on latents before
    the decode, or leaving the interpolation node orphaned while CreateVideo
    still references the raw decode -- are excluded by these two edge facts.
    """
    root = report_dir.resolve()
    root.mkdir(parents=True, exist_ok=True)

    workflow = load_workflow_any("video/wan_t2v")

    # 1. Add the interpolation node and feed it the decoded IMAGES (8.0).
    interp = workflow.add_node(INTERP_CLASS, multiplier=2)
    workflow.connect(f"{VAEDECODE_ID}.0", f"{interp.id}.images")

    # 2. Rewire the video combine node to consume interpolated frames, NOT the
    #    raw decode. This is the load-bearing edge the rubric enforces.
    workflow.replace_edge(f"{CREATEVIDEO_ID}.images", f"{interp.id}.0")

    workflow.finalize_metadata()

    output_path = root / "outputs" / "video.mp4"
    _write_placeholder(output_path, "structural video placeholder\n")

    evidence = _write_workflow_evidence(
        root=root,
        run_id="m4-wan-t2v-append-frame-interpolation",
        workflow=workflow,
        output_path=output_path,
        origin=(
            "agentic",
            "agentic/actors_m4/wan_t2v_append_frame_interpolation.py:build_m4_wan_t2v_append_frame_interpolation_evidence",
        ),
    )

    _write_actions(
        root / "actions.jsonl",
        [
            {
                "op": "load_workflow_any",
                "template": "video/wan_t2v",
                "run_id": evidence.run_id,
            },
            {
                "op": "add_node",
                "class_type": INTERP_CLASS,
                "node_id": interp.id,
                "run_id": evidence.run_id,
                "status": "added",
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
        "Appended a frame-interpolation node after the VAE decode and rewired "
        "the video combine node to consume the interpolated frames.\n",
        encoding="utf-8",
    )
    return {
        "scenario": "wan-t2v-append-frame-interpolation",
        "run_id": evidence.run_id,
        "compiled_api_path": evidence.compiled_api_path,
        "metadata_path": evidence.metadata_path,
        "actions_path": str(root / "actions.jsonl"),
        "output_path": str(output_path),
        "report_path": str(root / "report.md"),
    }
