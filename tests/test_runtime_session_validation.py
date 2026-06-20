from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

import pytest

import vibecomfy.runtime.prompt as prompt_module
import vibecomfy.runtime.session as session_module
from vibecomfy.contracts import (
    INTENT_CODE_MAX_BYTES,
    RUNTIME_CODE_CONTRACT_VERSION,
    RUNTIME_CODE_EXECUTION_MODE,
    RUNTIME_CODE_POLICY_VERSION,
    intent_node_properties,
)
from vibecomfy.errors import SchemaValidationError
from vibecomfy.runtime.session import (
    EmbeddedSession,
    ServerSession,
    SessionConfig,
    _prepare_prompt_async,
    _warm_schema_provider,
)
from vibecomfy.schema import InputSpec, NodeSchema
from vibecomfy.schema.cache import write_object_info_cache
from vibecomfy.workflow import VibeNode, VibeWorkflow, WorkflowSource

from tests._runtime_session_helpers import (
    WarmProvider,
    _workflow,
    fake_comfy,  # noqa: F401 -- pytest fixture imported for use in tests
    fake_server,  # noqa: F401 -- pytest fixture imported for use in tests
    _patch_fast_runtime_run,
)


class _StrictProvider:
    """Pre-warmed schema provider that only knows one class type.

    Any workflow node whose class_type is not in _known_classes will trigger
    an unknown_class_type validation error → SchemaValidationError.
    """

    def __init__(self, known_classes: dict[str, Any]) -> None:
        self._object_info: dict[str, Any] = {"ready": True}
        self._known_classes = known_classes

    def schemas(self) -> dict[str, Any]:
        return self._known_classes

    def get_schema(self, class_type: str) -> Any | None:
        return self._known_classes.get(class_type)


def test_async_warmup_populates_cache_then_validates() -> None:
    provider = WarmProvider()

    async def run_prepare() -> dict:
        return await _prepare_prompt_async(
            _workflow(),
            backend="api",
            schema_provider=provider,
            on_unavailable=lambda msg: (_ for _ in ()).throw(AssertionError(msg)),
        )

    api = asyncio.run(run_prepare())

    assert provider.object_info_calls == 1
    assert provider._object_info == {"ready": True}
    assert api["1"]["inputs"]["ckpt_name"] == "model-a.safetensors"


def test_session_caches_schema_provider_across_runs(
    fake_server, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    provider = WarmProvider()
    built_for: list[str | None] = []

    def fake_build(server_url: str | None):
        built_for.append(server_url)
        return provider

    monkeypatch.setattr(session_module, "_build_schema_provider", fake_build)

    async def run_twice() -> None:
        session = ServerSession(SessionConfig(port=8200))
        try:
            await session.run(_workflow())
            await session.run(_workflow(seed=2))
        finally:
            await session.stop()

    asyncio.run(run_twice())

    assert built_for == ["http://127.0.0.1:8200"]
    assert provider.object_info_calls == 1
    assert len(fake_server) == 1


def test_provider_unavailable_falls_back_to_structural_with_error_and_metadata(
    fake_server, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    monkeypatch.chdir(tmp_path)

    class UnavailableProvider:
        _object_info = None

        async def object_info_async(self):
            raise OSError("offline")

    monkeypatch.setattr(session_module, "_build_schema_provider", lambda server_url: UnavailableProvider())

    metadata_paths: list[Path] = []

    async def run_twice() -> None:
        session = ServerSession(SessionConfig(port=8200))
        try:
            first = await session.run(_workflow())
            second = await session.run(_workflow(seed=2))
            metadata_paths.extend([Path(first.metadata_path), Path(second.metadata_path)])
        finally:
            await session.stop()

    with caplog.at_level("ERROR", logger=session_module.__name__):
        asyncio.run(run_twice())

    assert any(record.levelname == "ERROR" and "schema validation skipped for class types" in record.message for record in caplog.records)
    metadata = session_module.json.loads(metadata_paths[0].read_text(encoding="utf-8"))
    assert metadata["schema_validation_skipped"] == ["CheckpointLoaderSimple", "KSampler"]


def test_schema_degradation_env_offramp_downgrades_to_warning(
    fake_server, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("VIBECOMFY_SCHEMA_WARN_ONLY", "1")

    class UnavailableProvider:
        _object_info = None

        async def object_info_async(self):
            raise OSError("offline")

    monkeypatch.setattr(session_module, "_build_schema_provider", lambda server_url: UnavailableProvider())

    async def run_once() -> None:
        session = ServerSession(SessionConfig(port=8200))
        try:
            await session.run(_workflow())
        finally:
            await session.stop()

    with caplog.at_level("WARNING", logger=session_module.__name__):
        asyncio.run(run_once())

    assert any(record.levelname == "WARNING" and "schema validation skipped for class types" in record.message for record in caplog.records)


def test_server_session_validates_against_started_url(
    fake_server, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    built_for: list[str | None] = []
    prepared_with: list[object | None] = []

    def fake_build(server_url: str | None):
        provider = object()
        built_for.append(server_url)
        return provider

    async def fake_prepare(workflow, *, backend, schema_provider, on_unavailable, cache_only=False):
        prepared_with.append(schema_provider)
        return workflow.compile(backend=backend)

    monkeypatch.setattr(session_module, "_build_schema_provider", fake_build)
    monkeypatch.setattr(session_module, "_prepare_prompt_async", fake_prepare)

    async def run_once() -> None:
        session = ServerSession(SessionConfig(port=8200))
        try:
            await session.run(_workflow())
            assert session.url == "http://127.0.0.1:8200"
        finally:
            await session.stop()

    asyncio.run(run_once())

    assert built_for == ["http://127.0.0.1:8200"]
    assert len(prepared_with) == 1


def test_prepare_prompt_async_preserves_runtime_code_with_local_builtin_schema() -> None:
    provider = _StrictProvider(
        {
            "CheckpointLoaderSimple": NodeSchema(
                "CheckpointLoaderSimple",
                None,
                {"ckpt_name": InputSpec("STRING")},
                [],
            )
        }
    )
    workflow = VibeWorkflow("runtime-intent", WorkflowSource("runtime-intent"))
    workflow.nodes["1"] = VibeNode(
        "1",
        "vibecomfy.code",
        inputs={"value": 41},
        metadata={
            "_ui": {
                "properties": intent_node_properties(
                    kind="code",
                    uid="runtime-code",
                    intent={"source": "value + 1", "spec": "increment"},
                    inputs=[("value", "INT")],
                    outputs=[("result", "JSON")],
                    extra_vibecomfy={
                        "runtime": {
                            "runtime_backed": True,
                            "runtime_contract_version": RUNTIME_CODE_CONTRACT_VERSION,
                            "execution_mode": RUNTIME_CODE_EXECUTION_MODE,
                            "timeout_ms": 250,
                            "max_source_bytes": INTENT_CODE_MAX_BYTES,
                            "allowed_builtins": ["abs", "len", "min", "max", "round"],
                            "redaction_policy": ["source_hash_only", "closed_set_redaction"],
                            "policy_version": RUNTIME_CODE_POLICY_VERSION,
                            "passthrough_on_non_json": False,
                        }
                    },
                )
            }
        },
    )

    async def run_prepare() -> dict:
        return await _prepare_prompt_async(
            workflow,
            backend="api",
            schema_provider=provider,
            on_unavailable=lambda msg: (_ for _ in ()).throw(AssertionError(msg)),
        )

    api = asyncio.run(run_prepare())

    assert api["1"]["class_type"] == "vibecomfy.code"
    assert api["1"]["inputs"]["value"] == 41
    assert api["1"]["inputs"]["source"] == "value + 1"
    assert api["1"]["inputs"]["spec"] == "increment"
    assert api["1"]["inputs"]["io"] == {"inputs": [["value", "INT"]], "outputs": [["result", "JSON"]]}
    assert api["1"]["inputs"]["execution_mode"] == RUNTIME_CODE_EXECUTION_MODE


def test_env_var_disables_gate(
    fake_server, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("VIBECOMFY_SCHEMA_VALIDATE", "0")

    async def run_once() -> ServerSession:
        session = ServerSession(SessionConfig(port=8200))
        try:
            await session.run(_workflow())
            return session
        finally:
            await session.stop()

    session = asyncio.run(run_once())

    assert session._schema_provider is None


def test_embedded_path_does_not_spawn_extra_comfy_server(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    entered = False

    class Provider:
        cache_path = tmp_path / "missing-object-info.json"
        _object_info = None

    @asynccontextmanager
    async def fail_if_entered(*args, **kwargs):
        nonlocal entered
        entered = True
        yield "http://should-not-start.test"

    unavailable: list[str] = []
    monkeypatch.setattr("vibecomfy.runtime.server.comfy_server", fail_if_entered)

    effective = asyncio.run(
        _warm_schema_provider(
            Provider(),
            on_unavailable=unavailable.append,
            cache_only=True,
        )
    )

    assert effective is None
    assert entered is False
    assert len(unavailable) == 1
    assert "using structural validation only" in unavailable[0]


def test_cache_only_warmup_rejects_runtime_fingerprint_mismatch(tmp_path: Path) -> None:
    cache_path = tmp_path / "object_info.stale-runtime.json"
    write_object_info_cache(
        cache_path,
        {"CheckpointLoaderSimple": {"input": {"required": {"ckpt_name": ["STRING", {}]}}}},
        runtime_fingerprint="stale-runtime",
    )

    class Provider:
        def __init__(self) -> None:
            self.cache_path = cache_path
            self._object_info = None

        def _cache_validation_expected(self) -> dict[str, str]:
            return {"runtime_fingerprint": "fresh-runtime"}

    for warm in (_warm_schema_provider, prompt_module._warm_schema_provider):
        provider = Provider()
        unavailable: list[str] = []

        effective = asyncio.run(warm(provider, on_unavailable=unavailable.append, cache_only=True))

        assert effective is None
        assert provider._object_info is None
        assert len(unavailable) == 1
        assert "cache_runtime_fingerprint_mismatch" in unavailable[0]
        assert "using structural validation only" in unavailable[0]


def test_cache_only_prepare_reports_cache_mismatch_and_skipped_classes(tmp_path: Path) -> None:
    cache_path = tmp_path / "object_info.stale-runtime.json"
    write_object_info_cache(
        cache_path,
        {"CheckpointLoaderSimple": {"input": {"required": {"ckpt_name": ["STRING", {}]}}}},
        runtime_fingerprint="stale-runtime",
    )

    class Provider:
        def __init__(self) -> None:
            self.cache_path = cache_path
            self._object_info = None

        def _cache_validation_expected(self) -> dict[str, str]:
            return {"runtime_fingerprint": "fresh-runtime"}

    unavailable: list[str] = []
    api = asyncio.run(
        _prepare_prompt_async(
            _workflow(),
            backend="api",
            schema_provider=Provider(),
            on_unavailable=unavailable.append,
            cache_only=True,
        )
    )

    assert api["1"]["class_type"] == "CheckpointLoaderSimple"
    assert api.schema_validation_skipped == ["CheckpointLoaderSimple", "KSampler"]
    assert len(unavailable) == 2
    assert "cache_runtime_fingerprint_mismatch" in unavailable[0]
    assert unavailable[1] == "schema validation skipped for class types: CheckpointLoaderSimple, KSampler"


def _patch_watchdog_and_flush(monkeypatch: pytest.MonkeyPatch) -> None:
    """Patch only the watchdog and flush helpers, leaving schema/prepare paths intact."""

    async def fake_maybe_flush(_session, _fp):
        return None

    async def fake_start_watchdog(*, server_url, client_id, api_dict):
        return object()

    async def fake_finalize_watchdog(_watchdog, *, run_dir, reason):
        return None

    monkeypatch.setattr(session_module, "_maybe_flush_for_policy", fake_maybe_flush)
    monkeypatch.setattr(session_module, "_start_watchdog", fake_start_watchdog)
    monkeypatch.setattr(session_module, "_finalize_watchdog", fake_finalize_watchdog)


def _strict_provider() -> _StrictProvider:
    """Pre-warmed provider that knows only CheckpointLoaderSimple; KSampler triggers rejection."""
    return _StrictProvider(
        {
            "CheckpointLoaderSimple": NodeSchema(
                "CheckpointLoaderSimple", None, {"ckpt_name": InputSpec("STRING")}, []
            )
        }
    )


def test_embedded_session_rejects_schema_invalid_workflow(
    fake_comfy,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Embedded path raises SchemaValidationError for a schema-backed unknown class type."""
    monkeypatch.chdir(tmp_path)
    _patch_watchdog_and_flush(monkeypatch)
    monkeypatch.setattr(session_module, "_build_schema_provider", lambda _url: _strict_provider())

    async def run_once() -> None:
        session = EmbeddedSession()
        try:
            await session.run(_workflow())
        finally:
            await session.stop()

    with pytest.raises(SchemaValidationError):
        asyncio.run(run_once())


def test_server_session_rejects_schema_invalid_workflow(
    fake_server,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Server path raises SchemaValidationError for the same schema-backed unknown class type."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(session_module, "_build_schema_provider", lambda _url: _strict_provider())

    async def run_once() -> None:
        session = ServerSession(SessionConfig(port=8200))
        try:
            await session.run(_workflow())
        finally:
            await session.stop()

    with pytest.raises(SchemaValidationError):
        asyncio.run(run_once())


def test_embedded_session_schema_validate_env_off_ramp(
    fake_comfy,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """VIBECOMFY_SCHEMA_VALIDATE=0 disables the schema gate for embedded sessions."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("VIBECOMFY_SCHEMA_VALIDATE", "0")
    _patch_watchdog_and_flush(monkeypatch)

    async def run_once() -> EmbeddedSession:
        session = EmbeddedSession()
        try:
            await session.run(_workflow())
            return session
        finally:
            await session.stop()

    session = asyncio.run(run_once())
    assert session._schema_provider is None


def test_embedded_and_server_schema_validate_env_off_ramp_parity(
    fake_comfy,
    fake_server,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """VIBECOMFY_SCHEMA_VALIDATE=0 disables the schema gate consistently for both embedded and server paths."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("VIBECOMFY_SCHEMA_VALIDATE", "0")
    _patch_watchdog_and_flush(monkeypatch)

    embedded_provider = []
    server_provider = []

    async def run_embedded() -> None:
        session = EmbeddedSession()
        try:
            await session.run(_workflow())
            embedded_provider.append(session._schema_provider)
        finally:
            await session.stop()

    async def run_server() -> None:
        session = ServerSession(SessionConfig(port=8200))
        try:
            await session.run(_workflow())
            server_provider.append(session._schema_provider)
        finally:
            await session.stop()

    asyncio.run(run_embedded())
    asyncio.run(run_server())

    assert embedded_provider == [None]
    assert server_provider == [None]
