from __future__ import annotations

import importlib

__all__ = (
    "audit",
    "contracts",
    "diagnostics",
    "edit",
    "execution_plan",
    "executor_response",
    "fixture_provider",
    "gates",
    "hivemind_feedback",
    "provider",
    "routes",
    "runtime",
    "runtime_code",
    "session",
    "worker",
)


def __getattr__(name: str):
    """Lazy-load remaining agent submodules on first attribute access."""
    if name in __all__:
        module = importlib.import_module(f"vibecomfy.comfy_nodes.agent.{name}")
        globals()[name] = module
        return module
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
