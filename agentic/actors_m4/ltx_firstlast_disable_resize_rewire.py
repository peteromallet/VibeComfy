"""Builder for the ltx-firstlast-disable-resize-rewire recovery scenario.

Models the user task: on the LTX 2.3 first-last-frame workflow
(video/ltx2_3_runexx_first_last_frame) DISABLE the resize node on the frame
inputs (keep the original resolution) and rewire the graph so the
original-resolution frames flow straight through to the downstream consumers.

The naive "compiles-but-wrong" trap: deleting / bypassing the resize node but
leaving its former consumers (ResizeImageMaskNode and LTXVAddGuide) with a
dangling input that still points at the removed node, so the graph will not
queue. The canonical edit instead rewires every consumer of the resize output
to read directly from the resize node's former upstream source, then removes
the now-orphaned resize node entirely.

Concretely, in the real template:
  * node "49" (ResizeImagesByLongerEdge) reads ``images`` from ``["48", 0]``
    (the ImageResizeKJv2 output for the second / last frame).
  * node "49" output is consumed by node "2" (ResizeImageMaskNode ``.input``)
    and node "2152" (LTXVAddGuide ``.image``).

The correct disable+rewire: point ``2.input`` and ``2152.image`` directly at
``["48", 0]`` (the resize's former source), then remove node "49". No
ResizeImagesByLongerEdge node "49" remains feeding the pipeline and nothing
dangles.
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


# Resize node we are disabling, its former upstream source, and the consumers
# that read its output. Grounded in the real template's compiled graph.
RESIZE_NODE_ID = "49"            # ResizeImagesByLongerEdge on the last-frame input
RESIZE_SOURCE_REF = "48.0"       # ImageResizeKJv2 output that fed the resize
CONSUMER_REFS = ("2.input", "2152.image")  # ResizeImageMaskNode / LTXVAddGuide


def build_m4_ltx_firstlast_disable_resize_rewire_evidence(report_dir: Path) -> dict[str, Any]:
    """Write structural evidence for disabling + rewiring the LTX resize node."""
    root = report_dir.resolve()
    root.mkdir(parents=True, exist_ok=True)

    workflow = load_workflow_any("video/ltx2_3_runexx_first_last_frame")

    # Rewire every consumer of the resize OUTPUT to the resize's former SOURCE,
    # so the original-resolution frames flow straight through.
    for consumer_ref in CONSUMER_REFS:
        workflow.replace_edge(consumer_ref, RESIZE_SOURCE_REF)

    # Remove the now-orphaned resize node so nothing remains feeding the pipeline.
    workflow.remove_node(RESIZE_NODE_ID)

    workflow.finalize_metadata()

    output_path = root / "outputs" / "video.mp4"
    _write_placeholder(output_path, "structural video placeholder\n")

    evidence = _write_workflow_evidence(
        root=root,
        run_id="m4-ltx-firstlast-disable-resize-rewire",
        workflow=workflow,
        output_path=output_path,
        origin=(
            "agentic",
            "agentic/actors_m4/ltx_firstlast_disable_resize_rewire.py:"
            "build_m4_ltx_firstlast_disable_resize_rewire_evidence",
        ),
    )

    _write_actions(
        root / "actions.jsonl",
        [
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
        "Disabled the last-frame resize node (ResizeImagesByLongerEdge) on the "
        "LTX first-last-frame workflow and rewired its consumers "
        "(ResizeImageMaskNode, LTXVAddGuide) directly to the resize node's "
        "former source so original-resolution frames flow straight through. "
        "The orphaned resize node was removed and nothing dangles.\n",
        encoding="utf-8",
    )

    return {
        "scenario": "ltx-firstlast-disable-resize-rewire",
        "run_id": evidence.run_id,
        "compiled_api_path": evidence.compiled_api_path,
        "metadata_path": evidence.metadata_path,
        "actions_path": str(root / "actions.jsonl"),
        "output_path": str(output_path),
        "report_path": str(root / "report.md"),
    }
