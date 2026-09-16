from __future__ import annotations

import argparse
from contextlib import asynccontextmanager
from typing import Any

import pytest

import vibecomfy.schema.provider as provider_module
import importlib
from vibecomfy.runtime.session import _schema_provider_provenance
from vibecomfy.schema import (
    TargetSchemaProvider,
    get_schema_provider,
)
from vibecomfy.schema.cache import runtime_fingerprint, write_object_info_cache
from vibecomfy.schema.provider import SchemaProviderError
from vibecomfy.schema.validate import validate_api_against_schema


runtime_run = importlib.import_module("vibecomfy.runtime.run")


def _target_server(monkeypatch: pytest.MonkeyPatch, payload: dict[str, Any]) -> list[str]:
    requested: list[str] = []

    @asynccontextmanager
    async def fake_server(*, server_url: str | None = None, log_path=None):
        requested.append(str(server_url))
        yield "http://active-target.test:8188"

    class FakeClient:
        def __init__(self, url: str) -> None:
            assert url == "http://active-target.test:8188"

        async def object_info(self) -> dict[str, Any]:
            return payload

    monkeypatch.setattr(provider_module, "comfy_server", fake_server)
    monkeypatch.setattr(provider_module, "ComfyClient", FakeClient)
    return requested


def test_target_provider_precedes_and_separates_historical_cache(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    requested = _target_server(monkeypatch, {"LiveNode": {"input": {}}})
    provider = TargetSchemaProvider(server_url="http://target.test:8188", cache_dir=tmp_path)
    write_object_info_cache(
        provider.cache_path,
        {"HistoricalNode": {"input": {}}},
        runtime_fingerprint=runtime_fingerprint("http://target.test:8188"),
        server_url="http://target.test:8188",
    )

    live = provider.get_schema("LiveNode")

    assert live is not None
    assert live.source_provider == "target_object_info"
    assert live.source_server_url == "http://active-target.test:8188"
    assert live.source_cache_path is None
    assert provider.get_schema("HistoricalNode") is None
    assert requested == ["http://target.test:8188"]
    provenance = _schema_provider_provenance(provider)
    assert provenance["authority"] == "live_target"
    assert provenance["fresh_target"] is True
    assert provenance["target_server_url"] == "http://active-target.test:8188"


def test_target_provider_fetch_and_validation_are_target_bound(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    _target_server(monkeypatch, {"TargetPresentNode": {"input": {}}})
    provider = get_schema_provider("auto", server_url="http://target.test:8188")

    present = validate_api_against_schema(
        {"1": {"class_type": "TargetPresentNode", "inputs": {}}}, provider
    )
    absent = validate_api_against_schema(
        {"1": {"class_type": "TargetAbsentNode", "inputs": {}}}, provider
    )

    assert present == []
    assert [issue.code for issue in absent] == ["unknown_class_type"]
    assert isinstance(provider, TargetSchemaProvider)


def test_target_provider_fails_closed_on_malformed_payload(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _target_server(monkeypatch, {"BrokenNode": []})
    provider = TargetSchemaProvider(server_url="http://target.test:8188", cache_dir=tmp_path)

    with pytest.raises(SchemaProviderError, match="object_info"):
        provider.get_schema("BrokenNode")

    assert provider._object_info is None
    assert not provider.cache_path.exists()


def test_run_sync_forwards_the_same_explicit_target_provider(monkeypatch: pytest.MonkeyPatch) -> None:
    provider = object()
    captured: dict[str, object] = {}

    async def fake_run(record, bundle, **kwargs):
        captured.update(kwargs)
        return object()

    monkeypatch.setattr(runtime_run, "run", fake_run)

    result = runtime_run.run_sync(object(), object(), schema_provider=provider)

    assert result is not None
    assert captured["schema_provider"] is provider


def test_external_run_command_reuses_target_provider_for_compile_and_run(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from vibecomfy.commands import run as run_command

    provider = object()
    observed: dict[str, object] = {}

    class Workflow:
        id = "target-run"
        inputs = {}

    class Bundle:
        workflow = Workflow()

        def require_canonical_authority(self, _action: str) -> None:
            return None

        def compile(self, **kwargs):
            observed["compile_provider"] = kwargs["schema_provider"]
            return object()

    monkeypatch.setattr(
        run_command,
        "get_schema_provider",
        lambda _prefer, *, server_url=None: provider,
    )
    monkeypatch.setattr(run_command, "load_bundle", lambda *args, **kwargs: Bundle())
    monkeypatch.setattr(
        run_command,
        "run_sync",
        lambda record, bundle, **kwargs: (
            observed.update(run_provider=kwargs["schema_provider"])
            or argparse.Namespace(
                run_id="run",
                prompt_id="prompt",
                metadata_path="metadata.json",
                log_path="comfy.log",
            )
        ),
    )

    args = argparse.Namespace(
        path="target.py",
        runtime="auto",
        server_url="http://target.test:8188",
        backend="api",
        prompt=None,
        seed=None,
        steps=None,
        memory_profile=None,
        ensure_packs=False,
        ensure_models=None,
        shared_models_root=None,
        session=None,
        runtime_root=None,
        restart_session=False,
        keep_warm=False,
        json=False,
        quiet_schema_degradation=False,
    )

    assert run_command._cmd_run(args) == 0
    assert observed == {"compile_provider": provider, "run_provider": provider}
