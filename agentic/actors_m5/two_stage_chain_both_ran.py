from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from agentic.actors import (
    _write_actions,
    _write_command_log_jsonl,
    _write_placeholder,
)


def build_m5_two_stage_chain_both_ran_evidence(
    report_dir: Path,
) -> dict[str, Any]:
    """Two-stage chain: t2i → i2v, both stages completed.

    Writes TWO watchdog rollups (watchdog.t2i.json and watchdog.i2v.json) in
    the real header+body format to avoid clobber.  actions.jsonl records two
    stages (``t2i`` and ``i2v``) with ``status == 'completed'``.
    evidence/outputs/ contains a placeholder image and placeholder video.
    """
    root = report_dir.resolve()
    root.mkdir(parents=True, exist_ok=True)
    outputs_dir = root / "outputs"
    outputs_dir.mkdir(parents=True, exist_ok=True)

    run_id = "m5-two-stage-chain-both-ran"

    # ---- Placeholder outputs --------------------------------------------------
    (outputs_dir / "stage1_t2i_output.png").write_text("placeholder-image\n", encoding="utf-8")
    (outputs_dir / "stage2_i2v_output.mp4").write_text("placeholder-video\n", encoding="utf-8")

    # ---- Actions (two stages, both completed) --------------------------------
    ts_t2i_start = time.time()
    ts_t2i_end = ts_t2i_start + 3.0
    ts_i2v_start = ts_t2i_end + 0.2
    ts_i2v_end = ts_i2v_start + 5.0

    _write_actions(
        root / "actions.jsonl",
        [
            {
                "op": "load_workflow_any",
                "template": "image/sd3_medium_t2i",
                "run_id": run_id,
                "stage": "t2i",
                "status": "completed",
                "output": "evidence/outputs/stage1_t2i_output.png",
            },
            {
                "op": "load_workflow_any",
                "template": "video/wan_i2v",
                "run_id": run_id,
                "stage": "i2v",
                "status": "completed",
                "output": "evidence/outputs/stage2_i2v_output.mp4",
            },
        ],
    )

    # ---- Command log ---------------------------------------------------------
    _write_command_log_jsonl(
        root / "command_log.jsonl",
        [
            {
                "ts": ts_t2i_start,
                "command": "run",
                "argv": ["run", "image/sd3_medium_t2i", "--prompt", "a cat"],
                "exit_code": 0,
                "summary": "Synthetic: t2i stage completed, output stage1_t2i_output.png",
            },
            {
                "ts": ts_i2v_start,
                "command": "run",
                "argv": [
                    "run",
                    "video/wan_i2v",
                    "--input-image",
                    "evidence/outputs/stage1_t2i_output.png",
                ],
                "exit_code": 0,
                "summary": "Synthetic: i2v stage completed, output stage2_i2v_output.mp4",
            },
        ],
    )

    # ---- Watchdog rollups (header+body format, two files) ---------------------
    def _make_watchdog(
        diagnosis: str,
        stage_label: str,
        node_id: str,
        node_class: str,
        vram_samples: list[dict[str, Any]],
        elapsed: float,
    ) -> str:
        """Build a watchdog.json string in the real header+body format."""
        body = {
            "diagnosis": diagnosis,
            "diagnosis_reason": f"Stage {stage_label} completed successfully.",
            "state": {
                "current_node_id": node_id,
                "current_node_class_type": node_class,
                "prompt_id": run_id,
                "status": "completed",
            },
            "vram_samples": vram_samples,
            "recent_progress_events": [
                {
                    "timestamp": vram_samples[-1]["timestamp"] if vram_samples else ts_t2i_start,
                    "event": "node_complete",
                    "node_id": node_id,
                    "node_class_type": node_class,
                },
            ],
            "timestamps": {
                "start": vram_samples[0]["timestamp"] if vram_samples else ts_t2i_start,
                "end": vram_samples[-1]["timestamp"] if vram_samples else ts_t2i_start + elapsed,
            },
            "elapsed_seconds": elapsed,
            "elapsed_in_current_node_seconds": elapsed * 0.5,
        }
        vram_free_str = ""
        if vram_samples:
            free = vram_samples[-1].get("vram_free_bytes")
            if isinstance(free, int):
                vram_free_str = f"{free / (1024**3):.1f}GB"
        header = (
            f"WATCHDOG diagnosis={diagnosis} prompt_id={run_id} "
            f"last_node={node_id} ({node_class}) elapsed_in_node={int(elapsed * 0.5)}s "
            f"vram_free={vram_free_str}"
        )
        body_json = json.dumps(body, indent=2, default=str)
        return f"{header}\n{body_json}\n"

    t2i_vram = [
        {
            "timestamp": ts_t2i_start + 0.5,
            "vram_free_bytes": 18_000_000_000,
            "vram_total_bytes": 24_000_000_000,
        },
        {
            "timestamp": ts_t2i_end,
            "vram_free_bytes": 16_500_000_000,
            "vram_total_bytes": 24_000_000_000,
        },
    ]
    i2v_vram = [
        {
            "timestamp": ts_i2v_start + 0.5,
            "vram_free_bytes": 15_000_000_000,
            "vram_total_bytes": 24_000_000_000,
        },
        {
            "timestamp": ts_i2v_end,
            "vram_free_bytes": 13_000_000_000,
            "vram_total_bytes": 24_000_000_000,
        },
    ]

    (root / "watchdog.t2i.json").write_text(
        _make_watchdog("healthy", "t2i", "17", "KSampler", t2i_vram, 3.0),
        encoding="utf-8",
    )
    (root / "watchdog.i2v.json").write_text(
        _make_watchdog("healthy", "i2v", "40", "EmptyHunyuanLatentVideo", i2v_vram, 5.0),
        encoding="utf-8",
    )

    # ---- Narrative -----------------------------------------------------------
    (root / "stdout.txt").write_text("stage1: t2i done\nstage2: i2v done\n", encoding="utf-8")
    (root / "stderr.txt").write_text("", encoding="utf-8")
    (root / "report.md").write_text(
        "Two-stage chain completed successfully. "
        "Stage 1 (t2i): generated a 1024x1024 image from SD3 Medium. "
        "Stage 2 (i2v): turned that image into a 2-second video via wan_i2v. "
        "Both stages completed without errors.\n",
        encoding="utf-8",
    )

    return {
        "scenario": "two-stage-chain-both-ran",
        "run_id": run_id,
        "actions_path": str(root / "actions.jsonl"),
        "command_log_path": str(root / "command_log.jsonl"),
        "watchdog_t2i_path": str(root / "watchdog.t2i.json"),
        "watchdog_i2v_path": str(root / "watchdog.i2v.json"),
        "report_path": str(root / "report.md"),
        "output_path": str(outputs_dir),
    }
