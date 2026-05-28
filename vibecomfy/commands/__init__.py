from __future__ import annotations

from dataclasses import dataclass
from importlib import import_module
from types import ModuleType


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
    CommandSpec("runpod", "vibecomfy.commands.runpod"),
    CommandSpec("watchdog", "vibecomfy.commands.watchdog"),
    CommandSpec("schemas", "vibecomfy.commands.schemas"),
    CommandSpec("check", "vibecomfy.commands.check"),
    CommandSpec("agentic", "vibecomfy.commands.agentic"),
    CommandSpec("copy-to-recipe", "vibecomfy.commands.copy_to_recipe"),
    CommandSpec("test", "vibecomfy.commands.test"),
)


def load_command(spec: CommandSpec) -> ModuleType:
    module = import_module(spec.module)
    if not callable(getattr(module, "register", None)):
        raise TypeError(f"{spec.module} must expose register(subparsers)")
    return module


def register_commands(subparsers, commands: tuple[CommandSpec, ...] = COMMANDS) -> None:
    for spec in commands:
        load_command(spec).register(subparsers)


def register(subparsers) -> None:
    register_commands(subparsers)
