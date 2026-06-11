from __future__ import annotations

import argparse
import json
import sys

from vibecomfy.commands import build_security_parent, register_commands
from vibecomfy.security.gate import (
    CapabilityFenceError,
    GateContext,
    set_gate_context,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="vibecomfy")
    subparsers = parser.add_subparsers(dest="cmd", required=True)
    register_commands(subparsers, security_parent=build_security_parent())
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    ctx = GateContext(
        non_interactive=bool(getattr(args, "non_interactive", False)),
        assume_yes=bool(getattr(args, "assume_yes", False)),
        audit=[],
    )
    set_gate_context(ctx)
    try:
        return args.func(args)
    except CapabilityFenceError as exc:
        print(
            json.dumps({"error": "capability_fence", **exc.detail}, sort_keys=True),
            file=sys.stderr,
        )
        raise SystemExit(42)


if __name__ == "__main__":
    raise SystemExit(main())
