from __future__ import annotations

import importlib
import json
import sys
import types
from pathlib import Path
from typing import Any

import pytest

from vibecomfy.comfy_nodes.agent.routes import (
    _is_agentic_replay_enabled,
    _is_safe_replay_id,
    _list_agentic_replay_runs,
    _list_agentic_replay_tests,
    _resolve_agentic_replay_scenario,
)


@pytest.fixture
def replay_root(tmp_path: Path, monkeypatch):
    root = tmp_path / "out" / "agentic"
    root.mkdir(parents=True)
    monkeypatch.setenv("VIBECOMFY_AGENTIC_REPLAY", "1")
    monkeypatch.setattr(
        "vibecomfy.comfy_nodes.agent.routes._agentic_replay_root",
        lambda: root,
    )
    return root


def _write_replay_case(
    root: Path,
    *,
    run_id: str = "agentic-100-20260630-021138",
    test_id: str = "tts_emotion_injection",
) -> Path:
    case_dir = root / run_id / test_id
    case_dir.mkdir(parents=True)
    (case_dir / "original.ui.json").write_text(
        json.dumps({"nodes": [{"id": "orig"}], "links": []}),
        encoding="utf-8",
    )
    (case_dir / "candidate.ui.json").write_text(
        json.dumps({"nodes": [{"id": "cand"}], "links": []}),
        encoding="utf-8",
    )
    (case_dir / "response.json").write_text(
        json.dumps(
            {
                "title": "TTS emotion injection",
                "query": "Add emotion to this voiceover",
                "reply": "Updated the graph.",
                "session_id": "sess-1",
                "turn_id": "turn-1",
                "checks": [{"name": "route_shape", "status": "passed"}],
                "artifacts": {
                    "original_ui": "original.ui.json",
                    "candidate_ui": "candidate.ui.json",
                },
            }
        ),
        encoding="utf-8",
    )
    return case_dir


def test_agentic_replay_id_rejects_traversal() -> None:
    assert _is_safe_replay_id("agentic-100-20260630-021138") is True
    assert _is_safe_replay_id("") is False
    assert _is_safe_replay_id("~") is False
    assert _is_safe_replay_id("~/escape") is False
    assert _is_safe_replay_id("../escape") is False
    assert _is_safe_replay_id("run/test") is False
    assert _is_safe_replay_id(".hidden") is False


def test_agentic_replay_routes_are_gated(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.delenv("VIBECOMFY_AGENTIC_REPLAY", raising=False)
    monkeypatch.setattr(
        "vibecomfy.comfy_nodes.agent.routes._agentic_replay_root",
        lambda: tmp_path / "out" / "agentic",
    )

    assert _is_agentic_replay_enabled() is False
    for result, status in (
        _list_agentic_replay_runs(),
        _list_agentic_replay_tests("agentic-100"),
        _resolve_agentic_replay_scenario("agentic-100", "case"),
    ):
        assert status == 404
        assert result == {"ok": False, "error": "Not found"}


def test_agentic_replay_lists_runs_and_tests(replay_root: Path) -> None:
    _write_replay_case(replay_root)

    runs, run_status = _list_agentic_replay_runs()
    assert run_status == 200
    assert runs == {
        "ok": True,
        "runs": [
            {
                "run_id": "agentic-100-20260630-021138",
                "label": "agentic-100-20260630-021138",
            }
        ],
    }

    tests, test_status = _list_agentic_replay_tests("agentic-100-20260630-021138")
    assert test_status == 200
    assert tests["ok"] is True
    assert tests["run_id"] == "agentic-100-20260630-021138"
    assert tests["tests"] == [
        {
            "test_id": "tts_emotion_injection",
            "label": "TTS emotion injection",
            "query": "Add emotion to this voiceover",
        }
    ]


def test_agentic_replay_scenario_projection(replay_root: Path) -> None:
    _write_replay_case(replay_root)

    result, status = _resolve_agentic_replay_scenario(
        "agentic-100-20260630-021138",
        "tts_emotion_injection",
    )

    assert status == 200
    assert result["ok"] is True
    assert result["run_id"] == "agentic-100-20260630-021138"
    assert result["test_id"] == "tts_emotion_injection"
    assert result["status"] == "ready"
    assert result["checks"] == [{"name": "route_shape", "status": "passed"}]
    assert result["query"] == "Add emotion to this voiceover"
    assert result["agent_reply"] == "Updated the graph."
    assert result["session_id"] == "sess-1"
    assert result["turn_id"] == "turn-1"
    assert result["original_graph"]["nodes"][0]["id"] == "orig"
    assert result["candidate_graph"]["nodes"][0]["id"] == "cand"
    assert [stage["id"] for stage in result["stages"]] == [
        "sent",
        "thinking",
        "ready_to_apply",
        "applied",
    ]
    assert result["stages"][2]["candidate_graph"] == result["candidate_graph"]


def test_agentic_replay_missing_artifacts_returns_user_facing_status(replay_root: Path) -> None:
    case_dir = _write_replay_case(replay_root, test_id="missing_candidate")
    (case_dir / "candidate.ui.json").unlink()

    result, status = _resolve_agentic_replay_scenario(
        "agentic-100-20260630-021138",
        "missing_candidate",
    )

    assert status == 200
    assert result["ok"] is False
    assert result["status"] == "missing"
    assert result["missing_artifacts"] == ["candidate_graph"]
    assert "candidate_graph" in result["error"]
    assert [stage["id"] for stage in result["stages"]] == [
        "sent",
        "thinking",
        "missing_artifacts",
    ]


def test_agentic_replay_scenario_rejects_unsafe_ids(replay_root: Path) -> None:
    result, status = _resolve_agentic_replay_scenario("../escape", "case")
    assert status == 400
    assert result["ok"] is False


def test_agentic_replay_http_routes_are_registered(monkeypatch, replay_root: Path) -> None:
    _write_replay_case(replay_root)
    routes = importlib.import_module("vibecomfy.comfy_nodes.agent.routes")
    registered: dict[tuple[str, str], Any] = {}

    class _Routes:
        def post(self, path: str):
            def _decorator(fn):
                registered[("POST", path)] = fn
                return fn

            return _decorator

        def get(self, path: str):
            def _decorator(fn):
                registered[("GET", path)] = fn
                return fn

            return _decorator

    real_aiohttp = sys.modules.get("aiohttp")
    aiohttp_module = types.ModuleType("aiohttp")
    aiohttp_module.web = types.SimpleNamespace(
        json_response=lambda body, status=200: {"status": status, "body": body},
    )
    monkeypatch.setitem(sys.modules, "aiohttp", aiohttp_module)

    class _Request:
        query = {}

        def __init__(self, match_info: dict[str, str] | None = None) -> None:
            self.match_info = match_info or {}

    try:
        routes.register_agent_edit_routes(types.SimpleNamespace(routes=_Routes()))
        runs_response = routes.asyncio.run(
            registered[("GET", "/vibecomfy/agentic-replay/runs")](_Request())
        )
        tests_response = routes.asyncio.run(
            registered[("GET", "/vibecomfy/agentic-replay/runs/{run_id}/tests")](
                _Request({"run_id": "agentic-100-20260630-021138"})
            )
        )
        scenario_response = routes.asyncio.run(
            registered[("GET", "/vibecomfy/agentic-replay/runs/{run_id}/tests/{test_id}")](
                _Request(
                    {
                        "run_id": "agentic-100-20260630-021138",
                        "test_id": "tts_emotion_injection",
                    }
                )
            )
        )
    finally:
        if real_aiohttp is not None:
            sys.modules["aiohttp"] = real_aiohttp
        else:
            sys.modules.pop("aiohttp", None)

    assert runs_response["status"] == 200
    assert runs_response["body"]["runs"][0]["run_id"] == "agentic-100-20260630-021138"
    assert tests_response["status"] == 200
    assert tests_response["body"]["tests"][0]["test_id"] == "tts_emotion_injection"
    assert scenario_response["status"] == 200
    assert scenario_response["body"]["candidate_graph"]["nodes"][0]["id"] == "cand"
