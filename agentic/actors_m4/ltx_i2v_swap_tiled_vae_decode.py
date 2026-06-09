"""Builder: swap LTX tiled VAE decode for a standard VAE Decode.

Grounds in the real ``video/ltx2_3_i2v`` ready template. That workflow decodes
its video latents through ``LTXVTiledVAEDecode`` nodes (a common source of grid
artifacts from wrong temporal-tiling settings). The canonical edit replaces every
tiled decoder with a standard ``VAEDecode`` that consumes the *same* upstream
latent and vae, and repoints the downstream ``CreateVideo`` consumer at the new
decode — so the declared ``SaveVideo`` output stays wired and nothing dangles.

The trap a naive agent falls into: removing/replacing the tiled node but
orphaning it or dropping the edge into the downstream consumer, leaving a
dangling required input that will not queue.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from agentic.actors import _write_actions, _write_placeholder, _write_workflow_evidence
from vibecomfy import load_workflow_any

# (tiled-decode node id, downstream CreateVideo consumer id) pairs in the real
# template. 4983 -> CreateVideo 4819 -> SaveVideo 4823 is the declared output
# chain; 4982 -> CreateVideo 4849 -> SaveVideo 4852 is the parallel chain.
_TILED_DECODE_PAIRS = (("4983", "4819"), ("4982", "4849"))
_TILED_CLASS = "LTXVTiledVAEDecode"


def _swap_one(workflow: Any, tiled_id: str, consumer_id: str) -> str:
    """Replace tiled decoder ``tiled_id`` with a standard VAEDecode.

    Returns the new VAEDecode node id. The new node consumes the SAME latents
    and vae the tiled node consumed; the downstream CreateVideo ``images`` input
    is repointed at the new node; the tiled node is removed.
    """
    incoming = {
        edge.to_input: (edge.from_node, edge.from_output)
        for edge in workflow.edges
        if edge.to_node == tiled_id
    }
    latents_from = incoming["latents"]
    vae_from = incoming["vae"]

    decode = workflow.add_node("VAEDecode")
    workflow.connect(f"{latents_from[0]}.{latents_from[1]}", f"{decode.id}.samples")
    workflow.connect(f"{vae_from[0]}.{vae_from[1]}", f"{decode.id}.vae")
    workflow.replace_edge(f"{consumer_id}.images", f"{decode.id}.0")
    workflow.remove_node(tiled_id)
    return str(decode.id)


def build_m4_ltx_i2v_swap_tiled_vae_decode_evidence(report_dir: Path) -> dict[str, Any]:
    """Construct the canonical tiled->standard VAE decode swap and freeze evidence."""
    root = report_dir.resolve()
    root.mkdir(parents=True, exist_ok=True)

    workflow = load_workflow_any("video/ltx2_3_i2v")

    new_decode_ids: list[str] = []
    for tiled_id, consumer_id in _TILED_DECODE_PAIRS:
        new_decode_ids.append(_swap_one(workflow, tiled_id, consumer_id))

    workflow.finalize_metadata()

    output_path = root / "outputs" / "video.mp4"
    _write_placeholder(output_path, "structural video placeholder\n")

    evidence = _write_workflow_evidence(
        root=root,
        run_id="m4-ltx-i2v-swap-tiled-vae-decode",
        workflow=workflow,
        output_path=output_path,
        origin=(
            "agentic",
            "agentic/actors_m4/ltx_i2v_swap_tiled_vae_decode.py:"
            "build_m4_ltx_i2v_swap_tiled_vae_decode_evidence",
        ),
    )

    _write_actions(
        root / "actions.jsonl",
        [
            {
                "op": "swap_node",
                "removed_class": _TILED_CLASS,
                "removed_id": tiled_id,
                "added_class": "VAEDecode",
                "added_id": new_id,
                "downstream_consumer": consumer_id,
                "run_id": evidence.run_id,
                "status": "completed",
            }
            for (tiled_id, consumer_id), new_id in zip(
                _TILED_DECODE_PAIRS, new_decode_ids
            )
        ]
        + [
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
        "Swapped LTX tiled VAE decode for standard VAEDecode, preserving latent "
        "and vae inputs and the downstream save chain.\n",
        encoding="utf-8",
    )
    return {
        "scenario": "ltx-i2v-swap-tiled-vae-decode",
        "run_id": evidence.run_id,
        "compiled_api_path": evidence.compiled_api_path,
        "metadata_path": evidence.metadata_path,
        "actions_path": str(root / "actions.jsonl"),
        "output_path": str(output_path),
        "report_path": str(root / "report.md"),
    }
