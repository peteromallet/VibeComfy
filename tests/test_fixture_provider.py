"""Tests for the fixture-backed Arnold runtime provider.

These tests exercise every entry point (readiness, v1, delta, batch_repl)
against the committed editor-session fixtures.  They do *not* require any
credentials, production provider changes, or a running ComfyUI.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from vibecomfy.comfy_nodes.agent import fixture_provider


# ── helpers ──────────────────────────────────────────────────────────────────

def _fixture_root() -> Path:
    """Resolve the fixture root the same way the provider does."""
    repo = os.environ.get("REPO_ROOT") or str(Path(__file__).resolve().parents[2])
    return Path(repo) / "tests" / "fixtures" / "editor_sessions"


def _assert_has_fixtures() -> None:
    """Skip if the fixture tree is missing."""
    manifest = _fixture_root() / "manifest.json"
    if not manifest.is_file():
        pytest.skip("Fixture tree not available (run tests from repo root or set REPO_ROOT)")


# ── readiness ────────────────────────────────────────────────────────────────

def test_readiness_returns_ready_without_credentials() -> None:
    """readiness() should report ready=True without any provider keys."""
    _assert_has_fixtures()
    result = fixture_provider.readiness(route="deepseek", model="agent-edit")
    assert isinstance(result, dict)
    assert result["ready"] is True
    assert "fixture_provider" in result.get("backend", "")
    assert result.get("route") == "deepseek"
    assert result.get("model") == "agent-edit"
    assert isinstance(result.get("fixture_count"), int)
    assert result["fixture_count"] > 0
    assert "reason" in result


def test_readiness_accepts_none_model() -> None:
    _assert_has_fixtures()
    result = fixture_provider.readiness(route="arnold")
    assert result["ready"] is True
    assert result["model"] == "agent-edit"


def test_readiness_works_when_fixture_tree_is_empty(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """readiness() should still return ready=True when manifest is empty."""
    empty = tmp_path / "empty_sessions"
    empty.mkdir()
    (empty / "manifest.json").write_text("{}")
    monkeypatch.setattr(fixture_provider, "_FIXTURE_ROOT", empty)
    monkeypatch.setattr(fixture_provider, "_MANIFEST_CACHE", None)
    monkeypatch.setattr(fixture_provider, "_CONTENT_CACHE", {})
    result = fixture_provider.readiness(route="arnold")
    assert result["ready"] is True
    assert result["fixture_count"] == 0


# ── get_agent_status ─────────────────────────────────────────────────────────

def test_get_agent_status_wraps_readiness() -> None:
    _assert_has_fixtures()
    result = fixture_provider.get_agent_status(route="deepseek")
    assert result["ok"] is True
    assert result["readiness"] == "ready"
    assert "detail" in result
    assert "fixture_count" in result


# ── run_agent_turn (v1) ──────────────────────────────────────────────────────

def test_run_agent_turn_returns_valid_envelope() -> None:
    """v1 should return a content string that parses as valid JSON with
    `python` and `message` keys."""
    _assert_has_fixtures()
    result = fixture_provider.run_agent_turn(
        task="Bypass the video VAE decode",
        python_source="",
        route="deepseek",
    )
    assert isinstance(result, dict)
    assert "content" in result
    # The content must be valid JSON with `python` and `message` keys
    inner = json.loads(result["content"])
    assert "python" in inner
    assert "message" in inner
    assert isinstance(inner["python"], str)
    assert isinstance(inner["message"], str)
    assert len(inner["message"]) > 0


def test_run_agent_turn_synthesizes_when_no_fixture_matches(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """When no fixture matches, a synthetic response is returned."""
    empty = tmp_path / "empty_sessions"
    empty.mkdir()
    (empty / "manifest.json").write_text("{}")
    monkeypatch.setattr(fixture_provider, "_FIXTURE_ROOT", empty)
    monkeypatch.setattr(fixture_provider, "_MANIFEST_CACHE", None)
    monkeypatch.setattr(fixture_provider, "_CONTENT_CACHE", {})
    result = fixture_provider.run_agent_turn(
        task="completely unknown task",
        python_source="x = 1",
        route="arnold",
    )
    inner = json.loads(result["content"])
    assert inner["python"] == ""
    assert "done()" not in inner["message"]  # prose only, no fence


# ── run_agent_turn_delta ─────────────────────────────────────────────────────

def test_run_agent_turn_delta_returns_delta_and_message() -> None:
    _assert_has_fixtures()
    result = fixture_provider.run_agent_turn_delta(
        task="Bypass the video VAE decode",
        projection="{}",
        op_schema={},
        route="deepseek",
    )
    assert isinstance(result, dict)
    assert "delta" in result
    assert "message" in result
    assert isinstance(result["delta"], list)
    assert isinstance(result["message"], str)
    assert len(result["message"]) > 0


def test_run_agent_turn_delta_synthesizes_when_no_fixture_matches(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    empty = tmp_path / "empty_sessions"
    empty.mkdir()
    (empty / "manifest.json").write_text("{}")
    monkeypatch.setattr(fixture_provider, "_FIXTURE_ROOT", empty)
    monkeypatch.setattr(fixture_provider, "_MANIFEST_CACHE", None)
    monkeypatch.setattr(fixture_provider, "_CONTENT_CACHE", {})
    result = fixture_provider.run_agent_turn_delta(
        task="unknown",
        projection="{}",
        op_schema={},
        route="arnold",
    )
    assert result["delta"] == []
    assert len(result["message"]) > 0


# ── run_agent_turn_batch ─────────────────────────────────────────────────────

def test_run_agent_turn_batch_returns_content_with_batch_fence() -> None:
    """The primary protocol: returns content with exactly one ```batch block."""
    _assert_has_fixtures()
    result = fixture_provider.run_agent_turn_batch(
        task="Bypass the video VAE decode node and instead wire",
        route="deepseek",
    )
    assert isinstance(result, dict)
    assert "content" in result
    content = result["content"]
    assert isinstance(content, str)
    # Must contain a ```batch fence
    assert "```batch" in content
    # Must have a closing fence
    assert content.count("```batch") == 1


def test_run_agent_turn_batch_matches_by_substring() -> None:
    """A task that contains the task_preview text should match."""
    _assert_has_fixtures()
    result = fixture_provider.run_agent_turn_batch(
        task="Bypass the video VAE decode node",
        route="deepseek",
    )
    assert "```batch" in result["content"]


def test_run_agent_turn_batch_falls_back_to_first_fixture() -> None:
    """A completely unrecognized task gets the first available fixture."""
    _assert_has_fixtures()
    result = fixture_provider.run_agent_turn_batch(
        task="zzz_unrecognizable_task_xyz",
        route="arnold",
    )
    assert "```batch" in result["content"]


def test_run_agent_turn_batch_synthesizes_when_no_fixtures_exist(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    empty = tmp_path / "empty_sessions"
    empty.mkdir()
    (empty / "manifest.json").write_text("{}")
    monkeypatch.setattr(fixture_provider, "_FIXTURE_ROOT", empty)
    monkeypatch.setattr(fixture_provider, "_MANIFEST_CACHE", None)
    monkeypatch.setattr(fixture_provider, "_CONTENT_CACHE", {})
    result = fixture_provider.run_agent_turn_batch(
        task="anything",
        route="arnold",
    )
    assert "```batch" in result["content"]
    assert "done()" in result["content"]


# ── explicit missing-key errors ─────────────────────────────────────────────

def test_missing_fixture_key_does_not_crash() -> None:
    """Requesting a non-existent fixture key is handled gracefully.
    
    When the forced scenario doesn't exist, the provider falls through
    to substring/fallback matching instead of crashing.  The response is
    always a well-formed batch-repl envelope.
    """
    _assert_has_fixtures()
    os.environ["VIBECOMFY_FIXTURE_SCENARIO"] = "nonexistent_session_xyz"
    try:
        result = fixture_provider.run_agent_turn_batch(
            task="any task",
            route="arnold",
        )
        # Should not crash — falls through to substring/fallback match
        assert "```batch" in result["content"]
        assert "```" in result["content"]
    finally:
        os.environ.pop("VIBECOMFY_FIXTURE_SCENARIO", None)


def test_env_var_forces_specific_scenario() -> None:
    """VIBECOMFY_FIXTURE_SCENARIO forces a specific session's fixture."""
    _assert_has_fixtures()
    os.environ["VIBECOMFY_FIXTURE_SCENARIO"] = "smoke_upscale_1"
    try:
        result = fixture_provider.run_agent_turn_batch(
            task="irrelevant task text",
            route="arnold",
        )
        assert "ImageScaleBy" in result["content"]
    finally:
        os.environ.pop("VIBECOMFY_FIXTURE_SCENARIO", None)


def test_all_entry_points_accept_keyword_messages() -> None:
    """All four entry points accept `messages` without crashing."""
    _assert_has_fixtures()
    sample_messages = [
        {"role": "system", "content": "You are an agent."},
        {"role": "user", "content": "Bypass the video VAE decode node."},
    ]

    r1 = fixture_provider.readiness(route="deepseek")
    assert r1["ready"] is True

    r2 = fixture_provider.run_agent_turn(
        task="Bypass the video VAE decode",
        python_source="",
        route="deepseek",
        messages=sample_messages,
    )
    assert "content" in r2

    r3 = fixture_provider.run_agent_turn_delta(
        task="Bypass the video VAE decode",
        projection="{}",
        op_schema={},
        route="deepseek",
        messages=sample_messages,
    )
    assert "delta" in r3

    r4 = fixture_provider.run_agent_turn_batch(
        task="Bypass the video VAE decode",
        route="deepseek",
        messages=sample_messages,
    )
    assert "content" in r4


def test_no_credentials_or_env_keys_required() -> None:
    """The fixture provider does not read any credential env vars."""
    _assert_has_fixtures()
    # Temporarily unset any credential env vars to prove they aren't needed
    saved = {}
    for var in ("DEEPSEEK_API_KEY", "ARNOLD_API_KEY", "HERMES_API_KEY",
                "ANTHROPIC_API_KEY", "OPENAI_API_KEY"):
        saved[var] = os.environ.pop(var, None)

    try:
        result = fixture_provider.readiness(route="deepseek")
        assert result["ready"] is True
        result2 = fixture_provider.run_agent_turn_batch(
            task="Bypass the video VAE decode node",
            route="deepseek",
        )
        assert "```batch" in result2["content"]
    finally:
        for var, val in saved.items():
            if val is not None:
                os.environ[var] = val
            else:
                os.environ.pop(var, None)


# ── REPO_ROOT fallback ──────────────────────────────────────────────────────

def test_repo_root_fallback_uses_file_location() -> None:
    """When REPO_ROOT is not set, the provider falls back to walking up from
    __file__."""
    saved = os.environ.pop("REPO_ROOT", None)
    try:
        # This should not crash — it resolves from __file__
        root = fixture_provider._repo_root()
        assert root.is_dir()
    finally:
        if saved is not None:
            os.environ["REPO_ROOT"] = saved


def test_repo_root_env_var_takes_priority(tmp_path: Path) -> None:
    """When REPO_ROOT is set, it is used directly."""
    os.environ["REPO_ROOT"] = str(tmp_path)
    try:
        root = fixture_provider._repo_root()
        assert root == tmp_path
    finally:
        os.environ.pop("REPO_ROOT", None)
