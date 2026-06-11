"""Pytest fixtures and plain factory helpers for VibeComfy user tests (T4).

Builders use only the public `VibeWorkflow` surface — `add_node`, `connect`,
`register_input`, `finalize_metadata` — never private internals.
"""
from __future__ import annotations

from typing import Any, Callable

import pytest

from vibecomfy.handles import Handle
from vibecomfy.workflow import VibeWorkflow, WorkflowSource


def make_workflow_factory() -> Callable[..., VibeWorkflow]:
    """Return a callable that builds a minimal `VibeWorkflow` for tests.

    Usage:
        wf = make_workflow_factory()(id="my-test")
    """

    def _factory(*, id: str = "test-workflow", **metadata: Any) -> VibeWorkflow:
        wf = VibeWorkflow(id=id, source=WorkflowSource(id=id))
        for key, value in metadata.items():
            wf.metadata[key] = value
        return wf

    return _factory


def make_handle_factory() -> Callable[..., Handle]:
    """Return a callable that builds a `Handle` against an existing workflow node."""

    def _factory(wf: VibeWorkflow, node_id: str, output_slot: int = 0) -> Handle:
        if node_id not in wf.nodes:
            raise KeyError(f"node {node_id!r} is not in workflow {wf.id!r}")
        return Handle(node_id=node_id, output_slot=output_slot)

    return _factory


@pytest.fixture
def vibecomfy_workflow_factory() -> Callable[..., VibeWorkflow]:
    """Pytest fixture wrapping `make_workflow_factory`."""
    return make_workflow_factory()


@pytest.fixture
def vibecomfy_handle_factory() -> Callable[..., Handle]:
    """Pytest fixture wrapping `make_handle_factory`."""
    return make_handle_factory()


_dry_runtime_cache: dict[str, Any] = {}


@pytest.fixture(scope="session")
def dry_runtime() -> Any:
    """Session-scoped dry-run helper. Caches a single stub schema provider."""
    from vibecomfy.testing._stub_schema import _StubSchemaProvider
    from vibecomfy.testing.dry_run import dry_run

    if "stub" not in _dry_runtime_cache:
        _dry_runtime_cache["stub"] = _StubSchemaProvider()

    class _DryRuntime:
        def __init__(self, schema_provider: Any) -> None:
            self.schema_provider = schema_provider

        def __call__(self, wf: VibeWorkflow, **kwargs: Any) -> Any:
            kwargs.setdefault("schema_provider", self.schema_provider)
            return dry_run(wf, **kwargs)

    return _DryRuntime(_dry_runtime_cache["stub"])


__all__ = [
    "make_workflow_factory",
    "make_handle_factory",
    "vibecomfy_workflow_factory",
    "vibecomfy_handle_factory",
    "dry_runtime",
]
