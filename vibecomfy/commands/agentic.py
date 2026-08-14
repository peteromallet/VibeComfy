from __future__ import annotations

import argparse


def _cmd_agentic(args: argparse.Namespace) -> int:
    print(
        "headless agent: `python -m vibecomfy.agent --help`; "
        "typed clarification is returned as `needs_input`"
    )
    return 0


def register(subparsers) -> None:
    parser = subparsers.add_parser(
        "agentic",
        help="Show the headless agent entrypoint and typed ambiguity contract.",
    )
    parser.set_defaults(func=_cmd_agentic)
