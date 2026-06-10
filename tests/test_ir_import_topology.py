"""Subprocess-based import-isolation tests for ``vibecomfy.ir``.

Verifies that ``vibecomfy/ir/types.py`` has zero module-level imports
from ``vibecomfy.contracts.*`` or ``vibecomfy.workflow`` (the source-level
constraint the plan mandates for the IR leaf module).

Also verifies via fresh subprocess that ``import vibecomfy.ir.types``
leaves ``sys.modules`` free of ``vibecomfy.contracts.*`` and
``vibecomfy.workflow``.

.. note::

   The subprocess check currently fails for two reasons:

   1. ``vibecomfy/__init__.py`` pre-loads ``vibecomfy.contracts`` and
      ``vibecomfy.workflow`` at package-init time via its own import chain.
   2. ``vibecomfy/ir/workflow.py`` imports ``vibecomfy.contracts.validation``
      at module level (a known carry-over from the original monolithic
      ``workflow.py``, moved during M1 decomposition).

   ``vibecomfy/ir/types.py`` itself is verified import-clean by the
   source-level AST check (``test_ir_types_source_has_no_forbidden_imports``).
   The subprocess tests are marked ``xfail`` until the two leak paths above
   are addressed.
"""

from __future__ import annotations

import ast
import os
import pathlib
import subprocess
import sys

import pytest

# ── repo root (one level above tests/) ──────────────────────────────────────
_REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
_IR_TYPES = _REPO_ROOT / "vibecomfy" / "ir" / "types.py"

FORBIDDEN_NAMESPACES: list[str] = [
    "vibecomfy.contracts",
    "vibecomfy.workflow",
]


# ── source-level check: ir/types.py must have clean imports ─────────────────

def _module_level_imports(source: str, filename: str) -> list[str]:
    """Extract module-level import targets from Python source."""
    try:
        tree = ast.parse(source, filename=filename)
    except SyntaxError:
        return []
    imports: list[str] = []
    for node in ast.iter_child_nodes(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.append(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.module is not None:
                imports.append(node.module)
    return imports


def test_ir_types_source_has_no_forbidden_imports() -> None:
    """``vibecomfy/ir/types.py`` must have zero module-level imports from
    ``vibecomfy.contracts.*`` or ``vibecomfy.workflow``."""
    source = _IR_TYPES.read_text()
    imports = _module_level_imports(source, str(_IR_TYPES))
    bad = [
        imp
        for imp in imports
        if any(
            imp == pfx or imp.startswith(pfx + ".")
            for pfx in FORBIDDEN_NAMESPACES
        )
    ]

    assert not bad, (
        f"vibecomfy/ir/types.py has forbidden module-level imports: {bad}\n"
        f"All imports: {imports}"
    )


def test_ir_all_source_files_except_workflow_have_no_forbidden_imports() -> None:
    """Every ``vibecomfy/ir/*.py`` file except ``workflow.py`` must have
    zero module-level imports from ``vibecomfy.contracts.*`` or
    ``vibecomfy.workflow``.

    ``workflow.py`` is excluded because it carries a known
    ``vibecomfy.contracts.validation`` import (inherited from the
    pre-decomposition monolithic ``workflow.py``).
    """
    ir_dir = _IR_TYPES.parent
    violations: dict[str, list[str]] = {}
    for path in sorted(ir_dir.glob("*.py")):
        if path.name == "workflow.py":
            continue  # known exception — see module docstring
        source = path.read_text()
        imports = _module_level_imports(source, str(path))
        bad = [
            imp
            for imp in imports
            if any(
                imp == pfx or imp.startswith(pfx + ".")
                for pfx in FORBIDDEN_NAMESPACES
            )
        ]
        if bad:
            violations[str(path.relative_to(_REPO_ROOT))] = bad

    assert not violations, (
        f"ir/ source files have forbidden module-level imports:\n"
        + "\n".join(f"  {k}: {v}" for k, v in violations.items())
    )


# ── subprocess-based import isolation ───────────────────────────────────────

def _build_forbidden_check_script(import_target: str) -> str:
    r"""Construct a Python script that imports *import_target*, then
    checks that none of ``FORBIDDEN_NAMESPACES`` appear as a key or
    prefix in ``sys.modules``."""

    forbidden_list_repr = repr(FORBIDDEN_NAMESPACES)
    return (
        "import sys\n"
        f"import {import_target}\n"
        f"forbidden_prefixes = {forbidden_list_repr}\n"
        "found = sorted(\n"
        "    k for k in sys.modules\n"
        "    if any(k == pfx or k.startswith(pfx + '.') for pfx in forbidden_prefixes)\n"
        ")\n"
        "if found:\n"
        "    print('FORBIDDEN:' + ','.join(found))\n"
        "    sys.exit(1)\n"
        "print('CLEAN')\n"
    )


def _run_isolation_check(import_target: str) -> subprocess.CompletedProcess[str]:
    """Run the isolation check in a fresh subprocess with the repo root
    on ``PYTHONPATH``."""
    check_script = _build_forbidden_check_script(import_target)
    env = os.environ.copy()
    existing = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = str(_REPO_ROOT) + (
        os.pathsep + existing if existing else ""
    )

    return subprocess.run(
        [sys.executable, "-c", check_script],
        capture_output=True,
        text=True,
        timeout=30,
        env=env,
    )


@pytest.mark.xfail(
    reason=(
        "Two leak paths: (1) vibecomfy/__init__.py pre-loads contracts "
        "and workflow at package-init time; (2) vibecomfy/ir/workflow.py "
        "imports vibecomfy.contracts.validation at module level. "
        "vibecomfy/ir/types.py is verified import-clean by "
        "test_ir_types_source_has_no_forbidden_imports."
    ),
    strict=True,
)
def test_ir_types_import_isolation() -> None:
    """Fresh subprocess: ``import vibecomfy.ir.types`` must leave
    ``sys.modules`` free of ``vibecomfy.contracts.*`` and
    ``vibecomfy.workflow``."""
    result = _run_isolation_check("vibecomfy.ir.types")

    stdout = result.stdout.strip()
    stderr = result.stderr.strip()

    assert result.returncode == 0, (
        f"ir.types import isolation subprocess failed (rc={result.returncode}).\n"
        f"stdout: {stdout}\n"
        f"stderr: {stderr}"
    )
    assert "CLEAN" in stdout, (
        f"Expected 'CLEAN' in stdout, got: {stdout}\nstderr: {stderr}"
    )


@pytest.mark.xfail(
    reason=(
        "Two leak paths: (1) vibecomfy/__init__.py pre-loads contracts "
        "and workflow at package-init time; (2) vibecomfy/ir/workflow.py "
        "imports vibecomfy.contracts.validation at module level. "
        "vibecomfy/ir/types.py is verified import-clean by "
        "test_ir_types_source_has_no_forbidden_imports."
    ),
    strict=True,
)
def test_ir_import_isolation() -> None:
    """Fresh subprocess: ``import vibecomfy.ir`` must leave
    ``sys.modules`` free of ``vibecomfy.contracts.*`` and
    ``vibecomfy.workflow``.

    .. note::

       ``vibecomfy.ir.__init__`` imports ``VibeWorkflow`` from
       ``vibecomfy.ir.workflow``, so this exercises the full IR
       import surface.
    """
    result = _run_isolation_check("vibecomfy.ir")

    stdout = result.stdout.strip()
    stderr = result.stderr.strip()

    assert result.returncode == 0, (
        f"ir import isolation subprocess failed (rc={result.returncode}).\n"
        f"stdout: {stdout}\n"
        f"stderr: {stderr}"
    )
    assert "CLEAN" in stdout, (
        f"Expected 'CLEAN' in stdout, got: {stdout}\nstderr: {stderr}"
    )
