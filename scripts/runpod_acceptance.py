"""Fail-closed placeholder for the retired live RunPod acceptance driver."""

from __future__ import annotations

import argparse
import sys


_FAILURE_TEXT = (
    "scripts/runpod_acceptance.py cannot execute raw API, UI, scratchpad, or bare-workflow payloads "
    "and does not provision a RunPod machine.\n"
    "Next: vibecomfy port check <source> --json\n"
    "Then: vibecomfy port convert <source> --out out/scratchpads/<name>.py\n"
    "Then: load the canonical bundle, compile an ApprovedProjectionRecord, and call "
    "vibecomfy.runtime.runpod_adapter.prepare_runpod_transport / queue_runpod_stub offline."
)


def _shell_quote(value: str) -> str:
    return "'" + value.replace("'", "'\\''") + "'"


def _remote_script(*, model_template: str | None = None, model_phase: str | None = None) -> str:
    """Return a remote script that refuses execution before any side effect."""
    del model_template, model_phase
    return f"#!/bin/sh\nset -eu\nprintf '%s\\n' {_shell_quote(_FAILURE_TEXT)} >&2\nexit 1\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="The live RunPod acceptance route is disabled; use the offline approved-record transport."
    )
    parser.add_argument("--model-template")
    parser.add_argument(
        "--model-phase",
        choices=["core", "gguf", "ltx", "wan_wrapper", "qwen_image"],
    )
    parser.add_argument("--timeout", type=int, default=3600)
    parser.add_argument("--poll-interval", type=int, default=30)
    args = parser.parse_args(argv)
    if args.model_phase and not args.model_template:
        parser.error("--model-phase requires --model-template")
    print(_FAILURE_TEXT, file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
