from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from agentic.actors import (
    _write_actions,
    _write_command_log_jsonl,
    _write_placeholder,
    _write_workflow_evidence,
)
from vibecomfy import load_workflow_any

# The resolution-setting node in video/wan_t2v: EmptyHunyuanLatentVideo
RESOLUTION_NODE_ID = 40
RESOLUTION_WIDTH = 832
RESOLUTION_HEIGHT = 480


def build_m5_trace_resolution_source_evidence(
    report_dir: Path,
) -> dict[str, Any]:
    """Trace the resolution source: which node sets output width/height.

    Loads the wan_t2v template, identifies the EmptyHunyuanLatentVideo node
    that defines the latent dimensions (width, height), records synthetic
    diagnostic CLI invocations, and writes resolution_source.json documenting
    the node and its resolution values.
    """
    root = report_dir.resolve()
    root.mkdir(parents=True, exist_ok=True)

    workflow = load_workflow_any("video/wan_t2v")

    # Read the resolution from the actual node to ensure correctness.
    node = workflow.nodes[str(RESOLUTION_NODE_ID)]
    width = node.inputs["width"]
    height = node.inputs["height"]

    workflow.finalize_metadata()

    output_path = root / "outputs" / "video.mp4"
    _write_placeholder(output_path, "structural video placeholder\n")

    evidence = _write_workflow_evidence(
        root=root,
        run_id="m5-trace-resolution-source",
        workflow=workflow,
        output_path=output_path,
        origin=(
            "agentic",
            "agentic/actors_m5/trace_resolution_source.py:build_m5_trace_resolution_source_evidence",
        ),
    )

    # ---- Action log ----------------------------------------------------------
    _write_actions(
        root / "actions.jsonl",
        [
            {
                "op": "load_workflow_any",
                "template": "video/wan_t2v",
                "run_id": evidence.run_id,
            },
            {
                "op": "inspect_node",
                "node_id": str(RESOLUTION_NODE_ID),
                "class_type": node.class_type,
                "run_id": evidence.run_id,
                "status": "resolved",
            },
            {
                "op": "finalize_metadata",
                "run_id": evidence.run_id,
                "status": "completed",
            },
        ],
    )

    # ---- Synthetic command log (M5 trajectory format) ------------------------
    ts = time.time()
    _write_command_log_jsonl(
        root / "command_log.jsonl",
        [
            {
                "ts": ts,
                "command": "analyze",
                "argv": ["analyze", "trace"],
                "exit_code": 0,
                "summary": "Synthetic: traced resolution upstream to latent node",
            },
            {
                "ts": ts + 0.1,
                "command": "analyze",
                "argv": ["analyze", "values"],
                "exit_code": 0,
                "summary": f"Synthetic: read resolution values width={width} height={height}",
            },
        ],
    )

    # ---- Resolution source report --------------------------------------------
    resolution_source = {
        "node_id": int(RESOLUTION_NODE_ID),
        "width": int(width),
        "height": int(height),
    }
    (root / "resolution_source.json").write_text(
        json.dumps(resolution_source, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    # ---- Narrative -----------------------------------------------------------
    (root / "stdout.txt").write_text("", encoding="utf-8")
    (root / "stderr.txt").write_text("", encoding="utf-8")
    (root / "report.md").write_text(
        f"Traced resolution source: node {RESOLUTION_NODE_ID} "
        f"(EmptyHunyuanLatentVideo) sets the latent dimensions to "
        f"{width}x{height}. This determines the output resolution.\n",
        encoding="utf-8",
    )

    return {
        "scenario": "trace-resolution-source",
        "run_id": evidence.run_id,
        "compiled_api_path": evidence.compiled_api_path,
        "metadata_path": evidence.metadata_path,
        "actions_path": str(root / "actions.jsonl"),
        "command_log_path": str(root / "command_log.jsonl"),
        "resolution_source_path": str(root / "resolution_source.json"),
        "output_path": str(output_path),
        "report_path": str(root / "report.md"),
    }
