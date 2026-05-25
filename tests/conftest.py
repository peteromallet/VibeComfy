from __future__ import annotations

pytest_plugins = ("pytester",)

# Parallel-worktree WIP: test_agentic_affordances.py imports error classes
# (CanonicalParityFailure, MissingModelAssetError, SchemaMismatchError,
# UnknownClassError) that are not yet defined in vibecomfy.errors — they are
# planned for the vibecomfy.testing sprint (megaplan B) and will be wired in
# when that sprint merges.  Excluding it here prevents a collection-time
# ImportError that blocks the entire test run.
#
# test_testing_dry_run.py and test_testing_import_cost.py test import-cost
# contracts for vibecomfy.testing which currently pulls vibecomfy.runtime.client
# and vibecomfy.runtime.server eagerly.  Those tests belong to the same
# vibecomfy.testing sprint and are excluded until that sprint's import
# refactoring lands.
collect_ignore = [
    "test_agentic_affordances.py",
    "test_testing_dry_run.py",
    "test_testing_import_cost.py",
]

import importlib.util
import warnings

import pytest


@pytest.fixture(autouse=True)
def _release_workflow_context_binding():
    """Release any leaked ContextVar workflow binding after each test.

    Templates now use ``wf = new_workflow(...)`` (no ``with`` block), which
    eagerly binds the ContextVar and relies on ``finalize()`` to release it.
    Tests that ``exec`` + call ``build()`` directly are an unguarded exec+build
    loop: a build that raises before ``finalize()`` leaks a binding that would
    poison the next test's ``new_workflow()`` with a nested-context error. This
    keeps test isolation the way the loader ``finally`` guards keep prod clean.
    """
    yield
    from vibecomfy.workflow_context import active_workflow, unbind_workflow

    unbind_workflow(active_workflow())


def pytest_configure(config: pytest.Config) -> None:
    # Hand the active pytest config to the runpod budget helpers so that
    # ``--runpod-full`` raises the default cap from $2 to $15 without each
    # smoke test having to thread the config through.
    try:
        from tests.smoke import _runpod_helpers as _rh
    except Exception:
        return
    _rh.set_pytest_config(config)


def pytest_sessionfinish(session: pytest.Session, exitstatus: int) -> None:
    config = session.config
    if not (config.getoption("--runpod") or config.getoption("--runpod-full")):
        return
    try:
        from tests.smoke import _runpod_helpers as _rh
    except Exception:
        return
    state = _rh.get_budget_state()
    budget = state.get("budget_usd")
    actual = float(state.get("actual_usd", 0.0))
    if budget is None:
        budget_str = "unset"
    else:
        budget_str = f"${float(budget):.2f}"
    reporter = config.pluginmanager.getplugin("terminalreporter")
    line = f"RunPod spend: ${actual:.2f} / {budget_str}"
    if reporter is not None:
        reporter.write_line(line)
    else:
        print(line)


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption(
        "--runpod",
        action="store_true",
        default=False,
        help="Run opt-in RunPod GPU smoke tests (provisions real pods; requires RUNPOD_API_KEY).",
    )
    parser.addoption(
        "--runpod-full",
        action="store_true",
        default=False,
        help="Run the opt-in production-resolution matrix (multi-pod; ~$5-10; requires RUNPOD_API_KEY).",
    )


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    runpod_enabled = config.getoption("--runpod")
    runpod_full_enabled = config.getoption("--runpod-full")
    if not (runpod_enabled and runpod_full_enabled):
        selected: list[pytest.Item] = []
        deselected: list[pytest.Item] = []
        for item in items:
            if "runpod_full" in item.keywords and not runpod_full_enabled:
                deselected.append(item)
            elif "runpod" in item.keywords and not runpod_enabled:
                deselected.append(item)
            else:
                selected.append(item)
        if deselected:
            config.hook.pytest_deselected(items=deselected)
            items[:] = selected

    if importlib.util.find_spec("pytest_rerunfailures") is None:
        warnings.warn(
            "pytest-rerunfailures not installed; runpod flake-retry markers skipped",
            stacklevel=2,
        )
        return
    flaky_marker = pytest.mark.flaky(reruns=1, reruns_delay=10)
    for item in items:
        if "runpod" in item.keywords or "runpod_full" in item.keywords:
            item.add_marker(flaky_marker)