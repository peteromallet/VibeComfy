from __future__ import annotations

import argparse
from dataclasses import dataclass
from importlib import import_module
from types import ModuleType


@dataclass(frozen=True)
class CommandSpec:
    name: str
    module: str


COMMANDS: tuple[CommandSpec, ...] = (
    CommandSpec("sources", "vibecomfy.commands.sources"),
    CommandSpec("import", "vibecomfy.commands.import_workflow"),
    CommandSpec("edit", "vibecomfy.commands.edit"),
    CommandSpec("recover", "vibecomfy.commands.recover_workflow"),
    CommandSpec("workflows", "vibecomfy.commands.workflows"),
    CommandSpec("templates", "vibecomfy.commands.templates"),
    CommandSpec("nodes", "vibecomfy.commands.nodes"),
    CommandSpec("node", "vibecomfy.commands.node"),
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
    CommandSpec("prepare", "vibecomfy.commands.prepare"),
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


def add_security_flags(parser: argparse.ArgumentParser) -> None:
    """Add capability-fence flags to a parser without masking earlier flags.

    Suppressed defaults matter here: argparse parses each subparser into the
    same namespace, so a child parser's implicit ``False`` would otherwise
    overwrite a ``--yes`` supplied before the child command.
    """
    present = {option for action in parser._actions for option in action.option_strings}
    for dest, options, help_text in (
        (
            "assume_yes",
            ("--yes", "-y"),
            "Auto-confirm capability-fence prompts (audited as bypass).",
        ),
        (
            "non_interactive",
            ("--non-interactive",),
            "Refuse any capability-fence prompt; raise instead of asking.",
        ),
    ):
        existing = [
            a for a in parser._actions
            if a.dest == dest or any(option in a.option_strings for option in options)
        ]
        if existing:
            # Some leaf commands already define --yes for their own prompt.
            # Reuse that action; only suppress defaults for the shared global
            # destination. Local command-specific destinations keep semantics.
            for action in existing:
                if action.dest == dest:
                    action.default = argparse.SUPPRESS
            continue
        if any(option in present for option in options):
            continue
        parser.add_argument(
            *options,
            dest=dest,
            action="store_true",
            default=argparse.SUPPRESS,
            help=help_text,
        )


def build_security_parent() -> argparse.ArgumentParser:
    """Return a reusable argparse parent carrying the global security flags."""
    parent = argparse.ArgumentParser(add_help=False)
    add_security_flags(parent)
    return parent


def add_security_flags_recursively(parser: argparse.ArgumentParser) -> None:
    """Install the global security flags at every command depth."""
    seen: set[int] = set()

    def visit(current: argparse.ArgumentParser) -> None:
        if id(current) in seen:
            return
        seen.add(id(current))
        add_security_flags(current)
        for action in current._actions:
            if isinstance(action, argparse._SubParsersAction):
                for child in action.choices.values():
                    visit(child)

    visit(parser)


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
    # Keep the former keyword usable for callers while registering flags
    # recursively so nested commands receive them too.
    del security_parent
    for spec in commands:
        load_command(spec).register(subparsers)
    for parser in subparsers.choices.values():
        add_security_flags_recursively(parser)


def register(subparsers) -> None:
    register_commands(subparsers)
