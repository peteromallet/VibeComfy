"""Focused contracts for typed-wrapper class discovery."""

from __future__ import annotations

import subprocess
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from vibecomfy.blocks import _wrapper_discovery as discovery
from vibecomfy.blocks._utils import add_block_node


def _literal_block(workflow: Any) -> None:
    add_block_node(workflow, "vibecomfy.blocks.test", "FakeClass")


def _dynamic_block(workflow: Any, class_type: str) -> None:
    add_block_node(workflow, "vibecomfy.blocks.subgraph.opaque", class_type)


def test_extractor_matches_literal_class_types_only() -> None:
    classes = discovery.extract_typed_wrapper_class_types(
        {"literal": _literal_block, "dynamic": _dynamic_block}
    )

    assert classes == frozenset({"FakeClass"})
    assert "vibecomfy" not in classes


@pytest.mark.parametrize("error", [OSError("no source"), TypeError("not a function")])
def test_extractor_skips_known_source_errors_per_function(
    monkeypatch: pytest.MonkeyPatch, error: Exception
) -> None:
    real_getsource = discovery.inspect.getsource

    def getsource(value: Callable[..., Any]) -> str:
        if value is _dynamic_block:
            raise error
        return real_getsource(value)

    monkeypatch.setattr(discovery.inspect, "getsource", getsource)

    classes = discovery.extract_typed_wrapper_class_types(
        {"broken": _dynamic_block, "literal": _literal_block}
    )

    assert classes == frozenset({"FakeClass"})


def test_extractor_propagates_unexpected_source_errors(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def getsource(_value: Callable[..., Any]) -> str:
        raise ValueError("unexpected source failure")

    monkeypatch.setattr(discovery.inspect, "getsource", getsource)

    with pytest.raises(ValueError, match="unexpected source failure"):
        discovery.extract_typed_wrapper_class_types({"literal": _literal_block})


def test_importer_continues_in_declared_order_after_module_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    attempted: list[str] = []
    failed_module = discovery._BLOCK_MODULES[3]

    def import_module(name: str) -> object:
        attempted.append(name)
        if name == failed_module:
            raise RuntimeError("optional module unavailable")
        return object()

    monkeypatch.setattr(discovery.importlib, "import_module", import_module)

    discovery.import_block_submodules()

    assert attempted == list(discovery._BLOCK_MODULES)


def test_importing_callers_does_not_import_block_submodules() -> None:
    script = """
import sys
import vibecomfy.porting.lint
import vibecomfy.analysis.node_coverage
modules = {
    'vibecomfy.blocks.loaders',
    'vibecomfy.blocks.sampling',
    'vibecomfy.blocks.encoding',
    'vibecomfy.blocks.decode',
    'vibecomfy.blocks.latent',
    'vibecomfy.blocks.save',
    'vibecomfy.blocks.video',
    'vibecomfy.blocks.subgraph',
}
assert not (modules & set(sys.modules)), modules & set(sys.modules)
"""
    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=Path(__file__).resolve().parents[1],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr


def test_lint_builder_fail_soft_and_sticky_cache(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import vibecomfy.blocks as blocks
    from vibecomfy.porting import lint

    calls = 0

    def registered_blocks() -> dict[str, Any]:
        nonlocal calls
        calls += 1
        raise RuntimeError("registry unavailable")

    monkeypatch.setattr(blocks, "registered_blocks", registered_blocks)
    monkeypatch.setattr(lint, "_TYPED_WRAPPER_CLASSES", None)

    assert lint._class_has_typed_wrapper("SaveImage") is False
    assert lint._class_has_typed_wrapper("SaveImage") is False
    assert calls == 1

    monkeypatch.setattr(
        blocks, "registered_blocks", lambda: {"literal": _literal_block}
    )
    assert lint._class_has_typed_wrapper("FakeClass") is False


def test_lint_builder_fail_softs_unexpected_extractor_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from vibecomfy.porting import lint

    def fail(_blocks: Any) -> frozenset[str]:
        raise ValueError("unexpected extractor failure")

    monkeypatch.setattr(discovery, "extract_typed_wrapper_class_types", fail)

    assert lint._build_typed_wrapper_set() == frozenset()


def test_coverage_registry_failure_is_empty_but_retries(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from vibecomfy.analysis import node_coverage

    def fail() -> dict[str, Any]:
        raise RuntimeError("registry unavailable")

    monkeypatch.setattr(node_coverage, "registered_blocks", fail)
    assert node_coverage._build_typed_wrapper_set() == frozenset()

    monkeypatch.setattr(
        node_coverage, "registered_blocks", lambda: {"literal": _literal_block}
    )
    assert node_coverage._build_typed_wrapper_set() == frozenset({"FakeClass"})


def test_coverage_propagates_unexpected_extractor_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from vibecomfy.analysis import node_coverage

    def fail(_blocks: Any) -> frozenset[str]:
        raise ValueError("unexpected extractor failure")

    monkeypatch.setattr(discovery, "extract_typed_wrapper_class_types", fail)

    with pytest.raises(ValueError, match="unexpected extractor failure"):
        node_coverage._build_typed_wrapper_set()


def test_lint_and_coverage_have_known_class_parity() -> None:
    from vibecomfy.analysis import node_coverage
    from vibecomfy.porting import lint

    lint_classes = lint._build_typed_wrapper_set()
    coverage_classes = node_coverage._build_typed_wrapper_set()

    assert lint_classes == coverage_classes
    assert "SaveImage" in lint_classes
