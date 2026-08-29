from __future__ import annotations

import tomllib
from pathlib import Path


def test_comfy_nodes_are_counted_by_coverage_policy() -> None:
    pyproject = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))

    coverage_run = pyproject["tool"]["coverage"]["run"]
    omitted_paths = coverage_run.get("omit", [])

    assert "vibecomfy" in coverage_run["source"]
    assert "vibecomfy/comfy_nodes/*" not in omitted_paths


def test_fast_gate_uses_declared_coverage_floor() -> None:
    makefile = Path("Makefile").read_text(encoding="utf-8")

    assert "COVERAGE_FAIL_UNDER ?= 70" in makefile
    assert "--cov-fail-under=$(COVERAGE_FAIL_UNDER)" in makefile
    assert "--cov-fail-under=0" not in makefile


def test_fast_and_broad_python_gates_are_explicitly_distinct() -> None:
    makefile = Path("Makefile").read_text(encoding="utf-8")

    assert "FAST_PYTEST :=" in makefile
    assert "fast:" in makefile
    assert "BROAD Python gate: all tests under tests" in makefile
    assert "broad-pytest:" in makefile
    assert "PYTEST) -n 8 -q -p no:cacheprovider tests" in makefile
    assert "full-pytest: broad-pytest" in makefile
