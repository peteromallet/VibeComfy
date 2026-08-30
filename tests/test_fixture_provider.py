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
    repo = (
        os.environ.get("VIBECOMFY_FIXTURE_DIR")
        or os.environ.get("REPO_ROOT")
        or str(Path(__file__).resolve().parents[2])
    )
    if os.environ.get("VIBECOMFY_FIXTURE_DIR"):
        return Path(repo)
    return Path(repo) / "tests" / "fixtures" / "editor_sessions"


def _assert_has_fixtures() -> None:
    """Skip if the fixture tree is missing."""
    manifest = _fixture_root() / "manifest.json"
    if not manifest.is_file():
        pytest.skip("Fixture tree not available (run tests from repo root or set REPO_ROOT)")


def _write_fixture(
    root: Path,
    *,
    key: str = "fixture-key",
    session: str = "session",
    turn: str = "0001",
    task: str = "known task",
    content: object = "ok\n```batch\ndone()\n```",
    metadata: dict[str, object] | None = None,
) -> dict[str, str]:
    task_hash = fixture_provider._compute_key(task)
    entry = {
        "session": session,
        "turn": turn,
        "task_preview": task,
        "task_hash": task_hash,
    }
    root.mkdir(parents=True, exist_ok=True)
    (root / "manifest.json").write_text(json.dumps({key: entry}))
    fixture = root / key
    fixture.mkdir()
    fixture_meta = {
        "key": key,
        "session": session,
        "turn": turn,
        "task_hash": task_hash,
    }
    if metadata:
        fixture_meta.update(metadata)
    (fixture / "fixture.json").write_text(
        json.dumps({"content": content, "_meta": fixture_meta})
    )
    (fixture / "request.json").write_text(json.dumps({"task": task}))
    return {"key": key, "session": session, "task": task}


def _reset_fixture_caches(monkeypatch: pytest.MonkeyPatch, root: Path) -> None:
    monkeypatch.setattr(fixture_provider, "_FIXTURE_ROOT", root)
    monkeypatch.setattr(fixture_provider, "_MANIFEST_CACHE", None)
    monkeypatch.setattr(fixture_provider, "_MANIFEST_ERROR", None)
    monkeypatch.setattr(fixture_provider, "_MANIFEST_CACHE_ROOT", None)
    monkeypatch.setattr(fixture_provider, "_CONTENT_CACHE", {})
    monkeypatch.setattr(fixture_provider, "_METADATA_CACHE", {})
    monkeypatch.setattr(fixture_provider, "_DOCUMENT_CACHE", {})
    monkeypatch.setattr(fixture_provider, "_DOCUMENT_CACHE_ROOT", None)


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


def test_readiness_rejects_empty_fixture_tree(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """An empty corpus is unavailable, never a ready synthetic backend."""
    empty = tmp_path / "empty_sessions"
    empty.mkdir()
    (empty / "manifest.json").write_text("{}")
    monkeypatch.setattr(fixture_provider, "_FIXTURE_ROOT", empty)
    monkeypatch.setattr(fixture_provider, "_MANIFEST_CACHE", None)
    monkeypatch.setattr(fixture_provider, "_CONTENT_CACHE", {})
    result = fixture_provider.readiness(route="arnold")
    assert result["ready"] is False
    assert result["ok"] is False
    assert result["error"]["kind"] == "fixture_unavailable"
    assert result["error"]["code"] == "empty_manifest"
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


def test_run_agent_turn_refuses_when_fixture_corpus_is_empty(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """v1 refuses instead of manufacturing a successful response."""
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
    assert "content" not in result
    assert result["error"]["kind"] == "fixture_unavailable"
    assert result["error"]["code"] == "empty_manifest"


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
    assert set(result) == {"delta", "message"}
    assert result.audit_metadata["fixture"]["fallback_used"] is False


def test_run_agent_turn_delta_refuses_when_fixture_corpus_is_empty(
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
    assert "delta" not in result
    assert result["error"]["kind"] == "fixture_unavailable"
    assert result["error"]["code"] == "empty_manifest"


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
    assert result["fixture"]["match_kind"] in {"hash", "substring"}
    assert result["fallback_used"] is False


def test_committed_manifest_task_hash_selects_exact_fixture() -> None:
    """The corpus' documented task-only hash path is exercised, not dead code."""
    _assert_has_fixtures()
    result = fixture_provider.run_agent_turn_batch(
        task=(
            "Bypass the video VAE decode node and instead wire the video save node's "
            "images input directly from whatever feeds the decode (rewire around the "
            "bypassed node)."
        ),
        route="arnold",
    )
    assert result["fixture"]["match_kind"] == "hash"
    assert result["fixture"]["key"] == "66e9a889a48d5f60"


def test_run_agent_turn_batch_matches_by_substring() -> None:
    """A task that contains the task_preview text should match."""
    _assert_has_fixtures()
    result = fixture_provider.run_agent_turn_batch(
        task="Bypass the video VAE decode node",
        route="deepseek",
    )
    assert "```batch" in result["content"]
    assert result["fixture"]["match_kind"] == "substring"
    assert result["fixture"]["key"]
    assert result["fallback_used"] is False


def test_run_agent_turn_batch_falls_back_to_first_fixture() -> None:
    """An unforced, unrecognized task uses the documented generic fallback."""
    _assert_has_fixtures()
    result = fixture_provider.run_agent_turn_batch(
        task="zzz_unrecognizable_task_xyz",
        route="arnold",
    )
    assert "```batch" in result["content"]
    assert result["fixture"]["match_kind"] == "fallback"
    assert result["fixture"]["key"]
    assert result["fallback_used"] is True


def test_run_agent_turn_batch_refuses_when_no_fixtures_exist(
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
    assert result["content"] == ""
    assert result["fixture"]["match_kind"] == "unavailable"
    assert result["fallback_used"] is False
    assert result["error"]["kind"] == "fixture_unavailable"
    assert result["error"]["code"] == "empty_manifest"


# ── explicit missing-key errors ─────────────────────────────────────────────

def test_missing_fixture_key_fails_closed_with_actionable_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A missing forced selector must never select another fixture."""
    _assert_has_fixtures()
    monkeypatch.setenv("VIBECOMFY_FIXTURE_SCENARIO", "nonexistent_session_xyz")
    result = fixture_provider.run_agent_turn_batch(task="any task", route="arnold")
    assert result["fixture"]["match_kind"] == "forced_missing"
    assert result["fallback_used"] is False
    assert result["fixture"]["key"] is None
    assert result["error"]["kind"] == "fixture_not_found"
    assert result["error"]["code"] == "forced_scenario_not_found"
    assert "nonexistent_session_xyz" in result["error"]["message"]
    assert "```batch" not in result["content"]
    assert "done()" not in result["content"]


def test_missing_forced_fixture_remains_typed_through_batch_provider(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The composed provider preserves the refusal instead of a fence parse error."""
    _assert_has_fixtures()
    monkeypatch.setenv("VIBECOMFY_FIXTURE_SCENARIO", "nonexistent_session_xyz")
    from vibecomfy.comfy_nodes.agent import provider

    raw = fixture_provider.run_agent_turn_batch(task="any task", route="arnold")
    with pytest.raises(provider.ProviderError, match="Fixture provider refused") as exc_info:
        provider._normalize_batch_response(raw, route="arnold", model="agent-edit")
    assert exc_info.value.fixture_error["code"] == "forced_scenario_not_found"
    assert exc_info.value.fixture["fallback_used"] is False


def test_forced_fixture_manifest_drift_fails_closed(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """A manifest entry without readable content is also a hard refusal."""
    root = tmp_path / "sessions"
    root.mkdir()
    key = "deadbeefdeadbeef"
    task_hash = fixture_provider._compute_key("known")
    (root / "manifest.json").write_text(
        json.dumps(
            {
                key: {
                    "session": "drifted_session",
                    "turn": "0001",
                    "task_preview": "known",
                    "task_hash": task_hash,
                }
            }
        )
    )
    fixture = root / key
    fixture.mkdir()
    (fixture / "fixture.json").write_text(
        json.dumps(
            {
                "_meta": {
                    "key": key,
                    "session": "drifted_session",
                    "turn": "0001",
                    "task_hash": task_hash,
                }
            }
        )
    )
    (fixture / "request.json").write_text(json.dumps({"task": "known"}))
    monkeypatch.setattr(fixture_provider, "_FIXTURE_ROOT", root)
    monkeypatch.setattr(fixture_provider, "_MANIFEST_CACHE", None)
    monkeypatch.setattr(fixture_provider, "_CONTENT_CACHE", {})
    monkeypatch.setenv("VIBECOMFY_FIXTURE_SCENARIO", "drifted_session")
    result = fixture_provider.run_agent_turn_batch(task="known", route="arnold")
    assert result["fixture"]["match_kind"] in {"corrupt", "forced_missing"}
    assert result["fixture"]["key"] == key
    assert result["error"]["code"] == "fixture_content_missing"
    assert result["fallback_used"] is False


@pytest.mark.parametrize("entrypoint", ["v1", "delta", "batch"])
@pytest.mark.parametrize("bad_content", [True, 1, [], {}])
def test_non_string_fixture_content_is_typed_corruption(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    entrypoint: str,
    bad_content: object,
) -> None:
    """Every protocol refuses truthy JSON values that are not fixture text."""
    root = tmp_path / "sessions"
    _write_fixture(root, content=bad_content)
    _reset_fixture_caches(monkeypatch, root)
    monkeypatch.setenv("VIBECOMFY_FIXTURE_SCENARIO", "session")
    if entrypoint == "v1":
        result = fixture_provider.run_agent_turn(task="ignored", python_source="", route="arnold")
    elif entrypoint == "delta":
        result = fixture_provider.run_agent_turn_delta(
            task="ignored", projection="{}", op_schema={}, route="arnold"
        )
    else:
        result = fixture_provider.run_agent_turn_batch(task="ignored", route="arnold")
    assert result["error"]["kind"] == "fixture_corruption"
    assert result["error"]["code"] == "fixture_content_invalid"
    assert result["fixture"]["match_kind"] in {"corrupt", "forced_missing"}
    assert result["fallback_used"] is False


@pytest.mark.parametrize("entrypoint", ["v1", "delta", "batch"])
def test_fence_less_fixture_content_is_typed_corruption(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    entrypoint: str,
) -> None:
    """Every protocol rejects a text fixture without its required batch fence."""
    root = tmp_path / "sessions"
    _write_fixture(root, content="prose without a batch fence")
    _reset_fixture_caches(monkeypatch, root)
    monkeypatch.setenv("VIBECOMFY_FIXTURE_SCENARIO", "session")
    if entrypoint == "v1":
        result = fixture_provider.run_agent_turn(task="ignored", python_source="", route="arnold")
    elif entrypoint == "delta":
        result = fixture_provider.run_agent_turn_delta(
            task="ignored", projection="{}", op_schema={}, route="arnold"
        )
    else:
        result = fixture_provider.run_agent_turn_batch(task="ignored", route="arnold")
    assert result["error"]["kind"] == "fixture_corruption"
    assert result["error"]["code"] == "fixture_fence_invalid"
    assert result["fixture"]["match_kind"] == "forced_missing"


def test_unforced_corrupt_fixture_never_falls_back_to_valid_shape(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Manual fallback also refuses corrupt content with provenance."""
    root = tmp_path / "sessions"
    _write_fixture(root, content="prose without a batch fence")
    _reset_fixture_caches(monkeypatch, root)
    monkeypatch.delenv("VIBECOMFY_FIXTURE_SCENARIO", raising=False)
    result = fixture_provider.run_agent_turn_batch(task="unrecognized", route="arnold")
    assert result["error"]["kind"] == "fixture_corruption"
    assert result["error"]["code"] == "fixture_fence_invalid"
    assert result["fixture"]["match_kind"] == "corrupt"
    assert result["fallback_used"] is False


@pytest.mark.parametrize("fixture_key", ["../outside", "/tmp/outside", "nested/id", "nested\\id"])
def test_unsafe_manifest_fixture_keys_fail_closed(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    fixture_key: str,
) -> None:
    root = tmp_path / "sessions"
    root.mkdir()
    (root / "manifest.json").write_text(
        json.dumps(
            {
                fixture_key: {
                    "session": "session",
                    "turn": "0001",
                    "task_preview": "known task",
                    "task_hash": fixture_provider._compute_key("known task"),
                }
            }
        )
    )
    _reset_fixture_caches(monkeypatch, root)
    monkeypatch.setenv("VIBECOMFY_FIXTURE_SCENARIO", "session")
    result = fixture_provider.run_agent_turn_batch(task="known task", route="arnold")
    assert result["error"]["kind"] == "fixture_corruption"
    assert result["error"]["code"] == "manifest_key_unsafe"
    assert result["fixture"]["match_kind"] == "manifest_invalid"
    assert result["fallback_used"] is False


@pytest.mark.parametrize("symlink_target", ["directory", "fixture.json"])
def test_fixture_symlink_escape_fails_closed(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    symlink_target: str,
) -> None:
    root = tmp_path / "sessions"
    outside = tmp_path / "outside"
    outside.mkdir()
    key = "escape"
    task = "known task"
    entry = {
        "session": "session",
        "turn": "0001",
        "task_preview": task,
        "task_hash": fixture_provider._compute_key(task),
    }
    (root / "manifest.json").parent.mkdir(parents=True)
    (root / "manifest.json").write_text(json.dumps({key: entry}))
    outside_fixture = outside / "fixture.json"
    outside_fixture.write_text(
        json.dumps(
            {
                "content": "outside\n```batch\ndone()\n```",
                "_meta": {
                    "key": key,
                    "session": "session",
                    "turn": "0001",
                    "task_hash": fixture_provider._compute_key(task),
                },
            }
        )
    )
    if symlink_target == "directory":
        (root / key).symlink_to(outside, target_is_directory=True)
    else:
        fixture = root / key
        fixture.mkdir()
        (fixture / "fixture.json").symlink_to(outside_fixture)
        (fixture / "request.json").write_text(json.dumps({"task": task}))
    _reset_fixture_caches(monkeypatch, root)
    monkeypatch.setenv("VIBECOMFY_FIXTURE_SCENARIO", "session")
    result = fixture_provider.run_agent_turn_batch(task=task, route="arnold")
    assert result["error"]["kind"] == "fixture_corruption"
    assert result["error"]["code"] in {"fixture_metadata_missing", "fixture_request_missing"}
    assert result["fixture"]["fallback_used"] is False


@pytest.mark.parametrize("fixture_document", [None, [], "fixture", 1, True])
def test_non_object_fixture_json_is_typed_corruption(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    fixture_document: object,
) -> None:
    root = tmp_path / "sessions"
    _write_fixture(root)
    (root / "fixture-key" / "fixture.json").write_text(json.dumps(fixture_document))
    _reset_fixture_caches(monkeypatch, root)
    monkeypatch.setenv("VIBECOMFY_FIXTURE_SCENARIO", "session")
    result = fixture_provider.run_agent_turn_batch(task="known task", route="arnold")
    assert result["error"]["kind"] == "fixture_corruption"
    assert result["error"]["code"] == "fixture_metadata_missing"
    assert result["fixture"]["match_kind"] == "forced_missing"


@pytest.mark.parametrize(
    "content",
    [
        "prose\n```batch\ndone()\n```\n```batch",
        "prose\n```batch\ndone()\n```\n```",
        "prose\n```batch\ndone()\n```\n```python\nextra\n```",
    ],
)
def test_extra_or_unmatched_batch_fence_markers_fail_closed(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    content: str,
) -> None:
    root = tmp_path / "sessions"
    _write_fixture(root, content=content)
    _reset_fixture_caches(monkeypatch, root)
    monkeypatch.setenv("VIBECOMFY_FIXTURE_SCENARIO", "session")
    result = fixture_provider.run_agent_turn_batch(task="known task", route="arnold")
    assert result["error"]["kind"] == "fixture_corruption"
    assert result["error"]["code"] == "fixture_fence_invalid"
    assert result["fallback_used"] is False


def test_duplicate_committed_task_hash_refuses_without_context() -> None:
    _assert_has_fixtures()
    result = fixture_provider.run_agent_turn_batch(task="switch to SDXL", route="arnold")
    assert result["error"]["kind"] == "fixture_ambiguous"
    assert result["error"]["code"] == "ambiguous_task_hash"
    assert len(result["error"]["fixture_keys"]) > 1
    assert result["fixture"]["match_kind"] == "ambiguous"
    assert result["fallback_used"] is False


@pytest.mark.parametrize("manifest_text", ["{", "null", "[]", '"manifest"'])
def test_readiness_reports_typed_manifest_corruption(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    manifest_text: str,
) -> None:
    root = tmp_path / "sessions"
    root.mkdir()
    (root / "manifest.json").write_text(manifest_text)
    _reset_fixture_caches(monkeypatch, root)
    result = fixture_provider.readiness(route="arnold")
    assert result["ready"] is False
    assert result["ok"] is False
    assert result["error"]["kind"] == "fixture_corruption"
    assert result["error"]["code"] in {"manifest_unreadable", "manifest_not_object"}


def test_readiness_reports_corrupt_manifest_entry_and_fixture_identity(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    root = tmp_path / "sessions"
    _write_fixture(root, metadata={"session": "wrong"})
    _reset_fixture_caches(monkeypatch, root)
    result = fixture_provider.readiness(route="arnold")
    assert result["ready"] is False
    assert result["error"]["kind"] == "fixture_corruption"
    assert result["error"]["code"] == "fixture_identity_mismatch"

    invalid = tmp_path / "invalid"
    invalid.mkdir()
    (invalid / "manifest.json").write_text(json.dumps({"key": None}))
    _reset_fixture_caches(monkeypatch, invalid)
    result = fixture_provider.readiness(route="arnold")
    assert result["ready"] is False
    assert result["error"]["code"] == "manifest_entry_not_object"


@pytest.mark.parametrize("manifest_value", [None, [], "manifest", 1, True])
@pytest.mark.parametrize("forced", [False, True])
def test_non_object_manifest_is_typed_corruption(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    manifest_value: object,
    forced: bool,
) -> None:
    """Null/list/scalar manifests refuse in both manual and forced paths."""
    root = tmp_path / "sessions"
    root.mkdir()
    (root / "manifest.json").write_text(json.dumps(manifest_value))
    _reset_fixture_caches(monkeypatch, root)
    if forced:
        monkeypatch.setenv("VIBECOMFY_FIXTURE_SCENARIO", "session")
    result = fixture_provider.run_agent_turn_batch(task="anything", route="arnold")
    assert result["error"]["kind"] == "fixture_corruption"
    assert result["error"]["code"] == "manifest_not_object"
    assert result["fixture"]["match_kind"] == "manifest_invalid"
    assert result["fallback_used"] is False


@pytest.mark.parametrize(
    ("entry", "code"),
    [
        (None, "manifest_entry_not_object"),
        ([], "manifest_entry_not_object"),
        ({"session": 1, "turn": "0001", "task_preview": "x"}, "manifest_session_invalid"),
        ({"session": "s", "turn": 1, "task_preview": "x"}, "malformed_turn"),
        ({"session": "s", "turn": "0001", "task_preview": []}, "manifest_task_preview_invalid"),
        (
            {"session": "s", "turn": "0001", "task_preview": "x", "task_hash": 1},
            "manifest_task_hash_invalid",
        ),
    ],
)
def test_malformed_manifest_entry_is_typed_corruption(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    entry: object,
    code: str,
) -> None:
    root = tmp_path / "sessions"
    root.mkdir()
    (root / "manifest.json").write_text(json.dumps({"key": entry}))
    _reset_fixture_caches(monkeypatch, root)
    result = fixture_provider.run_agent_turn_batch(task="anything", route="arnold")
    assert result["error"]["kind"] == "fixture_corruption"
    assert result["error"]["code"] == code


@pytest.mark.parametrize("forced", [False, True])
def test_fixture_identity_and_hash_mismatch_fail_closed(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    forced: bool,
) -> None:
    """Manifest claims cannot make mismatched fixture metadata authoritative."""
    root = tmp_path / "sessions"
    key = "identity-key"
    _write_fixture(
        root,
        key=key,
        metadata={"session": "other", "task_hash": "0000000000000000"},
    )
    _reset_fixture_caches(monkeypatch, root)
    if forced:
        monkeypatch.setenv("VIBECOMFY_FIXTURE_SCENARIO", "session")
    result = fixture_provider.run_agent_turn_batch(task="known task", route="arnold")
    assert result["error"]["kind"] == "fixture_corruption"
    assert result["error"]["code"] in {
        "fixture_identity_mismatch",
        "manifest_task_hash_mismatch",
        "fixture_task_hash_mismatch",
    }
    assert result["fixture"]["match_kind"] in {"corrupt", "forced_missing"}
    assert result["fallback_used"] is False


def test_forced_fixture_empty_manifest_fails_closed(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """A forced selector cannot turn an empty fixture tree into a fake turn."""
    empty = tmp_path / "empty_sessions"
    empty.mkdir()
    (empty / "manifest.json").write_text("{}")
    monkeypatch.setattr(fixture_provider, "_FIXTURE_ROOT", empty)
    monkeypatch.setattr(fixture_provider, "_MANIFEST_CACHE", None)
    monkeypatch.setattr(fixture_provider, "_CONTENT_CACHE", {})
    monkeypatch.setenv("VIBECOMFY_FIXTURE_SCENARIO", "smoke_upscale_1")
    result = fixture_provider.run_agent_turn_batch(task="anything", route="arnold")
    assert result["error"]["code"] == "empty_manifest"
    assert result["fixture"]["match_kind"] == "forced_missing"
    assert result["content"] == ""


def test_env_var_forces_specific_scenario(monkeypatch: pytest.MonkeyPatch) -> None:
    """VIBECOMFY_FIXTURE_SCENARIO forces a specific session's fixture."""
    _assert_has_fixtures()
    monkeypatch.setenv("VIBECOMFY_FIXTURE_SCENARIO", "smoke_upscale_1")
    result = fixture_provider.run_agent_turn_batch(
        task="irrelevant task text",
        route="arnold",
    )
    assert "ImageScaleBy" in result["content"]
    assert result["fixture"]["session"] == "smoke_upscale_1"
    assert result["fixture"]["match_kind"] == "explicit"
    assert result["fallback_used"] is False


def test_forced_multi_turn_session_chooses_lowest_numeric_turn(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Forced selection is stable even when manifest rows are shuffled."""
    root = tmp_path / "sessions"
    root.mkdir()
    entries = {
        "later": {
            "session": "multi",
            "turn": "0009",
            "task_preview": "later",
            "task_hash": fixture_provider._compute_key("later"),
        },
        "first": {
            "session": "multi",
            "turn": "0001",
            "task_preview": "first",
            "task_hash": fixture_provider._compute_key("first"),
        },
    }
    (root / "manifest.json").write_text(json.dumps(entries))
    for key, turn, task in (("later", "0009", "later"), ("first", "0001", "first")):
        fixture = root / key
        fixture.mkdir()
        (fixture / "fixture.json").write_text(
            json.dumps(
                {
                    "content": f"{key}\n```batch\ndone()\n```",
                    "_meta": {
                        "key": key,
                        "session": "multi",
                        "turn": turn,
                        "task_hash": fixture_provider._compute_key(task),
                    },
                }
            )
        )
        (fixture / "request.json").write_text(json.dumps({"task": task}))
    monkeypatch.setattr(fixture_provider, "_FIXTURE_ROOT", root)
    monkeypatch.setattr(fixture_provider, "_MANIFEST_CACHE", None)
    monkeypatch.setattr(fixture_provider, "_CONTENT_CACHE", {})
    monkeypatch.setattr(fixture_provider, "_METADATA_CACHE", {})
    monkeypatch.setenv("VIBECOMFY_FIXTURE_SCENARIO", "multi")
    result = fixture_provider.run_agent_turn_batch(task="irrelevant", route="arnold")
    assert result["content"].startswith("first")
    assert result["fixture"]["key"] == "first"


@pytest.mark.parametrize(
    ("entries", "code"),
    [
        (
            {"bad": {"session": "multi", "turn": "not-a-turn", "task_preview": "bad"}},
            "malformed_turn",
        ),
        (
            {
                "first": {"session": "multi", "turn": "0001", "task_preview": "first"},
                "duplicate": {"session": "multi", "turn": "1", "task_preview": "duplicate"},
            },
            "duplicate_turn",
        ),
    ],
)
def test_forced_multi_turn_manifest_anomalies_fail_closed(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    entries: dict[str, dict[str, str]],
    code: str,
) -> None:
    """Malformed or numerically duplicate turns cannot silently pick a turn."""
    root = tmp_path / "sessions"
    root.mkdir()
    (root / "manifest.json").write_text(json.dumps(entries))
    monkeypatch.setattr(fixture_provider, "_FIXTURE_ROOT", root)
    monkeypatch.setattr(fixture_provider, "_MANIFEST_CACHE", None)
    monkeypatch.setattr(fixture_provider, "_CONTENT_CACHE", {})
    monkeypatch.setattr(fixture_provider, "_METADATA_CACHE", {})
    monkeypatch.setenv("VIBECOMFY_FIXTURE_SCENARIO", "multi")
    result = fixture_provider.run_agent_turn_batch(task="irrelevant", route="arnold")
    assert result["error"]["code"] == code
    assert result["fixture"]["match_kind"] in {"forced_missing", "manifest_invalid"}
    assert result["fallback_used"] is False


def test_all_provider_entrypoints_preserve_forced_refusal(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """v1, delta, and batch callers retain the typed fixture refusal."""
    _assert_has_fixtures()
    from vibecomfy.comfy_nodes.agent import provider

    monkeypatch.setenv("VIBECOMFY_FIXTURE_SCENARIO", "nonexistent_session_xyz")
    monkeypatch.setattr(provider, "_load_arnold_runtime", lambda: fixture_provider)
    calls = [
        lambda: provider.run_agent_turn("task", "", route="arnold"),
        lambda: provider.run_agent_turn_delta("task", "{}", route="arnold"),
        lambda: provider.run_agent_turn_batch("task", [], route="arnold"),
    ]
    for call in calls:
        with pytest.raises(provider.ProviderError) as exc_info:
            call()
        assert exc_info.value.fixture_error["code"] == "forced_scenario_not_found"
        assert exc_info.value.fixture["fallback_used"] is False


def test_all_provider_entrypoints_preserve_corruption_refusal(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Corrupt fixture content stays typed through every composed caller."""
    from vibecomfy.comfy_nodes.agent import provider

    root = tmp_path / "sessions"
    _write_fixture(root, content={"not": "text"})
    _reset_fixture_caches(monkeypatch, root)
    monkeypatch.setenv("VIBECOMFY_FIXTURE_SCENARIO", "session")
    monkeypatch.setattr(provider, "_load_arnold_runtime", lambda: fixture_provider)
    calls = [
        lambda: provider.run_agent_turn("task", "", route="arnold"),
        lambda: provider.run_agent_turn_delta("task", "{}", route="arnold"),
        lambda: provider.run_agent_turn_batch("task", [], route="arnold"),
    ]
    for call in calls:
        with pytest.raises(provider.ProviderError) as exc_info:
            call()
        assert exc_info.value.fixture_error["kind"] == "fixture_corruption"
        assert exc_info.value.fixture_error["code"] == "fixture_content_invalid"
        assert exc_info.value.fixture["match_kind"] == "forced_missing"


def test_fixture_provenance_survives_batch_normalization() -> None:
    """Provider evidence retains fixture identity and fallback provenance."""
    _assert_has_fixtures()
    from vibecomfy.comfy_nodes.agent import provider

    raw = fixture_provider.run_agent_turn_batch(
        task="Bypass the video VAE decode node",
        route="deepseek",
    )
    normalized = provider._normalize_batch_response(
        raw,
        route="deepseek",
        model="agent-edit",
    )
    assert normalized.audit_metadata["fixture"] == raw["fixture"]


def test_fixture_delta_sidecar_survives_strict_provider_normalization(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Delta wire keys stay strict while its audit sidecar reaches evidence."""
    _assert_has_fixtures()
    from vibecomfy.comfy_nodes.agent import provider

    monkeypatch.setattr(provider, "_load_arnold_runtime", lambda: fixture_provider)
    normalized = provider.run_agent_turn_delta(
        "Bypass the video VAE decode node",
        "{}",
        route="arnold",
    )
    assert normalized.audit_metadata["fixture"]["match_kind"] == "substring"


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


# ── fixture-root authority ──────────────────────────────────────────────────

def test_repo_root_fallback_uses_checkout_fixture_corpus_from_neutral_cwd(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The source-checkout fallback is independent of CWD and package depth."""
    monkeypatch.delenv("REPO_ROOT", raising=False)
    monkeypatch.delenv("VIBECOMFY_FIXTURE_DIR", raising=False)
    monkeypatch.chdir(Path("/tmp"))
    root = fixture_provider._fixture_root()
    assert root == Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "editor_sessions"
    assert (root / "manifest.json").is_file()
    manifest = fixture_provider._load_manifest()
    assert len(manifest) > 0
    result = fixture_provider.run_agent_turn_batch(
        task="Bypass the video VAE decode node",
        route="arnold",
    )
    assert result["fixture"]["key"]
    assert result["fallback_used"] is False


def test_explicit_fixture_dir_is_execution_authority(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """A valid custom corpus is the same corpus the launcher preflights."""
    custom = tmp_path / "custom-fixtures"
    _write_fixture(
        custom,
        key="custom-key",
        task="custom authority",
        content="custom authority\n```batch\ndone()\n```",
    )
    monkeypatch.setenv("VIBECOMFY_FIXTURE_DIR", str(custom))
    monkeypatch.setenv("REPO_ROOT", str(tmp_path / "wrong-repo"))
    _reset_fixture_caches(monkeypatch, custom)
    assert fixture_provider._fixture_root() == custom
    assert fixture_provider.readiness(route="arnold")["ready"] is True
    result = fixture_provider.run_agent_turn_batch(task="custom authority", route="arnold")
    assert result["fixture"]["key"] == "custom-key"
    assert "custom authority" in result["content"]


@pytest.mark.parametrize("corpus_kind", ["missing", "empty", "file"])
def test_missing_or_empty_explicit_fixture_dir_is_typed_unavailable(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    corpus_kind: str,
) -> None:
    root = tmp_path / corpus_kind
    if corpus_kind == "empty":
        root.mkdir()
        (root / "manifest.json").write_text("{}")
    elif corpus_kind == "file":
        root.write_text("not a fixture directory")
    monkeypatch.setenv("VIBECOMFY_FIXTURE_DIR", str(root))
    monkeypatch.delenv("REPO_ROOT", raising=False)
    _reset_fixture_caches(monkeypatch, root)
    status = fixture_provider.readiness(route="arnold")
    assert status["ready"] is False
    assert status["ok"] is False
    assert status["error"]["kind"] == "fixture_unavailable"
    assert status["error"]["code"] in {"fixture_root_missing", "empty_manifest"}
    for call in (
        lambda: fixture_provider.run_agent_turn(
            task="anything", python_source="", route="arnold"
        ),
        lambda: fixture_provider.run_agent_turn_delta(
            task="anything", projection="{}", op_schema={}, route="arnold"
        ),
        lambda: fixture_provider.run_agent_turn_batch(task="anything", route="arnold"),
    ):
        result = call()
        assert result["error"]["kind"] == "fixture_unavailable"
        assert result["fallback_used"] is False
        assert "done()" not in str(result)


def test_repo_root_is_used_when_custom_fixture_dir_is_unset(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    repo = tmp_path / "repo"
    repo_fixture = repo / "tests" / "fixtures" / "editor_sessions"
    _write_fixture(repo_fixture, key="repo-key", task="repo authority")
    custom = tmp_path / "custom"
    _write_fixture(custom, key="custom-key", task="custom authority")
    monkeypatch.setenv("REPO_ROOT", str(repo))
    monkeypatch.setenv("VIBECOMFY_FIXTURE_DIR", str(custom))
    _reset_fixture_caches(monkeypatch, custom)
    assert fixture_provider._fixture_root() == custom
    monkeypatch.delenv("VIBECOMFY_FIXTURE_DIR")
    _reset_fixture_caches(monkeypatch, repo_fixture)
    assert fixture_provider._fixture_root() == repo_fixture
    result = fixture_provider.run_agent_turn_batch(task="repo authority", route="arnold")
    assert result["fixture"]["key"] == "repo-key"


def test_warm_fixture_root_switch_uses_new_same_key_content_and_metadata(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Changing the public root invalidates key-only fixture caches."""
    root_a = tmp_path / "corpus-a"
    root_b = tmp_path / "corpus-b"
    _write_fixture(
        root_a,
        key="shared-key",
        task="shared task",
        content="corpus A\n```batch\nfrom_a()\n```",
        metadata={"corpus": "A"},
    )
    _write_fixture(
        root_b,
        key="shared-key",
        task="shared task",
        content="corpus B\n```batch\nfrom_b()\n```",
        metadata={"corpus": "B"},
    )
    monkeypatch.setenv("VIBECOMFY_FIXTURE_DIR", str(root_a))
    _reset_fixture_caches(monkeypatch, root_a)
    monkeypatch.setattr(fixture_provider, "_FIXTURE_ROOT", None)

    first = fixture_provider.run_agent_turn_batch(task="shared task", route="arnold")
    assert first["content"].startswith("corpus A")
    assert fixture_provider._load_fixture_metadata("shared-key")["corpus"] == "A"

    monkeypatch.setenv("VIBECOMFY_FIXTURE_DIR", str(root_b))
    second = fixture_provider.run_agent_turn_batch(task="shared task", route="arnold")
    assert second["content"].startswith("corpus B")
    assert second["fixture"]["key"] == "shared-key"
    assert fixture_provider._load_fixture_metadata("shared-key")["corpus"] == "B"
    assert fixture_provider._DOCUMENT_CACHE_ROOT == root_b
    assert fixture_provider._MANIFEST_CACHE_ROOT == root_b


@pytest.mark.parametrize(
    ("corpus_kind", "expected_kind", "expected_code"),
    [
        ("missing", "fixture_unavailable", "fixture_root_missing"),
        ("empty", "fixture_unavailable", "empty_manifest"),
        ("malformed", "fixture_corruption", "manifest_unreadable"),
    ],
)
def test_warm_fixture_then_invalid_root_refuses_without_stale_content(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    corpus_kind: str,
    expected_kind: str,
    expected_code: str,
) -> None:
    """A newly selected unusable root cannot replay the previous corpus."""
    root_a = tmp_path / "corpus-a"
    _write_fixture(
        root_a,
        key="shared-key",
        task="shared task",
        content="corpus A\n```batch\nfrom_a()\n```",
        metadata={"corpus": "A"},
    )
    invalid = tmp_path / corpus_kind
    if corpus_kind == "empty":
        invalid.mkdir()
        (invalid / "manifest.json").write_text("{}")
    elif corpus_kind == "malformed":
        invalid.mkdir()
        (invalid / "manifest.json").write_text("not json")

    monkeypatch.setenv("VIBECOMFY_FIXTURE_DIR", str(root_a))
    _reset_fixture_caches(monkeypatch, root_a)
    monkeypatch.setattr(fixture_provider, "_FIXTURE_ROOT", None)
    warm = fixture_provider.run_agent_turn_batch(task="shared task", route="arnold")
    assert warm["content"].startswith("corpus A")

    monkeypatch.setenv("VIBECOMFY_FIXTURE_DIR", str(invalid))
    result = fixture_provider.run_agent_turn_batch(task="shared task", route="arnold")
    assert result["content"] == ""
    assert result["error"]["kind"] == expected_kind
    assert result["error"]["code"] == expected_code
    assert "corpus A" not in str(result)
    assert fixture_provider._DOCUMENT_CACHE_ROOT == invalid
    assert fixture_provider._MANIFEST_CACHE_ROOT == invalid
    assert fixture_provider._CONTENT_CACHE == {}
    assert fixture_provider._METADATA_CACHE == {}


def test_blank_fixture_dir_uses_private_override_before_repo_root(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Blank environment values do not mask the test override or repo root."""
    custom = tmp_path / "custom"
    _write_fixture(custom, key="custom-key", task="custom authority")
    monkeypatch.setenv("VIBECOMFY_FIXTURE_DIR", "  \t")
    monkeypatch.setenv("REPO_ROOT", str(tmp_path / "wrong-repo"))
    _reset_fixture_caches(monkeypatch, custom)
    assert fixture_provider._fixture_root() == custom
    result = fixture_provider.run_agent_turn_batch(task="custom authority", route="arnold")
    assert result["fixture"]["key"] == "custom-key"

    monkeypatch.setattr(fixture_provider, "_FIXTURE_ROOT", None)
    monkeypatch.setattr(fixture_provider, "_MANIFEST_CACHE", None)
    monkeypatch.setattr(fixture_provider, "_MANIFEST_CACHE_ROOT", None)
    repo_fixture = tmp_path / "wrong-repo" / "tests" / "fixtures" / "editor_sessions"
    _write_fixture(repo_fixture, key="repo-key", task="repo authority")
    assert fixture_provider._fixture_root() == repo_fixture


def test_repo_root_env_var_takes_priority(tmp_path: Path) -> None:
    """When REPO_ROOT is set, it is used directly."""
    os.environ["REPO_ROOT"] = str(tmp_path)
    try:
        root = fixture_provider._repo_root()
        assert root == tmp_path
    finally:
        os.environ.pop("REPO_ROOT", None)
