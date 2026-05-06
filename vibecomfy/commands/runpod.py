from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path


def _runpod_lifecycle_root() -> Path:
    configured = getattr(sys, "_vibecomfy_runpod_lifecycle_root", None)
    if configured:
        return Path(configured)
    configured_env = os.getenv("VIBECOMFY_RUNPOD_LIFECYCLE_ROOT")
    if configured_env:
        return Path(configured_env)
    return Path(__file__).resolve().parents[3] / "runpod-lifecycle"


def _runpod_lifecycle_main(argv: list[str]) -> int:
    try:
        from dotenv import load_dotenv
        from runpod_lifecycle.cli import main as runpod_main
    except ImportError:
        root = _runpod_lifecycle_root()
        src = root / "src"
        if not src.exists():
            print(
                "runpod-lifecycle is not installed. Install VibeComfy with `pip install -e '.[runpod-local]'` "
                "or set VIBECOMFY_RUNPOD_LIFECYCLE_ROOT for a local checkout.",
                file=sys.stderr,
            )
            return 1
        sys.path.insert(0, str(src))
        try:
            from dotenv import load_dotenv
            from runpod_lifecycle.cli import main as runpod_main
        except Exception as exc:
            print(f"could not import runpod-lifecycle: {type(exc).__name__}: {exc}", file=sys.stderr)
            return 1
    root = _runpod_lifecycle_root()
    load_dotenv(root / ".env")
    return runpod_main(argv)


def _cmd_runpod_list(args: argparse.Namespace) -> int:
    argv = ["list"]
    if args.name_prefix:
        argv.extend(["--name-prefix", args.name_prefix])
    if args.json:
        argv.append("--json")
    return _runpod_lifecycle_main(argv)


def _cmd_runpod_status(args: argparse.Namespace) -> int:
    return _runpod_lifecycle_main(["status", args.pod_id])


def _cmd_runpod_terminate(args: argparse.Namespace) -> int:
    argv = ["terminate", args.pod_id]
    if args.yes:
        argv.append("--yes")
    return _runpod_lifecycle_main(argv)


def _cmd_runpod_gpu_types(args: argparse.Namespace) -> int:
    argv = ["gpu-types"]
    if args.json:
        argv.append("--json")
    return _runpod_lifecycle_main(argv)


def _cmd_runpod_corpus_matrix(args: argparse.Namespace) -> int:
    script = Path("scripts/runpod_corpus_matrix.py")
    if not script.exists():
        print("scripts/runpod_corpus_matrix.py not found; run from the VibeComfy repo root", file=sys.stderr)
        return 1
    argv = [sys.executable, str(script)]
    if args.scope:
        argv.extend(["--scope", args.scope])
    return subprocess.call(argv)


def register(subparsers) -> None:
    runpod = subparsers.add_parser("runpod")
    runpod_sub = runpod.add_subparsers(dest="subcmd", required=True)

    runpod_list = runpod_sub.add_parser("list")
    runpod_list.add_argument("--name-prefix")
    runpod_list.add_argument("--json", action="store_true")
    runpod_list.set_defaults(func=_cmd_runpod_list)

    runpod_status = runpod_sub.add_parser("status")
    runpod_status.add_argument("pod_id")
    runpod_status.set_defaults(func=_cmd_runpod_status)

    runpod_terminate = runpod_sub.add_parser("terminate")
    runpod_terminate.add_argument("pod_id")
    runpod_terminate.add_argument("--yes", "-y", action="store_true")
    runpod_terminate.set_defaults(func=_cmd_runpod_terminate)

    runpod_gpu_types = runpod_sub.add_parser("gpu-types")
    runpod_gpu_types.add_argument("--json", action="store_true")
    runpod_gpu_types.set_defaults(func=_cmd_runpod_gpu_types)

    runpod_corpus = runpod_sub.add_parser("corpus-matrix")
    runpod_corpus.add_argument("--scope")
    runpod_corpus.set_defaults(func=_cmd_runpod_corpus_matrix)
