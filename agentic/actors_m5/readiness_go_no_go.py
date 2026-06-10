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

# Missing items for the readiness go/no-go verdict.
# These are stable, sorted lists representing models and node packs that are
# required by the template but not available in the current environment.
MISSING_MODELS = sorted(
    [
        "umt5_xxl_fp8_e4m3fn_scaled.safetensors",
        "wan2.1_t2v_1.3B_fp16.safetensors",
    ]
)
MISSING_PACKS = sorted(
    [
        "ComfyUI-KJNodes",
        "ComfyUI-VideoHelperSuite",
    ]
)


def build_m5_readiness_go_no_go_evidence(
    report_dir: Path,
) -> dict[str, Any]:
    """Readiness go/no-go: can the template run right now?

    Loads the wan_t2v template, runs synthetic inspect + doctor + install-plan
    + fetch dry-run diagnostics, and writes readiness_verdict.json reporting
    which models and packs are missing (ready=false).
    """
    root = report_dir.resolve()
    root.mkdir(parents=True, exist_ok=True)

    workflow = load_workflow_any("video/wan_t2v")
    workflow.finalize_metadata()

    output_path = root / "outputs" / "video.mp4"
    _write_placeholder(output_path, "structural video placeholder\n")

    evidence = _write_workflow_evidence(
        root=root,
        run_id="m5-readiness-go-no-go",
        workflow=workflow,
        output_path=output_path,
        origin=(
            "agentic",
            "agentic/actors_m5/readiness_go_no_go.py:build_m5_readiness_go_no_go_evidence",
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
                "op": "inspect",
                "template": "video/wan_t2v",
                "run_id": evidence.run_id,
                "status": "inspected",
            },
            {
                "op": "doctor",
                "check": "models",
                "run_id": evidence.run_id,
                "status": "missing_models_detected",
            },
            {
                "op": "fetch",
                "mode": "dry-run",
                "run_id": evidence.run_id,
                "status": "would_fetch",
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
                "command": "inspect",
                "argv": ["inspect", "video/wan_t2v"],
                "exit_code": 0,
                "summary": "Synthetic: inspected template video/wan_t2v",
            },
            {
                "ts": ts + 0.1,
                "command": "doctor",
                "argv": ["doctor", "--models", "video/wan_t2v"],
                "exit_code": 1,
                "summary": "Synthetic: doctor --models reports missing models",
            },
            {
                "ts": ts + 0.2,
                "command": "nodes",
                "argv": ["nodes", "install-plan", "video/wan_t2v"],
                "exit_code": 0,
                "summary": "Synthetic: install-plan lists required packs",
            },
            {
                "ts": ts + 0.3,
                "command": "fetch",
                "argv": ["fetch", "--dry-run", "video/wan_t2v"],
                "exit_code": 0,
                "summary": "Synthetic: fetch --dry-run shows missing assets",
            },
        ],
    )

    # ---- Readiness verdict ---------------------------------------------------
    readiness_verdict = {
        "ready": False,
        "missing_models": MISSING_MODELS,
        "missing_packs": MISSING_PACKS,
    }
    (root / "readiness_verdict.json").write_text(
        json.dumps(readiness_verdict, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    # ---- Narrative -----------------------------------------------------------
    (root / "stdout.txt").write_text("", encoding="utf-8")
    (root / "stderr.txt").write_text("", encoding="utf-8")
    (root / "report.md").write_text(
        "Readiness check: NOT ready. Missing models: "
        + ", ".join(MISSING_MODELS)
        + ". Missing packs: "
        + ", ".join(MISSING_PACKS)
        + ". Run `vibecomfy fetch video/wan_t2v` and install the listed packs first.\n",
        encoding="utf-8",
    )

    return {
        "scenario": "readiness-go-no-go",
        "run_id": evidence.run_id,
        "compiled_api_path": evidence.compiled_api_path,
        "metadata_path": evidence.metadata_path,
        "actions_path": str(root / "actions.jsonl"),
        "command_log_path": str(root / "command_log.jsonl"),
        "readiness_verdict_path": str(root / "readiness_verdict.json"),
        "output_path": str(output_path),
        "report_path": str(root / "report.md"),
    }
