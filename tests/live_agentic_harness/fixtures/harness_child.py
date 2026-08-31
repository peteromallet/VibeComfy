"""Fake scenario child for the runner's timeout regression tests (R2-A).

The outer runner normally spawns ``python -m tests.live_agentic_harness.runner
--single ... --single-out ...``. These tests substitute THIS script via a
command-rewriting wrapper around the real ``_run_scenario_subprocess``, so the
real Popen/process-group/kill logic is exercised against a controllable child.

Flags mirror the real child's contract:
- ``--write-summary``: write a valid summary JSON to ``--single-out`` (atomic,
  like the real child) and print ``{"ok": true}`` to stdout.
- ``--hold-stdio``: spawn a grandchild that INHERITS our stdout/stderr fds and
  keeps them open (sleeping) while we exit immediately. With the old captured
  pipes this held the runner's ``communicate()`` open forever; with temp files
  it is harmless and the runner must NOT time out.
- ``--hang-after-summary``: sleep forever (never exit) — the runner must time
  out, kill our process group, and reap us.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path


def _summary(scenario_id: str) -> dict:
    return {
        "scenario_id": scenario_id,
        "status": "success",
        "ok": True,
        "output_dir": f"out/agentic/{scenario_id}",
        "flow_metadata": {
            "status": "success",
            "phases": ["classify", "research", "implement", "reply"],
            "phase_status": {
                "classify": "ok",
                "research": "ok",
                "implement": "ok",
                "reply": "ok",
            },
        },
        "guard": {
            "live_agentic_success": True,
            "score_class": "pass",
            "assessment": {"passed": True, "verdict": "pass", "issues": []},
        },
        "deepseek_usage": {},
        "deepseek_est_cost_usd": 0.0,
        "deepseek_cost_basis": "not_available",
        "model_attempts": [],
    }


def _write_json_atomic(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload), encoding="utf-8")
    tmp.replace(path)


def _write_probe(path: Path) -> None:
    _write_json_atomic(
        path,
        {
            "pid": os.getpid(),
            "ppid": os.getppid(),
            "pgid": os.getpgid(0) if hasattr(os, "getpgid") else None,
            "cwd": os.getcwd(),
            "module_name": __name__,
            "argv": list(sys.argv),
            "vibecomfy_modules": sorted(
                name
                for name in sys.modules
                if name == "vibecomfy" or name.startswith("vibecomfy.")
            ),
            "env": {
                key: os.environ.get(key)
                for key in (
                    "VIBECOMFY_TRANSPORT",
                    "VIBECOMFY_OPENROUTER_BASE_URL",
                    "VIBECOMFY_FORCE_MODEL",
                    "VIBECOMFY_HEADLESS",
                    "OPENROUTER_API_KEY",
                    "DEEPSEEK_API_KEY",
                )
            },
        },
    )


def _spawn_stdio_holder(pid_file: Path | None, seconds: float) -> int:
    holder = subprocess.Popen(
        [sys.executable, "-c", f"import time; time.sleep({seconds!r})"],
        stdin=subprocess.DEVNULL,
    )
    if pid_file is not None:
        pid_file.parent.mkdir(parents=True, exist_ok=True)
        with pid_file.open("a", encoding="utf-8") as fh:
            fh.write(f"{holder.pid}\n")
            fh.flush()
    return holder.pid


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--single-out", required=True)
    parser.add_argument("--scenario-id", default="fixture")
    parser.add_argument("--probe", default=None)
    parser.add_argument("--pid-file", default=None)
    parser.add_argument("--hold-seconds", type=float, default=60.0)
    parser.add_argument("--exit-code", type=int, default=0)
    parser.add_argument("--write-summary", action="store_true")
    parser.add_argument("--hold-stdio", action="store_true")
    parser.add_argument("--hang-after-summary", action="store_true")
    args = parser.parse_args()

    if args.probe:
        _write_probe(Path(args.probe))

    if args.write_summary:
        out = Path(args.single_out)
        out.parent.mkdir(parents=True, exist_ok=True)
        tmp = out.with_suffix(out.suffix + ".tmp")
        tmp.write_text(json.dumps(_summary(args.scenario_id), default=str), encoding="utf-8")
        tmp.replace(out)
        print(json.dumps({"scenario_id": args.scenario_id, "ok": True}), flush=True)

    if args.hold_stdio:
        # Grandchild inherits our stdout/stderr fds (regular temp files under
        # the new runner; captured pipes under the old one) and holds them open
        # well past our exit. We exit immediately.
        _spawn_stdio_holder(Path(args.pid_file) if args.pid_file else None, args.hold_seconds)
        return args.exit_code

    if args.hang_after_summary:
        _spawn_stdio_holder(Path(args.pid_file) if args.pid_file else None, args.hold_seconds)
        time.sleep(3600)
    return args.exit_code


if __name__ == "__main__":
    raise SystemExit(main())
