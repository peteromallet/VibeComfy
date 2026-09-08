from __future__ import annotations

import argparse

from vibecomfy.commands.port._shared import _build_conversion_provider


def _args(**overrides: object) -> argparse.Namespace:
    values = {
        "runtime_object_info": True,
        "server_url": None,
        "object_info_cache": None,
        "no_object_info_cache": True,
    }
    values.update(overrides)
    return argparse.Namespace(**values)


def test_runtime_port_provider_reuses_active_managed_session(monkeypatch) -> None:
    monkeypatch.setattr(
        "vibecomfy.runtime.session.find_active_session",
        lambda: "http://127.0.0.1:8291",
    )
    args = _args()

    provider = _build_conversion_provider(args)

    assert args.server_url == "http://127.0.0.1:8291"
    assert provider._runtime is not None
    assert provider._runtime.server_url == "http://127.0.0.1:8291"
    assert provider._runtime.cache_enabled is False


def test_runtime_port_provider_keeps_one_shot_fallback_without_session(monkeypatch) -> None:
    monkeypatch.setattr("vibecomfy.runtime.session.find_active_session", lambda: None)
    args = _args()

    provider = _build_conversion_provider(args)

    # No active session means RuntimeSchemaProvider retains its existing
    # one-shot managed-server fallback; no stale URL is invented.
    assert args.server_url is None
    assert provider._runtime is not None
    assert provider._runtime.server_url is None
