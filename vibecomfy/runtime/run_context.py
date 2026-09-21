"""The CLI attempt identity, established before executing workflow Python."""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from vibecomfy.utils import atomic_write_json


@dataclass
class RunContext:
    run_id: str
    run_dir: Path
    phase: str = "setup"
    error: BaseException | None = None
    diagnostics: list[dict[str, Any]] = field(default_factory=list)
    task_id: str | None = None
    attempt_id: str | None = None
    execution_id: str | None = None

    @property
    def receipt_path(self) -> Path:
        return self.run_dir / "attempt.json"

    def begin(self, reference: str) -> None:
        payload: dict[str, Any] = {
            "run_id": self.run_id,
            "receipt_path": str(self.receipt_path),
            "source_reference": reference,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "status": "started",
            "phase": self.phase,
            "queue_status": "not_attempted",
            "queue_acceptance": {"status": "not_attempted", "prompt_id": None},
            "prompt_id": None,
            "diagnostics": [],
        }
        for field_name in ("task_id", "attempt_id", "execution_id"):
            value = getattr(self, field_name)
            if value is not None:
                payload[field_name] = value
        atomic_write_json(self.receipt_path, payload)

    def fail(self, error: BaseException) -> dict[str, Any]:
        payload = json.loads(self.receipt_path.read_text(encoding="utf-8"))
        acceptance = payload.get("queue_acceptance") or {}
        prompt_id = acceptance.get("prompt_id") or payload.get("prompt_id") or getattr(error, "prompt_id", None)
        queue_status = acceptance.get("status", "not_attempted")
        if prompt_id:
            queue_status = "accepted"
        payload.update(run_id=self.run_id, receipt_path=str(self.receipt_path))
        # Accepted, rejected, and uncertain queue outcomes belong to the runtime
        # journal. Never turn a delivery failure into permission to resample.
        if queue_status != "not_attempted":
            payload["queue_status"] = queue_status
            atomic_write_json(self.receipt_path, payload)
            return payload
        terminal = payload.get("terminal") or {}
        phase = terminal.get("phase") or self.phase
        if phase == "prepared":
            phase = self.phase
        diagnostics = list(getattr(error, "diagnostics", None) or self.diagnostics)
        if not diagnostics:
            diagnostics = [{"code": f"{phase}_failed", "message": str(error)}]
        payload.update(
            status="failed", phase=phase, queue_status="not_attempted", prompt_id=None,
            error={"type": type(error).__name__, "message": str(error)},
            diagnostics=diagnostics,
            finished_at=datetime.now(timezone.utc).isoformat(),
        )
        payload["queue_acceptance"] = {"status": "not_attempted", "prompt_id": None}
        payload["terminal"] = {
            **terminal, "phase": phase, "reason_type": type(error).__name__,
            "reason": str(error), "acceptance_known": False,
        }
        if isinstance(payload.get("runtime_evidence"), dict):
            payload["runtime_evidence"]["terminal"] = dict(payload["terminal"])
        atomic_write_json(self.receipt_path, payload)
        return payload
