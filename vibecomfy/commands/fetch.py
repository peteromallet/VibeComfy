from __future__ import annotations

import argparse

from vibecomfy.commands._model_ensure import command_args as _reconcile_workflow_models


def _cmd_fetch(args: argparse.Namespace) -> int:
    # Compatibility alias. Keep one implementation so fetch cannot drift from
    # the workflow-scoped models ensure command.
    return _reconcile_workflow_models(args)


def register(subparsers) -> None:
    fetch = subparsers.add_parser("fetch")
    fetch.add_argument("workflow")
    fetch.add_argument("--force", action="store_true")
    fetch.add_argument("--dry-run", action="store_true")
    fetch.set_defaults(func=_cmd_fetch)


__all__ = ["register"]
