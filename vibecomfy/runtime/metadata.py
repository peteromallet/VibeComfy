from __future__ import annotations

import hashlib
import json
import subprocess
from dataclasses import asdict
from typing import Any

from vibecomfy.memory_profile import MemoryProfile
from vibecomfy.workflow import VibeWorkflow

from .config import SessionConfig


def _run_metadata(
    *,
    run_id: str,
    workflow: VibeWorkflow,
    api_dict: dict[str, Any],
    queued: Any,
    outputs: list[str],
    runtime: str,
    config: SessionConfig | None = None,
) -> dict[str, Any]:
    serialized = json.dumps(api_dict, sort_keys=True, default=str)
    metadata = {
        "run_id": run_id,
        "workflow_id": workflow.id,
        "source": asdict(workflow.source),
        "workflow_hash": hashlib.sha256(serialized.encode("utf-8")).hexdigest(),
        "git_sha": _git_sha(),
        "inputs": {name: item.value for name, item in workflow.inputs.items()},
        "queued": queued,
        "outputs": outputs,
        "runtime": runtime,
    }
    if config is not None and config.memory_profile is not None:
        metadata.update(MemoryProfile.parse(config.memory_profile).to_telemetry())
    return metadata


def _git_sha() -> str | None:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return None
    return result.stdout.strip() or None
