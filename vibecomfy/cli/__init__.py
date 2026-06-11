from __future__ import annotations

import argparse
import json
import os
import sys

from vibecomfy.commands import build_security_parent, register_commands
from vibecomfy.security.gate import (
    CapabilityFenceError,
    GateContext,
    set_gate_context,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="vibecomfy")
    parser.add_argument(
        "--quiet",
        "-q",
        action="store_true",
        help="Suppress informational output such as configuration nudges.",
    )
    subparsers = parser.add_subparsers(dest="cmd", required=True)
    register_commands(subparsers, security_parent=build_security_parent())
    return parser


def _maybe_print_nudge(args: argparse.Namespace) -> None:
    try:
        if getattr(args, "cmd", None) == "config":
            return
        if os.environ.get("VIBECOMFY_NO_NUDGE"):
            return
        if getattr(args, "quiet", False):
            return
        if getattr(args, "json", False):
            return

        from vibecomfy.local_library import Slot, SlotState, resolve

        cn = resolve(Slot.custom_nodes)
        mo = resolve(Slot.models)

        if cn.state is not SlotState.UNSET and mo.state is not SlotState.UNSET:
            return

        lines: list[str] = ["[vibecomfy] Local-library config is not fully set up:"]
        if cn.state is SlotState.UNSET:
            lines.append(
                "  custom_nodes: run `vibecomfy config set-library --custom-nodes <PATH>`"
            )
        if mo.state is SlotState.UNSET:
            lines.append(
                "  models: run `vibecomfy config set-library --models <PATH>`"
            )
        print("\n".join(lines), file=sys.stderr)
    except Exception:
        return


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    ctx = GateContext(
        non_interactive=bool(getattr(args, "non_interactive", False)),
        assume_yes=bool(getattr(args, "assume_yes", False)),
        audit=[],
    )
    set_gate_context(ctx)
    _maybe_print_nudge(args)
    try:
        return args.func(args)
    except CapabilityFenceError as exc:
        print(
            json.dumps({"error": "capability_fence", **exc.detail}, sort_keys=True),
            file=sys.stderr,
        )
        raise SystemExit(42)
