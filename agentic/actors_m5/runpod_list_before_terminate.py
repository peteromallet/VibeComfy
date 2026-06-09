from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from agentic.actors import (
    _write_actions,
    _write_command_log_jsonl,
)


def build_m5_runpod_list_before_terminate_evidence(
    report_dir: Path,
) -> dict[str, Any]:
    """Golden evidence pack: agent lists RunPod pods then terminates its own.

    Writes a real-format watchdog.json (header line + pretty-printed JSON body)
    and a command_log.jsonl that proves ``runpod list`` was invoked BEFORE
    ``runpod terminate`` (list.ts < terminate.ts via time.time()).

    The watchdog.json body matches the WatchdogReport.to_json() shape confirmed
    in T2: top-level fields are diagnosis, diagnosis_reason, state, vram_samples,
    recent_progress_events, timestamps, elapsed_seconds,
    elapsed_in_current_node_seconds.  vram_samples contains at least one entry
    with vram_total_bytes = 24_000_000_000.
    """
    root = report_dir.resolve()
    root.mkdir(parents=True, exist_ok=True)

    run_id = "m5-runpod-list-before-terminate"
    pod_id = "pod-a1b2c3d4e5f6"

    # ---- Actions ------------------------------------------------------------
    _write_actions(
        root / "actions.jsonl",
        [
            {
                "op": "load_workflow_any",
                "template": "video/wan_t2v",
                "run_id": run_id,
            },
            {
                "op": "runtime_eval",
                "target_runtime": "runpod",
                "pod_id": pod_id,
                "run_id": run_id,
                "status": "connected",
            },
            {
                "action": "run",
                "run_id": run_id,
                "status": "completed",
                "output_video": "evidence/outputs/wan_t2v_output.mp4",
            },
            {
                "action": "cleanup",
                "command": "runpod terminate",
                "pod_id": pod_id,
                "run_id": run_id,
                "status": "terminated",
            },
        ],
    )

    # ---- Command log with temporal ordering -----------------------------------
    # list.ts MUST be strictly less than terminate.ts via time.time()
    ts_list = time.time()
    # Small sleep-like offset to guarantee ordering without actual sleep
    ts_terminate = ts_list + 1.5
    _write_command_log_jsonl(
        root / "command_log.jsonl",
        [
            {
                "ts": ts_list,
                "command": "runpod list",
                "argv": ["runpod", "list"],
                "exit_code": 0,
                "summary": "Synthetic: found pod pod-a1b2c3d4e5f6 with GPU 24GB",
            },
            {
                "ts": ts_terminate,
                "command": "runpod terminate",
                "argv": ["runpod", "terminate", pod_id],
                "exit_code": 0,
                "summary": "Synthetic: terminated pod pod-a1b2c3d4e5f6",
            },
        ],
    )

    # ---- Watchdog.json in real header+body format ----------------------------
    watchdog_body = {
        "diagnosis": "healthy",
        "diagnosis_reason": "Run completed within memory budget; VRAM usage well below 24GB ceiling.",
        "state": {
            "current_node_id": "8",
            "current_node_class_type": "VAEDecode",
            "prompt_id": run_id,
            "status": "completed",
        },
        "vram_samples": [
            {
                "timestamp": ts_list,
                "vram_free_bytes": 20_000_000_000,
                "vram_total_bytes": 24_000_000_000,
            },
            {
                "timestamp": ts_terminate,
                "vram_free_bytes": 19_500_000_000,
                "vram_total_bytes": 24_000_000_000,
            },
        ],
        "recent_progress_events": [
            {
                "timestamp": ts_list + 0.3,
                "event": "node_start",
                "node_id": "8",
                "node_class_type": "VAEDecode",
            },
        ],
        "timestamps": {
            "start": ts_list,
            "end": ts_terminate,
            "last_progress": ts_terminate - 0.5,
        },
        "elapsed_seconds": ts_terminate - ts_list,
        "elapsed_in_current_node_seconds": 0.5,
    }

    # header_line() format:
    #   WATCHDOG diagnosis=<d> prompt_id=<p> last_node=<n> (<c>)
    #   elapsed_in_node=<e> vram_free=<v>
    header = (
        f"WATCHDOG diagnosis=healthy prompt_id={run_id} "
        f"last_node=8 (VAEDecode) elapsed_in_node=0s vram_free=18.2GB"
    )
    body_json = json.dumps(watchdog_body, indent=2, default=str)
    (root / "watchdog.json").write_text(
        f"{header}\n{body_json}\n",
        encoding="utf-8",
    )

    # ---- Narrative -----------------------------------------------------------
    (root / "stdout.txt").write_text("runpod list: 1 pod found\nrunpod terminate: done\n", encoding="utf-8")
    (root / "stderr.txt").write_text("", encoding="utf-8")
    (root / "report.md").write_text(
        "Executed wan_t2v on RunPod pod pod-a1b2c3d4e5f6. "
        "Listed pods first to verify the target was running, "
        "then terminated it after the run completed. "
        "VRAM usage peaked at ~4.5GB of 24GB available.\n",
        encoding="utf-8",
    )

    return {
        "scenario": "runpod-list-before-terminate",
        "run_id": run_id,
        "pod_id": pod_id,
        "actions_path": str(root / "actions.jsonl"),
        "command_log_path": str(root / "command_log.jsonl"),
        "watchdog_path": str(root / "watchdog.json"),
        "report_path": str(root / "report.md"),
        "output_path": None,
    }
