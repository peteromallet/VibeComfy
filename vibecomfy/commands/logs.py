from __future__ import annotations

import argparse
import sys
from pathlib import Path


def _cmd_logs(args: argparse.Namespace) -> int:
    run_dir = Path("out/runs") / args.run_id
    if not run_dir.exists():
        print(f"run not found: {args.run_id}", file=sys.stderr)
        return 1
    for name in ("completion.json", "metadata.json", "comfy.log"):
        path = run_dir / name
        if path.exists():
            print(f"== {path} ==")
            print(path.read_text(encoding="utf-8", errors="replace")[-args.tail :])
    return 0


def register(subparsers) -> None:
    logs = subparsers.add_parser("logs")
    logs.add_argument("run_id")
    logs.add_argument("--tail", type=int, default=4000)
    logs.set_defaults(func=_cmd_logs)
