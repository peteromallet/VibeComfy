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

# Real wan_t2v node ids for the CreateVideo node whose images input we break.
CREATEVIDEO_ID = "49"


def build_m5_diagnose_broken_graph_evidence(
    report_dir: Path,
) -> dict[str, Any]:
    """Diagnose a broken graph: wan_t2v with CreateVideo.images disconnected.

    The agent must detect that node 49 (CreateVideo) has a disconnected
    ``images`` input — no upstream node feeds it.  The builder deliberately
    disconnects that edge to create a fault, records synthetic diagnostic CLI
    invocations into ``command_log.jsonl``, and writes a ``fault_report.json``
    describing the break so the rubric can verify the agent found it.
    """
    root = report_dir.resolve()
    root.mkdir(parents=True, exist_ok=True)

    workflow = load_workflow_any("video/wan_t2v")

    # ---- Introduce the fault: disconnect CreateVideo's images input ----------
    workflow.disconnect(f"{CREATEVIDEO_ID}.images")

    workflow.finalize_metadata()

    output_path = root / "outputs" / "video.mp4"
    _write_placeholder(output_path, "structural video placeholder\n")

    evidence = _write_workflow_evidence(
        root=root,
        run_id="m5-diagnose-broken-graph",
        workflow=workflow,
        output_path=output_path,
        origin=(
            "agentic",
            "agentic/actors_m5/diagnose_broken_graph.py:build_m5_diagnose_broken_graph_evidence",
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
                "op": "disconnect",
                "node_id": CREATEVIDEO_ID,
                "input": "images",
                "run_id": evidence.run_id,
                "status": "fault_introduced",
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
                "argv": ["analyze", "unconnected"],
                "exit_code": 0,
                "summary": "Synthetic: detected unconnected input 49.images",
            },
            {
                "ts": ts + 0.1,
                "command": "analyze",
                "argv": ["analyze", "trace"],
                "exit_code": 0,
                "summary": "Synthetic: traced upstream of 49.images — no source found",
            },
        ],
    )

    # ---- Fault report --------------------------------------------------------
    fault_report = {
        "broken_input_node_id": "49",
        "broken_input_field": "images",
    }
    (root / "fault_report.json").write_text(
        json.dumps(fault_report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    # ---- Narrative -----------------------------------------------------------
    (root / "stdout.txt").write_text("", encoding="utf-8")
    (root / "stderr.txt").write_text("", encoding="utf-8")
    (root / "report.md").write_text(
        "Diagnosed broken graph: CreateVideo (node 49) has a disconnected "
        "``images`` input. No upstream node feeds it, so the video combine "
        "step cannot execute.\n",
        encoding="utf-8",
    )

    return {
        "scenario": "diagnose-broken-graph",
        "run_id": evidence.run_id,
        "compiled_api_path": evidence.compiled_api_path,
        "metadata_path": evidence.metadata_path,
        "actions_path": str(root / "actions.jsonl"),
        "command_log_path": str(root / "command_log.jsonl"),
        "fault_report_path": str(root / "fault_report.json"),
        "output_path": str(output_path),
        "report_path": str(root / "report.md"),
    }
