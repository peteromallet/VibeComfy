from __future__ import annotations

pytest_plugins = ("pytester",)


import importlib.util
import os
import pathlib
import sys
import warnings
from dataclasses import dataclass

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
_QUARANTINE_DIR = pathlib.Path(__file__).parent / "quarantine"
_QUARANTINE_REQUIRED_METADATA = ("owner", "reason")

# Test modules can temporarily replace the ComfyUI entry-point package while
# exercising loader registration.  Keep the module objects imported during
# collection authoritative so a later monkeypatch targets the same module as
# collection-time handler imports.
_CANONICAL_AGENT_PACKAGE = None
_CANONICAL_AGENT_ROUTES = None


@dataclass(frozen=True)
class QuarantineEntry:
    nodeid: str
    path: pathlib.Path
    owner: str
    reason: str
    metadata: dict[str, str]

    @property
    def display_path(self) -> str:
        try:
            return self.path.relative_to(_REPO_ROOT).as_posix()
        except ValueError:
            return self.path.as_posix()


def _metadata_key(raw: str) -> str:
    return raw.strip().lower().replace("-", "_").replace(" ", "_")


def _validate_quarantine_nodeid(path: pathlib.Path, line_number: int, nodeid: str) -> None:
    path_part, separator, selector = nodeid.partition("::")
    if not separator or not path_part.startswith("tests/") or not path_part.endswith(".py"):
        raise ValueError(f"{path}:{line_number}: quarantine entry is not a pytest nodeid: {nodeid!r}")

    selector_without_params = selector.split("[", 1)[0]
    selector_parts = [part for part in selector_without_params.split("::") if part]
    if not selector_parts:
        raise ValueError(f"{path}:{line_number}: quarantine entry is missing a test selector: {nodeid!r}")
    if not selector_parts[-1].startswith("test_"):
        raise ValueError(
            f"{path}:{line_number}: quarantine entry is too broad; list a single test function nodeid: {nodeid!r}"
        )


def _parse_quarantine_file(path: pathlib.Path) -> list[QuarantineEntry]:
    metadata: dict[str, str] = {}
    nodeids: list[str] = []
    for line_number, raw_line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        line = raw_line.strip()
        if not line:
            continue
        if line.startswith("#"):
            payload = line[1:].strip()
            if ":" in payload:
                key, value = payload.split(":", 1)
                normalized_key = _metadata_key(key)
                if normalized_key == "package_owner":
                    normalized_key = "owner"
                metadata[normalized_key] = value.strip()
            continue
        _validate_quarantine_nodeid(path, line_number, line)
        nodeids.append(line)

    if not nodeids:
        return []

    missing = [key for key in _QUARANTINE_REQUIRED_METADATA if not metadata.get(key)]
    if missing:
        missing_list = ", ".join(missing)
        raise ValueError(f"{path}: missing required quarantine metadata: {missing_list}")

    return [
        QuarantineEntry(
            nodeid=nodeid,
            path=path,
            owner=metadata["owner"],
            reason=metadata["reason"],
            metadata=dict(metadata),
        )
        for nodeid in nodeids
    ]


def _legacy_known_failure_entries() -> list[QuarantineEntry]:
    if not _KNOWN_FAILURES_FILE.exists():
        return []
    entries: list[QuarantineEntry] = []
    for line in _KNOWN_FAILURES_FILE.read_text(encoding="utf-8").splitlines():
        nodeid = line.strip()
        if not nodeid or nodeid.startswith("#"):
            continue
        entries.append(
            QuarantineEntry(
                nodeid=nodeid,
                path=_KNOWN_FAILURES_FILE,
                owner="legacy-known-failures",
                reason="unmigrated legacy baseline",
                metadata={
                    "owner": "legacy-known-failures",
                    "reason": "unmigrated legacy baseline",
                },
            )
        )
    return entries


def _active_legacy_known_failure_nodeids() -> list[str]:
    if not _KNOWN_FAILURES_FILE.exists():
        return []
    return [
        line.strip()
        for line in _KNOWN_FAILURES_FILE.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.strip().startswith("#")
    ]


def _load_quarantine_index(*, include_legacy: bool = False) -> dict[str, QuarantineEntry]:
    index: dict[str, QuarantineEntry] = {}
    if _QUARANTINE_DIR.exists():
        for path in sorted(_QUARANTINE_DIR.glob("*.txt")):
            for entry in _parse_quarantine_file(path):
                previous = index.get(entry.nodeid)
                if previous is not None:
                    raise ValueError(
                        f"{entry.nodeid} is quarantined by both {previous.display_path} and {entry.display_path}"
                    )
                index[entry.nodeid] = entry

    if include_legacy:
        for entry in _legacy_known_failure_entries():
            index.setdefault(entry.nodeid, entry)

    return index


def _assert_known_failures_file_is_retired() -> None:
    active_nodeids = _active_legacy_known_failure_nodeids()
    if not active_nodeids:
        return
    sample = ", ".join(active_nodeids[:3])
    raise ValueError(
        f"{_KNOWN_FAILURES_FILE}: active legacy known-failure entries are not allowed; "
        f"move them to scoped tests/quarantine/*.txt files with owner/reason metadata. Sample: {sample}"
    )


def _load_known_failures() -> frozenset[str]:
    return frozenset(_load_quarantine_index())


@pytest.fixture(autouse=True)
def _isolate_external_network_tokens(monkeypatch: pytest.MonkeyPatch) -> None:
    """Prevent accidental real network calls from developer environment tokens."""
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)


@pytest.fixture(autouse=True)
def _default_on_demand_schemas_off_in_tests(monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep the test suite deterministic.

    On-demand schema resolution does network/git clones of public repos, so it is OFF
    by default in tests even though production defaults ON (the agent should author any
    node pack out of the box). A test opts in by setting ``VIBECOMFY_ON_DEMAND_SCHEMAS=1``
    via ``monkeypatch.setenv``, or by running the suite with that var in the real env
    (e.g. the live on-demand tests). Only applies when the var is otherwise unset, so an
    explicit opt-in — including a ``delenv`` to assert the default-ON path — still wins.
    """
    if "VIBECOMFY_ON_DEMAND_SCHEMAS" not in os.environ:
        monkeypatch.setenv("VIBECOMFY_ON_DEMAND_SCHEMAS", "0")


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
def _reset_gate_context_var() -> None:
    """Prevent a test's ``--yes`` gate context from leaking to later tests."""
    from vibecomfy.security.gate import _gate_context_var, _safe_default_context

    token = _gate_context_var.set(_safe_default_context())
    try:
        yield
    finally:
        _gate_context_var.reset(token)


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

    # Only import the (heavy) ComfyUI agent when the test actually pulled the
    # ComfyUI stack in; otherwise there is nothing to isolate.  Importing
    # ``vibecomfy.comfy_nodes.agent`` transitively loads torch/comfy and can
    # take tens of seconds, which made single-test runs flaky against the
    # pytest-timeout budget even though the test itself never touched ComfyUI.
    if any(name == "comfy" or name.startswith("comfy.") for name in sys.modules):
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

    # A failed import (or a deliberate headless import probe) can remove a
    # submodule from sys.modules while Python leaves the old module object on
    # its parent package.  A later ``from package import child`` then receives
    # that orphan, making monkeypatches ineffective and importlib.reload fail.
    # Remove only such stale module attributes; ordinary package attributes and
    # live modules are untouched.
    for package_name, child_name in (
        ("vibecomfy.agent", "service"),
        ("vibecomfy.comfy_nodes.agent", "routes"),
        ("vibecomfy.runtime", "server"),
        ("vibecomfy.comfy_nodes", "web"),
    ):
        module_name = f"{package_name}.{child_name}"
        if module_name in sys.modules:
            continue
        package = sys.modules.get(package_name)
        child = getattr(package, child_name, None) if package is not None else None
        if getattr(child, "__name__", None) == module_name:
            try:
                delattr(package, child_name)
            except AttributeError:
                pass


def _restore_canonical_agent_module_identity() -> None:
    """Undo in-process entry-point module swaps after fixture teardown."""
    package = _CANONICAL_AGENT_PACKAGE
    routes = _CANONICAL_AGENT_ROUTES
    if package is None or routes is None:
        return

    sys.modules["vibecomfy.comfy_nodes.agent"] = package
    sys.modules["vibecomfy.comfy_nodes.agent.routes"] = routes

    parent = sys.modules.get("vibecomfy.comfy_nodes")
    if parent is not None:
        setattr(parent, "agent", package)
    setattr(package, "routes", routes)


@pytest.hookimpl(hookwrapper=True, trylast=True)
def pytest_runtest_teardown(item: pytest.Item, nextitem: pytest.Item | None) -> None:
    """Restore canonical module identity after all fixture finalizers run."""
    yield
    _restore_canonical_agent_module_identity()

    # Entry-point tests temporarily install synthetic ``vibecomfy.comfy_nodes``
    # packages/modules in sys.modules.  They have no source file and must not
    # shadow the real package for later tests that imported route handlers at
    # collection time.
    for module_name in (
        "vibecomfy.comfy_nodes.agent.routes",
        "vibecomfy.comfy_nodes.agent",
    ):
        module = sys.modules.get(module_name)
        if module is None or getattr(module, "__file__", None) is not None:
            continue
        sys.modules.pop(module_name, None)
        parent_name, _, child_name = module_name.rpartition(".")
        parent = sys.modules.get(parent_name)
        if parent is not None and getattr(parent, child_name, None) is module:
            try:
                delattr(parent, child_name)
            except AttributeError:
                pass


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
    try:
        _assert_known_failures_file_is_retired()
    except ValueError as exc:
        raise pytest.UsageError(str(exc)) from exc
    config.addinivalue_line(
        "markers",
        "info: informational baseline tests that may skip when prerequisites are unavailable",
    )
    try:
        _load_quarantine_index()
    except ValueError as exc:
        raise pytest.UsageError(str(exc)) from exc


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
        help="Report entries in tests/quarantine/*.txt that no longer match any collected test ID.",
    )
    parser.addoption(
        "--run-live",
        action="store_true",
        default=False,
        help="Run opt-in live model/provider tests (calls real APIs; requires credentials).",
    )


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    global _CANONICAL_AGENT_PACKAGE, _CANONICAL_AGENT_ROUTES
    if _CANONICAL_AGENT_PACKAGE is None:
        _CANONICAL_AGENT_PACKAGE = sys.modules.get("vibecomfy.comfy_nodes.agent")
        _CANONICAL_AGENT_ROUTES = sys.modules.get("vibecomfy.comfy_nodes.agent.routes")

    runpod_enabled = config.getoption("--runpod")
    runpod_full_enabled = config.getoption("--runpod-full")
    run_live_enabled = config.getoption("--run-live")
    allow_runpod = runpod_enabled or runpod_full_enabled
    allow_runpod_full = runpod_full_enabled
    selected: list[pytest.Item] = []
    deselected: list[pytest.Item] = []
    for item in items:
        if "runpod_full" in item.keywords and not allow_runpod_full:
            deselected.append(item)
        elif "runpod" in item.keywords and not allow_runpod:
            deselected.append(item)
        elif "live" in item.keywords and not run_live_enabled:
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
    """Exit non-zero only when there are NEW failures not in scoped quarantine files.

    Tests that are already in the by-design-red baseline are silently accepted.
    A rising set (test IDs not in the baseline) is the real regression signal.

    When ``--known-failures-audit`` is passed, also report STALE entries in
    ``tests/quarantine/*.txt`` that no longer map to any collected test ID.
    """
    try:
        quarantine = _load_quarantine_index()
    except ValueError as exc:
        terminalreporter.write_sep("=", "QUARANTINE CONFIG ERROR", red=True)
        terminalreporter.write_line(str(exc), red=True)
        terminalreporter._session.exitstatus = 1  # type: ignore[attr-defined]
        return

    stats = terminalreporter.stats
    failed_items = stats.get("failed", [])
    error_items = stats.get("error", [])
    skipped_items = stats.get("skipped", [])
    xfailed_items = stats.get("xfailed", [])
    xpassed_items = stats.get("xpassed", [])

    # Compute stale entries for every run so the machine-readable count below
    # remains truthful. Details remain opt-in to avoid changing the normal
    # human-facing gate output or making retirement a hard gate here.
    stale: list[str] = []
    if quarantine:
        collected_ids = {item.nodeid for item in terminalreporter.stats.get("passed", [])}
        collected_ids.update(item.nodeid for item in terminalreporter.stats.get("failed", []))
        collected_ids.update(item.nodeid for item in terminalreporter.stats.get("skipped", []))
        collected_ids.update(item.nodeid for item in terminalreporter.stats.get("xfailed", []))
        collected_ids.update(item.nodeid for item in terminalreporter.stats.get("xpassed", []))
        # Also try to get the full collected set from the session
        session = terminalreporter._session  # type: ignore[attr-defined]
        if hasattr(session, "items"):
            collected_ids.update(item.nodeid for item in session.items)
        stale = sorted(set(quarantine) - collected_ids)

    # --- Stale-failures audit (independent of exit status) ---
    if config.getoption("--known-failures-audit", default=False):
        if quarantine:
            if stale:
                terminalreporter.write_sep("=", "STALE FAILURES / QUARANTINES (not collected)", yellow=True)
                for nodeid in stale:
                    entry = quarantine[nodeid]
                    terminalreporter.write_line(
                        f"  STALE: {nodeid} [{entry.display_path}; owner={entry.owner}]",
                        yellow=True,
                    )
                terminalreporter.write_line(
                    f"{len(stale)} stale quarantine entry(s) — remove or update the owning file.",
                    yellow=True,
                )
            else:
                terminalreporter.write_line(
                    f"quarantine audit: all {len(quarantine)} entry(s) map to collected tests.",
                    green=True,
                )

    # Keep this line stable for corrective-gate consumers.  The ordinary pytest
    # summary is human-oriented and does not distinguish quarantined failures
    # from new failures or expose setup/collection errors as a count.
    tolerated_failures = [
        rep.nodeid for rep in failed_items if rep.nodeid in quarantine
    ]
    new_failures = [
        rep.nodeid for rep in failed_items if rep.nodeid not in quarantine
    ]
    terminalreporter.write_line(
        "pytest gate counts: "
        f"passed={len(stats.get('passed', []))} "
        f"failed={len(failed_items)} "
        f"errors={len(error_items)} "
        f"skipped={len(skipped_items)} "
        f"xfailed={len(xfailed_items)} "
        f"xpassed={len(xpassed_items)} "
        f"quarantined_failures={len(tolerated_failures)} "
        f"unexpected_failures={len(new_failures)} "
        f"stale_quarantines={len(stale)}"
    )

    # --- New-failures gate ---
    if not failed_items:
        if error_items:
            terminalreporter.write_sep("=", "PYTEST ERRORS (not quarantinable)", red=True)
            terminalreporter.write_line(
                f"{len(error_items)} setup/collection/internal error(s) detected.",
                red=True,
            )
            # A quarantined test failure must never erase a pytest error.  Keep
            # the original non-zero status (or set the ordinary test-failure
            # status when pytest did not publish one).
            terminalreporter._session.exitstatus = int(exitstatus or pytest.ExitCode.TESTS_FAILED)  # type: ignore[attr-defined]
        elif xpassed_items:
            terminalreporter.write_sep("=", "UNEXPECTED XPASSES", red=True)
            for rep in sorted(xpassed_items, key=lambda report: report.nodeid):
                terminalreporter.write_line(f"  XPASS: {rep.nodeid}", red=True)
            terminalreporter.write_line(
                f"{len(xpassed_items)} unexpected xpass(es) detected.",
                red=True,
            )
            terminalreporter._session.exitstatus = 1  # type: ignore[attr-defined]
        return

    if tolerated_failures:
        terminalreporter.write_sep("=", "TOLERATED QUARANTINED FAILURES", yellow=True)
        for nodeid in sorted(tolerated_failures):
            entry = quarantine[nodeid]
            terminalreporter.write_line(
                f"  TOLERATED FAIL: {nodeid} [{entry.display_path}; owner={entry.owner}]",
                yellow=True,
            )

    if new_failures or error_items or xpassed_items:
        title = "NEW FAILURES (not quarantined)" if new_failures else "PYTEST GATE ERRORS"
        terminalreporter.write_sep("=", title, red=True)
        for nodeid in sorted(new_failures):
            terminalreporter.write_line(f"  NEW FAIL: {nodeid}", red=True)
        if new_failures:
            terminalreporter.write_line(
                f"{len(new_failures)} new failure(s) detected — add a scoped tests/quarantine/*.txt entry only if intentional.",
                red=True,
            )
        if error_items:
            terminalreporter.write_line(
                f"{len(error_items)} setup/collection/internal error(s) detected; these cannot be quarantined.",
                red=True,
            )
        if xpassed_items:
            terminalreporter.write_line(
                f"{len(xpassed_items)} unexpected xpass(es) detected.",
                red=True,
            )
        # Force a non-zero exit even if pytest would otherwise consider only
        # known failures.  Errors and XPASS are never baseline failures.
        terminalreporter._session.exitstatus = 1  # type: ignore[attr-defined]
    else:
        known_count = len(tolerated_failures)
        terminalreporter.write_line(
            f"All {known_count} failure(s) are quarantined baseline failures. No regressions.",
            green=True,
        )
        # Reset only pytest's ordinary test-failure status.  Interrupts,
        # collection failures, usage errors, and internal errors remain red.
        if exitstatus == int(pytest.ExitCode.TESTS_FAILED):
            terminalreporter._session.exitstatus = 0  # type: ignore[attr-defined]
