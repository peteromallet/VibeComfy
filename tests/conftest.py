from __future__ import annotations

pytest_plugins = ("pytester",)


import importlib.util
import pathlib
import sys
import warnings

import pytest

_REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))
for _module_name, _module in tuple(sys.modules.items()):
    if _module_name != "vibecomfy" and not _module_name.startswith("vibecomfy."):
        continue
    _module_file = getattr(_module, "__file__", None)
    if _module_file is None:
        continue
    try:
        pathlib.Path(_module_file).resolve().relative_to(_REPO_ROOT)
    except ValueError:
        sys.modules.pop(_module_name, None)

_KNOWN_FAILURES_FILE = pathlib.Path(__file__).parent / "known_failures.txt"


def _load_known_failures() -> frozenset[str]:
    if not _KNOWN_FAILURES_FILE.exists():
        return frozenset()
    lines = _KNOWN_FAILURES_FILE.read_text().splitlines()
    return frozenset(ln.strip() for ln in lines if ln.strip() and not ln.strip().startswith("#"))


@pytest.fixture(autouse=True)
def _reset_workflow_context_var() -> None:
    """Reset ``_CURRENT_WORKFLOW`` between tests.

    Post-revert, ``new_workflow()`` eagerly binds the ContextVar so that the
    emitted ``wf = new_workflow(...)`` form can be discovered by node() at
    build time.  Tests that build workflows but don't call ``wf.finalize(...)``
    (the canonical release point) can leak the binding into subsequent tests,
    which then trip ``Nested workflow contexts not supported``.  This autouse
    fixture clears any leaked binding before each test.
    """
    try:
        from vibecomfy.workflow_context import _CURRENT_WORKFLOW
    except Exception:
        yield
        return
    _CURRENT_WORKFLOW.set(None)
    yield
    _CURRENT_WORKFLOW.set(None)


@pytest.fixture(autouse=True)
def _isolate_comfyui_import_state() -> None:
    """Keep optional live-ComfyUI imports from leaking across tests."""
    sys_path_before = list(sys.path)
    modules_before = set(sys.modules)
    yield

    sys.path[:] = sys_path_before

    try:
        from vibecomfy import comfy_backend

        comfy_backend.reset_cache()
    except Exception:
        pass

    try:
        from vibecomfy.comfy_nodes.agent import edit as agent_edit

        agent_edit._RUNTIME_OBJECT_INFO_PATH.clear()
    except Exception:
        pass

    for name in tuple(sys.modules):
        if name in modules_before:
            continue
        if (
            name == "comfy"
            or name.startswith("comfy.")
            or name in {"nodes", "folder_paths", "execution", "latent_preview"}
        ):
            sys.modules.pop(name, None)


def pytest_configure(config: pytest.Config) -> None:
    # Hand the active pytest config to the runpod budget helpers so that
    # ``--runpod-full`` raises the default cap from $2 to $15 without each
    # smoke test having to thread the config through.
    try:
        from tests.smoke import _runpod_helpers as _rh
    except Exception:
        pass
    else:
        _rh.set_pytest_config(config)
    config.addinivalue_line(
        "markers",
        "info: informational baseline tests that may skip when prerequisites are unavailable",
    )


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
    parser.addoption(
        "--known-failures-audit",
        action="store_true",
        default=False,
        help="Report entries in known_failures.txt that no longer match any collected test ID.",
    )


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    runpod_enabled = config.getoption("--runpod")
    runpod_full_enabled = config.getoption("--runpod-full")
    allow_runpod = runpod_enabled or runpod_full_enabled
    allow_runpod_full = runpod_full_enabled
    if not (allow_runpod and allow_runpod_full):
        selected: list[pytest.Item] = []
        deselected: list[pytest.Item] = []
        for item in items:
            if "runpod_full" in item.keywords and not allow_runpod_full:
                deselected.append(item)
            elif "runpod" in item.keywords and not allow_runpod:
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


def pytest_terminal_summary(terminalreporter: pytest.TerminalReporter, exitstatus: int, config: pytest.Config) -> None:
    """Exit non-zero only when there are NEW failures not in known_failures.txt.

    Tests that are already in the by-design-red baseline are silently accepted.
    A rising set (test IDs not in the baseline) is the real regression signal.

    When ``--known-failures-audit`` is passed, also report STALE entries in
    ``known_failures.txt`` that no longer map to any collected test ID.
    """
    # --- Stale-failures audit (independent of exit status) ---
    if config.getoption("--known-failures-audit", default=False):
        known = _load_known_failures()
        if known:
            collected_ids = {item.nodeid for item in terminalreporter.stats.get("passed", [])}
            collected_ids.update(item.nodeid for item in terminalreporter.stats.get("failed", []))
            collected_ids.update(item.nodeid for item in terminalreporter.stats.get("skipped", []))
            collected_ids.update(item.nodeid for item in terminalreporter.stats.get("xfailed", []))
            collected_ids.update(item.nodeid for item in terminalreporter.stats.get("xpassed", []))
            # Also try to get the full collected set from the session
            session = terminalreporter._session  # type: ignore[attr-defined]
            if hasattr(session, "items"):
                collected_ids.update(item.nodeid for item in session.items)
            stale = sorted(known - collected_ids)
            if stale:
                terminalreporter.write_sep("=", "STALE FAILURES (in known_failures.txt but not collected)", yellow=True)
                for nodeid in stale:
                    terminalreporter.write_line(f"  STALE: {nodeid}", yellow=True)
                terminalreporter.write_line(
                    f"{len(stale)} stale entry(s) in known_failures.txt — remove or update them.",
                    yellow=True,
                )
            else:
                terminalreporter.write_line(
                    f"known_failures.txt audit: all {len(known)} entry(s) map to collected tests.",
                    green=True,
                )

    # --- New-failures gate ---
    stats = terminalreporter.stats
    failed_items = stats.get("failed", [])
    if not failed_items:
        return

    known = _load_known_failures()
    new_failures = [
        rep.nodeid for rep in failed_items if rep.nodeid not in known
    ]

    if new_failures:
        terminalreporter.write_sep("=", "NEW FAILURES (not in known_failures.txt)", red=True)
        for nodeid in sorted(new_failures):
            terminalreporter.write_line(f"  NEW FAIL: {nodeid}", red=True)
        terminalreporter.write_line(
            f"{len(new_failures)} new failure(s) detected — update tests/known_failures.txt if intentional.",
            red=True,
        )
        # Force a non-zero exit even if pytest would otherwise consider only known failures
        terminalreporter._session.exitstatus = 1  # type: ignore[attr-defined]
    else:
        known_count = len(failed_items)
        terminalreporter.write_line(
            f"All {known_count} failure(s) are in known_failures.txt baseline (by-design-red). No regressions.",
            green=True,
        )
        # Reset exit status so CI gates pass when failures are all known-baseline.
        terminalreporter._session.exitstatus = 0  # type: ignore[attr-defined]
