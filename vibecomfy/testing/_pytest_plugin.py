"""Pytest plugin for VibeComfy user tests (T9).

Triggers on `test_workflow_*.py` files; auto-wraps functions that return a
`VibeWorkflow` with `assert_compiles_cleanly`. Plain `test_*` functions in
the same file continue to collect normally.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Iterator

import pytest


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption(
        "--vibecomfy-snapshot-update",
        action="store_true",
        default=False,
        help="Rewrite stale sibling <recipe>.snapshot.json files when running pytest.",
    )


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line(
        "markers",
        "vibecomfy_workflow: marker for tests that return a VibeWorkflow and should be auto-asserted.",
    )


class _WorkflowFunctionItem(pytest.Function):
    def runtest(self) -> None:
        from vibecomfy.testing.assertions import assert_compiles_cleanly
        from vibecomfy.workflow import VibeWorkflow

        result = self.obj()
        if isinstance(result, VibeWorkflow):
            assert_compiles_cleanly(result)
        else:
            # Plain function — already executed; nothing more to do.
            pass


def pytest_collect_file(parent: pytest.Collector, file_path: Path) -> pytest.Collector | None:
    """Augment pytest's collection for `test_workflow_*.py` files."""
    if file_path.suffix != ".py":
        return None
    if not file_path.name.startswith("test_workflow_"):
        return None
    # Let the default collector handle it; we attach behavior via pytest_pycollect_makeitem.
    return None


def pytest_pycollect_makeitem(
    collector: pytest.Collector, name: str, obj: Any
) -> pytest.Item | list[pytest.Item] | None:
    """Wrap top-level functions in `test_workflow_*.py` files."""
    path = collector.path if hasattr(collector, "path") else None
    if path is None or not getattr(path, "name", "").startswith("test_workflow_"):
        return None
    if not callable(obj) or not name.startswith("test_"):
        return None
    # Only wrap zero-argument top-level functions to avoid breaking parametrize/etc.
    try:
        import inspect

        sig = inspect.signature(obj)
        if sig.parameters:
            return None
    except (TypeError, ValueError):
        return None
    return _WorkflowFunctionItem.from_parent(collector, name=name, callobj=obj)


# Re-export the public fixtures so users get them from the plugin.
from vibecomfy.testing.fixtures import (  # noqa: E402
    dry_runtime,
    vibecomfy_handle_factory,
    vibecomfy_workflow_factory,
)

__all__ = [
    "dry_runtime",
    "vibecomfy_handle_factory",
    "vibecomfy_workflow_factory",
]
