from __future__ import annotations

import json
from types import SimpleNamespace

import pytest


@pytest.fixture
def info_module(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("VIBECOMFY_HEADLESS", "1")
    from vibecomfy import comfy_nodes

    return comfy_nodes


def _set_git_results(
    monkeypatch: pytest.MonkeyPatch,
    *,
    sha: str | None = "a" * 40,
    status: str | None = "",
    diagnostic: object | None = None,
) -> None:
    from vibecomfy import _git_utils

    def fake_git_stdout_result(repo_root, args):
        del repo_root
        stdout = sha if args == ["rev-parse", "HEAD"] else status
        return SimpleNamespace(stdout=stdout, diagnostic=diagnostic)

    monkeypatch.setattr(_git_utils, "git_stdout_result", fake_git_stdout_result)


def test_source_serving_has_stable_content_identity(info_module, monkeypatch):
    _set_git_results(monkeypatch)
    monkeypatch.setattr(info_module, "WEB_DIRECTORY", "./web")
    monkeypatch.setattr(info_module, "_web_source_hash", lambda: "123456789abc")

    first = info_module._info_payload()
    second = info_module._info_payload()

    assert first == second
    assert first == {
        "info_contract_version": 1,
        "process_start_id": info_module._PROCESS_START_ID,
        "start_time_utc": info_module._utc_isoformat(info_module._MODULE_START_AT_UTC),
        "git_sha": "a" * 40,
        "git_dirty": False,
        "git_state": "clean",
        "web_source_hash": "123456789abc",
        "web_source_state": "identified",
        "served_asset_kind": "source",
        "served_asset_id": "source:123456789abc",
        "served_asset_state": "identified",
        "runtime_modes": {
            "headless": True,
            "dynamic_io": False,
            "runtime_module": "default",
            "demo_picker": False,
            "agentic_replay": False,
        },
        "remediation": [],
    }


def test_cache_busted_dist_serving_uses_hash_identifier(info_module, monkeypatch):
    _set_git_results(monkeypatch)
    monkeypatch.setattr(info_module, "WEB_DIRECTORY", "./web_dist/123456789abc")
    monkeypatch.setattr(info_module, "_web_source_hash", lambda: "123456789abc")

    payload = info_module._info_payload()

    assert payload["served_asset_kind"] == "cache_busted_dist"
    assert payload["served_asset_id"] == "dist:123456789abc"
    assert payload["served_asset_state"] == "identified"


def test_missing_git_metadata_is_closed_set_and_actionable(info_module, monkeypatch):
    secret = "/home/private-user/repository-with-a-secret"
    _set_git_results(
        monkeypatch,
        sha=None,
        status=None,
        diagnostic=RuntimeError(secret),
    )
    monkeypatch.setattr(info_module, "_web_source_hash", lambda: "123456789abc")
    # Pin the served-asset dimension so remediation is the closed set for the
    # missing-git problem alone; without this the checkout's real web_dist hash
    # (which differs from the fake hash) adds restart_with_matching_web_assets.
    monkeypatch.setattr(info_module, "WEB_DIRECTORY", "./web")

    payload = info_module._info_payload()

    assert payload["git_sha"] is None
    assert payload["git_dirty"] is None
    assert payload["git_state"] == "unavailable"
    assert payload["remediation"] == ["restore_git_metadata"]
    assert secret not in json.dumps(payload)


def test_dirty_checkout_is_part_of_identity(info_module, monkeypatch):
    _set_git_results(monkeypatch, status=" M vibecomfy/comfy_nodes/__init__.py\n")
    monkeypatch.setattr(info_module, "_web_source_hash", lambda: "123456789abc")

    payload = info_module._info_payload()

    assert payload["git_sha"] == "a" * 40
    assert payload["git_dirty"] is True
    assert payload["git_state"] == "dirty"


def test_hash_failure_never_uses_mutable_source_path_as_proof(info_module, monkeypatch):
    _set_git_results(monkeypatch)
    monkeypatch.setattr(info_module, "WEB_DIRECTORY", "./web")
    monkeypatch.setattr(info_module, "_web_source_hash", lambda: None)

    payload = info_module._info_payload()

    assert payload["web_source_hash"] is None
    assert payload["web_source_state"] == "unavailable"
    assert payload["served_asset_kind"] == "source"
    assert payload["served_asset_id"] is None
    assert payload["served_asset_state"] == "unavailable"
    assert payload["remediation"] == ["rebuild_web_assets"]


def test_environment_values_and_paths_are_never_reflected(info_module, monkeypatch):
    _set_git_results(monkeypatch)
    monkeypatch.setattr(info_module, "_web_source_hash", lambda: "123456789abc")
    secrets = {
        "VIBECOMFY_HEADLESS": "secret-headless-value",
        "VIBECOMFY_CODE_DYNAMIC_IO": "credential-dynamic-value",
        "VIBECOMFY_ARNOLD_RUNTIME_MODULE": "/home/alice/private/runtime.py",
        "VIBECOMFY_DEMO_PICKER": "secret-demo-value",
        "VIBECOMFY_AGENTIC_REPLAY": "secret-replay-value",
    }
    for name, value in secrets.items():
        monkeypatch.setenv(name, value)

    payload = info_module._info_payload()
    serialized = json.dumps(payload, sort_keys=True)

    assert payload["runtime_modes"] == {
        "headless": False,
        "dynamic_io": False,
        "runtime_module": "configured",
        "demo_picker": False,
        "agentic_replay": False,
    }
    for raw_value in secrets.values():
        assert raw_value not in serialized
    assert "/" not in serialized
    assert "WEB_DIRECTORY" not in payload
    assert not {
        "web_source_path",
        "web_dist_path",
        "served_web_path",
        "launch_flags",
        "git_branch",
        "git_diagnostic",
        "uptime_seconds",
    } & payload.keys()
