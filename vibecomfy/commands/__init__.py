from __future__ import annotations

import argparse
from dataclasses import dataclass
from importlib import import_module
from types import ModuleType
from typing import Any


@dataclass(frozen=True)
class CommandSpec:
    name: str
    module: str


COMMANDS: tuple[CommandSpec, ...] = (
    CommandSpec("sources", "vibecomfy.commands.sources"),
    CommandSpec("workflows", "vibecomfy.commands.workflows"),
    CommandSpec("nodes", "vibecomfy.commands.nodes"),
    CommandSpec("analyze", "vibecomfy.commands.analyze"),
    CommandSpec("search", "vibecomfy.commands.search"),
    CommandSpec("inspect", "vibecomfy.commands.inspect"),
    CommandSpec("reorganise", "vibecomfy.commands.reorganise"),
    CommandSpec("port", "vibecomfy.commands.port"),
    CommandSpec("contract", "vibecomfy.commands.contract"),
    CommandSpec("validate", "vibecomfy.commands.validate"),
    CommandSpec("doctor", "vibecomfy.commands.doctor"),
    CommandSpec("fetch", "vibecomfy.commands.fetch"),
    CommandSpec("models", "vibecomfy.commands.models"),
    CommandSpec("run", "vibecomfy.commands.run"),
    CommandSpec("runtime", "vibecomfy.commands.runtime"),
    CommandSpec("session", "vibecomfy.commands.session"),
    CommandSpec("logs", "vibecomfy.commands.logs"),
    CommandSpec("debug", "vibecomfy.commands.debug"),
    CommandSpec("runpod", "vibecomfy.commands.runpod"),
    CommandSpec("watchdog", "vibecomfy.commands.watchdog"),
    CommandSpec("schemas", "vibecomfy.commands.schemas"),
    CommandSpec("check", "vibecomfy.commands.check"),
    CommandSpec("agentic", "vibecomfy.commands.agentic"),
    CommandSpec("copy-to-recipe", "vibecomfy.commands.copy_to_recipe"),
    CommandSpec("test", "vibecomfy.commands.test"),
    CommandSpec("config", "vibecomfy.commands.config"),
)


def build_security_parent() -> argparse.ArgumentParser:
    """Argparse parent parser carrying the capability-fence flags.

    Used via ``parents=[parent]`` on every top-level subparser so ``--yes`` /
    ``-y`` / ``--non-interactive`` work AFTER the subcommand name (the form
    users actually type, e.g. ``vibecomfy doctor --yes wf.py``).
    """
    parent = argparse.ArgumentParser(add_help=False)
    parent.add_argument(
        "--yes",
        "-y",
        dest="assume_yes",
        action="store_true",
        help="Auto-confirm capability-fence prompts (audited as bypass).",
    )
    parent.add_argument(
        "--non-interactive",
        dest="non_interactive",
        action="store_true",
        help="Refuse any capability-fence prompt; raise instead of asking.",
    )
    return parent


class _SubparsersWithParents:
    """Wraps an argparse ``_SubParsersAction`` so every ``add_parser`` call
    automatically inherits the security parent(s). Keeps each command module
    unmodified — they still call ``subparsers.add_parser(name, ...)``.
    """

    def __init__(self, inner: Any, parents: list[argparse.ArgumentParser]):
        self._inner = inner
        self._parents = parents

    def add_parser(self, name: str, **kwargs: Any) -> argparse.ArgumentParser:
        existing = list(kwargs.pop("parents", []))
        kwargs["parents"] = existing + self._parents
        return self._inner.add_parser(name, **kwargs)

    def __getattr__(self, attr: str) -> Any:
        return getattr(self._inner, attr)


def load_command(spec: CommandSpec) -> ModuleType:
    module = import_module(spec.module)
    if not callable(getattr(module, "register", None)):
        raise TypeError(f"{spec.module} must expose register(subparsers)")
    return module


def register_commands(
    subparsers,
    commands: tuple[CommandSpec, ...] = COMMANDS,
    *,
    security_parent: argparse.ArgumentParser | None = None,
) -> None:
    if security_parent is None:
        security_parent = build_security_parent()
    proxy = _SubparsersWithParents(subparsers, [security_parent])
    for spec in commands:
        load_command(spec).register(proxy)


def register(subparsers) -> None:
    register_commands(subparsers)
