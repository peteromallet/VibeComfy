from __future__ import annotations

import ast
import json
from pathlib import Path

import pytest

from vibecomfy.cli import build_parser
from vibecomfy.comfy_nodes.agent.contracts import DiagnosticRecord
from vibecomfy.comfy_nodes.agent.session import iter_turn_records


REPO_ROOT = Path(__file__).resolve().parents[1]
DEBUG_PATH = REPO_ROOT / "vibecomfy" / "commands" / "_agent_edit_debug.py"
ROUTES_PATH = REPO_ROOT / "vibecomfy" / "comfy_nodes" / "agent" / "routes.py"
SESSION_PATH = REPO_ROOT / "vibecomfy" / "comfy_nodes" / "agent" / "session.py"
CONTRACTS_PATH = REPO_ROOT / "vibecomfy" / "comfy_nodes" / "agent" / "contracts.py"


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


@pytest.fixture()
def editor_sessions(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    comfy = tmp_path / "ComfyUI"
    repo = tmp_path / "vibecomfy"
    root = comfy / "out" / "editor_sessions"
    turn_dir = root / "abc123session" / "turns" / "0001"
    _write_json(
        root / "abc123session" / "session_state.json",
        {
            "baseline_turn_id": "0001",
            "turns": {
                "0001": {
                    "state": "accepted",
                    "agent_edit_protocol": "v2",
                    "accepted_at": "2026-06-03T12:00:00",
                    "submitted_client_live_canvas_token": "live:1:hash",
                }
            },
        },
    )
    _write_json(
        turn_dir / "request.json",
        {"task": "make it brighter", "route": "agent-edit"},
    )
    _write_json(
        turn_dir / "response.json",
        {
            "ok": True,
            "graph": {"nodes": [{"id": 1}, {"id": 2}]},
            "gates": {
                "ui_fidelity_ok": True,
                "state_match_ok": True,
                "queue_validate_ok": True,
            },
            "canvas_apply_allowed": True,
            "queue_allowed": False,
            "done_summary": "Added a sampler.",
        },
    )
    monkeypatch.setenv("COMFY_DIR", str(comfy))
    monkeypatch.setenv("VIBECOMFY_REPO", str(repo))
    monkeypatch.setenv("VIBECOMFY_PORT", "65530")
    return root


def _run_cli(argv: list[str]) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


def test_iter_turn_records_yields_diagnostic_records(editor_sessions: Path) -> None:
    records = list(iter_turn_records(editor_sessions, "abc123session"))
    assert len(records) == 1
    record = records[0]
    assert isinstance(record, DiagnosticRecord)
    assert record.session_id == "abc123session"
    assert record.turn_id == "0001"
    assert record.ok is True
    assert record.lifecycle == "accepted"
    assert record.outcome == "✅ APPLIED"
    assert record.candidate_nodes == 2
    assert record.task == "make it brighter"
    assert record.route == "agent-edit"
    assert record.fidelity_ok is True


def test_iter_turn_records_labels_discarded_v2_terminal_state(
    editor_sessions: Path,
) -> None:
    state_path = editor_sessions / "abc123session" / "session_state.json"
    state = json.loads(state_path.read_text(encoding="utf-8"))
    state["turns"]["0001"]["state"] = "discarded"
    _write_json(state_path, state)

    record = list(iter_turn_records(editor_sessions, "abc123session"))[0]
    assert record.lifecycle == "discarded"
    assert record.outcome == "✗ discarded"


def test_cli_iter_turns_matches_diagnostic_records(
    editor_sessions: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert _run_cli(["debug", "log", "--json"]) == 0
    cli_rows = json.loads(capsys.readouterr().out)
    assert len(cli_rows) == 1

    records = list(iter_turn_records(editor_sessions, "abc123session"))
    record = records[0]
    row = cli_rows[0]
    assert row["session"] == record.session_id
    assert row["turn"] == record.turn_id
    assert row["outcome"] == record.outcome
    assert row["task"] == record.task
    assert row["route"] == record.route
    assert row["fid"] == record.fidelity_ok
    assert row["cand_nodes"] == record.candidate_nodes


def test_iter_turn_records_ignores_missing_session(editor_sessions: Path) -> None:
    records = list(iter_turn_records(editor_sessions, "no-such-session"))
    assert records == []


def test_diagnostic_record_from_dict_ignores_unknown_fields() -> None:
    payload = {
        "session_id": "s",
        "turn_id": "t",
        "unknown_future_field": "ignored",
    }
    record = DiagnosticRecord.from_dict(payload)
    assert record.session_id == "s"
    assert record.turn_id == "t"
    assert record.to_dict()["session_id"] == "s"


def test_cli_debug_uses_session_iterator_without_reowning_diagnostics() -> None:
    debug_source = DEBUG_PATH.read_text(encoding="utf-8")
    session_source = SESSION_PATH.read_text(encoding="utf-8")
    contracts_source = CONTRACTS_PATH.read_text(encoding="utf-8")
    debug_tree = ast.parse(debug_source, filename=str(DEBUG_PATH))
    session_tree = ast.parse(session_source, filename=str(SESSION_PATH))
    contracts_tree = ast.parse(contracts_source, filename=str(CONTRACTS_PATH))

    debug_imports_iter_turn_records = any(
        isinstance(node, ast.ImportFrom)
        and node.module == "vibecomfy.comfy_nodes.agent.session"
        and any(alias.name == "iter_turn_records" for alias in node.names)
        for node in debug_tree.body
    )
    debug_imports_diagnostic_record = any(
        isinstance(node, ast.ImportFrom)
        and node.module == "vibecomfy.comfy_nodes.agent.contracts"
        and any(alias.name == "DiagnosticRecord" for alias in node.names)
        for node in debug_tree.body
    )
    debug_class_names = {
        node.name for node in debug_tree.body if isinstance(node, ast.ClassDef)
    }
    debug_function_names = {
        node.name for node in debug_tree.body if isinstance(node, ast.FunctionDef)
    }
    iter_turns = next(
        node
        for node in debug_tree.body
        if isinstance(node, ast.FunctionDef) and node.name == "_iter_turns"
    )
    iter_turns_names = {
        node.id for node in ast.walk(iter_turns) if isinstance(node, ast.Name)
    }

    session_imports_diagnostic_record = any(
        isinstance(node, ast.ImportFrom)
        and node.level == 1
        and node.module == "contracts"
        and any(alias.name == "DiagnosticRecord" for alias in node.names)
        for node in session_tree.body
    )
    session_iter_turn_records = next(
        node
        for node in session_tree.body
        if isinstance(node, ast.FunctionDef) and node.name == "iter_turn_records"
    )
    session_return_annotation = ast.unparse(session_iter_turn_records.returns)

    assert debug_imports_iter_turn_records
    assert not debug_imports_diagnostic_record
    assert "DiagnosticRecord" not in debug_class_names
    assert "DiagnosticRecord" not in debug_function_names
    assert "iter_turn_records" in iter_turns_names
    assert "DiagnosticRecord" not in iter_turns_names
    assert "_load" not in iter_turns_names
    assert "open" not in iter_turns_names
    assert "json" not in iter_turns_names
    assert "from_dict" not in ast.unparse(iter_turns)
    assert "for record in iter_turn_records(SESS_ROOT, sid)" in debug_source
    assert session_imports_diagnostic_record
    assert session_return_annotation == "Iterator[DiagnosticRecord]"
    assert any(
        isinstance(node, ast.ClassDef) and node.name == "DiagnosticRecord"
        for node in contracts_tree.body
    )


def _python_sources_under(*roots: Path) -> list[Path]:
    return sorted(
        path
        for root in roots
        for path in root.rglob("*.py")
        if "__pycache__" not in path.parts
    )


def _module_imports_name(tree: ast.Module, module: str, name: str, alias: str | None = None) -> bool:
    return any(
        isinstance(node, ast.ImportFrom)
        and node.module == module
        and any(
            imported.name == name and (alias is None or imported.asname == alias)
            for imported in node.names
        )
        for node in tree.body
    )


def test_backend_debug_ownership_definitions_are_canonical() -> None:
    backend_paths = _python_sources_under(
        REPO_ROOT / "vibecomfy" / "comfy_nodes" / "agent",
        REPO_ROOT / "vibecomfy" / "commands",
    )
    definitions: dict[str, list[Path]] = {
        "DiagnosticRecord": [],
        "iter_turn_records": [],
        "_mutate_turn_state": [],
    }

    for path in backend_paths:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in tree.body:
            if isinstance(node, ast.ClassDef) and node.name == "DiagnosticRecord":
                definitions["DiagnosticRecord"].append(path)
            if isinstance(node, ast.FunctionDef) and node.name in {
                "iter_turn_records",
                "_mutate_turn_state",
            }:
                definitions[node.name].append(path)

    assert definitions["DiagnosticRecord"] == [CONTRACTS_PATH]
    assert definitions["iter_turn_records"] == [SESSION_PATH]
    assert definitions["_mutate_turn_state"] == [SESSION_PATH]

    debug_tree = ast.parse(DEBUG_PATH.read_text(encoding="utf-8"), filename=str(DEBUG_PATH))
    assert _module_imports_name(
        debug_tree,
        "vibecomfy.comfy_nodes.agent.session",
        "iter_turn_records",
    )


def test_routes_accept_reject_wrappers_are_thin_session_delegates() -> None:
    routes_tree = ast.parse(ROUTES_PATH.read_text(encoding="utf-8"), filename=str(ROUTES_PATH))

    assert _module_imports_name(
        routes_tree,
        "session",
        "accept_turn",
        "_session_accept_turn",
    )
    assert _module_imports_name(
        routes_tree,
        "session",
        "reject_turn",
        "_session_reject_turn",
    )

    for public_name, private_name in [
        ("accept_turn", "_session_accept_turn"),
        ("reject_turn", "_session_reject_turn"),
    ]:
        wrapper = next(
            node
            for node in routes_tree.body
            if isinstance(node, ast.FunctionDef) and node.name == public_name
        )
        assert len(wrapper.body) == 1
        statement = wrapper.body[0]
        assert isinstance(statement, ast.Return)
        assert isinstance(statement.value, ast.Call)
        assert isinstance(statement.value.func, ast.Name)
        assert statement.value.func.id == private_name
        assert [arg.arg for arg in wrapper.args.args] == []
        assert wrapper.args.vararg is not None
        assert wrapper.args.vararg.arg == "args"
        assert wrapper.args.kwarg is not None
        assert wrapper.args.kwarg.arg == "kwargs"
        assert len(statement.value.args) == 1
        assert isinstance(statement.value.args[0], ast.Starred)
        assert isinstance(statement.value.args[0].value, ast.Name)
        assert statement.value.args[0].value.id == "args"
        assert len(statement.value.keywords) == 1
        assert statement.value.keywords[0].arg is None
        assert isinstance(statement.value.keywords[0].value, ast.Name)
        assert statement.value.keywords[0].value.id == "kwargs"
