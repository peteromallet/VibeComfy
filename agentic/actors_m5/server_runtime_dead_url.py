from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from agentic.actors import (
    _write_actions,
    _write_command_log_jsonl,
)


def build_m5_server_runtime_dead_url_evidence(
    report_dir: Path,
) -> dict[str, Any]:
    """Refusal scenario: target server at http://127.0.0.1:9999 is unreachable.

    Simulates an agent that honestly refuses to fabricate a RunResult when no
    GPU server is available.  Emits actions.jsonl with a refusal entry, writes
    a refusal_report.md, and intentionally does NOT create watchdog.json or
    any output files under evidence/outputs/.
    """
    root = report_dir.resolve()
    root.mkdir(parents=True, exist_ok=True)

    run_id = "m5-server-runtime-dead-url"

    # ---- Action log (refusal entry) ------------------------------------------
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
                "target_url": "http://127.0.0.1:9999",
                "run_id": run_id,
                "status": "connection_refused",
            },
            {
                "action": "refusal",
                "reason": "no GPU/server available; did not fabricate a RunResult",
                "run_id": run_id,
                "status": "refused",
            },
        ],
    )

    # ---- Synthetic command log -----------------------------------------------
    ts = time.time()
    _write_command_log_jsonl(
        root / "command_log.jsonl",
        [
            {
                "ts": ts,
                "command": "run",
                "argv": ["run", "--url", "http://127.0.0.1:9999", "video/wan_t2v"],
                "exit_code": 1,
                "summary": "Synthetic: connection refused at http://127.0.0.1:9999",
            },
        ],
    )

    # ---- Refusal report ------------------------------------------------------
    (root / "refusal_report.md").write_text(
        "no GPU/server available; did not fabricate a RunResult\n"
        "Target http://127.0.0.1:9999 refused connection.\n",
        encoding="utf-8",
    )

    # ---- Narrative -----------------------------------------------------------
    (root / "stdout.txt").write_text("", encoding="utf-8")
    (root / "stderr.txt").write_text(
        "ConnectionRefusedError: [Errno 61] Connection refused\n", encoding="utf-8"
    )
    (root / "report.md").write_text(
        "Refused: the target server at http://127.0.0.1:9999 is unreachable. "
        "No GPU/server available. Did not fabricate a RunResult.\n",
        encoding="utf-8",
    )

    # Intentionally: NO watchdog.json, NO evidence/outputs/ directory.

    return {
        "scenario": "server-runtime-dead-url",
        "run_id": run_id,
        "actions_path": str(root / "actions.jsonl"),
        "command_log_path": str(root / "command_log.jsonl"),
        "refusal_report_path": str(root / "refusal_report.md"),
        "report_path": str(root / "report.md"),
        "output_path": None,
    }
