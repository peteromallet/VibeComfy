"""T-021: characterize the two /vibecomfy/agent-edit route families.

Ground truth (S1, resolutions-digest.md):

* Production submit routes — POST /vibecomfy/agent-edit, POST
  /vibecomfy/agent-executor, and the legacy POST /agent/edit alias — all
  dispatch through ``_handle_agent_executor_submit``, which builds an
  ``ExecutorRequest`` and calls ``executor.core.run_executor``.  None of them
  touches any ``_handle_agent_edit*`` legacy handler.
* The five legacy handlers (``_handle_agent_edit``, ``_handle_agent_edit_accept``,
  ``_handle_agent_edit_chat``, ``_handle_agent_edit_rebaseline``,
  ``_handle_agent_edit_audit``) are referenced only by test code, and there is
  no live ``/vibecomfy/agent-edit/audit`` route.
* ``reject_turn`` (the routes.py wrapper over ``session.reject_turn``) is
  ALIVE: the live ``/vibecomfy/agent-edit/reject`` route calls
  ``_handle_agent_edit_reject``, which calls ``reject_turn``, which delegates
  to ``_session_reject_turn``.

This is a static characterization: it parses ``routes.py`` with the ``ast``
module and scans the repo for references.  No HTTP harness is needed.
"""

from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ROUTES_PATH = ROOT / "vibecomfy" / "comfy_nodes" / "agent" / "routes.py"

EXECUTOR_SUBMIT = "_handle_agent_executor_submit"
REJECT_HANDLER = "_handle_agent_edit_reject"

# S1: the legacy chain is test-only; reject_turn is separately ALIVE.
LEGACY_HANDLERS = frozenset(
    {
        "_handle_agent_edit",
        "_handle_agent_edit_accept",
        "_handle_agent_edit_chat",
        "_handle_agent_edit_rebaseline",
        "_handle_agent_edit_audit",
    }
)

# Production submit routes: all three must route through the executor adapter.
SUBMIT_ROUTES = frozenset(
    {
        "/vibecomfy/agent-edit",
        "/vibecomfy/agent-executor",
        "/agent/edit",
    }
)

REJECT_ROUTE = "/vibecomfy/agent-edit/reject"
AUDIT_ROUTE = "/vibecomfy/agent-edit/audit"

# Every agent-edit-family path registered inside register_agent_edit_routes.
AGENT_EDIT_ROUTES = SUBMIT_ROUTES | frozenset(
    {
        "/vibecomfy/agent-edit/accept",
        "/vibecomfy/agent-edit/prepare",
        "/vibecomfy/agent-edit/finalize",
        "/vibecomfy/agent-edit/rollback",
        "/vibecomfy/agent-edit/reconcile",
        REJECT_ROUTE,
        "/vibecomfy/agent-edit/rebaseline",
        "/vibecomfy/agent-edit/chat",
        "/vibecomfy/agent-edit/recover",
        "/vibecomfy/agent-edit/session-bundle",
        "/vibecomfy/agent-edit/session-json",
    }
)

# Directories that are gitignored scratch/venv/vendored trees — rg skips them.
_SKIP_DIRS = frozenset(
    {
        ".git",
        ".venv",
        "node_modules",
        "out",
        "external_workflows",
        "web_dist",
        ".megaplan",
        ".megaplan-worktrees",
        ".desloppify",
        ".pytest_cache",
        ".mypy_cache",
        ".ruff_cache",
        ".hypothesis",
        ".import_linter_cache",
        ".watchdog-runs",
        ".tmp",
        ".claude",
        ".vscode",
        ".github",
        "temp",
        "test-results",
        "__pycache__",
    }
)


def _routes_module_ast() -> ast.Module:
    return ast.parse(ROUTES_PATH.read_text(encoding="utf-8"))


def _route_method(decorator: ast.expr) -> str | None:
    """HTTP method for ``@app.routes.<method>(<path>)`` decorators."""
    if not isinstance(decorator, ast.Call):
        return None
    func = decorator.func
    if not isinstance(func, ast.Attribute) or func.attr not in {"post", "get"}:
        return None
    if not (isinstance(func.value, ast.Attribute) and func.value.attr == "routes"):
        return None
    return func.attr


def _route_path(decorator: ast.expr) -> str | None:
    if not isinstance(decorator, ast.Call) or not decorator.args:
        return None
    arg = decorator.args[0]
    if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
        return arg.value
    return None


def _is_agent_edit_family_path(path: str) -> bool:
    return (
        path == "/agent/edit"
        or path.startswith("/vibecomfy/agent-edit")
        or path.startswith("/vibecomfy/agent-executor")
    )


def _route_table(tree: ast.Module) -> dict[str, tuple[str, ast.AsyncFunctionDef]]:
    """path -> (http_method, route handler) registered in register_agent_edit_routes."""
    table: dict[str, tuple[str, ast.AsyncFunctionDef]] = {}
    for node in tree.body:
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if node.name != "register_agent_edit_routes":
            continue
        for child in node.body:
            if not isinstance(child, ast.AsyncFunctionDef):
                continue
            for decorator in child.decorator_list:
                method = _route_method(decorator)
                path = _route_path(decorator)
                if method is not None and path is not None:
                    table[path] = (method, child)
    return table


def _referenced_names(node: ast.AST) -> set[str]:
    """Every ``ast.Name`` referenced in the subtree.

    Route handlers hand function objects to ``asyncio.to_thread(...)`` as plain
    arguments (e.g. ``_handle_agent_executor_submit``), so call-target
    collection alone is insufficient: any Name reference counts.
    """
    return {child.id for child in ast.walk(node) if isinstance(child, ast.Name)}


def _module_function(tree: ast.Module, name: str) -> ast.FunctionDef | ast.AsyncFunctionDef | None:
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name:
            return node
    return None


def _session_reject_turn_imported(tree: ast.Module) -> bool:
    for node in tree.body:
        if isinstance(node, ast.ImportFrom) and node.level == 1 and node.module == "session":
            for alias in node.names:
                if alias.name == "reject_turn" and alias.asname == "_session_reject_turn":
                    return True
    return False


def _repo_python_files() -> list[Path]:
    files: list[Path] = []
    for path in ROOT.rglob("*.py"):
        if any(part in _SKIP_DIRS for part in path.parts):
            continue
        files.append(path)
    return files


def _repo_reference_map() -> dict[str, list[Path]]:
    """For each legacy name, the repo Python files whose bytes contain it."""
    refs: dict[str, list[Path]] = {name: [] for name in LEGACY_HANDLERS}
    for path in _repo_python_files():
        try:
            data = path.read_bytes()
        except OSError:
            continue
        for name in LEGACY_HANDLERS:
            if name.encode("utf-8") in data:
                refs[name].append(path)
    return refs


# ── (1) Production submit routes map to the executor adapter ────────────────


def test_submit_routes_map_to_executor_submit_only() -> None:
    table = _route_table(_routes_module_ast())
    for path in sorted(SUBMIT_ROUTES):
        assert path in table, f"submit route {path} is not registered"
        method, handler = table[path]
        assert method == "post", f"submit route {path} must be POST, got {method}"
        called = _referenced_names(handler)
        assert EXECUTOR_SUBMIT in called, (
            f"{path} must dispatch through {EXECUTOR_SUBMIT}; calls {sorted(called)}"
        )
        legacy = sorted(called & LEGACY_HANDLERS)
        assert not legacy, f"{path} must not call legacy handlers: {legacy}"

    # Both directions: no other route may touch the executor adapter.
    executor_routes = {
        path
        for path, (_, handler) in table.items()
        if EXECUTOR_SUBMIT in _referenced_names(handler)
    }
    assert executor_routes == SUBMIT_ROUTES, (
        f"executor submit must be wired to exactly {sorted(SUBMIT_ROUTES)}, "
        f"got {sorted(executor_routes)}"
    )


def test_executor_submit_uses_executor_core_run_executor() -> None:
    tree = _routes_module_ast()
    submit = _module_function(tree, EXECUTOR_SUBMIT)
    assert submit is not None, f"{EXECUTOR_SUBMIT} is no longer defined in routes.py"
    called = _referenced_names(submit)
    assert "run_executor" in called, f"{EXECUTOR_SUBMIT} must call run_executor"
    assert "ExecutorRequest" in called, f"{EXECUTOR_SUBMIT} must build an ExecutorRequest"


# ── (2) The five legacy handlers are referenced only by test code ───────────


def test_legacy_handlers_are_test_only() -> None:
    tree = _routes_module_ast()
    refs = _repo_reference_map()
    for name in sorted(LEGACY_HANDLERS):
        assert _module_function(tree, name) is not None, (
            f"{name} is no longer defined in routes.py"
        )
        hits = refs[name]
        offending = [p for p in hits if p != ROUTES_PATH and "tests" not in p.parts]
        assert not offending, (
            f"{name} is referenced outside routes.py and tests: {[str(p) for p in offending]}"
        )
        test_hits = [p for p in hits if "tests" in p.parts]
        assert test_hits, f"{name} has no test references at all"


# ── (3) reject_turn is wired to a live route ────────────────────────────────


def test_reject_turn_wrapper_is_wired_to_live_route() -> None:
    tree = _routes_module_ast()
    table = _route_table(tree)
    assert REJECT_ROUTE in table, f"{REJECT_ROUTE} is not registered"
    _, reject_route_handler = table[REJECT_ROUTE]
    assert REJECT_HANDLER in _referenced_names(reject_route_handler), (
        f"{REJECT_ROUTE} must dispatch through {REJECT_HANDLER}"
    )

    reject_impl = _module_function(tree, REJECT_HANDLER)
    assert reject_impl is not None, f"{REJECT_HANDLER} is no longer defined in routes.py"
    assert "reject_turn" in _referenced_names(reject_impl), (
        f"{REJECT_HANDLER} must call the reject_turn wrapper"
    )

    reject_wrapper = _module_function(tree, "reject_turn")
    assert reject_wrapper is not None, "routes.py reject_turn wrapper is gone"
    assert "_session_reject_turn" in _referenced_names(reject_wrapper), (
        "routes.reject_turn must delegate to session.reject_turn"
    )
    assert _session_reject_turn_imported(tree), (
        "routes.py must import reject_turn from .session as _session_reject_turn"
    )


# ── (4) No /agent-edit/audit route exists ───────────────────────────────────


def test_no_agent_edit_audit_route_exists() -> None:
    table = _route_table(_routes_module_ast())
    agent_edit_paths = {path for path in table if _is_agent_edit_family_path(path)}
    assert AUDIT_ROUTE not in agent_edit_paths, f"{AUDIT_ROUTE} must not be registered"
    assert not any(path.endswith("/audit") for path in agent_edit_paths), (
        f"unexpected audit route: {sorted(p for p in agent_edit_paths if p.endswith('/audit'))}"
    )
    for path, (_, handler) in table.items():
        assert "_handle_agent_edit_audit" not in _referenced_names(handler), (
            f"{path} wires the test-only audit handler"
        )


# ── Families are distinct and fully accounted for ───────────────────────────


def test_route_families_are_distinct() -> None:
    tree = _routes_module_ast()
    table = _route_table(tree)
    agent_edit_paths = {path for path in table if _is_agent_edit_family_path(path)}
    assert agent_edit_paths == AGENT_EDIT_ROUTES, (
        "unexpected agent-edit route set: "
        f"{sorted(agent_edit_paths ^ AGENT_EDIT_ROUTES)}"
    )
    for path, (_, handler) in table.items():
        legacy = sorted(_referenced_names(handler) & LEGACY_HANDLERS)
        assert not legacy, f"{path} references a test-only legacy handler: {legacy}"


def test_module_registration_hook_installs_the_route_table() -> None:
    """Production (non-headless) import registers the live route table."""
    tree = _routes_module_ast()
    assert any(
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "register_agent_edit_routes"
        for node in ast.walk(tree)
    ), "routes.py must call register_agent_edit_routes at module scope"


# ── T-022: both route families emit the single unified failure envelope ─────


def _import_routes_headless(monkeypatch):
    """Import routes.py without the aiohttp registration hook side effects."""
    monkeypatch.setenv("VIBECOMFY_HEADLESS", "1")
    from vibecomfy.comfy_nodes.agent import routes as routes_mod

    return routes_mod


def _assert_unified_failure_envelope(envelope: dict) -> None:
    """The single wire envelope every agent-edit failure must carry."""
    from vibecomfy.comfy_nodes.agent.contracts import (
        AGENT_EDIT_TURN_CONTRACT_VERSION,
        FailureKind,
    )

    assert envelope["ok"] is False
    assert envelope["kind"] in {kind.value for kind in FailureKind}
    assert isinstance(envelope["stage"], str) and envelope["stage"]
    assert envelope["canvas_apply_allowed"] is False
    assert envelope["apply_allowed"] is False
    assert envelope["queue_allowed"] is False
    assert isinstance(envelope["retryable"], bool)
    assert isinstance(envelope["next_action"], str)
    assert isinstance(envelope["graph_unchanged"], bool)
    assert envelope["contract_version"] == AGENT_EDIT_TURN_CONTRACT_VERSION
    assert isinstance(envelope["message"], str) and envelope["message"].strip()
    assert isinstance(envelope["user_facing_message"], str)
    assert envelope["outcome"]["kind"] == "error"
    assert envelope["outcome"]["failure_kind"] == envelope["kind"]
    assert envelope["outcome"]["stage"] == envelope["stage"]
    assert envelope["outcome"]["retryable"] == envelope["retryable"]
    assert envelope["outcome"]["next_action"] == envelope["next_action"]
    assert envelope["internal_outcome"]["kind"] == "failure"
    assert "candidate" in envelope
    assert envelope["eligibility"] == envelope["apply_eligibility"]
    assert "audit_ref" in envelope
    assert "debug" in envelope
    assert envelope["debug"]["failure"]["kind"] == envelope["kind"]


def test_both_route_families_emit_the_same_failure_envelope(
    monkeypatch,
    tmp_path,
) -> None:
    """The executor submit family and the legacy handlers route every failure
    through the single ``_failure_response`` builder, so both families emit the
    same wire envelope on failure."""
    from vibecomfy.comfy_nodes.agent.contracts import FailureKind, classify_failure, failure_envelope

    routes_mod = _import_routes_headless(monkeypatch)

    # Legacy family: _handle_agent_edit surfaces a classified handler failure.
    def _boom(*_args, **_kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr(routes_mod, "handle_agent_edit", _boom)
    legacy = routes_mod._handle_agent_edit(
        {"graph": {"nodes": [], "links": []}, "task": "change the save prefix to after"},
        session_root=tmp_path,
    )
    expected_legacy = routes_mod._failure_response(
        "route",
        classify_failure("route", RuntimeError("boom")),
    )
    assert legacy == expected_legacy, "legacy handler must route through _failure_response"

    # Executor family: _handle_agent_executor_submit surfaces a validation failure.
    executor, status = routes_mod._handle_agent_executor_submit(None)
    expected_executor = routes_mod._failure_response(
        "agent_executor",
        failure_envelope(
            FailureKind.MISSING_REQUIRED_FIELD,
            "agent_executor",
            agent_failure_context={"explanation": "Request body must be a JSON object."},
        ),
    )
    assert status == 400
    assert executor == expected_executor, "executor submit must route through _failure_response"

    # Both families emit the same envelope shape (same keys, same contract).
    _assert_unified_failure_envelope(legacy)
    _assert_unified_failure_envelope(executor)
    assert set(legacy) == set(executor), (
        f"families must emit the same envelope keys: {sorted(set(legacy) ^ set(executor))}"
    )
    for key in ("ok", "canvas_apply_allowed", "apply_allowed", "queue_allowed", "contract_version"):
        assert legacy[key] == executor[key], f"{key} must match across families"


def test_failure_response_contract_error_fails_closed(monkeypatch) -> None:
    """Malformed internal failures must never escape as unstamped wire data."""
    from vibecomfy.comfy_nodes.agent.contracts import FailureKind

    routes_mod = _import_routes_headless(monkeypatch)

    def _contract_boom(*_args, **_kwargs):
        raise RuntimeError("contract enforcement failed")

    monkeypatch.setattr(routes_mod, "ensure_agent_edit_response_contract", _contract_boom)

    response = routes_mod._failure_response(
        "agent_executor",
        {
            "ok": False,
            "outcome": {"kind": "not-a-public-outcome"},
            "unvalidated_internal_field": "must-not-escape",
        },
    )

    _assert_unified_failure_envelope(response)
    assert response["kind"] == FailureKind.VALIDATION_ERROR.value
    assert response["stage"] == "agent_executor"
    assert response["agent_failure_context"] == {
        "explanation": "The agent response failed public contract validation.",
        "contract_error": "RuntimeError",
    }
    assert "unvalidated_internal_field" not in response


def test_executor_submit_failure_envelope_matches_legacy_reject_envelope(
    monkeypatch,
) -> None:
    """The live reject route handler (same envelope family) emits the same
    unified failure envelope as the executor submit family for a missing body."""
    routes_mod = _import_routes_headless(monkeypatch)

    executor, status = routes_mod._handle_agent_executor_submit(None)
    legacy_reject = routes_mod._handle_agent_edit_reject(None)

    assert status == 400
    _assert_unified_failure_envelope(executor)
    _assert_unified_failure_envelope(legacy_reject)
    assert set(executor) == set(legacy_reject)
    for key in ("ok", "canvas_apply_allowed", "apply_allowed", "queue_allowed", "contract_version"):
        assert executor[key] == legacy_reject[key], f"{key} must match across families"
