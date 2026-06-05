from __future__ import annotations

import json
from pathlib import Path

import pytest

from vibecomfy.cli import build_parser


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
    graph_before = {
        "nodes": [
            {
                "id": 1,
                "type": "CheckpointLoaderSimple",
                "pos": [1, 2],
                "properties": {"vibecomfy_uid": "old"},
            }
        ]
    }
    graph_after = {
        "nodes": [
            {
                "id": 1,
                "type": "CheckpointLoaderSimple",
                "pos": [9, 9],
                "properties": {"vibecomfy_uid": "new"},
            },
            {"id": 2, "type": "KSampler"},
        ]
    }
    _write_json(turn_dir / "request.json", {"task": "make it brighter", "route": "agent-edit"})
    _write_json(
        turn_dir / "response.json",
        {
            "ok": True,
            "graph": graph_after,
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
    _write_json(turn_dir / "original.ui.json", graph_before)
    _write_json(turn_dir / "candidate.ui.json", graph_after)
    _write_json(turn_dir / "audit" / "audit.json", {"batch": "add_node KSampler", "report": "ok"})
    monkeypatch.setenv("COMFY_DIR", str(comfy))
    monkeypatch.setenv("VIBECOMFY_REPO", str(repo))
    monkeypatch.setenv("VIBECOMFY_PORT", "65530")
    return root


def _run_cli(argv: list[str]) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


def test_debug_log_json_routes_through_top_level_cli(
    editor_sessions: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert _run_cli(["debug", "log", "--json"]) == 0

    payload = json.loads(capsys.readouterr().out)
    assert len(payload) == 1
    row = payload[0]
    assert row["session"] == "abc123session"
    assert row["turn"] == "0001"
    assert row["outcome"] == "✅ APPLIED"
    assert row["task"] == "make it brighter"
    assert row["fid"] is True


def test_debug_tail_json_uses_log_shape(
    editor_sessions: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert _run_cli(["debug", "tail", "1", "--json"]) == 0

    payload = json.loads(capsys.readouterr().out)
    assert [row["turn"] for row in payload] == ["0001"]


def test_debug_turn_json_includes_uid_normalized_faithful_diff(
    editor_sessions: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert _run_cli(["debug", "turn", "abc123", "1", "--json"]) == 0

    payload = json.loads(capsys.readouterr().out)
    assert payload["session"] == "abc123session"
    assert payload["faithful"]["changed"] == []
    assert payload["faithful"]["added"] == [2]
    assert payload["faithful"]["node_types"] == {"2": "KSampler"}


def test_debug_stats_json_reports_failure_distribution(
    editor_sessions: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert _run_cli(["debug", "stats", "--json"]) == 0

    payload = json.loads(capsys.readouterr().out)
    assert payload == {
        "sessions": 1,
        "turns": 1,
        "applied_to_canvas": 1,
        "candidates_ok": 1,
        "clarify_or_noop": 0,
        "fidelity_ok": 1,
        "failures_by_kind": {},
    }


def test_debug_status_json_uses_live_status_when_reachable(
    editor_sessions: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    import vibecomfy._agent_edit_debug as debug

    monkeypatch.setattr(debug, "_listener_pid", lambda: "12345")
    monkeypatch.setattr(
        debug,
        "_fetch_runtime_status",
        lambda: (
            {
                "ok": True,
                "backend": "deepseek",
                "route": "/vibecomfy/agent/status",
                "provider_available": True,
                "credential_present": True,
                "identity": "agent",
            },
            None,
        ),
    )
    assert _run_cli(["debug", "status", "--json"]) == 0

    payload = json.loads(capsys.readouterr().out)
    assert payload["listener"]["pid"] == "12345"
    assert payload["runtime"]["ok"] is True
    assert payload["live_flags"] == {
        "route_available": True,
        "provider_available": True,
        "credential_present": True,
        "identity": "agent",
    }


def test_debug_status_json_falls_back_when_server_unreachable(
    editor_sessions: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    import vibecomfy._agent_edit_debug as debug

    monkeypatch.setenv("VIBECOMFY_AGENT_EDIT_LEGACY", "full")
    monkeypatch.setattr(debug, "_listener_pid", lambda: (None, "no lsof"))
    monkeypatch.setattr(debug, "_fetch_runtime_status", lambda: (None, "connection refused"))
    assert _run_cli(["debug", "status", "--json"]) == 0

    payload = json.loads(capsys.readouterr().out)
    assert payload["runtime"] is None
    assert payload["runtime_error"] == "connection refused"
    assert payload["env_flags"]["VIBECOMFY_AGENT_EDIT_LEGACY"] == "full"
