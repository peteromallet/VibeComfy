"""Tests for the T-035 batch-REPL dependency object (A/edit_batch_repl.py).

Pins the S4 design contract:
- invocation-time resolution from a façade globals mapping (no snapshot),
- KeyError-style missing-name failure listing the missing names,
- stdlib-only imports and no module-level singleton (static + runtime).
"""

from __future__ import annotations

import ast
import importlib.util
import subprocess
import sys
from dataclasses import fields
from pathlib import Path

import pytest

from vibecomfy.comfy_nodes.agent import edit_batch_repl as ebr

REPO_ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = Path(ebr.__file__)
MODULE_SOURCE = MODULE_PATH.read_text(encoding="utf-8")

# S4 ground truth: the batch loop references 80 external names; 5 are
# stdlib-importable (Any/Mapping/dataclasses/json/time) and the remaining
# 75 real deps (58 private + 17 public) are resolved from the façade globals.
S4_TOTAL = 75
S4_PRIVATE = 58
S4_PUBLIC = 17

# S3 seam names that the batch loop pulls in from the façade through the deps
# object (subset of the 75 fields; the rest stay local to the loop/facade).
SEAM_NAMES_IN_DEPS = {
    "run_agent_turn_batch",
    "_format_batch_report",
    "_format_batch_report_json",
}


def _expected_names() -> set[str]:
    return {field.name for field in fields(ebr.EditBatchReplDeps)}


def test_field_set_matches_s4_counts_and_required_set() -> None:
    expected = _expected_names()
    assert ebr.REQUIRED_DEPENDENCY_NAMES == expected
    assert len(expected) == S4_TOTAL
    private = {name for name in expected if name.startswith("_")}
    assert len(private) == S4_PRIVATE
    assert len(expected - private) == S4_PUBLIC
    assert SEAM_NAMES_IN_DEPS <= expected


def test_build_resolves_every_field_from_synthetic_globals() -> None:
    expected = _expected_names()
    sentinels = {name: object() for name in expected}

    deps = ebr.build_edit_batch_repl_deps(sentinels)

    assert isinstance(deps, ebr.EditBatchReplDeps)
    for name in expected:
        assert getattr(deps, name) is sentinels[name], name


def test_each_invocation_rebuilds_fresh_deps() -> None:
    sentinels = {name: object() for name in ebr.REQUIRED_DEPENDENCY_NAMES}
    first = ebr.build_edit_batch_repl_deps(sentinels)
    second = ebr.build_edit_batch_repl_deps(sentinels)
    assert first is not second  # no singleton snapshot


def test_build_missing_names_raises_keyerror_style_error() -> None:
    with pytest.raises(ebr.MissingEditBatchReplDepsError) as excinfo:
        ebr.build_edit_batch_repl_deps({})

    error = excinfo.value
    assert isinstance(error, KeyError)  # KeyError-style: T-036 catches this
    message = str(error)
    for name in ("LOGGER", "run_agent_turn_batch", "_format_batch_report"):
        assert name in message
    assert f"{S4_TOTAL}" in message


def test_build_reports_only_the_missing_names() -> None:
    dropped = {"LOGGER", "_format_batch_report"}
    provided = {name: object() for name in _expected_names() - dropped}

    with pytest.raises(ebr.MissingEditBatchReplDepsError) as excinfo:
        ebr.build_edit_batch_repl_deps(provided)

    message = str(excinfo.value)
    for name in dropped:
        assert name in message
    for name in ("AgentEditState", "run_agent_turn_batch"):
        assert name not in message
    assert f"2 of {S4_TOTAL}" in message


def test_module_imports_are_stdlib_only() -> None:
    tree = ast.parse(MODULE_SOURCE, filename=str(MODULE_PATH))
    findings: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                root = alias.name.split(".")[0]
                if root not in sys.stdlib_module_names:
                    findings.append(f"{node.lineno}: import {alias.name}")
        elif isinstance(node, ast.ImportFrom):
            root = (node.module or "").split(".")[0]
            if root and root not in sys.stdlib_module_names:
                findings.append(f"{node.lineno}: from {node.module} import ...")
    assert findings == [], findings


def test_importing_module_pulls_no_package_code() -> None:
    """Fresh interpreter: importing the module by path must not import any
    vibecomfy package (the exec assembler and its fragments stay untouched)."""
    loader = (
        "import importlib.util, sys\n"
        f"spec = importlib.util.spec_from_file_location('edit_batch_repl_under_test', {str(MODULE_PATH)!r})\n"
        "m = importlib.util.module_from_spec(spec)\n"
        "sys.modules['edit_batch_repl_under_test'] = m\n"
        "spec.loader.exec_module(m)\n"
        "print(','.join(sorted(k for k in sys.modules if k.startswith('vibecomfy'))))"
    )
    result = subprocess.run(
        [sys.executable, "-c", loader], cwd=REPO_ROOT, capture_output=True, text=True, timeout=120
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "", result.stdout


def _call_name(node: ast.AST) -> str | None:
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
        return node.func.id
    return None


def _is_deps_construction(node: ast.AST) -> bool:
    return _call_name(node) in {"build_edit_batch_repl_deps", "EditBatchReplDeps"}


def test_no_module_level_singleton_snapshot() -> None:
    """No module-level `EditBatchReplDeps(...)` or `build_edit_batch_repl_deps(...)`
    call: deps must be rebuilt per invocation, never snapshot at import time."""
    tree = ast.parse(MODULE_SOURCE, filename=str(MODULE_PATH))
    findings: list[str] = []
    for node in tree.body:
        if isinstance(node, (ast.Assign, ast.AnnAssign)) and _is_deps_construction(node.value):
            findings.append(f"{node.lineno}: module-level {_call_name(node.value)} call")
        elif isinstance(node, ast.Expr) and _is_deps_construction(node.value):
            findings.append(f"{node.lineno}: module-level {_call_name(node.value)} call")
    assert findings == [], findings
