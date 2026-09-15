"""High-signal contract coverage for generated node wrappers."""

from __future__ import annotations

import importlib
from pathlib import Path
from typing import Any


def _generated_node_modules() -> list[str]:
    nodes_root = Path(__file__).parents[1] / "vibecomfy" / "nodes"
    return [
        f"vibecomfy.nodes.{path.stem}"
        for path in sorted(nodes_root.glob("*.py"))
        if path.read_text(encoding="utf-8").splitlines()[:1]
        == ["# vibecomfy:generated"]
    ]


def test_every_generated_wrapper_dispatches_through_public_node_abi(
    monkeypatch,
) -> None:  # noqa: ANN001
    """Every generated entry point stays a thin, callable shared-ABI wrapper."""
    sentinel_workflow = object()
    dispatched: list[tuple[Any, str, str | None, dict[str, Any]]] = []

    def fake_node(
        workflow: Any,
        class_type: str,
        node_id: str | None = None,
        **kwargs: Any,
    ) -> tuple[Any, str, str | None, dict[str, Any]]:
        dispatched.append((workflow, class_type, node_id, kwargs))
        return dispatched[-1]

    wrapper_count = 0
    for module_name in _generated_node_modules():
        module = importlib.import_module(module_name)
        monkeypatch.setattr(module, "node", fake_node)
        for wrapper_name in module.__all__:
            wrapper = getattr(module, wrapper_name)
            assert callable(wrapper), f"{module_name}.{wrapper_name} is not callable"
            result = wrapper(sentinel_workflow, _id="wrapper-contract", pass_raw=True)
            assert result[0] is sentinel_workflow
            assert result[1], f"{module_name}.{wrapper_name} emitted no class type"
            assert result[2] == "wrapper-contract"
            assert result[3]["pass_raw"] is True
            wrapper_count += 1

    assert wrapper_count == len(dispatched) == 1503
