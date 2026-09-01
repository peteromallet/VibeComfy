from __future__ import annotations

import tomllib
from pathlib import Path

import yaml


def test_comfy_nodes_are_counted_by_coverage_policy() -> None:
    pyproject = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))

    coverage_run = pyproject["tool"]["coverage"]["run"]
    omitted_paths = coverage_run.get("omit", [])

    assert "vibecomfy" in coverage_run["source"]
    assert "vibecomfy/comfy_nodes/*" not in omitted_paths


def test_fast_gate_reports_coverage_without_enforcing_a_floor() -> None:
    makefile = Path("Makefile").read_text(encoding="utf-8")
    pyproject = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))
    fast_recipe = makefile.split("\nfast:\n", 1)[1].split("\n\n", 1)[0]
    broad_recipe = makefile.split("\nbroad-pytest:\n", 1)[1].split("\n\n", 1)[0]

    assert "--cov=vibecomfy" in fast_recipe
    assert "--cov-report=term-missing" in fast_recipe
    assert "--cov-report=xml" in fast_recipe
    assert "--cov-fail-under" not in fast_recipe
    assert pyproject["tool"]["coverage"]["report"].get("fail_under") is None
    assert "BROAD_COVERAGE_FAIL_UNDER ?= 70" in makefile
    assert "--cov-fail-under=$(BROAD_COVERAGE_FAIL_UNDER)" in broad_recipe


def test_fast_and_broad_python_gates_are_explicitly_distinct() -> None:
    makefile = Path("Makefile").read_text(encoding="utf-8")

    assert "FAST_PYTEST :=" in makefile
    assert "FAST_POLICY_TESTS :=" in makefile
    assert "test_coverage_policy.py" in makefile
    assert "test_canonical_parity_reports_hash_mismatch" in makefile
    assert "test_canonical_parity_update_refuses_unbuildable_template" in makefile
    fast_recipe = makefile.split("\nfast:\n", 1)[1].split("\n\n", 1)[0]
    assert "test_layer3_corpus_wide_convert_ui_to_api_gate" not in fast_recipe
    assert "BROAD Python gate: all tests under tests" in makefile
    assert "broad-pytest:" in makefile
    assert "PYTEST) -n 8 -q -p no:cacheprovider tests" in makefile
    assert "full-pytest: broad-pytest" in makefile


def test_make_installers_support_uv_venvs_without_pip() -> None:
    makefile = Path("Makefile").read_text(encoding="utf-8")

    assert "ifneq ($(origin PIP), undefined)" in makefile
    assert "PIP_INSTALL := $(PIP) install" in makefile
    assert "$(PYTHON) -m pip --version" in makefile
    assert "PIP_INSTALL := $(UV) pip install --python $(PYTHON)" in makefile
    assert '$(PIP_INSTALL) --extra-index-url "$(COMFY_INDEX_URL)" -e ".[dev,comfy]"' in makefile
    assert '$(PIP_INSTALL) --extra-index-url "$(COMFY_INDEX_URL)" -e ".[dev,runpod-launch,comfy]"' in makefile


def test_broad_python_workflow_is_scheduled_manual_and_non_required() -> None:
    """Keep the repository-wide lane observable without making PR CI broad."""
    workflow_path = Path(".github/workflows/broad-python.yml")
    workflow_text = workflow_path.read_text(encoding="utf-8")

    # PyYAML's YAML 1.1 loader treats the unquoted ``on`` key as boolean True.
    parsed = yaml.safe_load(workflow_text)
    trigger = parsed.get("on", parsed.get(True))
    assert set(trigger) == {"schedule", "workflow_dispatch"}
    assert trigger["schedule"]

    assert "timeout-minutes: 45" in workflow_text
    assert "make PYTHON=.venv/bin/python install-ci" in workflow_text
    assert "make PYTHON=.venv/bin/python broad-pytest" in workflow_text
    assert "if: always()" in workflow_text
    assert "name: broad-python-coverage-xml" in workflow_text

    forbidden = (
        "--run-live",
        "--runpod",
        "--runpod-full",
        "VIBECOMFY_COMFY_SMOKE",
        "VIBECOMFY_RUN_COVERAGE_SWEEP",
        "continue-on-error",
        "|| true",
        "set +e",
    )
    assert not [fragment for fragment in forbidden if fragment in workflow_text]
